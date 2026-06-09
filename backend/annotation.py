"""
LeKai 段落标注 — 教研组长审核时标注教案具体段落
"""

import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ANNOTATION_DIR = PROJECT_ROOT / "data" / "annotations"
ANNOTATION_DIR.mkdir(parents=True, exist_ok=True)

SECTIONS = [
    "教材分析", "学情分析", "教学目标", "教学重难点",
    "教学准备", "教学过程", "板书设计", "作业布置", "教学反思"
]


def add_annotation(
    review_id: str, reviewer: str,
    section: str,  # 教案章节
    ann_type: str,  # "praise" | "improve" | "note"
    text: str,
) -> dict:
    """添加段落标注"""
    if section not in SECTIONS:
        section = "其他"

    filepath = ANNOTATION_DIR / f"{review_id}.json"
    annotations = []
    if filepath.exists():
        try:
            annotations = json.loads(filepath.read_text())
        except Exception:
            pass

    annotations.append({
        "reviewer": reviewer,
        "section": section,
        "type": ann_type,
        "text": text,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })

    from security import atomic_write
    atomic_write(filepath, json.dumps(annotations, ensure_ascii=False, indent=2).encode())
    return {"ok": True, "annotations": annotations}


def get_annotations(review_id: str) -> list[dict]:
    """获取某次审核的所有标注"""
    filepath = ANNOTATION_DIR / f"{review_id}.json"
    if filepath.exists():
        try:
            return json.loads(filepath.read_text())
        except Exception:
            pass
    return []


def get_stats() -> dict:
    """标注统计：哪些章节经常被表扬/需要改进"""
    stats = {s: {"praise": 0, "improve": 0, "note": 0} for s in SECTIONS}
    for f in ANNOTATION_DIR.glob("*.json"):
        try:
            for ann in json.loads(f.read_text()):
                sec = ann.get("section", "其他")
                tp = ann.get("type", "note")
                if sec in stats:
                    stats[sec][tp] += 1
        except Exception:
            pass
    return stats
