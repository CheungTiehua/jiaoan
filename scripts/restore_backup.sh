#!/bin/bash
# LeKai 恢复脚本 — 换新电脑时从备份 SSD 恢复数据
# 用法: sudo bash restore_backup.sh

set -e
BACKUP_DIR="/mnt/backup"
APP_DIR="/opt/lekai"

[ -d "$BACKUP_DIR" ] || { echo "请插入备份 SSD，挂载到 $BACKUP_DIR"; exit 1; }

LATEST=$(ls -t "$BACKUP_DIR"/lekai_backup_*.zip 2>/dev/null | head -1)
[ -z "$LATEST" ] && { echo "未找到备份文件"; exit 1; }

echo "恢复自: $LATEST"
systemctl stop lekai-backend lekai-frontend 2>/dev/null || true

cd "$APP_DIR"
export LATEST
python3 -c "
import os, sys
sys.path.insert(0, 'backend')
from backup import restore_backup
f = os.environ['LATEST']
with open(f, 'rb') as fh:
    ok, msg = restore_backup(fh.read())
print(msg if ok else ('ERROR: ' + msg))
"

systemctl start lekai-backend lekai-frontend 2>/dev/null || true
echo "恢复完成。"
