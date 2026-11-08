"""
Langfuse 监控模块 - 用于追踪 Agent 的 LLM 调用消耗和性能

功能：
1. 自动追踪 LLM API 调用
2. 监控 Token 消耗和成本
3. 记录对话历史和上下文
4. 支持多智能体系统的分布式追踪
5. 与现有错误处理和记忆系统集成

作者: AI Product Architect
版本: 1.0.0
日期: 2025-05-12
"""

import os
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager

# Langfuse 导入
from langfuse import Langfuse

# 集中式配置模块（密钥仅从环境变量读取，无默认值）
import config


class LangfuseConfig:
    """Langfuse 配置管理"""
    
    # 全部从环境变量读取，无任何默认密钥（统一由 config.py 管理）
    # 注意：模块顶部通过 `import config` 引入，避免重复定义
    SECRET_KEY = config.LANGFUSE_SECRET_KEY
    PUBLIC_KEY = config.LANGFUSE_PUBLIC_KEY
    BASE_URL = config.LANGFUSE_HOST

    # 追踪配置（默认关闭；启用需 LANGFUSE_ENABLED=true 且密钥齐全）
    ENABLED = (
        config.LANGFUSE_ENABLED
        and bool(config.LANGFUSE_SECRET_KEY)
        and bool(config.LANGFUSE_PUBLIC_KEY)
    )
    DEBUG = config.LANGFUSE_DEBUG
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """导出配置为字典"""
        return {
            "public_key": cls.PUBLIC_KEY[:10] + "..." if cls.PUBLIC_KEY else None,
            "base_url": cls.BASE_URL,
            "enabled": cls.ENABLED,
            "debug": cls.DEBUG
        }


class AgentMonitor:
    """
    Agent 监控器 - 集成 Langfuse 进行全面的调用追踪
    
    使用示例：
        monitor = AgentMonitor()
        
        # 方式1：使用上下文管理器
        with monitor.trace_conversation("user_123") as trace:
            response = call_llm(prompt)
    """
    
    def __init__(self):
        self.config = LangfuseConfig()
        self.langfuse: Optional[Langfuse] = None
        self._initialized = False
        
        if self.config.ENABLED:
            self._initialize()
    
    def _initialize(self):
        """初始化 Langfuse 客户端"""
        try:
            self.langfuse = Langfuse(
                secret_key=self.config.SECRET_KEY,
                public_key=self.config.PUBLIC_KEY,
                host=self.config.BASE_URL,
                debug=self.config.DEBUG
            )
            self._initialized = True
            print(f"✅ Langfuse 监控已启用")
            print(f"   项目: https://cloud.langfuse.com")
        except Exception as e:
            print(f"⚠️ Langfuse 初始化失败: {e}")
            self._initialized = False
    
    def is_enabled(self) -> bool:
        """检查监控是否启用"""
        return self._initialized and self.config.ENABLED
    
    @contextmanager
    def trace_conversation(self, user_id: str, session_id: Optional[str] = None):
        """
        追踪整个对话会话
        
        Args:
            user_id: 用户标识
            session_id: 会话标识（可选）
            
        Yields:
            trace_id: 追踪ID
        """
        if not self.is_enabled():
            yield None
            return
        
        # 创建 trace ID
        trace_id = self.langfuse.create_trace_id()
        
        # 使用 start_as_current_observation 创建 trace
        try:
            with self.langfuse.start_as_current_observation(
                name="deepinsight_conversation",
                as_type="span",
                input={"user_id": user_id, "session_id": session_id},
                metadata={
                    "agent_version": "1.0.0",
                    "environment": "production",
                    "user_id": user_id,
                    "session_id": session_id or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                }
            ):
                yield trace_id
        finally:
            # 确保追踪数据被发送
            self.langfuse.flush()
    
    def log_span(self, 
                 name: str,
                 metadata: Optional[Dict] = None):
        """
        记录 span 事件
        
        Args:
            name: span名称
            metadata: 元数据
        """
        if not self.is_enabled():
            return None
        
        return self.langfuse.start_as_current_observation(
            name=name,
            as_type="span",
            metadata=metadata or {}
        )
    
    def log_generation(self,
                       name: str,
                       model: str,
                       prompt: str,
                       completion: str,
                       usage: Optional[Dict] = None,
                       metadata: Optional[Dict] = None):
        """
        记录 LLM 生成事件
        
        Args:
            name: 生成名称
            model: 模型名称
            prompt: 提示词
            completion: 生成结果
            usage: Token 使用情况
            metadata: 额外元数据
        """
        if not self.is_enabled():
            return None
        
        # 合并 usage 到 metadata
        event_metadata = metadata or {}
        if usage:
            event_metadata["usage"] = usage
            event_metadata["model"] = model
        
        return self.langfuse.start_as_current_observation(
            name=name,
            as_type="generation",
            model=model,
            input=prompt,
            output=completion,
            usage_details=usage or {},
            metadata=event_metadata
        )
    
    def score_response(self,
                       name: str,
                       value: float,
                       comment: Optional[str] = None):
        """
        为响应打分（用于质量评估）
        
        Args:
            name: 评分名称
            value: 分数（0-1）
            comment: 评论
        """
        if not self.is_enabled():
            return
        
        self.langfuse.score_current_trace(
            name=name,
            value=value,
            comment=comment
        )
    
    def get_current_trace_id(self) -> Optional[str]:
        """获取当前追踪ID"""
        if not self.is_enabled():
            return None
        return self.langfuse.get_current_trace_id()
    
    def get_trace_url(self, trace_id: str) -> str:
        """获取追踪的 URL 链接"""
        return f"{self.config.BASE_URL}/trace/{trace_id}"
    
    def flush(self):
        """强制发送所有待处理的追踪数据"""
        if self.is_enabled():
            self.langfuse.flush()


