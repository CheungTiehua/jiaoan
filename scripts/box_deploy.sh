#!/bin/bash
# LeKai教案知识库 — Linux 盒子完整部署（后端+前端+Nginx）
# 用法: sudo bash box_deploy.sh

set -e
APP_DIR="/opt/lekai"
SERVICE_BACKEND="lekai-backend"
SERVICE_FRONTEND="lekai-frontend"
SERVICE_NGINX="lekai-nginx"
APP_USER="lekai"
NGINX_PORT=${1:-80}
BACKEND_PORT=8000
FRONTEND_PORT=3000

echo "========================================"
echo "  LeKai 教案知识库 — 盒子完整部署"
echo "========================================"

# 0. 创建非特权用户
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/false "$APP_USER"
    echo "[0/6] 创建用户: $APP_USER"
fi

# 1. 系统依赖
echo "[1/6] 安装系统依赖..."
apt-get update -qq
apt-get install -y -qq python3 python3-pip python3-venv nginx curl nodejs npm avahi-daemon

# mDNS 主机名：网管老师在浏览器输入 lekai.local 即可访问
echo "lekai" > /etc/hostname
hostname lekai
sed -i 's/^#host-name=.*/host-name=lekai/' /etc/avahi/avahi-daemon.conf 2>/dev/null || true
systemctl enable avahi-daemon
systemctl restart avahi-daemon

# 2. 目录结构
echo "[2/6] 创建目录..."
mkdir -p $APP_DIR/{backend,frontend,scripts,knowledge-base,data,logs,chroma_db}
mkdir -p $APP_DIR/data/{history,feedback,annotations,reviews,collab,_backup}

# 3. 复制文件
echo "[3/6] 复制应用文件..."
cp -r backend/ $APP_DIR/
cp -r scripts/ $APP_DIR/
cp -r knowledge-base/ $APP_DIR/
cp .env $APP_DIR/ 2>/dev/null || echo "  请手动创建 $APP_DIR/.env"

# 4. Python venv
echo "[4/6] 安装 Python 依赖..."
python3 -m venv $APP_DIR/.venv
source $APP_DIR/.venv/bin/activate
pip install -q -r $APP_DIR/scripts/requirements.txt

# 5. 前端构建
echo "[5/6] 构建前端..."
cd frontend
npm ci --silent
NEXT_PUBLIC_API_URL=/api npm run build
cp -r .next/standalone $APP_DIR/frontend/
cp -r .next/static $APP_DIR/frontend/.next/static 2>/dev/null || true
cp -r public $APP_DIR/frontend/ 2>/dev/null || true
cd ..

# 6. systemd + Nginx
echo "[6/6] 配置服务..."

# Backend service
cat > /etc/systemd/system/${SERVICE_BACKEND}.service << EOF
[Unit]
Description=LeKai Backend
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/.venv/bin/uvicorn backend.main:app --host 127.0.0.1 --port $BACKEND_PORT --proxy-headers
Restart=always
RestartSec=5
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=$APP_DIR/data $APP_DIR/chroma_db $APP_DIR/logs

[Install]
WantedBy=multi-user.target
EOF

# Frontend service
cat > /etc/systemd/system/${SERVICE_FRONTEND}.service << EOF
[Unit]
Description=LeKai Frontend
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR/frontend
Environment=NODE_ENV=production
Environment=PORT=$FRONTEND_PORT
ExecStart=node server.js
Restart=always
RestartSec=5
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF

# Nginx config
cat > /etc/nginx/sites-available/lekai << 'NGINXEOF'
server {
    listen 80;
    server_name _;
    client_max_body_size 50m;

    # 安全头
    add_header X-Content-Type-Options nosniff;
    add_header X-Frame-Options SAMEORIGIN;
    add_header X-XSS-Protection "1; mode=block";

    # API 限流: 30次/秒
    limit_req_zone $binary_remote_addr zone=api:10m rate=30r/s;
    limit_req_status 429;

    # 前端
    location / {
        proxy_pass http://127.0.0.1:FRONTEND_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API
    location /api/ {
        limit_req zone=api burst=10 nodelay;
        proxy_pass http://127.0.0.1:BACKEND_PORT/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 30s;
    }

    # 健康检查
    location /health {
        proxy_pass http://127.0.0.1:BACKEND_PORT/api/health;
    }
}
NGINXEOF

sed -i "s/FRONTEND_PORT/$FRONTEND_PORT/g" /etc/nginx/sites-available/lekai
sed -i "s/BACKEND_PORT/$BACKEND_PORT/g" /etc/nginx/sites-available/lekai
ln -sf /etc/nginx/sites-available/lekai /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# 权限
chown -R $APP_USER:$APP_USER $APP_DIR
chmod 600 $APP_DIR/.env 2>/dev/null || true

# 启动
systemctl daemon-reload
systemctl enable $SERVICE_BACKEND $SERVICE_FRONTEND nginx
systemctl restart nginx
systemctl start $SERVICE_BACKEND $SERVICE_FRONTEND

echo ""
echo "========================================"
echo "  部署完成！"
echo ""
echo "  访问方式:"
echo "    浏览器打开 http://lekai.local"
echo "    （若打不开，请查看路由器DHCP列表获取盒子IP）"
echo ""
echo "  状态: systemctl status $SERVICE_BACKEND $SERVICE_FRONTEND nginx"
echo "  日志: journalctl -u $SERVICE_BACKEND -f"
echo "========================================"

# 7. 生成备份 token + cron 自动备份
echo "[7/7] 配置自动备份..."

# 生成永不重复的备份 token
BACKUP_TOKEN=$(python3 -c "import secrets; print(secrets.token_hex(32))")
echo "$BACKUP_TOKEN" > $APP_DIR/.backup_token
chmod 600 $APP_DIR/.backup_token
chown $APP_USER:$APP_USER $APP_DIR/.backup_token

# 将 token 注入 auth 系统（重启后生效）
python3 -c "
import json, os
tf = '$APP_DIR/.backup_token'
if os.path.exists(tf):
    tok = open(tf).read().strip()
    # 将 backup token 作为系统级 session 写入
    sessions_file = '$APP_DIR/data/sessions.json'
    sessions = {}
    import sys; sys.path.insert(0, '$APP_DIR')
    from auth import load_sessions, save_sessions
    sessions = load_sessions()
    sessions[tok] = {'username': 'system', 'created_at': 0, 'expires_at': 9999999999}
    save_sessions(sessions)
"

# cron: 每天凌晨 3 点备份
(crontab -u root -l 2>/dev/null; echo "0 3 * * * bash $APP_DIR/scripts/auto_backup.sh >> $APP_DIR/logs/backup.log 2>&1") | crontab -u root -

# 挂载点提示
echo "提示: 请将第二块 SSD 挂载到 /mnt/backup"
