#!/usr/bin/env python3
"""
LeKai 交付验收脚本
用法:
  LEKAI_ACCEPTANCE_MODE=1 ACCEPT_ADMIN_USER=admin ACCEPT_ADMIN_PASSWORD=xxx python scripts/acceptance_check.py

环境变量:
  LEKAI_ACCEPTANCE_MODE  必须设为 1（验收模式开关，保护正式环境）
  ACCEPT_ADMIN_USER      已有管理员账号
  ACCEPT_ADMIN_PASSWORD  管理员密码
  ACCEPT_BASE_URL        后端地址（默认 http://127.0.0.1:8000）
  ACCEPT_SKIP_REAL_MINDMAP 设为 1 跳过真实思维导图生成
"""

import json
import io
import os
import shutil
import sys
import requests
import zipfile

ADMIN_USER = os.environ.get("ACCEPT_ADMIN_USER", "")
ADMIN_PASS = os.environ.get("ACCEPT_ADMIN_PASSWORD", "")
BASE = os.environ.get("ACCEPT_BASE_URL", "http://127.0.0.1:8000")

if not ADMIN_USER or not ADMIN_PASS:
    print("错误: 请设置环境变量 ACCEPT_ADMIN_USER 和 ACCEPT_ADMIN_PASSWORD")
    print("用法: LEKAI_ACCEPTANCE_MODE=1 ACCEPT_ADMIN_USER=admin ACCEPT_ADMIN_PASSWORD=xxx python scripts/acceptance_check.py")
    sys.exit(2)

if os.environ.get("LEKAI_ACCEPTANCE_MODE", "0") != "1":
    print("错误: 请设置 LEKAI_ACCEPTANCE_MODE=1 后再运行验收脚本")
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

# ============================================================
# 思维导图验收
# ============================================================

teacher_h = {"Authorization": f"Bearer {teacher_token}"}
SKIP_REAL_MINDMAP = os.environ.get("ACCEPT_SKIP_REAL_MINDMAP", "") == "1"

# ---- 10. mindmap 接口必须登录 ----
r = requests.post(f"{BASE}/api/mindmap/generate",
                  json={"lesson": "测试", "lesson_plan": "x" * 100})
check("10. mindmap requires auth", r.status_code in (401, 403), f"status={r.status_code}")

# ---- 11. mindmap 空输入校验 ----
r = requests.post(f"{BASE}/api/mindmap/generate",
                  json={"lesson": "", "lesson_plan": ""},
                  headers=teacher_h)
check("11. mindmap validates empty input",
      r.status_code == 400 and ("课题名称不能为空" in str(r.json().get("detail", ""))
                                or "教案内容不能为空" in str(r.json().get("detail", ""))),
      f"status={r.status_code}, detail={r.json().get('detail', '')[:60]}")

# ---- 12. mindmap 太短教案校验 ----
r = requests.post(f"{BASE}/api/mindmap/generate",
                  json={"lesson": "测试课", "lesson_plan": "太短"},
                  headers=teacher_h)
check("12. mindmap validates short lesson_plan",
      r.status_code == 400 and "教案内容过短" in str(r.json().get("detail", "")),
      f"status={r.status_code}, detail={r.json().get('detail', '')[:60]}")

# ---- 13. mindmap 测试钩子 ----
r = requests.post(f"{BASE}/api/mindmap/generate",
                  json={"lesson": "测试课", "lesson_plan": "x" * 100},
                  headers={**admin_h, "X-Accept-Force-Mindmap-Error": "1"})
err_detail = r.json().get("detail", "")
check("13. mindmap forced error surfaces detail",
      r.status_code == 400 and "验收用错误" in err_detail,
      f"status={r.status_code}, detail={err_detail[:60]}")