# ==========================================
# 与现有系统的集成
# ==========================================

class MonitoredOpenAIClient:
    """
    受监控的 OpenAI 客户端包装器
    自动追踪所有 LLM 调用
    """
    
    def __init__(self, client, monitor: AgentMonitor):
        self.client = client
        self.monitor = monitor
    
    def chat_completions_create(self, **kwargs):
        """包装 chat.completions.create 方法"""
        if not self.monitor.is_enabled():
            return self.client.chat.completions.create(**kwargs)
        
        # 提取信息用于追踪
        model = kwargs.get('model', 'unknown')
        messages = kwargs.get('messages', [])
        prompt = json.dumps(messages, ensure_ascii=False)[:1000]  # 限制长度
        
        start_time = datetime.now()
        try:
            response = self.client.chat.completions.create(**kwargs)
            
            # 记录结果
            completion = response.choices[0].message.content if response.choices else ""
            usage = response.usage
            duration = (datetime.now() - start_time).total_seconds()
            
            # 记录生成事件
            with self.monitor.log_generation(
                name="chat_completion",
                model=model,
                prompt=prompt,
                completion=completion[:1000],  # 限制长度
                usage={
                    "input": usage.prompt_tokens if usage else 0,
                    "output": usage.completion_tokens if usage else 0,
                    "total": usage.total_tokens if usage else 0
                },
                metadata={
                    "temperature": kwargs.get('temperature'),
                    "max_tokens": kwargs.get('max_tokens'),
                    "duration_seconds": duration,
                    "status": "success"
                }
            ):
                pass  # 上下文管理器自动处理
            
            return response
            
        except Exception as e:
            # 记录错误
            duration = (datetime.now() - start_time).total_seconds()
            with self.monitor.log_generation(
                name="chat_completion",
                model=model,
                prompt=prompt,
                completion=f"Error: {str(e)}",
                metadata={
                    "duration_seconds": duration,
                    "status": "error",
                    "error": str(e)
                }
            ):
                pass
            raise


# ==========================================
# 便捷函数
# ==========================================

def create_monitor() -> AgentMonitor:
    """创建监控器实例（单例模式建议）"""
    return AgentMonitor()


# 全局监控器实例
_monitor_instance: Optional[AgentMonitor] = None

def get_monitor() -> AgentMonitor:
    """获取全局监控器实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = create_monitor()
    return _monitor_instance


# ==========================================
# 使用示例
# ==========================================

if __name__ == "__main__":
    # 测试监控功能
    monitor = create_monitor()
    
    print("\n" + "="*60)
    print("Langfuse 监控测试")
    print("="*60)
    
    if monitor.is_enabled():
        print(f"✅ 监控已启用")
        print(f"   配置: {json.dumps(LangfuseConfig.to_dict(), indent=2)}")
        
        # 测试追踪
        with monitor.trace_conversation("test_user") as trace_id:
            if trace_id:
                current_trace_id = monitor.get_current_trace_id()
                print(f"\n📊 追踪已创建")
                print(f"   当前追踪ID: {current_trace_id}")
                
                # 模拟数据获取 span
                with monitor.log_span(
                    name="fetch_data",
                    metadata={"source": "test", "items": 10}
                ):
                    print(f"   ✓ 已记录 span")
                
                # 模拟 LLM 调用记录
                with monitor.log_generation(
                    name="test_generation",
                    model=config.MODEL_NAME,
                    prompt="测试提示词",
                    completion="测试回复",
                    usage={"input": 10, "output": 20, "total": 30},
                    metadata={"test": True}
                ):
                    print(f"   ✓ 已记录生成操作")
                
                # 模拟评分
                monitor.score_response(
                    name="response_quality",
                    value=0.95,
                    comment="测试评分"
                )
                print(f"   ✓ 已记录评分")
        
        monitor.flush()
        print("\n✅ 测试完成，数据已发送到 Langfuse")
        print(f"   请访问: https://cloud.langfuse.com 查看追踪数据")
    else:
        print("⚠️ 监控未启用，请检查配置")
