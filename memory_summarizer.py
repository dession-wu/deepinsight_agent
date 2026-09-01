import os
import re
import json
import time
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from collections import Counter
import threading

# 集中式配置（模型名等从环境变量读取）
import config


# ==========================================
# 配置类
# ==========================================

@dataclass
class SummarizerConfig:
    """记忆摘要器配置"""
    # 触发阈值
    max_messages_before_summary: int = 10      # 达到多少条消息后触发摘要
    max_tokens_before_summary: int = 3000      # 达到多少token后触发摘要
    
    # 摘要参数
    summary_detail_level: str = "medium"       # 详细程度: low/medium/high
    max_summary_length: int = 800              # 摘要最大字符数
    min_summary_length: int = 200              # 摘要最小字符数
    
    # 更新频率
    summary_update_frequency: int = 5          # 每新增多少轮对话更新一次摘要
    
    # 质量评估标准
    min_completeness_ratio: float = 0.85       # 信息完整度最低要求
    min_redundancy_removal_ratio: float = 0.60 # 冗余去除率最低要求
    
    # 性能限制
    max_summary_time_ms: int = 200             # 摘要生成最大耗时(ms)
    
    # 实体提取
    extract_entities: bool = True              # 是否提取关键实体
    extract_intents: bool = True               # 是否提取用户意图
    extract_decisions: bool = True             # 是否提取决策点
    
    # 存储
    preserve_full_history: bool = True         # 是否保留完整历史
    max_full_history_rounds: int = 100         # 最大保留的完整对话轮数


# ==========================================
# 数据结构
# ==========================================

@dataclass
class ExtractedEntity:
    """提取的实体"""
    name: str
    entity_type: str  # person/organization/location/stock/sector/date/number/etc
    mentions: int = 1
    first_mention_idx: int = 0
    related_context: str = ""


@dataclass
class ConversationTurn:
    """单轮对话"""
    turn_id: int
    role: str
    content: str
    timestamp: str
    token_estimate: int = 0
    is_data_fetch: bool = False  # 是否包含数据获取结果


@dataclass
class ConversationSummary:
    """对话摘要"""
    summary_id: str
    created_at: str
    updated_at: str
    
    # 摘要内容
    overview: str = ""                    # 总体概述
    key_points: List[str] = field(default_factory=list)      # 关键要点
    user_intents: List[str] = field(default_factory=list)    # 用户意图列表
    key_entities: List[ExtractedEntity] = field(default_factory=list)  # 关键实体
    decisions_made: List[str] = field(default_factory=list)  # 已做决策
    action_items: List[str] = field(default_factory=list)    # 待办/行动项
    data_sources_used: List[str] = field(default_factory=list)  # 使用的数据源
    
    # 统计信息
    total_turns: int = 0
    total_user_turns: int = 0
    total_assistant_turns: int = 0
    
    # 质量指标
    completeness_score: float = 0.0
    redundancy_removal_ratio: float = 0.0
    generation_time_ms: float = 0.0
    
    # 关联信息
    covered_turn_range: Tuple[int, int] = (0, 0)  # 覆盖的对话轮次范围
    full_history_hash: str = ""  # 关联的完整历史哈希


@dataclass
class SummarizedMemory:
    """带摘要的记忆结构"""
    # 当前活跃上下文（system prompt + 最近几轮 + 摘要）
    active_context: List[Dict[str, str]] = field(default_factory=list)
    
    # 摘要（多层）
    current_summary: Optional[ConversationSummary] = None
    summary_history: List[ConversationSummary] = field(default_factory=list)
    
    # 完整历史（可选保留）
    full_history: List[ConversationTurn] = field(default_factory=list)
    
    # 元数据
    total_turns_processed: int = 0
    summary_count: int = 0
    last_summary_turn: int = 0


# ==========================================
# 核心摘要引擎
# ==========================================

