"""LeKai RAG Pipeline — 检索 + 生成"""

import sys
from pathlib import Path

import chromadb
import requests

# 确保可以 import 同目录模块
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    CHROMA_DIR, CHROMA_COLLECTION,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    RETRIEVAL_TOP_K, MAX_CONTEXT_LENGTH
)
from prompts import (
    LESSON_PLAN_SYSTEM, LESSON_PLAN_USER,
    TEACHING_GUIDE_SYSTEM, TEACHING_GUIDE_USER
)

# 懒加载
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


# ============================================================
# 检索
# ============================================================

def retrieve(query: str, grade: str | None = None, top_k: int = RETRIEVAL_TOP_K) -> str:
    """检索相关教案 chunk，返回拼接后的上下文字符串"""
    model = get_embedding_model()
    collection = get_collection()

    if collection.count() == 0:
        return "（知识库为空，请先导入教案）"

    # 生成查询向量
    query_embedding = model.encode(
        [query], normalize_embeddings=True, show_progress_bar=False
    )[0].tolist()

    # 检索
    where_filter = None
    if grade:
        where_filter = {"grade": grade}

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        where=where_filter,
        include=["documents", "metadatas", "distances"]
    )

    # 拼接上下文
    seen_lessons = set()
    context_parts = []

    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        lesson_key = meta.get("lesson", "")
        chunk_type = meta.get("chunk_type", "")

        # 优先保留完整教案，去重
        if lesson_key and lesson_key not in seen_lessons and chunk_type == "overview":
            seen_lessons.add(lesson_key)

        text = doc[:1500]  # 每个 chunk 截断
        header = f"【参考教案：《{lesson_key}》- {chunk_type}】"
        context_parts.append(f"{header}\n{text}")

        if sum(len(p) for p in context_parts) > MAX_CONTEXT_LENGTH:
            break

    context = "\n\n---\n\n".join(context_parts)
    return context


# ============================================================
# LLM 调用
# ============================================================

def call_deepseek(system_prompt: str, user_prompt: str, temperature: float = 0.3) -> str:
    """调用 DeepSeek API"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("请设置环境变量 DEEPSEEK_API_KEY")

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": 4096
    }

    resp = requests.post(
        f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=180
    )
    resp.raise_for_status()
    result = resp.json()
    return result["choices"][0]["message"]["content"]


# ============================================================
# 生成 Pipeline
# ============================================================

def generate_lesson(
    grade: str,
    lesson: str,
    requirements: str = "",
    class_hours: str = "2",
    semester: str = "上"
) -> dict:
    """
    主入口：检索 → 生成教案 → 生成辅导说明

    返回: {
        "lesson_plan": str,        # 教案 Markdown
        "teaching_guide": str,     # 辅导说明 Markdown
        "references": list[str],   # 引用的参考教案
    }
    """
    # 1. 检索相关教案
    search_query = f"{grade} {semester}学期 《{lesson}》{requirements}"
    context = retrieve(search_query, grade=grade)

    # 2. 生成教案
    user_prompt = LESSON_PLAN_USER.format(
        context=context,
        grade=grade,
        lesson=lesson,
        class_hours=class_hours,
        requirements=requirements or "无特殊要求"
    )
    lesson_plan = call_deepseek(LESSON_PLAN_SYSTEM, user_prompt)

    # 3. 生成辅导说明
    guide_prompt = TEACHING_GUIDE_USER.format(
        lesson_plan=lesson_plan,
        context=context,
        lesson=lesson
    )
    teaching_guide = call_deepseek(TEACHING_GUIDE_SYSTEM, guide_prompt)

    return {
        "lesson_plan": lesson_plan,
        "teaching_guide": teaching_guide,
        "references": []  # TODO: 从 context 中提取
    }
