"""
DeepInsight Agent 主程序

重构说明（第一阶段优化）：
1. 核心链路封装为 DeepInsightEngine 类，可同时供 CLI 与 FastAPI（api.py）调用；
2. 密钥与模型名统一从 config.py 读取（环境变量），代码中不再硬编码任何密钥；
3. 数据抓取函数统一收敛到 data_fetchers.py（以验证可用的财联社 telegraphList 实现为准），
   删除了本文件内重复的覆盖实现；
4. 多智能体框架（agent_integration.py / multi_agent_framework.py）未接入主链路，
   文件保留待后续阶段评估，本模块不再 import；
5. client 延迟初始化：无 OPENAI_API_KEY 时模块仍可正常导入（服务健康检查可用），
   仅在实际发起 LLM 调用时给出明确报错。
"""

import json
from contextlib import contextmanager
from datetime import datetime

from openai import OpenAI

import config
from config import validate_llm_config
from data_fetchers import (
    fetch_cls_telegraph,
    fetch_eastmoney_industry_capital_flow,
    fetch_eastmoney_stock_spot
)
from error_handler import GlobalErrorHandler, ErrorFormatter, ErrorHandlerConfig
from memory_summarizer import MemorySummarizer, SummarizerConfig

# 导入 Langfuse 监控模块（可选）
try:
    from langfuse_monitor import AgentMonitor, get_monitor
    LANGFUSE_AVAILABLE = True
except ImportError:
    LANGFUSE_AVAILABLE = False


