#!/usr/bin/env python3
"""
LeKai 交付验收脚本
用法:
  ACCEPT_ADMIN_USER=admin ACCEPT_ADMIN_PASSWORD=xxx python scripts/acceptance_check.py

环境变量:
  ACCEPT_ADMIN_USER     已有管理员账号
  ACCEPT_ADMIN_PASSWORD 管理员密码
  ACCEPT_BASE_URL       后端地址（默认 http://127.0.0.1:8000）
"""

import json
import io
import os
import sys
import requests
import zipfile

ADMIN_USER = os.environ.get("ACCEPT_ADMIN_USER", "")
ADMIN_PASS = os.environ.get("ACCEPT_ADMIN_PASSWORD", "")
BASE = os.environ.get("ACCEPT_BASE_URL", "http://127.0.0.1:8000")

if not ADMIN_USER or not ADMIN_PASS:
    print("错误: 请设置环境变量 ACCEPT_ADMIN_USER 和 ACCEPT_ADMIN_PASSWORD")
    print("用法: ACCEPT_ADMIN_USER=admin ACCEPT_ADMIN_PASSWORD=xxx python scripts/acceptance_check.py")
    sys.exit(2)

FAILED = 0
PASSED = 0


def check(name: str, ok: bool, detail=""):
    global FAILED, PASSED
    if ok:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}" + (f": {detail}" if detail else ""))


# ---- 0. 管理员登录 ----
r = requests.post(f"{BASE}/api/login",
                  json={"username": ADMIN_USER, "password": ADMIN_PASS})
if r.status_code != 200 or not r.json().get("token"):
    print(f"❌ 管理员登录失败: {r.status_code} {r.text[:100]}")
    sys.exit(1)

admin_token = r.json()["token"]
admin_h = {"Authorization": f"Bearer {admin_token}"}

# ---- 1. /api/health ----
r = requests.get(f"{BASE}/api/health")
check("1. /api/health 可访问", r.status_code == 200)

# ---- 2. /api/health/deep 未登录拒绝 ----
r = requests.get(f"{BASE}/api/health/deep")
check("2. /api/health/deep 未登录拒绝", r.status_code in (401, 403), f"status={r.status_code}")

# ---- 3. admin 可访问 /api/health/deep ----
r = requests.get(f"{BASE}/api/health/deep", headers=admin_h)
check("3. admin 可访问 /api/health/deep", r.status_code == 200)

# ---- 4. 创建 teacher 用户（admin 调注册接口） ----
import secrets, string
teacher_pw = "".join(secrets.choice(string.ascii_letters + string.digits) for _ in range(10))
teacher_name = f"acctest_{teacher_pw[:6]}"
r = requests.post(f"{BASE}/api/register",
                  json={"username": teacher_name, "password": teacher_pw},
                  headers=admin_h)
check("4. admin 可创建 teacher 账号", r.status_code == 200, str(r.json().get("detail", ""))[:80])

# ---- 5. teacher 无法访问 health/deep ----
r2 = requests.post(f"{BASE}/api/login",
                   json={"username": teacher_name, "password": teacher_pw})
teacher_token = r2.json().get("token", "")
if not teacher_token:
    check("5. teacher 无法访问 health/deep", False, "teacher login failed, cannot verify")
else:
    r = requests.get(f"{BASE}/api/health/deep",
                     headers={"Authorization": f"Bearer {teacher_token}"})
    check("5. teacher 无法访问 health/deep", r.status_code in (401, 403), f"status={r.status_code}")

# ---- 6. 备份包含 data/users.json ----
r = requests.post(f"{BASE}/api/admin/backup", headers=admin_h)
check("6. 备份接口可访问", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    try:
        zf = zipfile.ZipFile(io.BytesIO(r.content))
        has_users = "data/users.json" in [i.filename for i in zf.infolist()]
        check("6. 备份包含 data/users.json", has_users)
    except Exception as e:
        check("6. 备份包可解析", False, str(e))

# ---- 7. 上传入库失败时 ok=False ----
r = requests.post(f"{BASE}/api/admin/upload-lesson",
                  headers=admin_h,
                  files={"file": ("test.txt", io.BytesIO(b"not enough content here"))})
if r.status_code in (400, 422):
    check("7. 短文件上传被拒绝", True)
else:
    data = r.json() if r.status_code == 200 else {}
    check("7. 入库失败时 ok=False", data.get("ok") is not True, str(data.get("message", ""))[:80])

# ---- 8. 测试模式错误透出（请求头触发） ----
r = requests.post(f"{BASE}/api/generate",
                  json={"grade": "三年级", "lesson": "测试课", "requirements": "",
                        "class_hours": "1", "semester": "上"},
                  headers={**admin_h, "X-Accept-Force-Rag-Error": "1"})
err_detail = r.json().get("detail", "")
check("8. RuntimeError 透出真实错误",
      r.status_code == 400 and "验收用错误" in err_detail,
      f"status={r.status_code}, detail={err_detail[:80]}")

# ---- 9. 入库失败返回 ok:False ----
content = ("这是验收测试教案内容。" * 20).encode("utf-8")
r = requests.post(f"{BASE}/api/admin/upload-lesson",
                  headers=admin_h,
                  files={"file": ("force_ingest_fail_test.txt", io.BytesIO(content), "text/plain")})

try:
    data = r.json()
except Exception:
    data = {}

check("9. 入库失败时 ok=False",
      r.status_code == 200
      and data.get("ok") is False
      and "模拟入库失败" in str(data.get("message", "")),
      f"status={r.status_code}, body={str(data)[:120]}")

# ---- 结果 ----
print(f"\n{'='*40}")
print(f"PASSED: {PASSED}  FAILED: {FAILED}")
if FAILED == 0 and PASSED >= 9:
    print("ACCEPTANCE PASSED")
    sys.exit(0)
else:
    print("ACCEPTANCE FAILED")
    sys.exit(1)
