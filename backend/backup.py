"""
LeKai 备份恢复 — zip打包 + Zip Bomb防护
借鉴 zhishiku 的防离岗备份和恢复模式
"""

import io
import json
import shutil
import time
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
BACKUP_DIR = DATA_DIR / "_backup"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

MAX_RESTORE_SIZE = 500 * 1024 * 1024
MAX_ENTRY_SIZE = 100 * 1024 * 1024
MAX_RATIO = 100


def create_backup() -> io.BytesIO:
    """创建备份 zip"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # 用户数据
        users_file = DATA_DIR / "users.json"
        if users_file.exists():
            zf.write(users_file, "users.json")
        # 知识库教案
        kb = PROJECT_ROOT / "knowledge-base"
        if kb.exists():
            for f in kb.rglob("*.md"):
                zf.write(f, str(f.relative_to(PROJECT_ROOT)))
        # ChromaDB
        if CHROMA_DIR.exists():
            for f in CHROMA_DIR.rglob("*"):
                if f.is_file() and f.stat().st_size < 50 * 1024 * 1024:
                    zf.write(f, str(f.relative_to(PROJECT_ROOT)))
        # 配置文件（脱敏）
        env_file = PROJECT_ROOT / ".env"
        if env_file.exists():
            env_content = env_file.read_text()
            masked = "\n".join(
                l if not l.startswith("DEEPSEEK_API_KEY=") else "DEEPSEEK_API_KEY=***masked***"
                for l in env_content.split("\n")
            )
            zf.writestr("config.env.example", masked)
        # 元信息
        zf.writestr("backup_meta.json", json.dumps({
            "version": "0.7", "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }, ensure_ascii=False, indent=2))
    buf.seek(0)
    return buf


def restore_backup(file_data: bytes) -> tuple[bool, str]:
    """恢复备份，返回 (成功, 消息)"""
    try:
        buf = io.BytesIO(file_data)
        total_written = 0
        with zipfile.ZipFile(buf, "r") as zf:
            for info in zf.infolist():
                if info.file_size > MAX_ENTRY_SIZE:
                    continue
                if info.compress_size > 0 and (info.file_size / info.compress_size) > MAX_RATIO:
                    continue
                dest = (PROJECT_ROOT / info.filename).resolve()
                if not str(dest).startswith(str(PROJECT_ROOT.resolve())):
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as src:
                    data = src.read()
                total_written += len(data)
                if total_written > MAX_RESTORE_SIZE:
                    break
                dest.write_bytes(data)
        return True, "备份恢复成功。建议重启服务以确保索引同步。"
    except zipfile.BadZipFile:
        return False, "备份文件损坏"
    except Exception as e:
        return False, f"恢复失败: {str(e)}"


def mirror_upload(username: str, filename: str, filepath: Path):
    """防离岗备份：上传文件时自动镜像到 _backup/"""
    try:
        dest_dir = BACKUP_DIR / username / "uploads"
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(filepath), str(dest_dir / filename))
    except Exception:
        pass  # 镜像失败不影响主流程
