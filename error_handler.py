import os
import sys
import json
import traceback
import inspect
from datetime import datetime
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass, asdict
from enum import Enum


class ErrorSeverity(Enum):
    """错误严重程度等级"""
    LOW = "low"           # 轻微错误，不影响核心功能
    MEDIUM = "medium"     # 中等错误，部分功能受限
    HIGH = "high"         # 严重错误，核心功能受损
    CRITICAL = "critical" # 致命错误，系统无法运行


class ErrorCategory(Enum):
    """错误分类"""
    SYNTAX = "syntax_error"           # 语法错误
    RUNTIME = "runtime_error"         # 运行时错误
    LOGIC = "logic_error"             # 逻辑错误
    NETWORK = "network_error"         # 网络请求错误
    API = "api_error"                 # API调用错误
    DATA = "data_error"               # 数据处理错误
    CONFIG = "config_error"           # 配置错误
    EXTERNAL = "external_error"       # 外部资源错误
    UNKNOWN = "unknown_error"         # 未知错误


@dataclass
class ErrorContext:
    """错误上下文信息"""
    file_path: str
    line_number: int
    function_name: str
    code_snippet: str
    local_vars: Dict[str, Any]
    args: List[Any]
    kwargs: Dict[str, Any]


@dataclass
class StructuredError:
    """结构化错误信息"""
    error_id: str
    timestamp: str
    severity: ErrorSeverity
    category: ErrorCategory
    error_type: str
    error_message: str
    description: str
    context: ErrorContext
    traceback_str: str
    suggestions: List[str]


class ErrorFormatter:
    """错误信息格式化转换器"""

    SEVERITY_EMOJI = {
        ErrorSeverity.LOW: "⚠️",
        ErrorSeverity.MEDIUM: "🔶",
        ErrorSeverity.HIGH: "🔴",
        ErrorSeverity.CRITICAL: "💥"
    }

    CATEGORY_DESCRIPTIONS = {
        ErrorCategory.SYNTAX: "代码语法存在错误，解释器无法正确解析。",
        ErrorCategory.RUNTIME: "程序运行期间发生意外错误。",
        ErrorCategory.LOGIC: "程序逻辑存在问题，导致结果不符合预期。",
        ErrorCategory.NETWORK: "网络连接失败或请求超时。",
        ErrorCategory.API: "外部API返回错误响应或调用失败。",
        ErrorCategory.DATA: "数据格式不正确、缺失或处理失败。",
        ErrorCategory.CONFIG: "配置参数错误或环境变量缺失。",
        ErrorCategory.EXTERNAL: "外部资源（文件、数据库等）访问失败。",
        ErrorCategory.UNKNOWN: "发生未知类型的错误。"
    }

    @classmethod
    def format_for_llm(cls, error: StructuredError) -> str:
        """
        将结构化错误信息转换为适合大模型处理的自然语言指令。

        Args:
            error: 结构化错误对象

        Returns:
            自然语言描述字符串
        """
        severity_emoji = cls.SEVERITY_EMOJI.get(error.severity, "❓")
        category_desc = cls.CATEGORY_DESCRIPTIONS.get(error.category, "未知错误类型")

        # 构建上下文信息字符串
        local_vars_str = json.dumps(
            {k: str(v)[:100] for k, v in error.context.local_vars.items()},
            ensure_ascii=False, indent=2
        ) if error.context.local_vars else "无"

        prompt = f"""
{severity_emoji} 【系统错误报告】 {severity_emoji}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 错误概览
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 错误ID: {error.error_id}
• 发生时间: {error.timestamp}
• 严重程度: {error.severity.value.upper()}
• 错误类型: {error.error_type}
• 错误分类: {error.category.value}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📝 错误描述
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{category_desc}

具体错误信息: {error.error_message}

详细说明: {error.description}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📍 错误位置
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• 文件: {error.context.file_path}
• 函数: {error.context.function_name}
• 行号: {error.context.line_number}

代码片段:
```python
{error.context.code_snippet}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 运行时上下文
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
局部变量:
```json
{local_vars_str}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📚 完整堆栈跟踪
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
{error.traceback_str}
```

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💡 建议排查方向
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for i, suggestion in enumerate(error.suggestions, 1):
            prompt += f"{i}. {suggestion}\n"

        prompt += """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🤖 Agent 处理指令
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
作为 DeepInsight 智能体的错误处理模块，请你基于以上错误信息：

