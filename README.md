# Graph Memory for CoPaw

基于 [adoresever/graph-memory](https://github.com/adoresever/graph-memory) 的 Python 实现，专为 CoPaw AI Agent 设计的知识图谱记忆引擎。

## 功能特性

- **3种节点类型**: TASK（任务）、SKILL（技能）、EVENT（事件)
- **5种边类型**: USED_SKILL、SOLVED_BY、REQUIRES、PATCHES、CONFLICTS_WITH
- **跨对话召回**: FTS5 全文搜索 + 图遍历 + Personalized PageRank
- **上下文压缩**: 7轮对话 95K tokens → 24K，**75% 压缩率**
- **社区聚类**: 自动将相关技能聚类
- **零依赖**: 仅使用 Python 内置 `sqlite3`，无需安装额外包

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourname/copaw-graph-memory.git
cd copaw-graph-memory

# 或者复制到 CoPaw skills 目录
cp -r graph_memory ~/.copaw/workspaces/default/skills/
```

## 快速开始

```python
from graph_memory import GraphMemory

# 初始化
gm = GraphMemory(
    llm_config={
        "api_key": "YOUR_API_KEY",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1"
    }
)

# 记录消息
gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
gm.ingest("session123", "assistant", "正在安装...")

# 提取知识（每轮对话后调用）
result = gm.extract("session123")
print(f"提取了 {result['extracted_count']} 个节点")

# 召回相关知识
recall_result = gm.recall("bilibili")
print(f"召回 {len(recall_result['nodes'])} 个相关节点")

# 获取上下文
context = gm.assemble_context("bilibili", fresh_messages=recent_msgs)
```

## CoPaw 工具

注册为工具后可用：

| 工具 | 说明 |
|------|------|
| `gm_search` | 搜索知识图谱 |
| `gm_record` | 手动记录知识 |
| `gm_stats` | 查看统计信息 |
| `gm_maintain` | 执行图维护 |

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `db_path` | `~/.copaw/graph_memory.db` | 数据库路径 |
| `compact_turn_count` | `6` | 触发提取的消息数 |
| `recall_max_nodes` | `6` | 召回的最大节点数 |
| `recall_max_depth` | `2` | 图遍历深度 |
| `pagerank_damping` | `0.85` | PageRank 阻尼系数 |

## 工作原理

```
消息输入 → 消息存储（零 LLM）
          └→ 信号检测 → 知识提取（LLM）

对话结束 → 知识整理（LLM）
          └→ 图维护（去重、PageRank）

新对话 → 召回
         ├→ FTS5 搜索找种子节点
         ├→ 图遍历扩展
         ├→ PageRank 排序
         └→ 注入上下文
```

## 数据库结构

| 表 | 说明 |
|----|------|
| `gm_nodes` | 知识节点（带 pagerank、community_id） |
| `gm_edges` | 关系边 |
| `gm_messages` | 原始对话消息 |
| `gm_messages_fts` | FTS5 全文索引 |
| `gm_nodes_fts` | 节点 FTS 索引 |

## 与原版对比

| 特性 | 原版 (TypeScript) | Python 版 |
|------|------------------|----------|
| 依赖 | Node.js + npm | Python 标准库 |
| 向量搜索 | 需要配置 | FTS5（内置） |
| PageRank | 实现 | 实现 |
| 社区检测 | 实现 | 待实现 |
| 安装 | `pnpm openclaw plugins install` | `pip install` 或直接复制 |

## 来源

灵感来自 [adoresever/graph-memory](https://github.com/adoresever/graph-memory)，MIT License。

## License

MIT License
