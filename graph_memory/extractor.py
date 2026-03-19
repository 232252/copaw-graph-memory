"""
Graph Memory 知识提取模块
从对话中提取知识三元组
"""

import json
import re
from typing import List, Dict, Any, Optional, Callable


# 提取 System Prompt
EXTRACT_SYS = """你是 graph-memory 知识图谱提取引擎，从 AI Agent 对话中提取可复用的结构化知识三元组（节点 + 关系）。
提取的知识将在未来对话中被召回，帮助 Agent 避免重复犯错、复用已验证方案。
输出严格 JSON：{"nodes":[...],"edges":[...]}，不包含任何额外文字。

1. 节点提取：
   1.1 从对话中识别三类知识节点：
       - TASK：用户要求 Agent 完成的具体任务，或对话中讨论、分析、对比的主题
       - SKILL：可复用的操作技能，有具体工具/命令/API，有明确触发条件，步骤可直接执行
       - EVENT：一次性的报错或异常，记录现象、原因和解决方法
   1.2 每个节点必须包含 4 个字段，缺一不可：
       - type：节点类型，只允许 TASK / SKILL / EVENT
       - name：全小写连字符命名，确保整个提取过程命名一致
       - description：一句话说明什么场景触发
       - content：纯文本格式的知识内容（见 1.4 的模板）
   1.3 name 命名规范：
       - TASK：动词-对象格式，如 deploy-bilibili-mcp、extract-pdf-tables、compare-ocr-engines
       - SKILL：工具-操作格式，如 conda-env-create、docker-port-expose
       - EVENT：现象-工具格式，如 importerror-libgl1、timeout-paddleocr
       - 已有节点列表会提供，相同事物必须复用已有 name，不得创建重复节点
   1.4 content 模板（纯文本，按 type 选用）：
       TASK → "[name]\n目标: ...\n执行步骤:\n1. ...\n2. ...\n结果: ..."
       SKILL → "[name]\n触发条件: ...\n执行步骤:\n1. ...\n2. ...\n常见错误:\n- ... -> ..."
       EVENT → "[name]\n现象: ...\n原因: ...\n解决方法: ..."

2. 关系提取：
   2.1 识别节点之间直接、明确的关系，只允许以下 5 种边类型。
   2.2 每条边必须包含 from、to、type、instruction 四个字段，缺一不可。
   2.3 边类型定义与方向约束（严格遵守，不得混用）：

       USED_SKILL
         方向：TASK → SKILL（且仅限此方向）
         含义：任务执行过程中使用了该技能
         instruction：写第几步用的、怎么调用的、传了什么参数
         判定：from 节点是 TASK，to 节点是 SKILL

       SOLVED_BY
         方向：EVENT → SKILL 或 SKILL → SKILL
         含义：该报错/问题被该技能解决
         instruction：写具体执行了什么命令/操作来解决
         condition（必填）：写什么错误或条件触发了这个解决方案
         判定：from 节点是 EVENT 或 SKILL，to 节点是 SKILL
         注意：TASK 节点不能作为 SOLVED_BY 的 from，TASK 使用技能必须用 USED_SKILL

       REQUIRES
         方向：SKILL → SKILL
         含义：执行该技能前必须先完成另一个技能
         instruction：写为什么依赖、怎么判断前置条件是否已满足

       PATCHES
         方向：SKILL → SKILL（新 → 旧）
         含义：新技能修正/替代了旧技能的做法
         instruction：写旧方案有什么问题、新方案改了什么

       CONFLICTS_WITH
         方向：SKILL ↔ SKILL（双向）
         含义：两个技能在同一场景互斥
         instruction：写冲突的具体表现、应该选哪个

   2.4 关系方向选择决策树（按此顺序判定）：
       a. from 是 TASK，to 是 SKILL → 必须用 USED_SKILL
       b. from 是 EVENT，to 是 SKILL → 必须用 SOLVED_BY
       c. from 和 to 都是 SKILL → 根据语义选 SOLVED_BY / REQUIRES / PATCHES / CONFLICTS_WITH
       d. 不存在其他合法组合，不符合以上任何一条的关系不要提取

3. 提取策略（宁多勿漏）：
   3.1 所有对话内容都应尝试提取，包括讨论、分析、对比、方案选型等
   3.2 用户纠正 AI 的错误时，旧做法和新做法都要提取，用 PATCHES 边关联
   3.3 讨论和对比类对话提取为 TASK，记录讨论的结论和要点
   3.4 只有纯粹的寒暄问候（如"你好""谢谢"）才不提取

4. 输出规范：
   4.1 只返回 JSON，格式为 {"nodes":[...],"edges":[...]}
   4.2 禁止 markdown 代码块包裹，禁止解释文字，禁止额外字段
   4.3 没有知识产出时返回 {"nodes":[],"edges":[]}
   4.4 每条 edge 的 instruction 必须写具体可执行的内容，不能为空或写"见上文"

示例 1（TASK + SKILL + USED_SKILL 边）：

对话摘要：用户要求抓取B站弹幕，Agent 使用 bili-tool 的 danmaku 子命令完成。

输出：
{"nodes":[{"type":"TASK","name":"extract-bilibili-danmaku","description":"从B站视频中批量抓取弹幕数据","content":"extract-bilibili-danmaku\n目标: 从指定B站视频抓取全部弹幕\n执行步骤:\n1. 获取视频 BV 号\n2. 调用 bili-tool danmaku --bv BVxxx\n3. 输出 JSON 格式弹幕列表\n结果: 成功抓取 2341 条弹幕"},{"type":"SKILL","name":"bili-tool-danmaku","description":"使用 bili-tool 抓取B站视频弹幕","content":"bili-tool-danmaku\n触发条件: 需要抓取B站视频弹幕时\n执行步骤:\n1. pip install bilibili-api-python\n2. python bili_tool.py danmaku --bv BVxxx --output danmaku.json\n常见错误:\n- cookie 过期 -> 重新获取 SESSDATA"}],"edges":[{"from":"extract-bilibili-danmaku","to":"bili-tool-danmaku","type":"USED_SKILL","instruction":"第 2 步调用 bili-tool danmaku 子命令，传入 --bv 和 --output 参数"}]}

示例 2（EVENT + SKILL + SOLVED_BY 边）：

对话摘要：执行 PaddleOCR 时报 libGL 缺失，通过 apt 安装解决。

输出：
{"nodes":[{"type":"EVENT","name":"importerror-libgl1","description":"导入 cv2/paddleocr 时报 libGL.so.1 缺失","content":"importerror-libgl1\n现象: ImportError: libGL.so.1: cannot open shared object file\n原因: OpenCV 依赖系统级 libGL 库，conda/pip 不自动安装\n解决方法: apt install -y libgl1-mesa-glx"},{"type":"SKILL","name":"apt-install-libgl1","description":"安装 libgl1 解决 OpenCV 系统依赖缺失","content":"apt-install-libgl1\n触发条件: ImportError: libGL.so.1\n执行步骤:\n1. sudo apt update\n2. sudo apt install -y libgl1-mesa-glx\n常见错误:\n- Permission denied -> 加 sudo"}],"edges":[{"from":"importerror-libgl1","to":"apt-install-libgl1","type":"SOLVED_BY","instruction":"执行 sudo apt install -y libgl1-mesa-glx","condition":"报 ImportError: libGL.so.1 时"}]}"""


