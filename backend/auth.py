"""
LeKai 用户认证 — 轻量 Token 鉴权

设计原则：
- 学校场景，注册无需邮箱，Username + Password 即可
- Token 持久化到文件，服务重启不丢失
- 知识库共享，生成历史按用户隔离
"""

import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
USERS_FILE = DATA_DIR / "users.json"
SESSIONS_FILE = DATA_DIR / "sessions.json"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def _hash_pw(password: str) -> str:
    """PBKDF2 密码哈希"""
    salt = os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
    return salt.hex() + ":" + dk.hex()


def _verify_pw(password: str, hashed: str) -> bool:
    """验证密码"""
    try:
        salt_hex, dk_hex = hashed.split(":")
        salt = bytes.fromhex(salt_hex)
        dk = bytes.fromhex(dk_hex)
        new_dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600000)
        return new_dk == dk
    except (ValueError, KeyError):
        return False


def load_users() -> dict:
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except json.JSONDecodeError:
            import logging
            logging.getLogger("lekai").error("users.json 损坏！从备份恢复")
            # 尝试从 .bak 恢复
            bak = USERS_FILE.with_suffix(".json.bak")
            if bak.exists():
                try:
                    return json.loads(bak.read_text())
                except Exception:
                    pass
    return {}


def save_users(users: dict):
    from security import atomic_write
    # 写入前先备份
    if USERS_FILE.exists():
        import shutil
        shutil.copy2(USERS_FILE, USERS_FILE.with_suffix(".json.bak"))
    atomic_write(USERS_FILE, json.dumps(users, ensure_ascii=False, indent=2).encode())
    USERS_FILE.chmod(0o600)


def load_sessions() -> dict:
    if SESSIONS_FILE.exists():
        try:
            return json.loads(SESSIONS_FILE.read_text())
        except json.JSONDecodeError:
            import logging
            logging.getLogger("lekai").warning("sessions.json 损坏，重新初始化")
    return {}


def save_sessions(sessions: dict):
    from security import atomic_write
    now = time.time()
    sessions = {k: v for k, v in sessions.items() if v.get("expires_at", 0) > now}
    atomic_write(SESSIONS_FILE, json.dumps(sessions, ensure_ascii=False, indent=2).encode())
    SESSIONS_FILE.chmod(0o600)


def register_user(username: str, password: str) -> tuple[bool, str]:
    """注册（文件锁保护），返回 (成功, 消息)"""
    username = username.strip()
    if not username or len(username) < 2:
        return False, "用户名至少2个字符"
    import re
    if not re.match(r'^[a-zA-Z0-9_\-]+$', username):
        return False, "用户名只能包含字母、数字、下划线和连字符"
    if not password or len(password) < 4:
        return False, "密码至少4个字符"

    import fcntl
    lock_file = DATA_DIR / "users.lock"
    with open(lock_file, "w") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            users = load_users()
            if username in users:
                return False, "用户名已存在"

            users[username] = {
                "password": _hash_pw(password),
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "role": "teacher",
            }
            # 首个注册用户自动成为管理员
            if len(users) == 1:
                users[username]["role"] = "admin"

            save_users(users)
            return True, "注册成功"
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


def login_user(username: str, password: str) -> Optional[str]:
    """登录成功返回 token，失败返回 None"""
    users = load_users()
    user = users.get(username.strip())
    if not user:
        return None
    if not _verify_pw(password, user["password"]):
        return None

    token = secrets.token_hex(32)
    sessions = load_sessions()
    sessions[token] = {
        "username": username,
        "created_at": time.time(),
        "expires_at": time.time() + 7 * 24 * 3600,
    }
    save_sessions(sessions)
    return token


def logout_user(token: str):
    sessions = load_sessions()
    sessions.pop(token, None)
    save_sessions(sessions)


def get_user_from_token(token: str) -> Optional[str]:
    """从 token 获取用户名，token 失效返回 None"""
    sessions = load_sessions()
    sess = sessions.get(token)
    if not sess:
        return None
    if sess.get("expires_at", 0) < time.time():
        sessions.pop(token, None)
        save_sessions(sessions)
        return None
    return sess.get("username")


def get_user_role(username: str) -> str:
    users = load_users()
    return users.get(username, {}).get("role", "teacher")


def list_users() -> list[dict]:
    users = load_users()
    return [
        {"username": u, "role": d.get("role", "teacher"), "created_at": d.get("created_at", "")}
        for u, d in users.items()
    ]


# ============================================================
# 生成历史（按用户隔离）
# ============================================================

HISTORY_DIR = DATA_DIR / "history"
HISTORY_DIR.mkdir(parents=True, exist_ok=True)


def save_history(username: str, grade: str, lesson: str, plan: dict) -> str:
    """保存生成记录，返回 record_id"""
    user_dir = HISTORY_DIR / username
    user_dir.mkdir(parents=True, exist_ok=True)

    ts = int(time.time() * 1000)
    filepath = user_dir / f"{ts}.json"
    # 防时钟回拨：若文件已存在则递增后缀
    if filepath.exists():
        for suffix in range(1, 100):
            alt = user_dir / f"{ts}_{suffix}.json"
            if not alt.exists():
                filepath = alt
                break

    record = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "grade": grade,
        "lesson": lesson,
        "exam_analysis": plan.get("exam_analysis", ""),
        "peer_analysis": plan.get("peer_analysis", ""),
        "lesson_plan": plan.get("lesson_plan", ""),
        "teaching_guide": plan.get("teaching_guide", ""),
    }
    from security import atomic_write
    atomic_write(filepath, json.dumps(record, ensure_ascii=False, indent=2).encode())
    return str(ts)


def get_history(username: str, limit: int = 20) -> list[dict]:
    """获取用户的生成历史"""
    user_dir = HISTORY_DIR / username
    if not user_dir.exists():
        return []

    files = sorted(user_dir.glob("*.json"), reverse=True)[:limit]
    history = []
    for f in files:
        try:
            data = json.loads(f.read_text())
            data["id"] = f.stem
            # 不返回完整教案内容，只返回摘要
            data.pop("lesson_plan", None)
            data.pop("teaching_guide", None)
            history.append(data)
        except Exception:
            pass
    return history


def get_history_detail(username: str, record_id: str) -> Optional[dict]:
    """获取单条历史详情（含完整教案）"""
    safe_id = os.path.basename(str(record_id))
    filepath = HISTORY_DIR / username / f"{safe_id}.json"
    if not filepath.exists():
        return None
    try:
        data = json.loads(filepath.read_text())
        data["id"] = record_id
        return data
    except Exception:
        return None
