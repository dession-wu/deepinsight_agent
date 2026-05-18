import os
import sys
import json
import unittest
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# 确保可以导入当前目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from error_handler import (
    ErrorSeverity,
    ErrorCategory,
    ErrorContext,
    StructuredError,
    ErrorFormatter,
    ErrorClassifier,
    ErrorRecovery,
    GlobalErrorHandler,
    ErrorHandlerConfig,
    with_error_handling
)


# ==========================================
# 1. 单元测试：基础数据类
# ==========================================

class TestErrorEnums(unittest.TestCase):
    """测试错误枚举类"""

    def test_error_severity_values(self):
        """测试错误严重程度枚举值"""
        self.assertEqual(ErrorSeverity.LOW.value, "low")
        self.assertEqual(ErrorSeverity.MEDIUM.value, "medium")
        self.assertEqual(ErrorSeverity.HIGH.value, "high")
        self.assertEqual(ErrorSeverity.CRITICAL.value, "critical")

    def test_error_category_values(self):
        """测试错误分类枚举值"""
        self.assertEqual(ErrorCategory.SYNTAX.value, "syntax_error")
        self.assertEqual(ErrorCategory.NETWORK.value, "network_error")
        self.assertEqual(ErrorCategory.API.value, "api_error")


class TestErrorContext(unittest.TestCase):
    """测试错误上下文数据类"""

    def test_error_context_creation(self):
        """测试创建错误上下文对象"""
        context = ErrorContext(
            file_path="test.py",
            line_number=42,
            function_name="test_func",
            code_snippet="x = 1 / 0",
            local_vars={"x": 1, "y": 2},
            args=[1, 2],
            kwargs={"key": "value"}
        )
        self.assertEqual(context.file_path, "test.py")
        self.assertEqual(context.line_number, 42)
        self.assertEqual(context.function_name, "test_func")
        self.assertEqual(context.local_vars["x"], 1)


class TestStructuredError(unittest.TestCase):
    """测试结构化错误数据类"""

    def test_structured_error_creation(self):
        """测试创建结构化错误对象"""
        context = ErrorContext(
            file_path="test.py",
            line_number=10,
            function_name="main",
            code_snippet="print('test')",
            local_vars={},
            args=[],
            kwargs={}
        )
        error = StructuredError(
            error_id="ERR-20240101120000-0001",
            timestamp="2024-01-01 12:00:00.000",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.RUNTIME,
            error_type="ZeroDivisionError",
            error_message="division by zero",
            description="测试错误",
            context=context,
            traceback_str="Traceback (most recent call last):...",
            suggestions=["检查除数是否为零"]
        )
        self.assertEqual(error.error_type, "ZeroDivisionError")
        self.assertEqual(error.severity, ErrorSeverity.HIGH)
        self.assertEqual(len(error.suggestions), 1)


# ==========================================
# 2. 单元测试：错误格式化器
# ==========================================

