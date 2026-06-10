# LeKai 交付资料包

这个目录是正式交付时给学校、网管、管理员和验收人员使用的资料总入口。

> 说明：为避免破坏仓库中已有文档路径，本目录不重复复制原文档，而是集中索引所有交付资料。实际文档仍保留在原路径，后续维护只改一处，避免版本不一致。

---

## 1. 交付前必看

| 文件 | 用途 | 给谁看 |
|---|---|---|
| [`../README.md`](../README.md) | 产品总说明 / 白皮书 / 功能架构 | 负责人、校方、开发 |
| [`../RELEASE_CHECKLIST.md`](../RELEASE_CHECKLIST.md) | 正式交付前逐项打勾清单 | 交付人员、网管 |
| [`../CHANGELOG.md`](../CHANGELOG.md) | 版本变更记录 | 负责人、开发、验收人员 |

---

## 2. 部署与运维资料

| 文件 | 用途 | 给谁看 |
|---|---|---|
| [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) | Docker 部署、初始化、端口、目录权限、常用命令 | 网管、部署人员 |
| [`../docs/OFFLINE_MODEL.md`](../docs/OFFLINE_MODEL.md) | 离线模型准备，解决学校网络无法下载模型的问题 | 网管、部署人员 |
| [`../docs/BACKUP_RESTORE.md`](../docs/BACKUP_RESTORE.md) | 备份包内容、恢复方式、注意事项 | 网管、售后 |
| [`../docs/TROUBLESHOOTING.md`](../docs/TROUBLESHOOTING.md) | 登录、API Key、生成失败、知识库、导图、导出等故障排查 | 网管、售后 |

---

## 3. 管理员与学校使用资料

| 文件 | 用途 | 给谁看 |
|---|---|---|
| [`../docs/ADMIN_GUIDE.md`](../docs/ADMIN_GUIDE.md) | 创建账号、角色权限、上传教案、审核、导出、思维导图 | 校长、教研组长、管理员 |
| [`../docs/SECURITY_CHECKLIST.md`](../docs/SECURITY_CHECKLIST.md) | 安全检查：权限、API Key、备份脱敏、非 root 等 | 技术负责人、网管 |

---

## 4. 验收资料

| 文件 | 用途 | 给谁看 |
|---|---|---|
| [`../docs/ACCEPTANCE.md`](../docs/ACCEPTANCE.md) | 自动验收脚本说明、验收项、通过标准 | 验收人员、交付人员 |
| [`../scripts/acceptance_check.py`](../scripts/acceptance_check.py) | 自动验收脚本，检查登录、权限、备份、导图、导出等核心链路 | 验收人员、开发 |
| [`../scripts/pre_upgrade_check.py`](../scripts/pre_upgrade_check.py) | 升级前检查和备份脚本 | 网管、开发 |
| [`../scripts/prepare_offline_model.py`](../scripts/prepare_offline_model.py) | 离线模型准备脚本 | 网管、部署人员 |

---

## 5. 推荐交付流程

正式交付时按这个顺序走：

1. 先看 [`../RELEASE_CHECKLIST.md`](../RELEASE_CHECKLIST.md)。
2. 按 [`../docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md) 完成部署。
3. 按 [`../docs/OFFLINE_MODEL.md`](../docs/OFFLINE_MODEL.md) 确认模型可用。
4. 初始化管理员账号和 DeepSeek API Key。
5. 上传至少一篇优秀教案入库。
6. 运行：

```bash
ACCEPT_ADMIN_USER=admin ACCEPT_ADMIN_PASSWORD=<管理员密码> python scripts/acceptance_check.py
```

7. 确认输出：

```text
ACCEPTANCE PASSED
```

8. 按 [`../docs/ADMIN_GUIDE.md`](../docs/ADMIN_GUIDE.md) 给学校管理员培训。
9. 下载一次备份，确认备份包可解压。
10. 将交付信息记录到交付台账中。

---

## 6. 交付签字建议

交付时可以使用以下结论：

```text
LeKai 教案系统 K9-AI v1.0 已完成部署、初始化、知识库入库、功能验收、导出测试和备份检查。
系统具备教师备课、教案生成、辅导说明、双思维导图、历史记录、教案导出、校本审核、知识库管理和备份恢复能力。
经自动验收脚本检查，核心链路通过，可交付使用。
```

---

## 7. 注意事项

- 本目录是交付资料总入口，不是原文档副本。
- 原文档仍在 `docs/`、`scripts/` 和仓库根目录中维护。
- 后续新增交付资料时，先放到合适目录，再在本文件补索引。
- 不要把真实 DeepSeek API Key、管理员密码、学校内网信息写进仓库。
