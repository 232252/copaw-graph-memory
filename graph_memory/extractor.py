"""
Graph Memory 知识提取模块
从对话中提取知识三元组
支持 MiniMax 等推理模型的自然语言输出
"""

import json
import re
from typing import List, Dict, Any, Optional, Callable


# 提取 System Prompt
EXTRACT_SYS = """You are a knowledge graph extractor. Extract structured knowledge from the conversation.

Task types:
- TASK: user request or goal
- SKILL: reusable procedure with steps  
- EVENT: error or exception

Edge types:
- USED_SKILL: TASK uses SKILL
- SOLVED_BY: EVENT fixed by SKILL
- REQUIRES: SKILL needs another SKILL
- PATCHES: new SKILL fixes old SKILL
- CONFLICTS_WITH: two SKILLs conflict

Example:
Input: user asked to install bilibili-mcp, assistant ran pip install
Output:
{"nodes":[{"type":"TASK","name":"install-bilibili-mcp","description":"install bilibili-mcp package","content":"install-bilibili-mcp\nGoal: install bilibili-mcp\nSteps:\n1. pip install bilibili-mcp\nResult: done"}],"edges":[]}"""


class Extractor:
    """知识提取器"""
    
    def __init__(self, llm_fn: Callable):
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
            return "(none)"
        return ", ".join(existing_names)
    
    def extract(self, messages: List[Dict[str, Any]], existing_names: List[str]) -> Dict[str, Any]:
        """从对话中提取知识"""
        formatted_msgs = self.format_messages(messages)
        existing = self.format_existing_nodes(existing_names)
        
        user_prompt = f"""Existing nodes: {existing}

Conversation:
{formatted_msgs}

Output JSON only with nodes and edges:"""
        
        response = self.llm_fn(EXTRACT_SYS, user_prompt)
        result = self._parse_json_response(response)
        
        if result is None:
            # 尝试从自然语言中提取
            result = self._parse_natural_language(response)
        
        if result is None:
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
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 返回的 JSON 响应"""
        if not response:
            return None
        
        # 尝试直接解析
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # 清理 markdown
        cleaned = re.sub(r"^```json\s*", "", response.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # 暴力查找 { 和 }
        start = response.rfind('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            candidate = response[start:end]
            try:
                return json.loads(candidate)
            except:
                pass
        
        return None
    
    def _parse_natural_language(self, text: str) -> Optional[Dict[str, Any]]:
        """从自然语言中提取结构化知识"""
        nodes = []
        edges = []
        
        # 提取 TASK/SKILL/EVENT 节点
        # 匹配各种模式
        patterns = [
            # TASK pattern
            r'(?:type[:\s]*["\']?TASK["\']?|["\']type["\']\s*:\s*["\']TASK["\'])[^}]*?name[:\s]*["\']?([a-z0-9-]+)["\']?[^}]*?description[:\s]*["\']?([^"\'\n]+)["\']?',
            # SKILL pattern  
            r'(?:type[:\s]*["\']?SKILL["\']?|["\']type["\']\s*:\s*["\']SKILL["\'])[^}]*?name[:\s]*["\']?([a-z0-9-]+)["\']?[^}]*?description[:\s]*["\']?([^"\'\n]+)["\']?',
            # EVENT pattern
            r'(?:type[:\s]*["\']?EVENT["\']?|["\']type["\']\s*:\s*["\']EVENT["\'])[^}]*?name[:\s]*["\']?([a-z0-9-]+)["\']?[^}]*?description[:\s]*["\']?([^"\'\n]+)["\']?',
        ]
        
        # 更简单的方法：查找文本中提到的节点
        # TASK 关键词
        task_keywords = ['install', 'setup', 'build', 'deploy', 'create', 'run', 'execute', 'download']
        for keyword in task_keywords:
            if keyword in text.lower():
                # 尝试提取任务名
                match = re.search(rf'{keyword}[- ]([a-z0-9-]+)', text, re.IGNORECASE)
                if match:
                    name = match.group(1).lower()
                    # 查找描述
                    desc_match = re.search(rf'{keyword}[- ]{name}[^.]*\.\s*([^.!?]+)', text, re.IGNORECASE)
                    desc = desc_match.group(1).strip() if desc_match else f"{keyword} {name}"
                    
                    # 检查是否已存在
                    if not any(n.get('name') == name for n in nodes):
                        nodes.append({
                            "type": "TASK",
                            "name": name,
                            "description": desc[:100],
                            "content": f"{name}\nGoal: {desc}\nSteps:\n1. (to be filled)\nResult: pending"
                        })
        
        # SKILL 关键词
        skill_keywords = ['pip install', 'apt install', 'npm install', 'docker', 'git clone', 'curl', 'wget']
        for keyword in skill_keywords:
            if keyword in text.lower():
                match = re.search(rf'{re.escape(keyword)}[- ]([a-z0-9-]+)', text, re.IGNORECASE)
                if match:
                    name = match.group(1).lower().replace('.', '-')
                    desc = f"使用{keyword}安装{name}"
                    
                    if not any(n.get('name') == name for n in nodes):
                        nodes.append({
                            "type": "SKILL",
                            "name": name,
                            "description": desc[:100],
                            "content": f"{name}\nTrigger: 需要安装{name}时\nSteps:\n1. {keyword} {name}\nCommon errors:\n- permission denied -> sudo"
                        })
        
        if nodes or edges:
            return {"nodes": nodes, "edges": edges}
        
        return None
    
    def _validate_node(self, node: Dict) -> bool:
        """验证节点"""
        if not isinstance(node, dict):
            return False
        required = ("type", "name")
        if not all(k in node for k in required):
            return False
        if node["type"] not in ("TASK", "SKILL", "EVENT"):
            return False
        if not node.get("name"):
            return False
        return True
    
    def _validate_edge(self, edge: Dict) -> bool:
        """验证边"""
        if not isinstance(edge, dict):
            return False
        required = ("from", "to", "type")
        if not all(k in edge for k in required):
            return False
        if edge["type"] not in ("USED_SKILL", "SOLVED_BY", "REQUIRES", "PATCHES", "CONFLICTS_WITH"):
            return False
        return True
