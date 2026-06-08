"""
LeKai 安全模块 — 速率限制 + HMAC签名 + 原子写入
借鉴 zhishiku 的安全加固模式
"""

import hashlib
import hmac
import os
import time
from pathlib import Path

# HMAC Key（用于索引签名，服务重启后不变）
HMAC_KEY_FILE = Path(__file__).resolve().parent.parent / "data" / ".hmac_key"
HMAC_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)

if HMAC_KEY_FILE.exists():
    HMAC_KEY = HMAC_KEY_FILE.read_bytes()
else:
    HMAC_KEY = os.urandom(32)
    HMAC_KEY_FILE.write_bytes(HMAC_KEY)
    HMAC_KEY_FILE.chmod(0o600)


def sign_data(data: bytes) -> bytes:
    """HMAC-SHA256 签名，返回 signature + data"""
    sig = hmac.digest(HMAC_KEY, data, "sha256")
    return sig + data


def verify_and_load(data: bytes) -> bytes | None:
    """验证 HMAC 签名后返回原始数据，签名无效返回 None"""
    if len(data) < 32:
        return None
    sig, payload = data[:32], data[32:]
    expected = hmac.digest(HMAC_KEY, payload, "sha256")
    if hmac.compare_digest(sig, expected):
        return payload
    return None


def atomic_write(filepath: Path, data: bytes):
    """原子写入：先写 .tmp，再 rename，崩溃不损坏原文件"""
    tmp = filepath.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(filepath)


# ---- 速率限制 ----

_rate_store: dict[str, tuple[int, float]] = {}  # key -> (count, timestamp)

def check_rate_limit(key: str, max_attempts: int = 10, window_sec: int = 60) -> bool:
    """滑动窗口速率限制，返回 True 表示被限流"""
    now = time.time()
    if key in _rate_store:
        cnt, last = _rate_store[key]
        if now - last > window_sec:
            _rate_store[key] = (1, now)
        elif cnt >= max_attempts:
            return True
        else:
            _rate_store[key] = (cnt + 1, now)
    else:
        _rate_store[key] = (1, now)
    return False
