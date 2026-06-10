#!/usr/bin/env python3
"""
LeKai 升级前检查与备份脚本

用法:
  python scripts/pre_upgrade_check.py                  # 正式升级前检查
  python scripts/pre_upgrade_check.py --allow-empty-kb # 首次部署（允许空知识库）

功能:
  1. 读取当前版本号
  2. 检查核心数据完整性
  3. 检查磁盘空间
  4. 生成升级前备份
  5. 输出检查结果
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FAILED = 0


def ok(msg: str):
    print(f"  ✅ {msg}")


def fail(msg: str):
    global FAILED
    FAILED += 1
    print(f"  ❌ {msg}")


def check(condition: bool, msg: str):
    if condition:
        ok(msg)
    else:
        fail(msg)


def main():
    global FAILED

    parser = argparse.ArgumentParser(description="LeKai 升级前检查与备份")
    parser.add_argument("--allow-empty-kb", action="store_true",
                        help="允许首次部署时知识库和 ChromaDB 为空")
    args = parser.parse_args()

    if args.allow_empty_kb:
        print("(首次部署模式：知识库和 ChromaDB 允许为空)")
        print()

    # 1. 版本
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from config import VERSION
    except Exception as e:
        print(f"[WARN] 无法读取版本号: {e}", file=sys.stderr)
        VERSION = "unknown"
    print(f"当前版本: {VERSION}")

    # 2. 用户数据
    users_file = PROJECT_ROOT / "data" / "users.json"
    check(users_file.exists(), f"用户数据: data/users.json 存在")
    if users_file.exists():
        import json
        try:
            users = json.loads(users_file.read_text())
            check(len(users) > 0, f"用户数据: 包含 {len(users)} 个用户")
        except Exception:
            fail("用户数据: 无法解析 users.json")

    # 3. 知识库
    kb_dir = PROJECT_ROOT / "knowledge-base"
    check(kb_dir.exists(), "知识库目录: 存在")
    md_files = list(kb_dir.rglob("*.md")) if kb_dir.exists() else []

    if args.allow_empty_kb:
        ok(f"知识库目录: {len(md_files)} 个教案文件（允许为空）")
    else:
        check(len(md_files) > 0, f"知识库目录: {len(md_files)} 个教案文件")

    # 4. ChromaDB
    chroma_dir = PROJECT_ROOT / "chroma_db"
    check(chroma_dir.exists(), "ChromaDB: 目录存在")
    if chroma_dir.exists():
        chroma_files = list(chroma_dir.rglob("*"))
        if args.allow_empty_kb:
            ok(f"ChromaDB: {len(chroma_files)} 个文件（允许为空）")
        else:
            check(len(chroma_files) > 0, f"ChromaDB: {len(chroma_files)} 个文件")

    # 5. 磁盘空间
    import shutil
    disk = shutil.disk_usage(PROJECT_ROOT)
    free_gb = round(disk.free / 1024**3, 1)
    check(free_gb > 1, f"磁盘空间: {free_gb}GB 可用")

    # 6. 生成升级前备份
    print()
    backup_dir = PROJECT_ROOT / "data" / "_backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"pre_upgrade_{ts}.zip"

    try:
        from backend.backup import create_backup
        buf = create_backup()
        backup_file.write_bytes(buf.getvalue())
        ok(f"升级前备份: {backup_file}")
    except Exception as e:
        fail(f"升级前备份失败: {e}")

    # 结果
    print()
    if FAILED == 0:
        print("PRE-UPGRADE CHECK PASSED")
        return 0
    else:
        print(f"PRE-UPGRADE CHECK FAILED ({FAILED} 项未通过)")
        return 1


if __name__ == "__main__":
    sys.exit(main())
