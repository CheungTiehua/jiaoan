"""
LeKai 教案反馈闭环 — 教师评分 + 检索权重反哺
"""

import json
import time
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FEEDBACK_DIR = PROJECT_ROOT / "data" / "feedback"
WEIGHTS_FILE = FEEDBACK_DIR / "reference_weights.json"
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)


def submit_feedback(
    username: str, plan_id: str, grade: str, lesson: str,
    rating: int = 0,  # 1-5
    useful_refs: list[str] | None = None,  # 有用的同行参考来源
    tags: list[str] | None = None,  # 标签：如"板书好""导入弱"
    comment: str = "",
) -> dict:
    """提交教案反馈"""
    if not 1 <= rating <= 5:
        rating = 0  # 0 = 跳过评分，仅记录标签/评论

    record = {
        "username": username,
        "plan_id": plan_id,
        "grade": grade,
        "lesson": lesson,
        "rating": rating,
        "useful_refs": useful_refs or [],
        "tags": tags or [],
        "comment": comment,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    filepath = FEEDBACK_DIR / f"{plan_id}.json"
    from security import atomic_write
    atomic_write(filepath, json.dumps(record, ensure_ascii=False, indent=2).encode())

    # 更新引用权重
    if useful_refs:
        _update_weights(useful_refs, rating)

    return {"ok": True}


def get_feedback(plan_id: str) -> dict | None:
    """获取教案反馈"""
    filepath = FEEDBACK_DIR / f"{plan_id}.json"
    if filepath.exists():
        try:
            return json.loads(filepath.read_text())
        except Exception:
            pass
    return None


def get_stats() -> dict:
    """全局反馈统计"""
    ratings = defaultdict(int)
    tags_count = defaultdict(int)
    total = 0
    for f in FEEDBACK_DIR.glob("*.json"):
        try:
            d = json.loads(f.read_text())
            if d.get("rating"):
                ratings[d["rating"]] += 1
            for t in d.get("tags", []):
                tags_count[t] += 1
            total += 1
        except Exception:
            pass
    return {
        "total_feedbacks": total,
        "avg_rating": round(
            sum(k * v for k, v in ratings.items()) / max(sum(ratings.values()), 1), 1
        ),
        "ratings": dict(ratings),
        "top_tags": sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:10],
    }


# ---- 引用权重系统 ----

def _update_weights(refs: list[str], rating: int):
    """根据反馈调整引用来源的权重"""
    weights = _load_weights()
    boost = (rating - 3) * 0.05  # 4星=+0.05, 5星=+0.10, 2星=-0.05, 1星=-0.10
    for ref in refs:
        key = ref.split("》")[0] if "》" in ref else ref  # 提取教案名
        weights[key] = round(weights.get(key, 1.0) + boost, 2)
        weights[key] = max(0.5, min(2.0, weights[key]))  # 限制在 0.5-2.0

    _save_weights(weights)


def _load_weights() -> dict:
    if WEIGHTS_FILE.exists():
        try:
            return json.loads(WEIGHTS_FILE.read_text())
        except Exception:
            pass
    return {}


def _save_weights(data: dict):
    from security import atomic_write
    atomic_write(WEIGHTS_FILE, json.dumps(data, ensure_ascii=False, indent=2).encode())


def get_reference_weight(source: str) -> float:
    """获取某个参考来源的权重（用于检索排序）"""
    weights = _load_weights()
    return weights.get(source, 1.0)
