"""LeKai v0.4 — 多用户 + 认证 + 历史"""

import json as _json
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from rag import generate_lesson, revise_lesson, generate_unit_plan, generate_reflection
from scripts.all_textbooks import GRADE_TEXTBOOKS
from auth import (
    register_user, login_user, logout_user, get_user_from_token,
    list_users, save_history, get_history, get_history_detail,
    get_user_role,
)
from admin_api import (
    submit_for_review, get_review_queue, get_review_detail,
    approve_review, reject_review, get_dashboard_stats, set_user_role,
)
from collab import (
    create_group, list_groups, join_group, get_user_groups,
    share_plan, get_group_plans, assign_task, get_group_tasks,
    complete_task, add_comment,
)
from security import check_rate_limit
from health import get_health
from backup import create_backup, restore_backup
from feedback import submit_feedback, get_feedback, get_stats as get_feedback_stats
from annotation import add_annotation, get_annotations, get_stats as get_annotation_stats
from fastapi import UploadFile, File as FastAPIFile, Form

app = FastAPI(
    title="LeKai教案知识库 API",
    description="小学语文教案智能生成平台 v0.4",
    version="0.4.0"
)

import os as _os
_cors_origins = _os.getenv("LEKAI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ---- Auth dependency ----

def require_auth(authorization: str = Header(default="")) -> str:
    """从 Authorization: Bearer <token> 中提取用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="请先登录")
    token = authorization[len("Bearer "):]
    username = get_user_from_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    return username


# ---- Models ----

class AuthRequest(BaseModel):
    username: str
    password: str


class GenerateRequest(BaseModel):
    grade: str = Field(..., max_length=20, json_schema_extra={"example": "三年级"})
    lesson: str = Field(..., max_length=100, json_schema_extra={"example": "富饶的西沙群岛"})
    requirements: str = Field(default="", max_length=500, json_schema_extra={"example": "重点修辞手法"})
    class_hours: str = Field(default="2", max_length=5)
    semester: str = Field(default="上", max_length=5)


class GenerateResponse(BaseModel):
    exam_analysis: str = Field(default="")
    peer_analysis: str = Field(default="")
    lesson_plan: str = Field(default="")
    teaching_guide: str = Field(default="")
    record_id: str = Field(default="")


class ReviseRequest(BaseModel):
    current_plan: str = Field(...)
    revision_request: str = Field(...)
    history: str = Field(default="")


class ReviseResponse(BaseModel):
    lesson_plan: str


# ---- Public API ----

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.4.0"}


@app.get("/api/textbooks")
async def textbooks():
    tree = []
    for grade in ["一年级","二年级","三年级","四年级","五年级","六年级"]:
        gd = GRADE_TEXTBOOKS.get(grade, {})
        sems = []
        for sn in ["上册","下册"]:
            sd = gd.get(sn, {})
            units = [{"name": un, "lessons": ls} for un, ls in sd.items()]
            sems.append({"name": sn, "units": units})
        tree.append({"grade": grade, "semesters": sems})
    return {"textbooks": tree}


# ---- Auth API ----

@app.post("/api/register")
async def register(req: AuthRequest, request: Request = None):
    client_ip = request.client.host if request else "127.0.0.1"
    if check_rate_limit(f"reg_{client_ip}", 5, 300):
        raise HTTPException(status_code=429, detail="注册过于频繁，请5分钟后再试")
    ok, msg = register_user(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/api/login")
async def login(req: AuthRequest, request: Request = None):
    client_ip = request.client.host if request else "127.0.0.1"
    if check_rate_limit(f"login_{client_ip}", 10, 60):
        raise HTTPException(status_code=429, detail="登录尝试过多，请1分钟后再试")
    token = login_user(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    role = get_user_role(req.username)
    return {"token": token, "username": req.username, "role": role}


@app.post("/api/logout")
async def logout(authorization: str = Header(default="")):
    if authorization.startswith("Bearer "):
        logout_user(authorization[len("Bearer "):])
    return {"message": "已退出"}


@app.get("/api/me")
async def me(authorization: str = Header(default="")):
    if authorization.startswith("Bearer "):
        username = get_user_from_token(authorization[len("Bearer "):])
        if username:
            role = get_user_role(username)
            return {"username": username, "role": role}
    return {"username": "", "role": ""}


# ---- Protected API ----

@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, request: Request, username: str = Depends(require_auth)):
    if not req.lesson.strip():
        raise HTTPException(status_code=400, detail="课题名称不能为空")
    # 生成端点速率限制
    from security import check_rate_limit
    if check_rate_limit(f"gen_{username}", 20, 60):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
    try:
        result = generate_lesson(
            grade=req.grade, lesson=req.lesson.strip(),
            requirements=req.requirements.strip(),
            class_hours=req.class_hours, semester=req.semester
        )
        record_id = save_history(username, req.grade, req.lesson.strip(), result)
        result["record_id"] = record_id
        return GenerateResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail="API Key 未配置")
    except Exception:
        import traceback, logging
        logging.getLogger("lekai").error("生成失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="生成失败，请稍后重试")


@app.post("/api/revise", response_model=ReviseResponse)
async def revise(req: ReviseRequest, username: str = Depends(require_auth)):
    if not req.current_plan.strip():
        raise HTTPException(status_code=400, detail="请提供当前教案")
    try:
        new_plan = revise_lesson(req.current_plan, req.revision_request, req.history)
        return ReviseResponse(lesson_plan=new_plan)
    except RuntimeError:
        raise HTTPException(status_code=500, detail="API Key 未配置")
    except Exception:
        import traceback, logging
        logging.getLogger("lekai").error("修改失败:\n%s", traceback.format_exc())
        raise HTTPException(status_code=500, detail="修改失败，请稍后重试")


@app.get("/api/history")
async def history(username: str = Depends(require_auth)):
    """获取当前用户的生成历史"""
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")
    return {"history": get_history(username)}


@app.get("/api/history/{record_id}")
async def history_detail(record_id: str, username: str = Depends(require_auth)):
    detail = get_history_detail(username, record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="记录不存在")
    return detail


# ---- Review API ----

class ReviewSubmitRequest(BaseModel):
    record_id: str

@app.post("/api/review/submit")
async def review_submit(req: ReviewSubmitRequest, username: str = Depends(require_auth)):
    ok = submit_for_review(username, req.record_id)
    if not ok:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"message": "已提交审核"}


# ---- Admin API ----

def require_admin_or_reviewer(username: str = Depends(require_auth)) -> str:
    role = get_user_role(username)
    if role not in ("admin", "reviewer"):
        raise HTTPException(status_code=403, detail="需要管理员或教研组长权限")
    return username

def require_admin(username: str = Depends(require_auth)) -> str:
    if get_user_role(username) != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return username

@app.get("/api/admin/dashboard")
async def admin_dashboard(username: str = Depends(require_admin_or_reviewer)):
    return get_dashboard_stats()

@app.get("/api/admin/reviews")
async def admin_reviews(username: str = Depends(require_admin_or_reviewer)):
    return {"reviews": get_review_queue()}

@app.get("/api/admin/reviews/{record_id}")
async def admin_review_detail(record_id: str, username: str = Depends(require_admin_or_reviewer)):
    detail = get_review_detail(record_id)
    if not detail:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return detail

@app.post("/api/admin/reviews/{record_id}/approve")
async def admin_approve(record_id: str, username: str = Depends(require_admin_or_reviewer)):
    ok = approve_review(record_id, username)
    if not ok:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return {"message": "已批准"}

class ReviewRejectRequest(BaseModel):
    comment: str = ""


@app.post("/api/admin/reviews/{record_id}/reject")
async def admin_reject(record_id: str, req: ReviewRejectRequest = ReviewRejectRequest(), username: str = Depends(require_admin_or_reviewer)):
    ok = reject_review(record_id, username, req.comment)
    if not ok:
        raise HTTPException(status_code=404, detail="审核记录不存在")
    return {"message": "已打回"}

@app.post("/api/admin/users/set-role")
async def admin_set_role(req: dict, username: str = Depends(require_admin)):
    target = req.get("username", "")
    role = req.get("role", "")
    ok = set_user_role(target, role)
    if not ok:
        raise HTTPException(status_code=400, detail="设置失败")
    return {"message": f"已将 {target} 的角色设为 {role}"}


# ---- 单元规划 API ----

class UnitPlanRequest(BaseModel):
    grade: str = Field(default="三年级")
    unit: str = Field(default="第六单元")
    semester: str = Field(default="上")

@app.post("/api/unit-plan")
async def unit_plan(req: UnitPlanRequest, username: str = Depends(require_auth)):
    try:
        result = generate_unit_plan(req.grade, req.unit, req.semester)
        return {"unit_plan": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail="生成失败，请稍后重试")


# ---- 教研协作 API ----

@app.get("/api/collab/groups")
async def collab_groups(username: str = Depends(require_auth)):
    return {"groups": list_groups(), "my_groups": get_user_groups(username)}

@app.post("/api/collab/groups/create")
async def collab_create(req: dict, username: str = Depends(require_auth)):
    r = create_group(req.get("name", ""), username)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["msg"])
    return r

@app.post("/api/collab/groups/join")
async def collab_join(req: dict, username: str = Depends(require_auth)):
    r = join_group(req.get("name", ""), username)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["msg"])
    return r

@app.post("/api/collab/share")
async def collab_share(req: dict, username: str = Depends(require_auth)):
    r = share_plan(username, req.get("group", ""), req.get("grade", ""),
                   req.get("lesson", ""), req.get("record_id", ""))
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["msg"])
    return r

@app.get("/api/collab/groups/{group_name}/plans")
async def collab_plans(group_name: str, username: str = Depends(require_auth)):
    return {"plans": get_group_plans(group_name)}

@app.post("/api/collab/tasks/assign")
async def collab_assign(req: dict, username: str = Depends(require_auth)):
    r = assign_task(req.get("group", ""), req.get("assigned_to", ""),
                    req.get("lesson", ""), username)
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["msg"])
    return r

@app.get("/api/collab/groups/{group_name}/tasks")
async def collab_tasks(group_name: str, username: str = Depends(require_auth)):
    return {"tasks": get_group_tasks(group_name)}

@app.post("/api/collab/tasks/complete")
async def collab_complete(req: dict, username: str = Depends(require_auth)):
    r = complete_task(req.get("group", ""), req.get("task_index", 0))
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["msg"])
    return r

@app.post("/api/collab/comment")
async def collab_comment(req: dict, username: str = Depends(require_auth)):
    r = add_comment(req.get("group", ""), req.get("plan_index", 0),
                    username, req.get("text", ""))
    if not r["ok"]:
        raise HTTPException(status_code=400, detail=r["msg"])
    return r


# ---- 课后反思 API ----

class ReflectionRequest(BaseModel):
    lesson: str = Field(default="")
    lesson_plan: str = Field(default="")

@app.post("/api/reflect")
async def reflect(req: ReflectionRequest, username: str = Depends(require_auth)):
    try:
        result = generate_reflection(req.lesson, req.lesson_plan)
        return {"reflection": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail="生成失败，请稍后重试")


# ---- 健康检查 ----

@app.get("/api/admin/health")
async def admin_health(username: str = Depends(require_admin_or_reviewer)):
    return get_health()


# ---- 备份恢复 ----

@app.post("/api/admin/backup")
async def admin_backup(username: str = Depends(require_admin)):
    import time as _t
    buf = create_backup()
    ts = _t.strftime("%Y%m%d_%H%M%S")
    return StreamingResponse(buf, media_type="application/zip",
                            headers={"Content-Disposition": f"attachment; filename=lekai_backup_{ts}.zip"})


@app.post("/api/admin/restore")
async def admin_restore(file: UploadFile = FastAPIFile(...), username: str = Depends(require_admin)):
    data = await file.read()
    ok, msg = restore_backup(data)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


# ---- Prompt 在线配置 ----

PROMPTS_FILE = Path(__file__).resolve().parent.parent / "data" / ".system_prompts"


@app.get("/api/admin/prompts")
async def admin_get_prompts(username: str = Depends(require_admin_or_reviewer)):
    if PROMPTS_FILE.exists():
        try:
            return _json.loads(PROMPTS_FILE.read_text())
        except Exception:
            pass
    return {"chat_prompt": "", "audit_prompt": ""}


@app.post("/api/admin/prompts")
async def admin_set_prompts(req: dict, username: str = Depends(require_admin)):
    cur = {}
    if PROMPTS_FILE.exists():
        try:
            cur = _json.loads(PROMPTS_FILE.read_text())
        except Exception:
            pass
    for key in ("chat_prompt", "audit_prompt"):
        if key in req:
            cur[key] = str(req[key])[:5000]
    from security import atomic_write
    atomic_write(PROMPTS_FILE, _json.dumps(cur, ensure_ascii=False, indent=2).encode())
    return {"ok": True, "message": "提示词已更新，立即生效"}


# ---- 教案反馈 ----

class FeedbackRequest(BaseModel):
    plan_id: str
    grade: str = ""
    lesson: str = ""
    rating: int = 0
    useful_refs: list[str] = []
    tags: list[str] = []
    comment: str = ""

@app.post("/api/feedback")
async def api_feedback(req: FeedbackRequest, username: str = Depends(require_auth)):
    return submit_feedback(username, req.plan_id, req.grade, req.lesson,
                           req.rating, req.useful_refs, req.tags, req.comment)

@app.get("/api/feedback/{plan_id}")
async def api_get_feedback(plan_id: str, username: str = Depends(require_auth)):
    fb = get_feedback(plan_id)
    if not fb:
        raise HTTPException(status_code=404, detail="无反馈记录")
    return fb

@app.get("/api/admin/feedback-stats")
async def admin_feedback_stats(username: str = Depends(require_admin_or_reviewer)):
    return get_feedback_stats()


# ---- 段落标注 ----

class AnnotationRequest(BaseModel):
    review_id: str
    section: str
    type: str  # praise | improve | note
    text: str

@app.post("/api/admin/annotations")
async def api_add_annotation(req: AnnotationRequest, username: str = Depends(require_admin_or_reviewer)):
    return add_annotation(req.review_id, username, req.section, req.type, req.text)

@app.get("/api/admin/annotations/{review_id}")
async def api_get_annotations(review_id: str, username: str = Depends(require_admin_or_reviewer)):
    return {"annotations": get_annotations(review_id)}

@app.get("/api/admin/annotation-stats")
async def admin_annotation_stats(username: str = Depends(require_admin_or_reviewer)):
    return get_annotation_stats()


# ---- 教案入库（管理员上传教案文档） ----

@app.post("/api/admin/upload-lesson")
async def admin_upload_lesson(
    file: UploadFile = FastAPIFile(...),
    username: str = Depends(require_admin_or_reviewer)
):
    """上传教案文档(.md/.docx/.txt)，自动格式化后入库"""
    import re
    fn = file.filename or "untitled"
    ext = Path(fn).suffix.lower()
    if ext not in (".md", ".txt", ".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .md / .txt / .docx 格式")

    content = (await file.read()).decode("utf-8", errors="ignore")
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="文档内容过短（至少100字符）")

    # 尝试用 DeepSeek 格式化为标准模板
    try:
        from rag import call_deepseek
        fmt_sys = "你是教案格式化助手。将原始教案内容整理为规范Markdown格式。保留全部教学要点。"
        fmt_user = f"请将以下原始教案整理为标准格式：\n\n{content[:8000]}\n\n输出完整的Markdown教案。"
        formatted = call_deepseek(fmt_sys, fmt_user)
    except Exception:
        formatted = content  # API不可用时直接用原文

    # 提取课题名做文件名
    match = re.search(r'《(.+?)》', formatted)
    lesson_name = match.group(1) if match else Path(fn).stem

    # 保存到 knowledge-base/
    import re as _re
    safe_name = _re.sub(r'[《》\s]', '', lesson_name)
    dest = Path(__file__).resolve().parent.parent / "knowledge-base" / f"{safe_name}.md"
    dest.write_text(formatted, encoding="utf-8")

    # 触发入库
    import subprocess, sys
    try:
        subprocess.run([sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "ingest_knowledge.py")],
                       capture_output=True, timeout=60)
        return {"ok": True, "lesson": lesson_name, "message": f"《{lesson_name}》已入库"}
    except Exception:
        return {"ok": True, "lesson": lesson_name, "message": f"《{lesson_name}》已保存，请手动运行入库脚本"}


# ---- 设备信息 ----

@app.get("/api/admin/device-info")
async def admin_device_info(username: str = Depends(require_admin_or_reviewer)):
    import uuid, shutil
    proj = Path(__file__).resolve().parent.parent
    mac = ":".join(f"{(uuid.getnode() >> (8*i)) & 0xff:02x}" for i in range(5, -1, -1))
    disk = shutil.disk_usage(proj)
    lic_file = proj / ".license"
    lic_status = "已授权" if lic_file.exists() else "未授权"

    return {
        "mac": mac,
        "disk_total_gb": round(disk.total / 1024**3, 1),
        "disk_free_gb": round(disk.free / 1024**3, 1),
        "disk_used_pct": round((disk.used / disk.total) * 100, 1),
        "license": lic_status,
        "version": "0.8.0",
    }


# ---- Prompt 格式化模板（用于教案导入） ----

FORMAT_LESSON_SYSTEM = """你是教案格式化助手。将原始教案内容整理为规范Markdown格式。保留全部教学要点。"""
FORMAT_LESSON_USER = """请将以下原始教案整理为标准格式：

{raw}

输出完整的Markdown教案。"""


# ---- 知识库 Chunk 管理 ----

@app.get("/api/admin/chunks")
async def admin_chunks(username: str = Depends(require_admin_or_reviewer)):
    """浏览知识库 chunks"""
    from search_engine import get_collection
    col = get_collection()
    if col.count() == 0:
        return {"chunks": [], "total": 0}
    result = col.get(include=["documents", "metadatas"], limit=200)
    chunks = []
    for i in range(min(len(result["ids"]), len(result.get("documents", [])))):
        meta = result["metadatas"][i] if result.get("metadatas") and i < len(result["metadatas"]) else {}
        chunks.append({
            "id": result["ids"][i],
            "text": (t := result["documents"][i])[:200] + ("..." if len(t) > 200 else ""),
            "lesson": meta.get("lesson", ""),
            "grade": meta.get("grade", ""),
            "chunk_type": meta.get("chunk_type", ""),
        })
    return {"chunks": chunks, "total": col.count()}


@app.post("/api/admin/chunks/delete")
async def admin_delete_chunk(req: dict, username: str = Depends(require_admin)):
    """删除单个 chunk"""
    chunk_id = req.get("chunk_id", "")
    if not chunk_id:
        raise HTTPException(status_code=400, detail="请提供 chunk_id")
    from search_engine import get_collection
    col = get_collection()
    col.delete(ids=[chunk_id])
    from search_engine import refresh_index
    refresh_index()
    return {"ok": True, "message": "已删除并刷新索引"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
