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

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

# Embedding 维度（bge-small-zh-v1.5 → 512）
EMBEDDING_DIM = 512
COLLECTION_NAME = "lesson_plans"

# 懒加载 Embedding 模型
_embedding_model = None

def get_embedding_model():
    """懒加载本地 Embedding 模型"""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
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
        "lesson": lesson,
        "unit": str(unit),
        "lesson_type": lesson_type,
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
    model = get_embedding_model()

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
