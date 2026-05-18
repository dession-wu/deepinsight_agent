import os
import sys
import json
import requests
from datetime import datetime
from contextlib import contextmanager
from openai import OpenAI

# 导入数据获取函数（独立模块，避免循环导入）
from data_fetchers import (
    fetch_cls_telegraph,
    fetch_eastmoney_industry_capital_flow,
    fetch_eastmoney_stock_spot
)

# 导入全局错误处理模块
from error_handler import (
    GlobalErrorHandler,
    ErrorFormatter,
    with_error_handling,
    ErrorHandlerConfig
)

# 导入记忆摘要模块
from memory_summarizer import (
    MemorySummarizer,
    SummarizerConfig
)

# 导入多智能体集成模块（可选）
try:
    from agent_integration import DeepInsightMultiAgent
    MULTI_AGENT_AVAILABLE = True
except ImportError:
    MULTI_AGENT_AVAILABLE = False

# 导入 Langfuse 监控模块（可选）
try:
    from langfuse_monitor import AgentMonitor, get_monitor, MonitoredOpenAIClient
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False

# ==========================================
# 1. 初始化大模型客户端
# ==========================================
# 导师注：这里使用的是通用 OpenAI SDK。如果你在国内，极力推荐使用 DeepSeek、Kimi 或通义千问等
# 只需要修改 api_key 和 base_url 即可无缝切换，完全不需要改下面的业务逻辑！
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY", "sk-ffd39ec0145b411a9f4233edd80b49aa"), # TODO: 换成你真实的大模型 API Key
    base_url="https://api.deepseek.com" # 如果你用国内模型（如DeepSeek），取消这行注释
)

# ==========================================
# 1.1 初始化全局错误处理器
# ==========================================
error_config = ErrorHandlerConfig()
error_handler = GlobalErrorHandler(
    client=client,
    auto_report=error_config.get("auto_report", True),
    max_history=error_config.get("max_history", 50)
)
# 安装全局异常捕获钩子
error_handler.install()

# ==========================================
# 1.2 初始化记忆摘要器
# ==========================================
summary_config = SummarizerConfig(
    max_messages_before_summary=10,      # 10条消息后触发摘要
    max_tokens_before_summary=3000,      # 3000 token后触发摘要
    summary_detail_level="medium",       # 中等详细程度
    max_summary_length=800,              # 摘要最大800字符
    summary_update_frequency=5,          # 每5轮更新一次
    preserve_full_history=True,          # 保留完整历史
    max_full_history_rounds=100          # 最大保留100轮
)
summarizer = MemorySummarizer(client=client, config=summary_config)

# ==========================================
# 1.5 财联社（CLS）数据获取工具
# ==========================================

def fetch_cls_telegraph(num_items: int = 20) -> str:
    """
    从财联社（CLS）电报接口获取最新的财经快讯。

    Args:
        num_items: 获取的新闻条数，默认 20 条，最大建议 50 条。

    Returns:
        格式化后的新闻字符串，适合直接输入给大模型。
    """
    url = "https://www.cls.cn/nodeapi/telegraphList"
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "refresh_type": "1",
        "order": "1",
        "rn": min(num_items, 50),
        "sv": "8.4.6",
        "sign": "8bc6630fbf8b4a195cd99b4da66ed07b"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://www.cls.cn/telegraph"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("error") != 0:
            return f"❌ 财联社接口返回错误: {data}"

        roll_data = data.get("data", {}).get("roll_data", [])
        if not roll_data:
            return "⚠️ 未从财联社获取到任何数据。"

        formatted_news = []
        for item in roll_data:
            ctime = item.get("ctime")
            time_str = datetime.fromtimestamp(ctime).strftime("%m-%d %H:%M") if ctime else "未知时间"
            title = item.get("title", "")
            content = item.get("content", "")
            # 财联社 content 通常已经包含标题，如果 content 为空则使用 brief
            if not content:
                content = item.get("brief", "")
            formatted_news.append(f"[{time_str}] {content}")

        return "\n\n".join(formatted_news)

    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求失败，无法连接财联社: {e}"
    except Exception as e:
        return f"❌ 处理财联社数据时发生错误: {e}"


# ==========================================
# 1.6 东方财富（Eastmoney）数据获取工具
# ==========================================

