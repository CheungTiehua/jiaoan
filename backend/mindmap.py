"""
LeKai 双思维导图生成 — 教案导图 + 备课方法导图

教案导图: 回答"这节课怎么上"
备课方法导图: 回答"老师以后怎么自己备课"（授之以渔）
"""

import json
import os
import re


# ============================================================
# Prompt
# ============================================================

MINDMAP_SYSTEM = """你是一位资深小学语文教研员，擅长将教学内容和备课方法论提炼为结构化思维导图。

你的任务是：根据提供的教案内容和辅导说明，生成两张思维导图的 JSON 结构数据。

你必须输出严格 JSON 格式，不要输出任何其他内容。不要用 markdown 代码块包裹。"""

MINDMAP_USER = """## 教案内容
{lesson_plan}

## 教案辅导说明
{teaching_guide}

## 考点分析
{analysis}

## 同行参考
{peer_reference}

---

请生成以下 JSON（注意：children 为数组，每个元素必须有 title 和 children）：

```json
{{
  "lesson_outline": {{
    "title": "《{lesson}》教案导图",
    "nodes": [
      {{
        "title": "教学目标",
        "children": [
          {{"title": "具体目标1", "children": []}},
          {{"title": "具体目标2", "children": []}}
        ]
      }},
      {{
        "title": "教学重点",
        "children": [
          {{"title": "重点1", "children": []}},
          {{"title": "重点2", "children": []}}
        ]
      }},
      {{
        "title": "教学难点",
        "children": [
          {{"title": "难点1", "children": []}},
          {{"title": "难点2", "children": []}}
        ]
      }},
      {{
        "title": "教学流程",
        "children": [
          {{"title": "环节1", "children": [
            {{"title": "关键问题", "children": []}},
            {{"title": "学生活动", "children": []}}
          ]}}
        ]
      }},
      {{
        "title": "板书设计",
        "children": [
          {{"title": "板书要点", "children": []}}
        ]
      }},
      {{
        "title": "作业与拓展",
        "children": [
          {{"title": "作业内容", "children": []}}
        ]
      }}
    ]
  }},
  "method_outline": {{
    "title": "《{lesson}》备课方法导图",
    "nodes": [
      {{
        "title": "备课起点",
        "children": [
          {{"title": "具体做法1", "children": []}},
          {{"title": "具体做法2", "children": []}}
        ]
      }},
      {{
        "title": "目标提炼方法",
        "children": [
          {{"title": "方法1", "children": []}},
          {{"title": "方法2", "children": []}}
        ]
      }},
      {{
        "title": "重难点判断方法",
        "children": [
          {{"title": "判断依据", "children": []}}
        ]
      }},
      {{
        "title": "教学流程设计方法",
        "children": [
          {{"title": "设计原则", "children": []}}
        ]
      }},
      {{
        "title": "提问设计方法",
        "children": [
          {{"title": "设计技巧", "children": []}}
        ]
      }},
      {{
        "title": "活动设计方法",
        "children": [
          {{"title": "设计思路", "children": []}}
        ]
      }},
      {{
        "title": "板书设计方法",
        "children": [
          {{"title": "板书原则", "children": []}}
        ]
      }},
      {{
        "title": "可迁移经验",
        "children": [
          {{"title": "通用技巧", "children": []}}
        ]
      }},
      {{
        "title": "常见误区",
        "children": [
          {{"title": "易错点", "children": []}}
        ]
      }}
    ]
  }}
}}
```

要求：
1. 教案导图必须紧贴当前教案内容，不要泛泛而谈。
2. 备课方法导图要提炼"方法论"，不能简单重复教案内容。要体现：从教材/课标/习题反推目标、从学生经验判断重难点、流程设计通用方法、提问/活动/板书设计方法、可迁移到其他课文备课的经验、常见误区。
3. 所有节点文字简洁（10字以内），层级不超过4层。
4. 只输出 JSON，不要输出任何解释文字。"""


# ============================================================
# 校验
# ============================================================

LESSON_KEYWORDS = ["教学目标", "教学重点", "教学难点", "教学流程", "关键问题", "板书", "作业"]
METHOD_KEYWORDS = ["方法", "备课", "目标提炼", "重难点", "提问设计", "活动设计", "可迁移", "常见误区"]


def validate_lesson_mindmap(mermaid: str) -> bool:
    """教案导图至少包含 7 个关键词中的 3 个"""
    hits = sum(1 for kw in LESSON_KEYWORDS if kw in mermaid)
    return hits >= 3


