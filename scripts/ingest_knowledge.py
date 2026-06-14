"""
LeKai 知识库入库 Pipeline

流程：
1. 扫描 knowledge-base/ 下所有 .md 文件
2. 解析 YAML frontmatter 元数据
3. 按章节分块（chunk）
4. 生成 Embedding（本地模型: BAAI/bge-small-zh-v1.5, 512维）
5. 存入 ChromaDB

使用方式：
    python scripts/ingest_knowledge.py                  # 全量导入
    python scripts/ingest_knowledge.py --grade 3        # 只导入三年级
    python scripts/ingest_knowledge.py --reset          # 清空后重新导入
"""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

import chromadb
import yaml

# ============================================================
# 配置
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge-base"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"

# Embedding 维度（bge-small-zh-v1.5 → 512）
EMBEDDING_DIM = 512
COLLECTION_NAME = "lesson_plans"

# 懒加载 Embedding 模型
_embedding_model = None

def get_embedding_model():
    """懒加载本地 Embedding 模型（优先 LEKAI_MODEL_DIR > 默认目录 > 在线下载）"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        import os as _os_ingest

        # 优先使用 LEKAI_MODEL_DIR 环境变量指定的本地模型
        local_dir = _os_ingest.environ.get("LEKAI_MODEL_DIR", "")
        if local_dir:
            p = __import__("pathlib").Path(local_dir)
            if p.exists():
                print(f"[INFO] 从 LEKAI_MODEL_DIR 加载模型: {local_dir}")
                _embedding_model = SentenceTransformer(str(p))
                return _embedding_model

        # 默认本地目录
        default_dir = PROJECT_ROOT / ".cache" / "models" / "bge-small-zh-v1.5"
        if default_dir.exists():
            print(f"[INFO] 从默认目录加载模型: {default_dir}")
            _embedding_model = SentenceTransformer(str(default_dir))
            return _embedding_model

        print("[INFO] 加载 Embedding 模型: BAAI/bge-small-zh-v1.5 ...")
        _embedding_model = SentenceTransformer(
            "BAAI/bge-small-zh-v1.5",
            cache_folder=str(PROJECT_ROOT / ".cache" / "models")
        )
        print("[INFO] 模型加载完成")
    return _embedding_model

# 分块策略
CHUNK_SECTIONS = [
    "教材分析", "学情分析", "教学目标",
    "教学重难点", "教学准备", "教学过程",
    "板书设计", "作业布置", "教学反思"
]

GRADE_DIRS = {
    "grade-1": "一年级",
    "grade-2": "二年级",
    "grade-3": "三年级",
    "grade-4": "四年级",
    "grade-5": "五年级",
    "grade-6": "六年级",
}

NORMATIVE_DOC_TYPES = {"textbook", "curriculum_standard", "exam_outline", "unit_goal", "exam_material"}
METHOD_DOC_TYPES = {"teaching_guidance", "teacher_case", "local_case", "training_case"}


# ============================================================
# YAML Frontmatter 解析
# ============================================================

def parse_frontmatter(filepath: Path) -> tuple[dict, str]:
    """解析 Markdown 文件的 YAML frontmatter，返回 (元数据, 正文)"""
    text = filepath.read_text(encoding="utf-8")
    meta = {}
    body = text

    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if match:
        try:
            meta = yaml.safe_load(match.group(1)) or {}
        except yaml.YAMLError:
            meta = {}
        body = text[match.end():]

    return meta, body.strip()


def normalize_metadata(meta: dict, filepath: Path, body: str) -> dict:
    """补齐旧教案缺失的关键元数据，保证年级过滤和课题检索可用。"""
    normalized = dict(meta or {})

    if not normalized.get("grade"):
        for parent in filepath.parents:
            if parent.name in GRADE_DIRS:
                normalized["grade"] = GRADE_DIRS[parent.name]
                break

    if not normalized.get("lesson"):
        title_match = re.search(r'#\s*《(.+?)》', body) or re.search(r'《(.+?)》', body)
        normalized["lesson"] = title_match.group(1).strip() if title_match else filepath.stem

    if not normalized.get("semester"):
        normalized["semester"] = ""
    if not normalized.get("type"):
        normalized["type"] = "阅读课"
    if not normalized.get("tags"):
        normalized["tags"] = []

    if not normalized.get("doc_type"):
        normalized["doc_type"] = infer_doc_type(normalized, filepath, body)
    if not normalized.get("source_role"):
        normalized["source_role"] = "normative" if normalized["doc_type"] in NORMATIVE_DOC_TYPES else "method_case"

    return normalized


def infer_doc_type(meta: dict, filepath: Path, body: str) -> str:
    locator = f"{filepath}\n{meta.get('source', '')}\n{meta.get('title', '')}\n{meta.get('doc_title', '')}".lower()
    lesson_kind = str(meta.get("type") or "").lower()
    body_head = body[:600].lower()

    if any(k in locator for k in ["课标", "课程标准", "curriculum"]):
        return "curriculum_standard"
    if any(k in locator for k in ["考纲", "考试说明", "exam_outline"]):
        return "exam_outline"
    if any(k in locator for k in ["单元目标", "unit_goal"]):
        return "unit_goal"
    if any(k in locator for k in ["题库", "试题", "考点", "exam_material"]):
        return "exam_material"
    if any(k in locator for k in ["教材", "课文原文", "textbook"]):
        return "textbook"

    # 普通 Markdown 教案即使包含“教材分析”“考点”等章节，也只是方法样本。
    if "教案" in body_head or "教学过程" in body_head or lesson_kind.endswith("课"):
        return "local_case"

    text = f"{locator}\n{body_head}"
    if any(k in text for k in ["教学设计与指导", "教学指导", "teaching_guidance"]):
        return "teaching_guidance"
    if any(k in text for k in ["进修校", "training"]):
        return "training_case"
    if any(k in text for k in ["老教师", "teacher_case"]):
        return "teacher_case"
    return "local_case"


# ============================================================
# 分块 (Chunking)
# ============================================================

def chunk_lesson(meta: dict, body: str, source_file: str) -> list[dict]:
    """
    将教案按教学章节分块，每块包含上下文信息。
    返回: [{"id": str, "text": str, "metadata": dict}, ...]
    """
    chunks = []
    grade = meta.get("grade", "")
    lesson = meta.get("lesson", "")
    unit = meta.get("unit", "")
    tags = meta.get("tags", [])
    lesson_type = meta.get("type", "")

    base_meta = {
        "source_file": source_file,
        "grade": grade,
        "semester": str(meta.get("semester", "")),
        "lesson": lesson,
        "unit": str(unit),
        "lesson_type": lesson_type,
        "doc_type": str(meta.get("doc_type", "local_case")),
        "source_role": str(meta.get("source_role", "method_case")),
        "doc_title": str(meta.get("doc_title") or meta.get("title") or lesson or source_file),
        "source_file_id": str(meta.get("source_file_id") or meta.get("file_id") or source_file),
        "source_file_name": str(meta.get("source_file_name") or meta.get("file_name") or source_file),
        "source_hash": str(meta.get("source_hash") or hashlib.sha256(body.encode("utf-8")).hexdigest()),
        "page_num": int(meta.get("page_num") or meta.get("page") or 0),
        "page_width": int(meta.get("page_width") or 0),
        "page_height": int(meta.get("page_height") or 0),
        "bbox": json.dumps(meta.get("bbox", []), ensure_ascii=False) if isinstance(meta.get("bbox"), list) else str(meta.get("bbox", "")),
        "page_image_url": str(meta.get("page_image_url") or meta.get("image_url") or ""),
        "dee_url": str(meta.get("dee_url") or meta.get("source_url") or ""),
        "tags": json.dumps(tags, ensure_ascii=False) if tags else "",
    }

    # 1. 概览 chunk（整个教案摘要，用于语义匹配）
    overview_text = f"年级：{grade}\n课题：《{lesson}》\n单元：{unit}\n课型：{lesson_type}\n"
    overview_text += f"标签：{', '.join(tags) if tags else ''}\n\n"
    # 取前1500字作为概览
    overview_text += body[:1500]

    chunks.append({
        "id": f"{source_file}__overview",
        "text": overview_text,
        "metadata": {**base_meta, "chunk_type": "overview"}
    })

    # 2. 按章节分块
    for section_name in CHUNK_SECTIONS:
        # 匹配 "## 一、教材分析" 或 "### 一、教材分析"
        pattern = rf'(?:^|\n)#{{2,3}}\s*(?:[一二三四五六七八九十]+、)?\s*{re.escape(section_name)}\s*\n(.*?)(?=\n#{{2,3}}\s|\Z)'
        match = re.search(pattern, body, re.DOTALL)
        if match:
            section_text = match.group(1).strip()
            if len(section_text) > 20:  # 有实质内容
                chunk_id = hashlib.md5(
                    f"{source_file}__{section_name}".encode()
                ).hexdigest()[:12]
                chunks.append({
                    "id": chunk_id,
                    "text": f"《{lesson}》- {section_name}\n{section_text}",
                    "metadata": {**base_meta, "chunk_type": section_name}
                })

    return chunks


# ============================================================
# Embedding 生成（批量）
# ============================================================

def generate_embeddings(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    """使用本地 BGE 模型生成 Embeddings"""
    try:
        model = get_embedding_model()
    except Exception as e:
        print(f"[WARN] Embedding 模型不可用，使用占位向量完成入库: {e}")
        return [_placeholder_embedding(text) for text in texts]

    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        # BGE 模型：BAAI/bge-small-zh-v1.5
        encoded = model.encode(
            batch,
            normalize_embeddings=True,
            show_progress_bar=False
        )
        all_embeddings.extend(encoded.tolist())

        print(f"  Embedding batch {i // batch_size + 1}/{(len(texts) - 1) // batch_size + 1} "
              f"({len(batch)} texts)")

    return all_embeddings


def _placeholder_embedding(text: str) -> list[float]:
    """Deterministic fallback embedding for offline placeholder knowledge."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < EMBEDDING_DIM:
        for byte in digest:
            values.append((byte / 127.5) - 1.0)
            if len(values) >= EMBEDDING_DIM:
                break
        digest = hashlib.sha256(digest).digest()
    norm = sum(v * v for v in values) ** 0.5 or 1.0
    return [v / norm for v in values]


