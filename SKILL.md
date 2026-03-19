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

## 安装

```bash
git clone https://github.com/232252/copaw-graph-memory.git
cd copaw-graph-memory
pip install numpy  # 可选
```

## 快速开始

### 1. 配置 API

**方式一：环境变量（推荐）**
```bash
export GM_LLM_API_KEY="your-api-key"
export GM_LLM_BASE_URL="http://192.168.110.125:3000/v1"
export GM_LLM_MODEL="MiniMax-Text-01"
```

**方式二：代码配置**
```python
from graph_memory import GraphMemory

gm = GraphMemory(
    llm_config={
        "api_key": "YOUR_API_KEY_HERE",  # 替换为你的 API key
        "base_url": "http://192.168.110.125:3000/v1",
        "model": "MiniMax-Text-01"
    }
)
```

### 2. 基本使用

```python
# 记录消息
gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
gm.ingest("session123", "assistant", "正在安装...")

# 提取知识
result = gm.extract("session123")
print(f"提取了 {result.get('extracted_count', 0)} 个节点")

# 召回相关知识
context = gm.assemble_context("bilibili")
print(context)

# 查看统计
stats = gm.get_stats()
print(f"节点: {stats['nodes']}, 边: {stats['edges']}")

# 执行维护
gm.maintain()
```

### 3. CLI 工具

```bash
# 统计
python -m graph_memory.cli stats

# 搜索
python -m graph_memory.cli search "docker"

# 维护
python -m graph_memory.cli maintain
```

## API 配置

### MiniMax
```python
gm = GraphMemory(
    llm_config={
        "api_key": "YOUR_API_KEY",
        "base_url": "http://192.168.110.125:3000/v1",
        "model": "MiniMax-Text-01"
    }
)
```

### OpenAI 兼容
```python
gm = GraphMemory(
    llm_config={
        "api_key": "YOUR_API_KEY",
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini"
    }
)
```

### 环境变量
| 变量 | 说明 |
|------|------|
| `GM_LLM_API_KEY` | API 密钥 |
| `GM_LLM_BASE_URL` | API 地址 |
| `GM_LLM_MODEL` | 模型名称 |
| `GM_DB_PATH` | 数据库路径 |

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
