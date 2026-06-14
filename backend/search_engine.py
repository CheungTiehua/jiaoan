"""
混合检索引擎 — BM25(jieba分词) + ChromaDB向量 + RRF融合

借鉴 zhishiku 的四路混合检索方案，适配教案知识库场景。
"""

import os
from pathlib import Path
from typing import Optional

import chromadb
import jieba
from rank_bm25 import BM25Okapi

# 懒加载
_embedding_model = None
_chroma_collection = None
_bm25_corpus: Optional[dict] = None  # {doc_id: tokenized_text}

MODEL_NAME = "BAAI/bge-small-zh-v1.5"


def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        project_root = Path(__file__).resolve().parent.parent

        # 按优先级尝试本地模型目录: LEKAI_MODEL_DIR > 默认 .cache/models/bge-small-zh-v1.5
        candidate_dirs = []

        env_model_dir = os.environ.get("LEKAI_MODEL_DIR", "")
        if env_model_dir:
            candidate_dirs.append(Path(env_model_dir))

        candidate_dirs.append(project_root / ".cache" / "models" / "bge-small-zh-v1.5")

        for model_dir in candidate_dirs:
            if model_dir.exists():
                try:
                    _embedding_model = SentenceTransformer(str(model_dir))
                    return _embedding_model
                except Exception as e:
                    import sys
                    print(f"[search_engine] 本地模型加载失败 ({model_dir}): {e}", file=sys.stderr)

        # 本地无模型，尝试在线下载
        try:
            _embedding_model = SentenceTransformer(
                MODEL_NAME,
                cache_folder=str(project_root / ".cache" / "models")
            )
        except Exception as e:
            raise RuntimeError(
                f"Embedding 模型加载失败，请检查 LEKAI_MODEL_DIR 或网络连接: {e}"
            ) from e

    return _embedding_model


def get_collection():
    global _chroma_collection
    if _chroma_collection is None:
        from config import CHROMA_DIR, CHROMA_COLLECTION
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _chroma_collection = client.get_or_create_collection(name=CHROMA_COLLECTION)
    return _chroma_collection


def _tokenize(text: str) -> list[str]:
    """jieba 分词"""
    return [w.strip() for w in jieba.cut(text) if w.strip()]


def _build_bm25():
    """从 ChromaDB 构建 BM25 索引"""
    global _bm25_corpus
    collection = get_collection()
    if collection.count() == 0:
        _bm25_corpus = None
        return

    results = collection.get(include=["documents", "metadatas"])
    if not results or not results.get("ids"):
        _bm25_corpus = None
        return

    tokenized = []
    id_map = {}
    for i, (cid, doc) in enumerate(zip(results["ids"], results["documents"])):
        tokens = _tokenize(doc or "")
        tokenized.append(tokens)
        id_map[i] = cid

    _bm25_corpus = {
        "bm25": BM25Okapi(tokenized),
        "id_map": id_map,
        "ids": results["ids"],
        "metadatas": results["metadatas"] or [],
        "documents": results["documents"] or [],
    }


def _ensure_bm25():
    if _bm25_corpus is None or _bm25_corpus.get("bm25") is None:
        _build_bm25()


# ============================================================
# 混合检索
# ============================================================

def search_hybrid(
    query: str,
    grade: Optional[str] = None,
    top_k: int = 10,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> list[dict]:
    """
    BM25 + 向量 + RRF 融合检索

    返回: [{"text": str, "meta": dict, "score": float}, ...]
    """
    collection = get_collection()
    if collection.count() == 0:
        return []

    _ensure_bm25()

    # 1. 向量检索 (top_k * 2, 给融合留余量)
    model = get_embedding_model()
    query_vec = model.encode([query], normalize_embeddings=True, show_progress_bar=False)[0].tolist()
    where = {"grade": grade} if grade else None

    vec_results = collection.query(
        query_embeddings=[query_vec], n_results=top_k * 3,
        where=where, include=["documents", "metadatas", "distances"]
    )

    # 2. BM25 检索
    bm25_scores = {}
    if _bm25_corpus and _bm25_corpus.get("bm25"):
        bm25 = _bm25_corpus["bm25"]
        tokenized_query = _tokenize(query)
        scores = bm25.get_scores(tokenized_query)
        for i, score in enumerate(scores):
            if i in _bm25_corpus["id_map"]:
                meta = _bm25_corpus["metadatas"][i] if i < len(_bm25_corpus.get("metadatas", [])) else {}
                if grade and meta.get("grade") != grade:
                    continue
                cid = _bm25_corpus["id_map"][i]
                bm25_scores[cid] = float(score)

    # 3. RRF 融合
    vec_rank = {}
    if vec_results and vec_results.get("ids") and vec_results["ids"][0]:
        for rank, cid in enumerate(vec_results["ids"][0]):
            vec_rank[cid] = 1.0 / (60 + rank + 1)

    bm25_rank = {}
    if bm25_scores:
        sorted_bm25 = sorted(bm25_scores.items(), key=lambda x: x[1], reverse=True)
        for rank, (cid, _) in enumerate(sorted_bm25):
            bm25_rank[cid] = 1.0 / (60 + rank + 1)

    # 合并分数
    all_ids = set(list(vec_rank.keys()) + list(bm25_rank.keys()))
    fused = {}
    for cid in all_ids:
        v = vec_rank.get(cid, 0.0)
        b = bm25_rank.get(cid, 0.0)
        fused[cid] = vector_weight * v + bm25_weight * b

    sorted_fused = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]

    # 4. 组装结果
    results = []
    for cid, score in sorted_fused:
        # 从 ChromaDB 或 BM25 元数据中查找
        text = ""
        meta = {}
        if vec_results and vec_results.get("ids"):
            for i, vid in enumerate(vec_results["ids"][0]):
                if vid == cid:
                    text = (vec_results["documents"][0][i]
                            if vec_results.get("documents") else "")
                    meta = (vec_results["metadatas"][0][i]
                            if vec_results.get("metadatas") else {})
                    break

        if not text and _bm25_corpus:
            for i, bid in enumerate(_bm25_corpus.get("ids", [])):
                if bid == cid:
                    text = _bm25_corpus["documents"][i]
                    meta = _bm25_corpus["metadatas"][i] if i < len(_bm25_corpus.get("metadatas", [])) else {}
                    break

        results.append({"id": cid, "text": text, "meta": meta, "score": score})

    return results


def refresh_index():
    """重建 BM25 索引（入库后调用）"""
    global _bm25_corpus
    _bm25_corpus = None
    _build_bm25()
