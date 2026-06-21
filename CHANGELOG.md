# Changelog

## 1.0.1 (2026-06-21)
- 🐛 **Bug 修复**
  - 修复 `graph_walk` 在 `seed_ids` 为空时崩溃 (SQL `IN ()` 非法)
  - 修复 `upsert_node` 中 FTS5 索引重建逻辑 (之前用 `SELECT rowid` 错位,现在直接用 lastrowid)
  - 修复 `extract()` 线程安全 (用 threading.Lock 保护 `_extract_running`)
- ✨ **优化**
  - `GraphDB` 和 `GraphMemory` 支持 `with` 上下文管理器
  - 减少 `upsert_node` 多余的 get_node 查询
- 🔄 **上游对照**
  - 上游 adoresever/graph-memory (TypeScript) 最后更新 2026-04-07
  - 本项目是独立 Python 重构,需手动同步思路

## 1.0.0 (2026-03-19)
- 初始版本
