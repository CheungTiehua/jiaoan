#!/usr/bin/env python3
"""Create placeholder teaching-evidence documents.

These files are intentionally low-quality content placeholders. Their purpose
is to exercise the full evidence workflow before authorized source documents
are available.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge-base"

LESSONS = [
    {"grade_dir": "grade-1", "grade": "一年级", "semester": "上", "lesson": "对韵歌", "unit": "第五单元"},
    {"grade_dir": "grade-2", "grade": "二年级", "semester": "上", "lesson": "小蝌蚪找妈妈", "unit": "第一单元"},
    {"grade_dir": "grade-3", "grade": "三年级", "semester": "上", "lesson": "秋天的雨", "unit": "第二单元"},
    {"grade_dir": "grade-4", "grade": "四年级", "semester": "上", "lesson": "观潮", "unit": "第一单元"},
    {"grade_dir": "grade-5", "grade": "五年级", "semester": "上", "lesson": "慈母情深", "unit": "第六单元"},
    {"grade_dir": "grade-6", "grade": "六年级", "semester": "上", "lesson": "少年闰土", "unit": "第八单元"},
]

DOCS = [
    ("textbook", "normative", "教材占位", "教材原文与教材说明占位"),
    ("curriculum_standard", "normative", "课标占位", "课程标准条目占位"),
    ("exam_outline", "normative", "考纲占位", "考试说明与考点要求占位"),
    ("unit_goal", "normative", "单元目标占位", "单元语文要素与学习目标占位"),
    ("exam_material", "normative", "考点材料占位", "题型、命题方向与评价任务占位"),
    ("teaching_guidance", "method_case", "教学设计指导占位", "备课方法指导占位"),
    ("teacher_case", "method_case", "老教师案例占位", "老教师课堂经验占位"),
]


def body_for(doc_type: str, role: str, title: str, lesson: dict[str, str], index: int) -> str:
    name = lesson["lesson"]
    grade = lesson["grade"]
    unit = lesson["unit"]
    page = 10 + index
    frontmatter = f"""---
title: "{name}{title}"
doc_title: "{name}{title}"
grade: "{grade}"
semester: "{lesson['semester']}"
unit: "{unit}"
lesson: "{name}"
type: "占位材料"
doc_type: "{doc_type}"
source_role: "{role}"
source_file_id: "placeholder-{doc_type}-{name}"
source_file_name: "{name}{title}.md"
source_hash: "placeholder-{doc_type}-{name}"
page_num: {page}
page_width: 1200
page_height: 1800
bbox: [80, 120, 1040, 260]
tags: ["占位", "功能联调"]
---
"""
    if role == "normative":
        content = f"""
# 《{name}》{title}

## 教材分析
【占位规范依据】本材料用于临时补齐《{name}》在{grade}{lesson['semester']}册{unit}的规范依据覆盖。正式交付前必须替换为授权教材、课标、考纲或单元资料原文。

## 教学目标
1. 【占位】围绕《{name}》的核心内容，落实识字写字、朗读理解、语言积累与表达训练。
2. 【占位】结合{unit}学习任务，形成可观察、可评价的课堂学习目标。
3. 【占位】通过文本阅读和表达实践，提升语文学习兴趣与方法意识。

## 教学重难点
- 【占位重点】理解文本主要内容，积累关键语言形式。
- 【占位难点】把阅读理解转化为表达、复述或迁移练习。

## 教学准备
【占位】教材页图、课文朗读、字词卡片、课堂练习单。

## 教学过程
【占位规范材料】建议课堂过程先读通文本，再聚焦关键语句，最后完成表达迁移。此段只用于联调 evidence_ids，不代表正式教材结论。

## 作业布置
【占位】朗读或背诵指定语段，完成一项语言运用练习。
"""
    else:
        content = f"""
# 《{name}》{title}

## 教材分析
【占位方法参考】本材料用于临时补齐《{name}》的方法样本覆盖，只能显示为“参考”，不能显示为“依据”。

## 学情分析
【占位】年轻教师可先判断学生已有阅读经验，再安排朗读、圈画、交流和表达任务。

## 教学目标
【占位】目标书写可采用“知识能力 + 过程方法 + 情感态度”的三层结构，但正式目标仍需回到规范材料校验。

## 教学重难点
【占位】重难点可从文本特点、学生困难和课堂产出三方面综合确定。

## 教学过程
【占位参考做法】导入不宜过长；初读解决字词和整体感知；精读围绕一两个关键语段展开；结尾安排可完成的迁移练习。

## 板书设计
【占位】板书突出课题、关键词、写法和课堂生成。

## 教学反思
【占位】课后反思关注目标是否达成、活动是否有效、学生表达是否有支架。
"""
    return frontmatter + content.strip() + "\n"


def main() -> int:
    written = 0
    for lesson in LESSONS:
        lesson_dir = KNOWLEDGE_BASE / lesson["grade_dir"] / "placeholders"
        lesson_dir.mkdir(parents=True, exist_ok=True)
        for index, (doc_type, role, suffix, _) in enumerate(DOCS, start=1):
            path = lesson_dir / f"{lesson['lesson']}-{suffix}.md"
            path.write_text(body_for(doc_type, role, suffix, lesson, index), encoding="utf-8")
            written += 1
    print(f"created {written} placeholder files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
