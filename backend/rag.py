"""LeKai RAG Pipeline v0.2 — 四层输出：考点 + 同行 + 教案 + 辅导"""

import sys
from pathlib import Path

import chromadb
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CHROMA_DIR, CHROMA_COLLECTION,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    RETRIEVAL_TOP_K, MAX_CONTEXT_LENGTH
)
from prompts import (
    EXAM_ANALYSIS_SYSTEM, EXAM_ANALYSIS_USER,
    PEER_ANALYSIS_SYSTEM, PEER_ANALYSIS_USER,
    LESSON_PLAN_SYSTEM, LESSON_PLAN_USER,
    TEACHING_GUIDE_SYSTEM, TEACHING_GUIDE_USER,
    REVISE_SYSTEM, REVISE_USER,
)

_embedding_model = None
_chroma_collection = None


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        project_root = Path(__file__).resolve().parent.parent
        cache = str(project_root / ".cache" / "models")
        _embedding_model = SentenceTransformer("BAAI/bge-small-zh-v1.5", cache_folder=cache)
    return _embedding_model


def get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _chroma_collection = client.get_or_create_collection(name=CHROMA_COLLECTION)
    return _chroma_collection


def retrieve(query: str, grade: str | None = None, top_k: int = RETRIEVAL_TOP_K) -> str:
    model = get_embedding_model()
    collection = get_collection()
    if collection.count() == 0:
        return "（知识库为空）"

    query_embedding = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0].tolist()
    where_filter = {"grade": grade} if grade else None
    results = collection.query(
        query_embeddings=[query_embedding], n_results=top_k,
        where=where_filter, include=["documents", "metadatas", "distances"]
    )

    seen = set()
    parts = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        key = meta.get("lesson", "")
        if key and key not in seen and meta.get("chunk_type") == "overview":
            seen.add(key)
        parts.append(f"【{meta.get('lesson', '')} - {meta.get('chunk_type', '')}】\n{doc[:1200]}")
        if sum(len(p) for p in parts) > MAX_CONTEXT_LENGTH:
            break
    return "\n\n---\n\n".join(parts)


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


# ============================================================
# 生成 Pipeline（增强版）
# ============================================================

def generate_lesson(
    grade: str, lesson: str,
    requirements: str = "", class_hours: str = "2", semester: str = "上"
) -> dict:
    """四步生成：考点分析 → 同行参考 → 教案 → 辅导说明"""

    # 0. 检索知识库
    search_query = f"{grade} {semester}学期 《{lesson}》{requirements}"
    context = retrieve(search_query, grade=grade)

    # 1. 考点分析
    exam_prompt = EXAM_ANALYSIS_USER.format(grade=grade, lesson=lesson, semester=semester)
    exam_analysis = call_deepseek(EXAM_ANALYSIS_SYSTEM, exam_prompt, temperature=0.2)

    # 2. 同行参考
    peer_prompt = PEER_ANALYSIS_USER.format(grade=grade, lesson=lesson, semester=semester, context=context)
    peer_analysis = call_deepseek(PEER_ANALYSIS_SYSTEM, peer_prompt, temperature=0.3)

    # 3. 教案生成
    plan_prompt = LESSON_PLAN_USER.format(
        exam_analysis=exam_analysis, peer_analysis=peer_analysis,
        context=context, grade=grade, lesson=lesson,
        class_hours=class_hours, requirements=requirements or "无特殊要求"
    )
    lesson_plan = call_deepseek(LESSON_PLAN_SYSTEM, plan_prompt)

    # 4. 辅导说明
    guide_prompt = TEACHING_GUIDE_USER.format(
        lesson_plan=lesson_plan, exam_analysis=exam_analysis, peer_analysis=peer_analysis, lesson=lesson
    )
    teaching_guide = call_deepseek(TEACHING_GUIDE_SYSTEM, guide_prompt)

    return {
        "exam_analysis": exam_analysis,
        "peer_analysis": peer_analysis,
        "lesson_plan": lesson_plan,
        "teaching_guide": teaching_guide,
    }


# ============================================================
# 对话修改
# ============================================================

def revise_lesson(current_plan: str, revision_request: str, history: str = "") -> str:
    """对话式修改教案"""
    prompt = REVISE_USER.format(
        current_plan=current_plan,
        revision_request=revision_request,
        conversation_history=history or "（首次修改）"
    )
    return call_deepseek(REVISE_SYSTEM, prompt, temperature=0.3)
