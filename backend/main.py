"""LeKai v0.4 — 多用户 + 认证 + 历史"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Header, Depends
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

app = FastAPI(
    title="LeKai教案知识库 API",
    description="小学语文教案智能生成平台 v0.4",
    version="0.4.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
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
    grade: str = Field(..., json_schema_extra={"example": "三年级"})
    lesson: str = Field(..., json_schema_extra={"example": "富饶的西沙群岛"})
    requirements: str = Field(default="", json_schema_extra={"example": "重点修辞手法"})
    class_hours: str = Field(default="2", json_schema_extra={"example": "2"})
    semester: str = Field(default="上", json_schema_extra={"example": "上"})


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
async def register(req: AuthRequest):
    ok, msg = register_user(req.username, req.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/api/login")
async def login(req: AuthRequest):
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
async def me(username: str = Header(default="", alias="X-Username")):
    # 这个接口由前端通过 token 解析后调用
    return {"username": username or "未登录"}


# ---- Protected API ----

@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest, username: str = Depends(require_auth)):
    if not req.lesson.strip():
        raise HTTPException(status_code=400, detail="课题名称不能为空")
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
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.post("/api/revise", response_model=ReviseResponse)
async def revise(req: ReviseRequest, username: str = Depends(require_auth)):
    if not req.current_plan.strip():
        raise HTTPException(status_code=400, detail="请提供当前教案")
    try:
        new_plan = revise_lesson(req.current_plan, req.revision_request, req.history)
        return ReviseResponse(lesson_plan=new_plan)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/history")
async def history(username: str = Depends(require_auth)):
    """获取当前用户的生成历史"""
    if not username:
        raise HTTPException(status_code=401, detail="请先登录")
    return {"history": get_history(username)}


@app.get("/api/history/{record_id}")
async def history_detail(record_id: str):
    """获取单条历史详情（暂不需认证，通过 id 访问）"""
    # 从任意用户目录查找
    from auth import HISTORY_DIR
    for user_dir in HISTORY_DIR.iterdir():
        if user_dir.is_dir():
            detail = get_history_detail(user_dir.name, record_id)
            if detail:
                return detail
    raise HTTPException(status_code=404, detail="记录不存在")


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
async def admin_reject(record_id: str, username: str = Depends(require_admin_or_reviewer)):
    # 从 query 参数获取打回意见
    from fastapi import Query
    ok = reject_review(record_id, username, "")
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
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


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
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
