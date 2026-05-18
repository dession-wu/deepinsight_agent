"""
多智能体协作架构框架 (Multi-Agent Collaboration Framework)
基于 DeepInsight Agent 项目的功能扩展方案

作者: AI Product Architect
版本: 1.0.0
日期: 2025-05-11
"""

import os
import json
import time
import uuid
import asyncio
import hashlib
from enum import Enum, auto
from typing import Dict, List, Any, Optional, Callable, Set, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import defaultdict
import threading
from queue import PriorityQueue
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ==========================================
# 1. 智能体角色定义与职责划分
# ==========================================

class AgentRole(Enum):
    """智能体角色枚举"""
    ORCHESTRATOR = "orchestrator"      # 协调者：负责任务分解与调度
    DATA_COLLECTOR = "data_collector"  # 数据采集者：负责外部数据获取
    ANALYZER = "analyzer"              # 分析者：负责数据分析与洞察
    DECISION_MAKER = "decision_maker"  # 决策者：负责策略生成与决策
    EXECUTOR = "executor"              # 执行者：负责具体操作执行
    MONITOR = "monitor"                # 监控者：负责系统监控与告警
    LEARNER = "learner"                # 学习者：负责知识积累与模型优化
    INTERFACE = "interface"            # 交互者：负责用户交互与反馈


class AgentStatus(Enum):
    """智能体状态枚举"""
    IDLE = "idle"                      # 空闲
    BUSY = "busy"                      # 忙碌
    ERROR = "error"                    # 错误
    OFFLINE = "offline"                # 离线
    LEARNING = "learning"              # 学习中


