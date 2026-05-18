# DeepInsight Agent 快速启动指南

## 项目概述

DeepInsight Agent 是一个智能金融分析助手，支持：
- 实时财经数据获取（财联社、东方财富）
- 智能对话与记忆管理
- 多智能体协作架构
- Langfuse 监控追踪
- 全面的错误处理

---

## 环境要求

- **Python**: 3.8+
- **操作系统**: Windows / Linux / macOS
- **网络**: 需要访问互联网获取实时数据

---

## 安装步骤

### 1. 安装依赖包

在项目目录下运行：

```bash
# 安装核心依赖
pip install openai requests

# 安装 Langfuse 监控（可选）
pip install langfuse
```

### 2. 配置 API 密钥

编辑 `main.py` 文件，配置您的大模型 API 密钥：

```python
# 第 43 行
client = OpenAI(
    api_key="your-api-key-here",  # 替换为您的 API Key
    base_url="https://api.deepseek.com"  # 或您使用的其他 API 地址
)
```

**支持的模型服务商**：
- DeepSeek (推荐): https://api.deepseek.com
- OpenAI: https://api.openai.com
- 阿里云百炼: https://dashscope.aliyuncs.com/compatible-mode/v1
- 其他兼容 OpenAI API 的服务商

---

## 运行方式

### 方式1：基础运行（推荐新手）

```bash
cd d:\deepinsight_agent
python main.py
```

### 方式2：使用特定 Python 环境

```bash
# 如果使用 Anaconda
conda activate your_env
python main.py

# 如果使用 venv
.\venv\Scripts\activate
python main.py
```

---

## 使用指南

### 启动后的界面

```
============================================================
🧠 DeepInsight Agent 已启动！(输入 'quit' 退出)
--------------------------------------------------
✅ 全局错误处理系统已安装
✅ 记忆摘要系统已初始化
✅ 多智能体协作系统已加载
✅ Langfuse 监控已加载
   追踪面板: https://cloud.langfuse.com
============================================================

👤 提问:
```

### 基本对话

直接输入您的问题：

```
👤 提问: 你好，请介绍一下自己
🤖 DeepInsight: 我是 DeepInsight Agent，一个智能金融分析助手...
```

### 获取实时财经数据

#### 财联社电报
```
👤 提问: 财联社有什么最新消息？
🌐 正在从财联社获取最新电报数据...
✅ 成功获取财联社数据，共 20 条。
🤖 DeepInsight: [基于最新财经新闻的回答]
```

#### 东方财富资金流向
```
👤 提问: 看看今天的资金流向
📈 正在从东方财富获取资金流向数据...
✅ 成功获取东方财富行业资金流向数据。
📊 正在从东方财富获取A股行情快照...
✅ 成功获取A股行情快照。
🤖 DeepInsight: [基于资金流向数据的分析]
```

#### 综合分析
```
👤 提问: 分析一下今天的市场行情
🌐 正在从财联社获取最新电报数据...
📈 正在从东方财富获取资金流向数据...
📊 正在从东方财富获取A股行情快照...
🤖 DeepInsight: [综合分析报告]
```

### 退出程序

```
👤 提问: quit
👋 DeepInsight 已关闭。
```

---

## 功能特性

### 1. 智能记忆管理

当对话超过 10 轮或 3000 tokens 时，系统会自动：
- 生成对话摘要
- 压缩上下文
- 保留关键信息

显示信息：
```
📝 对话上下文较长，正在生成记忆摘要...
✅ 摘要生成完成（耗时1250ms）
   完整度: 85.5%, 冗余去除: 45.2%
   上下文已压缩，保留最近4轮完整对话 + 摘要
```

### 2. 错误自动处理

当发生错误时，系统会：
- 自动捕获错误
- 尝试自我修复
- 提供友好的错误提示

### 3. Langfuse 监控

每次对话都会自动记录到 Langfuse：
- Token 消耗
- API 调用延迟
- 数据获取操作
- 错误追踪

查看监控数据：
- 访问 https://cloud.langfuse.com
- 使用配置的 API 密钥登录

---

## 故障排除

### 问题1：ImportError

**现象**：
```
ModuleNotFoundError: No module named 'openai'
```

**解决**：
```bash
pip install openai requests langfuse
```

### 问题2：API 密钥错误

**现象**：
```
❌ 网络或 API 发生错误: 401 Unauthorized
```

**解决**：
1. 检查 `main.py` 中的 `api_key` 是否正确
2. 确认 API 密钥是否有效
3. 检查 `base_url` 是否正确

### 问题3：网络连接问题

**现象**：
```
❌ 网络或 API 发生错误: Connection timeout
```

**解决**：
1. 检查网络连接
2. 确认能访问外网
3. 如果使用代理，配置代理设置

### 问题4：Langfuse 监控未启用

**现象**：
```
⚠️ Langfuse 监控未启用（检查配置）
```

**解决**：
这是正常的，不影响主程序运行。如需启用，检查 `langfuse_monitor.py` 中的 API 密钥配置。

---

## 高级用法

### 运行单元测试

```bash
# 测试错误处理
python test_error_handler.py

# 测试记忆摘要
python test_memory_summarizer.py

# 测试 Langfuse 监控
python langfuse_monitor.py
```

### 使用多智能体模式

系统会自动根据查询复杂度选择：
- **简单查询**：单智能体处理
- **复杂分析**：多智能体协作

### 自定义配置

编辑 `main.py` 中的配置参数：

```python
# 记忆摘要配置（第 62-70 行）
summary_config = SummarizerConfig(
    max_messages_before_summary=10,      # 调整触发摘要的消息数
    max_tokens_before_summary=3000,      # 调整触发摘要的 token 数
    summary_detail_level="medium",       # 摘要详细程度: low/medium/high
    max_summary_length=800,              # 摘要最大长度
)
```

---

## 项目文件结构

```
deepinsight_agent/
├── main.py                    # 主程序入口
├── error_handler.py           # 错误处理模块
├── memory_summarizer.py       # 记忆摘要模块
├── multi_agent_framework.py   # 多智能体框架
├── agent_integration.py       # 智能体集成
├── langfuse_monitor.py        # Langfuse 监控
├── test_error_handler.py      # 错误处理测试
├── test_memory_summarizer.py  # 记忆摘要测试
├── QUICK_START.md            # 本文件
└── LANGFUSE_INTEGRATION.md   # Langfuse 集成指南
```

---

## 常用命令速查

| 命令 | 说明 |
|------|------|
| `python main.py` | 启动 Agent |
| `quit` / `exit` / `q` | 退出程序 |
| `python langfuse_monitor.py` | 测试 Langfuse 监控 |
| `python test_error_handler.py` | 测试错误处理 |
| `python test_memory_summarizer.py` | 测试记忆摘要 |

---

## 下一步建议

1. **测试基础功能**
   ```
   👤 提问: 你好
   ```

2. **测试数据获取**
   ```
   👤 提问: 财联社最新消息
   ```

3. **测试综合分析**
   ```
   👤 提问: 分析一下今天的市场行情
   ```

4. **查看监控数据**
   - 访问 https://cloud.langfuse.com
   - 查看对话追踪和 Token 消耗

---

**文档版本**: 1.0.0  
**更新日期**: 2025-05-12
