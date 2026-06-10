# LeKai教案系统 — 部署指南

## 环境要求

- Docker 20.10+ & Docker Compose v2+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

## Docker Compose 部署

### 1. 准备环境变量

```bash
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key
```

### 2. 准备数据目录

```bash
mkdir -p data knowledge-base
chown 10001:10001 data knowledge-base
```

容器内以 `lekai` (uid=10001) 用户运行，绑定挂载的目录必须可写。

### 3. 构建并启动

```bash
docker compose up -d --build
```

首次构建约需 3-5 分钟（包含 embedding 模型下载）。

### 4. 首次初始化

启动后访问 `http://<服务器IP>/` 进入首次启动向导：

1. 设置管理员密码（至少4位）
2. 输入 DeepSeek API Key
3. 完成后自动创建 `admin` 账号

### 5. 验证服务

```bash
# 后端健康检查
curl http://localhost:8000/api/health

# 前端页面
curl http://localhost:3000

# 通过 Nginx
curl http://localhost/api/health
```

## 管理员账号

首个通过启动向导注册的账号自动成为 `admin`。也可直接在服务器创建：

```bash
# 进入后端容器
docker compose exec backend python -c "
from auth import register_user
print(register_user('admin', 'yourpassword'))
"
```

## DeepSeek API Key 配置

API Key 通过以下方式配置：

1. **首次启动向导**（推荐）
2. **环境变量**：在 `.env` 中设置 `DEEPSEEK_API_KEY=sk-xxx`
3. **已初始化系统**：Key 持久化在 `data/api_key.json`，修改需同时更新 `.env`

## 端口说明

| 端口 | 服务 | 说明 |
|------|------|------|
| 80 | Nginx | 统一入口，代理前端和后端 |
| 3000 | Next.js 前端 | 内部端口，不对外暴露 |
| 8000 | FastAPI 后端 | 内部端口，不对外暴露 |

## 常用命令

```bash
# 启动
docker compose up -d

# 停止
docker compose down

# 重启后端
docker compose restart backend

# 重启所有服务
docker compose restart

# 查看日志
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx

# 查看最近100条日志
docker compose logs --tail=100 backend

# 进入容器
docker compose exec backend bash

# 查看容器状态
docker compose ps

# 更新后重新构建
docker compose up -d --build

# 完全清理（含数据卷）
docker compose down -v
```

## 数据目录

| 目录 | 内容 | 持久化方式 |
|------|------|-----------|
| `data/` | 用户、会话、历史、反馈 | volume |
| `knowledge-base/` | 教案 Markdown 文件 | volume |
| `chroma_db/` | ChromaDB 向量库 | named volume |
| `.cache/` | embedding 模型缓存 | named volume |

## 防火墙

确保开放端口 80：

```bash
# Ubuntu/Debian
ufw allow 80/tcp

# CentOS/RHEL
firewall-cmd --add-port=80/tcp --permanent
firewall-cmd --reload
```