@dataclass
class AgentCapability:
    """智能体能力定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]       # 输入参数Schema
    output_schema: Dict[str, Any]      # 输出参数Schema
    performance_score: float = 0.0     # 性能评分 (0-1)
    success_rate: float = 0.0          # 成功率 (0-1)
    avg_execution_time: float = 0.0    # 平均执行时间(ms)
    call_count: int = 0                # 调用次数


@dataclass
class AgentProfile:
    """智能体档案"""
    agent_id: str
    name: str
    role: AgentRole
    description: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 资源限制
    max_concurrent_tasks: int = 5
    current_task_count: int = 0
    
    # 性能指标
    total_tasks_completed: int = 0
    total_tasks_failed: int = 0
    average_response_time: float = 0.0
    
    # 权限级别
    permission_level: int = 1          # 1-10，10为最高
    allowed_actions: Set[str] = field(default_factory=set)
    restricted_actions: Set[str] = field(default_factory=set)


class BaseAgent:
    """智能体基类"""
    
    def __init__(self, profile: AgentProfile):
        self.profile = profile
        self.message_queue = asyncio.Queue()
        self.task_history: List[Dict] = []
        self.knowledge_base: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        
    async def process_message(self, message: 'AgentMessage') -> Optional['AgentMessage']:
        """处理接收到的消息"""
        raise NotImplementedError
        
    async def execute_task(self, task: 'Task') -> 'TaskResult':
        """执行任务"""
        raise NotImplementedError
        
    def update_capability_score(self, capability_name: str, success: bool, execution_time: float):
        """更新能力评分"""
        for cap in self.profile.capabilities:
            if cap.name == capability_name:
                cap.call_count += 1
                # 使用指数移动平均更新成功率
                alpha = 0.1
                cap.success_rate = (1 - alpha) * cap.success_rate + alpha * (1.0 if success else 0.0)
                # 更新平均执行时间
                cap.avg_execution_time = ((cap.avg_execution_time * (cap.call_count - 1)) + execution_time) / cap.call_count
                break
                
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.profile.agent_id,
            "name": self.profile.name,
            "role": self.profile.role.value,
            "status": self.profile.status.value,
            "capabilities": [asdict(cap) for cap in self.profile.capabilities],
            "performance": {
                "total_completed": self.profile.total_tasks_completed,
                "total_failed": self.profile.total_tasks_failed,
                "avg_response_time": self.profile.average_response_time
            }
        }


# 具体智能体实现

class OrchestratorAgent(BaseAgent):
    """协调者智能体 - 负责任务分解与调度"""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.task_decomposition_rules: Dict[str, Callable] = {}
        
    async def process_message(self, message: 'AgentMessage') -> Optional['AgentMessage']:
        if message.message_type == MessageType.TASK_ASSIGNMENT:
            # 分解任务并分配给合适的智能体
            subtasks = self._decompose_task(message.payload)
            return AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id=self.profile.agent_id,
                receiver_id=message.sender_id,  # 回复给调度器
                message_type=MessageType.TASK_DECOMPOSED,
                payload={"subtasks": subtasks, "original_task": message.payload},
                timestamp=datetime.now().isoformat()
            )
        return None
        
    def _decompose_task(self, task: Dict) -> List[Dict]:
        """任务分解逻辑"""
        task_type = task.get("type", "default")
        
        decomposition_strategies = {
            "data_analysis": self._decompose_data_analysis_task,
            "market_research": self._decompose_market_research_task,
            "portfolio_optimization": self._decompose_portfolio_task,
            "risk_assessment": self._decompose_risk_task,
        }
        
        strategy = decomposition_strategies.get(task_type, self._default_decomposition)
        return strategy(task)
        
    def _decompose_data_analysis_task(self, task: Dict) -> List[Dict]:
        """分解数据分析任务"""
        return [
            {"type": "data_collection", "priority": 1, "agent_role": AgentRole.DATA_COLLECTOR},
            {"type": "data_cleaning", "priority": 2, "agent_role": AgentRole.ANALYZER, "depends_on": [0]},
            {"type": "analysis", "priority": 3, "agent_role": AgentRole.ANALYZER, "depends_on": [1]},
            {"type": "report_generation", "priority": 4, "agent_role": AgentRole.INTERFACE, "depends_on": [2]},
        ]
        
    def _decompose_market_research_task(self, task: Dict) -> List[Dict]:
        """分解市场研究任务"""
        return [
            {"type": "news_collection", "priority": 1, "agent_role": AgentRole.DATA_COLLECTOR},
            {"type": "sentiment_analysis", "priority": 2, "agent_role": AgentRole.ANALYZER, "depends_on": [0]},
            {"type": "trend_prediction", "priority": 3, "agent_role": AgentRole.DECISION_MAKER, "depends_on": [1]},
        ]
        
    def _decompose_portfolio_task(self, task: Dict) -> List[Dict]:
        """分解投资组合优化任务"""
        return [
            {"type": "portfolio_data_collection", "priority": 1, "agent_role": AgentRole.DATA_COLLECTOR},
            {"type": "risk_analysis", "priority": 2, "agent_role": AgentRole.ANALYZER, "depends_on": [0]},
            {"type": "optimization", "priority": 3, "agent_role": AgentRole.DECISION_MAKER, "depends_on": [1]},
            {"type": "execution_plan", "priority": 4, "agent_role": AgentRole.EXECUTOR, "depends_on": [2]},
        ]
        
    def _decompose_risk_task(self, task: Dict) -> List[Dict]:
        """分解风险评估任务"""
        return [
            {"type": "market_data_collection", "priority": 1, "agent_role": AgentRole.DATA_COLLECTOR},
            {"type": "volatility_calculation", "priority": 2, "agent_role": AgentRole.ANALYZER, "depends_on": [0]},
            {"type": "risk_report", "priority": 3, "agent_role": AgentRole.INTERFACE, "depends_on": [1]},
        ]
        
    def _default_decomposition(self, task: Dict) -> List[Dict]:
        """默认任务分解"""
        return [
            {"type": "data_collection", "priority": 1, "agent_role": AgentRole.DATA_COLLECTOR},
            {"type": "analysis", "priority": 2, "agent_role": AgentRole.ANALYZER, "depends_on": [0]},
            {"type": "response", "priority": 3, "agent_role": AgentRole.INTERFACE, "depends_on": [1]},
        ]


class DataCollectorAgent(BaseAgent):
    """数据采集者智能体 - 负责外部数据获取"""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.data_sources: Dict[str, Callable] = {}
        self.cache: Dict[str, Any] = {}
        self.cache_ttl: int = 300  # 5分钟缓存
        
    async def execute_task(self, task: 'Task') -> 'TaskResult':
        start_time = time.time()
        
        try:
            data_type = task.payload.get("data_type")
            source = task.payload.get("source")
            params = task.payload.get("params", {})
            
            # 检查缓存
            cache_key = self._generate_cache_key(data_type, source, params)
            if cache_key in self.cache:
                cached_data, timestamp = self.cache[cache_key]
                if time.time() - timestamp < self.cache_ttl:
                    return TaskResult(
                        task_id=task.task_id,
                        status=TaskStatus.COMPLETED,
                        result=cached_data,
                        execution_time=(time.time() - start_time) * 1000,
                        agent_id=self.profile.agent_id
                    )
            
            # 执行数据获取
            data = await self._fetch_data(data_type, source, params)
            
            # 更新缓存
            self.cache[cache_key] = (data, time.time())
            
            execution_time = (time.time() - start_time) * 1000
            self.update_capability_score("data_collection", True, execution_time)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=data,
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.update_capability_score("data_collection", False, execution_time)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
    async def _fetch_data(self, data_type: str, source: str, params: Dict) -> Any:
        """获取数据的具体实现"""
        # 这里可以集成现有的数据获取函数
        if source == "cailianshe":
            from main import fetch_cls_telegraph
            return fetch_cls_telegraph(params.get("num_items", 20))
        elif source == "eastmoney":
            from main import fetch_eastmoney_industry_capital_flow, fetch_eastmoney_stock_spot
            if data_type == "capital_flow":
                return fetch_eastmoney_industry_capital_flow()
            else:
                return fetch_eastmoney_stock_spot()
        else:
            raise ValueError(f"Unknown data source: {source}")
            
    def _generate_cache_key(self, data_type: str, source: str, params: Dict) -> str:
        """生成缓存键"""
        key_str = f"{data_type}:{source}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(key_str.encode()).hexdigest()


class AnalyzerAgent(BaseAgent):
    """分析者智能体 - 负责数据分析与洞察"""
    
    def __init__(self, profile: AgentProfile, llm_client=None):
        super().__init__(profile)
        self.llm_client = llm_client
        self.analysis_models: Dict[str, Callable] = {}
        
    async def execute_task(self, task: 'Task') -> 'TaskResult':
        start_time = time.time()
        
        try:
            analysis_type = task.payload.get("analysis_type")
            data = task.payload.get("data")
            
            if analysis_type == "sentiment":
                result = await self._sentiment_analysis(data)
            elif analysis_type == "trend":
                result = await self._trend_analysis(data)
            elif analysis_type == "correlation":
                result = await self._correlation_analysis(data)
            else:
                result = await self._general_analysis(data)
                
            execution_time = (time.time() - start_time) * 1000
            self.update_capability_score("analysis", True, execution_time)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.update_capability_score("analysis", False, execution_time)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
    async def _sentiment_analysis(self, data: Any) -> Dict:
        """情感分析"""
        # 实现情感分析逻辑
        return {"sentiment": "positive", "score": 0.75, "details": {}}
        
    async def _trend_analysis(self, data: Any) -> Dict:
        """趋势分析"""
        return {"trend": "upward", "confidence": 0.8, "prediction": {}}
        
    async def _correlation_analysis(self, data: Any) -> Dict:
        """相关性分析"""
        return {"correlations": {}, "significant_pairs": []}
        
    async def _general_analysis(self, data: Any) -> Dict:
        """通用分析"""
        if self.llm_client:
            # 使用LLM进行分析
            prompt = f"请分析以下数据并提供洞察：\n{json.dumps(data, ensure_ascii=False)[:2000]}"
            # 这里调用LLM
            return {"analysis": "基于LLM的分析结果", "insights": []}
        return {"analysis": "基础分析完成", "data_summary": str(data)[:500]}


class DecisionMakerAgent(BaseAgent):
    """决策者智能体 - 负责策略生成与决策"""
    
    def __init__(self, profile: AgentProfile, llm_client=None):
        super().__init__(profile)
        self.llm_client = llm_client
        self.decision_history: List[Dict] = []
        
    async def execute_task(self, task: 'Task') -> 'TaskResult':
        start_time = time.time()
        
        try:
            decision_type = task.payload.get("decision_type")
            context = task.payload.get("context", {})
            constraints = task.payload.get("constraints", {})
            
            # 生成决策
            decision = await self._make_decision(decision_type, context, constraints)
            
            # 记录决策历史
            self.decision_history.append({
                "timestamp": datetime.now().isoformat(),
                "type": decision_type,
                "decision": decision,
                "context": context
            })
            
            execution_time = (time.time() - start_time) * 1000
            self.update_capability_score("decision_making", True, execution_time)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=decision,
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self.update_capability_score("decision_making", False, execution_time)
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
    async def _make_decision(self, decision_type: str, context: Dict, constraints: Dict) -> Dict:
        """做出决策"""
        if self.llm_client:
            prompt = f"""基于以下上下文做出{decision_type}决策：
            
上下文：{json.dumps(context, ensure_ascii=False)}
约束条件：{json.dumps(constraints, ensure_ascii=False)}

