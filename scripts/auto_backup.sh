#!/bin/bash
# LeKai 自动备份 — 每天凌晨执行，由 cron 调度
# 备份目标: /mnt/backup/（第二块 SSD 挂载点）

# 互斥锁：防止上一次备份未完成时 cron 再次触发
exec 200>/var/lock/lekai_backup.lock
flock -n 200 || exit 0

BACKUP_DIR="/mnt/backup"
RETENTION_DAYS=7
TOKEN_FILE="/opt/lekai/.backup_token"

[ -d "$BACKUP_DIR" ] || { echo "备份盘未挂载: $BACKUP_DIR"; exit 1; }

TOKEN=$(cat "$TOKEN_FILE" 2>/dev/null)
[ -z "$TOKEN" ] && { echo "备份 token 不存在"; exit 1; }

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/lekai_backup_${TIMESTAMP}.zip"

if curl -sf -o "$BACKUP_FILE" -H "Authorization: Bearer $TOKEN" http://localhost/api/admin/backup; then
    echo "备份成功: $BACKUP_FILE"
else
    echo "备份失败"
    rm -f "$BACKUP_FILE"
    exit 1
fi

# 清理旧备份，保留最近 N 天
find "$BACKUP_DIR" -name "lekai_backup_*.zip" -mtime +$RETENTION_DAYS -delete
