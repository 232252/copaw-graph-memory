"""
Graph Memory 社区检测模块
使用简单的标签传播算法
"""

from typing import Dict, Any, List, Set, Tuple
from collections import defaultdict
import random
from .db import GraphDB


class CommunityDetector:
    """社区检测器（使用标签传播算法）"""
    
    def __init__(self, db: GraphDB):
        self.db = db
    
    def detect_communities(self) -> Dict[str, str]:
        """
        检测社区，返回 node_id -> community_id 映射
        
        使用标签传播算法（Label Propagation Algorithm）
        时间复杂度 O(m)，适合大规模图
        """
        # 获取所有活跃节点
        nodes = self.db.get_all_nodes(status="active")
        if not nodes:
            return {}
        
        node_ids = [n["id"] for n in nodes]
        
        # 初始化：每个节点有自己的标签
        labels: Dict[str, str] = {nid: nid for nid in node_ids}
        
        # 构建邻接表
        adj: Dict[str, Set[str]] = {nid: set() for nid in node_ids}
        
        edges = self.db.conn.execute("SELECT from_id, to_id FROM gm_edges").fetchall()
        for edge in edges:
            if edge["from_id"] in adj and edge["to_id"] in adj:
                adj[edge["from_id"]].add(edge["to_id"])
                adj[edge["to_id"]].add(edge["from_id"])
        
        # 标签传播迭代
        max_iterations = 50
        for _ in range(max_iterations):
            changed = False
            nodes_shuffled = node_ids.copy()
            random.shuffle(nodes_shuffled)
            
            for node_id in nodes_shuffled:
                if not adj[node_id]:  # 孤立节点
                    continue
                
                # 统计邻居标签频率
                label_counts: Dict[str, int] = defaultdict(int)
                for neighbor in adj[node_id]:
                    label_counts[labels[neighbor]] += 1
                
                # 选择最频繁的标签
                max_count = max(label_counts.values())
                most_common = [l for l, c in label_counts.items() if c == max_count]
                
                new_label = random.choice(most_common)
                if new_label != labels[node_id]:
                    labels[node_id] = new_label
                    changed = True
            
            if not changed:
                break
        
        # 规范化标签（用最小的节点 ID 作为代表）
        label_to_nodes: Dict[str, List[str]] = defaultdict(list)
        for node_id, label in labels.items():
            label_to_nodes[label].append(node_id)
        
        # 每个社区用最小的节点 ID 作为 community_id
        community_map: Dict[str, str] = {}
        for label, members in label_to_nodes.items():
            rep = min(members)  # 选择最小的作为代表
            for node_id in members:
                community_map[node_id] = rep
        
        return community_map
    
    def update_communities(self) -> int:
        """
        更新所有节点的社区 ID
        
        Returns:
            更新了多少个节点
        """
        community_map = self.detect_communities()
        
        count = 0
        for node_id, community_id in community_map.items():
            self.db.set_community(node_id, community_id)
            count += 1
        
        return count
