# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-19

### ✨ Added

- **Graph Memory Core**
  - 3 node types: TASK, SKILL, EVENT
  - 5 edge types: USED_SKILL, SOLVED_BY, REQUIRES, PATCHES, CONFLICTS_WITH
  - SQLite + FTS5 for full-text search
  - PageRank algorithm for node ranking
  - Community detection using Label Propagation Algorithm
  - Knowledge extraction from conversations via LLM

- **Recall System**
  - FTS5 search for seed nodes
  - Graph traversal for expanding context
  - Personalized ranking by type priority and PageRank

- **CLI Tools**
  - `search` - Search knowledge graph
  - `stats` - View statistics
  - `record` - Manually record knowledge
  - `maintain` - Run graph maintenance
  - `sync` - Check upstream updates

- **CoPaw Integration**
  - `gm_search` tool - Search knowledge graph
  - `gm_record` tool - Record knowledge manually
  - `gm_stats` tool - View statistics
  - `gm_maintain` tool - Run maintenance

- **Upstream Sync**
  - Built-in sync tool to check adoresever/graph-memory updates

### 🧪 Testing

- 6 test cases covering:
  - Basic workflow
  - Knowledge extraction
  - Recall and context assembly
  - Tools export
  - PageRank calculation
  - Community detection

### 📚 Documentation

- SKILL.md - CoPaw skill documentation
- README.md - Project documentation
- LICENSE - MIT License

## Credits

Inspired by [adoresever/graph-memory](https://github.com/adoresever/graph-memory)

---

## Version History

| Version | Date | Status |
|---------|------|--------|
| 1.0.0 | 2026-03-19 | Initial release |
