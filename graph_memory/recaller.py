"""
Graph Memory 召回模块
跨对话知识召回
支持：
1. FTS5 全文搜索找种子节点
2. 图遍历扩展
3. Personalized PageRank 排序
4. 按轮次切分 + 图谱全量注入
"""

from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from .db import GraphDB
from .pprank import PersonalizedPageRank


# 节点类型优先级
TYPE_PRIORITY = {"SKILL": 3, "TASK": 2, "EVENT": 1}
CHARS_PER_TOKEN = 3


class Recaller:
    """知识召回器"""
    
    def __init__(self, db: GraphDB, config: Dict[str, Any]):
        """
        初始化召回器
        
        Args:
            db: GraphDB 实例
            config: 配置
        """
        self.db = db
        self.max_nodes = config.get("recall_max_nodes", 6)
        self.max_depth = config.get("recall_max_depth", 2)
        self.token_budget = config.get("token_budget", 4000)
        self.ppr = PersonalizedPageRank(
            damping=config.get("pagerank_damping", 0.85),
            iterations=config.get("pagerank_iterations", 20)
        )
    
    def recall(self, query: str, include_all: bool = False) -> Dict[str, Any]:
        """
        召回与查询相关的知识
        
        Args:
            query: 查询文本
            include_all: 是否返回所有节点（不限制数量）
        
        Returns:
            {"nodes": [...], "edges": [...], "token_estimate": int, "communities": {...}}
        """
        # 1. FTS5 搜索找种子节点
        seed_nodes = self.db.search_nodes(query, limit=20)
        
        if not seed_nodes:
            # 没有匹配结果，返回空
            return {"nodes": [], "edges": [], "token_estimate": 0, "communities": {}}
        
        seed_ids = [n["id"] for n in seed_nodes]
        
        # 2. 图遍历扩展
        nodes, edges = self.db.graph_walk(seed_ids, self.max_depth)
        
        if not nodes:
            return {"nodes": [], "edges": [], "token_estimate": 0, "communities": {}}
        
        # 3. 使用 Personalized PageRank 排序
        nodes = self.ppr.rank_nodes(nodes, edges, seed_ids)
        
        # 4. 限制数量
        if not include_all:
            nodes = nodes[:self.max_nodes]
        
        selected_ids = {n["id"] for n in nodes}
        
        # 5. 过滤边
        filtered_edges = [
            e for e in edges 
            if e["from_id"] in selected_ids and e["to_id"] in selected_ids
        ]
        
        # 6. 按社区分组
        communities = self._group_by_community(nodes)
        
        # 7. 估计 token
        token_estimate = self._estimate_tokens(nodes, filtered_edges)
        
        return {
            "nodes": nodes,
            "edges": filtered_edges,
            "token_estimate": token_estimate,
            "communities": communities
        }
    
    def _sort_nodes(self, nodes: List[Dict], seed_ids: List[str]) -> List[Dict]:
        """排序节点"""
        seed_set = set(seed_ids)
        
        return sorted(nodes, key=lambda n: (
            # 优先本 session 的（这里简化处理）
            0,
            # 类型优先级
            -(TYPE_PRIORITY.get(n["type"], 0)),
            # 验证次数
            -n.get("validated_count", 0),
            # 全局 PageRank
            -n.get("pagerank", 0)
        ))
    
    def _group_by_community(self, nodes: List[Dict]) -> Dict[str, List[Dict]]:
        """按社区分组"""
        communities = defaultdict(list)
        no_community = []
        
        for node in nodes:
            cid = node.get("community_id")
            if cid:
                communities[cid].append(node)
            else:
                no_community.append(node)
        
        result = dict(communities)
        if no_community:
            result["_no_community"] = no_community
        
        return result
    
    def _estimate_tokens(self, nodes: List[Dict], edges: List[Dict]) -> int:
        """粗略估计 token 数量"""
        total_chars = 0
        
        for node in nodes:
            total_chars += len(node.get("name", ""))
            total_chars += len(node.get("description", ""))
            total_chars += len(node.get("content", ""))
        
        for edge in edges:
            total_chars += len(edge.get("type", ""))
            total_chars += len(edge.get("instruction", ""))
            if edge.get("condition"):
                total_chars += len(edge["condition"])
        
        return total_chars // CHARS_PER_TOKEN
    
    def assemble_context(
        self, 
        recall_result: Dict[str, Any], 
        fresh_messages: List[Dict[str, Any]] = None,
        token_budget: int = None
    ) -> str:
        """
        组装上下文文本
        
        Args:
            recall_result: recall() 返回的结果
            fresh_messages: 最新消息（原始形式保留）
            token_budget: token 预算
        
        Returns:
            格式化的上下文字符串
        """
        budget = token_budget or self.token_budget
        lines = []
        
        nodes = recall_result.get("nodes", [])
        edges = recall_result.get("edges", [])
        communities = recall_result.get("communities", {})
        
        # 生成 header
        skill_count = sum(1 for n in nodes if n["type"] == "SKILL")
        event_count = sum(1 for n in nodes if n["type"] == "EVENT")
        task_count = sum(1 for n in nodes if n["type"] == "TASK")
        
        lines.append("")
        lines.append("## Graph Memory — 知识图谱记忆")
        lines.append("")
        lines.append("以下是来自过去对话积累的结构化知识：")
        lines.append("")
        lines.append(f"当前图谱: {skill_count} 个技能, {event_count} 个事件, {task_count} 个任务, {len(edges)} 个关系")
        lines.append("")
        
        # 图导航提示
        if len(nodes) >= 3:
            lines.append("**知识图谱导航：**")
            lines.append("- `SOLVED_BY`: 某个事件被技能解决了 — 遇到类似错误时应用该技能")
            lines.append("- `USED_SKILL`: 某个任务使用了技能 — 复用相同方法处理类似任务")
            lines.append("- `PATCHES`: 新技能修正了旧技能 — 优先使用新版本")
            lines.append("- `CONFLICTS_WITH`: 两个技能互斥 — 选择前检查条件")
            lines.append("")
        
        # 节点内容
        lines.append("<knowledge_graph>")
        
        if not nodes:
            lines.append("（无相关记忆）")
        else:
            # 按社区分组输出
            for cid, members in communities.items():
                if cid == "_no_community":
                    for node in members:
                        lines.extend(self._format_node(node, edges, nodes))
                else:
                    lines.append(f"  <社区 id=\"{cid[:8]}...\">")
                    for node in members:
                        lines.extend(self._format_node(node, edges, nodes, indent=4))
                    lines.append("  </社区>")
        
        lines.append("</knowledge_graph>")
        
        # 保留最新消息
        if fresh_messages:
            lines.append("")
            lines.append("**最近对话：**")
            for msg in fresh_messages[-5:]:  # 最多5条
                role = msg.get("role", "?")
                content = msg.get("content", "")
                if role in ("user", "assistant") and content:
                    # 截断过长的消息
                    if len(content) > 200:
                        content = content[:200] + "..."
                    lines.append(f"- [{role.upper()}] {content}")
        
        return "\n".join(lines)
    
    def _format_node(self, node: Dict, edges: List[Dict], all_nodes: List[Dict], indent: int = 2) -> List[str]:
        """格式化单个节点"""
        prefix = " " * indent
        tag = node["type"].lower()
        
        lines = []
        lines.append(f"{prefix}<{tag} name=\"{node['name']}\" desc=\"{node['description']}\">")
        
        # 添加边信息
        node_edges = [e for e in edges if e["from_id"] == node["id"] or e["to_id"] == node["id"]]
        if node_edges:
            for edge in node_edges[:3]:  # 最多3条边
                if edge["from_id"] == node["id"]:
                    target = next((n for n in all_nodes if n["id"] == edge["to_id"]), None)
                    if target:
                        lines.append(f"{prefix}  <{edge['type']}>{target['name']}</{edge['type']}>")
        
        # 添加内容
        content = node.get("content", "")
        for line in content.split("\n"):
            lines.append(f"{prefix}  {line}")
        
        lines.append(f"{prefix}</{tag}>")
        
        return lines
    
    def build_system_prompt_addition(self, recall_result: Dict[str, Any]) -> str:
        """
        构建 system prompt 引导文字
        
        Args:
            recall_result: recall() 返回的结果
        
        Returns:
            system prompt 文本
        """
        nodes = recall_result.get("nodes", [])
        edges = recall_result.get("edges", [])
        
        if not nodes:
            return ""
        
        skill_count = sum(1 for n in nodes if n["type"] == "SKILL")
        event_count = sum(1 for n in nodes if n["type"] == "EVENT")
        task_count = sum(1 for n in nodes if n["type"] == "TASK")
        
        sections = [
            "## Graph Memory — 知识图谱记忆",
            "",
            "Below is your accumulated experience from past conversations.",
            f"Current graph: {skill_count} skills, {event_count} events, {task_count} tasks, {len(edges)} relationships.",
            "",
            "**Recall priority:**",
            "1. Check knowledge_graph below FIRST for matching SKILL/EVENT nodes",
            "2. Use gm_search tool to find related nodes",
            "3. Use gm_record tool to save new discoveries",
            "4. The graph is your primary memory, not MEMORY.md",
        ]
        
        return "\n".join(sections)
