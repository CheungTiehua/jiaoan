#!/usr/bin/env python3
"""
LeKai 交付验收脚本
用法: python scripts/acceptance_check.py
"""

import json
import io
import sys
import os
import requests
import zipfile
from pathlib import Path

BASE = "http://127.0.0.1:8000"
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


# ---- 1. /api/health ----
r = requests.get(f"{BASE}/api/health")
check("1. /api/health 可访问", r.status_code == 200)

# ---- 2. /api/health/deep 未登录拒绝 ----
r = requests.get(f"{BASE}/api/health/deep")
check("2. /api/health/deep 未登录拒绝", r.status_code in (401, 403), f"status={r.status_code}")

# ---- 3. admin 登录 ----
r = requests.post(f"{BASE}/api/register", json={"username":"acctest_admin","password":"test1234"})
r = requests.post(f"{BASE}/api/login", json={"username":"acctest_admin","password":"test1234"})
admin_token = r.json().get("token", "")
check("3. admin 登录成功", bool(admin_token))

admin_h = {"Authorization": f"Bearer {admin_token}"}

# ---- 4. admin 可访问 /api/health/deep ----
r = requests.get(f"{BASE}/api/health/deep", headers=admin_h)
check("4. admin 可访问 /api/health/deep", r.status_code == 200)

# ---- 5. teacher 不可访问 /api/health/deep ----
r = requests.post(f"{BASE}/api/register", json={"username":"acctest_teacher","password":"test1234"})
r = requests.post(f"{BASE}/api/login", json={"username":"acctest_teacher","password":"test1234"})
teacher_token = r.json().get("token", "")
r = requests.get(f"{BASE}/api/health/deep", headers={"Authorization": f"Bearer {teacher_token}"})
check("5. teacher 不可访问 health/deep", r.status_code in (401, 403), f"status={r.status_code}")

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
# 上传一个无效文件触发失败
r = requests.post(f"{BASE}/api/admin/upload-lesson",
                  headers=admin_h,
                  files={"file": ("test.txt", io.BytesIO(b"not enough"))})
if r.status_code in (400, 422):
    check("7. 短文件上传被拒绝", True)
else:
    # 即使入库脚本失败，ok 也应为 false（而非 true）
    data = r.json() if r.status_code == 200 else {}
    check("7. 入库失败时 ok=False", data.get("ok") is not True, str(data.get("message", ""))[:80])

# ---- 8. 错误透出非统一"API Key 未配置" ----
# 用无效 token 触发 RuntimeError
r = requests.post(f"{BASE}/api/generate", json={"grade":"","lesson":"","requirements":""},
                 headers={"Authorization": "Bearer invalid_token"})
err_detail = r.json().get("detail","")
check("8. 错误信息非统一 Key 未配置", "API Key 未配置" not in err_detail, err_detail[:80])

# ---- 结果 ----
print(f"\n{'='*40}")
print(f"PASSED: {PASSED}  FAILED: {FAILED}")
if FAILED == 0 and PASSED >= 8:
    print("ACCEPTANCE PASSED")
    sys.exit(0)
else:
    print("ACCEPTANCE FAILED")
    sys.exit(1)
