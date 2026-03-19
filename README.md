# 🧠 Graph Memory

> Knowledge Graph Memory Engine for CoPaw AI Agent

[English](./README.md) | [中文](./README_ZH.md)

## What is Graph Memory?

Graph Memory is a knowledge graph-based memory system for AI agents. It extracts structured knowledge triples (nodes + relationships) from conversations, enabling:

- **Cross-session recall** - Remember past solutions without repeating mistakes
- **Context compression** - 75% token reduction (95K → 24K for 7-round conversations)
- **Structured knowledge** - Task, Skill, Event nodes with typed relationships

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/232252/copaw-graph-memory.git
cd copaw-graph-memory

# Install optional dependency (for PageRank)
pip install numpy
```

### Python API

```python
from graph_memory import GraphMemory

# Initialize
gm = GraphMemory(
    llm_config={
        "api_key": "your-api-key",
        "model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1"
    }
)

# Record messages
gm.ingest("session123", "user", "帮我安装 bilibili-mcp")
gm.ingest("session123", "assistant", "正在安装...")

# Extract knowledge (after conversation)
result = gm.extract("session123")

# Recall relevant knowledge
context = gm.assemble_context("bilibili")
```

### CLI Usage

```bash
# View statistics
python -m graph_memory.cli stats

# Search knowledge
python -m graph_memory.cli search "docker"

# Record knowledge manually
python -m graph_memory.cli record \
  --type SKILL \
  --name docker-build \
  --description "Build Docker image" \
  --content "docker-build\nTrigger: When building images..."

# Run maintenance
python -m graph_memory.cli maintain

# Check upstream
python -m graph_memory.cli sync
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Graph Memory                             │
├─────────────────────────────────────────────────────────────┤
│  Message In → Store (zero LLM)                              │
│              └→ Signal Detection → Knowledge Extraction      │
│                                                              │
│  Session End → Knowledge Organization (LLM)                  │
│              └→ Graph Maintenance (dedup, PageRank)         │
│                                                              │
│  New Session → Recall                                        │
│              ├→ FTS5 search for seed nodes                  │
│              ├→ Graph traversal expansion                   │
│              ├→ PageRank ranking                            │
│              └→ Inject into context                          │
└─────────────────────────────────────────────────────────────┘
```

## Knowledge Graph Structure

### Node Types

| Type | Description | Example |
|------|-------------|---------|
| `TASK` | User-requested tasks | `install-bilibili-mcp` |
| `SKILL` | Reusable operations | `pip-install-package` |
| `EVENT` | Errors or exceptions | `importerror-libgl1` |

### Edge Types

| Edge | Direction | Description |
|------|-----------|-------------|
| `USED_SKILL` | TASK → SKILL | Task uses a skill |
| `SOLVED_BY` | EVENT → SKILL | Error solved by skill |
| `REQUIRES` | SKILL → SKILL | Skill requires another |
| `PATCHES` | SKILL → SKILL | New skill patches old one |
| `CONFLICTS_WITH` | SKILL ↔ SKILL | Skills are mutually exclusive |

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `GM_LLM_API_KEY` | LLM API key |
| `GM_LLM_BASE_URL` | LLM API base URL |
| `GM_LLM_MODEL` | Model name (default: gpt-4o-mini) |
| `GM_DB_PATH` | Database path |

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `compact_turn_count` | 6 | Messages to trigger extraction |
| `recall_max_nodes` | 6 | Max nodes to recall |
| `recall_max_depth` | 2 | Graph traversal depth |
| `pagerank_damping` | 0.85 | PageRank damping factor |

## Database

SQLite database with the following tables:

| Table | Description |
|-------|-------------|
| `gm_nodes` | Knowledge nodes |
| `gm_edges` | Relationships |
| `gm_messages` | Raw conversation messages |
| `gm_messages_fts` | FTS5 full-text index |
| `gm_nodes_fts` | Node FTS index |

## Comparison with Original

| Feature | Original (TypeScript) | Python Version |
|---------|----------------------|----------------|
| Runtime | Node.js + npm | Python stdlib |
| Database | @photostructure/sqlite | sqlite3 (built-in) |
| Vector Search | Optional | FTS5 (built-in) |
| PageRank | ✅ | ✅ |
| Community Detection | ✅ | ✅ |

## Upstream

This project is inspired by [adoresever/graph-memory](https://github.com/adoresever/graph-memory), which is a TypeScript implementation for OpenClaw.

The Python version is a standalone rewrite with equivalent functionality, designed for CoPaw and other Python-based agent systems.

## License

MIT License - see [LICENSE](./LICENSE)

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.