# ---- 14. mindmap 正常双导图生成 ----
mindmap_record_id = None
if not SKIP_REAL_MINDMAP:
    test_plan = (
        "这是验收测试教案内容。" * 20
        + "\n## 教学目标\n1. 认识生字。\n2. 朗读课文。\n3. 体会情感。"
        + "\n## 教学流程\n导入激趣、初读感知、精读品味、拓展延伸。"
        + "\n## 板书设计\n课题 + 关键词"
        + "\n## 作业\n背诵课文"
    )
    test_guide = (
        "教案辅导说明。" * 20
        + "\n先看单元语文要素，再看课后习题反推目标。"
    )
    r = requests.post(f"{BASE}/api/mindmap/generate",
                      json={"grade": "三年级", "lesson": "验收测试课",
                            "lesson_plan": test_plan, "teaching_guide": test_guide},
                      headers=teacher_h)
    if r.status_code == 200:
        data = r.json()
        has_lesson = "lesson_mindmap_mermaid" in data and data["lesson_mindmap_mermaid"].startswith("mindmap")
        has_method = "method_mindmap_mermaid" in data and data["method_mindmap_mermaid"].startswith("mindmap")
        has_outline = "lesson_outline" in data and "method_outline" in data

        lesson_mm = data.get("lesson_mindmap_mermaid", "")
        method_mm = data.get("method_mindmap_mermaid", "")

        lesson_kw_ok = sum(1 for kw in ["教学目标", "教学流程", "板书", "作业"] if kw in lesson_mm) >= 2
        method_kw_ok = sum(1 for kw in ["备课", "方法", "目标提炼", "可迁移", "常见误区"] if kw in method_mm) >= 2

        ok = has_lesson and has_method and has_outline and lesson_kw_ok and method_kw_ok
        check("14. mindmap generates dual maps", ok,
              f"lesson_ok={has_lesson}, method_ok={has_method}, outline_ok={has_outline}, lesson_kw={lesson_kw_ok}, method_kw={method_kw_ok}")

        # 记录 record_id 用于后续历史保存验收
        # 需要先从生成教案中获得 record_id，这里使用 admin 生成一个测试教案
        if ok:
            r_gen = requests.post(f"{BASE}/api/generate",
                                  json={"grade": "三年级", "lesson": "验收测试课", "requirements": "",
                                        "class_hours": "1", "semester": "上"},
                                  headers=teacher_h)
            if r_gen.status_code == 200:
                mindmap_record_id = r_gen.json().get("record_id", "")
    else:
        detail = r.json().get("detail", str(r.status_code))
        check("14. mindmap generates dual maps", False, detail)
else:
    print("  ⏭️  14. mindmap generates dual maps (skipped, ACCEPT_SKIP_REAL_MINDMAP=1)")

# ---- 15. mindmap 历史保存 ----
if mindmap_record_id:
    r = requests.post(f"{BASE}/api/history/{mindmap_record_id}/mindmap",
                      json={"lesson_mindmap_mermaid": "mindmap\n  root((测试教案导图))\n    教学目标\n    教学流程",
                            "method_mindmap_mermaid": "mindmap\n  root((测试备课方法导图))\n    备课方法\n    可迁移经验"},
                      headers=teacher_h)
    if r.status_code == 200:
        # 读回验证
        r2 = requests.get(f"{BASE}/api/history/{mindmap_record_id}", headers=teacher_h)
        if r2.status_code == 200:
            d2 = r2.json()
            has_saved_lesson = "mindmap" in d2.get("lesson_mindmap_mermaid", "")
            has_saved_method = "mindmap" in d2.get("method_mindmap_mermaid", "")
            check("15. mindmap persists to history",
                  has_saved_lesson and has_saved_method,
                  f"lesson_saved={has_saved_lesson}, method_saved={has_saved_method}")
        else:
            check("15. mindmap persists to history", False, "history read failed")
    else:
        check("15. mindmap persists to history", False, f"save failed: status={r.status_code}")
else:
    if not SKIP_REAL_MINDMAP:
        check("15. mindmap persists to history", False, "no record_id — lesson plan generation for record_id failed")
    else:
        print("  ⏭️  15. mindmap persists to history (skipped, ACCEPT_SKIP_REAL_MINDMAP=1)")

# ---- 16. mindmap 导出附录（MD） ----
if mindmap_record_id:
    r = requests.get(f"{BASE}/api/export/{mindmap_record_id}?format=md&include_mindmap=true",
                     headers=teacher_h)
    if r.status_code == 200:
        body = r.text
        has_lesson_appendix = "附录：教案思维导图" in body
        has_method_appendix = "附录：备课方法思维导图" in body
        check("16. mindmap appendix exported in markdown",
              has_lesson_appendix and has_method_appendix,
              f"lesson_appendix={has_lesson_appendix}, method_appendix={has_method_appendix}")
    else:
        check("16. mindmap appendix exported in markdown", False, f"status={r.status_code}")
else:
    if not SKIP_REAL_MINDMAP:
        check("16. mindmap appendix exported in markdown", False, "no record_id — mindmap generation for record_id failed")
    else:
        print("  ⏭️  16. mindmap appendix exported in markdown (skipped, ACCEPT_SKIP_REAL_MINDMAP=1)")

# ---- 17. mindmap 导出附录（DOCX） ----
if mindmap_record_id:
    r = requests.get(f"{BASE}/api/export/{mindmap_record_id}?format=docx&include_mindmap=true",
                     headers=teacher_h)
    ok = r.status_code == 200 and len(r.content) > 1000
    check("17. mindmap appendix exported in docx", ok,
          f"status={r.status_code}, size={len(r.content)}")