class TestErrorFormatter(unittest.TestCase):
    """测试错误格式化器"""

    def setUp(self):
        """设置测试数据"""
        self.context = ErrorContext(
            file_path="/path/to/test.py",
            line_number=42,
            function_name="divide",
            code_snippet="    result = a / b",
            local_vars={"a": 10, "b": 0},
            args=[10, 0],
            kwargs={}
        )
        self.error = StructuredError(
            error_id="ERR-20240101120000-1234",
            timestamp="2024-01-01 12:00:00.000",
            severity=ErrorSeverity.HIGH,
            category=ErrorCategory.RUNTIME,
            error_type="ZeroDivisionError",
            error_message="division by zero",
            description="在divide函数中发生除零错误",
            context=self.context,
            traceback_str="Traceback:...",
            suggestions=["检查除数是否为零", "添加异常处理"]
        )

    def test_format_short(self):
        """测试短格式输出"""
        short = ErrorFormatter.format_short(self.error)
        self.assertIn("ZeroDivisionError", short)
        self.assertIn("division by zero", short)
        self.assertIn("test.py:42", short)

    def test_format_for_llm(self):
        """测试LLM格式输出"""
        llm_prompt = ErrorFormatter.format_for_llm(self.error)
        # 验证包含关键部分
        self.assertIn("系统错误报告", llm_prompt)
        self.assertIn("ERR-20240101120000-1234", llm_prompt)
        self.assertIn("ZeroDivisionError", llm_prompt)
        self.assertIn("division by zero", llm_prompt)
        self.assertIn("Agent 处理指令", llm_prompt)
        self.assertIn("检查除数是否为零", llm_prompt)

    def test_severity_emoji(self):
        """测试严重程度emoji映射"""
        self.assertEqual(ErrorFormatter.SEVERITY_EMOJI[ErrorSeverity.LOW], "⚠️")
        self.assertEqual(ErrorFormatter.SEVERITY_EMOJI[ErrorSeverity.CRITICAL], "💥")

    def test_category_descriptions(self):
        """测试分类描述"""
        self.assertIn("语法", ErrorFormatter.CATEGORY_DESCRIPTIONS[ErrorCategory.SYNTAX])
        self.assertIn("网络", ErrorFormatter.CATEGORY_DESCRIPTIONS[ErrorCategory.NETWORK])


# ==========================================
# 3. 单元测试：错误分类器
# ==========================================

class TestErrorClassifier(unittest.TestCase):
    """测试错误分类器"""

    def test_classify_syntax_error(self):
        """测试语法错误分类"""
        exc = SyntaxError("invalid syntax")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.SYNTAX)

    def test_classify_network_error(self):
        """测试网络错误分类"""
        exc = ConnectionError("Connection refused")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.NETWORK)

    def test_classify_timeout_error(self):
        """测试超时错误分类"""
        exc = TimeoutError("Request timed out")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.NETWORK)

    def test_classify_value_error(self):
        """测试数值错误分类"""
        exc = ValueError("invalid value")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.DATA)

    def test_classify_key_error(self):
        """测试键错误分类"""
        exc = KeyError("missing_key")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.DATA)

    def test_classify_file_not_found(self):
        """测试文件未找到分类"""
        exc = FileNotFoundError("file not found")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.CONFIG)

    def test_classify_unknown_error(self):
        """测试未知错误分类"""
        exc = Exception("unknown error")
        category = ErrorClassifier.classify_exception(exc)
        self.assertEqual(category, ErrorCategory.UNKNOWN)

    def test_assess_severity_critical(self):
        """测试致命错误严重度"""
        exc = MemoryError("out of memory")
        severity = ErrorClassifier.assess_severity(exc, ErrorCategory.RUNTIME)
        self.assertEqual(severity, ErrorSeverity.CRITICAL)

    def test_assess_severity_high(self):
        """测试高严重度"""
        exc = ConnectionError("connection failed")
        severity = ErrorClassifier.assess_severity(exc, ErrorCategory.NETWORK)
        self.assertEqual(severity, ErrorSeverity.HIGH)

    def test_assess_severity_low(self):
        """测试低严重度"""
        exc = ValueError("invalid input")
        severity = ErrorClassifier.assess_severity(exc, ErrorCategory.DATA)
        self.assertEqual(severity, ErrorSeverity.LOW)


# ==========================================
# 4. 单元测试：错误恢复策略
# ==========================================

