"""
集中式配置模块

所有配置均从环境变量读取，代码中不硬编码任何密钥。
必填项 OPENAI_API_KEY 缺失时，由调用方（CLI/FastAPI）负责给出明确报错。
"""

import os

# ==========================================
# LLM（OpenAI 兼容协议，默认 DeepSeek）
# ==========================================
# 必填：DeepSeek API Key，无默认值，缺失时应明确报错而非静默降级
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# OpenAI 兼容 API 地址，默认 DeepSeek 官方
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")

# 模型名：默认 deepseek-chat（原硬编码的 deepseek-v4-flash 疑似无效模型名）
MODEL_NAME = os.environ.get("MODEL_NAME", "deepseek-chat")

# ==========================================
# Langfuse 监控（可选）
# ==========================================
# 默认关闭；启用时必须同时提供 PUBLIC_KEY / SECRET_KEY，否则自动视为未启用
LANGFUSE_ENABLED = os.environ.get("LANGFUSE_ENABLED", "false").lower() == "true"
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
LANGFUSE_DEBUG = os.environ.get("LANGFUSE_DEBUG", "false").lower() == "true"


def validate_llm_config() -> str:
    """
    校验 LLM 配置是否可用。

    Returns:
        OPENAI_API_KEY

    Raises:
        RuntimeError: 缺少必填的 OPENAI_API_KEY
    """
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "未配置 OPENAI_API_KEY 环境变量。"
            "请通过环境变量或 .env 文件提供（参考 .env.example），"
            "代码中不再内置任何默认密钥。"
        )
    return OPENAI_API_KEY