1. 分析错误的根本原因
2. 提供具体的修复建议或代码修改方案
3. 如果错误与外部服务（API/网络）相关，评估是否需要重试或降级处理
4. 生成用户友好的错误提示信息
5. 如有必要，提供预防措施避免同类错误再次发生

请用中文回复，保持简洁专业。
"""
        return prompt

    @classmethod
    def format_short(cls, error: StructuredError) -> str:
        """生成简短的错误摘要（用于日志或快速展示）"""
        return (
            f"[{error.timestamp}] {cls.SEVERITY_EMOJI.get(error.severity, '❓')} "
            f"{error.error_type}: {error.error_message[:80]}... "
            f"({error.context.file_path}:{error.context.line_number})"
        )


class ErrorClassifier:
    """错误分类器"""

    @staticmethod
    def classify_exception(exc: Exception) -> ErrorCategory:
        """根据异常类型自动分类"""
        exc_type = type(exc).__name__

        syntax_errors = ['SyntaxError', 'IndentationError', 'TabError']
        runtime_errors = ['RuntimeError', 'RecursionError', 'MemoryError']
        network_errors = [
            'ConnectionError', 'TimeoutError', 'ConnectionRefusedError',
            'ConnectionResetError', 'ConnectionAbortedError'
        ]
        api_errors = ['HTTPError', 'URLError', 'APIError', 'AuthenticationError']
        data_errors = ['ValueError', 'TypeError', 'KeyError', 'IndexError', 'AttributeError']
        config_errors = ['FileNotFoundError', 'PermissionError']
        runtime_errors_all = ['RuntimeError', 'RecursionError', 'MemoryError', 'ZeroDivisionError']

        if exc_type in syntax_errors:
            return ErrorCategory.SYNTAX
        elif exc_type in runtime_errors_all:
            return ErrorCategory.RUNTIME
        elif exc_type in network_errors:
            return ErrorCategory.NETWORK
        elif exc_type in api_errors:
            return ErrorCategory.API
        elif exc_type in data_errors:
            return ErrorCategory.DATA
        elif exc_type in config_errors:
            return ErrorCategory.CONFIG
        elif 'Request' in exc_type or 'HTTP' in exc_type:
            return ErrorCategory.NETWORK
        else:
            return ErrorCategory.UNKNOWN

    @staticmethod
    def assess_severity(exc: Exception, category: ErrorCategory) -> ErrorSeverity:
        """评估错误严重程度"""
        exc_type = type(exc).__name__

        critical_types = ['MemoryError', 'SyntaxError', 'SystemExit', 'KeyboardInterrupt']
        high_types = ['ConnectionError', 'TimeoutError', 'PermissionError', 'FileNotFoundError']
        low_types = ['ValueError', 'TypeError', 'KeyError', 'IndexError']

        if exc_type in critical_types:
            return ErrorSeverity.CRITICAL
        elif exc_type in high_types or category == ErrorCategory.NETWORK:
            return ErrorSeverity.HIGH
        elif exc_type in low_types:
            return ErrorSeverity.LOW
        elif category == ErrorCategory.API:
            return ErrorSeverity.MEDIUM
        else:
            return ErrorSeverity.MEDIUM


class ErrorRecovery:
    """错误恢复策略生成器"""

    @staticmethod
    def generate_suggestions(error: StructuredError) -> List[str]:
        """根据错误类型生成修复建议"""
        suggestions = []

        if error.category == ErrorCategory.NETWORK:
            suggestions.extend([
                "检查网络连接是否正常",
                "确认目标服务器地址和端口是否正确",
                "检查防火墙或代理设置是否阻止了连接",
                "考虑增加请求超时时间或实现重试机制",
                "验证SSL证书配置（如果是HTTPS请求）"
            ])
        elif error.category == ErrorCategory.API:
            suggestions.extend([
                "检查API密钥是否有效且未过期",
                "确认API请求参数格式是否正确",
                "查看API文档确认接口是否变更",
                "检查API调用频率是否超过限制",
                "验证请求头（Headers）中的认证信息"
            ])
        elif error.category == ErrorCategory.DATA:
            suggestions.extend([
                "检查输入数据的类型和格式是否符合预期",
                "验证数据是否包含必需的字段",
                "确认数据编码格式是否正确（UTF-8等）",
                "检查数据长度或大小是否超出限制",
                "添加数据预处理或清洗步骤"
            ])
        elif error.category == ErrorCategory.CONFIG:
            suggestions.extend([
                "检查配置文件路径是否正确",
                "验证环境变量是否已正确设置",
                "确认配置文件格式是否符合要求（JSON/YAML等）",
                "检查文件权限是否允许读取/写入",
                "恢复默认配置进行测试"
            ])
        elif error.category == ErrorCategory.SYNTAX:
            suggestions.extend([
                "检查代码缩进是否一致（空格/制表符）",
                "确认括号、引号等符号是否正确配对",
                "检查Python版本兼容性",
                "使用IDE的语法检查功能定位问题",
                "参考官方文档确认语法用法"
            ])
        else:
            suggestions.extend([
                "检查相关函数的输入参数",
                "查看日志文件获取更多上下文信息",
                "尝试简化代码以定位问题根源",
                "查阅相关库或框架的官方文档",
                "在隔离环境中复现问题"
            ])

        return suggestions[:5]  # 最多返回5条建议


class GlobalErrorHandler:
    """全局错误处理器"""

    def __init__(self, client=None, auto_report: bool = True, max_history: int = 50):
        """
        初始化全局错误处理器。

        Args:
            client: 大模型客户端实例（如OpenAI客户端）
            auto_report: 是否自动向大模型报告错误
            max_history: 错误历史最大保留数量
        """
        self.client = client
        self.auto_report = auto_report
        self.max_history = max_history
        self.error_history: List[StructuredError] = []
        self._original_excepthook = sys.excepthook
        self._is_installed = False

    def install(self):
        """安装全局异常捕获钩子"""
        if not self._is_installed:
            sys.excepthook = self._handle_uncaught_exception
            self._is_installed = True
            print("✅ 全局错误捕获机制已启用")

    def uninstall(self):
        """卸载全局异常捕获钩子"""
        if self._is_installed:
            sys.excepthook = self._original_excepthook
            self._is_installed = False
            print("🛑 全局错误捕获机制已禁用")

    def _handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """处理未捕获的异常"""
        if issubclass(exc_type, KeyboardInterrupt):
            # 保留Ctrl+C的正常行为
            self._original_excepthook(exc_type, exc_value, exc_traceback)
            return

        structured_error = self.capture_error(
            exc_value,
            traceback_obj=exc_traceback,
            context="未捕获的全局异常"
        )

        print(f"\n{'='*60}")
        print(f"💥 捕获到未处理的全局异常")
        print(f"{'='*60}")
        print(ErrorFormatter.format_short(structured_error))

        if self.auto_report and self.client:
            self.report_to_agent(structured_error)

    def capture_error(
        self,
        exc: Exception,
        traceback_obj=None,
        context: str = "",
        local_vars: Optional[Dict] = None
    ) -> StructuredError:
        """
        捕获并结构化处理错误信息。

        Args:
            exc: 异常对象
            traceback_obj: 可选的traceback对象
            context: 错误上下文描述
            local_vars: 可选的局部变量字典

        Returns:
            结构化错误对象
        """
        now = datetime.now()
        error_id = f"ERR-{now.strftime('%Y%m%d%H%M%S')}-{id(exc) % 10000:04d}"

        # 获取traceback信息
        tb = traceback_obj or sys.exc_info()[2]
        tb_str = "".join(traceback.format_exception(type(exc), exc, tb)) if tb else str(exc)

        # 提取错误位置信息
        file_path = "未知文件"
        line_number = 0
        function_name = "未知函数"
        code_snippet = ""

        if tb:
            # 获取最底层的栈帧
            last_frame = tb
            while last_frame.tb_next:
                last_frame = last_frame.tb_next

            frame = last_frame.tb_frame
            file_path = frame.f_code.co_filename
            line_number = last_frame.tb_lineno
            function_name = frame.f_code.co_name

            # 尝试获取代码片段
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    start = max(0, line_number - 3)
                    end = min(len(lines), line_number + 2)
                    code_snippet = "".join(lines[start:end])
            except Exception:
                code_snippet = "无法读取源代码"

            # 获取局部变量
            if local_vars is None:
                local_vars = {k: str(v) for k, v in frame.f_locals.items() if not k.startswith('__')}

        # 分类和评估
        category = ErrorClassifier.classify_exception(exc)
        severity = ErrorClassifier.assess_severity(exc, category)

        # 构建错误上下文
        error_context = ErrorContext(
            file_path=file_path,
            line_number=line_number,
            function_name=function_name,
            code_snippet=code_snippet,
            local_vars=local_vars or {},
            args=[],
            kwargs={}
        )

        # 构建结构化错误
        structured_error = StructuredError(
            error_id=error_id,
            timestamp=now.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            severity=severity,
            category=category,
            error_type=type(exc).__name__,
            error_message=str(exc),
            description=context or str(exc),
            context=error_context,
            traceback_str=tb_str,
            suggestions=ErrorRecovery.generate_suggestions(
                StructuredError(
                    error_id=error_id,
                    timestamp="",
                    severity=severity,
                    category=category,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    description="",
                    context=error_context,
                    traceback_str="",
                    suggestions=[]
                )
            )
        )

        # 更新建议（使用完整的结构化错误）
        structured_error.suggestions = ErrorRecovery.generate_suggestions(structured_error)

        # 添加到历史记录
        self.error_history.append(structured_error)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)

        return structured_error

    def report_to_agent(self, error: StructuredError) -> Optional[str]:
        """
        将错误报告发送给大模型Agent进行处理。

        Args:
            error: 结构化错误对象

        Returns:
            Agent的回复内容，如果失败则返回None
        """
        if not self.client:
            print("⚠️ 未配置大模型客户端，无法向Agent报告错误")
            return None

        try:
            prompt = ErrorFormatter.format_for_llm(error)

            response = self.client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {"role": "system", "content": "你是DeepInsight智能体的错误处理专家。你的任务是分析系统错误并提供专业的修复建议。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )

            agent_reply = response.choices[0].message.content
            print(f"\n🤖 Agent错误处理建议:\n{agent_reply}")
            return agent_reply

        except Exception as e:
            print(f"❌ 向Agent报告错误时失败: {e}")
            return None

    def get_error_history(self, limit: int = 10) -> List[StructuredError]:
        """获取最近的错误历史"""
        return self.error_history[-limit:]

    def clear_history(self):
        """清空错误历史"""
        self.error_history.clear()


def with_error_handling(handler: GlobalErrorHandler, context: str = ""):
    """
    装饰器：为函数添加自动错误捕获和处理。

    Args:
        handler: 全局错误处理器实例
        context: 错误上下文描述
    """
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 捕获局部变量
                local_vars = {
                    'args': str(args),
                    'kwargs': str(kwargs)
                }

                structured_error = handler.capture_error(
                    e,
                    context=f"在函数 '{func.__name__}' 中: {context}"
                )

                print(f"\n{'='*60}")
                print(f"🔍 捕获到函数异常: {func.__name__}")
                print(f"{'='*60}")
                print(ErrorFormatter.format_short(structured_error))

                if handler.auto_report and handler.client:
                    handler.report_to_agent(structured_error)

                # 重新抛出异常，让上层决定如何处理
                raise
        return wrapper
    return decorator


# ==========================================
# 配置管理
# ==========================================

class ErrorHandlerConfig:
    """错误处理器配置"""

    DEFAULT_CONFIG = {
        "auto_report": True,
        "max_history": 50,
        "report_severity_levels": ["medium", "high", "critical"],
        "include_local_vars": True,
        "include_traceback": True,
        "retry_on_network_error": True,
        "max_retries": 3,
        "retry_delay": 1.0
    }

    def __init__(self, config_path: Optional[str] = None):
        self.config = self.DEFAULT_CONFIG.copy()
        if config_path and os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config.update(json.load(f))

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value

    def save(self, config_path: str):
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
