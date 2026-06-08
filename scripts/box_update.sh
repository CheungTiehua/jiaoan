#!/bin/bash
# LeKai 盒子远程更新脚本
# 用法: bash box_update.sh

set -e
APP_DIR="/opt/lekai"
SERVICE="lekai-jiaoan"

echo "更新 LeKai 教案知识库..."

# 停止服务
systemctl stop $SERVICE

# 备份旧版
cp -r $APP_DIR/backend $APP_DIR/backend.bak.$(date +%Y%m%d)
cp -r $APP_DIR/scripts $APP_DIR/scripts.bak.$(date +%Y%m%d)

# 从更新包解压
if [ -f /tmp/lekai_update.tar.gz ]; then
    tar xzf /tmp/lekai_update.tar.gz -C $APP_DIR/
    rm /tmp/lekai_update.tar.gz
fi

# 更新依赖
source $APP_DIR/.venv/bin/activate
pip install -q -r $APP_DIR/scripts/requirements.txt

# 启动
systemctl start $SERVICE

echo "更新完成。"
systemctl status $SERVICE --no-pager
