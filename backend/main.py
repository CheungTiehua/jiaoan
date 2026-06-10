"""LeKai教案系统(K9-AI版) — v1.0"""

import io
import json as _json
import sys
import time as _time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Header, Depends, Request
from fastapi.responses import StreamingResponse, RedirectResponse
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
from config import VERSION
from security import check_rate_limit
from health import get_health
from backup import create_backup, restore_backup
from feedback import submit_feedback, get_feedback, get_stats as get_feedback_stats
from annotation import add_annotation, get_annotations, get_stats as get_annotation_stats
from fastapi import UploadFile, File as FastAPIFile, Form

app = FastAPI(
    title="LeKai教案知识库 API",
    description="小学语文教案智能生成平台 — LeKai K9-AI版",
    version=VERSION
)

import os as _os
_cors_origins = [o.strip() for o in _os.getenv("LEKAI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")]
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

@app.get("/")
async def root():
    return RedirectResponse(url="/api/health")


# ---- 首次启动引导 ----

@app.get("/api/setup/status")
async def setup_status():
    from auth import load_users
    return {"needs_setup": len(load_users()) == 0}


@app.post("/api/setup/complete")
async def setup_complete(req: dict):
    from auth import load_users, register_user
    if len(load_users()) > 0:
        raise HTTPException(status_code=403, detail="系统已初始化")

    password = str(req.get("password", "")).strip()
    api_key = str(req.get("api_key", "")).strip().replace("\n", "").replace("\r", "")
    if len(password) < 4:
        raise HTTPException(status_code=400, detail="管理员密码至少4位")
    if not api_key:
        raise HTTPException(status_code=400, detail="请填写DeepSeek API Key")

    # 持久化 API Key：同时写 .env 和 data/api_key.json
    env_file = Path(__file__).resolve().parent.parent / ".env"
    # 保留现有 .env 中的其他配置
    existing = ""
    if env_file.exists():
        lines = env_file.read_text().split("\n")
        existing = "\n".join(l for l in lines if not l.startswith("DEEPSEEK_API_KEY=") and l.strip())
        if existing:
            existing += "\n"
    from security import atomic_write
    atomic_write(env_file, (existing + f"DEEPSEEK_API_KEY={api_key}\n").encode())
    import os as _os2
    _os2.chmod(env_file, 0o600)

    import json as _j
    key_file = Path(__file__).resolve().parent.parent / "data" / "api_key.json"
    atomic_write(key_file, _j.dumps({"api_key": api_key}).encode())
    _os2.chmod(key_file, 0o600)

    ok, msg = register_user("admin", password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    import rag
    rag.reload_keys(api_key)
    return {"ok": True, "message": "初始化完成"}


@app.get("/api/setup/wifi-scan")
async def setup_wifi_scan():
    import subprocess
    try:
        r = subprocess.run(["nmcli","-t","-f","SSID,SIGNAL,SECURITY","dev","wifi","list","--rescan","yes"],
                         capture_output=True, text=True, timeout=15)
        nets = []
        for line in r.stdout.strip().split("\n"):
            p = line.split(":")
            if len(p) >= 2 and p[0].strip():
                nets.append({"ssid": p[0], "signal": int(p[1]) if len(p)>1 and p[1].isdigit() else 0,
                            "security": p[2] if len(p)>2 else ""})
        seen = set()
        uniq = [n for n in sorted(nets, key=lambda x: -x["signal"]) if not (n["ssid"] in seen or seen.add(n["ssid"]))]
        return {"networks": uniq[:20]}
    except Exception:
        return {"networks": [], "error": "WiFi扫描仅Linux盒子可用"}


@app.post("/api/setup/wifi-connect")
async def setup_wifi_connect(req: dict):
    ssid = str(req.get("ssid","")).strip()
    pw = str(req.get("password","")).strip()
    if not ssid:
        raise HTTPException(status_code=400, detail="请选择WiFi网络")
    import subprocess
    try:
        args = ["nmcli","dev","wifi","connect",ssid]
        if pw: args += ["password", pw]
        subprocess.run(args, capture_output=True, timeout=30, check=True)
        return {"ok": True, "ssid": ssid}
    except subprocess.CalledProcessError:
        raise HTTPException(status_code=400, detail="WiFi密码错误或信号弱")
    except Exception:
        raise HTTPException(status_code=400, detail="WiFi连接失败")

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": VERSION}

@app.get("/api/health/deep")
async def health_deep(username: str = Depends(require_admin_or_reviewer)):
    """深度健康检查：验证API Key、Embedding模型、知识库"""
    try:
        from rag import call_deepseek
        call_deepseek("ping", "pong", temperature=0)
        api_ok = True
    except Exception:
        api_ok = False
    try:
        from search_engine import get_embedding_model
        get_embedding_model()
        model_ok = True
    except Exception:
        model_ok = False
    try:
        from search_engine import get_collection
        col = get_collection()
        chunk_count = col.count()
    except Exception:
        chunk_count = 0
    return {"status": "ok", "api_key_ok": api_ok, "model_ok": model_ok, "chunks": chunk_count}


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
async def register(req: AuthRequest, request: Request = None, username: str = Depends(require_auth)):
    """仅管理员可创建新用户（学校场景，关闭公开注册）"""
    role = get_user_role(username)
    if role != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可创建用户")
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
        raise HTTPException(status_code=400, detail=str(e))
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
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
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

@app.post("/api/admin/reviews/{record_id}/reject")
async def admin_reject(record_id: str, req: dict = {}, username: str = Depends(require_admin_or_reviewer)):
    comment = str(req.get("comment", "")) if isinstance(req, dict) else ""
    ok = reject_review(record_id, username, comment)
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


# ---- 教案评价（老师上传自己的教案，AI对照知识库评价） ----

@app.post("/api/evaluate")
async def evaluate_plan(file: UploadFile = FastAPIFile(...), username: str = Depends(require_auth)):
    """上传教案文件，AI对照知识库中的优秀教案进行评价"""
    fn = file.filename or "untitled"
    ext = Path(fn).suffix.lower()
    if ext not in (".md", ".txt", ".docx"):
        raise HTTPException(status_code=400, detail="仅支持 .md / .txt / .docx 格式")
    # 上传安全：大小限制 + 安全文件名
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过5MB")

    # 解析文档内容（复用已读取的 data 变量）
    if ext == ".docx":
        from docx import Document as DocxDoc
        doc = DocxDoc(io.BytesIO(data))
        content = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        content = data.decode("utf-8", errors="ignore")

    if len(content) < 200:
        raise HTTPException(status_code=400, detail="教案内容过短，至少200字符")

    # 提取课题名
    import re
    match = re.search(r'《(.+?)》', content)
    lesson_name = match.group(1) if match else Path(fn).stem

    # 检索知识库中的同类优秀教案
    from rag import retrieve_structured, call_deepseek
    context, _ = retrieve_structured(f"{lesson_name} 教案", top_k=8)

    # 调用评价 Prompt
    from prompts import EVALUATE_SYSTEM, EVALUATE_USER
    eval_prompt = EVALUATE_USER.format(uploaded_plan=content[:6000], context=context, lesson_name=lesson_name)
    try:
        evaluation = call_deepseek(EVALUATE_SYSTEM, eval_prompt, temperature=0.3)
    except Exception:
        raise HTTPException(status_code=500, detail="评价生成失败，请稍后重试")

    return {"evaluation": evaluation, "lesson_name": lesson_name}


# ---- 教案导出 ----

@app.get("/api/export/{plan_id}")
async def export_plan(plan_id: str, format: str = "md", username: str = Depends(require_auth)):
    """导出教案为 md / docx"""
    from auth import get_history_detail
    detail = get_history_detail(username, plan_id)
    if not detail:
        raise HTTPException(status_code=404, detail="教案不存在")

    plan_text = detail.get("lesson_plan", "")
    guide_text = detail.get("teaching_guide", "")
    lesson = detail.get("lesson", "教案")
    grade = detail.get("grade", "")

    if format == "md":
        full = plan_text
        if guide_text:
            full += "\n\n---\n\n" + guide_text
        from fastapi.responses import Response
        return Response(content=full.encode("utf-8"), media_type="text/markdown",
                       headers={"Content-Disposition": f"attachment; filename={lesson}_教案.md"})

    elif format == "docx":
        from docx import Document
        from docx.shared import Pt
        doc = Document()
        doc.styles["Normal"].font.size = Pt(11)
        doc.add_heading(f"《{lesson}》教案", 0)
        if grade:
            doc.add_paragraph(f"年级：{grade}", style="Subtitle")

        for line in plan_text.split("\n"):
            if line.startswith("# "):
                doc.add_heading(line[2:], 1)
            elif line.startswith("## "):
                doc.add_heading(line[3:], 2)
            elif line.startswith("### "):
                doc.add_heading(line[4:], 3)
            elif line.strip():
                doc.add_paragraph(line.strip())

        if guide_text:
            doc.add_page_break()
            doc.add_heading("教案辅导说明", 1)
            for line in guide_text.split("\n"):
                if line.startswith("# "):
                    doc.add_heading(line[2:], 1)
                elif line.startswith("## "):
                    doc.add_heading(line[3:], 2)
                elif line.strip():
                    doc.add_paragraph(line.strip())

        buf = io.BytesIO()
        doc.save(buf)
        buf.seek(0)
        return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                headers={"Content-Disposition": f"attachment; filename={lesson}_教案.docx"})

    raise HTTPException(status_code=400, detail="仅支持 md / docx 格式")


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
    # 上传安全：大小限制 + 安全文件名
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过5MB")

    # 解析文档内容（复用已读取的 data 变量）
    if ext == ".docx":
        from docx import Document as DocxDoc
        doc = DocxDoc(io.BytesIO(data))
        content = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    else:
        content = data.decode("utf-8", errors="ignore")

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
    safe_name = _re.sub(r'[《》\s/:*?"<>|]', '', lesson_name)[:100]
    dest = Path(__file__).resolve().parent.parent / "knowledge-base" / f"{safe_name}.md"
    from security import atomic_write
    atomic_write(dest, formatted.encode("utf-8"))

    # 触发入库
    import subprocess, sys
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve().parent.parent / "scripts" / "ingest_knowledge.py")],
            capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            import logging
            logging.getLogger("lekai").error("入库失败: %s", (result.stderr or result.stdout or "")[:500])
            return {"ok": False, "lesson": lesson_name, "message": f"《{lesson_name}》入库失败，请查看服务端日志"}
        return {"ok": True, "lesson": lesson_name, "message": f"《{lesson_name}》已入库"}
    except Exception:
        return {"ok": False, "lesson": lesson_name, "message": f"《{lesson_name}》已保存，请手动运行入库脚本"}


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
        "version": VERSION,
    }


# ---- start ----


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