class TestErrorRecovery(unittest.TestCase):
    """测试错误恢复策略生成器"""

    def setUp(self):
        self.context = ErrorContext(
            file_path="test.py",
            line_number=1,
            function_name="test",
            code_snippet="pass",
            local_vars={},
            args=[],
            kwargs={}
        )

    def _create_error(self, category):
        return StructuredError(
            error_id="ERR-001",
            timestamp="2024-01-01",
            severity=ErrorSeverity.MEDIUM,
            category=category,
            error_type="TestError",
            error_message="test",
            description="test",
            context=self.context,
            traceback_str="",
            suggestions=[]
        )

    def test_network_suggestions(self):
        """测试网络错误建议"""
        error = self._create_error(ErrorCategory.NETWORK)
        suggestions = ErrorRecovery.generate_suggestions(error)
        self.assertTrue(len(suggestions) > 0)
        self.assertTrue(any("网络" in s for s in suggestions))

    def test_api_suggestions(self):
        """测试API错误建议"""
        error = self._create_error(ErrorCategory.API)
        suggestions = ErrorRecovery.generate_suggestions(error)
        self.assertTrue(len(suggestions) > 0)
        self.assertTrue(any("API" in s or "密钥" in s for s in suggestions))

    def test_data_suggestions(self):
        """测试数据错误建议"""
        error = self._create_error(ErrorCategory.DATA)
        suggestions = ErrorRecovery.generate_suggestions(error)
        self.assertTrue(len(suggestions) > 0)
        self.assertTrue(any("数据" in s for s in suggestions))

    def test_config_suggestions(self):
        """测试配置错误建议"""
        error = self._create_error(ErrorCategory.CONFIG)
        suggestions = ErrorRecovery.generate_suggestions(error)
        self.assertTrue(len(suggestions) > 0)
        self.assertTrue(any("配置" in s for s in suggestions))

    def test_suggestions_limit(self):
        """测试建议数量限制"""
        error = self._create_error(ErrorCategory.NETWORK)
        suggestions = ErrorRecovery.generate_suggestions(error)
        self.assertLessEqual(len(suggestions), 5)


# ==========================================
# 5. 单元测试：全局错误处理器
# ==========================================

class TestGlobalErrorHandler(unittest.TestCase):
    """测试全局错误处理器"""

    def setUp(self):
        """每个测试前创建新的处理器"""
        self.mock_client = Mock()
        self.handler = GlobalErrorHandler(
            client=self.mock_client,
            auto_report=False,
            max_history=10
        )

    def tearDown(self):
        """每个测试后卸载处理器"""
        if self.handler._is_installed:
            self.handler.uninstall()

    def test_initialization(self):
        """测试初始化"""
        self.assertEqual(self.handler.max_history, 10)
        self.assertFalse(self.handler.auto_report)
        self.assertEqual(len(self.handler.error_history), 0)

    def test_install_uninstall(self):
        """测试安装和卸载"""
        original_hook = sys.excepthook

        self.handler.install()
        self.assertTrue(self.handler._is_installed)
        self.assertNotEqual(sys.excepthook, original_hook)

        self.handler.uninstall()
        self.assertFalse(self.handler._is_installed)
        self.assertEqual(sys.excepthook, original_hook)

    def test_capture_error(self):
        """测试错误捕获"""
        try:
            1 / 0
        except Exception as e:
            error = self.handler.capture_error(e, context="测试除零错误")

        self.assertIsInstance(error, StructuredError)
        self.assertEqual(error.error_type, "ZeroDivisionError")
        self.assertEqual(error.category, ErrorCategory.RUNTIME)
        self.assertEqual(error.description, "测试除零错误")
        self.assertIsNotNone(error.error_id)
        self.assertIsNotNone(error.timestamp)

    def test_error_history(self):
        """测试错误历史记录"""
        # 生成多个错误
        for i in range(5):
            try:
                raise ValueError(f"错误 {i}")
            except Exception as e:
                self.handler.capture_error(e)

        history = self.handler.get_error_history()
        self.assertEqual(len(history), 5)

    def test_error_history_limit(self):
        """测试历史记录上限"""
        handler = GlobalErrorHandler(max_history=3)

        for i in range(5):
            try:
                raise ValueError(f"错误 {i}")
            except Exception as e:
                handler.capture_error(e)

        history = handler.get_error_history()
        self.assertEqual(len(history), 3)
        # 应该保留最新的错误
        self.assertIn("错误 4", history[-1].error_message)

    def test_clear_history(self):
        """测试清空历史"""
        try:
            raise ValueError("测试")
        except Exception as e:
            self.handler.capture_error(e)

        self.assertEqual(len(self.handler.error_history), 1)
        self.handler.clear_history()
        self.assertEqual(len(self.handler.error_history), 0)

    def test_report_to_agent_without_client(self):
        """测试无客户端时报告错误"""
        handler = GlobalErrorHandler(client=None)
        error = StructuredError(
            error_id="ERR-001",
            timestamp="2024-01-01",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.UNKNOWN,
            error_type="TestError",
            error_message="test",
            description="test",
            context=ErrorContext("", 0, "", "", {}, [], {}),
            traceback_str="",
            suggestions=[]
        )
        result = handler.report_to_agent(error)
        self.assertIsNone(result)

    @patch('error_handler.ErrorFormatter.format_for_llm')
    def test_report_to_agent_with_client(self, mock_format):
        """测试有客户端时报告错误"""
        mock_format.return_value = "测试提示词"

        # 模拟API响应
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="修复建议"))]
        self.mock_client.chat.completions.create.return_value = mock_response

        error = StructuredError(
            error_id="ERR-001",
            timestamp="2024-01-01",
            severity=ErrorSeverity.LOW,
            category=ErrorCategory.UNKNOWN,
            error_type="TestError",
            error_message="test",
            description="test",
            context=ErrorContext("", 0, "", "", {}, [], {}),
            traceback_str="",
            suggestions=[]
        )

        handler = GlobalErrorHandler(client=self.mock_client, auto_report=True)
        result = handler.report_to_agent(error)

        self.assertIsNotNone(result)
        self.assertEqual(result, "修复建议")
        self.mock_client.chat.completions.create.assert_called_once()


