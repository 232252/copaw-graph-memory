---
name: graph-memory
description: "知识图谱记忆引擎 - 从对话中提取结构化知识，支持跨对话召回。灵感来自 adoresever/graph-memory，MIT License。使用场景：(1) AI 助手需要记住之前的操作经验，(2) 避免重复犯错，(3) 压缩上下文提升效率。"
metadata:
  {
    "openclaw":
      {
        "emoji": "🧠",
        "requires": { "bins": [] },
        "install":
          [
            {
              "id": "python",
              "kind": "python",
              "package": "numpy",
              "bins": [],
              "label": "NumPy (for PageRank, auto-installed if missing)",
            },
          ],
      },
  }
---

# 🧠 Graph Memory - 知识图谱记忆引擎

基于 [adoresever/graph-memory](https://github.com/adoresever/graph-memory) 的 Python 实现，专为 CoPaw AI Agent 设计的知识图谱记忆引擎。

## 核心功能

- **3种节点类型**: TASK（任务）、SKILL（技能）、EVENT（事件）
- **5种边类型**: USED_SKILL、SOLVED_BY、REQUIRES、PATCHES、CONFLICTS_WITH
- **跨对话召回**: FTS5 全文搜索 + 图遍历 + Personalized PageRank
- **上下文压缩**: 7轮对话 95K tokens → 24K，**75% 压缩率**
- **零依赖**: 仅使用 Python 内置 `sqlite3`，NumPy 可选（用于 PageRank）

## 快速开始

### 初始化配置

```python
from graph_memory import GraphMemory

# 使用 MiniMax API（CoPaw 当前配置）
gm = GraphMemory(
    llm_config={
        "api_key": "sk-cp-XOHAixI-9cgve5KMm-l-bms1DYFHk0r5PdXhccohpNGpHPigfJIQCE_vFXNn6loeJieW2OE0kNfhw9Li5ta9XOBwybXKRpQSpbr6-f6khFCFiN4gR3kSR_Y",
        "base_url": "https://api.minimaxi.com/v1",
        "model": "MiniMax-M2.7"
    }
)
```

### 基本使用

```python
# 记录消息
gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
gm.ingest("session123", "assistant", "正在安装...")

# 提取知识（对话结束后或积累足够消息后）
result = gm.extract("session123")
print(f"提取了 {result.get('extracted_count', 0)} 个节点")

# 召回相关知识
context = gm.assemble_context("bilibili")
print(context)

# 查看统计
stats = gm.get_stats()
print(f"节点: {stats['nodes']}, 边: {stats['edges']}")

# 执行维护（定期运行）
gm.maintain()
```

### CLI 工具

```bash
# 统计
python -m graph_memory.cli stats

# 搜索
python -m graph_memory.cli search "docker"

# 维护
python -m graph_memory.cli maintain

# 查看帮助
python -m graph_memory.cli --help
```

## API 配置

### 使用 MiniMax（推荐，CoPaw 当前配置）

```python
gm = GraphMemory(
    llm_config={
        "api_key": "sk-cp-XOHAixI-9cgve5KMm-l-bms1DYFHk0r5PdXhccohpNGpHPigfJIQCE_vFXNn6loeJieW2OE0kNfhw9Li5ta9XOBwybXKRpQSpbr6-f6khFCFiN4gR3kSR_Y",
        "base_url": "https://api.minimaxi.com/v1",
        "model": "MiniMax-M2.7"
    }
)
```

### 使用 OpenAI 兼容 API

```python
gm = GraphMemory(
    llm_config={
        "api_key": "your-api-key",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini"
    }
)
```

## 工具列表

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

## 数据库结构

| 表 | 说明 |
|----|------|
| `gm_nodes` | 知识节点（带 pagerank、community_id） |
| `gm_edges` | 关系边 |
| `gm_messages` | 原始对话消息 |
| `gm_messages_fts` | FTS5 全文索引 |

## 开源项目

**GitHub**: https://github.com/232252/copaw-graph-memory

**上游**: https://github.com/adoresever/graph-memory
