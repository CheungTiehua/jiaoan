"""LeKai v0.2 — 四层输出 + 教材目录 + 对话修改"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag import generate_lesson, revise_lesson
from scripts.all_textbooks import GRADE_TEXTBOOKS

app = FastAPI(
    title="LeKai教案知识库 API",
    description="小学语文教案智能生成平台 v0.2",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


# ---- Models ----

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


# ---- API ----

@app.get("/api/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/api/textbooks")
async def textbooks():
    """返回全年级教材目录树"""
    tree = []
    for grade in ["一年级", "二年级", "三年级", "四年级", "五年级", "六年级"]:
        grade_data = GRADE_TEXTBOOKS.get(grade, {})
        semesters = []
        for sem_name in ["上册", "下册"]:
            sem_data = grade_data.get(sem_name, {})
            units = []
            for unit_name, lessons in sem_data.items():
                units.append({"name": unit_name, "lessons": lessons})
            semesters.append({"name": sem_name, "units": units})
        tree.append({"grade": grade, "semesters": semesters})
    return {"textbooks": tree}


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """四步生成：考点分析 → 同行参考 → 教案 → 辅导说明"""
    if not req.lesson.strip():
        raise HTTPException(status_code=400, detail="课题名称不能为空")

    try:
        result = generate_lesson(
            grade=req.grade, lesson=req.lesson.strip(),
            requirements=req.requirements.strip(),
            class_hours=req.class_hours, semester=req.semester
        )
        return GenerateResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


@app.post("/api/revise", response_model=ReviseResponse)
async def revise(req: ReviseRequest):
    """对话式修改教案"""
    if not req.current_plan.strip():
        raise HTTPException(status_code=400, detail="请提供当前教案")
    if not req.revision_request.strip():
        raise HTTPException(status_code=400, detail="请说明修改要求")

    try:
        new_plan = revise_lesson(req.current_plan, req.revision_request, req.history)
        return ReviseResponse(lesson_plan=new_plan)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"修改失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
