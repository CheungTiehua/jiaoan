"""
LeKai 种子知识库批量生成工具

为每个年级生成 2-5 篇代表性教案的种子教案，作为 RAG 检索基础。

使用方式：
    python scripts/seed_knowledge.py                    # 全部年级（每级3篇）
    python scripts/seed_knowledge.py --grade 3          # 只生成三年级
    python scripts/seed_knowledge.py --grade 3 --dry-run # 预览不生成

环境变量：
    DEEPSEEK_API_KEY: DeepSeek API密钥
"""

import argparse
import os
import re
import sys
from datetime import date
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge-base"

_key_file = PROJECT_ROOT / "data" / "api_key.json"
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not DEEPSEEK_API_KEY and _key_file.exists():
    try:
        import json as _json
        DEEPSEEK_API_KEY = _json.loads(_key_file.read_text()).get("api_key", "")
    except Exception:
        DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-pro")
DEEPSEEK_THINKING = os.environ.get("DEEPSEEK_THINKING", "enabled")
DEEPSEEK_REASONING_EFFORT = os.environ.get("DEEPSEEK_REASONING_EFFORT", "high")


def _post_deepseek(headers: dict, payload: dict, timeout: int = 180) -> requests.Response:
    base = DEEPSEEK_BASE_URL.rstrip("/")
    urls = [base] if base.endswith("/chat/completions") else [f"{base}/chat/completions", f"{base}/v1/chat/completions"]
    resp = None
    for url in dict.fromkeys(urls):
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 404:
            break
    if resp is not None and resp.status_code == 400 and ("thinking" in resp.text or "reasoning" in resp.text):
        payload = {k: v for k, v in payload.items() if k not in ("thinking", "reasoning_effort")}
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    return resp

# 每年级精选代表性课文（覆盖不同课型）
SEED_SELECTIONS = {
    "一年级": [
        {"title": "秋天", "semester": "上", "type": "阅读课", "tags": ["识字", "朗读", "秋天"]},
        {"title": "小小的船", "semester": "上", "type": "阅读课", "tags": ["儿歌", "想象", "叠词"]},
        {"title": "端午粽", "semester": "下", "type": "阅读课", "tags": ["传统文化", "亲情", "长句子朗读"]},
    ],
    "二年级": [
        {"title": "曹冲称象", "semester": "上", "type": "阅读课", "tags": ["历史故事", "逻辑思维", "动词"]},
        {"title": "黄山奇石", "semester": "上", "type": "阅读课", "tags": ["写景", "想象", "比喻"]},
        {"title": "雷雨", "semester": "下", "type": "阅读课", "tags": ["写景", "观察", "按顺序描写"]},
    ],
    "三年级": [
        {"title": "秋天的雨", "semester": "上", "type": "阅读课", "tags": ["写景", "比喻拟人", "语言美"]},
        {"title": "在牛肚子里旅行", "semester": "上", "type": "阅读课", "tags": ["童话", "科学知识", "对话"]},
        {"title": "赵州桥", "semester": "下", "type": "阅读课", "tags": ["说明文", "传统文化", "围绕中心句"]},
    ],
    "四年级": [
        {"title": "观潮", "semester": "上", "type": "阅读课", "tags": ["写景", "顺序描写", "朗读指导"]},
        {"title": "爬山虎的脚", "semester": "上", "type": "阅读课", "tags": ["观察", "说明方法", "连续观察"]},
        {"title": "猫", "semester": "下", "type": "阅读课", "tags": ["状物", "明贬实褒", "细节描写"]},
    ],
    "五年级": [
        {"title": "落花生", "semester": "上", "type": "阅读课", "tags": ["借物喻人", "详略得当", "对比"]},
        {"title": "圆明园的毁灭", "semester": "上", "type": "阅读课", "tags": ["爱国", "对比手法", "资料搜集"]},
        {"title": "草船借箭", "semester": "下", "type": "阅读课", "tags": ["古典名著", "人物形象", "情节"]},
    ],
    "六年级": [
        {"title": "草原", "semester": "上", "type": "阅读课", "tags": ["写景抒情", "情景交融", "比喻"]},
        {"title": "少年闰土", "semester": "上", "type": "阅读课", "tags": ["鲁迅", "人物描写", "回忆"]},
        {"title": "匆匆", "semester": "下", "type": "阅读课", "tags": ["散文", "珍惜时间", "连续问"]},
    ],
}

