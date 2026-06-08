# LeKai教案知识库 — 盒子部署指南

## 硬件参考

| 配置 | 版本 | 成本 | 支持老师数 |
|------|------|------|:--:|
| RK3566, 4GB RAM, 64GB eMMC | 入门版 | ¥150-250 | ≤20 人 |
| RK3588, 8GB RAM, 64GB eMMC | 标准版 | ¥400-600 | ≤50 人 |
| N150/N100, 12GB RAM, 256GB SSD | 旗舰版 | ¥600-800 | ≤100 人 |

均支持 Armbian / Debian / Ubuntu Server。功耗 5-15W。内存占用约 1GB。

## 发货目录结构

```
lekai/
├── backend/           ← FastAPI 后端
├── frontend/.next/    ← Next.js 构建产物
├── scripts/           ← 工具脚本
├── knowledge-base/    ← 种子教案
├── .venv/             ← Python 虚拟环境（含所有依赖）
├── .env               ← DeepSeek API Key
├── .license           ← MAC 地址白名单
└── box_deploy.sh      ← 一键部署脚本
```

## 部署步骤

```bash
# 1. 拷贝到盒子
scp -r lekai/ root@192.168.x.x:/opt/lekai/

# 2. SSH 进盒子，运行部署
ssh root@192.168.x.x
cd /opt/lekai
bash scripts/box_deploy.sh

# 3. 设置授权
bash scripts/box_setup_license.sh

# 4. 验证
curl http://localhost:8000/api/health
```

## MAC 地址授权

```bash
# 查看本机 MAC
ip link show | grep ether | awk '{print $2}' | head -1

# 写入授权
echo "00:11:22:33:44:55" > .license

# 多台设备：每行一个 MAC
# 开发机：echo "any" > .license
```

## 开机自启

部署脚本自动配置 systemd：
```bash
systemctl status lekai-jiaoan   # 查看状态
systemctl restart lekai-jiaoan  # 重启
journalctl -u lekai-jiaoan -f   # 查看日志
```

## 更新流程

```bash
# 本地打包更新
tar czf lekai_update.tar.gz backend/ scripts/

# 传到盒子
scp lekai_update.tar.gz root@192.168.x.x:/tmp/

# 执行更新
ssh root@192.168.x.x "cd /opt/lekai && bash scripts/box_update.sh"
```

## 发货前检查清单

- [ ] `.env` 有 DeepSeek API Key
- [ ] `.license` 是客户 MAC（不是 any）
- [ ] systemd 服务正常运行
- [ ] 管理员能登录（首个注册用户自动 admin）
- [ ] 选课生成教案正常
- [ ] 管理端 `/admin` 可访问
- [ ] 备份下载正常
