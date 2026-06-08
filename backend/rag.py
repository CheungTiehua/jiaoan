"""LeKai RAG Pipeline v0.3 — 混合检索 + Evidence Pack + 结构化同行参考"""

import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    RETRIEVAL_TOP_K
)
from prompts import (
    EXAM_ANALYSIS_SYSTEM, EXAM_ANALYSIS_USER,
    PEER_ANALYSIS_STRUCTURED_SYSTEM, PEER_ANALYSIS_STRUCTURED_USER,
    LESSON_PLAN_SYSTEM, LESSON_PLAN_USER,
    TEACHING_GUIDE_SYSTEM, TEACHING_GUIDE_USER,
    REVISE_SYSTEM, REVISE_USER,
    UNIT_PLAN_SYSTEM, UNIT_PLAN_USER,
    REFLECTION_SYSTEM, REFLECTION_USER,
)
from search_engine import search_hybrid, refresh_index
from lesson_evidence import build_lesson_evidence, format_lesson_evidence


def call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("请设置 DEEPSEEK_API_KEY")
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {"model": DEEPSEEK_MODEL, "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], "temperature": temperature, "max_tokens": 4096}
    resp = requests.post(f"{DEEPSEEK_BASE_URL}/v1/chat/completions", headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def retrieve_structured(query: str, grade: str | None = None,
                        top_k: int = RETRIEVAL_TOP_K) -> tuple[str, dict]:
    """
    混合检索 + Evidence Pack 分层

    返回: (formatted_context, evidence_pack_dict)
    """
    results = search_hybrid(query, grade=grade, top_k=top_k * 2)
    pack = build_lesson_evidence(results, top_k_per_dim=3)
    context = format_lesson_evidence(pack)
    return context, pack


# ============================================================
# 生成 Pipeline（增强版）
# ============================================================

def generate_lesson(
    grade: str, lesson: str,
    requirements: str = "", class_hours: str = "2", semester: str = "上"
) -> dict:
    """Step 1: 考点分析 → Step 2: 结构化同行参考 → Step 3: 教案 → Step 4: 辅导说明"""

    # 0. 混合检索 + Evidence Pack
    search_query = f"{grade} {semester}学期 《{lesson}》{requirements}"
    context, evidence_pack = retrieve_structured(search_query, grade=grade)

    # 1. 考点分析
    exam_prompt = EXAM_ANALYSIS_USER.format(grade=grade, lesson=lesson, semester=semester)
    exam_analysis = call_deepseek(EXAM_ANALYSIS_SYSTEM, exam_prompt, temperature=0.2)

    # 2. 结构化同行参考
    peer_prompt = PEER_ANALYSIS_STRUCTURED_USER.format(
        grade=grade, lesson=lesson, semester=semester, context=context
    )
    peer_analysis = call_deepseek(PEER_ANALYSIS_STRUCTURED_SYSTEM, peer_prompt, temperature=0.3)

    # 3. 教案生成
    plan_prompt = LESSON_PLAN_USER.format(
        exam_analysis=exam_analysis, peer_analysis=peer_analysis,
        context=context, grade=grade, lesson=lesson,
        class_hours=class_hours, requirements=requirements or "无特殊要求"
    )
    lesson_plan = call_deepseek(LESSON_PLAN_SYSTEM, plan_prompt)

    # 4. 辅导说明
    guide_prompt = TEACHING_GUIDE_USER.format(
        lesson_plan=lesson_plan, exam_analysis=exam_analysis,
        peer_analysis=peer_analysis, lesson=lesson
    )
    teaching_guide = call_deepseek(TEACHING_GUIDE_SYSTEM, guide_prompt)

    return {
        "exam_analysis": exam_analysis,
        "peer_analysis": peer_analysis,
        "lesson_plan": lesson_plan,
        "teaching_guide": teaching_guide,
    }


def generate_unit_plan(grade: str, unit: str, semester: str = "上") -> str:
    """生成单元整体规划"""
    context, _ = retrieve_structured(f"{grade} {semester}册 {unit}", grade=grade)
    prompt = UNIT_PLAN_USER.format(grade=grade, semester=semester, unit=unit, context=context)
    return call_deepseek(UNIT_PLAN_SYSTEM, prompt, temperature=0.3)


def generate_reflection(lesson: str, lesson_plan: str) -> str:
    """生成课后反思引导"""
    prompt = REFLECTION_USER.format(lesson=lesson, lesson_plan=lesson_plan)
    return call_deepseek(REFLECTION_SYSTEM, prompt, temperature=0.4)


def revise_lesson(current_plan: str, revision_request: str, history: str = "") -> str:
    prompt = REVISE_USER.format(
        current_plan=current_plan, revision_request=revision_request,
        conversation_history=history or "（首次修改）"
    )
    return call_deepseek(REVISE_SYSTEM, prompt, temperature=0.3)
