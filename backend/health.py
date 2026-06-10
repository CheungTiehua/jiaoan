"""
LeKai 健康检查 — 服务状态/API/磁盘/索引
"""

import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"


def get_health() -> dict:
    """健康检查报告"""
    health = {"status": "ok", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": {}}

    # 磁盘
    try:
        disk = shutil.disk_usage(PROJECT_ROOT)
        health["checks"]["disk"] = {
            "total_gb": round(disk.total / 1024**3, 1),
            "free_gb": round(disk.free / 1024**3, 1),
            "used_pct": round((disk.used / disk.total) * 100, 1),
            "ok": disk.free > 100 * 1024**2,
        }
    except Exception as e:
        health["checks"]["disk"] = {"ok": False, "error": str(e)}

    # 向量库
    try:
        from search_engine import get_collection
        col = get_collection()
        count = col.count()
        health["checks"]["chromadb"] = {"total_chunks": count, "ok": True}
    except Exception as e:
        health["checks"]["chromadb"] = {"ok": False, "error": str(e)}

    # 用户数据
    users_file = PROJECT_ROOT / "data" / "users.json"
    users_ok = users_file.exists()
    health["checks"]["users"] = {"exists": users_ok, "ok": users_ok}

    return health
