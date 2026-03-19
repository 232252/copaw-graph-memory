"""
Graph Memory 数据库模块
SQLite + FTS5 实现
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager


class GraphDB:
    """知识图谱数据库"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()
    
    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode = WAL")
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn
    
    @contextmanager
    def transaction(self):
        """事务上下文管理器"""
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
    
    def _init_db(self):
        """初始化数据库表"""
        c = self.conn.cursor()
        
        # 节点表
        c.execute("""
            CREATE TABLE IF NOT EXISTS gm_nodes (
                id              TEXT PRIMARY KEY,
                type            TEXT NOT NULL CHECK(type IN ('TASK','SKILL','EVENT')),
                name            TEXT NOT NULL UNIQUE,
                description     TEXT NOT NULL DEFAULT '',
                content         TEXT NOT NULL,
                status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active','deprecated')),
                validated_count INTEGER NOT NULL DEFAULT 1,
                source_sessions TEXT NOT NULL DEFAULT '[]',
                community_id    TEXT,
                pagerank        REAL NOT NULL DEFAULT 0,
                created_at      INTEGER NOT NULL,
                updated_at      INTEGER NOT NULL
            )
        """)
        
        # 边表
        c.execute("""
            CREATE TABLE IF NOT EXISTS gm_edges (
                id          TEXT PRIMARY KEY,
                from_id     TEXT NOT NULL REFERENCES gm_nodes(id),
                to_id       TEXT NOT NULL REFERENCES gm_nodes(id),
                type        TEXT NOT NULL CHECK(type IN ('USED_SKILL','SOLVED_BY','REQUIRES','PATCHES','CONFLICTS_WITH')),
                instruction TEXT NOT NULL,
                condition   TEXT,
                session_id  TEXT NOT NULL,
                created_at  INTEGER NOT NULL
            )
        """)
        
        # 消息表
        c.execute("""
            CREATE TABLE IF NOT EXISTS gm_messages (
                id          TEXT PRIMARY KEY,
                session_id  TEXT NOT NULL,
                turn_index  INTEGER NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                extracted   INTEGER NOT NULL DEFAULT 0,
                created_at  INTEGER NOT NULL
            )
        """)
        
        # FTS5 全文索引
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS gm_messages_fts USING fts5(
                content,
                session_id UNINDEXED,
                turn_index UNINDEXED,
                role UNINDEXED,
                content='gm_messages',
                content_rowid='rowid'
            )
        """)
        
        # 节点 FTS
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS gm_nodes_fts USING fts5(
                name,
                description,
                content,
                content='gm_nodes',
                content_rowid='rowid'
            )
        """)
        
        # 索引
        c.execute("CREATE INDEX IF NOT EXISTS ix_gm_msg_session ON gm_messages(session_id, turn_index)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gm_msg_extracted ON gm_messages(session_id, extracted)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gm_edges_from ON gm_edges(from_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gm_edges_to ON gm_edges(to_id)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gm_nodes_type ON gm_nodes(type)")
        c.execute("CREATE INDEX IF NOT EXISTS ix_gm_nodes_community ON gm_nodes(community_id)")
        
        self.conn.commit()
    
    # ─── 节点操作 ───────────────────────────────────────────
    
    def upsert_node(self, node_type: str, name: str, description: str, 
                    content: str, session_id: str) -> Dict[str, Any]:
        """插入或更新节点"""
        now = int(datetime.now().timestamp() * 1000)
        
        existing = self.get_node_by_name(name)
        if existing:
            # 更新
            sessions = json.loads(existing["source_sessions"])
            if session_id not in sessions:
                sessions.append(session_id)
            
            self.conn.execute("""
                UPDATE gm_nodes SET
                    description = ?,
                    content = ?,
                    validated_count = validated_count + 1,
                    source_sessions = ?,
                    updated_at = ?
                WHERE name = ?
            """, (description, content, json.dumps(sessions), now, name))
            
            # 更新 FTS
            self.conn.execute("DELETE FROM gm_nodes_fts WHERE rowid=?", (existing["rowid"],))
            
            node_id = existing["id"]
        else:
            # 新建
            node_id = str(uuid.uuid4())
            self.conn.execute("""
                INSERT INTO gm_nodes (id, type, name, description, content, source_sessions, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (node_id, node_type, name, description, content, json.dumps([session_id]), now, now))
        
        # 重建 FTS
        self.conn.execute("""
            INSERT INTO gm_nodes_fts(rowid, name, description, content)
            SELECT rowid, name, description, content FROM gm_nodes WHERE id = ?
        """, (node_id,))
        
        self.conn.commit()
        
        return self.get_node(node_id)
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """获取节点"""
        row = self.conn.execute("SELECT * FROM gm_nodes WHERE id = ?", (node_id,)).fetchone()
        return dict(row) if row else None
    
    def get_node_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """按名称获取节点"""
        row = self.conn.execute("SELECT rowid, * FROM gm_nodes WHERE name = ?", (name,)).fetchone()
        return dict(row) if row else None
    
    def get_all_nodes(self, status: str = "active") -> List[Dict[str, Any]]:
        """获取所有节点"""
        rows = self.conn.execute(
            "SELECT * FROM gm_nodes WHERE status = ?", (status,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    # ─── 边操作 ─────────────────────────────────────────────
    
    def upsert_edge(self, from_id: str, to_id: str, edge_type: str,
                    instruction: str, condition: Optional[str] = None,
                    session_id: Optional[str] = None) -> Dict[str, Any]:
        """插入或更新边"""
        now = int(datetime.now().timestamp() * 1000)
        
        # 检查是否已存在
        existing = self.conn.execute("""
            SELECT id FROM gm_edges WHERE from_id = ? AND to_id = ? AND type = ?
        """, (from_id, to_id, edge_type)).fetchone()
        
        if existing:
            self.conn.execute("""
                UPDATE gm_edges SET instruction = ?, condition = ? WHERE id = ?
            """, (instruction, condition, existing["id"]))
            edge_id = existing["id"]
        else:
            edge_id = str(uuid.uuid4())
            self.conn.execute("""
                INSERT INTO gm_edges (id, from_id, to_id, type, instruction, condition, session_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (edge_id, from_id, to_id, edge_type, instruction, condition, session_id or "", now))
        
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM gm_edges WHERE id = ?", (edge_id,)).fetchone())
    
    def get_edges_between(self, from_id: str, to_id: str) -> List[Dict[str, Any]]:
        """获取两个节点之间的所有边"""
        rows = self.conn.execute("""
            SELECT * FROM gm_edges WHERE from_id = ? AND to_id = ?
        """, (from_id, to_id)).fetchall()
        return [dict(r) for r in rows]
    
    def get_node_edges(self, node_id: str) -> Tuple[List[Dict], List[Dict]]:
        """获取节点的所有边（入边和出边）"""
        outgoing = self.conn.execute(
            "SELECT * FROM gm_edges WHERE from_id = ?", (node_id,)
        ).fetchall()
        incoming = self.conn.execute(
            "SELECT * FROM gm_edges WHERE to_id = ?", (node_id,)
        ).fetchall()
        return [dict(r) for r in outgoing], [dict(r) for r in incoming]
    
    # ─── 消息操作 ────────────────────────────────────────────
    
    def save_message(self, session_id: str, turn_index: int, role: str, content: str) -> str:
        """保存消息"""
        msg_id = str(uuid.uuid4())
        now = int(datetime.now().timestamp() * 1000)
        
        cursor = self.conn.execute("""
            INSERT INTO gm_messages (id, session_id, turn_index, role, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (msg_id, session_id, turn_index, role, content, now))
        rowid = cursor.lastrowid
        
        # 更新 FTS
        self.conn.execute("""
            INSERT INTO gm_messages_fts(rowid, content, session_id, turn_index, role)
            VALUES (?, ?, ?, ?, ?)
        """, (rowid, content, session_id, turn_index, role))
        
        self.conn.commit()
        return msg_id
    
    def get_unextracted_messages(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """获取未提取的消息"""
        rows = self.conn.execute("""
            SELECT * FROM gm_messages 
            WHERE session_id = ? AND extracted = 0
            ORDER BY turn_index ASC
            LIMIT ?
        """, (session_id, limit)).fetchall()
        return [dict(r) for r in rows]
    
    def mark_messages_extracted(self, session_id: str, max_turn_index: int):
        """标记消息已提取"""
        self.conn.execute("""
            UPDATE gm_messages SET extracted = 1
            WHERE session_id = ? AND turn_index <= ?
        """, (session_id, max_turn_index))
        self.conn.commit()
    
    # ─── 搜索 ────────────────────────────────────────────────
    
    def search_nodes(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """FTS5 全文搜索节点"""
        rows = self.conn.execute("""
            SELECT gm_nodes.*, bm25(gm_nodes_fts) as rank
            FROM gm_nodes_fts
            JOIN gm_nodes ON gm_nodes.rowid = gm_nodes_fts.rowid
            WHERE gm_nodes_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit)).fetchall()
        return [dict(r) for r in rows]
    
    def search_messages(self, query: str, session_id: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """FTS5 全文搜索消息"""
        if session_id:
            rows = self.conn.execute("""
                SELECT gm_messages.*, bm25(gm_messages_fts) as rank
                FROM gm_messages_fts
                JOIN gm_messages ON gm_messages.rowid = gm_messages_fts.rowid
                WHERE gm_messages_fts MATCH ? AND gm_messages.session_id = ?
                ORDER BY rank
                LIMIT ?
            """, (query, session_id, limit)).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT gm_messages.*, bm25(gm_messages_fts) as rank
                FROM gm_messages_fts
                JOIN gm_messages ON gm_messages.rowid = gm_messages_fts.rowid
                WHERE gm_messages_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (query, limit)).fetchall()
        return [dict(r) for r in rows]
    
    # ─── 图遍历 ──────────────────────────────────────────────
    
    def graph_walk(self, seed_ids: List[str], max_depth: int = 2) -> Tuple[List[Dict], List[Dict]]:
        """从种子节点出发遍历图"""
        visited = set(seed_ids)
        queue = list(seed_ids)
        nodes_dict = {}
        edges_dict = {}
        
        # 获取种子节点
        for row in self.conn.execute("SELECT * FROM gm_nodes WHERE id IN (" + ",".join("?" * len(seed_ids)) + ")", seed_ids):
            node = dict(row)
            nodes_dict[node["id"]] = node
        
        for _ in range(max_depth):
            new_queue = []
            for node_id in queue:
                # 获取相邻边
                out_edges = self.conn.execute("SELECT * FROM gm_edges WHERE from_id = ?", (node_id,)).fetchall()
                in_edges = self.conn.execute("SELECT * FROM gm_edges WHERE to_id = ?", (node_id,)).fetchall()
                
                for edge in list(out_edges) + list(in_edges):
                    edge_dict = dict(edge)
                    edges_dict[edge_dict["id"]] = edge_dict
                    
                    next_id = edge_dict["to_id"] if edge_dict["from_id"] == node_id else edge_dict["from_id"]
                    if next_id not in visited:
                        visited.add(next_id)
                        new_queue.append(next_id)
                        row = self.conn.execute("SELECT * FROM gm_nodes WHERE id = ?", (next_id,)).fetchone()
                        if row:
                            nodes_dict[next_id] = dict(row)
            
            queue = new_queue
            if not queue:
                break
        
        return list(nodes_dict.values()), list(edges_dict.values())
    
    # ─── PageRank ────────────────────────────────────────────
    
    def update_pageranks(self, damping: float = 0.85, iterations: int = 20):
        """更新所有节点的 PageRank"""
        import numpy as np
        
        # 构建邻接表
        nodes = {r["id"]: r for r in self.conn.execute("SELECT * FROM gm_nodes WHERE status='active'").fetchall()}
        node_ids = list(nodes.keys())
        n = len(node_ids)
        
        if n == 0:
            return
        
        idx = {nid: i for i, nid in enumerate(node_ids)}
        
        # 构建转移矩阵
        M = np.zeros((n, n))
        out_degree = {nid: 0 for nid in node_ids}
        
        for row in self.conn.execute("SELECT from_id, to_id FROM gm_edges").fetchall():
            if row["from_id"] in idx and row["to_id"] in idx:
                M[idx[row["to_id"]], idx[row["from_id"]]] = 1
                out_degree[row["from_id"]] += 1
        
        # 归一化
        for i, nid in enumerate(node_ids):
            if out_degree[nid] > 0:
                M[:, i] /= out_degree[nid]
        
        # PageRank 迭代
        pr = np.ones(n) / n
        for _ in range(iterations):
            pr = (1 - damping) / n + damping * M @ pr
        
        # 更新数据库
        for i, nid in enumerate(node_ids):
            self.conn.execute("UPDATE gm_nodes SET pagerank = ? WHERE id = ?", (pr[i], nid))
        
        self.conn.commit()
    
    def set_community(self, node_id: str, community_id: str):
        """设置节点社区"""
        self.conn.execute("UPDATE gm_nodes SET community_id = ? WHERE id = ?", (community_id, node_id))
        self.conn.commit()
    
    def get_nodes_by_community(self, community_id: str) -> List[Dict[str, Any]]:
        """获取社区内所有节点"""
        rows = self.conn.execute(
            "SELECT * FROM gm_nodes WHERE community_id = ?", (community_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    # ─── 统计 ────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        c = self.conn.cursor()
        
        node_count = c.execute("SELECT COUNT(*) FROM gm_nodes WHERE status='active'").fetchone()[0]
        edge_count = c.execute("SELECT COUNT(*) FROM gm_edges").fetchone()[0]
        msg_count = c.execute("SELECT COUNT(*) FROM gm_messages").fetchone()[0]
        
        type_counts = {}
        for row in c.execute("SELECT type, COUNT(*) as cnt FROM gm_nodes WHERE status='active' GROUP BY type"):
            type_counts[row["type"]] = row["cnt"]
        
        top_nodes = c.execute("""
            SELECT name, type, pagerank, validated_count 
            FROM gm_nodes WHERE status='active'
            ORDER BY pagerank DESC LIMIT 10
        """).fetchall()
        
        communities = c.execute("SELECT COUNT(DISTINCT community_id) FROM gm_nodes WHERE community_id IS NOT NULL").fetchone()[0]
        
        return {
            "nodes": node_count,
            "edges": edge_count,
            "messages": msg_count,
            "type_counts": type_counts,
            "communities": communities,
            "top_nodes": [dict(r) for r in top_nodes]
        }
    
    def close(self):
        """关闭连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