def validate_method_mindmap(mermaid: str) -> bool:
    """备课方法导图至少包含 8 个关键词中的 3 个"""
    hits = sum(1 for kw in METHOD_KEYWORDS if kw in mermaid)
    return hits >= 3


# ============================================================
# JSON → Mermaid 转换
# ============================================================

def _clean_node(text: str) -> str:
    """清理节点文字，移除可能破坏 Mermaid 语法的字符"""
    t = text.strip()
    t = t.replace("\n", "").replace("\r", "")
    t = t.replace("(", "（").replace(")", "）")
    t = t.replace("[", "").replace("]", "")
    t = t.replace(":", "：")
    t = t.replace('"', "").replace("'", "")
    if len(t) > 20:
        t = t[:18] + ".."
    return t


def _render_nodes(nodes: list[dict], depth: int, max_depth: int = 4) -> list[str]:
    """递归渲染节点列表为 Mermaid 行"""
    lines = []
    if depth > max_depth:
        return lines
    indent = "  " * depth
    for node in nodes:
        title = _clean_node(node.get("title", ""))
        if not title:
            continue
        lines.append(f"{indent}{title}")
        children = node.get("children", [])
        if children:
            lines.extend(_render_nodes(children, depth + 1, max_depth))
    return lines


def outline_to_mermaid(outline: dict) -> str:
    """将结构化 outline 转为 Mermaid mindmap 字符串"""
    title = _clean_node(outline.get("title", "思维导图"))
    lines = ["mindmap", f"  root(({title}))"]
    nodes = outline.get("nodes", [])
    lines.extend(_render_nodes(nodes, depth=2))
    return "\n".join(lines)


# ============================================================
# JSON 解析
# ============================================================

def _extract_json(text: str) -> str:
    """从文本中提取 JSON 内容（处理模型多余输出）"""
    text = text.strip()
    if text.startswith("{"):
        # 找到最后一个 } 之后裁掉尾部多余文本
        last_brace = text.rfind("}")
        if last_brace != -1:
            text = text[:last_brace + 1]
        return text
    # 尝试提取 JSON 块
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        return m.group(0)
    return text


def parse_mindmap_json(text: str) -> dict:
    """解析 DeepSeek 返回的 JSON"""
    text = _extract_json(text)
    return json.loads(text)


# ============================================================
# 主生成函数
# ============================================================

def _build_user_prompt(req) -> str:
    return MINDMAP_USER.format(
        lesson=req.lesson,
        lesson_plan=req.lesson_plan,
        teaching_guide=req.teaching_guide or "",
        analysis=req.analysis or "",
        peer_reference=req.peer_reference or "",
    )


def _first_lines(text: str, limit: int = 3) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip(" -\t\r\n")
        if not line or line.startswith("#"):
            continue
        line = re.sub(r'^\d+[.、]\s*', '', line)
        if line:
            lines.append(line[:18])
        if len(lines) >= limit:
            break
    return lines


def _section_text(text: str, names: list[str]) -> str:
    for name in names:
        pattern = rf'(?:^|\n)#+\s*(?:[一二三四五六七八九十]+[、.．]?\s*)?{re.escape(name)}\s*\n([\s\S]*?)(?=\n#+\s|\Z)'
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return ""


def _children_from_text(text: str, fallback: list[str], limit: int = 3) -> list[dict]:
    titles = _first_lines(text, limit=limit) or fallback[:limit]
    return [{"title": title, "children": []} for title in titles]


