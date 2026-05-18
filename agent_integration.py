"""
多智能体框架与现有系统集成模块
实现 DeepInsight Agent 的多智能体协作能力

作者: AI Product Architect
版本: 1.0.0
日期: 2025-05-12
"""

import asyncio
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# 导入多智能体框架
from multi_agent_framework import (
    MultiAgentSystem,
    AgentInterface,
    Task,
    TaskStatus,
    AgentRole,
    AgentProfile,
    AgentCapability,
    MessageType,
    AgentMessage
)

# 导入数据获取函数（独立模块，避免循环导入）
from data_fetchers import (
    fetch_cls_telegraph,
    fetch_eastmoney_industry_capital_flow,
    fetch_eastmoney_stock_spot
)
from error_handler import GlobalErrorHandler, ErrorFormatter
from memory_summarizer import MemorySummarizer


class DeepInsightMultiAgent:
    """
    DeepInsight 多智能体集成类
    将多智能体框架与现有的单智能体系统无缝集成
    """
    
    def __init__(self, client, error_handler: GlobalErrorHandler, summarizer: MemorySummarizer):
        self.client = client
        self.error_handler = error_handler
        self.summarizer = summarizer
        
        # 初始化多智能体系统
        self.multi_agent_system = MultiAgentSystem(llm_client=client)
        self.interface: Optional[AgentInterface] = None
        
        # 用户会话管理
        self.user_sessions: Dict[str, Dict] = {}
        
        # 任务跟踪
        self.pending_tasks: Dict[str, Dict] = {}
        
    async def initialize(self):
        """初始化多智能体系统"""
        await self.multi_agent_system.initialize()
        self.interface = self.multi_agent_system.interface
        print("✅ 多智能体系统初始化完成")
        
    async def process_user_request(self, user_id: str, user_input: str) -> str:
        """
        处理用户请求，使用多智能体协作架构
        
        Args:
            user_id: 用户ID
            user_input: 用户输入
            
        Returns:
            处理结果
        """
        # 1. 意图识别与任务分解
        intent = self._recognize_intent(user_input)
        print(f"\n🔍 识别到用户意图: {intent['type']}")
        
        # 2. 根据意图类型选择处理方式
        if intent['type'] in ['data_query', 'market_analysis', 'stock_analysis']:
            # 使用多智能体协作处理复杂任务
            return await self._process_with_multi_agent(user_id, user_input, intent)
        else:
            # 简单查询使用原有单智能体处理
            return await self._process_with_single_agent(user_id, user_input)
    
    def _recognize_intent(self, user_input: str) -> Dict:
        """
        识别用户意图
        
        Returns:
            意图类型和相关信息
        """
        # 财联社触发关键词
        cls_keywords = ["财联社", "电报", "快讯", "最新财经", "财经新闻", "资讯", "新闻"]
        # 东方财富触发关键词
        em_keywords = ["东方财富", "资金流向", "板块资金", "行业资金", "主力净流入", "行情", "股票行情", "A股行情"]
        # 分析类关键词
        analysis_keywords = ["分析", "预测", "趋势", "建议", "策略", "投资", "价值"]
        # 个股关键词
        stock_keywords = ["股票", "个股", "茅台", "五粮液", "比亚迪", "腾讯", "阿里"]
        
        intent = {"type": "general", "data_sources": [], "requires_analysis": False}
        
        # 检测数据源需求
        if any(kw in user_input for kw in cls_keywords):
            intent["data_sources"].append("cailianshe")
        if any(kw in user_input for kw in em_keywords):
            intent["data_sources"].extend(["eastmoney_capital", "eastmoney_spot"])
            
        # 检测是否需要分析
        if any(kw in user_input for kw in analysis_keywords):
            intent["requires_analysis"] = True
            
        # 检测是否涉及个股
        if any(kw in user_input for kw in stock_keywords):
            intent["has_stock"] = True
            
        # 确定意图类型
        if intent["data_sources"] and intent["requires_analysis"]:
            intent["type"] = "market_analysis"
        elif intent["data_sources"]:
            intent["type"] = "data_query"
        elif intent.get("has_stock"):
            intent["type"] = "stock_analysis"
            
        return intent
    
    async def _process_with_multi_agent(self, user_id: str, user_input: str, intent: Dict) -> str:
        """
        使用多智能体协作处理复杂任务
        
        流程:
        1. 数据采集智能体获取实时数据
        2. 分析智能体进行数据分析
        3. 决策智能体生成建议
        4. 交互智能体格式化输出
        """
        results = []
        
        # 步骤1: 数据采集
        print("\n📡 [数据采集智能体] 正在获取实时数据...")
        data_results = await self._collect_data(intent)
        
        if not data_results:
            return "❌ 数据获取失败，请稍后重试。"
        
        results.append("✅ 数据采集完成")
        
        # 步骤2: 数据分析
        if intent.get("requires_analysis"):
            print("\n🔬 [分析智能体] 正在进行数据分析...")
            analysis_result = await self._analyze_data(user_input, data_results)
            results.append("✅ 数据分析完成")
        else:
            analysis_result = None
            
        # 步骤3: 生成综合响应
        print("\n💡 [交互智能体] 正在生成响应...")
        final_response = await self._generate_response(
            user_input, data_results, analysis_result
        )
        
        return final_response
    
    async def _collect_data(self, intent: Dict) -> List[Dict]:
        """
        根据意图收集数据
        
        Returns:
            数据结果列表
        """
        data_results = []
        
        for source in intent.get("data_sources", []):
            try:
                if source == "cailianshe":
                    data = fetch_cls_telegraph(num_items=20)
                    if not data.startswith("❌") and not data.startswith("⚠️"):
                        data_results.append({
                            "source": "财联社",
                            "type": "news",
                            "data": data,
                            "timestamp": datetime.now().isoformat()
                        })
                        print(f"   ✓ 财联社数据获取成功")
                        
                elif source == "eastmoney_capital":
                    data = fetch_eastmoney_industry_capital_flow()
                    if not data.startswith("❌") and not data.startswith("⚠️"):
                        data_results.append({
                            "source": "东方财富-资金流向",
                            "type": "capital_flow",
                            "data": data,
                            "timestamp": datetime.now().isoformat()
                        })
                        print(f"   ✓ 东方财富资金流向数据获取成功")
                        
                elif source == "eastmoney_spot":
                    data = fetch_eastmoney_stock_spot()
                    if not data.startswith("❌") and not data.startswith("⚠️"):
                        data_results.append({
                            "source": "东方财富-行情",
                            "type": "market_spot",
                            "data": data,
                            "timestamp": datetime.now().isoformat()
                        })
                        print(f"   ✓ 东方财富行情数据获取成功")
                        
            except Exception as e:
                print(f"   ✗ {source} 数据获取失败: {e}")
                continue
                
        return data_results
    
    async def _analyze_data(self, user_query: str, data_results: List[Dict]) -> Dict:
        """
        使用LLM分析数据
        
        Args:
            user_query: 用户原始查询
            data_results: 收集的数据结果
            
        Returns:
            分析结果
        """
        # 构建分析提示
        data_summary = "\n\n".join([
            f"【{d['source']}】\n{d['data'][:1000]}"  # 限制每份数据长度
            for d in data_results
        ])
        
        analysis_prompt = f"""
基于以下实时金融数据，分析回答用户问题："{user_query}"

{data_summary}

请提供：
1. 数据概览与关键发现
2. 市场趋势分析
3. 潜在机会或风险提示
4. 简明扼要的投资建议

请用中文回答，保持客观专业。
"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-v4-flash",
                messages=[
                    {"role": "system", "content": "你是专业的金融数据分析师。"},
                    {"role": "user", "content": analysis_prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            analysis_text = response.choices[0].message.content
            
            return {
                "analysis": analysis_text,
                "data_sources": [d['source'] for d in data_results],
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            structured_error = self.error_handler.capture_error(e, context="数据分析失败")
            return {
                "analysis": f"数据分析过程中遇到错误: {structured_error['message']}",
                "error": True,
                "timestamp": datetime.now().isoformat()
            }
    
    async def _generate_response(self, user_query: str, 
                                  data_results: List[Dict],
                                  analysis_result: Optional[Dict]) -> str:
        """
        生成最终响应
        
        Args:
            user_query: 用户原始查询
            data_results: 数据结果
            analysis_result: 分析结果
            
        Returns:
            格式化响应
        """
        if analysis_result and not analysis_result.get("error"):
            # 有分析结果时，整合数据和结论
            response_parts = []
            
            # 添加数据来源说明
            sources = ", ".join([d['source'] for d in data_results])
            response_parts.append(f"📊 基于 {sources} 的实时数据：\n")
            
            # 添加分析结论
            response_parts.append(analysis_result['analysis'])
            
            # 添加数据时间戳
            response_parts.append(f"\n⏰ 数据更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            
            return "\n".join(response_parts)
        else:
            # 无分析结果时，直接展示数据
            response_parts = ["📊 实时数据：\n"]
            for data in data_results:
                response_parts.append(f"\n【{data['source']}】\n{data['data'][:800]}")
            return "\n".join(response_parts)
    
    async def _process_with_single_agent(self, user_id: str, user_input: str) -> str:
        """
        使用单智能体处理简单查询
        保持与原有系统兼容
        """
        # 这里返回一个标记，表示应该使用原有系统处理
        return "__USE_SINGLE_AGENT__"
    
    def get_system_status(self) -> Dict:
        """获取多智能体系统状态"""
        if self.multi_agent_system:
            return self.multi_agent_system.get_system_overview()
        return {"status": "not_initialized"}
    
    async def shutdown(self):
        """关闭多智能体系统"""
        if self.multi_agent_system:
            await self.multi_agent_system.shutdown()
            print("✅ 多智能体系统已安全关闭")


# ==========================================
# 使用示例和测试
# ==========================================

async def test_multi_agent_integration():
    """测试多智能体集成"""
    from main import client, error_handler, summarizer
    
    # 创建集成实例
    integration = DeepInsightMultiAgent(client, error_handler, summarizer)
    
    # 初始化
    await integration.initialize()
    
    # 测试用户请求
    test_queries = [
        "分析一下今天的市场行情",
        "财联社有什么最新消息",
        "看看资金流向排行",
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"用户查询: {query}")
        print('='*60)
        
        result = await integration.process_user_request("test_user", query)
        if result != "__USE_SINGLE_AGENT__":
            print(f"\n🤖 响应:\n{result[:500]}...")
        else:
            print("\n🤖 使用单智能体处理")
    
    # 获取系统状态
    print(f"\n{'='*60}")
    print("系统状态:")
    print('='*60)
    status = integration.get_system_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    # 关闭系统
    await integration.shutdown()


if __name__ == "__main__":
    asyncio.run(test_multi_agent_integration())
