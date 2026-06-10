"""
LeKai 管理端 API — 校长仪表盘 + 教研组长审核流程
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional

from auth import (
    HISTORY_DIR, load_users, save_users,
    get_user_role, list_users, get_history, get_history_detail,
)
from security import atomic_write

_log = logging.getLogger("lekai")

import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REVIEWS_DIR = HISTORY_DIR.parent / "reviews"
REVIEWS_DIR.mkdir(parents=True, exist_ok=True)


def _safe_id(record_id: str) -> str:
    return os.path.basename(str(record_id))


# ============================================================
# 审核流程
# ============================================================

def submit_for_review(username: str, record_id: str) -> bool:
    """提交教案到审核队列"""
    detail = get_history_detail(username, record_id)
    if not detail:
        return False

    review = {
        "id": record_id,
        "username": username,
        "grade": detail.get("grade", ""),
        "lesson": detail.get("lesson", ""),
        "timestamp": detail.get("timestamp", ""),
        "status": "pending",  # pending / approved / rejected
        "reviewer": "",
        "review_time": "",
        "comment": "",
        "lesson_plan": detail.get("lesson_plan", ""),
        "teaching_guide": detail.get("teaching_guide", ""),
    }
    filepath = REVIEWS_DIR / f"{_safe_id(record_id)}.json"
    atomic_write(filepath, json.dumps(review, ensure_ascii=False, indent=2).encode())
    return True


def get_review_queue() -> list[dict]:
    """获取审核队列（按状态筛选）"""
    queue = []
    for f in sorted(REVIEWS_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text())
            data.pop("lesson_plan", None)
            data.pop("teaching_guide", None)
            queue.append(data)
        except Exception as e:
            _log.warning("解析审核记录失败: %s: %s", f.name, e)
    return queue


def get_review_detail(record_id: str) -> Optional[dict]:
    """获取待审核教案的完整详情"""
    filepath = REVIEWS_DIR / f"{_safe_id(record_id)}.json"
    if not filepath.exists():
        return None
    try:
        return json.loads(filepath.read_text())
    except Exception as e:
        _log.warning("读取审核详情失败: %s: %s", filepath.name, e)
        return None


def approve_review(record_id: str, reviewer: str, comment: str = "") -> bool:
    """审核通过"""
    filepath = REVIEWS_DIR / f"{_safe_id(record_id)}.json"
    if not filepath.exists():
        return False
    try:
        data = json.loads(filepath.read_text())
        data["status"] = "approved"
        data["reviewer"] = reviewer
        data["review_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["comment"] = comment
        atomic_write(filepath, json.dumps(data, ensure_ascii=False, indent=2).encode())
        return True
    except Exception as e:
        _log.warning("审核操作失败: %s: %s", filepath.name, e)
        return False


def reject_review(record_id: str, reviewer: str, comment: str) -> bool:
    """审核打回"""
    filepath = REVIEWS_DIR / f"{_safe_id(record_id)}.json"
    if not filepath.exists():
        return False
    try:
        data = json.loads(filepath.read_text())
        data["status"] = "rejected"
        data["reviewer"] = reviewer
        data["review_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        data["comment"] = comment
        atomic_write(filepath, json.dumps(data, ensure_ascii=False, indent=2).encode())
        return True
    except Exception as e:
        _log.warning("审核操作失败: %s: %s", filepath.name, e)
        return False


# ============================================================
# 仪表盘统计
# ============================================================

def get_dashboard_stats() -> dict:
    """获取管理端仪表盘数据"""
    users = list_users()
    total_users = len(users)

    # 统计所有用户生成记录
    all_records = []
    teacher_stats = {}
    for u in users:
        uname = u["username"]
        history = get_history(uname, limit=500)
        all_records.extend(history)
        teacher_stats[uname] = {
            "total": len(history),
            "lessons": list(set(h.get("lesson", "") for h in history if h.get("lesson"))),
        }

    # 按年级统计覆盖
    grade_coverage = {}
    for r in all_records:
        g = r.get("grade", "未知")
        l = r.get("lesson", "")
        if g not in grade_coverage:
            grade_coverage[g] = set()
        grade_coverage[g].add(l)

    # 审核统计
    review_queue = get_review_queue()
    pending = sum(1 for r in review_queue if r.get("status") == "pending")
    approved = sum(1 for r in review_queue if r.get("status") == "approved")
    rejected = sum(1 for r in review_queue if r.get("status") == "rejected")

    # 按时间趋势（最近7天）
    from collections import defaultdict
    daily = defaultdict(int)
    for r in all_records:
        ts = r.get("timestamp", "")
        if ts:
            day = ts[:10]
            daily[day] += 1

    return {
        "total_users": total_users,
        "total_plans": len(all_records),
        "grade_coverage": {g: len(lessons) for g, lessons in grade_coverage.items()},
        "grade_coverage_detail": {g: sorted(list(lessons)) for g, lessons in grade_coverage.items()},
        "review_stats": {"pending": pending, "approved": approved, "rejected": rejected},
        "daily_trend": dict(sorted(daily.items())[-14:]),
        "teacher_summary": [
            {"username": u, "total": teacher_stats.get(u, {}).get("total", 0),
             "recent_lessons": teacher_stats.get(u, {}).get("lessons", [])[:5],
             "role": next((usr.get("role", "teacher") for usr in users if usr["username"] == u), "teacher")}
            for u in sorted(teacher_stats.keys())
        ],
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
    }


# ============================================================
# 角色管理
# ============================================================

def set_user_role(username: str, role: str) -> bool:
    """设置用户角色: teacher / reviewer / admin"""
    if role not in ("teacher", "reviewer", "admin"):
        return False
    import fcntl
    lock_file = Path(__file__).resolve().parent.parent / "data" / "users.lock"
    with open(lock_file, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            users = load_users()
            if username not in users:
                return False
            users[username]["role"] = role
            save_users(users)
            return True
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)
