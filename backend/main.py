"""LeKai v0.4 — 多用户 + 认证 + 历史"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from rag import generate_lesson, revise_lesson
from scripts.all_textbooks import GRADE_TEXTBOOKS
from auth import (
    register_user, login_user, logout_user, get_user_from_token,
    list_users, save_history, get_history, get_history_detail,
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
    return {"token": token, "username": req.username}


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
        # 保存历史
        save_history(username, req.grade, req.lesson.strip(), result)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
