# DeepInsight Agent

<p align="center">
  <strong>基于大语言模型的智能金融分析助手</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python" />
  <img src="https://img.shields.io/badge/LangChain-OpenAI-green.svg" alt="LLM" />
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License" />
  <img src="https://img.shields.io/badge/Status-Active-brightgreen.svg" alt="Status" />
</p>

---

## 项目简介

DeepInsight Agent 是一个基于 OpenAI 兼容 API 的智能金融分析助手，具备实时数据获取、多智能体协作、记忆管理、错误处理和监控追踪等企业级能力。

### 核心特性

- **实时财经数据**：自动从财联社、东方财富获取最新行情
- **智能对话**：支持上下文记忆与自动摘要压缩
- **多智能体架构**：8种角色智能体协同工作
- **企业级错误处理**：结构化错误捕获与自动修复
- **全链路监控**：Langfuse 集成，追踪 Token 消耗与性能

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 语言 | Python 3.8+ |
| LLM 框架 | OpenAI SDK (兼容 DeepSeek/通义千问等) |
| 数据源 | 财联社 API / 东方财富 Web API |
| 监控追踪 | Langfuse |
| 架构模式 | 多智能体协作 (Multi-Agent) |

---

## 快速开始

### 环境要求

```bash
Python >= 3.8
pip install openai requests langfuse
```

### 安装步骤

1. 克隆仓库
```bash
git clone https://github.com/dession-wu/deepinsight_agent.git
cd deepinsight_agent
```

2. 安装依赖
```bash
pip install -r requirements.txt
```

3. 配置 API 密钥

编辑 `main.py`，修改第 43 行：
```python
client = OpenAI(
    api_key="your-api-key-here",
    base_url="https://api.deepseek.com"  # 或其他兼容API地址
)
```

4. 运行程序
```bash
python main.py
```

### 使用示例

```
👤 提问: 财联社有什么最新消息？
🌐 正在从财联社获取最新电报数据...
✅ 成功获取财联社数据，共 20 条。
🤖 DeepInsight: [基于最新新闻的分析]

👤 提问: 分析一下今天的市场行情
📈 正在从东方财富获取资金流向数据...
📊 正在从东方财富获取A股行情快照...
🤖 DeepInsight: [综合市场分析报告]

👤 提问: quit
👋 DeepInsight 已关闭。
```

---

## 项目结构

```
deepinsight_agent/
├── main.py                    # 主程序入口 & 对话循环
├── data_fetchers.py           # 数据获取模块 (财联社/东方财富)
├── error_handler.py            # 全局错误处理框架
├── memory_summarizer.py       # 记忆摘要与上下文管理
├── multi_agent_framework.py   # 多智能体协作核心框架
├── agent_integration.py       # 多智能体系统集成适配器
├── langfuse_monitor.py        # Langfuse 监控集成
│
├── test_error_handler.py      # 错误处理单元测试
├── test_memory_summarizer.py  # 记忆摘要单元测试
│
├── README.md                  # 本文件
├── LICENSE                    # MIT 许可证
└── requirements.txt           # 依赖配置
```

### 核心模块说明

| 模块 | 功能 | 代码行数 |
|------|------|---------|
| `data_fetchers.py` | 财联社电报、东方财富资金流向/行情 | ~175 行 |
| `error_handler.py` | 结构化错误捕获、格式化、自动修复 | ~400 行 |
| `memory_summarizer.py` | 对话摘要生成、实体提取、上下文压缩 | ~500 行 |
| `multi_agent_framework.py` | 8种智能体角色、消息总线、任务调度 | ~1800 行 |
| `langfuse_monitor.py` | Token消耗追踪、性能监控 | ~350 行 |

---

## 架构设计

### 多智能体角色体系

```
┌─────────────────────────────────────────────┐
│              协调者 (Orchestrator)          │
│         任务分解 → 智能体调度 → 结果整合     │
├─────────┬─────────┬─────────┬───────────────┤
│ 数据采集 │ 分析者  │ 决策者  │    执行者     │
│ Collector│ Analyzer│ Decision│   Executor   │
├─────────┴─────────┴─────────┴───────────────┤
│              监控者 (Monitor)                │
│         性能追踪 / 告警 / 审计              │
├─────────────────────────────────────────────┤
│              学习者 (Learner)                │
│         经验积累 / 能力进化                 │
└─────────────────────────────────────────────┘
```

### 数据流架构

```
用户输入 → 意图识别 → 任务分解
                    ↓
        ┌───────────┼───────────┐
        ↓           ↓           ↓
   财联社数据   东方财富数据   其他数据源
        ↓           ↓           ↓
        └───────────┼───────────┘
                    ↓
             数据预处理
                    ↓
             LLM 分析引擎
                    ↓
             响应格式化输出
```

---

## 高级功能

### 1. 智能记忆管理

当对话超过阈值时自动触发：
- 关键信息提取
- 对话摘要生成
- 上下文压缩（保留最近N轮 + 历史摘要）

### 2. 企业级错误处理

- 全局异常捕获装饰器
- 结构化错误信息（类型/位置/堆栈）
- 自动修复建议生成
- 错误历史记录与统计

### 3. Langfuse 监控集成

每次对话自动记录：
- Token 输入/输出统计
- API 调用延迟
- 数据获取操作追踪
- 错误日志

访问 https://cloud.langfuse.com 查看监控面板。

---

## 配置说明

### 环境变量

```bash
# 可选：通过环境变量配置
export OPENAI_API_KEY="your-key"
export OPENAI_BASE_URL="https://api.deepseek.com"

# Langfuse 监控（可选）
export LANGFUSE_SECRET_KEY="sk-lf-..."
export LANGFUSE_PUBLIC_KEY="pk-lf-..."
export LANGFUSE_HOST="https://cloud.langfuse.com"
```

### 记忆管理参数

编辑 `main.py` 第 62-70 行：
```python
summary_config = SummarizerConfig(
    max_messages_before_summary=10,   # 触发摘要的消息数
    max_tokens_before_summary=3000,   # 触发摘要的 token 数
    summary_detail_level="medium",    # low/medium/high
)
```

---

## 开发指南

### 运行测试

```bash
# 测试错误处理模块
python test_error_handler.py

# 测试记忆摘要模块
python test_memory_summarizer.py

# 测试 Langfuse 监控
python langfuse_monitor.py
```

### 扩展数据源

在 `data_fetchers.py` 中添加新函数：
```python
def fetch_your_data_source() -> str:
    """自定义数据源"""
    import requests
    response = requests.get("your-api-endpoint")
    return format_response(response.json())
```

然后在 `main.py` 的关键词列表中注册触发词。

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

---

## 许可证

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

## 致谢

- [OpenAI](https://openai.com/) - LLM API
- [DeepSeek](https://platform.deepseek.com/) - 大模型服务
- [财联社](https://www.cls.cn/) - 财经数据源
- [东方财富](https://www.eastmoney.com/) - 金融数据源
- [Langfuse](https://langfuse.com/) - LLM 可观测性平台

---

## 作者

**dession-wu**

- GitHub: [@dession-wu](https://github.com/dession-wu)

---

<p align="center">
  <sub>如果这个项目对您有帮助，欢迎 Star ⭐ 支持！</sub>
</p>