def fetch_eastmoney_industry_capital_flow() -> str:
    """
    从东方财富网获取行业板块资金流向排行数据。
    通过调用其内部 push2 接口（隐式 API）获取实时 JSON 数据。

    Returns:
        格式化后的行业资金流向字符串，适合直接输入给大模型。
    """
    # 东方财富行业资金流向接口
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",           # 页码
        "pz": "20",          # 每页条数
        "po": "1",           # 排序方向：1降序
        "np": "1",
        "fltt": "2",         # 浮点精度
        "invt": "2",
        "fid": "f62",        # 按主力净流入排序
        "fs": "m:90+t:2",    # 行业板块筛选条件
        "fields": "f12,f14,f2,f3,f62,f128,f140,f136,f141,f207,f208",
        "_": str(int(datetime.now().timestamp() * 1000))
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://data.eastmoney.com/bkzj/hy.html"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("data") is None:
            return "⚠️ 东方财富接口未返回数据，可能受反爬限制。"

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            return "⚠️ 未从东方财富获取到任何行业资金流向数据。"

        # 字段映射说明（f开头为东方财富内部字段编码）
        # f12: 板块代码, f14: 板块名称, f2: 最新价, f3: 涨跌幅
        # f62: 主力净流入(元), f128: 主力净流入占比, f140: 超大单净流入
        # f136: 超大单净流入占比, f141: 大单净流入, f207: 大单净流入占比
        formatted_lines = []
        formatted_lines.append("【行业板块资金流向排行】\n")

        for item in diff:
            name = item.get("f14", "未知板块")
            change_pct = item.get("f3", "-")
            main_inflow = item.get("f62", "-")
            main_inflow_pct = item.get("f128", "-")

            # 格式化数值
            change_str = f"{change_pct:.2f}%" if isinstance(change_pct, (int, float)) else "-"
            inflow_str = f"{main_inflow/10000:.2f}万" if isinstance(main_inflow, (int, float)) else "-"
            inflow_pct_str = f"{main_inflow_pct:.2f}%" if isinstance(main_inflow_pct, (int, float)) else "-"

            formatted_lines.append(
                f"• {name}: 涨跌幅 {change_str}, 主力净流入 {inflow_str} ({inflow_pct_str})"
            )

        return "\n".join(formatted_lines)

    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求失败，无法连接东方财富: {e}"
    except Exception as e:
        return f"❌ 处理东方财富数据时发生错误: {e}"