请提供：
1. 决策建议
2. 置信度评分 (0-1)
3. 风险评估
4. 备选方案
"""
            # 调用LLM生成决策
            return {
                "recommendation": "基于LLM的决策建议",
                "confidence": 0.85,
                "risk_level": "medium",
                "alternatives": []
            }
        
        return {
            "recommendation": "默认决策建议",
            "confidence": 0.5,
            "risk_level": "unknown",
            "alternatives": []
        }


class InterfaceAgent(BaseAgent):
    """交互者智能体 - 负责用户交互与反馈"""
    
    def __init__(self, profile: AgentProfile):
        super().__init__(profile)
        self.user_preferences: Dict[str, Any] = {}
        self.interaction_history: List[Dict] = []
        
    async def execute_task(self, task: 'Task') -> 'TaskResult':
        start_time = time.time()
        
        try:
            interaction_type = task.payload.get("interaction_type")
            content = task.payload.get("content")
            user_id = task.payload.get("user_id")
            
            if interaction_type == "format_response":
                result = self._format_response(content, user_id)
            elif interaction_type == "collect_feedback":
                result = self._collect_feedback(content)
            elif interaction_type == "update_preferences":
                result = self._update_preferences(user_id, content)
            else:
                result = {"message": str(content), "formatted": True}
                
            execution_time = (time.time() - start_time) * 1000
            
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.COMPLETED,
                result=result,
                execution_time=execution_time,
                agent_id=self.profile.agent_id
            )
            
        except Exception as e:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error=str(e),
                execution_time=(time.time() - start_time) * 1000,
                agent_id=self.profile.agent_id
            )
            
    def _format_response(self, content: Any, user_id: str) -> Dict:
        """格式化响应"""
        preferences = self.user_preferences.get(user_id, {})
        detail_level = preferences.get("detail_level", "medium")
        
        formatted = {
            "summary": self._extract_summary(content),
            "details": content if detail_level == "high" else None,
            "visualizations": self._suggest_visualizations(content),
            "action_items": self._extract_action_items(content)
        }
        
        return formatted
        
    def _extract_summary(self, content: Any) -> str:
        """提取摘要"""
        if isinstance(content, dict):
            return content.get("summary", str(content)[:200])
        return str(content)[:200]
        
    def _suggest_visualizations(self, content: Any) -> List[str]:
        """建议可视化方式"""
        suggestions = []
        if isinstance(content, dict):
            if any(k in content for k in ["trend", "time_series"]):
                suggestions.append("line_chart")
            if any(k in content for k in ["comparison", "ranking"]):
                suggestions.append("bar_chart")
            if any(k in content for k in ["correlation", "matrix"]):
                suggestions.append("heatmap")
        return suggestions
        
    def _extract_action_items(self, content: Any) -> List[str]:
        """提取行动项"""
        items = []
        if isinstance(content, dict):
            items.extend(content.get("recommendations", []))
            items.extend(content.get("action_items", []))
        return items
        
    def _collect_feedback(self, feedback: Any) -> Dict:
        """收集用户反馈"""
        self.interaction_history.append({
            "timestamp": datetime.now().isoformat(),
            "feedback": feedback
        })
        return {"status": "feedback_recorded"}
        
    def _update_preferences(self, user_id: str, preferences: Dict) -> Dict:
        """更新用户偏好"""
        self.user_preferences[user_id] = preferences
        return {"status": "preferences_updated"}


# ==========================================
# 2. 多智能体通信协议设计
# ==========================================

class MessageType(Enum):
    """消息类型枚举"""
    TASK_ASSIGNMENT = "task_assignment"      # 任务分配
    TASK_DECOMPOSED = "task_decomposed"      # 任务分解结果
    TASK_RESULT = "task_result"              # 任务结果
    DATA_REQUEST = "data_request"            # 数据请求
    DATA_RESPONSE = "data_response"          # 数据响应
    COORDINATION = "coordination"            # 协调消息
    CONFLICT_RESOLUTION = "conflict_resolution"  # 冲突解决
    STATUS_UPDATE = "status_update"          # 状态更新
    ERROR_REPORT = "error_report"            # 错误报告
    LEARNING_UPDATE = "learning_update"      # 学习更新


@dataclass
class AgentMessage:
    """智能体间消息"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: MessageType
    payload: Dict[str, Any]
    timestamp: str
    priority: int = 5                      # 1-10，1为最高优先级
    correlation_id: Optional[str] = None   # 关联消息ID（用于追踪对话）
    ttl: int = 300                         # 生存时间（秒）
    
    def to_json(self) -> str:
        """转换为JSON"""
        return json.dumps({
            "message_id": self.message_id,
            "sender_id": self.sender_id,
            "receiver_id": self.receiver_id,
            "message_type": self.message_type.value,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "priority": self.priority,
            "correlation_id": self.correlation_id,
            "ttl": self.ttl
        }, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentMessage':
        """从JSON解析"""
        data = json.loads(json_str)
        return cls(
            message_id=data["message_id"],
            sender_id=data["sender_id"],
            receiver_id=data["receiver_id"],
            message_type=MessageType(data["message_type"]),
            payload=data["payload"],
            timestamp=data["timestamp"],
            priority=data.get("priority", 5),
            correlation_id=data.get("correlation_id"),
            ttl=data.get("ttl", 300)
        )


class MessageBus:
    """消息总线 - 智能体间通信的基础设施"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.message_queue: PriorityQueue = PriorityQueue()
        self.message_history: List[AgentMessage] = []
        self._lock = threading.Lock()
        self._running = False
        
    def subscribe(self, agent_id: str, handler: Callable):
        """订阅消息"""
        self.subscribers[agent_id].append(handler)
        logger.info(f"Agent {agent_id} subscribed to message bus")
        
    def unsubscribe(self, agent_id: str, handler: Callable):
        """取消订阅"""
        if handler in self.subscribers[agent_id]:
            self.subscribers[agent_id].remove(handler)
            
    def publish(self, message: AgentMessage):
        """发布消息"""
        with self._lock:
            self.message_queue.put((message.priority, time.time(), message))
            self.message_history.append(message)
            
            # 限制历史记录大小
            if len(self.message_history) > 10000:
                self.message_history = self.message_history[-5000:]
                
        logger.debug(f"Message {message.message_id} published")
        
    async def route_message(self, message: AgentMessage):
        """路由消息到目标智能体"""
        receiver_id = message.receiver_id
        
        # 广播消息
        if receiver_id == "*":
            for agent_id, handlers in self.subscribers.items():
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Error routing message to {agent_id}: {e}")
        # 单播消息
        elif receiver_id in self.subscribers:
            for handler in self.subscribers[receiver_id]:
                try:
                    await handler(message)
                except Exception as e:
                    logger.error(f"Error routing message to {receiver_id}: {e}")
        else:
            logger.warning(f"No subscriber found for {receiver_id}")
            
    async def start(self):
        """启动消息总线"""
        self._running = True
        while self._running:
            try:
                if not self.message_queue.empty():
                    _, _, message = self.message_queue.get_nowait()
                    await self.route_message(message)
                else:
                    await asyncio.sleep(0.01)
            except Exception as e:
                logger.error(f"Message bus error: {e}")
                
    def stop(self):
        """停止消息总线"""
        self._running = False


class ConflictResolver:
    """冲突解决器"""
    
    def __init__(self):
        self.conflict_history: List[Dict] = []
        
    async def resolve_conflict(self, conflict_type: str, 
                              conflicting_agents: List[str],
                              conflicting_data: Dict) -> Dict:
        """解决智能体间的冲突"""
        
        resolution_strategies = {
            "resource_contention": self._resolve_resource_contention,
            "data_inconsistency": self._resolve_data_inconsistency,
            "decision_conflict": self._resolve_decision_conflict,
            "priority_dispute": self._resolve_priority_dispute,
        }
        
        strategy = resolution_strategies.get(conflict_type, self._default_resolution)
        resolution = await strategy(conflicting_agents, conflicting_data)
        
        # 记录冲突历史
        self.conflict_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": conflict_type,
            "agents": conflicting_agents,
            "resolution": resolution
        })
        
        return resolution
        
    async def _resolve_resource_contention(self, agents: List[str], data: Dict) -> Dict:
        """解决资源竞争冲突"""
        # 基于优先级和负载分配资源
        priorities = data.get("priorities", {})
        loads = data.get("current_loads", {})
        
        # 计算综合得分（优先级高且负载低的优先）
        scores = {}
        for agent in agents:
            priority = priorities.get(agent, 5)
            load = loads.get(agent, 0)
            scores[agent] = (10 - priority) * 10 + (100 - load)
            
        winner = max(scores, key=scores.get)
        
        return {
            "resolution_type": "resource_allocation",
            "winner": winner,
            "reason": f"Highest priority-score combination: {scores[winner]}",
            "alternative_assignments": {a: "queued" for a in agents if a != winner}
        }
        
    async def _resolve_data_inconsistency(self, agents: List[str], data: Dict) -> Dict:
        """解决数据不一致冲突"""
        versions = data.get("data_versions", {})
        timestamps = data.get("timestamps", {})
        
        # 选择最新的数据版本
        latest_agent = max(timestamps, key=timestamps.get)
        
        return {
            "resolution_type": "data_reconciliation",
            "authoritative_source": latest_agent,
            "reason": f"Most recent data from {latest_agent}",
            "sync_required": True
        }
        
    async def _resolve_decision_conflict(self, agents: List[str], data: Dict) -> Dict:
        """解决决策冲突"""
        decisions = data.get("decisions", [])
        confidences = data.get("confidences", {})
        
        # 选择置信度最高的决策
        best_agent = max(confidences, key=confidences.get)
        
        return {
            "resolution_type": "decision_override",
            "selected_decision": decisions[agents.index(best_agent)] if best_agent in agents else None,
            "selected_agent": best_agent,
            "reason": f"Highest confidence score: {confidences[best_agent]}",
            "escalation_required": confidences[best_agent] < 0.7
        }
        
    async def _resolve_priority_dispute(self, agents: List[str], data: Dict) -> Dict:
        """解决优先级争议"""
        claimed_priorities = data.get("claimed_priorities", {})
        task_impacts = data.get("task_impacts", {})
        
        # 综合考虑优先级声明和任务影响
        final_scores = {}
        for agent in agents:
            priority = claimed_priorities.get(agent, 5)
            impact = task_impacts.get(agent, 0.5)
            final_scores[agent] = priority * impact
            
        winner = min(final_scores, key=final_scores.get)  # 分数越低优先级越高
        
        return {
            "resolution_type": "priority_adjustment",
            "winner": winner,
            "final_priority": final_scores[winner],
            "reason": "Combined priority-impact score"
        }
        
    async def _default_resolution(self, agents: List[str], data: Dict) -> Dict:
        """默认冲突解决"""
        return {
            "resolution_type": "default",
            "winner": agents[0],
            "reason": "Default first-come-first-served",
            "manual_review_required": True
        }


# ==========================================
# 3. 任务分配与调度系统
# ==========================================

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"                # 待处理
    ASSIGNED = "assigned"              # 已分配
    IN_PROGRESS = "in_progress"        # 进行中
    COMPLETED = "completed"            # 已完成
    FAILED = "failed"                  # 失败
    CANCELLED = "cancelled"            # 已取消
    TIMEOUT = "timeout"                # 超时


@dataclass
class Task:
    """任务定义"""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = 5                  # 1-10，1为最高
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    deadline: Optional[str] = None
    assigned_agent: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)  # 依赖的任务ID
    estimated_duration: float = 0.0    # 预估执行时间（秒）
    required_capabilities: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "priority": self.priority,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "created_at": self.created_at,
            "deadline": self.deadline
        }


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: TaskStatus
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0        # 执行时间（毫秒）
    agent_id: Optional[str] = None
    completed_at: str = field(default_factory=lambda: datetime.now().isoformat())


class TaskScheduler:
    """任务调度器"""
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.task_queue: PriorityQueue = PriorityQueue()
        self.active_tasks: Dict[str, Task] = {}
        self.task_results: Dict[str, TaskResult] = {}
        self.agents: Dict[str, BaseAgent] = {}
        self._lock = asyncio.Lock()
        self._running = False
        
        # 调度策略
        self.scheduling_strategy: str = "capability_based"  # capability_based / round_robin / load_balanced
        
    def register_agent(self, agent: BaseAgent):
        """注册智能体"""
        self.agents[agent.profile.agent_id] = agent
        logger.info(f"Agent {agent.profile.name} registered with scheduler")
        
    def submit_task(self, task: Task) -> str:
        """提交任务"""
        with self._lock:
            self.task_queue.put((task.priority, time.time(), task))
            self.active_tasks[task.task_id] = task
            
        logger.info(f"Task {task.task_id} submitted with priority {task.priority}")
        return task.task_id
        
    async def schedule_task(self, task: Task) -> Optional[str]:
        """为任务分配合适的智能体"""
        available_agents = [
            agent for agent in self.agents.values()
            if agent.profile.status == AgentStatus.IDLE
            and agent.profile.current_task_count < agent.profile.max_concurrent_tasks
        ]
        
        if not available_agents:
            logger.warning(f"No available agents for task {task.task_id}")
            return None
            
        # 根据调度策略选择智能体
        if self.scheduling_strategy == "capability_based":
            selected_agent = self._select_by_capability(available_agents, task)
        elif self.scheduling_strategy == "round_robin":
            selected_agent = self._select_by_round_robin(available_agents)
        else:  # load_balanced
            selected_agent = self._select_by_load(available_agents)
            
        if selected_agent:
            task.assigned_agent = selected_agent.profile.agent_id
            task.status = TaskStatus.ASSIGNED
            selected_agent.profile.current_task_count += 1
            selected_agent.profile.status = AgentStatus.BUSY
            
            # 发送任务分配消息
            message = AgentMessage(
                message_id=str(uuid.uuid4()),
                sender_id="scheduler",
                receiver_id=selected_agent.profile.agent_id,
                message_type=MessageType.TASK_ASSIGNMENT,
                payload=task.to_dict(),
                timestamp=datetime.now().isoformat(),
                priority=task.priority
            )
            self.message_bus.publish(message)
            
            return selected_agent.profile.agent_id
            
        return None
        
    def _select_by_capability(self, agents: List[BaseAgent], task: Task) -> Optional[BaseAgent]:
        """基于能力匹配选择智能体"""
        best_agent = None
        best_score = -1
        
        for agent in agents:
            score = 0
            for cap in agent.profile.capabilities:
                if cap.name in task.required_capabilities:
                    score += cap.success_rate * (1 / (1 + cap.avg_execution_time / 1000))
                    
            if score > best_score:
                best_score = score
                best_agent = agent
                
        return best_agent
        
    def _select_by_round_robin(self, agents: List[BaseAgent]) -> BaseAgent:
        """轮询选择智能体"""
        # 简单实现：选择任务数最少的
        return min(agents, key=lambda a: a.profile.total_tasks_completed)
        
    def _select_by_load(self, agents: List[BaseAgent]) -> BaseAgent:
        """基于负载选择智能体"""
        return min(agents, key=lambda a: a.profile.current_task_count)
        
    async def execute_task(self, task: Task) -> TaskResult:
        """执行任务"""
        agent = self.agents.get(task.assigned_agent)
        if not agent:
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                error="Assigned agent not found"
            )
            
        task.status = TaskStatus.IN_PROGRESS
        
        try:
            result = await asyncio.wait_for(
                agent.execute_task(task),
                timeout=60.0  # 默认60秒超时
            )
            
            # 更新智能体统计
            if result.status == TaskStatus.COMPLETED:
                agent.profile.total_tasks_completed += 1
            else:
                agent.profile.total_tasks_failed += 1
                
            agent.profile.current_task_count -= 1
            if agent.profile.current_task_count == 0:
                agent.profile.status = AgentStatus.IDLE
                
            self.task_results[task.task_id] = result
            return result
            
        except asyncio.TimeoutError:
            task.status = TaskStatus.TIMEOUT
            agent.profile.current_task_count -= 1
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.TIMEOUT,
                error="Task execution timeout"
            )
            
    async def start(self):
        """启动调度器"""
        self._running = True
        while self._running:
            try:
                if not self.task_queue.empty():
                    _, _, task = self.task_queue.get_nowait()
                    
                    # 检查依赖是否完成
                    if task.dependencies:
                        deps_completed = all(
                            dep in self.task_results and 
                            self.task_results[dep].status == TaskStatus.COMPLETED
                            for dep in task.dependencies
                        )
                        if not deps_completed:
                            # 重新放回队列
                            self.task_queue.put((task.priority, time.time(), task))
                            await asyncio.sleep(0.1)
                            continue
                            
                    # 调度任务
                    assigned = await self.schedule_task(task)
                    if assigned:
                        await self.execute_task(task)
                    else:
                        # 没有可用智能体，稍后重试
                        self.task_queue.put((task.priority, time.time() + 1, task))
                        await asyncio.sleep(0.5)
                else:
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                logger.error(f"Scheduler error: {e}")
                
    def stop(self):
        """停止调度器"""
        self._running = False


# ==========================================
# 4. 多智能体协同决策机制
# ==========================================

@dataclass
class DecisionContext:
    """决策上下文"""
    decision_id: str
    decision_type: str
    context_data: Dict[str, Any]
    participating_agents: List[str]
    deadline: Optional[str] = None
    consensus_threshold: float = 0.7       # 共识阈值


@dataclass
class AgentVote:
    """智能体投票"""
    agent_id: str
    decision_id: str
    vote: Any
    confidence: float
    reasoning: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class CollaborativeDecisionMaker:
    """协同决策器"""
    
    def __init__(self, message_bus: MessageBus):
        self.message_bus = message_bus
        self.decision_history: List[Dict] = []
        self.active_decisions: Dict[str, DecisionContext] = {}
        self.votes: Dict[str, List[AgentVote]] = defaultdict(list)
        
    async def initiate_decision(self, context: DecisionContext) -> str:
        """发起协同决策"""
        self.active_decisions[context.decision_id] = context
        
        # 广播决策请求给所有参与智能体
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id="decision_maker",
            receiver_id="*",  # 广播
            message_type=MessageType.COORDINATION,
            payload={
                "action": "request_decision",
                "decision_context": asdict(context)
            },
            timestamp=datetime.now().isoformat(),
            priority=2
        )
        self.message_bus.publish(message)
        
        logger.info(f"Decision {context.decision_id} initiated with {len(context.participating_agents)} agents")
        return context.decision_id
        
    async def submit_vote(self, vote: AgentVote):
        """提交投票"""
        self.votes[vote.decision_id].append(vote)
        
        # 检查是否达到共识
        decision = self.active_decisions.get(vote.decision_id)
        if decision:
            consensus = self._check_consensus(vote.decision_id, decision.consensus_threshold)
            if consensus:
                return await self._finalize_decision(vote.decision_id, consensus)
                
        return None
        
    def _check_consensus(self, decision_id: str, threshold: float) -> Optional[Dict]:
        """检查是否达到共识"""
        votes = self.votes[decision_id]
        if not votes:
            return None
            
        # 统计投票
        vote_counts = defaultdict(list)
        for vote in votes:
            vote_counts[str(vote.vote)].append(vote)
            
        # 找出最高票的选项
        total_votes = len(votes)
        for option, option_votes in vote_counts.items():
            vote_ratio = len(option_votes) / total_votes
            avg_confidence = sum(v.confidence for v in option_votes) / len(option_votes)
            
            if vote_ratio >= threshold and avg_confidence >= 0.6:
                return {
                    "winning_option": option,
                    "vote_ratio": vote_ratio,
                    "avg_confidence": avg_confidence,
                    "supporting_agents": [v.agent_id for v in option_votes],
                    "total_votes": total_votes
                }
                
        return None
        
    async def _finalize_decision(self, decision_id: str, consensus: Dict) -> Dict:
        """最终化决策"""
        decision = self.active_decisions.pop(decision_id, None)
        
        result = {
            "decision_id": decision_id,
            "final_decision": consensus["winning_option"],
            "consensus_ratio": consensus["vote_ratio"],
            "confidence": consensus["avg_confidence"],
            "participating_agents": consensus["supporting_agents"],
            "timestamp": datetime.now().isoformat()
        }
        
        self.decision_history.append(result)
        
        # 广播决策结果
        message = AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id="decision_maker",
            receiver_id="*",
            message_type=MessageType.COORDINATION,
            payload={
                "action": "decision_finalized",
                "result": result
            },
            timestamp=datetime.now().isoformat()
        )
        self.message_bus.publish(message)
        
        logger.info(f"Decision {decision_id} finalized with consensus {consensus['vote_ratio']:.2%}")
        return result
        
    async def get_decision_recommendation(self, context: Dict) -> Dict:
        """获取决策建议（加权投票）"""
        # 这里可以实现更复杂的决策算法，如Borda计数、Condorcet方法等
        
        # 简单实现：加权平均
        weights = context.get("agent_weights", {})
        recommendations = context.get("recommendations", [])
        
        weighted_scores = defaultdict(float)
        for rec in recommendations:
            agent_id = rec.get("agent_id")
            option = rec.get("option")
            confidence = rec.get("confidence", 0.5)
            weight = weights.get(agent_id, 1.0)
            
            weighted_scores[option] += confidence * weight
            
        if weighted_scores:
            best_option = max(weighted_scores, key=weighted_scores.get)
            return {
                "recommendation": best_option,
                "score": weighted_scores[best_option],
                "all_scores": dict(weighted_scores)
            }
            
        return {"recommendation": None, "score": 0}


# ==========================================
# 5. 用户与智能体交互界面设计
# ==========================================

@dataclass
class SystemStatus:
    """系统状态"""
    timestamp: str
    active_agents: int
    busy_agents: int
    idle_agents: int
    error_agents: int
    pending_tasks: int
    completed_tasks: int
    failed_tasks: int
    average_response_time: float
    message_queue_size: int


class AgentInterface:
    """智能体交互界面"""
    
    def __init__(self, scheduler: TaskScheduler, message_bus: MessageBus):
        self.scheduler = scheduler
        self.message_bus = message_bus
        self.user_sessions: Dict[str, Dict] = {}
        
    def get_system_status(self) -> SystemStatus:
        """获取系统状态"""
        agents = self.scheduler.agents.values()
        
        active = sum(1 for a in agents if a.profile.status != AgentStatus.OFFLINE)
        busy = sum(1 for a in agents if a.profile.status == AgentStatus.BUSY)
        idle = sum(1 for a in agents if a.profile.status == AgentStatus.IDLE)
        error = sum(1 for a in agents if a.profile.status == AgentStatus.ERROR)
        
        completed = sum(a.profile.total_tasks_completed for a in agents)
        failed = sum(a.profile.total_tasks_failed for a in agents)
        
        avg_response = (
            sum(a.profile.average_response_time for a in agents) / len(agents)
            if agents else 0
        )
        
        return SystemStatus(
            timestamp=datetime.now().isoformat(),
            active_agents=active,
            busy_agents=busy,
            idle_agents=idle,
            error_agents=error,
            pending_tasks=self.scheduler.task_queue.qsize(),
            completed_tasks=completed,
            failed_tasks=failed,
            average_response_time=avg_response,
            message_queue_size=self.scheduler.message_queue.qsize() if hasattr(self.scheduler, 'message_queue') else 0
        )
        
    def get_agent_details(self, agent_id: str) -> Optional[Dict]:
        """获取智能体详情"""
        agent = self.scheduler.agents.get(agent_id)
        if agent:
            return agent.to_dict()
        return None
        
    def get_all_agents(self) -> List[Dict]:
        """获取所有智能体信息"""
        return [agent.to_dict() for agent in self.scheduler.agents.values()]
        
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        task = self.scheduler.active_tasks.get(task_id)
        if task:
            return task.to_dict()
            
        result = self.scheduler.task_results.get(task_id)
        if result:
            return {
                "task_id": result.task_id,
                "status": result.status.value,
                "execution_time": result.execution_time,
                "agent_id": result.agent_id
            }
        return None
        
    def submit_user_request(self, user_id: str, request: str, priority: int = 5) -> str:
        """提交用户请求"""
        task = Task(
            task_id=str(uuid.uuid4()),
            task_type="user_request",
            payload={
                "user_id": user_id,
                "request": request,
                "timestamp": datetime.now().isoformat()
            },
            priority=priority
        )
        
        task_id = self.scheduler.submit_task(task)
        
        # 记录用户会话
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "tasks": [],
                "preferences": {}
            }
        self.user_sessions[user_id]["tasks"].append(task_id)
        
        return task_id
        
    def get_user_history(self, user_id: str) -> Dict:
        """获取用户历史"""
        return self.user_sessions.get(user_id, {"tasks": [], "preferences": {}})


# ==========================================
# 6. 智能体能力进化系统
# ==========================================

@dataclass
class LearningRecord:
    """学习记录"""
    record_id: str
    agent_id: str
    learning_type: str                    # skill_improvement / knowledge_acquisition / strategy_optimization
    content: Dict[str, Any]
    performance_before: float
    performance_after: float
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


class AgentEvolutionSystem:
    """智能体进化系统"""
    
    def __init__(self):
        self.learning_records: List[LearningRecord] = []
        self.knowledge_base: Dict[str, Any] = {}
        self.skill_templates: Dict[str, Dict] = {}
        self.performance_history: Dict[str, List[Dict]] = defaultdict(list)
        
    def record_performance(self, agent_id: str, task_type: str, 
                          success: bool, execution_time: float):
        """记录性能数据"""
        self.performance_history[agent_id].append({
            "timestamp": datetime.now().isoformat(),
            "task_type": task_type,
            "success": success,
            "execution_time": execution_time
        })
        
        # 限制历史记录大小
        if len(self.performance_history[agent_id]) > 1000:
            self.performance_history[agent_id] = self.performance_history[agent_id][-500:]
            
    def analyze_performance_trends(self, agent_id: str) -> Dict:
        """分析性能趋势"""
        history = self.performance_history.get(agent_id, [])
        if not history:
            return {"trend": "insufficient_data"}
            
        # 计算最近10次和之前10次的成功率对比
        recent = history[-10:]
        previous = history[-20:-10] if len(history) >= 20 else history[:10]
        
        recent_success_rate = sum(1 for h in recent if h["success"]) / len(recent)
        previous_success_rate = sum(1 for h in previous if h["success"]) / len(previous)
        
        recent_avg_time = sum(h["execution_time"] for h in recent) / len(recent)
        previous_avg_time = sum(h["execution_time"] for h in previous) / len(previous)
        
        return {
            "success_rate_trend": recent_success_rate - previous_success_rate,
            "execution_time_trend": previous_avg_time - recent_avg_time,  # 正值表示改善
            "recent_success_rate": recent_success_rate,
            "recent_avg_time": recent_avg_time,
            "trend_direction": "improving" if recent_success_rate > previous_success_rate else "declining"
        }
        
    def generate_learning_recommendations(self, agent_id: str) -> List[str]:
        """生成学习建议"""
        recommendations = []
        trends = self.analyze_performance_trends(agent_id)
        
        if trends.get("success_rate_trend", 0) < -0.1:
            recommendations.append("建议复习相关技能，近期成功率下降明显")
            
        if trends.get("execution_time_trend", 0) < 0:
            recommendations.append("建议优化执行流程，近期响应时间增加")
            
        # 检查失败模式
        history = self.performance_history.get(agent_id, [])
        recent_failures = [h for h in history[-20:] if not h["success"]]
        if len(recent_failures) > 5:
            failure_types = defaultdict(int)
            for f in recent_failures:
                failure_types[f["task_type"]] += 1
            weakest = max(failure_types, key=failure_types.get)
            recommendations.append(f"建议重点提升 {weakest} 类型任务的处理能力")
            
        return recommendations
        
    def evolve_agent_skill(self, agent_id: str, skill_name: str) -> bool:
        """进化智能体技能"""
        # 这里可以实现实际的技能进化逻辑
        # 例如：更新模型参数、调整策略参数等
        
        record = LearningRecord(
            record_id=str(uuid.uuid4()),
            agent_id=agent_id,
            learning_type="skill_improvement",
            content={"skill_name": skill_name},
            performance_before=0.7,
            performance_after=0.8
        )
        
        self.learning_records.append(record)
        logger.info(f"Agent {agent_id} skill {skill_name} evolved")
        return True
        
    def share_knowledge(self, from_agent_id: str, to_agent_id: str, knowledge_type: str):
        """在智能体间共享知识"""
        # 实现知识迁移逻辑
        logger.info(f"Knowledge {knowledge_type} shared from {from_agent_id} to {to_agent_id}")


# ==========================================
# 7. 系统安全与权限控制模块
# ==========================================

class PermissionLevel(Enum):
    """权限级别"""
    GUEST = 1
    USER = 2
    PREMIUM = 3
    ADMIN = 5
    SYSTEM = 10


class SecurityPolicy:
    """安全策略"""
    
    def __init__(self):
        self.allowed_actions: Dict[PermissionLevel, Set[str]] = {
            PermissionLevel.GUEST: {"read_public_data", "query_basic_info"},
            PermissionLevel.USER: {"read_public_data", "query_basic_info", "submit_task", "view_own_history"},
            PermissionLevel.PREMIUM: {"read_public_data", "query_basic_info", "submit_task", "view_own_history", 
                                     "access_premium_data", "custom_analysis"},
            PermissionLevel.ADMIN: {"*"},  # 所有权限
            PermissionLevel.SYSTEM: {"*"}
        }
        
        self.rate_limits: Dict[PermissionLevel, Dict[str, int]] = {
            PermissionLevel.GUEST: {"requests_per_minute": 10, "tasks_per_hour": 5},
            PermissionLevel.USER: {"requests_per_minute": 60, "tasks_per_hour": 50},
            PermissionLevel.PREMIUM: {"requests_per_minute": 120, "tasks_per_hour": 200},
            PermissionLevel.ADMIN: {"requests_per_minute": 1000, "tasks_per_hour": 1000},
            PermissionLevel.SYSTEM: {"requests_per_minute": 10000, "tasks_per_hour": 10000}
        }
        
        self.sensitive_data_patterns: List[str] = [
            r"\b\d{18}\b",  # 身份证号
            r"\b1[3-9]\d{9}\b",  # 手机号
            r"\b\d{16,19}\b",  # 银行卡号
        ]
        
    def check_permission(self, user_level: PermissionLevel, action: str) -> bool:
        """检查权限"""
        allowed = self.allowed_actions.get(user_level, set())
        return "*" in allowed or action in allowed
        
    def get_rate_limit(self, user_level: PermissionLevel) -> Dict[str, int]:
        """获取速率限制"""
        return self.rate_limits.get(user_level, {"requests_per_minute": 10, "tasks_per_hour": 5})
        
    def scan_sensitive_data(self, content: str) -> List[str]:
        """扫描敏感数据"""
        import re
        findings = []
        for pattern in self.sensitive_data_patterns:
            matches = re.findall(pattern, content)
            findings.extend(matches)
        return findings
        
    def mask_sensitive_data(self, content: str) -> str:
        """脱敏处理"""
        import re
        masked = content
        
        # 身份证号脱敏
        masked = re.sub(r"(\d{6})\d{8}(\d{4})", r"\1********\2", masked)
        # 手机号脱敏
        masked = re.sub(r"(1[3-9])\d{4}(\d{4})", r"\1****\2", masked)
        # 银行卡号脱敏
        masked = re.sub(r"(\d{4})\d{8,12}(\d{4})", r"\1 **** **** \2", masked)
        
        return masked


class SecurityManager:
    """安全管理器"""
    
    def __init__(self):
        self.policy = SecurityPolicy()
        self.user_sessions: Dict[str, Dict] = {}
        self.access_logs: List[Dict] = []
        self._lock = threading.Lock()
        
    def authenticate_user(self, user_id: str, credentials: Dict) -> Optional[PermissionLevel]:
        """用户认证"""
        # 这里应该实现实际的认证逻辑
        # 简化示例：根据用户ID返回权限级别
        
        user_levels = {
            "guest": PermissionLevel.GUEST,
            "user": PermissionLevel.USER,
            "premium": PermissionLevel.PREMIUM,
            "admin": PermissionLevel.ADMIN,
            "system": PermissionLevel.SYSTEM
        }
        
        level = user_levels.get(user_id.lower(), PermissionLevel.GUEST)
        
        with self._lock:
            self.user_sessions[user_id] = {
                "level": level,
                "login_time": datetime.now().isoformat(),
                "request_count": 0,
                "task_count": 0
            }
            
        return level
        
    def check_access(self, user_id: str, action: str) -> Tuple[bool, str]:
        """检查访问权限"""
        session = self.user_sessions.get(user_id)
        if not session:
            return False, "User not authenticated"
            
        level = session["level"]
        
        if not self.policy.check_permission(level, action):
            self._log_access(user_id, action, False, "Permission denied")
            return False, "Permission denied"
            
        # 检查速率限制
        rate_limit = self.policy.get_rate_limit(level)
        if session["request_count"] >= rate_limit["requests_per_minute"]:
            self._log_access(user_id, action, False, "Rate limit exceeded")
            return False, "Rate limit exceeded"
            
        session["request_count"] += 1
        self._log_access(user_id, action, True, "Access granted")
        return True, "Access granted"
        
    def _log_access(self, user_id: str, action: str, success: bool, message: str):
        """记录访问日志"""
        self.access_logs.append({
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "action": action,
            "success": success,
            "message": message
        })
        
        # 限制日志大小
        if len(self.access_logs) > 10000:
            self.access_logs = self.access_logs[-5000:]
            
    def audit_data_access(self, user_id: str, data_content: str) -> Dict:
        """审计数据访问"""
        # 扫描敏感数据
        sensitive_data = self.policy.scan_sensitive_data(data_content)
        
        # 脱敏处理
        masked_content = self.policy.mask_sensitive_data(data_content)
        
        audit_result = {
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "sensitive_data_found": len(sensitive_data) > 0,
            "sensitive_data_count": len(sensitive_data),
            "data_masked": True,
            "audit_passed": len(sensitive_data) == 0 or self.user_sessions.get(user_id, {}).get("level", PermissionLevel.GUEST).value >= PermissionLevel.ADMIN.value
        }
        
        return audit_result, masked_content
        
    def get_security_report(self) -> Dict:
        """获取安全报告"""
        recent_logs = self.access_logs[-100:]
        
        failed_attempts = sum(1 for log in recent_logs if not log["success"])
        unique_users = len(set(log["user_id"] for log in recent_logs))
        
        return {
            "total_access_attempts": len(recent_logs),
            "failed_attempts": failed_attempts,
            "success_rate": (len(recent_logs) - failed_attempts) / len(recent_logs) if recent_logs else 1.0,
            "unique_users": unique_users,
            "timestamp": datetime.now().isoformat()
        }


# ==========================================
# 8. 多智能体系统主控
# ==========================================

class MultiAgentSystem:
    """多智能体系统主控"""
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.message_bus = MessageBus()
        self.scheduler = TaskScheduler(self.message_bus)
        self.decision_maker = CollaborativeDecisionMaker(self.message_bus)
        self.interface = AgentInterface(self.scheduler, self.message_bus)
        self.evolution_system = AgentEvolutionSystem()
        self.security_manager = SecurityManager()
        self.conflict_resolver = ConflictResolver()
        
        self._initialized = False
        self._running = False
        
    async def initialize(self):
        """初始化系统"""
        if self._initialized:
            return
            
        logger.info("Initializing Multi-Agent System...")
        
        # 创建并注册智能体
        await self._create_default_agents()
        
        # 启动消息总线
        asyncio.create_task(self.message_bus.start())
        
        # 启动调度器
        asyncio.create_task(self.scheduler.start())
        
        self._initialized = True
        logger.info("Multi-Agent System initialized successfully")
        
    async def _create_default_agents(self):
        """创建默认智能体"""
        
        # 1. 协调者
        orchestrator = OrchestratorAgent(AgentProfile(
            agent_id="agent_orchestrator_001",
            name="任务协调者",
            role=AgentRole.ORCHESTRATOR,
            description="负责任务分解与智能体协调",
            capabilities=[
                AgentCapability("task_decomposition", "任务分解", {}, {}),
                AgentCapability("agent_coordination", "智能体协调", {}, {}),
            ],
            permission_level=10
        ))
        self.scheduler.register_agent(orchestrator)
        
        # 2. 数据采集者
        collector = DataCollectorAgent(AgentProfile(
            agent_id="agent_collector_001",
            name="数据采集者",
            role=AgentRole.DATA_COLLECTOR,
            description="负责从外部数据源获取数据",
            capabilities=[
                AgentCapability("data_collection", "数据采集", {}, {}),
                AgentCapability("api_integration", "API集成", {}, {}),
                AgentCapability("data_caching", "数据缓存", {}, {}),
            ],
            permission_level=5
        ))
        self.scheduler.register_agent(collector)
        
        # 3. 分析者
        analyzer = AnalyzerAgent(
            AgentProfile(
                agent_id="agent_analyzer_001",
                name="数据分析者",
                role=AgentRole.ANALYZER,
                description="负责数据分析和洞察生成",
                capabilities=[
                    AgentCapability("sentiment_analysis", "情感分析", {}, {}),
                    AgentCapability("trend_analysis", "趋势分析", {}, {}),
                    AgentCapability("correlation_analysis", "相关性分析", {}, {}),
                ],
                permission_level=5
            ),
            llm_client=self.llm_client
        )
        self.scheduler.register_agent(analyzer)
        
        # 4. 决策者
        decision_maker = DecisionMakerAgent(
            AgentProfile(
                agent_id="agent_decision_001",
                name="策略决策者",
                role=AgentRole.DECISION_MAKER,
                description="负责策略生成和决策",
                capabilities=[
                    AgentCapability("strategy_generation", "策略生成", {}, {}),
                    AgentCapability("risk_assessment", "风险评估", {}, {}),
                    AgentCapability("decision_optimization", "决策优化", {}, {}),
                ],
                permission_level=7
            ),
            llm_client=self.llm_client
        )
        self.scheduler.register_agent(decision_maker)
        
        # 5. 交互者
        interface_agent = InterfaceAgent(AgentProfile(
            agent_id="agent_interface_001",
            name="用户交互者",
            role=AgentRole.INTERFACE,
            description="负责用户交互和反馈",
            capabilities=[
                AgentCapability("response_formatting", "响应格式化", {}, {}),
                AgentCapability("feedback_collection", "反馈收集", {}, {}),
                AgentCapability("preference_learning", "偏好学习", {}, {}),
            ],
            permission_level=3
        ))
        self.scheduler.register_agent(interface_agent)
        
        logger.info(f"Created {len(self.scheduler.agents)} default agents")
        
    async def process_user_request(self, user_id: str, request: str, 
                                   priority: int = 5) -> str:
        """处理用户请求"""
        
        # 安全检查
        allowed, message = self.security_manager.check_access(user_id, "submit_task")
        if not allowed:
            raise PermissionError(message)
            
        # 审计数据
        audit_result, masked_request = self.security_manager.audit_data_access(user_id, request)
        if not audit_result["audit_passed"]:
            logger.warning(f"Sensitive data detected in request from {user_id}")
            
        # 提交任务
        task_id = self.interface.submit_user_request(user_id, masked_request, priority)
        
        return task_id
        
    def get_system_overview(self) -> Dict:
        """获取系统概览"""
        status = self.interface.get_system_status()
        
        return {
            "system_status": asdict(status),
            "agents": self.interface.get_all_agents(),
            "security_report": self.security_manager.get_security_report(),
            "timestamp": datetime.now().isoformat()
        }
        
    async def shutdown(self):
        """关闭系统"""
        logger.info("Shutting down Multi-Agent System...")
        
        self.scheduler.stop()
        self.message_bus.stop()
        
        self._running = False
        logger.info("Multi-Agent System shutdown complete")


# ==========================================
# 9. 使用示例
# ==========================================

async def example_usage():
    """使用示例"""
    
    # 创建多智能体系统
    system = MultiAgentSystem()
    
    # 初始化
    await system.initialize()
    
    # 用户认证
    user_level = system.security_manager.authenticate_user("premium", {})
    print(f"User authenticated with level: {user_level}")
    
    # 处理用户请求
    task_id = await system.process_user_request(
        user_id="premium",
        request="分析贵州茅台和五粮液的投资价值",
        priority=3
    )
    print(f"Task submitted: {task_id}")
    
    # 获取系统概览
    overview = system.get_system_overview()
    print(f"System overview: {json.dumps(overview, indent=2, ensure_ascii=False)}")
    
    # 关闭系统
    await system.shutdown()


if __name__ == "__main__":
    # 运行示例
    asyncio.run(example_usage())
