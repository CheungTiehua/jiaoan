"""
LeKai 教研协作 — 教研组 + 共享教案 + 集体备课
"""

import fcntl
import json
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COLLAB_DIR = PROJECT_ROOT / "data" / "collab"
GROUPS_FILE = COLLAB_DIR / "groups.json"
COLLAB_DIR.mkdir(parents=True, exist_ok=True)

_lock_file = COLLAB_DIR / ".lock"


class _GroupsCtx:
    """上下文管理器：加锁→读→返回可修改dict→退出时写→解锁"""
    def __init__(self):
        self.fd = None
        self.data = {}

    def __enter__(self):
        self.fd = open(_lock_file, "w")
        fcntl.flock(self.fd, fcntl.LOCK_EX)
        if GROUPS_FILE.exists():
            try:
                self.data = json.loads(GROUPS_FILE.read_text())
            except json.JSONDecodeError:
                self.data = {}
        return self.data

    def __exit__(self, *args):
        try:
            from security import atomic_write
            atomic_write(GROUPS_FILE, json.dumps(self.data, ensure_ascii=False, indent=2).encode())
        finally:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            self.fd.close()


def _load_groups() -> dict:
    """仅读取（不修改），短期持锁"""
    with _GroupsCtx() as data:
        return data.copy()


def _atomic_update(mutate_fn) -> dict:
    """原子读-改-写：加锁→读→调用mutate_fn修改→写→解锁"""
    with _GroupsCtx() as data:
        result = mutate_fn(data)
        return result if result is not None else {}


# ---- 教研组管理 ----

def create_group(name: str, creator: str) -> dict:
    def _mut(data):
        if name in data:
            return {"ok": False, "msg": "教研组已存在"}
        data[name] = {"creator": creator, "members": [creator],
                      "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                      "shared_plans": [], "tasks": []}
        return {"ok": True, "msg": f"教研组「{name}」创建成功"}
    return _atomic_update(_mut)


def list_groups() -> list:
    groups = _load_groups()
    return [{"name": k, "members": v.get("members", []), "created_at": v.get("created_at", ""),
             "plan_count": len(v.get("shared_plans", []))} for k, v in groups.items()]


def join_group(name: str, username: str) -> dict:
    def _mut(data):
        if name not in data:
            return {"ok": False, "msg": "教研组不存在"}
        if username in data[name].get("members", []):
            return {"ok": False, "msg": "已在教研组中"}
        data[name].setdefault("members", []).append(username)
        return {"ok": True, "msg": f"已加入「{name}」"}
    return _atomic_update(_mut)


def get_user_groups(username: str) -> list:
    groups = _load_groups()
    return [k for k, v in groups.items() if username in v.get("members", [])]


# ---- 共享教案 ----

def share_plan(username: str, group_name: str, grade: str, lesson: str, record_id: str) -> dict:
    def _mut(data):
        if group_name not in data:
            return {"ok": False, "msg": "教研组不存在"}
        data[group_name].setdefault("shared_plans", []).append({
            "shared_by": username, "grade": grade, "lesson": lesson,
            "record_id": record_id, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "comments": [],
        })
        return {"ok": True, "msg": "已分享到教研组"}
    return _atomic_update(_mut)


def get_group_plans(group_name: str) -> list:
    groups = _load_groups()
    if group_name not in groups:
        return []
    return groups[group_name].get("shared_plans", [])


# ---- 集体备课任务 ----

def assign_task(group_name: str, assigned_to: str, lesson: str, requester: str) -> dict:
    def _mut(data):
        if group_name not in data:
            return {"ok": False, "msg": "教研组不存在"}
        data[group_name].setdefault("tasks", []).append({
            "assigned_to": assigned_to, "lesson": lesson, "status": "pending",
            "requester": requester, "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return {"ok": True, "msg": f"已分配任务给 {assigned_to}"}
    return _atomic_update(_mut)


def get_group_tasks(group_name: str) -> list:
    groups = _load_groups()
    if group_name not in groups:
        return []
    return groups[group_name].get("tasks", [])


def complete_task(group_name: str, task_index: int) -> dict:
    def _mut(data):
        if group_name not in data:
            return {"ok": False, "msg": "教研组不存在"}
        tasks = data[group_name].get("tasks", [])
        if task_index < 0 or task_index >= len(tasks):
            return {"ok": False, "msg": "任务不存在"}
        tasks[task_index]["status"] = "done"
        return {"ok": True, "msg": "任务已完成"}
    return _atomic_update(_mut)


# ---- 评论 ----

def add_comment(group_name: str, plan_index: int, username: str, text: str) -> dict:
    def _mut(data):
        if group_name not in data:
            return {"ok": False, "msg": "教研组不存在"}
        plans = data[group_name].get("shared_plans", [])
        if plan_index < 0 or plan_index >= len(plans):
            return {"ok": False, "msg": "教案不存在"}
        plans[plan_index].setdefault("comments", []).append({
            "username": username, "text": text,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        return {"ok": True, "msg": "评论已添加"}
    return _atomic_update(_mut)
