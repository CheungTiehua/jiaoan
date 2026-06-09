"""LeKai 安全模块 — 速率限制 + 原子写入"""

import threading
import time
from pathlib import Path


def atomic_write(filepath: Path, data: bytes):
    """原子写入：先写 .tmp，再 rename，崩溃不损坏原文件"""
    tmp = filepath.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(filepath)


# ---- 速率限制 ----

_rate_store: dict[str, tuple[int, float]] = {}
_rate_lock = threading.Lock()

def check_rate_limit(key: str, max_attempts: int = 10, window_sec: int = 60) -> bool:
    """滑动窗口速率限制（线程安全），返回 True 表示被限流"""
    now = time.time()
    with _rate_lock:
        if len(_rate_store) > 1000:
            expired = [k for k, (_, last) in _rate_store.items() if now - last > window_sec * 2]
            for k in expired:
                del _rate_store[k]

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
