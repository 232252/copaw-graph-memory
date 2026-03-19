#!/usr/bin/env python3
"""
Graph Memory 上游同步工具

检查上游 adoresever/graph-memory 的更新，
并提示如何同步到本 Python 实现。
"""

import urllib.request
import json
import sys
from pathlib import Path


UPSTREAM_REPO = "adoresever/graph-memory"
UPSTREAM_URL = f"https://api.github.com/repos/{UPSTREAM_REPO}"
LOCAL_VERSION = "1.0.0"


def get_upstream_info():
    """获取上游信息"""
    try:
        req = urllib.request.Request(
            UPSTREAM_URL,
            headers={"User-Agent": "GraphMemory-Sync/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except Exception as e:
        return {"error": str(e)}


def get_upstream_commits(limit=5):
    """获取上游最近提交"""
    try:
        url = f"https://api.github.com/repos/{UPSTREAM_REPO}/commits"
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "GraphMemory-Sync/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            commits = json.loads(resp.read())
            return commits[:limit]
    except Exception as e:
        return []


def check_updates():
    """检查更新"""
    print("=" * 60)
    print("Graph Memory 上游同步检查")
    print("=" * 60)
    print()
    print(f"上游仓库: https://github.com/{UPSTREAM_REPO}")
    print(f"本地版本: {LOCAL_VERSION}")
    print()
    
    info = get_upstream_info()
    
    if "error" in info:
        print(f"⚠️  无法获取上游信息: {info['error']}")
        return
    
    print(f"上游仓库信息:")
    print(f"  ⭐ Stars: {info.get('stargazers_count', 'N/A')}")
    print(f"  🍴 Forks: {info.get('forks_count', 'N/A')}")
    print(f"  最后更新: {info.get('updated_at', 'N/A')[:10]}")
    print()
    
    commits = get_upstream_commits()
    if commits:
        print("最近提交:")
        for i, commit in enumerate(commits, 1):
            msg = commit["commit"]["message"].split("\n")[0][:50]
            date = commit["commit"]["author"]["date"][:10]
            print(f"  {i}. [{date}] {msg}...")
        print()
    
    print("=" * 60)
    print("同步说明")
    print("=" * 60)
    print()
    print("上游 adoresever/graph-memory 是 TypeScript/Node.js 实现，")
    print("本项目是独立的 Python 重构版本。")
    print()
    print("同步上游更新的步骤:")
    print("  1. 克隆上游: git clone https://github.com/adoresever/graph-memory.git /tmp/graph-memory-upstream")
    print("  2. 对比差异: diff -r graph_memory/ /tmp/graph-memory-upstream/src/")
    print("  3. 手动同步: 根据上游更新调整 Python 代码")
    print("  4. 运行测试: python -m graph_memory.test")
    print()
    print("注意: 上游使用 Node.js 生态库（如 @photostructure/sqlite），")
    print("      Python 实现使用内置 sqlite3，功能等价但实现不同。")
    print()


def sync_from_upstream():
    """从上游同步（概念验证）"""
    print("正在获取上游代码...")
    
    try:
        # 获取 README
        readme_url = f"https://raw.githubusercontent.com/{UPSTREAM_REPO}/main/README.md"
        req = urllib.request.Request(readme_url, headers={"User-Agent": "GraphMemory-Sync/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read().decode()
            
            # 保存到本地
            skill_dir = Path(__file__).parent.parent
            local_readme = skill_dir / "UPSTREAM_README.md"
            with open(local_readme, "w") as f:
                f.write(content)
            print(f"✓ 已保存上游 README 到 {local_readme}")
            
    except Exception as e:
        print(f"⚠️  获取上游 README 失败: {e}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--sync":
        sync_from_upstream()
    else:
        check_updates()
