"""
Graph Memory Personalized PageRank 模块
基于种子节点的个性化 PageRank 排序
"""

import numpy as np
from typing import Dict, List, Set, Tuple, Optional


class PersonalizedPageRank:
    """个性化 PageRank 计算器"""
    
    def __init__(self, damping: float = 0.85, iterations: int = 20):
        """
        Args:
            damping: 阻尼系数
            iterations: 迭代次数
        """
        self.damping = damping
        self.iterations = iterations
    
    def compute(
        self,
        node_ids: List[str],
        edges: List[Dict],
        seed_ids: List[str],
        max_iterations: int = None
    ) -> Dict[str, float]:
        """
        计算 Personalized PageRank
        
        Args:
            node_ids: 所有节点 ID
            edges: 所有边列表 [{"from_id": "...", "to_id": "..."}]
            seed_ids: 种子节点 ID（查询匹配的节点）
            max_iterations: 最大迭代次数
        
        Returns:
            {node_id: ppr_score} 按分数降序排列
        """
        if not node_ids or not edges:
            return {}
        
        n = len(node_ids)
        idx = {nid: i for i, nid in enumerate(node_ids)}
        seed_set = set(seed_ids)
        
        # 构建邻接表（无向图）
        adj: Dict[int, Set[int]] = {i: set() for i in range(n)}
        for e in edges:
            if e["from_id"] in idx and e["to_id"] in idx:
                u = idx[e["from_id"]]
                v = idx[e["to_id"]]
                adj[u].add(v)
                adj[v].add(u)
        
        # 初始化 PageRank 向量
        # 种子节点获得更高初始权重
        pr = np.ones(n) / n
        
        # 个性化 teleport：只跳转到种子节点
        iterations = max_iterations or self.iterations
        for _ in range(iterations):
            new_pr = np.zeros(n)
            
            for i in range(n):
                if not adj[i]:  # 孤立节点
                    continue
                
                # 来自邻居的传播
                neighbors = adj[i]
                share = pr[i] / len(neighbors)
                
                for neighbor in neighbors:
                    new_pr[neighbor] += self.damping * share
            
            # 个性化 teleport：回到种子节点
            if seed_set:
                # 均匀分配给种子节点
                teleport_per_seed = (1 - self.damping) / len(seed_set)
                for sid in seed_ids:
                    if sid in idx:
                        new_pr[idx[sid]] += teleport_per_seed
            else:
                new_pr += (1 - self.damping) / n
            
            pr = new_pr
        
        # 构建结果
        scores = {nid: pr[idx[nid]] for nid in node_ids if nid in idx}
        
        # 按分数降序排序
        return dict(sorted(scores.items(), key=lambda x: -x[1]))
    
    def rank_nodes(
        self,
        nodes: List[Dict],
        edges: List[Dict],
        seed_ids: List[str]
    ) -> List[Dict]:
        """
        对节点按 Personalized PageRank 排序
        
        Args:
            nodes: 节点列表
            edges: 边列表
            seed_ids: 种子节点 ID
        
        Returns:
            排序后的节点列表（分数高的在前）
        """
        node_ids = [n["id"] for n in nodes]
        scores = self.compute(node_ids, edges, seed_ids)
        
        # 添加分数到节点
        for node in nodes:
            node["_ppr_score"] = scores.get(node["id"], 0)
        
        # 排序：PPR 分数 > validated_count > pagerank
        return sorted(
            nodes,
            key=lambda n: (
                -n["_ppr_score"],
                -n.get("validated_count", 0),
                -n.get("pagerank", 0)
            )
        )
