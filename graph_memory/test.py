"""
Graph Memory 测试模块
"""

import json
import tempfile
import os
from typing import Dict, Any


class MockLLM:
    """模拟 LLM 用于测试"""
    
    def __init__(self, response: str = None):
        self.call_count = 0
        self.responses = []
        self.default_response = response or json.dumps({
            "nodes": [],
            "edges": []
        })
    
    def __call__(self, system: str, user: str) -> str:
        self.call_count += 1
        self.responses.append({"system": system, "user": user})
        
        if self.responses:
            return self.responses[-1].get("_response", self.default_response)
        return self.default_response
    
    def set_response(self, response: str):
        """设置下次调用的响应"""
        if self.responses:
            self.responses[-1]["_response"] = response
        else:
            self.default_response = response


def test_basic_workflow():
    """测试基本工作流"""
    from graph_memory import GraphMemory
    
    db_path = tempfile.mktemp(suffix=".db")
    
    try:
        # 初始化
        gm = GraphMemory(db_path=db_path)
        assert gm is not None
        print("✓ 初始化成功")
        
        # 记录消息
        msg_id = gm.ingest("test_session", "user", "测试消息")
        assert msg_id is not None
        print("✓ 消息记录成功")
        
        # 获取统计
        stats = gm.get_stats()
        assert stats["messages"] == 1
        print("✓ 统计查询成功")
        
        # 搜索（空结果）
        result = gm.recall("测试")
        assert result["nodes"] == []
        print("✓ 搜索成功（空结果）")
        
        gm.close()
        print("\n✅ 基本工作流测试通过！")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_extraction():
    """测试知识提取"""
    from graph_memory import GraphMemory
    
    db_path = tempfile.mktemp(suffix=".db")
    
    # 设置模拟 LLM
    mock = MockLLM(json.dumps({
        "nodes": [
            {
                "type": "TASK",
                "name": "test-task",
                "description": "测试任务",
                "content": "test-task\n目标: 测试\n结果: 完成"
            }
        ],
        "edges": []
    }))
    
    try:
        gm = GraphMemory(db_path=db_path, llm_fn=mock)
        
        # 添加多条消息
        for i in range(6):
            gm.ingest("session1", "user", f"第 {i+1} 条消息")
        
        # 提取
        result = gm.extract("session1", force=True)
        assert result["extracted_count"] == 1
        print("✓ 知识提取成功")
        
        # 验证节点存在
        node = gm.get_node(name="test-task")
        assert node is not None
        assert node["type"] == "TASK"
        print("✓ 节点验证成功")
        
        gm.close()
        print("\n✅ 知识提取测试通过！")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_recall():
    """测试召回"""
    from graph_memory import GraphMemory
    
    db_path = tempfile.mktemp(suffix=".db")
    
    # 设置模拟 LLM
    mock = MockLLM(json.dumps({
        "nodes": [
            {
                "type": "SKILL",
                "name": "docker-build",
                "description": "构建 Docker 镜像",
                "content": "docker-build\n触发条件: 需要构建镜像时"
            }
        ],
        "edges": []
    }))
    
    try:
        gm = GraphMemory(db_path=db_path, llm_fn=mock)
        
        # 直接插入节点
        gm.db.upsert_node("SKILL", "docker-build", "构建 Docker 镜像", 
                         "docker-build\n触发条件: 需要构建镜像时", "test")
        
        # 召回
        result = gm.recall("docker")
        assert len(result["nodes"]) >= 1
        print(f"✓ 召回成功，找到 {len(result['nodes'])} 个节点")
        
        # 组装上下文
        context = gm.assemble_context(result)
        assert "docker" in context.lower() or "相关知识" in context
        print("✓ 上下文组装成功")
        
        gm.close()
        print("\n✅ 召回测试通过！")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_tools():
    """测试工具导出"""
    from graph_memory import GraphMemory
    
    db_path = tempfile.mktemp(suffix=".db")
    
    try:
        gm = GraphMemory(db_path=db_path)
        
        tools = gm.get_tools()
        assert len(tools) == 4
        tool_names = [t["name"] for t in tools]
        assert "gm_search" in tool_names
        assert "gm_record" in tool_names
        assert "gm_stats" in tool_names
        assert "gm_maintain" in tool_names
        print("✓ 工具导出成功")
        
        # 测试工具调用
        result = gm.call_tool("gm_stats", {})
        assert "nodes" in result
        print("✓ 工具调用成功")
        
        gm.close()
        print("\n✅ 工具测试通过！")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_pagerank():
    """测试 PageRank"""
    from graph_memory import GraphMemory
    
    db_path = tempfile.mktemp(suffix=".db")
    
    try:
        gm = GraphMemory(db_path=db_path)
        
        # 创建测试图
        for i in range(5):
            gm.db.upsert_node("TASK", f"task-{i}", f"任务 {i}", 
                            f"task-{i}", "test")
        
        # 添加边
        nodes = gm.db.get_all_nodes()
        for i in range(len(nodes) - 1):
            gm.db.upsert_edge(nodes[i]["id"], nodes[i+1]["id"], 
                            "USED_SKILL", "test", session_id="test")
        
        # 更新 PageRank
        gm.db.update_pageranks()
        
        stats = gm.get_stats()
        assert stats["nodes"] == 5
        assert stats["edges"] == 4
        print("✓ PageRank 计算成功")
        
        # 验证 pagerank 值
        nodes = gm.db.get_all_nodes()
        for node in nodes:
            assert node["pagerank"] > 0
        print("✓ PageRank 验证成功")
        
        gm.close()
        print("\n✅ PageRank 测试通过！")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def test_community():
    """测试社区检测"""
    from graph_memory import GraphMemory
    
    db_path = tempfile.mktemp(suffix=".db")
    
    try:
        gm = GraphMemory(db_path=db_path)
        
        # 创建两个社区
        # 社区 1: docker 相关
        for name in ["docker-build", "docker-run", "docker-compose"]:
            gm.db.upsert_node("SKILL", name, name, name, "test")
        
        # 社区 2: git 相关
        for name in ["git-commit", "git-push", "git-branch"]:
            gm.db.upsert_node("SKILL", name, name, name, "test")
        
        # 添加边（社区内连接）
        nodes = {n["name"]: n for n in gm.db.get_all_nodes()}
        
        # Docker 社区内连接
        gm.db.upsert_edge(nodes["docker-build"]["id"], nodes["docker-run"]["id"],
                         "REQUIRES", "需要先 build", session_id="test")
        
        # Git 社区内连接
        gm.db.upsert_edge(nodes["git-commit"]["id"], nodes["git-push"]["id"],
                         "REQUIRES", "需要先 commit", session_id="test")
        
        # 更新社区
        count = gm.community_detector.update_communities()
        assert count == 6
        print(f"✓ 社区检测完成，{count} 个节点分配了社区")
        
        # 验证社区
        nodes = gm.db.get_all_nodes()
        docker_nodes = [n for n in nodes if "docker" in n["name"] and n["community_id"]]
        git_nodes = [n for n in nodes if "git" in n["name"] and n["community_id"]]
        
        if docker_nodes:
            docker_communities = set(n["community_id"] for n in docker_nodes)
            print(f"✓ Docker 社区: {len(docker_communities)} 个")
        
        if git_nodes:
            git_communities = set(n["community_id"] for n in git_nodes)
            print(f"✓ Git 社区: {len(git_communities)} 个")
        
        gm.close()
        print("\n✅ 社区检测测试通过！")
        
    finally:
        if os.path.exists(db_path):
            os.unlink(db_path)


def run_all_tests():
    """运行所有测试"""
    print("=" * 50)
    print("Graph Memory 测试套件")
    print("=" * 50)
    
    tests = [
        ("基本工作流", test_basic_workflow),
        ("知识提取", test_extraction),
        ("召回", test_recall),
        ("工具", test_tools),
        ("PageRank", test_pagerank),
        ("社区检测", test_community),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        print(f"\n[{name}]")
        try:
            test_fn()
            passed += 1
        except Exception as e:
            print(f"❌ 失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {passed} 通过, {failed} 失败")
    print("=" * 50)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
