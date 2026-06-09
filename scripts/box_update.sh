#!/bin/bash
# LeKai 盒子更新脚本 — 带校验+回滚
set -e

APP_DIR="/opt/lekai"
UPDATE_FILE="/tmp/lekai_update.tar.gz"
UPDATE_SHA="/tmp/lekai_update.sha256"

echo "更新 LeKai 教案知识库..."

# 1. 校验更新包
if [ ! -f "$UPDATE_FILE" ]; then
    echo "错误: 找不到更新包 $UPDATE_FILE"
    exit 1
fi
if [ -f "$UPDATE_SHA" ]; then
    EXPECTED=$(cat "$UPDATE_SHA" | awk '{print $1}')
    ACTUAL=$(sha256sum "$UPDATE_FILE" | awk '{print $1}')
    if [ "$EXPECTED" != "$ACTUAL" ]; then
        echo "错误: SHA256 校验失败！"
        echo "  期望: $EXPECTED"
        echo "  实际: $ACTUAL"
        exit 1
    fi
    echo "SHA256 校验通过"
fi

# 2. 预检查：解压到临时目录验证结构
TEMP_DIR=$(mktemp -d)
tar xzf "$UPDATE_FILE" -C "$TEMP_DIR"
if [ ! -d "$TEMP_DIR/backend" ]; then
    echo "错误: 更新包缺少 backend/ 目录"
    rm -rf "$TEMP_DIR"
    exit 1
fi
rm -rf "$TEMP_DIR"

# 3. 停止服务
systemctl stop lekai-backend lekai-frontend

# 4. 备份当前版本
BACKUP_TAG=$(date +%Y%m%d_%H%M%S)
cp -r $APP_DIR/backend $APP_DIR/backend.bak.$BACKUP_TAG
cp -r $APP_DIR/scripts $APP_DIR/scripts.bak.$BACKUP_TAG
cp -r $APP_DIR/frontend $APP_DIR/frontend.bak.$BACKUP_TAG 2>/dev/null || true

# 5. 解压覆盖
tar xzf "$UPDATE_FILE" -C $APP_DIR/
rm -f "$UPDATE_FILE" "$UPDATE_SHA"

# 6. 更新依赖
source $APP_DIR/.venv/bin/activate
pip install -q -r $APP_DIR/scripts/requirements.txt

# 7. 启动
systemctl start lekai-backend lekai-frontend
sleep 5

# 8. 健康检查
if curl -sf http://127.0.0.1/api/health > /dev/null 2>&1; then
    echo "健康检查通过"

    # 保留最近3个备份
    for d in $APP_DIR/backend.bak.*; do
        echo "$d"
    done | sort | head -n -3 | while read d; do rm -rf "$d"; done
    for d in $APP_DIR/scripts.bak.*; do
        echo "$d"
    done | sort | head -n -3 | while read d; do rm -rf "$d"; done

    echo "更新完成。"
else
    echo "错误: 健康检查失败，执行回滚..."

    systemctl stop lekai-backend lekai-frontend
    rm -rf $APP_DIR/backend $APP_DIR/scripts $APP_DIR/frontend
    cp -r $APP_DIR/backend.bak.$BACKUP_TAG $APP_DIR/backend
    cp -r $APP_DIR/scripts.bak.$BACKUP_TAG $APP_DIR/scripts
    cp -r $APP_DIR/frontend.bak.$BACKUP_TAG $APP_DIR/frontend 2>/dev/null || true
    systemctl start lekai-backend lekai-frontend

    echo "已回滚到 $BACKUP_TAG"
    exit 1
fi
