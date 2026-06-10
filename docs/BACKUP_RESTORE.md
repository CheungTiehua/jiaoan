# LeKai教案系统 — 备份与恢复指南

## 备份包含的内容

| 内容 | 路径 | 说明 |
|------|------|------|
| 用户数据 | `data/users.json` | 所有用户账号和角色信息 |
| 知识库教案 | `knowledge-base/*.md` | 已格式化的教案文件 |
| ChromaDB | `chroma_db/*` | 向量数据库（单文件 < 50MB） |
| 配置示例 | `config.env.example` | `.env` 脱敏版（API Key 已替换为 `***masked***`） |
| 元信息 | `backup_meta.json` | 版本号和时间戳 |

## 备份不包含的内容

- **DeepSeek API Key**：`.env` 中的 `DEEPSEEK_API_KEY` 会被替换为 `***masked***`
- **会话 Token**：`data/sessions.json`
- **大体积 ChromaDB 文件**：超过 50MB 的单个文件
- **模型缓存**：`.cache/` 目录
- **构建产物**：`.next/`、`__pycache__/`
- **虚拟环境**：`.venv/`

## 创建备份

### 方式一：管理端（推荐）

进入管理端 → "系统备份" → 点击下载，浏览器自动下载 zip 文件。

### 方式二：API 调用

```bash
curl -X POST http://localhost:8000/api/admin/backup \
  -H "Authorization: Bearer <admin_token>" \
  -o lekai_backup.zip
```

### 方式三：自动备份

部署 `scripts/auto_backup.sh` 到 crontab 实现每日自动备份。

## 恢复备份

### 方式一：管理端

进入管理端 → "备份恢复" → 上传备份 zip 文件。

### 方式二：API 调用

```bash
curl -X POST http://localhost:8000/api/admin/restore \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@lekai_backup.zip"
```

## 白名单恢复范围

恢复仅允许覆盖以下三个目录：

- `data/` — 用户数据
- `knowledge-base/` — 教案文件
- `chroma_db/` — 向量数据库

恢复过程中自动拒绝写入其他路径，防止路径穿越攻击。

## 恢复后建议重启服务

```bash
docker compose restart
```

原因：

1. 后端内存中的 BM25 索引需要重新从 ChromaDB 加载
2. 缓存的用户 session 信息需要刷新
3. ChromaDB PersistentClient 需要重新连接

## 安全防护

备份恢复内置以下安全措施：

- **Zip Bomb 防护**：单文件 ≤ 100MB，压缩比 ≤ 100x，总量 ≤ 500MB
- **路径穿越防护**：resolve() + startswith 限制在项目目录内
- **白名单机制**：仅允许覆盖 `data/`、`knowledge-base/`、`chroma_db/`
- **API Key 脱敏**：备份包中的 `.env` 内容已脱敏

## 验证恢复结果

### 验证用户数据已恢复

```bash
# 检查 users.json
docker compose exec backend cat data/users.json | python -m json.tool
```

### 验证知识库已恢复

```bash
# 查看教案文件
ls -la knowledge-base/

# 通过 API 查看 chunks 数量
curl http://localhost:8000/api/admin/chunks \
  -H "Authorization: Bearer <admin_token>"
```

### 验证 ChromaDB 已恢复

```bash
# 检查 ChromaDB 目录
ls -la chroma_db/

# 通过 API 查看
curl http://localhost:8000/api/health/deep \
  -H "Authorization: Bearer <admin_token>"
```

回应中的 `chunks` 字段应 > 0。
