"""
教案采集与格式化工具

功能：
1. 从 URL 抓取教案原始内容（支持百度文库、学科网等）
2. 用 DeepSeek 将原始内容格式化为标准 Markdown 模板
3. 保存到 knowledge-base/ 目录

使用方式：
    # 方式1：从URL采集
    python scripts/collect_lesson.py --url "https://wenku.baidu.com/xxx" --grade 3 --lesson "富饶的西沙群岛"

    # 方式2：从剪贴板/文本文件采集
    python scripts/collect_lesson.py --file raw_lesson.txt --grade 3 --lesson "富饶的西沙群岛"

    # 方式3：交互模式（粘贴文本）
    python scripts/collect_lesson.py --interactive --grade 3 --lesson "富饶的西沙群岛"

环境变量：
    DEEPSEEK_API_KEY: DeepSeek API密钥
    DEEPSEEK_BASE_URL: API地址（默认 https://api.deepseek.com）
"""

import argparse
import os
import re
import sys
from pathlib import Path

import requests

# ============================================================
# 配置
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_BASE = PROJECT_ROOT / "knowledge-base"
TEMPLATE_PATH = KNOWLEDGE_BASE / "TEMPLATE.md"

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = "deepseek-chat"

FORMAT_PROMPT = """你是一位小学语文教研员。请将以下原始教案内容，整理为规范的 Markdown 格式教案。

## 输出要求

1. **严格按照以下模板结构输出**，不要遗漏任何章节
2. 保留原始教案中的所有教学设计和要点
3. 语言专业、规范，符合小学语文教学用语
4. 如果原始内容缺失某个章节，用你的专业知识补充完整
5. 补充元数据（YAML frontmatter）中的 tags，用 3-5 个关键词描述本课特点

## 输出模板

```markdown
---
grade: {grade}
semester: {semester}
unit:
lesson: {lesson}
type:
class_hours:
tags: []
source:
source_url: {source_url}
curated_by: LeKai采集工具
curated_date: {date}
---

# 《{lesson}》教案

## 一、教材分析

## 二、学情分析

## 三、教学目标

### 知识与能力
1.

### 过程与方法
1.

### 情感态度与价值观
1.

## 四、教学重难点

**重点：**

**难点：**

## 五、教学准备

## 六、教学过程

### 第一课时

#### （一）导入新课

#### （二）初读课文，整体感知

#### （三）精读品味，深入理解

#### （四）课堂小结

### 第二课时

#### （一）复习导入

#### （二）深入研读

#### （三）拓展延伸

#### （四）课堂总结

## 七、板书设计

## 八、作业布置

## 九、教学反思
```

## 原始教案内容

{raw_content}

请直接输出完整的 Markdown 教案，不要加任何解释。"""


# ============================================================
# 内容获取
# ============================================================

def fetch_from_url(url: str) -> str:
    """从 URL 获取原始内容"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        # 简单提取文本（去除 HTML 标签）
        text = re.sub(r'<script[^>]*>.*?</script>', '', resp.text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        return text[:15000]  # 截断，控制 token 消耗
    except Exception as e:
        print(f"[ERROR] 获取URL失败: {e}")
        sys.exit(1)


def read_from_file(filepath: str) -> str:
    """从文件读取原始内容"""
    path = Path(filepath)
    if not path.exists():
        print(f"[ERROR] 文件不存在: {filepath}")
        sys.exit(1)
    return path.read_text(encoding="utf-8")


def read_interactive() -> str:
    """交互式读取（粘贴文本）"""
    print("\n请粘贴教案原始内容（粘贴完成后输入 :done 回车）:\n")
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == ":done":
                break
            lines.append(line)
        except EOFError:
            break
    return "\n".join(lines)


# ============================================================
# DeepSeek 格式化
# ============================================================

def format_with_deepseek(
    raw_content: str,
    grade: str,
    lesson: str,
    semester: str = "上",
    source_url: str = ""
) -> str:
    """用 DeepSeek 将原始内容格式化为标准教案"""

    if not DEEPSEEK_API_KEY:
        print("[ERROR] 请设置环境变量 DEEPSEEK_API_KEY")
        sys.exit(1)

    from datetime import date

    prompt = FORMAT_PROMPT.format(
        grade=grade,
        semester=semester,
        lesson=lesson,
        source_url=source_url,
        date=date.today().isoformat(),
        raw_content=raw_content
    )

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": "你是一位资深小学语文教研员，擅长编写和审校教案。"},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 4096
    }

    try:
        resp = requests.post(
            f"{DEEPSEEK_BASE_URL}/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=120
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] DeepSeek API调用失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"  Response: {e.response.text[:500]}")
        sys.exit(1)


# ============================================================
# 保存
# ============================================================

def save_lesson(content: str, grade: str, lesson: str, semester: str) -> Path:
    """保存教案到 knowledge-base 目录"""
    # 生成文件名
    safe_lesson = re.sub(r'[《》\s]', '', lesson)
    grade_dir = KNOWLEDGE_BASE / f"grade-{grade}"
    grade_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{safe_lesson}.md"
    filepath = grade_dir / filename

    filepath.write_text(content, encoding="utf-8")
    print(f"[OK] 教案已保存: {filepath}")
    return filepath


# ============================================================
# 主入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="LeKai教案采集与格式化工具")
    parser.add_argument("--url", help="教案页面URL")
    parser.add_argument("--file", help="原始教案文本文件路径")
    parser.add_argument("--interactive", action="store_true", help="交互式粘贴模式")
    parser.add_argument("--grade", required=True, help="年级（如：三年级）")
    parser.add_argument("--lesson", required=True, help="课题名称（如：富饶的西沙群岛）")
    parser.add_argument("--semester", default="上", choices=["上", "下"], help="学期")

    args = parser.parse_args()

    # 获取原始内容
    if args.url:
        print(f"[INFO] 从URL获取: {args.url}")
        raw_content = fetch_from_url(args.url)
    elif args.file:
        print(f"[INFO] 从文件读取: {args.file}")
        raw_content = read_from_file(args.file)
    elif args.interactive:
        raw_content = read_interactive()
    else:
        parser.print_help()
        sys.exit(1)

    if len(raw_content) < 50:
        print("[ERROR] 获取的内容太短，请检查输入")
        sys.exit(1)

    print(f"[INFO] 获取到 {len(raw_content)} 字符原始内容")
    print(f"[INFO] 正在用 DeepSeek 格式化...")

    # 格式化
    formatted = format_with_deepseek(
        raw_content=raw_content,
        grade=args.grade,
        lesson=args.lesson,
        semester=args.semester,
        source_url=args.url or ""
    )

    # 保存
    save_lesson(formatted, args.grade, args.lesson, args.semester)

    print("\n--- 格式化结果预览（前500字）---")
    print(formatted[:500])
    print("...")


if __name__ == "__main__":
    main()
