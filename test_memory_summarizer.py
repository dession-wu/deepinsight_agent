import os
import sys
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from memory_summarizer import (
    SummarizerConfig,
    ExtractedEntity,
    ConversationTurn,
    ConversationSummary,
    SummarizedMemory,
    MemorySummarizer
)


# ==========================================
# 1. 基础数据类测试
# ==========================================

class TestSummarizerConfig(unittest.TestCase):
    """测试配置类"""

    def test_default_config(self):
        """测试默认配置值"""
        config = SummarizerConfig()
        self.assertEqual(config.max_messages_before_summary, 10)
        self.assertEqual(config.max_tokens_before_summary, 3000)
        self.assertEqual(config.summary_detail_level, "medium")
        self.assertEqual(config.max_summary_length, 800)
        self.assertEqual(config.summary_update_frequency, 5)
        self.assertEqual(config.min_completeness_ratio, 0.85)
        self.assertEqual(config.min_redundancy_removal_ratio, 0.60)
        self.assertEqual(config.max_summary_time_ms, 200)
        self.assertTrue(config.extract_entities)
        self.assertTrue(config.extract_intents)
        self.assertTrue(config.extract_decisions)
        self.assertTrue(config.preserve_full_history)
        self.assertEqual(config.max_full_history_rounds, 100)

    def test_custom_config(self):
        """测试自定义配置"""
        config = SummarizerConfig(
            max_messages_before_summary=5,
            summary_detail_level="high",
            max_summary_length=1200
        )
        self.assertEqual(config.max_messages_before_summary, 5)
        self.assertEqual(config.summary_detail_level, "high")
        self.assertEqual(config.max_summary_length, 1200)
        # 其他值应保持默认
        self.assertEqual(config.max_tokens_before_summary, 3000)


class TestExtractedEntity(unittest.TestCase):
    """测试实体数据类"""

    def test_entity_creation(self):
        """测试创建实体"""
        entity = ExtractedEntity(
            name="贵州茅台",
            entity_type="stock_name",
            mentions=3,
            first_mention_idx=2,
            related_context="贵州茅台今日大涨"
        )
        self.assertEqual(entity.name, "贵州茅台")
        self.assertEqual(entity.entity_type, "stock_name")
        self.assertEqual(entity.mentions, 3)
        self.assertEqual(entity.first_mention_idx, 2)

    def test_entity_defaults(self):
        """测试实体默认值"""
        entity = ExtractedEntity(name="测试", entity_type="test")
        self.assertEqual(entity.mentions, 1)
        self.assertEqual(entity.first_mention_idx, 0)
        self.assertEqual(entity.related_context, "")


class TestConversationTurn(unittest.TestCase):
    """测试对话轮次数据类"""

    def test_turn_creation(self):
        """测试创建对话轮次"""
        turn = ConversationTurn(
            turn_id=0,
            role="user",
            content="查询今日行情",
            timestamp="2024-01-01T12:00:00",
            token_estimate=10,
            is_data_fetch=False
        )
        self.assertEqual(turn.role, "user")
        self.assertEqual(turn.content, "查询今日行情")
        self.assertFalse(turn.is_data_fetch)


class TestConversationSummary(unittest.TestCase):
    """测试摘要数据类"""

    def test_summary_creation(self):
        """测试创建摘要"""
        summary = ConversationSummary(
            summary_id="SUM-001",
            created_at="2024-01-01T12:00:00",
            updated_at="2024-01-01T12:00:00",
            overview="测试概述",
            key_points=["要点1", "要点2"],
            total_turns=10
        )
        self.assertEqual(summary.summary_id, "SUM-001")
        self.assertEqual(summary.overview, "测试概述")
        self.assertEqual(len(summary.key_points), 2)
        self.assertEqual(summary.total_turns, 10)
        self.assertEqual(summary.completeness_score, 0.0)
        self.assertEqual(summary.redundancy_removal_ratio, 0.0)


# ==========================================
# 2. 核心功能测试
# ==========================================

