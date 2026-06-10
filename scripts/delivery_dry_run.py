#!/usr/bin/env python3
"""
LeKai 交付前演练脚本 — 自动生成交付报告

用法:
  ACCEPT_ADMIN_USER=admin ACCEPT_ADMIN_PASSWORD=xxx python scripts/delivery_dry_run.py

功能:
  1. 版本检查
  2. 服务健康检查
  3. 磁盘空间检查
  4. Docker 容器状态检查
  5. 非 root 用户检查
  6. 文件权限检查
  7. 用户数据检查
  8. 知识库检查
  9. Embedding 模型检查
  10. 备份生成测试
  11. API Key 脱敏验证
  12. 思维导图端点检查
  13. 生成演练报告

输出:
  delivery_report_YYYYMMDD_HHMMSS.txt
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ADMIN_USER = os.environ.get("ACCEPT_ADMIN_USER", "")
ADMIN_PASS = os.environ.get("ACCEPT_ADMIN_PASSWORD", "")
BASE = os.environ.get("ACCEPT_BASE_URL", "http://127.0.0.1:8000")

results = []
WARNINGS = 0
ERRORS = 0


def ok(msg: str):
    results.append(f"  ✅ {msg}")


def warn(msg: str):
    global WARNINGS
    WARNINGS += 1
    results.append(f"  ⚠️  {msg}")


def fail(msg: str):
    global ERRORS
    ERRORS += 1
    results.append(f"  ❌ {msg}")


def header(title: str):
    results.append(f"\n{'='*60}")
    results.append(f"  {title}")
    results.append(f"{'='*60}")


def main():
    header("LeKai 交付前演练报告")
    results.append(f"  时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    results.append(f"  项目路径: {PROJECT_ROOT}")

    # 1. 版本
    header("1. 版本信息")
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from config import VERSION
    except Exception:
        VERSION = "unknown"
    ok(f"当前版本: {VERSION}")

    # 2. 服务健康
    header("2. 服务健康")
    import requests
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        if r.status_code == 200:
            ok(f"后端健康: {r.json().get('status', '')}")
        else:
            fail(f"后端健康异常: status={r.status_code}")
    except requests.ConnectionError:
        fail("后端无法连接")
        results.append("\n❌ 后端服务不可用，终止检查")
        return _save_and_exit()
    except Exception as e:
        fail(f"后端健康检查异常: {e}")

    # 3. 磁盘空间
    header("3. 磁盘空间")
    import shutil
    disk = shutil.disk_usage(PROJECT_ROOT)
    free_gb = round(disk.free / 1024**3, 1)
    total_gb = round(disk.total / 1024**3, 1)
    if free_gb > 1:
        ok(f"磁盘空间: {free_gb}GB 可用 / {total_gb}GB 总量")
    else:
        fail(f"磁盘空间不足: 仅 {free_gb}GB 可用")

    # 4. Docker 容器状态
    header("4. Docker 容器状态")
    try:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            healthy = 0
            for line in lines:
                try:
                    d = json.loads(line)
                    name = d.get("Name", "?")
                    status = d.get("State", "?")
                    if status == "running":
                        healthy += 1
                        ok(f"容器 {name}: 运行中")
                    else:
                        warn(f"容器 {name}: {status}")
                except Exception:
                    pass
            if healthy >= 3:
                ok("所有核心容器运行正常")
            else:
                warn(f"仅有 {healthy} 个容器运行，预期至少 3 个")
        else:
            warn("Docker Compose 未运行或异常")
    except FileNotFoundError:
        warn("docker 命令不可用（非 Docker 部署？）")
    except Exception as e:
        warn(f"Docker 检查异常: {e}")

    # 5. 非 root 检查
    header("5. 非 root 用户检查")
    try:
        result = subprocess.run(
            ["docker", "compose", "exec", "backend", "id", "-u"],
            capture_output=True, text=True, timeout=10, cwd=PROJECT_ROOT
        )
        if result.returncode == 0:
            uid = result.stdout.strip()
            if uid != "0":
                ok(f"容器后端以 uid={uid} 运行（非 root）")
            else:
                fail("容器后端以 root 运行！")
        else:
            warn("无法检查容器用户（非 Docker 部署？）")
    except FileNotFoundError:
        warn("docker 命令不可用")
    except Exception as e:
        warn(f"用户检查异常: {e}")

    # 6. 文件权限
    header("6. 文件权限")
    for path in ["data/api_key.json", ".env"]:
        fp = PROJECT_ROOT / path
        if fp.exists():
            mode = fp.stat().st_mode & 0o777
            if mode == 0o600:
                ok(f"{path}: 权限 600 ✅")
            else:
                warn(f"{path}: 权限 {oct(mode)} (建议 600)")
        else:
            # .env may be optional in Docker deployments
            if path == ".env":
                warn(f"{path}: 不存在")
            else:
                fail(f"{path}: 不存在")

    # 7. 用户数据
    header("7. 用户数据")
    users_file = PROJECT_ROOT / "data" / "users.json"
    if users_file.exists():
        try:
            users = json.loads(users_file.read_text())
            ok(f"用户数据: {len(users)} 个用户")
            roles = {}
            for u, d in users.items():
                r = d.get("role", "teacher")
                roles[r] = roles.get(r, 0) + 1
            for r, c in roles.items():
                ok(f"  {r}: {c} 人")
        except Exception as e:
            fail(f"用户数据不可解析: {e}")
    else:
        fail("用户数据文件不存在")

    # 8. 知识库
    header("8. 知识库")
    kb_dir = PROJECT_ROOT / "knowledge-base"
    if kb_dir.exists():
        md_files = list(kb_dir.rglob("*.md"))
        ok(f"知识库教案: {len(md_files)} 篇")
    else:
        fail("知识库目录不存在")

    # 9. Embedding 模型
    header("9. Embedding 模型")
    model_dir = PROJECT_ROOT / ".cache" / "models" / "bge-small-zh-v1.5"
    if model_dir.exists():
        required = ["config.json", "tokenizer.json"]
        missing = [f for f in required if not (model_dir / f).exists()]
        if not missing:
            has_weights = any((model_dir / f).exists() for f in ["pytorch_model.bin", "model.safetensors"])
            if has_weights:
                ok("Embedding 模型 (bge-small-zh-v1.5): 已就绪")
            else:
                warn("Embedding 模型: 缺少权重文件")
        else:
            warn(f"Embedding 模型: 缺少文件 {missing}")
    else:
        warn("Embedding 模型目录不存在（首次运行时会自动下载）")

    # 10. 备份测试
    header("10. 备份测试")
    if not ADMIN_USER or not ADMIN_PASS:
        warn("未设置管理员账号，跳过备份测试")
    else:
        try:
            r_login = requests.post(
                f"{BASE}/api/login",
                json={"username": ADMIN_USER, "password": ADMIN_PASS},
                timeout=10
            )
            if r_login.status_code == 200 and r_login.json().get("token"):
                token = r_login.json()["token"]
                h = {"Authorization": f"Bearer {token}"}
                r_bak = requests.post(f"{BASE}/api/admin/backup", headers=h, timeout=30)
                if r_bak.status_code == 200:
                    import io, zipfile
                    zf = zipfile.ZipFile(io.BytesIO(r_bak.content))
                    filenames = [i.filename for i in zf.infolist()]
                    ok(f"备份包: {len(filenames)} 个文件")
                    has_users = "data/users.json" in filenames
                    if has_users:
                        ok("备份包含 data/users.json ✅")
                    else:
                        fail("备份缺少 data/users.json")
                    # API Key 脱敏检查
                    for f in filenames:
                        if "env" in f.lower() or f == "config.env.example":
                            content = zf.read(f).decode("utf-8", errors="ignore")
                            if "DEEPSEEK_API_KEY=***masked***" in content:
                                ok("API Key 脱敏: ✅")
                            elif "sk-" in content.lower():
                                fail("API Key 解密！备份包中仍含明文 Key")
                            break
                else:
                    fail(f"备份接口异常: status={r_bak.status_code}")
            else:
                warn(f"管理员登录失败: status={r_login.status_code}")
        except Exception as e:
            warn(f"备份测试异常: {e}")

    # 11. 思维导图端点
    header("11. 思维导图端点")
    try:
        r = requests.post(
            f"{BASE}/api/mindmap/generate",
            json={"lesson": "测试课", "lesson_plan": "x" * 100, "teaching_guide": "y" * 100},
            timeout=10
        )
        if r.status_code in (401, 403):
            ok("思维导图接口需要认证 ✅")
        else:
            warn(f"思维导图未登录返回: status={r.status_code}")
    except Exception as e:
        warn(f"思维导图端点检查异常: {e}")

    _save_and_exit()


def _save_and_exit():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = PROJECT_ROOT / f"delivery_report_{ts}.txt"
    content = "\n".join(results)

    print(content)

    summary = "\n" + "="*60
    if ERRORS == 0 and WARNINGS == 0:
        summary += "\n✅ DELIVERY DRY RUN PASSED"
    elif ERRORS == 0:
        summary += f"\n⚠️  DELIVERY DRY RUN PASSED (with {WARNINGS} warnings)"
    else:
        summary += f"\n❌ DELIVERY DRY RUN FAILED ({ERRORS} errors, {WARNINGS} warnings)"
    summary += f"\n报告已保存: {report_file}"

    print(summary)
    results.append(summary)

    with open(report_file, "w", encoding="utf-8") as f:
        f.write("\n".join(results))

    sys.exit(0 if ERRORS == 0 else 1)


if __name__ == "__main__":
    main()