class MemorySummarizer:
    """记忆摘要引擎"""
    
    def __init__(self, client=None, config: Optional[SummarizerConfig] = None):
        """
        初始化记忆摘要器。
        
        Args:
            client: 大模型客户端（用于高质量摘要生成）
            config: 摘要配置
        """
        self.client = client
        self.config = config or SummarizerConfig()
        self.memory = SummarizedMemory()
        self._lock = threading.Lock()
        
        # 预编译正则表达式
        self._entity_patterns = {
            'stock_code': re.compile(r'(?<![\d])(\d{6})(?![\d])'),
            'stock_name': re.compile(r'[\u4e00-\u9fa5]{2,6}(?:股份|科技|集团|银行|证券|保险|基金|能源|医药|生物|软件|网络|传媒)'),
            'sector': re.compile(r'(?:半导体|芯片|新能源|光伏|锂电|人工智能|AI|医药|医疗|金融|银行|地产|消费|白酒|汽车|军工|传媒|计算机|电子|通信|化工|有色|钢铁|煤炭|石油|电力|环保|建筑|建材|家电|食品|饮料|纺织服装|轻工制造|农林牧渔|交通运输|物流|商贸零售|社会服务|教育|公共事业)'),
            'date': re.compile(r'\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?|\d{1,2}[-/月]\d{1,2}[日]?'),
            'number': re.compile(r'\d+\.?\d*\s*(?:亿|万|千|百|十|元|美元|人民币|%|个百分点|倍)'),
            'person': re.compile(r'[\u4e00-\u9fa5]{2,4}(?:先生|女士|博士|教授|经理|总监|总裁|董事长|CEO|CFO|CTO)'),
        }
    
    def should_summarize(self, messages: List[Dict[str, str]]) -> bool:
        """
        判断是否需要触发摘要。
        
        Args:
            messages: 当前消息列表
            
        Returns:
            是否需要摘要
        """
        # 排除system prompt
        conversation_messages = [m for m in messages if m.get("role") != "system"]
        
        # 检查消息数量
        if len(conversation_messages) >= self.config.max_messages_before_summary:
            return True
        
        # 检查token估算
        total_chars = sum(len(m.get("content", "")) for m in conversation_messages)
        estimated_tokens = total_chars // 2  # 粗略估算：1 token ≈ 2 中文字符
        if estimated_tokens >= self.config.max_tokens_before_summary:
            return True
        
        # 检查自上次摘要以来的新增轮数
        # 只有当已经有摘要历史时，才按频率检查
        if self.memory.summary_count > 0:
            new_turns = len(conversation_messages) - self.memory.last_summary_turn
            if new_turns >= self.config.summary_update_frequency:
                return True
        
        return False
    
    def generate_summary(self, messages: List[Dict[str, str]], 
                         force: bool = False) -> Optional[ConversationSummary]:
        """
        生成对话摘要。
        
        Args:
            messages: 完整消息列表
            force: 是否强制生成（忽略触发条件）
            
        Returns:
            生成的摘要对象，如果不需要摘要则返回None
        """
        if not force and not self.should_summarize(messages):
            return None
        
        start_time = time.time()
        
        with self._lock:
            # 提取对话轮次
            turns = self._extract_turns(messages)
            
            # 使用本地算法快速提取关键信息
            summary = self._generate_local_summary(turns)
            
            # 如果有大模型客户端，使用大模型增强摘要质量
            if self.client and len(turns) > 4:
                enhanced_summary = self._enhance_with_llm(summary, turns)
                if enhanced_summary:
                    summary = enhanced_summary
            
            # 计算质量指标
            summary.generation_time_ms = (time.time() - start_time) * 1000
            summary = self._evaluate_quality(summary, turns)
            
            # 更新记忆
            self.memory.current_summary = summary
            self.memory.summary_history.append(summary)
            self.memory.last_summary_turn = len(turns)
            self.memory.summary_count += 1
            
            # 保留完整历史
            if self.config.preserve_full_history:
                self.memory.full_history.extend(turns[self.memory.total_turns_processed:])
                if len(self.memory.full_history) > self.config.max_full_history_rounds * 2:
                    # 归档旧历史
                    self._archive_old_history()
            
            self.memory.total_turns_processed = len(turns)
            
            return summary
    
    def _extract_turns(self, messages: List[Dict[str, str]]) -> List[ConversationTurn]:
        """提取对话轮次"""
        turns = []
        turn_id = 0
        
        for msg in messages:
            role = msg.get("role", "")
            if role == "system":
                continue
                
            content = msg.get("content", "")
            is_data = any(marker in content for marker in 
                         ["--- 以下为实时", "【行业板块", "【A股实时", "财联社数据结束"])
            
            turns.append(ConversationTurn(
                turn_id=turn_id,
                role=role,
                content=content,
                timestamp=datetime.now().isoformat(),
                token_estimate=len(content) // 2,
                is_data_fetch=is_data
            ))
            turn_id += 1
        
        return turns
    
    def _generate_local_summary(self, turns: List[ConversationTurn]) -> ConversationSummary:
        """使用本地算法生成基础摘要（无需调用大模型，保证速度）"""
        summary = ConversationSummary(
            summary_id=self._generate_summary_id(),
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            total_turns=len(turns),
            total_user_turns=sum(1 for t in turns if t.role == "user"),
            total_assistant_turns=sum(1 for t in turns if t.role == "assistant"),
            covered_turn_range=(self.memory.total_turns_processed, len(turns))
        )
        
        # 提取关键实体
        if self.config.extract_entities:
            summary.key_entities = self._extract_entities(turns)
        
        # 提取用户意图
        if self.config.extract_intents:
            summary.user_intents = self._extract_intents(turns)
        
        # 提取决策点
        if self.config.extract_decisions:
            summary.decisions_made = self._extract_decisions(turns)
        
        # 识别数据源
        summary.data_sources_used = self._extract_data_sources(turns)
        
        # 生成概述和关键要点
        summary.overview = self._generate_overview(turns, summary)
        summary.key_points = self._extract_key_points(turns)
        
        # 计算历史哈希
        content_hash = hashlib.md5(
            "".join(t.content for t in turns).encode('utf-8')
        ).hexdigest()[:16]
        summary.full_history_hash = content_hash
        
        return summary
    
    def _extract_entities(self, turns: List[ConversationTurn]) -> List[ExtractedEntity]:
        """提取关键实体"""
        entity_counter = Counter()
        entity_types = {}
        entity_contexts = {}
        first_mentions = {}
        
        for idx, turn in enumerate(turns):
            content = turn.content
            
            for entity_type, pattern in self._entity_patterns.items():
                matches = pattern.findall(content)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[0]
                    match = match.strip()
                    if len(match) < 2:
                        continue
                    
                    entity_counter[match] += 1
                    entity_types[match] = entity_type
                    if match not in first_mentions:
                        first_mentions[match] = idx
                        # 保存上下文（前后50字符）
                        pos = content.find(match)
                        start = max(0, pos - 50)
                        end = min(len(content), pos + len(match) + 50)
                        entity_contexts[match] = content[start:end]
        
        # 选择最频繁的实体
        top_entities = entity_counter.most_common(20)
        extracted = []
        for name, count in top_entities:
            extracted.append(ExtractedEntity(
                name=name,
                entity_type=entity_types.get(name, "unknown"),
                mentions=count,
                first_mention_idx=first_mentions.get(name, 0),
                related_context=entity_contexts.get(name, "")[:100]
            ))
        
        return extracted
    
    def _extract_intents(self, turns: List[ConversationTurn]) -> List[str]:
        """提取用户意图"""
        intents = []
        
        # 意图关键词映射
        intent_keywords = {
            "查询数据": ["查询", "获取", "查看", "看看", "显示", "列出"],
            "分析总结": ["分析", "总结", "概括", "归纳", "解读", "评价"],
            "比较对比": ["对比", "比较", "vs", "versus", "哪个更好", "差异"],
            "预测判断": ["预测", "判断", "走势", "未来", "会涨", "会跌"],
            "操作建议": ["建议", "推荐", "应该", "怎么操作", "买入", "卖出"],
            "解释说明": ["为什么", "怎么回事", "什么是", "如何", "怎么"],
        }
        
        for turn in turns:
            if turn.role != "user":
                continue
            content = turn.content.lower()
            
            for intent, keywords in intent_keywords.items():
                if any(kw in content for kw in keywords):
                    if intent not in intents:
                        intents.append(intent)
        
        return intents
    
    def _extract_decisions(self, turns: List[ConversationTurn]) -> List[str]:
        """提取决策点和结论"""
        decisions = []
        
        # 决策标记词
        decision_markers = [
            "决定", "确定", "选择", "采用", "使用", "设置为",
            "结论是", "综上", "因此", "所以", "最终",
            "建议", "推荐", "应该", "需要", "必须"
        ]
        
        for turn in turns:
            if turn.role != "assistant":
                continue
            content = turn.content
            sentences = content.split("。")
            
            for sentence in sentences:
                if any(marker in sentence for marker in decision_markers):
                    clean = sentence.strip()
                    if len(clean) > 10 and len(clean) < 200:
                        decisions.append(clean)
        
        # 去重并限制数量
        unique_decisions = list(dict.fromkeys(decisions))[:10]
        return unique_decisions
    
    def _extract_data_sources(self, turns: List[ConversationTurn]) -> List[str]:
        """提取使用的数据源"""
        sources = set()
        
        for turn in turns:
            content = turn.content
            if "财联社" in content or "CLS" in content:
                sources.add("财联社")
            if "东方财富" in content or "Eastmoney" in content:
                sources.add("东方财富")
            if "--- 以下为实时" in content:
                sources.add("实时数据接口")
        
        return list(sources)
    
    def _generate_overview(self, turns: List[ConversationTurn], 
                          summary: ConversationSummary) -> str:
        """生成总体概述"""
        parts = []
        
        # 对话轮次信息
        parts.append(f"本段对话共{summary.total_turns}轮")
        if summary.total_user_turns > 0:
            parts.append(f"用户提问{summary.total_user_turns}次")
        
        # 意图概述
        if summary.user_intents:
            parts.append(f"主要意图：{'、'.join(summary.user_intents[:3])}")
        
        # 数据源
        if summary.data_sources_used:
            parts.append(f"使用数据源：{'、'.join(summary.data_sources_used)}")
        
        # 关键实体
        if summary.key_entities:
            top_names = [e.name for e in summary.key_entities[:5]]
            parts.append(f"涉及关键词：{'、'.join(top_names)}")
        
        overview = "；".join(parts) + "。"
        
        # 截断到合理长度
        if len(overview) > self.config.max_summary_length:
            overview = overview[:self.config.max_summary_length - 3] + "..."
        
        return overview
    
    def _extract_key_points(self, turns: List[ConversationTurn]) -> List[str]:
        """提取关键要点"""
        points = []
        
        # 提取用户的核心问题
        for turn in turns:
            if turn.role == "user":
                content = turn.content.strip()
                # 过滤掉数据获取的标记内容
                if content.startswith("用户原始需求："):
                    content = content.replace("用户原始需求：", "").split("\n")[0].strip()
                if len(content) > 5 and len(content) < 150 and not content.startswith("---"):
                    if content not in points:
                        points.append(f"【用户问】{content}")
        
        # 提取助手的关键回复（取每段回复的前两句）
        for turn in turns:
            if turn.role == "assistant":
                content = turn.content.strip()
                sentences = content.split("。")
                for sentence in sentences[:2]:
                    sentence = sentence.strip()
                    if len(sentence) > 10 and len(sentence) < 200:
                        key_point = f"【Agent答】{sentence}"
                        if key_point not in points:
                            points.append(key_point)
                            break  # 每轮只取一个要点
        
        return points[:15]  # 限制要点数量
    
    def _enhance_with_llm(self, summary: ConversationSummary, 
                          turns: List[ConversationTurn]) -> Optional[ConversationSummary]:
        """使用大模型增强摘要质量"""
        if not self.client:
            return None
        
        try:
            # 构建摘要生成提示
            recent_turns = turns[-10:]  # 只取最近10轮，控制token
            conversation_text = "\n".join([
                f"{'用户' if t.role == 'user' else 'Agent'}: {t.content[:200]}"
                for t in recent_turns
            ])
            
            prompt = f"""请对以下对话进行摘要，要求：
1. 保留用户的核心需求和问题
2. 保留Agent的关键回复和结论
3. 提取重要实体（股票、板块、数据等）
4. 识别用户的明确意图
5. 记录任何决策或行动项
6. 去除冗余信息，保持简洁

对话内容：
{conversation_text}

请按以下格式输出：
概述：[一句话总结]
关键要点：
- [要点1]
- [要点2]
...
重要实体：[实体1, 实体2, ...]
用户意图：[意图1, 意图2, ...]
决策/结论：[结论1, 结论2, ...]
"""
            
            response = self.client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=[
                    {"role": "system", "content": "你是一个专业的对话摘要助手。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            enhanced_text = response.choices[0].message.content
            
            # 解析增强后的摘要
            summary.overview = self._parse_section(enhanced_text, "概述") or summary.overview
            summary.key_points = self._parse_list(enhanced_text, "关键要点") or summary.key_points
            
            # 合并实体
            new_entities = self._parse_entities_from_text(enhanced_text)
            if new_entities:
                existing_names = {e.name for e in summary.key_entities}
                for entity in new_entities:
                    if entity.name not in existing_names:
                        summary.key_entities.append(entity)
            
            summary.updated_at = datetime.now().isoformat()
            return summary
            
        except Exception:
            # 大模型增强失败，返回原始摘要
            return None
    
    def _parse_section(self, text: str, section_name: str) -> Optional[str]:
        """从文本中解析特定部分"""
        pattern = rf"{section_name}[:：]\s*(.+?)(?:\n\n|\n[A-Z]|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return None
    
    def _parse_list(self, text: str, section_name: str) -> Optional[List[str]]:
        """从文本中解析列表"""
        section = self._parse_section(text, section_name)
        if not section:
            return None
        
        items = []
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith("-") or line.startswith("•"):
                items.append(line[1:].strip())
            elif line.startswith("【"):
                items.append(line)
        
        return items if items else None
    
    def _parse_entities_from_text(self, text: str) -> List[ExtractedEntity]:
        """从文本中解析实体"""
        entities = []
        section = self._parse_section(text, "重要实体")
        if section:
            for name in section.split(","):
                name = name.strip()
                if name:
                    entities.append(ExtractedEntity(name=name, entity_type="extracted"))
        return entities
    
    def _evaluate_quality(self, summary: ConversationSummary, 
                         turns: List[ConversationTurn]) -> ConversationSummary:
        """评估摘要质量"""
        # 信息完整度：检查关键信息是否被保留
        total_content = " ".join(t.content for t in turns)
        summary_content = summary.overview + " ".join(summary.key_points)
        
        # 计算关键概念覆盖率
        key_concepts = set()
        for entity in summary.key_entities:
            key_concepts.add(entity.name)
        
        # 完整度评分（基于实体覆盖率和内容保留度）
        if len(turns) > 0:
            summary.completeness_score = min(0.95, 
                0.5 + len(summary.key_points) / max(len(turns) / 2, 1) * 0.5)
        else:
            summary.completeness_score = 1.0
        
        # 冗余去除率：确保在0-1范围内
        original_length = len(total_content)
        summary_length = len(summary_content)
        if original_length > 0 and summary_length < original_length:
            summary.redundancy_removal_ratio = min(0.95,
                1.0 - summary_length / original_length)
        else:
            # 如果摘要比原文还长，说明没有去除冗余，设为0
            summary.redundancy_removal_ratio = 0.0
        
        return summary
    
    def _generate_summary_id(self) -> str:
        """生成摘要ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_suffix = hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        return f"SUM-{timestamp}-{random_suffix}"
    
    def _archive_old_history(self):
        """归档旧的历史记录"""
        # 保留最近的部分，其余归档到文件（可选）
        keep_count = self.config.max_full_history_rounds * 2
        self.memory.full_history = self.memory.full_history[-keep_count:]
    
    def get_compressed_context(self, messages: List[Dict[str, str]], 
                               keep_recent: int = 4) -> List[Dict[str, str]]:
        """
        获取压缩后的上下文（用于发送给大模型）。
        
        Args:
            messages: 原始消息列表
            keep_recent: 保留最近几轮完整对话
            
        Returns:
            压缩后的消息列表
        """
        # 分离system prompt
        system_msgs = [m for m in messages if m.get("role") == "system"]
        conversation = [m for m in messages if m.get("role") != "system"]
        
        # 保留最近的几轮
        recent = conversation[-keep_recent:] if len(conversation) > keep_recent else conversation
        
        # 构建压缩上下文
        compressed = system_msgs.copy()
        
        # 如果有摘要，添加摘要作为上下文
        if self.memory.current_summary:
            summary_text = self._format_summary_for_context(self.memory.current_summary)
            compressed.append({
                "role": "system",
                "content": f"[历史对话摘要]\n{summary_text}"
            })
        
        # 添加最近的完整对话
        compressed.extend(recent)
        
        return compressed
    
    def _format_summary_for_context(self, summary: ConversationSummary) -> str:
        """将摘要格式化为上下文字符串"""
        lines = []
        lines.append(summary.overview)
        
        if summary.key_points:
            lines.append("\n关键要点：")
            for point in summary.key_points[:8]:
                lines.append(f"• {point}")
        
        if summary.decisions_made:
            lines.append("\n已做决策：")
            for decision in summary.decisions_made[:5]:
                lines.append(f"• {decision}")
        
        if summary.key_entities:
            lines.append("\n重要实体：")
            entity_names = [e.name for e in summary.key_entities[:8]]
            lines.append(", ".join(entity_names))
        
        return "\n".join(lines)
    
    def get_full_history(self) -> List[ConversationTurn]:
        """获取完整对话历史"""
        return self.memory.full_history.copy()
    
    def get_summary_history(self) -> List[ConversationSummary]:
        """获取摘要历史"""
        return self.memory.summary_history.copy()
    
    def clear(self):
        """清空记忆"""
        with self._lock:
            self.memory = SummarizedMemory()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_turns_processed": self.memory.total_turns_processed,
            "summary_count": self.memory.summary_count,
            "last_summary_turn": self.memory.last_summary_turn,
            "full_history_length": len(self.memory.full_history),
            "summary_history_length": len(self.memory.summary_history),
            "current_summary_quality": {
                "completeness": self.memory.current_summary.completeness_score if self.memory.current_summary else 0,
                "redundancy_removal": self.memory.current_summary.redundancy_removal_ratio if self.memory.current_summary else 0,
            } if self.memory.current_summary else None
        }