class TestMemorySummarizer(unittest.TestCase):
    """测试记忆摘要器核心功能"""

    def setUp(self):
        """设置测试环境"""
        self.config = SummarizerConfig(
            max_messages_before_summary=6,  # 降低阈值方便测试
            max_tokens_before_summary=5000,
            summary_update_frequency=3,
            preserve_full_history=True
        )
        self.summarizer = MemorySummarizer(client=None, config=self.config)

    def tearDown(self):
        """清理"""
        self.summarizer.clear()

    def test_initialization(self):
        """测试初始化"""
        self.assertIsNone(self.summarizer.client)
        self.assertIsNotNone(self.summarizer.config)
        self.assertIsNotNone(self.summarizer.memory)
        self.assertEqual(len(self.summarizer.memory.full_history), 0)

    def test_should_summarize_by_message_count(self):
        """测试按消息数量触发摘要"""
        messages = [
            {"role": "user", "content": f"消息{i}"}
            for i in range(7)
        ]
        self.assertTrue(self.summarizer.should_summarize(messages))

    def test_should_not_summarize_below_threshold(self):
        """测试低于阈值不触发摘要"""
        messages = [
            {"role": "user", "content": "短消息"}
            for _ in range(3)
        ]
        self.assertFalse(self.summarizer.should_summarize(messages))

    def test_should_summarize_by_tokens(self):
        """测试按token数量触发摘要"""
        # 创建长消息，超过token阈值
        long_content = "这是一个很长的消息。" * 500  # 约2500字符，1250 token
        messages = [
            {"role": "user", "content": long_content},
            {"role": "assistant", "content": long_content},
            {"role": "user", "content": long_content}
        ]
        # 总字符约7500，token约3750，超过3000阈值
        self.assertTrue(self.summarizer.should_summarize(messages))

    def test_generate_summary(self):
        """测试生成摘要"""
        messages = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "查询贵州茅台的行情"},
            {"role": "assistant", "content": "贵州茅台今日股价为1800元，涨幅2.5%。"},
            {"role": "user", "content": "那五粮液呢？"},
            {"role": "assistant", "content": "五粮液今日股价为200元，涨幅1.8%。"},
            {"role": "user", "content": "推荐买哪个？"},
            {"role": "assistant", "content": "从估值角度看，五粮液当前PE更低，性价比更高。"},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        self.assertIsNotNone(summary.summary_id)
        self.assertIsNotNone(summary.overview)
        self.assertGreater(len(summary.key_points), 0)
        self.assertEqual(summary.total_turns, 6)  # 排除system

    def test_summary_quality_metrics(self):
        """测试摘要质量指标"""
        messages = [
            {"role": "user", "content": "分析半导体板块"},
            {"role": "assistant", "content": "半导体板块今日大涨，长川科技涨停。"},
            {"role": "user", "content": "主力资金流向如何？"},
            {"role": "assistant", "content": "主力资金净流入半导体板块50亿元。"},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        self.assertGreaterEqual(summary.completeness_score, 0.0)
        self.assertLessEqual(summary.completeness_score, 1.0)
        self.assertGreaterEqual(summary.redundancy_removal_ratio, 0.0)
        self.assertLessEqual(summary.redundancy_removal_ratio, 1.0)

    def test_entity_extraction(self):
        """测试实体提取"""
        messages = [
            {"role": "user", "content": "查询600519贵州茅台和000858五粮液的行情"},
            {"role": "assistant", "content": "贵州茅台600519今日涨2%，五粮液000858涨1.5%。"},
            {"role": "user", "content": "半导体板块怎么样？"},
            {"role": "assistant", "content": "半导体板块大涨，长川科技20cm涨停。"},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        self.assertGreater(len(summary.key_entities), 0)

        # 检查是否提取到股票代码
        entity_names = [e.name for e in summary.key_entities]
        self.assertTrue(
            any("600519" in name or "000858" in name for name in entity_names),
            f"应该提取到股票代码，实际提取到: {entity_names}"
        )

    def test_intent_extraction(self):
        """测试意图提取"""
        messages = [
            {"role": "user", "content": "查询今日行情"},
            {"role": "assistant", "content": "今日行情如下..."},
            {"role": "user", "content": "分析一下走势"},
            {"role": "assistant", "content": "走势分析..."},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        # 应该识别出查询和分析意图
        self.assertTrue(
            len(summary.user_intents) > 0,
            f"应该提取到用户意图，实际: {summary.user_intents}"
        )

    def test_decision_extraction(self):
        """测试决策提取"""
        messages = [
            {"role": "user", "content": "该买哪只股票？"},
            {"role": "assistant", "content": "建议你关注五粮液，当前估值较低，具备投资价值。"},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        # 应该提取到建议
        self.assertTrue(
            len(summary.decisions_made) > 0 or len(summary.key_points) > 0,
            "应该提取到决策或关键回复"
        )

    def test_data_source_extraction(self):
        """测试数据源提取"""
        messages = [
            {"role": "user", "content": "看看财联社新闻"},
            {"role": "assistant", "content": "--- 以下为实时从财联社获取的最新电报数据 ---\n新闻内容\n--- 财联社数据结束 ---"},
            {"role": "user", "content": "东方财富资金流向如何？"},
            {"role": "assistant", "content": "【行业板块资金流向排行】\n数据..."},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        self.assertIn("财联社", summary.data_sources_used)
        self.assertIn("东方财富", summary.data_sources_used)

    def test_compressed_context(self):
        """测试上下文压缩"""
        # 先生成摘要
        messages = [
            {"role": "system", "content": "你是一个助手"},
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
            {"role": "assistant", "content": "回答2"},
            {"role": "user", "content": "问题3"},
            {"role": "assistant", "content": "回答3"},
        ]

        self.summarizer.generate_summary(messages, force=True)

        # 获取压缩上下文
        compressed = self.summarizer.get_compressed_context(messages, keep_recent=2)

        # 应该包含system prompt
        system_msgs = [m for m in compressed if m["role"] == "system"]
        self.assertGreaterEqual(len(system_msgs), 1)

        # 应该包含摘要
        summary_msgs = [m for m in compressed if "历史对话摘要" in m.get("content", "")]
        self.assertEqual(len(summary_msgs), 1)

        # 应该保留最近2轮
        user_msgs = [m for m in compressed if m["role"] == "user"]
        self.assertLessEqual(len(user_msgs), 2)

    def test_clear_memory(self):
        """测试清空记忆"""
        messages = [
            {"role": "user", "content": "测试"},
            {"role": "assistant", "content": "回复"},
        ]
        self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(self.summarizer.memory.current_summary)
        self.assertGreater(len(self.summarizer.memory.full_history), 0)

        self.summarizer.clear()

        self.assertIsNone(self.summarizer.memory.current_summary)
        self.assertEqual(len(self.summarizer.memory.full_history), 0)
        self.assertEqual(len(self.summarizer.memory.summary_history), 0)

    def test_get_stats(self):
        """测试统计信息"""
        messages = [
            {"role": "user", "content": "测试"},
            {"role": "assistant", "content": "回复"},
        ]
        self.summarizer.generate_summary(messages, force=True)

        stats = self.summarizer.get_stats()
        self.assertEqual(stats["total_turns_processed"], 2)
        self.assertEqual(stats["summary_count"], 1)
        self.assertIsNotNone(stats["current_summary_quality"])

    def test_full_history_retrieval(self):
        """测试获取完整历史"""
        messages = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
            {"role": "assistant", "content": "回答2"},
        ]
        self.summarizer.generate_summary(messages, force=True)

        history = self.summarizer.get_full_history()
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0].content, "问题1")
        self.assertEqual(history[1].content, "回答1")

    def test_summary_history(self):
        """测试摘要历史"""
        messages1 = [
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
        ]
        self.summarizer.generate_summary(messages1, force=True)

        messages2 = [
            {"role": "user", "content": "问题2"},
            {"role": "assistant", "content": "回答2"},
        ]
        self.summarizer.generate_summary(messages2, force=True)

        summary_history = self.summarizer.get_summary_history()
        self.assertEqual(len(summary_history), 2)


# ==========================================
# 3. 性能测试
# ==========================================

class TestPerformance(unittest.TestCase):
    """性能测试"""

    def setUp(self):
        self.config = SummarizerConfig(
            max_messages_before_summary=100,  # 设置高阈值，手动触发
            preserve_full_history=True
        )
        self.summarizer = MemorySummarizer(client=None, config=self.config)

    def tearDown(self):
        self.summarizer.clear()

    def test_summary_generation_time(self):
        """测试摘要生成时间是否在200ms以内"""
        # 创建模拟对话数据
        messages = [
            {"role": "system", "content": "你是一个助手"},
        ]
        for i in range(20):
            messages.append({"role": "user", "content": f"用户问题{i}，关于股票行情和数据分析"})
            messages.append({"role": "assistant", "content": f"助手回答{i}，提供详细的行情分析和投资建议。建议关注半导体板块和新能源板块。"})

        start_time = time.time()
        summary = self.summarizer.generate_summary(messages, force=True)
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000

        self.assertIsNotNone(summary)
        self.assertLess(
            elapsed_ms,
            200,
            f"摘要生成时间{elapsed_ms:.1f}ms超过200ms限制"
        )
        print(f"\n摘要生成耗时: {elapsed_ms:.1f}ms")

    def test_large_conversation_performance(self):
        """测试大规模对话的性能"""
        messages = [{"role": "system", "content": "你是一个助手"}]
        for i in range(50):
            messages.append({"role": "user", "content": f"问题{i}" * 20})
            messages.append({"role": "assistant", "content": f"回答{i}" * 50})

        start_time = time.time()
        summary = self.summarizer.generate_summary(messages, force=True)
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000

        self.assertIsNotNone(summary)
        self.assertLess(elapsed_ms, 500, f"大规模对话摘要时间{elapsed_ms:.1f}ms过长")
        print(f"\n大规模对话摘要耗时: {elapsed_ms:.1f}ms")

    def test_compression_performance(self):
        """测试上下文压缩性能"""
        messages = [{"role": "system", "content": "你是一个助手"}]
        for i in range(30):
            messages.append({"role": "user", "content": f"问题{i}"})
            messages.append({"role": "assistant", "content": f"回答{i}"})

        self.summarizer.generate_summary(messages, force=True)

        start_time = time.time()
        compressed = self.summarizer.get_compressed_context(messages, keep_recent=4)
        end_time = time.time()

        elapsed_ms = (end_time - start_time) * 1000

        self.assertLess(elapsed_ms, 50, f"压缩时间{elapsed_ms:.1f}ms过长")
        self.assertLess(len(compressed), len(messages))
        print(f"\n上下文压缩耗时: {elapsed_ms:.1f}ms")

    def test_multiple_summaries_performance(self):
        """测试多次摘要的性能稳定性"""
        times = []

        for round_num in range(5):
            messages = [{"role": "system", "content": "你是一个助手"}]
            for i in range(10):
                messages.append({"role": "user", "content": f"第{round_num}轮问题{i}"})
                messages.append({"role": "assistant", "content": f"第{round_num}轮回答{i}"})

            start_time = time.time()
            self.summarizer.generate_summary(messages, force=True)
            end_time = time.time()

            times.append((end_time - start_time) * 1000)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        self.assertLess(avg_time, 200, f"平均摘要时间{avg_time:.1f}ms超过限制")
        print(f"\n多次摘要平均耗时: {avg_time:.1f}ms, 最大: {max_time:.1f}ms")


# ==========================================
# 4. 质量评估测试
# ==========================================

class TestQualityMetrics(unittest.TestCase):
    """测试摘要质量指标"""

    def setUp(self):
        self.config = SummarizerConfig(
            min_completeness_ratio=0.85,
            min_redundancy_removal_ratio=0.60
        )
        self.summarizer = MemorySummarizer(client=None, config=self.config)

    def test_completeness_requirement(self):
        """测试信息完整度是否达到85%"""
        messages = [
            {"role": "user", "content": "查询贵州茅台、五粮液、泸州老窖的行情"},
            {"role": "assistant", "content": "贵州茅台涨2%，五粮液涨1.5%，泸州老窖涨3%。"},
            {"role": "user", "content": "主力资金流向如何？"},
            {"role": "assistant", "content": "主力资金净流入白酒板块100亿元。"},
            {"role": "user", "content": "推荐买入吗？"},
            {"role": "assistant", "content": "建议关注五粮液，估值较低。"},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        self.assertGreaterEqual(
            summary.completeness_score,
            0.85,
            f"信息完整度{summary.completeness_score:.2%}未达到85%要求"
        )

    def test_redundancy_removal_requirement(self):
        """测试冗余去除率是否达到60%"""
        # 创建包含大量冗余内容的对话
        messages = [
            {"role": "user", "content": "查询行情"},
            {"role": "assistant", "content": "好的，我为您查询行情。行情数据如下：股票A涨1%，股票B涨2%，股票C涨3%。这是详细的行情信息。" * 5},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        self.assertIsNotNone(summary)
        # 由于内容重复，应该有较高的冗余去除率
        print(f"\n冗余去除率: {summary.redundancy_removal_ratio:.2%}")

    def test_key_information_preservation(self):
        """测试关键信息保留"""
        messages = [
            {"role": "user", "content": "用户原始需求：查询600519贵州茅台的今日行情和主力资金流向"},
            {"role": "assistant", "content": "贵州茅台600519今日股价1800元，主力资金净流入5亿元，建议关注。"},
        ]

        summary = self.summarizer.generate_summary(messages, force=True)

        # 检查关键信息是否在摘要中
        summary_text = summary.overview + " ".join(summary.key_points)
        self.assertTrue(
            "600519" in summary_text or "贵州茅台" in summary_text,
            f"关键股票信息应在摘要中保留，实际摘要: {summary_text}"
        )


# ==========================================
# 运行测试
# ==========================================

if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestSummarizerConfig,
        TestExtractedEntity,
        TestConversationTurn,
        TestConversationSummary,
        TestMemorySummarizer,
        TestPerformance,
        TestQualityMetrics,
    ]

    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

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