def fetch_eastmoney_stock_spot() -> str:
    """
    从东方财富网获取 A 股实时行情快照（全市场涨跌幅前20）。

    Returns:
        格式化后的股票行情字符串。
    """
    url = "https://push2.eastmoney.com/api/qt/clist/get"
    params = {
        "pn": "1",
        "pz": "20",
        "po": "1",
        "np": "1",
        "fltt": "2",
        "invt": "2",
        "fid": "f12",
        "fs": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23",  # 沪深A股
        "fields": "f12,f14,f2,f3,f4,f5,f6,f7,f8,f9,f10,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
        "_": str(int(datetime.now().timestamp() * 1000))
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Referer": "https://quote.eastmoney.com/"
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("data") is None:
            return "⚠️ 东方财富行情接口未返回数据。"

        diff = data.get("data", {}).get("diff", [])
        if not diff:
            return "⚠️ 未获取到股票行情数据。"

        formatted_lines = []
        formatted_lines.append("【A股实时行情快照】\n")

        for item in diff[:10]:  # 只展示前10条避免过长
            code = item.get("f12", "-")
            name = item.get("f14", "-")
            price = item.get("f2", "-")
            change_pct = item.get("f3", "-")
            change_amt = item.get("f4", "-")

            price_str = f"{price:.2f}" if isinstance(price, (int, float)) else "-"
            change_str = f"{change_pct:.2f}%" if isinstance(change_pct, (int, float)) else "-"
            amt_str = f"{change_amt:.2f}" if isinstance(change_amt, (int, float)) else "-"

            formatted_lines.append(
                f"• {name}({code}): 最新价 {price_str}, 涨跌幅 {change_str}, 涨跌额 {amt_str}"
            )

        return "\n".join(formatted_lines)

    except requests.exceptions.RequestException as e:
        return f"❌ 网络请求失败: {e}"
    except Exception as e:
        return f"❌ 处理行情数据时发生错误: {e}"

# ==========================================
# 2. 初始化“记忆”（Memory）
# ==========================================
# // 核心知识点：剥开高级框架的外衣，Agent 的所谓“人设”和“长期记忆”，底层就是一个简单的 List（数组）。
# 数组里的每一个字典，都是对话剧本里的一句台词。
messages_history =[
    # System Prompt (系统提示词)：这是 Agent 的灵魂，定义了它的能力边界和行事风格。
    {"role": "system", "content": (
        "你是一个名为 DeepInsight 的高级信息总结与分析智能体。你说话简明扼要，具有极强的逻辑拆解能力。"
        "你具备实时联网能力：当用户要求获取最新财经资讯、新闻、电报或提及'财联社'时，"
        "请调用你的工具获取财联社（CLS）最新电报数据，并基于这些数据进行分析、总结或回答。"
        "当用户要求获取股票行情、资金流向、板块排行或提及'东方财富'时，"
        "请调用你的工具获取东方财富（Eastmoney）实时行情与资金流向数据，并基于这些数据进行分析、总结或回答。"
    )}
]

print("🧠 DeepInsight Agent 已启动！(输入 'quit' 退出)")
print("-" * 50)

# ==========================================
# 1.3 初始化多智能体系统（可选）
# ==========================================
multi_agent = None
if MULTI_AGENT_AVAILABLE:
    try:
        multi_agent = DeepInsightMultiAgent(client, error_handler, summarizer)
        # 注意：多智能体系统需要异步初始化，在首次使用时初始化
        print("✅ 多智能体协作系统已加载")
    except Exception as e:
        print(f"⚠️ 多智能体系统加载失败: {e}")

# ==========================================
# 1.4 初始化 Langfuse 监控（可选）
# ==========================================
monitor = None
monitored_client = None
if LANGFUSE_AVAILABLE:
    try:
        monitor = get_monitor()
        if monitor.is_enabled():
            # 包装客户端以自动追踪所有 LLM 调用
            monitored_client = MonitoredOpenAIClient(client, monitor)
            print("✅ Langfuse 监控已加载")
            print(f"   追踪面板: https://cloud.langfuse.com")
        else:
            print("⚠️ Langfuse 监控未启用（检查配置）")
    except Exception as e:
        print(f"⚠️ Langfuse 监控加载失败: {e}")

# ==========================================
# 3. 开启核心对话循环 (Chat Loop)
# ==========================================

# 当前会话追踪ID（用于 Langfuse）
current_trace_id = None

while True:
    try:
        user_input = input("\n👤 提问: ")
    except EOFError:
        print("\n⚠️ 检测到输入流关闭，程序将安全退出。")
        if monitor and monitor.is_enabled():
            monitor.flush()
        break
    except KeyboardInterrupt:
        print("\n👋 用户中断，DeepInsight 已关闭。")
        if monitor and monitor.is_enabled():
            monitor.flush()
        break
    
    if user_input.lower() in ['quit', 'exit', 'q']:
        print("👋 DeepInsight 已关闭。")
        # 确保所有追踪数据被发送
        if monitor and monitor.is_enabled():
            monitor.flush()
        break

    # 使用 Langfuse 追踪整个对话（如果启用）
    trace_context = None
    if monitor and monitor.is_enabled():
        trace_context = monitor.trace_conversation(
            user_id="default_user",
            session_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
    
    # 进入追踪上下文
    with trace_context if trace_context else contextmanager(lambda: (yield None))() as trace:
        if trace:
            # trace 是 trace_id 字符串，不是对象
            current_trace_id = trace
            print(f"\n📊 已创建追踪: {monitor.get_trace_url(trace)}")
        
        # 检测用户意图，匹配不同的数据源
        # 财联社触发关键词
        cls_keywords = ["财联社", "电报", "快讯", "最新财经", "财经新闻", "资讯", "新闻"]
        # 东方财富触发关键词
        em_keywords = ["东方财富", "资金流向", "板块资金", "行业资金", "主力净流入", "行情", "股票行情", "A股行情"]

        needs_cls = any(kw in user_input for kw in cls_keywords)
        needs_em = any(kw in user_input for kw in em_keywords)

        user_content = user_input
        extra_data_parts = []

        if needs_cls:
            print("\n🌐 正在从财联社获取最新电报数据...")
            cls_data = fetch_cls_telegraph(num_items=20)
            if cls_data.startswith("❌") or cls_data.startswith("⚠️"):
                print(f"{cls_data}")
            else:
                print(f"✅ 成功获取财联社数据，共 {cls_data.count('[')} 条。")
            extra_data_parts.append(
                f"--- 以下为实时从财联社获取的最新电报数据 ---\n\n{cls_data}\n\n--- 财联社数据结束 ---"
            )
            
            # 记录数据获取到 Langfuse
            if monitor and monitor.is_enabled() and trace:
                monitor.log_span(
                    name="fetch_cailianshe",
                    metadata={"source": "cailianshe", "items_count": cls_data.count('[')}
                )

        if needs_em:
            print("\n📈 正在从东方财富获取资金流向数据...")
            em_capital = fetch_eastmoney_industry_capital_flow()
            if not em_capital.startswith("❌") and not em_capital.startswith("⚠️"):
                print("✅ 成功获取东方财富行业资金流向数据。")
                extra_data_parts.append(em_capital)
            else:
                print(f"{em_capital}")

            print("\n📊 正在从东方财富获取A股行情快照...")
            em_spot = fetch_eastmoney_stock_spot()
            if not em_spot.startswith("❌") and not em_spot.startswith("⚠️"):
                print("✅ 成功获取A股行情快照。")
                extra_data_parts.append(em_spot)
            else:
                print(f"{em_spot}")
            
            # 记录数据获取到 Langfuse
            if monitor and monitor.is_enabled() and trace:
                monitor.log_span(
                    name="fetch_eastmoney",
                    metadata={"source": "eastmoney", "has_capital": bool(em_capital), "has_spot": bool(em_spot)}
                )

        if extra_data_parts:
            user_content = (
                f"用户原始需求：{user_input}\n\n"
                + "\n\n".join(extra_data_parts)
                + "\n\n请基于以上实时数据回答用户的问题。"
            )

        # // 核心知识点 [记忆管理 A]：把用户的新问题，作为一个 'user' 角色的字典，追加到记忆数组的末尾
        messages_history.append({"role": "user", "content": user_content})

        try:
            # 检查是否需要生成摘要
            if summarizer.should_summarize(messages_history):
                print("\n📝 对话上下文较长，正在生成记忆摘要...")
                summary = summarizer.generate_summary(messages_history)
                if summary:
                    print(f"✅ 摘要生成完成（耗时{summary.generation_time_ms:.0f}ms）")
                    print(f"   完整度: {summary.completeness_score:.1%}, 冗余去除: {summary.redundancy_removal_ratio:.1%}")
                    # 压缩上下文
                    messages_history = summarizer.get_compressed_context(messages_history, keep_recent=4)
                    print(f"   上下文已压缩，保留最近4轮完整对话 + 摘要")
                    
                    # 记录摘要操作到 Langfuse
                    if monitor and monitor.is_enabled() and trace:
                        monitor.log_span(
                            name="memory_summarization",
                            metadata={
                                "completeness": summary.completeness_score,
                                "redundancy_removal": summary.redundancy_removal_ratio,
                                "generation_time_ms": summary.generation_time_ms
                            }
                        )

            # 向大模型发起请求，把【压缩后的记忆数组】都发过去
            # 使用受监控的客户端（如果启用）
            if monitored_client and monitor and monitor.is_enabled() and trace:
                # 使用监控包装器记录详细信息
                response = client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=messages_history,
                    temperature=0.3
                )
                
                # 手动记录到 Langfuse
                assistant_reply = response.choices[0].message.content
                usage = response.usage
                
                monitor.log_generation(
                    name="chat_completion",
                    model="deepseek-v4-flash",
                    prompt=json.dumps(messages_history, ensure_ascii=False)[:2000],
                    completion=assistant_reply[:1000],
                    usage={
                        "input": usage.prompt_tokens if usage else 0,
                        "output": usage.completion_tokens if usage else 0,
                        "total": usage.total_tokens if usage else 0
                    },
                    metadata={
                        "temperature": 0.3,
                        "has_data_fetch": needs_cls or needs_em
                    }
                )
            else:
                # 普通调用（无监控）
                response = client.chat.completions.create(
                    model="deepseek-v4-flash",
                    messages=messages_history,
                    temperature=0.3
                )
                assistant_reply = response.choices[0].message.content

            print(f"\n🤖 DeepInsight: {assistant_reply}")

            # // 核心知识点 [记忆管理 B]：把大模型的回复，作为一个 'assistant' 角色的字典，追加到记忆数组！
            messages_history.append({"role": "assistant", "content": assistant_reply})

        except Exception as e:
            # 使用全局错误处理器捕获和结构化处理错误
            structured_error = error_handler.capture_error(
                e,
                context="大模型API调用失败"
            )

            print(f"\n{'='*60}")
            print(f"❌ 网络或 API 发生错误")
            print(f"{'='*60}")
            print(ErrorFormatter.format_short(structured_error))

            # 如果出错了，要把刚才加进去的用户问题弹出来（撤回），否则记忆会错乱
            messages_history.pop()

            # 尝试让Agent自动处理错误
            if error_handler.auto_report:
                print("\n🔄 正在请求Agent进行错误自动修复...")
                agent_fix = error_handler.report_to_agent(structured_error)
                if agent_fix:
                    # 将Agent的修复建议添加到对话历史中
                    messages_history.append({
                        "role": "system",
                        "content": f"[错误自动修复建议] {agent_fix}"
                    })