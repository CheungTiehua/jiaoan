"""
LeKai 健康检查 — 服务状态/API/磁盘/索引
"""

import shutil
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
LOG_FILE = PROJECT_ROOT / "logs" / "lekai.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


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
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        collections = client.list_collections()
        count = sum(c.count() for c in collections)
        health["checks"]["chromadb"] = {"collections": len(collections), "total_chunks": count, "ok": True}
    except Exception as e:
        health["checks"]["chromadb"] = {"ok": False, "error": str(e)}

    # 用户数据
    users_file = PROJECT_ROOT / "data" / "users.json"
    health["checks"]["users"] = {"exists": users_file.exists(), "ok": True}

    return health