# ==========================================
# 6. 集成测试
# ==========================================

class TestIntegration(unittest.TestCase):
    """集成测试"""

    def setUp(self):
        self.mock_client = Mock()
        self.handler = GlobalErrorHandler(
            client=self.mock_client,
            auto_report=False,
            max_history=50
        )

    def tearDown(self):
        if self.handler._is_installed:
            self.handler.uninstall()

    def test_full_error_pipeline(self):
        """测试完整错误处理流程"""
        # 1. 模拟一个网络请求错误
        try:
            import requests
            raise requests.ConnectionError("无法连接到服务器")
        except Exception as e:
            # 2. 捕获错误
            error = self.handler.capture_error(
                e,
                context="测试网络请求失败"
            )

        # 3. 验证结构化信息
        self.assertEqual(error.category, ErrorCategory.NETWORK)
        self.assertEqual(error.error_type, "ConnectionError")
        self.assertIn("无法连接到服务器", error.error_message)

        # 4. 验证生成了建议
        self.assertTrue(len(error.suggestions) > 0)

        # 5. 验证格式化输出
        short = ErrorFormatter.format_short(error)
        self.assertIn("ConnectionError", short)

        llm_prompt = ErrorFormatter.format_for_llm(error)
        self.assertIn("系统错误报告", llm_prompt)
        self.assertIn("Agent 处理指令", llm_prompt)

    def test_decorator_error_handling(self):
        """测试装饰器错误处理"""
        handler = GlobalErrorHandler(client=None, auto_report=False)

        @with_error_handling(handler, context="测试装饰器")
        def failing_function():
            raise ValueError("装饰器测试错误")

        with self.assertRaises(ValueError):
            failing_function()

        # 验证错误被记录
        history = handler.get_error_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].error_type, "ValueError")
        self.assertIn("装饰器", history[0].description)

    def test_decorator_success_case(self):
        """测试装饰器正常执行"""
        handler = GlobalErrorHandler(client=None, auto_report=False)

        @with_error_handling(handler)
        def success_function():
            return 42

        result = success_function()
        self.assertEqual(result, 42)
        self.assertEqual(len(handler.error_history), 0)

    def test_error_context_extraction(self):
        """测试错误上下文提取"""
        def inner_function():
            local_var = "test_value"
            raise RuntimeError("上下文测试")

        try:
            inner_function()
        except Exception as e:
            error = self.handler.capture_error(e)

        self.assertIsNotNone(error.context.file_path)
        self.assertIsNotNone(error.context.function_name)
        self.assertIn("inner_function", error.context.function_name)

    def test_multiple_error_types(self):
        """测试多种错误类型"""
        errors = [
            (SyntaxError("invalid syntax"), ErrorCategory.SYNTAX),
            (ValueError("bad value"), ErrorCategory.DATA),
            (ConnectionError("failed"), ErrorCategory.NETWORK),
            (FileNotFoundError("missing"), ErrorCategory.CONFIG),
        ]

        for exc, expected_category in errors:
            handler = GlobalErrorHandler(client=None, auto_report=False)
            try:
                raise exc
            except Exception as e:
                error = handler.capture_error(e)

            self.assertEqual(
                error.category,
                expected_category,
                f"{type(exc).__name__} 应该被分类为 {expected_category.value}"
            )

    def test_keyboard_interrupt_not_caught(self):
        """测试KeyboardInterrupt不被全局捕获"""
        self.handler.install()

        # 模拟KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            try:
                raise KeyboardInterrupt()
            except KeyboardInterrupt:
                # 应该正常抛出
                raise