class DeepInsightEngine:
    """
    DeepInsight 分析引擎：数据抓取 + LLM 分析的核心链路。

    用法：
        engine = DeepInsightEngine()
        reply = engine.chat("帮我看看今天的财联社快讯")
    """

    SYSTEM_PROMPT = (
        "你是一个名为 DeepInsight 的高级信息总结与分析智能体。你说话简明扼要，具有极强的逻辑拆解能力。"
        "你具备实时联网能力：当用户要求获取最新财经资讯、新闻、电报或提及'财联社'时，"
        "请调用你的工具获取财联社（CLS）最新电报数据，并基于这些数据进行分析、总结或回答。"
        "当用户要求获取股票行情、资金流向、板块排行或提及'东方财富'时，"
        "请调用你的工具获取东方财富（Eastmoney）实时行情与资金流向数据，并基于这些数据进行分析、总结或回答。"
    )

    CLS_KEYWORDS = ["财联社", "电报", "快讯", "最新财经", "财经新闻", "资讯", "新闻"]
    EM_KEYWORDS = ["东方财富", "资金流向", "板块资金", "行业资金", "主力净流入", "行情", "股票行情", "A股行情"]

    def __init__(self):
        # 延迟初始化：无 API Key 时仍可创建实例（供健康检查等场景使用）
        self._client = None
        self._error_handler = None
        self._summarizer = None
        self._monitor = None
        self.messages_history = [
            {"role": "system", "content": self.SYSTEM_PROMPT}
        ]

    # -----------------------------------------
    # 延迟初始化的组件（均从 config 读取配置）
    # -----------------------------------------

    @property
    def client(self) -> OpenAI:
        """OpenAI 兼容客户端（默认 DeepSeek）。缺失 API Key 时抛出明确错误。"""
        if self._client is None:
            validate_llm_config()
            self._client = OpenAI(
                api_key=config.OPENAI_API_KEY,
                base_url=config.OPENAI_BASE_URL
            )
        return self._client

    @property
    def error_handler(self) -> GlobalErrorHandler:
        if self._error_handler is None:
            error_config = ErrorHandlerConfig()
            self._error_handler = GlobalErrorHandler(
                client=self.client,
                auto_report=error_config.get("auto_report", True),
                max_history=error_config.get("max_history", 50)
            )
        return self._error_handler

    @property
    def summarizer(self) -> MemorySummarizer:
        if self._summarizer is None:
            summary_config = SummarizerConfig(
                max_messages_before_summary=10,
                max_tokens_before_summary=3000,
                summary_detail_level="medium",
                max_summary_length=800,
                summary_update_frequency=5,
                preserve_full_history=True,
                max_full_history_rounds=100
            )
            self._summarizer = MemorySummarizer(client=self.client, config=summary_config)
        return self._summarizer

    @property
    def monitor(self):
        """Langfuse 监控器（可选，默认关闭，未启用时返回 None）。"""
        if self._monitor is None and LANGFUSE_AVAILABLE:
            try:
                m = get_monitor()
                self._monitor = m if m.is_enabled() else False
            except Exception:
                self._monitor = False
        return self._monitor if self._monitor else None

    # -----------------------------------------
    # 数据抓取（基于关键词路由）
    # -----------------------------------------

    def _fetch_context_data(self, user_input: str) -> list:
        """按关键词检测用户意图，抓取对应数据源，返回附加数据片段列表。"""
        needs_cls = any(kw in user_input for kw in self.CLS_KEYWORDS)
        needs_em = any(kw in user_input for kw in self.EM_KEYWORDS)

        extra_data_parts = []

        if needs_cls:
            cls_data = fetch_cls_telegraph(num_items=20)
            if not (cls_data.startswith("❌") or cls_data.startswith("⚠️")):
                extra_data_parts.append(
                    f"--- 以下为实时从财联社获取的最新电报数据 ---\n\n{cls_data}\n\n--- 财联社数据结束 ---"
                )

        if needs_em:
            em_capital = fetch_eastmoney_industry_capital_flow()
            if not (em_capital.startswith("❌") or em_capital.startswith("⚠️")):
                extra_data_parts.append(em_capital)

            em_spot = fetch_eastmoney_stock_spot()
            if not (em_spot.startswith("❌") or em_spot.startswith("⚠️")):
                extra_data_parts.append(em_spot)

        return extra_data_parts

    # -----------------------------------------
    # 核心对话链路
    # -----------------------------------------

    def chat(self, user_input: str, user_id: str = "default_user") -> str:
        """
        处理一次用户输入，返回助手回复。

        链路：意图检测 -> 数据抓取 -> 上下文组装 -> 记忆压缩 -> LLM 调用 -> 记忆追加
        """
        trace_context = None
        monitor = self.monitor
        if monitor:
            trace_context = monitor.trace_conversation(
                user_id=user_id,
                session_id=f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )

        with trace_context if trace_context else contextmanager(lambda: (yield None))() as trace:
            # 1. 意图检测 + 数据抓取
            extra_data_parts = self._fetch_context_data(user_input)
            if extra_data_parts:
                user_content = (
                    f"用户原始需求：{user_input}\n\n"
                    + "\n\n".join(extra_data_parts)
                    + "\n\n请基于以上实时数据回答用户的问题。"
                )
            else:
                user_content = user_input

            self.messages_history.append({"role": "user", "content": user_content})

            try:
                # 2. 记忆压缩（对话较长时生成摘要并压缩上下文）
                if self.summarizer.should_summarize(self.messages_history):
                    summary = self.summarizer.generate_summary(self.messages_history)
                    if summary:
                        self.messages_history = self.summarizer.get_compressed_context(
                            self.messages_history, keep_recent=4
                        )
                        if monitor and trace:
                            monitor.log_span(
                                name="memory_summarization",
                                metadata={
                                    "completeness": summary.completeness_score,
                                    "redundancy_removal": summary.redundancy_removal_ratio,
                                    "generation_time_ms": summary.generation_time_ms
                                }
                            )

                # 3. LLM 调用（模型名从环境变量读取，默认 deepseek-chat）
                response = self.client.chat.completions.create(
                    model=config.MODEL_NAME,
                    messages=self.messages_history,
                    temperature=0.3
                )
                assistant_reply = response.choices[0].message.content

                # 4. 手动记录到 Langfuse（如果启用）
                if monitor and trace:
                    usage = response.usage
                    monitor.log_generation(
                        name="chat_completion",
                        model=config.MODEL_NAME,
                        prompt=json.dumps(self.messages_history, ensure_ascii=False)[:2000],
                        completion=assistant_reply[:1000],
                        usage={
                            "input": usage.prompt_tokens if usage else 0,
                            "output": usage.completion_tokens if usage else 0,
                            "total": usage.total_tokens if usage else 0
                        },
                        metadata={"temperature": 0.3, "has_data_fetch": bool(extra_data_parts)}
                    )

                self.messages_history.append({"role": "assistant", "content": assistant_reply})
                return assistant_reply

            except Exception as e:
                # 出错时撤回刚追加的用户消息，避免记忆错乱
                if self.messages_history and self.messages_history[-1]["role"] == "user":
                    self.messages_history.pop()

                structured_error = self.error_handler.capture_error(
                    e, context="大模型API调用失败"
                )
                return f"❌ 网络或 API 发生错误：\n{ErrorFormatter.format_short(structured_error)}"

    def close(self):
        """确保监控数据被发送。"""
        monitor = self.monitor
        if monitor and monitor.is_enabled():
            monitor.flush()


def main():
    """CLI 入口：交互式对话循环。"""
    engine = DeepInsightEngine()

    print("🧠 DeepInsight Agent 已启动！(输入 'quit' 退出)")
    print("-" * 50)

    # 提前校验 LLM 配置，缺失时给出明确提示（不打印密钥内容）
    try:
        validate_llm_config()
        print(f"   LLM: {config.OPENAI_BASE_URL} / 模型 {config.MODEL_NAME}")
    except RuntimeError as e:
        print(f"⚠️ {e}")

    while True:
        try:
            user_input = input("\n👤 提问: ")
        except EOFError:
            print("\n⚠️ 检测到输入流关闭，程序将安全退出。")
            engine.close()
            break
        except KeyboardInterrupt:
            print("\n👋 用户中断，DeepInsight 已关闭。")
            engine.close()
            break

        if user_input.lower() in ('quit', 'exit', 'q'):
            print("👋 DeepInsight 已关闭。")
            engine.close()
            break

        reply = engine.chat(user_input)
        print(f"\n🤖 DeepInsight: {reply}")


if __name__ == "__main__":
    main()