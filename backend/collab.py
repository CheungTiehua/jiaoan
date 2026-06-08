"""
LeKai 教研协作 — 教研组 + 共享教案 + 集体备课
"""

import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLAB_DIR = PROJECT_ROOT / "data" / "collab"
GROUPS_FILE = COLLAB_DIR / "groups.json"
COLLAB_DIR.mkdir(parents=True, exist_ok=True)


def _load_groups() -> dict:
    if GROUPS_FILE.exists():
        try:
            return json.loads(GROUPS_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def _save_groups(data: dict):
    GROUPS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))


# ---- 教研组管理 ----

def create_group(name: str, creator: str) -> dict:
    groups = _load_groups()
    if name in groups:
        return {"ok": False, "msg": "教研组已存在"}
    groups[name] = {
        "creator": creator,
        "members": [creator],
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "shared_plans": [],  # [{shared_by, lesson, record_id, timestamp}]
        "tasks": [],  # [{assigned_to, lesson, status, timestamp}]
    }
    _save_groups(groups)
    return {"ok": True, "msg": f"教研组「{name}」创建成功"}


def list_groups() -> list:
    groups = _load_groups()
    return [{"name": k, "members": v.get("members", []), "created_at": v.get("created_at", ""),
             "plan_count": len(v.get("shared_plans", []))} for k, v in groups.items()]


def join_group(name: str, username: str) -> dict:
    groups = _load_groups()
    if name not in groups:
        return {"ok": False, "msg": "教研组不存在"}
    if username in groups[name].get("members", []):
        return {"ok": False, "msg": "已在教研组中"}
    groups[name].setdefault("members", []).append(username)
    _save_groups(groups)
    return {"ok": True, "msg": f"已加入「{name}」"}


def get_user_groups(username: str) -> list:
    groups = _load_groups()
    return [k for k, v in groups.items() if username in v.get("members", [])]


# ---- 共享教案 ----

def share_plan(username: str, group_name: str, grade: str, lesson: str, record_id: str) -> dict:
    groups = _load_groups()
    if group_name not in groups:
        return {"ok": False, "msg": "教研组不存在"}
    g = groups[group_name]
    g.setdefault("shared_plans", []).append({
        "shared_by": username,
        "grade": grade,
        "lesson": lesson,
        "record_id": record_id,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "comments": [],  # [{username, text, timestamp}]
    })
    _save_groups(groups)
    return {"ok": True, "msg": "已分享到教研组"}


def get_group_plans(group_name: str) -> list:
    groups = _load_groups()
    if group_name not in groups:
        return []
    return groups[group_name].get("shared_plans", [])


# ---- 集体备课任务 ----

def assign_task(group_name: str, assigned_to: str, lesson: str, requester: str) -> dict:
    groups = _load_groups()
    if group_name not in groups:
        return {"ok": False, "msg": "教研组不存在"}
    g = groups[group_name]
    g.setdefault("tasks", []).append({
        "assigned_to": assigned_to,
        "lesson": lesson,
        "status": "pending",
        "requester": requester,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_groups(groups)
    return {"ok": True, "msg": f"已分配任务给 {assigned_to}"}


def get_group_tasks(group_name: str) -> list:
    groups = _load_groups()
    if group_name not in groups:
        return []
    return groups[group_name].get("tasks", [])


def complete_task(group_name: str, task_index: int) -> dict:
    groups = _load_groups()
    if group_name not in groups:
        return {"ok": False, "msg": "教研组不存在"}
    tasks = groups[group_name].get("tasks", [])
    if task_index >= len(tasks):
        return {"ok": False, "msg": "任务不存在"}
    tasks[task_index]["status"] = "done"
    _save_groups(groups)
    return {"ok": True, "msg": "任务已完成"}


# ---- 评论 ----

def add_comment(group_name: str, plan_index: int, username: str, text: str) -> dict:
    groups = _load_groups()
    if group_name not in groups:
        return {"ok": False, "msg": "教研组不存在"}
    plans = groups[group_name].get("shared_plans", [])
    if plan_index >= len(plans):
        return {"ok": False, "msg": "教案不存在"}
    plans[plan_index].setdefault("comments", []).append({
        "username": username,
        "text": text,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    _save_groups(groups)
    return {"ok": True, "msg": "评论已添加"}
