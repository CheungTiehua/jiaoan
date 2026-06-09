#!/bin/bash
# LeKai教案知识库 — Linux 盒子部署脚本
# 用法: sudo bash box_deploy.sh

set -e
APP_DIR="/opt/lekai"
SERVICE_NAME="lekai-jiaoan"
PORT=${1:-8000}

echo "========================================"
echo "  LeKai 教案知识库 — Linux 盒子部署"
echo "========================================"

# 1. 系统依赖
echo "[1/5] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv

# 2. 创建目录
echo "[2/5] 创建应用目录..."
mkdir -p $APP_DIR/{backend,frontend,scripts,knowledge-base,data,logs,chroma_db}

# 3. 复制文件（假设当前目录即项目根）
echo "[3/5] 复制应用文件..."
cp -r backend/ $APP_DIR/
cp -r scripts/ $APP_DIR/
cp -r knowledge-base/ $APP_DIR/
cp -r .env $APP_DIR/ 2>/dev/null || echo "  请手动创建 $APP_DIR/.env"

# 4. Python 虚拟环境
echo "[4/5] 安装 Python 依赖..."
python3 -m venv $APP_DIR/.venv
source $APP_DIR/.venv/bin/activate
pip install -q -r $APP_DIR/scripts/requirements.txt
pip install -q fastapi uvicorn pydantic chromadb sentence-transformers rank-bm25 jieba

# 5. systemd 服务
echo "[5/5] 配置 systemd 开机自启..."
cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=LeKai Jiaoan Knowledge Base
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
Environment="LEKAI_PORT=$PORT"
ExecStart=$APP_DIR/.venv/bin/python $APP_DIR/backend/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable $SERVICE_NAME
systemctl start $SERVICE_NAME

echo ""
echo "========================================"
echo "  部署完成！"
echo "  服务: systemctl status $SERVICE_NAME"
echo "  访问: http://\$(hostname -I | awk '{print \$1}'):$PORT"
echo "  日志: journalctl -u $SERVICE_NAME -f"
echo "========================================"
