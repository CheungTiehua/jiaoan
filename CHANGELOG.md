# Changelog

## v1.0.0 (2026-06)

- 完成账号权限闭环（teacher / reviewer / admin 三级角色）
- 完成 DeepSeek API Key 持久化（.env + data/api_key.json 双写）
- 完成备份恢复白名单（data/、knowledge-base/、chroma_db/）
- 完成备份 API Key 脱敏与 Zip Bomb 三层防护
- 完成上传入库失败识别（ok:false + 错误信息透出）
- 完成交付验收脚本（9 项自动化检查）
- 完成健康检查权限保护（deep 端点仅 admin/reviewer 可访问）
- 完成 PBKDF2-SHA256 密码存储（60 万次迭代）
- 完成速率限制（登录/注册/生成分级限流）
- 完成原子写入 + fcntl 文件锁防并发
- 完成离线 embedding 模型预置方案（LEKAI_MODEL_DIR）
- 完成升级前自动备份脚本
- 完成交付文档体系（部署/管理/验收/排障/备份/离线模型）
- 完成安全审计清单与发布清单
