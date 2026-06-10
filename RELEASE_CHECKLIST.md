# LeKai教案系统 — 发布检查清单

用于正式交付学校/客户前的现场操作验证，每步完成后打勾。

## 发布前准备

- [ ] 1. 拉取最新代码
  ```bash
  git pull origin main
  ```

- [ ] 2. 准备数据目录权限
  ```bash
  mkdir -p data knowledge-base
  chown 10001:10001 data knowledge-base
  ```
  容器内以 `lekai` (uid=10001) 运行，绑定挂载的目录必须可写。

- [ ] 3. 构建 Docker 镜像
  ```bash
  docker compose build --no-cache
  ```

- [ ] 4. 启动服务
  ```bash
  docker compose up -d
  ```

- [ ] 5. 等待服务健康
  ```bash
  docker compose ps  # 确认所有容器状态为 healthy
  curl http://localhost:8000/api/health  # 应返回 {"status":"ok"}
  ```

- [ ] 6. 首次初始化
  浏览器访问 `http://<服务器IP>/` → 按向导设置：
  - 管理员密码（至少 4 位，不要用默认密码）
  - DeepSeek API Key

- [ ] 7. 生成首次备份
  ```bash
  # 首次部署（知识库尚未上传教案）
  python scripts/pre_upgrade_check.py --allow-empty-kb

  # 后续升级前（已有知识库）
  python scripts/pre_upgrade_check.py
  ```
  确认输出 `PRE-UPGRADE CHECK PASSED`。

- [ ] 8. 验证 DeepSeek API Key
  确认初始化向导中 API Key 已生效：
  ```bash
  curl http://localhost:8000/api/health/deep \
    -H "Authorization: Bearer <admin_token>"
  ```
  确认 `api_key_ok: true`。

- [ ] 9. 准备 embedding 模型
  ```bash
  python scripts/prepare_offline_model.py
  ```
  确认输出 `OFFLINE MODEL READY`。
  如果失败，按 `docs/OFFLINE_MODEL.md` 手动预置。

- [ ] 10. 上传至少一篇优秀教案
  管理端 → "教案入库" → 上传 `.md` 文件。
  确认返回 `ok: true`，前端显示入库成功。

- [ ] 11. 运行入库
  上一步上传教案时自动触发入库。确认知识库不为空：
  ```bash
  curl http://localhost:8000/api/admin/chunks \
    -H "Authorization: Bearer <admin_token>" \
    | python -c "import sys,json; d=json.load(sys.stdin); print(f'chunks: {d[\"total\"]}')"
  ```
  确认 chunks > 0。

- [ ] 12. 运行验收脚本
  ```bash
  ACCEPT_BASE_URL=http://127.0.0.1:8000 \
  ACCEPT_ADMIN_USER=admin \
  ACCEPT_ADMIN_PASSWORD=<管理员密码> \
  python scripts/acceptance_check.py
  ```
  确认输出 `ACCEPTANCE PASSED`。

- [ ] 13. 创建测试教师账号
  管理端 → "用户管理" → 创建 `test_teacher` 账号。
  用 `test_teacher` 登录教师端确认可正常使用。

- [ ] 14. 完成一次教案生成
  教师端 → 选择年级/课文 → 点击生成。
  确认四部分内容（考点分析、同行参考、教案、辅导说明）均正常输出。

- [ ] 15. 完成一次导出
  教师端 → 历史记录 → 点击导出。
  选择 Markdown 和 Word 格式各导出一次，确认文件可正常打开。

- [ ] 16. 完成一次备份
  管理端 → "系统备份" → 下载备份 zip。
  确认备份包可正常解压，包含 `data/users.json`、教案文件、ChromaDB 数据。

- [ ] 17. 保存交付记录
  将以下信息记录存档：
  - 服务器 IP 地址
  - 管理员账号密码（安全保存）
  - MAC 地址
  - DeepSeek API Key 备注
  - 部署日期
  - 版本号
  - 备份文件路径

## 交付确认

全部 17 项完成后，项目达到正式交付标准。

交付日期：________  交付人：________  确认人：________
