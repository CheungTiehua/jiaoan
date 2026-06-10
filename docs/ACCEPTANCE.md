# LeKai教案系统 — 验收脚本指南

## 前置条件

1. 后端服务已启动（`http://127.0.0.1:8000`）
2. 已创建管理员账号（默认 `admin`）
3. 管理员账号可正常登录

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `LEKAI_ACCEPTANCE_MODE` | 是 | `0` | 必须设为 `1`（验收模式开关） |
| `ACCEPT_ADMIN_USER` | 是 | - | 管理员用户名 |
| `ACCEPT_ADMIN_PASSWORD` | 是 | - | 管理员密码 |
| `ACCEPT_BASE_URL` | 否 | `http://127.0.0.1:8000` | 后端地址 |
| `ACCEPT_SKIP_REAL_MINDMAP` | 否 | - | 设为 `1` 跳过真实导图生成 |

> 正式生产环境默认关闭 `LEKAI_ACCEPTANCE_MODE`，仅交付验收时临时开启，验收完成后关闭并重启后端。

## 运行命令

```bash
# 本地运行
LEKAI_ACCEPTANCE_MODE=1 \
ACCEPT_ADMIN_USER=admin \
ACCEPT_ADMIN_PASSWORD=你的密码 \
python scripts/acceptance_check.py

# 指定后端地址
LEKAI_ACCEPTANCE_MODE=1 \
ACCEPT_BASE_URL=http://127.0.0.1:8000 \
ACCEPT_ADMIN_USER=admin \
ACCEPT_ADMIN_PASSWORD=你的密码 \
python scripts/acceptance_check.py

# 跳过真实导图生成
LEKAI_ACCEPTANCE_MODE=1 \
ACCEPT_SKIP_REAL_MINDMAP=1 \
ACCEPT_ADMIN_USER=admin \
ACCEPT_ADMIN_PASSWORD=你的密码 \
python scripts/acceptance_check.py

# Docker 环境（必须先让后端容器以验收模式启动）
LEKAI_ACCEPTANCE_MODE=1 docker compose up -d --force-recreate backend

# 运行验收（脚本本身也需要这个环境变量来检查）
LEKAI_ACCEPTANCE_MODE=1 \
ACCEPT_ADMIN_USER=admin \
ACCEPT_ADMIN_PASSWORD=你的密码 \
python scripts/acceptance_check.py

# 验收完成后关闭验收模式
LEKAI_ACCEPTANCE_MODE=0 docker compose up -d --force-recreate backend
```

> 注意：不能用 `docker compose exec -e` 只给脚本进程设置环境变量，这不会改变已运行的后端容器环境。必须先重建后端容器使其以 `LEKAI_ACCEPTANCE_MODE=1` 启动，测试钩子才能生效。

验收结束后脚本会自动清理 `acctest_` 开头的测试用户、历史记录、审核记录和 session。清理失败不影响验收结论，但会输出 `[WARN]` 提示。

## 验收项目说明

| # | 项目 | 检查内容 |
|---|------|---------|
| 1 | `/api/health` 可访问 | 后端基础健康检查返回 200 |
| 2 | `/api/health/deep` 未登录拒绝 | 未认证用户访问深度健康检查应被拒绝（401/403） |
| 3 | admin 可访问 `/api/health/deep` | 管理员可正常访问深度健康检查 |
| 4 | admin 可创建 teacher 账号 | 管理员通过 `/api/register` 创建教师账号 |
| 5 | teacher 无法访问 health/deep | 普通教师访问深度健康检查应被拒绝 |
| 6 | 备份包含 `data/users.json` | 备份包内用户数据路径正确 |
| 7 | 入库失败时 `ok=False` | 短文件上传被拒绝或返回 `ok:false` |
| 8 | RuntimeError 透出真实错误 | admin 通过请求头触发测试错误，应返回 400 且 detail 包含"验收用错误" |
| 9 | 入库失败时 `ok=False` | `force_ingest_fail` 文件名触发模拟入库失败，应返回 200 + `ok:false` |
| 10 | mindmap 接口必须登录 | 未登录调用应返回 401/403 |
| 11 | mindmap 空输入校验 | 空 lesson/lesson_plan 返回 400 |
| 12 | mindmap 太短教案校验 | lesson_plan 少于 100 字符返回 400 |
| 13 | mindmap 测试钩子 | admin 触发 X-Accept-Force-Mindmap-Error 返回 400 + detail |
| 14 | mindmap 双导图生成 | 返回 Mermaid 格式双导图 + outline |
| 15 | mindmap 历史保存 | 导图保存后可读回 |
| 16 | mindmap 导出附录（MD） | 含导图 Markdown 导出包含附录 |
| 17 | mindmap 导出附录（DOCX） | 含导图 DOCX 导出包含附录 |

## 跳过真实生成

如果不想消耗 DeepSeek API 额度：

```bash
ACCEPT_SKIP_REAL_MINDMAP=1 \
ACCEPT_ADMIN_USER=admin \
ACCEPT_ADMIN_PASSWORD=你的密码 \
python scripts/acceptance_check.py
```

设置后跳过第 14-17 项（双导图生成/历史保存/导出附录），但仍执行第 10-13 项（权限/校验/测试钩子）。

## 验收标准

全部项通过时输出：

```text
========================================
PASSED: 17  FAILED: 0
ACCEPTANCE PASSED
```

并以退出码 0 退出。使用 `ACCEPT_SKIP_REAL_MINDMAP=1` 时最少通过 12 项。

## 失败时排查

### 管理员登录失败
- 检查 `ACCEPT_ADMIN_USER` 和 `ACCEPT_ADMIN_PASSWORD` 是否正确
- 确认后端服务是否正常运行

### 第 2/3/5 项失败
- 检查角色权限体系是否正确配置
- 确认 `admin` 账号角色为 `admin`

### 第 6 项失败
- 确认 `data/users.json` 文件存在
- 检查备份逻辑中路径拼接是否正确

### 第 8 项失败
- 确认当前用户角色为 `admin`
- 确认请求头 `X-Accept-Force-Rag-Error: 1` 正确发送
- 确认 `RuntimeError` 被 `except RuntimeError` 捕获并返回 400

### 第 9 项失败
- 确认上传文件名包含 `force_ingest_fail`
- 确认文件内容超过 100 字符
- 确认后端测试钩子在 DeepSeek 格式化之前触发
