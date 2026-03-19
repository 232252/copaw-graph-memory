"""
Graph Memory 知识提取模块
从对话中提取知识三元组
支持 MiniMax 等推理模型的自然语言输出
"""

import json
import re
from typing import List, Dict, Any, Optional, Callable


# 提取 System Prompt - 使用代码块格式提高 JSON 提取成功率
EXTRACT_SYS = """你是知识图谱提取器。你的输出必须用 ```json 代码块包裹，不要输出任何其他文字。

```json
{"nodes":[{"type":"TASK","name":"task-name","description":"描述"}],"edges":[{"from_id":"task-name","to_id":"skill-name","type":"USED_SKILL"}]}
```"""

# 节点类型和边类型的标准值
VALID_NODE_TYPES = ("TASK", "SKILL", "EVENT")
VALID_EDGE_TYPES = ("USED_SKILL", "SOLVED_BY", "REQUIRES", "PATCHES", "CONFLICTS_WITH")
EDGE_TYPE_ALIASES = {
    "source": "from_id",
    "target": "to_id",
    "前置条件": "USED_SKILL",
    "前置": "USED_SKILL",
    "使用": "USED_SKILL",
    "解决": "SOLVED_BY",
    "修复": "SOLVED_BY",
    "需要": "REQUIRES",
    "依赖": "REQUIRES",
    "更新": "PATCHES",
    "替代": "PATCHES",
    "冲突": "CONFLICTS_WITH",
    "互斥": "CONFLICTS_WITH",
}

