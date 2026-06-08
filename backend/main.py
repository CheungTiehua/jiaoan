"""LeKai教案知识库 — FastAPI 后端服务"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from rag import generate_lesson

app = FastAPI(
    title="LeKai教案知识库 API",
    description="小学语文教案生成与辅导平台",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 数据模型
# ============================================================

def json_schema_extra(examples: dict) -> dict:
    return {"json_schema_extra": {"examples": [examples]}}


class GenerateRequest(BaseModel):
    grade: str = Field(..., description="年级，如'三年级'", json_schema_extra={"example": "三年级"})
    lesson: str = Field(..., description="课题名称", json_schema_extra={"example": "富饶的西沙群岛"})
    requirements: str = Field(default="", description="教学要求/特殊需求", json_schema_extra={"example": "2课时，重点修辞手法"})
    class_hours: str = Field(default="2", description="课时数", json_schema_extra={"example": "2"})
    semester: str = Field(default="上", description="学期（上/下）", json_schema_extra={"example": "上"})


class GenerateResponse(BaseModel):
    lesson_plan: str = Field(..., description="教案 Markdown")
    teaching_guide: str = Field(..., description="教案辅导说明 Markdown")
    references: list[str] = Field(default_factory=list, description="引用的参考教案")


class HealthResponse(BaseModel):
    status: str
    version: str


# ============================================================
# API 端点
# ============================================================

@app.get("/api/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok", version="0.1.0")


@app.post("/api/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    """生成教案 + 辅导说明"""
    if not req.lesson.strip():
        raise HTTPException(status_code=400, detail="课题名称不能为空")

    try:
        result = generate_lesson(
            grade=req.grade,
            lesson=req.lesson.strip(),
            requirements=req.requirements.strip(),
            class_hours=req.class_hours,
            semester=req.semester
        )
        return GenerateResponse(**result)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
