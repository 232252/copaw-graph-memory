# 🧠 Graph Memory

> 面向 CoPaw AI Agent 的知识图谱记忆引擎

[English](./README.md) | [中文](./README_ZH.md)

## 什么是 Graph Memory？

Graph Memory 是一个基于知识图谱的 AI Agent 记忆系统。它从对话中提取结构化知识三元组（节点 + 关系），实现：

- **跨对话召回** - 记住过去的解决方案，避免重复犯错
- **上下文压缩** - 75% token 压缩率（7轮对话 95K → 24K）
- **结构化知识** - 任务、技能、事件节点，带类型化关系

## 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/232252/copaw-graph-memory.git
cd copaw-graph-memory

# 安装可选依赖（PageRank 需要）
pip install numpy
```

### Python API

```python
from graph_memory import GraphMemory

# 初始化
gm = GraphMemory(
    llm_config={
        "api_key": "your-api-key",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1"
    }
)

# 记录消息
gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
gm.ingest("session123", "assistant", "正在安装...")

# 提取知识（对话结束后）
result = gm.extract("session123")

# 召回相关知识
context = gm.assemble_context("bilibili")
```

### CLI 使用

```bash
# 查看统计
python -m graph_memory.cli stats

# 搜索知识
python -m graph_memory.cli search "docker"

# 手动记录知识
python -m graph_memory.cli record \
  --type SKILL \
  --name docker-build \
  --description "构建 Docker 镜像" \
  --content "docker-build\n触发条件: 需要构建镜像时\n..."

# 执行维护
python -m graph_memory.cli maintain

# 检查上游
python -m graph_memory.cli sync
```

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Graph Memory                             │
├─────────────────────────────────────────────────────────────┤
│  消息输入 → 存储（零 LLM）                                    │
│              └→ 信号检测 → 知识提取（LLM）                    │
│                                                              │
│  对话结束 → 知识整理（LLM）                                   │
│              └→ 图维护（去重、PageRank）                     │
│                                                              │
│  新对话 → 召回                                               │
│              ├→ FTS5 搜索找种子节点                           │
│              ├→ 图遍历扩展                                   │
│              ├→ PageRank 排序                               │
│              └→ 注入上下文                                    │
└─────────────────────────────────────────────────────────────┘
```

## 知识图谱结构

### 节点类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `TASK` | 用户请求的任务 | `install-bilibili-mcp` |
| `SKILL` | 可复用的操作 | `pip-install-package` |
| `EVENT` | 错误或异常 | `importerror-libgl1` |

### 边类型

| 边 | 方向 | 说明 |
|----|------|------|
| `USED_SKILL` | TASK → SKILL | 任务使用了技能 |
| `SOLVED_BY` | EVENT → SKILL | 错误被技能解决 |
| `REQUIRES` | SKILL → SKILL | 技能需要另一个 |
| `PATCHES` | SKILL → SKILL | 新技能修正旧技能 |
| `CONFLICTS_WITH` | SKILL ↔ SKILL | 技能互斥 |

## 配置

### 环境变量

| 变量 | 说明 |
|------|------|
| `GM_LLM_API_KEY` | LLM API 密钥 |
| `GM_LLM_BASE_URL` | LLM API 地址 |
| `GM_LLM_MODEL` | 模型名称（默认: gpt-4o-mini） |
| `GM_DB_PATH` | 数据库路径 |

### 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `compact_turn_count` | 6 | 触发提取的消息数 |
| `recall_max_nodes` | 6 | 召回的最大节点数 |
| `recall_max_depth` | 2 | 图遍历深度 |
| `pagerank_damping` | 0.85 | PageRank 阻尼系数 |

## 数据库

SQLite 数据库，包含以下表：

| 表 | 说明 |
|----|------|
| `gm_nodes` | 知识节点 |
| `gm_edges` | 关系边 |
| `gm_messages` | 原始对话消息 |
| `gm_messages_fts` | FTS5 全文索引 |
| `gm_nodes_fts` | 节点 FTS 索引 |

## 与原版对比

| 特性 | 原版 (TypeScript) | Python 版 |
|------|------------------|----------|
| 运行时 | Node.js + npm | Python 标准库 |
| 数据库 | @photostructure/sqlite | sqlite3（内置） |
| 向量搜索 | 可选 | FTS5（内置） |
| PageRank | ✅ | ✅ |
| 社区检测 | ✅ | ✅ |

## 上游项目

本项目灵感来自 [adoresever/graph-memory](https://github.com/adoresever/graph-memory)，这是一个面向 OpenClaw 的 TypeScript 实现。

Python 版本是独立重写，具有等价功能，专为 CoPaw 和其他基于 Python 的 Agent 系统设计。

## 开源协议

MIT License - 参见 [LICENSE](./LICENSE)

## 贡献

欢迎贡献！请提交 Issue 或 Pull Request。
