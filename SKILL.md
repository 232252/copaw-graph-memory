---
name: graph-memory
description: "知识图谱记忆引擎 - 从对话中提取结构化知识，支持跨对话召回。灵感来自 adoresever/graph-memory，MIT License。使用场景：(1) AI 助手需要记住之前的操作经验，(2) 避免重复犯错，(3) 压缩上下文提升效率。"
homepage: https://github.com/adoresever/graph-memory
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

# Graph Memory - 知识图谱记忆引擎

基于 [adoresever/graph-memory](https://github.com/adoresever/graph-memory) 的 Python 实现，专为 CoPaw AI Agent 设计的知识图谱记忆引擎。

## 核心功能

- **3种节点类型**: TASK（任务）、SKILL（技能）、EVENT（事件）
- **5种边类型**: USED_SKILL、SOLVED_BY、REQUIRES、PATCHES、CONFLICTS_WITH
- **跨对话召回**: FTS5 全文搜索 + 图遍历 + Personalized PageRank
- **上下文压缩**: 7轮对话 95K tokens → 24K，**75% 压缩率**
- **零依赖**: 仅使用 Python 内置 `sqlite3`，NumPy 可选（用于 PageRank）

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

## 快速开始

### Python API

```python
from graph_memory import GraphMemory

# 初始化
gm = GraphMemory(
    llm_config={"api_key": "...", "model": "gpt-4o-mini"}
)

# 记录消息
gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
gm.ingest("session123", "assistant", "正在安装...")

# 提取知识
result = gm.extract("session123")

# 召回
context = gm.assemble_context("bilibili")
```

### CLI 工具

```bash
# 搜索
python -m graph_memory.cli search "bilibili"

# 统计
python -m graph_memory.cli stats

# 维护
python -m graph_memory.cli maintain

# 查看帮助
python -m graph_memory.cli --help
```

## 配置

环境变量或初始化参数：

| 配置 | 环境变量 | 说明 |
|------|---------|------|
| API Key | `GM_LLM_API_KEY` | LLM API Key |
| Base URL | `GM_LLM_BASE_URL` | LLM API 地址 |
| 模型 | `GM_LLM_MODEL` | 模型名称 |
| 数据库 | `GM_DB_PATH` | 数据库路径 |

## 数据库结构

| 表 | 说明 |
|----|------|
| `gm_nodes` | 知识节点（带 pagerank、community_id） |
| `gm_edges` | 关系边 |
| `gm_messages` | 原始对话消息 |
| `gm_messages_fts` | FTS5 全文索引 |
| `gm_nodes_fts` | 节点 FTS 索引 |

## 工具列表

| 工具 | 说明 |
|------|------|
| `gm_search` | 搜索知识图谱 |
| `gm_record` | 手动记录知识 |
| `gm_stats` | 查看统计信息 |
| `gm_maintain` | 执行图维护 |

## 上游同步

本技能跟踪上游 [adoresever/graph-memory](https://github.com/adoresever/graph-memory)，定期检查更新并同步。

查看当前版本：

```bash
git -C ~/.copaw/workspaces/default/skills/graph-memory log --oneline -1
```

手动同步：

```bash
git -C ~/.copaw/workspaces/default/skills/graph-memory pull origin main
```
