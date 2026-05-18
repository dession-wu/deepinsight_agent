# Langfuse 监控集成指南

## 概述

已成功将 Langfuse 监控集成到 DeepInsight Agent 中，用于追踪 LLM 调用消耗和性能。

## 已安装组件

### 1. Python 包
```bash
pip install langfuse
```

### 2. 配置文件

**文件**: `langfuse_monitor.py`

包含以下核心组件：
- `LangfuseConfig` - 配置管理
- `AgentMonitor` - 监控器主类
- `MonitoredOpenAIClient` - 受监控的 OpenAI 客户端

### 3. API 密钥配置

已在代码中配置您的 API 密钥：
- **Secret Key**: `sk-lf-bd4d337d-896b-4137-b601-603d5d600b92`
- **Public Key**: `pk-lf-1805ebac-345f-4932-aa1d-622782a88a04`
- **Host**: `https://cloud.langfuse.com`

## 快速开始

### 方式1：直接运行测试
```bash
python langfuse_monitor.py
```

### 方式2：在代码中使用

```python
from langfuse_monitor import AgentMonitor, get_monitor

# 创建监控器
monitor = get_monitor()

# 追踪对话
with monitor.trace_conversation("user_123") as trace_id:
    # 您的代码在这里
    
    # 记录数据获取
    with monitor.log_span(name="fetch_data", metadata={"source": "api"}):
        data = fetch_data()
    
    # 记录 LLM 调用
    with monitor.log_generation(
        name="chat_completion",
        model="gpt-4",
        prompt="Hello",
        completion="Hi there!",
        usage={"input": 1, "output": 2, "total": 3}
    ):
        response = call_llm()
    
    # 评分
    monitor.score_response(name="quality", value=0.95, comment="Good response")

# 确保数据发送
monitor.flush()
```

## 查看监控数据

访问 Langfuse 控制台查看追踪数据：
- **URL**: https://cloud.langfuse.com
- **追踪ID**: 在控制台中查看具体会话

## 功能特性

### 1. 自动追踪
- LLM API 调用（Token 消耗、延迟）
- 数据获取操作
- 对话会话管理

### 2. 性能监控
- Token 使用量统计
- API 调用延迟
- 错误率追踪

### 3. 质量评估
- 响应评分
- 评论记录
- 历史趋势分析

## 环境变量配置（可选）

您也可以通过环境变量配置：

```bash
export LANGFUSE_SECRET_KEY="sk-lf-bd4d337d-896b-4137-b601-603d5d600b92"
export LANGFUSE_PUBLIC_KEY="pk-lf-1805ebac-345f-4932-aa1d-622782a88a04"
export LANGFUSE_HOST="https://cloud.langfuse.com"
export LANGFUSE_ENABLED="true"
```

## 故障排除

### 监控未启用
检查 API 密钥是否正确配置。

### 数据未显示
1. 确保调用 `monitor.flush()` 发送数据
2. 检查网络连接
3. 查看 Langfuse 控制台是否有延迟

## 最佳实践

1. **始终使用上下文管理器** - 确保资源正确释放
2. **及时 flush** - 在应用结束前调用 flush()
3. **合理命名** - 使用清晰的 span 和 generation 名称
4. **添加元数据** - 记录有用的上下文信息

---

**文档版本**: 1.0.0  
**更新日期**: 2025-05-12