# 中文到英文的映射
CHINESE_KEYWORD_MAP = {
    "安装": "install",
    "运行": "run",
    "创建": "create",
    "下载": "download",
    "设置": "setup",
    "配置": "config",
    "构建": "build",
    "部署": "deploy",
    "管理": "manage",
    "视频": "video",
    "错误": "error",
    "问题": "issue",
    "解决": "solve",
    "修复": "fix",
    "使用": "use",
    "需要": "need",
    "依赖": "dep",
    "更新": "update",
    "替代": "replace",
    "冲突": "conflict",
}


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
        
        # 1. 先尝试解析 JSON
        result = self._parse_json_response(response)
        
        # 2. 如果失败，从对话本身提取
        if result is None:
            result = self._extract_from_conversation(formatted_msgs)
        
        if result is None:
            return {"nodes": [], "edges": []}
        
        # 3. 规范化结果
        result = self._normalize_result(result)
        
        # 4. 如果规范化后有节点但没有边，尝试推断边
        nodes = result.get("nodes", [])
        edges = result.get("edges", [])
        
        if nodes and not edges:
            edges = self._infer_edges(nodes, formatted_msgs)
        
        return {"nodes": nodes, "edges": edges}
    
    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """规范化提取结果"""
        nodes = []
        node_names = {}  # 名称到节点的映射
        
        for n in result.get("nodes", []):
            if not isinstance(n, dict):
                continue
            
            # 提取和验证类型
            node_type = n.get("type", "")
            
            # 字段名映射：支持 name, id, label
            name = n.get("name") or n.get("label") or n.get("id") or ""
            
            if not name:
                continue
            
            # 如果 type 不是标准类型，尝试推断
            if node_type not in VALID_NODE_TYPES:
                # 根据 label/id 内容推断
                name_lower = name.lower()
                if any(k in name_lower for k in ['install', 'run', 'build', 'create', 'setup', 'download', 'config']):
                    node_type = "TASK"
                elif any(k in name_lower for k in ['docker', 'pip', 'apt', 'npm', 'curl', 'git']):
                    node_type = "SKILL"
                elif any(k in name_lower for k in ['error', 'fail', 'exception', 'timeout', 'refused']):
                    node_type = "EVENT"
                else:
                    # 默认为 TASK
                    node_type = "TASK"
            
            # 转换中文名称为英文 slug（如果需要）
            name = str(name)
            if re.search(r'[\u4e00-\u9fff]', name):
                name = self._transliterate_name(name)
                name = self._clean_name(name)
            else:
                name = self._clean_name(name)
            
            if not name or len(name) < 2:
                continue
            
            node = {
                "type": node_type,
                "name": name,
                "description": str(n.get("description", ""))[:200],
                "content": str(n.get("content", f"{name}\nDescription: {n.get('description', '')}"))[:500]
            }
            nodes.append(node)
            node_names[name] = node
        
        # 构建原始名称到节点名称的映射（用于边匹配）
        original_to_clean = {}
        for n in result.get("nodes", []):
            original = n.get("name") or n.get("label") or n.get("id") or ""
            if original:
                original_lower = original.lower()
                # 如果是中文，转换
                if re.search(r'[\u4e00-\u9fff]', original):
                    cleaned = self._transliterate_name(original)
                    cleaned = self._clean_name(cleaned)
                    original_to_clean[original_lower] = cleaned
                else:
                    original_to_clean[original_lower] = self._clean_name(original)
        
        # 规范化边
        edges = []
        for e in result.get("edges", []):
            if not isinstance(e, dict):
                continue
            
            # 标准化字段名
            from_id = e.get("from_id") or e.get("from") or e.get("source") or ""
            to_id = e.get("to_id") or e.get("to") or e.get("target") or ""
            edge_type = e.get("type") or e.get("relation") or ""
            
            # 转换中文边类型
            if edge_type in EDGE_TYPE_ALIASES:
                edge_type = EDGE_TYPE_ALIASES[edge_type]
            
            # 验证
            if edge_type not in VALID_EDGE_TYPES:
                continue
            if not from_id or not to_id:
                continue
            
            # 尝试匹配节点：先清理，再查找
            from_id_clean = self._clean_name(from_id)
            to_id_clean = self._clean_name(to_id)
            
            # 如果清理后找不到，尝试原始名称映射
            from_id_lower = from_id.lower()
            to_id_lower = to_id.lower()
            
            matched_from = None
            matched_to = None
            
            # 查找 from_id
            for node_name, node_obj in node_names.items():
                if (from_id_clean and node_name == from_id_clean) or \
                   (from_id_lower in original_to_clean and original_to_clean[from_id_lower] == node_name) or \
                   from_id_lower == node_name:
                    matched_from = node_obj.get("id", node_name)
                    break
            
            # 查找 to_id
            for node_name, node_obj in node_names.items():
                if (to_id_clean and node_name == to_id_clean) or \
                   (to_id_lower in original_to_clean and original_to_clean[to_id_lower] == node_name) or \
                   to_id_lower == node_name:
                    matched_to = node_obj.get("id", node_name)
                    break
            
            if matched_from and matched_to:
                edges.append({
                    "from_id": matched_from,
                    "to_id": matched_to,
                    "type": edge_type
                })
        
        return {"nodes": nodes, "edges": edges}
    
    def _transliterate_name(self, name: str) -> str:
        """将中文名称转换为英文 slug"""
        if not name:
            return ""
        
        name_lower = name.lower()
        
        # 如果已经是英文/数字，直接清理
        if re.match(r'^[a-z0-9\-_]+$', name_lower):
            return name_lower[:50]
        
        result = name_lower
        for cn, en in CHINESE_KEYWORD_MAP.items():
            result = result.replace(cn, en)
        
        # 移除非字母数字和连字符的字符
        result = re.sub(r'[^\w\-]', '', result)
        result = re.sub(r'-+', '-', result)
        
        return result.strip('-')[:50]
    
    def _clean_name(self, name: str) -> str:
        """清理节点名称"""
        if not name:
            return ""
        cleaned = re.sub(r'[^a-z0-9\-_]', '', name.lower())
        cleaned = cleaned.strip('-_')
        return cleaned[:50]
    
    def _infer_edges(self, nodes: List[Dict], text: str) -> List[Dict]:
        """从对话中推断边关系"""
        edges = []
        tasks = [n for n in nodes if n["type"] == "TASK"]
        skills = [n for n in nodes if n["type"] == "SKILL"]
        events = [n for n in nodes if n["type"] == "EVENT"]
        
        text_lower = text.lower()
        
        # TASK 使用 SKILL
        for task in tasks:
            for skill in skills:
                skill_cmd = skill.get("name", "").split("-")[0] if "-" in skill.get("name", "") else skill.get("name", "")
                if skill_cmd in text_lower or skill.get("name", "") in text_lower:
                    edges.append({
                        "from_id": task.get("id", task.get("name")),
                        "to_id": skill.get("id", skill.get("name")),
                        "type": "USED_SKILL"
                    })
        
        # EVENT 被 SKILL 解决
        for event in events:
            for skill in skills:
                if skill.get("name", "") in text_lower:
                    edges.append({
                        "from_id": event.get("id", event.get("name")),
                        "to_id": skill.get("id", skill.get("name")),
                        "type": "SOLVED_BY"
                    })
        
        return edges
    
    def _parse_json_response(self, response: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 返回的 JSON 响应"""
        if not response:
            return None
        
        # 方法1：从响应中提取 ```json 代码块
        match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        
        # 方法2：清理 markdown
        cleaned = re.sub(r"^```json\s*", "", response.strip())
        cleaned = re.sub(r"\s*```$", "", cleaned)
        
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass
        
        # 方法3：从 "nodes" 或 "edges" 关键词位置往前找 {
        for keyword in ['"nodes"', '"edges"', '"type"', '"name"']:
            pos = response.find(keyword)
            if pos >= 0:
                start = response.rfind('{', 0, pos + len(keyword))
                if start >= 0:
                    # 计数括号找完整的 JSON 对象
                    bracket_count = 0
                    end = len(response)
                    for i in range(start, len(response)):
                        if response[i] == '{':
                            bracket_count += 1
                        elif response[i] == '}':
                            bracket_count -= 1
                            if bracket_count == 0:
                                end = i + 1
                                break
                    
                    candidate = response[start:end]
                    try:
                        data = json.loads(candidate)
                        # 验证是有效的知识图谱结构
                        if "nodes" in data or "edges" in data:
                            return data
                    except json.JSONDecodeError:
                        pass
        
        # 方法4：暴力查找最后一个完整的 { }
        start = response.rfind('{')
        end = response.rfind('}') + 1
        if start >= 0 and end > start:
            candidate = response[start:end]
            try:
                return json.loads(candidate)
            except:
                pass
        
        return None
    
    def _extract_from_conversation(self, text: str) -> Optional[Dict[str, Any]]:
        """直接从对话文本中提取知识（规则方法，LLM 失败时的 fallback）"""
        nodes = []
        edges = []
        text_lower = text.lower()
        
        # TASK 模式：从用户请求中提取（中文）
        # "帮我安装 X" -> TASK: install-x
        for task_match in re.finditer(r'帮我(?:安装|运行|创建|下载|设置|编译)(?:一个)?\s*([^\s\n,，。]+)', text_lower):
            name = task_match.group(1).strip()
            name = self._transliterate_name(name)
            name = self._clean_name(name)
            if name and len(name) >= 2 and name[0].isalnum() and not any(n.get('name') == name for n in nodes):
                nodes.append({
                    "type": "TASK",
                    "name": name,
                    "description": f"User requested: {name}",
                    "content": f"{name}\nGoal: {name}\nSteps:\n1. (to be filled)\nResult: pending"
                })
        
        # TASK 模式：中文 "X 视频/工具/软件"
        for task_match in re.finditer(r'([a-z0-9]+(?:[- ][a-z0-9]+)*)\s*(?:视频|工具|软件|应用|项目)', text_lower):
            name = task_match.group(1).strip().replace(' ', '-')
            name = self._clean_name(name)
            if name and len(name) >= 2 and not any(n.get('name') == name for n in nodes):
                nodes.append({
                    "type": "TASK",
                    "name": name,
                    "description": f"Task: {name}",
                    "content": f"{name}\nGoal: {name}\nSteps:\n1. (to be filled)\nResult: pending"
                })
        
        # TASK 模式：英文
        for task_match in re.finditer(r'(?:install|setup|build|deploy|create|run|download|configure)\s+([a-z0-9\-_]+)', text_lower):
            name = task_match.group(1).strip()
            name = self._clean_name(name)
            if len(name) >= 2 and name[0].isalnum() and not any(n.get('name') == name for n in nodes):
                nodes.append({
                    "type": "TASK",
                    "name": name,
                    "description": f"Task: {name}",
                    "content": f"{name}\nGoal: {name}\nSteps:\n1. (to be filled)\nResult: pending"
                })
        
        # SKILL 模式：从命令中提取
        skill_patterns = [
            (r'pip\s+install\s+([^\s\n]+)', 'pip install'),
            (r'apt\s+install\s+([^\s\n]+)', 'apt install'),
            (r'npm\s+install\s*([^\s\n]*)?', 'npm install'),
            (r'yarn\s+add\s+([^\s\n]+)', 'yarn add'),
            (r'docker\s+(run|build|pull|exec)\s*([^\s\n]+)?', 'docker'),
            (r'git\s+clone\s+([^\s\n]+)', 'git clone'),
            (r'curl\s+([^\s\n]+)', 'curl'),
            (r'youtube-dl\s+([^\s\n]+)', 'youtube-dl'),
            (r'yt-dlp\s*([^\s\n]*)?', 'yt-dlp'),
            (r'wget\s+([^\s\n]+)', 'wget'),
        ]
        
        for pattern, cmd_type in skill_patterns:
            for match in re.finditer(pattern, text_lower):
                if match.lastindex and match.lastindex >= 1:
                    name = match.group(match.lastindex).strip()
                    name = name.replace('.', '-').replace('_', '-').replace('/', '-')
                    name = re.sub(r'[^a-z0-9\-]', '', name)
                else:
                    name = cmd_type.replace(' ', '-')
                
                if len(name) >= 2 and name[0].isalnum() and not any(n.get('name') == name for n in nodes):
                    desc = f"使用 {cmd_type}" if name == cmd_type.replace(' ', '-') else f"使用 {cmd_type} {name}"
                    nodes.append({
                        "type": "SKILL",
                        "name": name,
                        "description": desc[:100],
                        "content": f"{name}\nTrigger: 需要使用{name}\nSteps:\n1. {cmd_type} {name}\nCommon errors:\n- permission denied -> sudo"
                    })
        
        # EVENT 模式：常见错误
        error_patterns = [
            r'importerror',
            r'import error',
            r'module not found',
            r'no module',
            r'connection refused',
            r'connection timeout',
            r'permission denied',
            r'command not found',
            r'file not found',
        ]
        
        for pattern in error_patterns:
            for match in re.finditer(pattern, text_lower):
                name = match.group(0).replace(' ', '-')[:50]
                if name and not any(n.get('name') == name for n in nodes):
                    nodes.append({
                        "type": "EVENT",
                        "name": name,
                        "description": match.group(0),
                        "content": f"{name}\nError: {match.group(0)}\nSolution: (to be determined)"
                    })
        
        # 推断边
        if nodes:
            edges = self._infer_edges(nodes, text)
        
        if nodes:
            return {"nodes": nodes, "edges": edges}
        
        return None
    
    def _validate_node(self, node: Dict) -> bool:
        """验证节点"""
        if not isinstance(node, dict):
            return False
        required = ("type", "name")
        if not all(k in node for k in required):
            return False
        if node["type"] not in VALID_NODE_TYPES:
            return False
        name = node.get("name", "")
        if not name or len(str(name)) < 2:
            return False
        return True
    
    def _validate_edge(self, edge: Dict) -> bool:
        """验证边"""
        if not isinstance(edge, dict):
            return False
        edge_type = edge.get("type") or edge.get("relation") or ""
        from_id = edge.get("from_id") or edge.get("from") or edge.get("source") or ""
        to_id = edge.get("to_id") or edge.get("to") or edge.get("target") or ""
        
        if not all([edge_type, from_id, to_id]):
            return False
        
        # 检查边类型别名
        if edge_type not in VALID_EDGE_TYPES:
            if edge_type not in EDGE_TYPE_ALIASES:
                return False
        
        return True