SEED_PROMPT = """你是一位资深小学语文教研员，精通统编版（部编版）教材。
请为以下课题生成一份专业、规范、可直接使用的完整教案。

## 课题信息
- 年级：{grade}
- 学期：{semester}
- 课题：《{lesson}》
- 课型：{lesson_type}
- 2课时

## 教案要求
1. 严格遵循统编版教材体系和教学理念
2. 体现语文核心素养（语言、思维、审美、文化）
3. 教学过程具体可操作，标注每个环节时间
4. 板书设计简洁结构化

## 输出格式
请严格按以下 Markdown 格式输出：

```markdown
---
grade: {grade}
semester: {semester}
unit:
lesson: {lesson}
type: {lesson_type}
class_hours: 2
tags: [{tags}]
source: LeKai种子生成
source_url: ""
curated_by: DeepSeek自动生成
curated_date: {date}
---

# 《{lesson}》教案

## 一、教材分析

## 二、学情分析

## 三、教学目标
### 知识与能力
### 过程与方法
### 情感态度与价值观

## 四、教学重难点
**重点：**
**难点：**

## 五、教学准备

## 六、教学过程
### 第一课时
#### （一）导入新课（X分钟）
#### （二）初读课文，整体感知（X分钟）
#### （三）精读品味，深入理解（X分钟）
#### （四）课堂小结（X分钟）

### 第二课时
#### （一）复习导入（X分钟）
#### （二）深入研读（X分钟）
#### （三）拓展延伸（X分钟）
#### （四）课堂总结（X分钟）

## 七、板书设计
## 八、作业布置
## 九、教学反思
```

直接输出 Markdown，不要加任何解释。"""


def generate_seed(grade: str, lesson: str, semester: str, lesson_type: str, tags: str) -> str:
    """用 DeepSeek 生成种子教案"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("请设置 DEEPSEEK_API_KEY")

    prompt = SEED_PROMPT.format(
        grade=grade,
        semester=semester,
        lesson=lesson,
        lesson_type=lesson_type,
        tags=tags,
        date=date.today().isoformat()
    )

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "你是一位资深小学语文教研员，擅长编写统编版教材教案。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.4,
        "max_tokens": 4096,
        "stream": False,
    }
    if DEEPSEEK_THINKING:
        payload["thinking"] = {"type": DEEPSEEK_THINKING}
        if DEEPSEEK_REASONING_EFFORT:
            payload["reasoning_effort"] = DEEPSEEK_REASONING_EFFORT

    resp = _post_deepseek(headers, payload, timeout=180)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def save_seed(content: str, grade: str, lesson: str) -> Path:
    """保存种子教案"""
    grade_map = {
        "一年级": "grade-1", "二年级": "grade-2", "三年级": "grade-3",
        "四年级": "grade-4", "五年级": "grade-5", "六年级": "grade-6",
    }
    grade_dir = KNOWLEDGE_BASE / grade_map.get(grade, f"grade-{grade}")
    grade_dir.mkdir(parents=True, exist_ok=True)

    safe_name = re.sub(r'[《》\s]', '', lesson)
    filepath = grade_dir / f"{safe_name}.md"
    filepath.write_text(content, encoding="utf-8")
    print(f"  ✅ {filepath.name}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="LeKai种子知识库批量生成")
    parser.add_argument("--grade", type=str, help="只生成指定年级（如：三年级）")
    parser.add_argument("--dry-run", action="store_true", help="预览不实际生成")
    args = parser.parse_args()

    if not DEEPSEEK_API_KEY and not args.dry_run:
        print("[ERROR] 请设置 DEEPSEEK_API_KEY")
        sys.exit(1)

    grades_to_gen = [args.grade] if args.grade else list(SEED_SELECTIONS.keys())

    for grade in grades_to_gen:
        if grade not in SEED_SELECTIONS:
            print(f"[WARN] 未知年级: {grade}")
            continue

        print(f"\n{'='*50}")
        print(f"📚 {grade}")
        print(f"{'='*50}")

        for seed in SEED_SELECTIONS[grade]:
            print(f"  📝 《{seed['title']}》({seed['semester']}册) ... ", end="", flush=True)

            if args.dry_run:
                print("预览")
                continue

            try:
                content = generate_seed(
                    grade=grade,
                    lesson=seed["title"],
                    semester=seed["semester"],
                    lesson_type=seed["type"],
                    tags=", ".join(seed["tags"])
                )
            except Exception as e:
                print(f"❌ 生成失败: {e}")
                continue
            try:
                save_seed(content, grade, seed["title"])
            except Exception as e:
                print(f"❌ 保存失败: {e}")
                print(f"   已生成内容（请手动保存）:\n{content[:500]}")

    print(f"\n[完成] 知识库目录: {KNOWLEDGE_BASE}")


if __name__ == "__main__":
    main()