# ============================================================
# ChromaDB 操作
# ============================================================

def get_or_create_collection(reset: bool = False):
    """获取或创建 ChromaDB collection"""
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"[INFO] 已删除旧 collection: {COLLECTION_NAME}")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "LeKai教案知识库 - 统编版小学语文教案"}
    )
    return collection


# ============================================================
# 主流程
# ============================================================

def ingest(grade_filter: Optional[int] = None, reset: bool = False):
    """执行入库流程"""
    md_files = sorted(KNOWLEDGE_BASE.rglob("*.md"))
    # 排除模板文件
    md_files = [f for f in md_files if f.name != "TEMPLATE.md"]

    if grade_filter is not None:
        grade_dir = KNOWLEDGE_BASE / f"grade-{grade_filter}"
        md_files = [f for f in md_files if grade_dir in f.parents]

    if not md_files:
        print(f"[WARN] 没有找到教案文件。请先在 knowledge-base/ 下放置 .md 文件")
        return

    print(f"[INFO] 找到 {len(md_files)} 个教案文件")

    # 1. 解析 + 分块
    all_chunks = []
    for f in md_files:
        meta, body = parse_frontmatter(f)
        meta = normalize_metadata(meta, f, body)
        source_id = f.stem
        chunks = chunk_lesson(meta, body, source_id)
        all_chunks.extend(chunks)
        print(f"  {f.name} → {len(chunks)} chunks")

    print(f"[INFO] 总计 {len(all_chunks)} 个 chunk")

    # 2. 生成 Embeddings
    texts = [c["text"] for c in all_chunks]
    embeddings = generate_embeddings(texts)

    # 3. 存入 ChromaDB
    collection = get_or_create_collection(reset=reset)

    ids = [c["id"] for c in all_chunks]
    metadatas = [c["metadata"] for c in all_chunks]

    # 批量 upsert
    batch_size = 50
    for i in range(0, len(all_chunks), batch_size):
        end = min(i + batch_size, len(all_chunks))
        collection.upsert(
            ids=ids[i:end],
            embeddings=embeddings[i:end],
            documents=texts[i:end],
            metadatas=metadatas[i:end]
        )
        print(f"  Upsert {i}-{end-1} / {len(all_chunks)}")

    # 4. 验证
    count = collection.count()
    print(f"\n[DONE] 知识库入库完成！")
    print(f"  - 文件数: {len(md_files)}")
    print(f"  - Chunk数: {len(all_chunks)}")
    print(f"  - ChromaDB总量: {count}")
    print(f"  - 存储位置: {CHROMA_DIR}")

    # 注意：入库脚本运行在子进程中，BM25索引刷新由主进程在subprocess完成后执行
    print(f"  - 入库完成（BM25索引由主进程刷新）")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LeKai知识库入库工具")
    parser.add_argument("--grade", type=int, help="只导入指定年级")
    parser.add_argument("--reset", action="store_true", help="清空旧数据后重新导入")
    parser.add_argument("--search", type=str, help="测试检索（输入查询文本）")

    args = parser.parse_args()

    if args.search:
        # 测试检索（使用本地 BGE 模型）
        collection = get_or_create_collection()
        query_embedding = generate_embeddings([args.search])[0]
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=["documents", "metadatas", "distances"]
        )
        print(f"\n查询: {args.search}")
        print("=" * 60)
        for i, (doc, meta, dist) in enumerate(zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        )):
            print(f"\n#{i+1} [距离: {dist:.4f}] [{meta.get('grade', '')}] 《{meta.get('lesson', '')}》")
            print(f"  类型: {meta.get('chunk_type', '')}")
            print(f"  {doc[:120]}...")
    else:
        ingest(grade_filter=args.grade, reset=args.reset)


if __name__ == "__main__":
    main()
