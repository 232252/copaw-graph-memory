"""
Graph Memory - 知识图谱记忆引擎 for CoPaw
基于 adoresever/graph-memory 的 Python 实现
MIT License
"""

import json
import time
from typing import Dict, Any, List, Optional, Callable, Tuple
from pathlib import Path

from .db import GraphDB
from .extractor import Extractor
from .recaller import Recaller
from .community import CommunityDetector


# 默认配置
DEFAULT_CONFIG = {
    "db_path": "~/.copaw/graph_memory.db",
    "compact_turn_count": 6,
    "recall_max_nodes": 6,
    "recall_max_depth": 2,
    "fresh_tail_count": 10,
    "pagerank_damping": 0.85,
    "pagerank_iterations": 20,
    "llm_config": None,
    "embedding_config": None,
}


class GraphMemory:
    """
    知识图谱记忆引擎
    
    使用方式：
    
    ```python
    from graph_memory import GraphMemory
    
    # 初始化
    gm = GraphMemory(
        llm_config={"api_key": "...", "model": "gpt-4o-mini"}
    )
    
    # 记录消息
    gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
    
    # 提取知识
    gm.extract("session123")
    
    # 召回相关知识
    result = gm.recall("bilibili")
    print(result["nodes"])
    
    # 维护图谱
    gm.maintain()
    ```
    """
    
    def __init__(
        self,
        db_path: str = None,
        llm_config: Dict[str, Any] = None,
        embedding_config: Dict[str, Any] = None,
        llm_fn: Callable[[str, str], str] = None,
        **kwargs
    ):
        """
        初始化知识图谱
        
        Args:
            db_path: 数据库路径
            llm_config: LLM 配置 {"api_key": "...", "model": "...", "base_url": "..."}
            embedding_config: Embedding 配置（可选）
            llm_fn: 自定义 LLM 调用函数，签名为 (system: str, user: str) -> str
            **kwargs: 其他配置参数
        """
        # 合并配置
        self.config = {**DEFAULT_CONFIG, **kwargs}
        
        if db_path:
            self.config["db_path"] = db_path
        if llm_config:
            self.config["llm_config"] = llm_config
        if embedding_config:
            self.config["embedding_config"] = embedding_config
        
        # 初始化数据库
        self.db = GraphDB(self.config["db_path"])
        
        # 初始化 LLM 函数
        if llm_fn:
            self._llm_fn = llm_fn
        elif llm_config:
            self._llm_fn = self._create_llm_fn(llm_config)
        else:
            self._llm_fn = self._default_llm_fn
        
        # 初始化组件
        self.extractor = Extractor(self._llm_fn)
        self.recaller = Recaller(self.db, self.config)
        self.community_detector = CommunityDetector(self.db)
        
        # Session 状态
        self._msg_seq: Dict[str, int] = {}
        self._extract_running: Dict[str, bool] = {}
    
    def _create_llm_fn(self, config: Dict[str, Any]) -> Callable:
        """创建 LLM 调用函数"""
        api_key = config.get("api_key", "")
        model = config.get("model", "gpt-4o-mini")
        base_url = config.get("base_url", "https://api.openai.com/v1")
        
        def llm_fn(system: str, user: str) -> str:
            import requests
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user}
                ],
                "temperature": 0.1
            }
            
            response = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        
        return llm_fn
    
    def _default_llm_fn(self, system: str, user: str) -> str:
        """默认 LLM 函数（返回提示）"""
        return '{"nodes":[],"edges":[]}'
    
    # ─── 消息处理 ────────────────────────────────────────────
    
    def ingest(self, session_id: str, role: str, content: str) -> str:
        """
        记录消息
        
        Args:
            session_id: 会话 ID
            role: 角色 (user/assistant/system)
            content: 消息内容
        
        Returns:
            消息 ID
        """
        seq = self._msg_seq.get(session_id, 0) + 1
        self._msg_seq[session_id] = seq
        
        return self.db.save_message(session_id, seq, role, content)
    
    def extract(self, session_id: str, force: bool = False) -> Dict[str, Any]:
        """
        从当前会话提取知识
        
        Args:
            session_id: 会话 ID
            force: 是否强制提取（忽略检查）
        
        Returns:
            提取结果 {"nodes": [...], "edges": [...], "extracted_count": int}
        """
        if self._extract_running.get(session_id) and not force:
            return {"nodes": [], "edges": [], "error": "extraction in progress"}
        
        self._extract_running[session_id] = True
        
        try:
            # 获取未提取的消息
            messages = self.db.get_unextracted_messages(session_id, limit=50)
            
            if not messages:
                return {"nodes": [], "edges": []}
            
            # 检查是否达到提取阈值
            if len(messages) < self.config["compact_turn_count"] and not force:
                return {
                    "nodes": [], 
                    "edges": [], 
                    "pending": len(messages),
                    "message": f"还需要 {self.config['compact_turn_count'] - len(messages)} 条消息触发提取"
                }
            
            # 获取已存在的节点名称
            existing_nodes = self.db.get_all_nodes()
            existing_names = [n["name"] for n in existing_nodes]
            
            # 调用提取器
            result = self.extractor.extract(messages, existing_names)
            
            if not result.get("nodes") and not result.get("edges"):
                # 无提取结果
                max_turn = max(m["turn_index"] for m in messages)
                self.db.mark_messages_extracted(session_id, max_turn)
                return {"nodes": [], "edges": [], "extracted_count": 0}
            
            # 保存节点和边
            name_to_id = {}
            for node_data in result.get("nodes", []):
                node = self.db.upsert_node(
                    node_type=node_data["type"],
                    name=node_data["name"],
                    description=node_data["description"],
                    content=node_data["content"],
                    session_id=session_id
                )
                name_to_id[node_data["name"]] = node["id"]
            
            for edge_data in result.get("edges", []):
                from_id = name_to_id.get(edge_data["from"])
                to_id = name_to_id.get(edge_data["to"])
                
                if from_id and to_id:
                    self.db.upsert_edge(
                        from_id=from_id,
                        to_id=to_id,
                        edge_type=edge_data["type"],
                        instruction=edge_data.get("instruction", ""),
                        condition=edge_data.get("condition"),
                        session_id=session_id
                    )
            
            # 标记消息已提取
            max_turn = max(m["turn_index"] for m in messages)
            self.db.mark_messages_extracted(session_id, max_turn)
            
            return {
                "nodes": result.get("nodes", []),
                "edges": result.get("edges", []),
                "extracted_count": len(result.get("nodes", []))
            }
        
        except Exception as e:
            return {"nodes": [], "edges": [], "error": str(e)}
        
        finally:
            self._extract_running[session_id] = False
    
    # ─── 召回 ────────────────────────────────────────────────
    
    def recall(self, query: str) -> Dict[str, Any]:
        """
        召回相关知识
        
        Args:
            query: 查询文本
        
        Returns:
            召回结果 {"nodes": [...], "edges": [...], "token_estimate": int}
        """
        return self.recaller.recall(query)
    
    def assemble_context(self, query_or_result: str = None, fresh_messages: List[Dict] = None) -> str:
        """
        组装上下文
        
        Args:
            query_or_result: 查询文本或 recall 结果
            fresh_messages: 最新消息（保留原始形式）
        
        Returns:
            格式化的上下文文本
        """
        if isinstance(query_or_result, dict):
            result = query_or_result
        else:
            query = query_or_result or ""
            result = self.recall(query) if query else {"nodes": [], "edges": []}
        
        return self.recaller.assemble_context(result, fresh_messages)
    
    # ─── 维护 ────────────────────────────────────────────────
    
    def maintain(self) -> Dict[str, Any]:
        """
        执行图维护：去重、更新 PageRank、更新社区
        
        Returns:
            维护结果
        """
        results = {}
        
        # 更新 PageRank
        try:
            self.db.update_pageranks(
                damping=self.config["pagerank_damping"],
                iterations=self.config["pagerank_iterations"]
            )
            results["pagerank"] = "ok"
        except Exception as e:
            results["pagerank"] = f"error: {e}"
        
        # 更新社区
        try:
            count = self.community_detector.update_communities()
            results["communities"] = count
        except Exception as e:
            results["communities"] = f"error: {e}"
        
        stats = self.get_stats()
        return {"status": "ok", "results": results, "stats": stats}
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.db.get_stats()
    
    # ─── 节点/边查询 ────────────────────────────────────────
    
    def get_node(self, node_id: str = None, name: str = None) -> Optional[Dict[str, Any]]:
        """获取节点"""
        if node_id:
            return self.db.get_node(node_id)
        elif name:
            return self.db.get_node_by_name(name)
        return None
    
    def get_related_nodes(self, node_id: str) -> Dict[str, Any]:
        """获取相关节点（入边和出边）"""
        outgoing, incoming = self.db.get_node_edges(node_id)
        
        # 获取节点详情
        related = []
        for edge in outgoing:
            target = self.db.get_node(edge["to_id"])
            if target:
                related.append({"node": target, "edge": edge, "direction": "out"})
        
        for edge in incoming:
            source = self.db.get_node(edge["from_id"])
            if source:
                related.append({"node": source, "edge": edge, "direction": "in"})
        
        return {"related": related}
    
    # ─── 工具导出 ────────────────────────────────────────────
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        获取 CoPaw 工具定义
        
        Returns:
            工具定义列表
        """
        return [
            {
                "name": "gm_search",
                "description": "搜索知识图谱，查找相关的任务、技能和解决方案。使用自然语言查询，如 '安装 bilibili' 或 'docker 部署'",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "搜索查询"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "gm_record",
                "description": "手动记录知识到图谱。用于保存重要的操作经验、解决方案等",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["TASK", "SKILL", "EVENT"],
                            "description": "节点类型：TASK=任务, SKILL=技能, EVENT=事件"
                        },
                        "name": {
                            "type": "string",
                            "description": "节点名称（英文小写连字符，如 install-docker）"
                        },
                        "description": {
                            "type": "string",
                            "description": "简短描述（一句话说明什么场景）"
                        },
                        "content": {
                            "type": "string",
                            "description": "详细内容"
                        },
                        "session_id": {
                            "type": "string",
                            "description": "会话 ID（可选）"
                        }
                    },
                    "required": ["type", "name", "description", "content"]
                }
            },
            {
                "name": "gm_stats",
                "description": "查看知识图谱统计信息：节点数、边数、消息数、各类型分布、Top 节点等",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "gm_maintain",
                "description": "执行图维护：更新 PageRank 分数、检测社区聚类。推荐定期执行",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            }
        ]
    
    def call_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            tool_input: 工具输入参数
        
        Returns:
            工具执行结果
        """
        if tool_name == "gm_search":
            result = self.recall(tool_input["query"])
            return {
                "content": self.recaller.assemble_context(result),
                "nodes": result["nodes"],
                "edges": result["edges"],
                "token_estimate": result["token_estimate"]
            }
        
        elif tool_name == "gm_record":
            node = self.db.upsert_node(
                node_type=tool_input["type"],
                name=tool_input["name"],
                description=tool_input["description"],
                content=tool_input["content"],
                session_id=tool_input.get("session_id", "manual")
            )
            return {"status": "ok", "node_id": node["id"]}
        
        elif tool_name == "gm_stats":
            return self.get_stats()
        
        elif tool_name == "gm_maintain":
            return self.maintain()
        
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
    
    def close(self):
        """关闭连接"""
        self.db.close()


# 便捷函数
def create_graph_memory(**kwargs) -> GraphMemory:
    """创建 GraphMemory 实例"""
    return GraphMemory(**kwargs)


# CLI 入口点
if __name__ == "__main__":
    from .cli import main
    main()