class Extractor:
    """知识提取器"""
    
    def __init__(self, llm_fn: Callable):
        """
        初始化提取器
        
        Args:
            llm_fn: LLM 调用函数，签名为 (system: str, user: str) -> str
        """
        self.llm_fn = llm_fn
    
    def format_messages(self, messages: List[Dict[str, Any]]) -> str:
        """格式化对话为提取输入"""
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                formatted.append(f"[{role.upper()}] {content}")
        return "\n\n".join(formatted)
    
    def format_existing_nodes(self, existing_names: List[str]) -> str:
        """格式化已有节点列表"""
        if not existing_names:
            return "（无）"
        return ", ".join(existing_names)
    
    def extract(self, messages: List[Dict[str, Any]], existing_names: List[str]) -> Dict[str, Any]:
        """
        从对话中提取知识
        
        Args:
            messages: 对话消息列表
            existing_names: 已存在节点的名称列表
        
        Returns:
            {"nodes": [...], "edges": [...]}
        """
        formatted_msgs = self.format_messages(messages)
        existing = self.format_existing_nodes(existing_names)
        
        user_prompt = f"""<Existing Nodes>
{existing}

<Conversation>
{formatted_msgs}"""
        
        response = self.llm_fn(EXTRACT_SYS, user_prompt)
        
        # 解析 JSON
        try:
            # 尝试直接解析
            result = json.loads(response)
        except json.JSONDecodeError:
            # 尝试移除 markdown 代码块
            cleaned = re.sub(r"^```json\s*", "", response.strip())
            cleaned = re.sub(r"\s*```$", "", cleaned)
            try:
                result = json.loads(cleaned)
            except json.JSONDecodeError:
                # 返回空结果
                return {"nodes": [], "edges": []}
        
        # 验证和清理
        nodes = []
        for n in result.get("nodes", []):
            if self._validate_node(n):
                nodes.append(n)
        
        edges = []
        for e in result.get("edges", []):
            if self._validate_edge(e):
                edges.append(e)
        
        return {"nodes": nodes, "edges": edges}
    
    def _validate_node(self, node: Dict) -> bool:
        """验证节点"""
        required = ("type", "name", "description", "content")
        if not all(k in node for k in required):
            return False
        if node["type"] not in ("TASK", "SKILL", "EVENT"):
            return False
        return True
    
    def _validate_edge(self, edge: Dict) -> bool:
        """验证边"""
        required = ("from", "to", "type", "instruction")
        if not all(k in edge for k in required):
            return False
        if edge["type"] not in ("USED_SKILL", "SOLVED_BY", "REQUIRES", "PATCHES", "CONFLICTS_WITH"):
            return False
        return True
