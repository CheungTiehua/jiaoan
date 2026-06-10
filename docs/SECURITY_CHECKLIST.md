# LeKai教案系统 — 安全审计清单

## 认证与授权

- [ ] 默认管理员密码不得用于正式环境（首次启动向导必须修改）
- [ ] 管理员密码至少 4 位
- [ ] 密码使用 PBKDF2-SHA256 存储，60 万次迭代，随机盐
- [ ] Token 有效期 7 天，服务重启不丢失
- [ ] `/api/health/deep` 需要 admin 或 reviewer 权限
- [ ] `/api/register` 仅 admin 可调用（关闭公开注册）

## API Key 安全

- [ ] DeepSeek API Key 不得提交到 Git（已在 `.gitignore` 中排除 `.env`）
- [ ] `.env` 文件权限为 600
- [ ] `data/api_key.json` 权限为 600
- [ ] 备份包中 `.env` 的 `DEEPSEEK_API_KEY` 已脱敏为 `***masked***`
- [ ] 日志不得输出完整 API Key
- [ ] 建议定期更换 API Key（每季度或每学期）

## 输入验证

- [ ] 上传文件大小限制为 5MB
- [ ] 上传文件类型限制为 `.md`、`.docx`、`.txt`
- [ ] 文档内容长度校验（至少 100 字符）
- [ ] 用户名仅允许字母、数字、下划线和连字符
- [ ] 用户名至少 2 个字符，密码至少 4 个字符

## 文件系统安全

- [ ] 文件名使用 `os.path.basename` 防目录穿越
- [ ] 路径使用 `resolve()` 防 Zip Slip 攻击
- [ ] 备份恢复仅允许写入 `data/`、`knowledge-base/`、`chroma_db/`
- [ ] 备份写入使用原子写入（tmp + rename）
- [ ] 用户数据写入使用 `fcntl` 文件锁防并发

## 网络安全

- [ ] 速率限制：登录 10次/分钟，注册 5次/5分钟，生成 20次/分钟
- [ ] Nginx 安全头：X-Content-Type-Options、X-Frame-Options、X-XSS-Protection
- [ ] Nginx API 限流：30r/s
- [ ] 生产环境 CORS 不应使用 `*`，配置 `LEKAI_CORS_ORIGINS` 环境变量

## 备份安全

- [ ] Zip Bomb 三层防护：单文件 ≤ 100MB、压缩比 ≤ 100x、总量 ≤ 500MB
- [ ] API Key 在备份包中脱敏
- [ ] 备份恢复前路径验证
- [ ] 建议定期备份（每日自动 + 升级前手动）

## 部署安全

- [ ] Docker 容器以非 root 用户运行
- [ ] 敏感文件权限 600（`.env`、`data/api_key.json`、`data/users.json`）
- [ ] 生产环境移除开发调试信息
- [ ] 建议定期更新依赖（`pip list --outdated`、`npm outdated`）

## 代码级检查确认

| 检查项 | 状态 |
|--------|------|
| API Key 不会被日志打印 | 已确认（日志仅输出错误摘要） |
| 备份包 `.env` 脱敏 | 已确认（`***masked***` 替换） |
| `data/api_key.json` chmod 600 | 已确认（`_os2.chmod(key_file, 0o600)`） |
| 上传大小限制 5MB | 已确认（`len(data) > 5 * 1024 * 1024`） |
| 恢复白名单仅 data/knowledge-base/chroma_db | 已确认 |
| 速率限制线程安全 | 已确认（内存字典 + 无锁清理） |
| 原子写入防数据损坏 | 已确认（tmp + rename） |
