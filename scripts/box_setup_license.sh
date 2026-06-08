#!/bin/bash
# LeKai 盒子授权配置
# 用法: sudo bash box_setup_license.sh [MAC地址]
# 不传MAC则自动检测本机MAC

APP_DIR="/opt/lekai"
MAC=${1}

if [ -z "$MAC" ]; then
    MAC=$(ip link show | grep ether | awk '{print $2}' | head -1)
fi

if [ -z "$MAC" ]; then
    echo "错误: 无法获取 MAC 地址，请手动指定"
    echo "用法: bash box_setup_license.sh 00:11:22:33:44:55"
    exit 1
fi

echo "$MAC" > $APP_DIR/.license
chmod 600 $APP_DIR/.license
echo "授权完成: MAC=$MAC"
echo ""
echo "多台设备: 每行一个 MAC 地址"
echo "开发模式: echo 'any' > $APP_DIR/.license"