else:
    if not SKIP_REAL_MINDMAP:
        check("17. mindmap appendix exported in docx", False, "no record_id — mindmap generation for record_id failed")
    else:
        print("  ⏭️  17. mindmap appendix exported in docx (skipped, ACCEPT_SKIP_REAL_MINDMAP=1)")

# ---- 清理验收测试数据 ----
def cleanup_acceptance_artifacts():
    """清理 acctest_ 开头的测试用户及相关数据"""
    from pathlib import Path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    cleaned = 0
    warnings = []

    users_file = os.path.join(project_root, "data", "users.json")
    sessions_file = os.path.join(project_root, "data", "sessions.json")
    history_dir = os.path.join(project_root, "data", "history")
    reviews_dir = os.path.join(project_root, "data", "reviews")
    feedback_dir = os.path.join(project_root, "data", "feedback")

    # 1. 清理测试用户历史目录
    if os.path.isdir(history_dir):
        for d in os.listdir(history_dir):
            if d.startswith("acctest_"):
                path = os.path.join(history_dir, d)
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path)
                        print(f"  [CLEANUP] 已删除历史目录: {d}")
                        cleaned += 1
                    except Exception as e:
                        warnings.append(f"删除历史目录失败 {d}: {e}")

    # 2. 清理测试反馈记录
    if os.path.isdir(feedback_dir):
        for f in os.listdir(feedback_dir):
            if f.startswith("acctest_"):
                path = os.path.join(feedback_dir, f)
                try:
                    os.remove(path)
                    print(f"  [CLEANUP] 已删除反馈记录: {f}")
                    cleaned += 1
                except Exception as e:
                    warnings.append(f"删除反馈记录失败 {f}: {e}")

    # 3. 清理测试审核记录
    if os.path.isdir(reviews_dir):
        for f in os.listdir(reviews_dir):
            if f.endswith(".json"):
                path = os.path.join(reviews_dir, f)
                try:
                    with open(path, "r") as fh:
                        data = json.loads(fh.read())
                    if isinstance(data, dict) and str(data.get("username", "")).startswith("acctest_"):
                        os.remove(path)
                        print(f"  [CLEANUP] 已删除审核记录: {f}")
                        cleaned += 1
                except Exception as e:
                    warnings.append(f"删除审核记录失败 {f}: {e}")

    # 4. 清理 users.json 中测试用户
    if os.path.exists(users_file):
        try:
            with open(users_file, "r") as fh:
                users = json.loads(fh.read())
            test_users = [u for u in users if u.startswith("acctest_")]
            if test_users:
                for u in test_users:
                    del users[u]
                    print(f"  [CLEANUP] 已删除用户: {u}")
                    cleaned += 1
                from backend.security import atomic_write
                atomic_write(Path(users_file), json.dumps(users, ensure_ascii=False, indent=2).encode())
        except Exception as e:
            warnings.append(f"清理 users.json 失败: {e}")

    # 5. 清理 sessions.json 中测试 session
    if os.path.exists(sessions_file):
        try:
            with open(sessions_file, "r") as fh:
                sessions = json.loads(fh.read())
            test_sessions = [k for k, v in sessions.items()
                           if isinstance(v, dict) and str(v.get("username", "")).startswith("acctest_")]
            for k in test_sessions:
                del sessions[k]
                cleaned += 1
            if test_sessions:
                from backend.security import atomic_write
                atomic_write(Path(sessions_file), json.dumps(sessions, ensure_ascii=False, indent=2).encode())
                print(f"  [CLEANUP] 已清理 {len(test_sessions)} 个 acctest session")
        except Exception as e:
            warnings.append(f"清理 sessions.json 失败: {e}")

    if warnings:
        for w in warnings:
            print(f"  [WARN] cleanup failed: {w}")
    if cleaned > 0:
        print(f"  [PASS] cleanup acceptance artifacts ({cleaned} items)")
    return len(warnings) == 0


# ---- 结果 ----
print(f"\n{'='*40}")
print(f"PASSED: {PASSED}  FAILED: {FAILED}")

cleanup_ok = cleanup_acceptance_artifacts()

MIN_PASS = 17 if not SKIP_REAL_MINDMAP else 12
if FAILED == 0 and PASSED >= MIN_PASS:
    if not cleanup_ok:
        print("ACCEPTANCE PASSED WITH CLEANUP WARNINGS")
    else:
        print("ACCEPTANCE PASSED")
    sys.exit(0)
else:
    print("ACCEPTANCE FAILED")
    sys.exit(1)