# ==========================================
# 7. 配置测试
# ==========================================

class TestErrorHandlerConfig(unittest.TestCase):
    """测试配置管理"""

    def test_default_config(self):
        """测试默认配置"""
        config = ErrorHandlerConfig()
        self.assertTrue(config.get("auto_report"))
        self.assertEqual(config.get("max_history"), 50)
        self.assertEqual(config.get("max_retries"), 3)

    def test_custom_config(self):
        """测试自定义配置"""
        config = ErrorHandlerConfig()
        config.set("auto_report", False)
        config.set("max_history", 100)

        self.assertFalse(config.get("auto_report"))
        self.assertEqual(config.get("max_history"), 100)

    def test_config_save_load(self):
        """测试配置保存和加载"""
        config = ErrorHandlerConfig()
        config.set("test_key", "test_value")

        test_path = "test_config.json"
        try:
            config.save(test_path)

            loaded_config = ErrorHandlerConfig(test_path)
            self.assertEqual(loaded_config.get("test_key"), "test_value")
        finally:
            if os.path.exists(test_path):
                os.remove(test_path)


# ==========================================
# 8. 性能测试
# ==========================================

class TestPerformance(unittest.TestCase):
    """性能测试"""

    def test_capture_performance(self):
        """测试错误捕获性能"""
        handler = GlobalErrorHandler(client=None, auto_report=False, max_history=200)

        start_time = time.time()
        for _ in range(100):
            try:
                raise ValueError("性能测试")
            except Exception as e:
                handler.capture_error(e)
        end_time = time.time()

        # 100次捕获应该在1秒内完成
        self.assertLess(end_time - start_time, 1.0)
        self.assertEqual(len(handler.error_history), 100)

    def test_format_performance(self):
        """测试格式化性能"""
        handler = GlobalErrorHandler(client=None, auto_report=False)

        try:
            raise ValueError("格式化测试")
        except Exception as e:
            error = handler.capture_error(e)

        start_time = time.time()
        for _ in range(100):
            ErrorFormatter.format_for_llm(error)
        end_time = time.time()

        # 100次格式化应该在1秒内完成
        self.assertLess(end_time - start_time, 1.0)


# ==========================================
# 运行测试
# ==========================================

if __name__ == "__main__":
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # 添加所有测试类
    test_classes = [
        TestErrorEnums,
        TestErrorContext,
        TestStructuredError,
        TestErrorFormatter,
        TestErrorClassifier,
        TestErrorRecovery,
        TestGlobalErrorHandler,
        TestIntegration,
        TestErrorHandlerConfig,
        TestPerformance,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # 输出测试摘要
    print("\n" + "="*60)
    print("测试摘要")
    print("="*60)
    print(f"总测试数: {result.testsRun}")
    print(f"通过: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"失败: {len(result.failures)}")
    print(f"错误: {len(result.errors)}")

    if result.wasSuccessful():
        print("\n✅ 所有测试通过！")
    else:
        print("\n❌ 存在失败的测试")
        sys.exit(1)
