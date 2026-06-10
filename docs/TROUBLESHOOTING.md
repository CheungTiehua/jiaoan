# LeKai教案系统 — 故障排查指南

## 1. 登录失败

**现象**：输入用户名密码后提示"用户名或密码错误"

**排查**：
- 确认用户名拼写正确
- 检查 `data/users.json` 文件是否存在
- 查看后端日志：`docker compose logs backend | grep login`

## 2. DeepSeek API Key 未配置

**现象**：生成教案时报错"请配置 DeepSeek API Key"

**排查**：
- 检查 `.env` 文件中 `DEEPSEEK_API_KEY` 是否已设置
- 检查 `data/api_key.json` 文件是否存在且内容有效
- 重新运行首次启动向导设置 API Key

## 3. API Key 无效

**现象**：生成教案时返回 500 错误

**排查**：
- 进入管理端 → "系统健康" 查看 `api_key_ok` 状态
- 在 DeepSeek 平台确认 Key 是否已过期或余额不足
- 更新 `.env` 和 `data/api_key.json` 后重启服务

## 4. DeepSeek 超时

**现象**：生成教案长时间无响应

**排查**：
- DeepSeek API 默认超时 300 秒，复杂教案生成可能需要 30-60 秒
- 检查服务器网络连接：`curl https://api.deepseek.com`
- 如持续超时，检查 `DEEPSEEK_BASE_URL` 是否被防火墙拦截

## 5. 429 限流

**现象**：返回 `429 Too Many Requests`

**排查**：
- 生成端点：20次/分钟限制，等待 1 分钟后重试
- 登录端点：10次/分钟限制
- 注册端点：5次/5分钟限制
- 确认是否多人共用同一账号触发限流

## 6. Embedding 模型加载失败

**现象**：启动时报错 `Embedding 模型加载失败`

**排查**：
- 检查网络连接（首次需从 HuggingFace 下载模型）
- 设置 `LEKAI_MODEL_DIR` 指向预下载的模型目录
- 运行 `python scripts/prepare_offline_model.py` 检查模型状态
- 离线环境需将 `BAAI/bge-small-zh-v1.5` 模型预置到 `.cache/models/`

## 7. 知识库 chunk 数为 0

**现象**：管理端 → "系统健康" 显示 chunks=0

**排查**：
- 确认是否已上传教案入库
- 上传后检查后端日志确认入库脚本是否成功
- 手动运行入库：`docker compose exec backend python scripts/ingest_knowledge.py`
- 检查 `chroma_db/` 目录是否存在且有数据文件

## 8. 上传教案失败

**现象**：管理端上传教案后报错

**排查**：
- 确认文件格式为 `.md`、`.docx` 或 `.txt`
- 确认文件内容超过 100 字符
- 确认文件大小不超过 5MB
- 检查 `knowledge-base/` 目录是否有写入权限

## 9. 入库失败

**现象**：教案上传成功但入库返回 `ok:false`

**排查**：
- 查看后端日志：`docker compose logs backend | grep "入库失败"`
- 确认 Python 环境和依赖完整
- 手动运行 `scripts/ingest_knowledge.py` 查看详细错误
- 检查 ChromaDB 数据目录权限

## 10. 前端打不开

**现象**：浏览器访问 `http://<IP>/` 无响应

**排查**：
- 确认 Docker 容器运行：`docker compose ps`
- 检查 Nginx 状态：`docker compose logs nginx`
- 检查防火墙是否开放 80 端口
- 检查前端容器是否健康：`docker compose ps frontend`

## 11. 后端健康检查失败

**现象**：`curl http://localhost:8000/api/health` 无响应

**排查**：
- 查看后端日志：`docker compose logs backend --tail=50`
- 确认 `.env` 文件存在
- 检查 MAC 授权：确认 `.license` 文件内容正确
- 检查过期时间：确认 `LEKAI_EXPIRE_DATE` 未过期

## 12. 磁盘空间不足

**现象**：操作报错或服务异常

**排查**：
- 查看磁盘：`df -h`
- 检查 Docker 占用：`docker system df`
- 清理旧日志：`docker compose logs` 的日志轮转配置为 10MB×3
- 清理未使用的 Docker 资源：`docker system prune -a`
- 进入管理端 → "设备信息" 查看磁盘使用率

## 13. 备份恢复后数据未更新

**现象**：恢复备份后数据仍是旧的

**排查**：
- 恢复后必须重启服务以确保索引同步
- 恢复备份会覆盖 `data/`、`knowledge-base/`、`chroma_db/` 三个目录
- 确认备份包中包含目标数据
- 检查恢复过程中是否有报错
- 恢复后运行 `docker compose restart` 刷新内存中的索引和缓存