def _fallback_mindmap(req) -> dict:
    lesson_plan = req.lesson_plan or ""
    teaching_guide = req.teaching_guide or ""

    target_text = _section_text(lesson_plan, ["教学目标"])
    key_text = _section_text(lesson_plan, ["教学重难点", "教学重点"])
    process_text = _section_text(lesson_plan, ["教学过程"])
    board_text = _section_text(lesson_plan, ["板书设计"])
    homework_text = _section_text(lesson_plan, ["作业布置", "作业与拓展"])
    guide_text = teaching_guide[:1500]

    lesson_outline = {
        "title": f"《{req.lesson}》教案导图",
        "nodes": [
            {"title": "教学目标", "children": _children_from_text(target_text, ["知识能力", "过程方法", "情感态度"])},
            {"title": "教学重点", "children": _children_from_text(key_text, ["品读语言", "理解结构", "朗读积累"], 2)},
            {"title": "教学难点", "children": _children_from_text(key_text, ["读写迁移", "方法运用"], 2)},
            {"title": "教学流程", "children": _children_from_text(process_text, ["导入新课", "初读感知", "精读品味", "拓展练习"], 4)},
            {"title": "板书设计", "children": _children_from_text(board_text, ["结构清晰", "突出重点"], 2)},
            {"title": "作业与拓展", "children": _children_from_text(homework_text, ["基础巩固", "拓展表达"], 2)},
        ],
    }
    method_outline = {
        "title": f"《{req.lesson}》备课方法导图",
        "nodes": [
            {"title": "备课起点", "children": [{"title": "研读教材", "children": []}, {"title": "分析学情", "children": []}]},
            {"title": "目标提炼方法", "children": _children_from_text(target_text or guide_text, ["扣课标", "扣单元", "扣课后题"], 3)},
            {"title": "重难点判断方法", "children": _children_from_text(key_text or guide_text, ["看学生基础", "看文本价值"], 2)},
            {"title": "教学流程设计方法", "children": _children_from_text(process_text or guide_text, ["情境导入", "任务推进", "当堂反馈"], 3)},
            {"title": "提问设计方法", "children": [{"title": "由浅入深", "children": []}, {"title": "指向表达", "children": []}]},
            {"title": "活动设计方法", "children": [{"title": "朗读品味", "children": []}, {"title": "读写结合", "children": []}]},
            {"title": "板书设计方法", "children": [{"title": "抓关键词", "children": []}, {"title": "显结构", "children": []}]},
            {"title": "可迁移经验", "children": [{"title": "结构支架", "children": []}, {"title": "语言积累", "children": []}]},
            {"title": "常见误区", "children": [{"title": "目标泛化", "children": []}, {"title": "活动散乱", "children": []}]},
        ],
    }
    return {
        "lesson_mindmap_mermaid": outline_to_mermaid(lesson_outline),
        "method_mindmap_mermaid": outline_to_mermaid(method_outline),
        "lesson_outline": lesson_outline,
        "method_outline": method_outline,
    }


def generate_dual_mindmap(req) -> dict:
    """生成双思维导图，返回 {lesson_mindmap_mermaid, method_mindmap_mermaid, lesson_outline, method_outline}"""
    if os.environ.get("LEKAI_MINDMAP_AI", "0") != "1":
        return _fallback_mindmap(req)

    from rag import call_deepseek

    user_prompt = _build_user_prompt(req)

    try:
        raw = call_deepseek(MINDMAP_SYSTEM, user_prompt, temperature=0.3)
        data = parse_mindmap_json(raw)
    except Exception:
        return _fallback_mindmap(req)

    lesson_outline = data.get("lesson_outline", {})
    method_outline = data.get("method_outline", {})

    lesson_mermaid = outline_to_mermaid(lesson_outline)
    method_mermaid = outline_to_mermaid(method_outline)

    # 质量校验
    lesson_ok = validate_lesson_mindmap(lesson_mermaid)
    method_ok = validate_method_mindmap(method_mermaid)

    if not (lesson_ok and method_ok):
        # 自动重试一次
        try:
            raw2 = call_deepseek(MINDMAP_SYSTEM, user_prompt, temperature=0.5)
            data2 = parse_mindmap_json(raw2)
        except Exception:
            return _fallback_mindmap(req)
        lesson_outline2 = data2.get("lesson_outline", {})
        method_outline2 = data2.get("method_outline", {})
        lesson_mermaid2 = outline_to_mermaid(lesson_outline2)
        method_mermaid2 = outline_to_mermaid(method_outline2)

        lesson_ok2 = validate_lesson_mindmap(lesson_mermaid2)
        method_ok2 = validate_method_mindmap(method_mermaid2)

        if not (lesson_ok2 and method_ok2):
            return _fallback_mindmap(req)

        return {
            "lesson_mindmap_mermaid": lesson_mermaid2,
            "method_mindmap_mermaid": method_mermaid2,
            "lesson_outline": lesson_outline2,
            "method_outline": method_outline2,
        }

    return {
        "lesson_mindmap_mermaid": lesson_mermaid,
        "method_mindmap_mermaid": method_mermaid,
        "lesson_outline": lesson_outline,
        "method_outline": method_outline,
    }
