#!/usr/bin/env python3
"""
Graph Memory CLI 工具
用法:
    python -m graph_memory.cli [command] [args]
"""

import sys
import argparse
import os
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from graph_memory import GraphMemory


def get_gm() -> GraphMemory:
    """创建 GraphMemory 实例"""
    llm_config = None
    
    api_key = os.environ.get("GM_LLM_API_KEY")
    if api_key:
        llm_config = {
            "api_key": api_key,
            "base_url": os.environ.get("GM_LLM_BASE_URL", "https://api.openai.com/v1"),
            "model": os.environ.get("GM_LLM_MODEL", "gpt-4o-mini")
        }
    
    return GraphMemory(
        db_path=os.environ.get("GM_DB_PATH"),
        llm_config=llm_config
    )


def cmd_search(args):
    """搜索命令"""
    gm = get_gm()
    result = gm.recall(args.query)
    
    print(f"找到 {len(result['nodes'])} 个相关节点")
    print()
    
    context = gm.assemble_context(result)
    print(context)


def cmd_stats(args):
    """统计命令"""
    gm = get_gm()
    stats = gm.get_stats()
    
    print("📊 Graph Memory 统计")
    print("=" * 40)
    print(f"节点数: {stats['nodes']}")
    print(f"边数:   {stats['edges']}")
    print(f"消息数: {stats['messages']}")
    print(f"社区数: {stats['communities']}")
    print()
    
    if stats['type_counts']:
        print("节点类型分布:")
        for t, c in stats['type_counts'].items():
            print(f"  {t}: {c}")
    
    if stats['top_nodes']:
        print()
        print("Top 10 节点 (PageRank):")
        for n in stats['top_nodes']:
            print(f"  {n['name']} ({n['type']}) - PR: {n['pagerank']:.4f}")


def cmd_maintain(args):
    """维护命令"""
    gm = get_gm()
    print("正在执行图维护...")
    result = gm.maintain()
    print(f"✅ 完成! {result['stats']['nodes']} 节点, {result['stats']['edges']} 边")


def cmd_record(args):
    """记录命令"""
    gm = get_gm()
    result = gm.call_tool("gm_record", {
        "type": args.type,
        "name": args.name,
        "description": args.description,
        "content": args.content,
        "session_id": args.session or "cli"
    })
    print(f"✅ 记录成功! Node ID: {result['node_id']}")


def cmd_sync(args):
    """同步上游"""
    skill_dir = Path(__file__).parent.parent
    print(f"技能目录: {skill_dir}")
    print("上游: https://github.com/adoresever/graph-memory")
    print()
    print("上游是 TypeScript 实现，本技能是独立 Python 重构。")
    print("如有功能更新，请手动对比并同步。")


def main():
    parser = argparse.ArgumentParser(
        description="Graph Memory CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # search
    p_search = subparsers.add_parser("search", help="搜索知识图谱")
    p_search.add_argument("query", help="搜索查询")
    
    # stats
    subparsers.add_parser("stats", help="查看统计")
    
    # maintain
    subparsers.add_parser("maintain", help="执行图维护")
    
    # record
    p_record = subparsers.add_parser("record", help="记录知识")
    p_record.add_argument("--type", "-t", required=True, 
                         choices=["TASK", "SKILL", "EVENT"],
                         help="节点类型")
    p_record.add_argument("--name", "-n", required=True,
                         help="节点名称")
    p_record.add_argument("--description", "-d", required=True,
                         help="节点描述")
    p_record.add_argument("--content", "-c", required=True,
                         help="详细内容")
    p_record.add_argument("--session", "-s",
                         help="会话 ID")
    
    # sync
    subparsers.add_parser("sync", help="同步上游")
    
    args = parser.parse_args()
    
    if args.command == "search":
        cmd_search(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "maintain":
        cmd_maintain(args)
    elif args.command == "record":
        cmd_record(args)
    elif args.command == "sync":
        cmd_sync(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
