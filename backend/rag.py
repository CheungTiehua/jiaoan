"""LeKai RAG Pipeline v0.3 — 混合检索 + Evidence Pack + 结构化同行参考"""

import sys
from pathlib import Path
import json
import re

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, DEEPSEEK_FAST_MODEL,
    DEEPSEEK_REASONING_EFFORT, DEEPSEEK_THINKING, DEEPSEEK_MAX_TOKENS,
    RETRIEVAL_TOP_K, PROMPTS_FILE
)
from prompts import (
    EXAM_ANALYSIS_SYSTEM, EXAM_ANALYSIS_USER,
    PEER_ANALYSIS_STRUCTURED_SYSTEM, PEER_ANALYSIS_STRUCTURED_USER,
    LESSON_PLAN_SYSTEM, LESSON_PLAN_USER,
    TEACHING_GUIDE_SYSTEM, TEACHING_GUIDE_USER,
    REVISE_SYSTEM, REVISE_USER,
    UNIT_PLAN_SYSTEM, UNIT_PLAN_USER,
    REFLECTION_SYSTEM, REFLECTION_USER,
)
from search_engine import search_hybrid, refresh_index
from lesson_evidence import build_lesson_evidence, format_lesson_evidence
from teaching_evidence import (
    build_generated_blocks,
    evidence_lookup,
    format_evidence_context,
    search_teaching_evidence,
    split_evidence,
    validate_block_citations,
)


# Multi-Key 轮询
import threading
_key_counter = 0
_key_lock = threading.Lock()
_keys = [k.strip() for k in DEEPSEEK_API_KEY.split(",") if k.strip()] if DEEPSEEK_API_KEY else []

# 启动时尝试从持久化文件加载 Key（Docker场景环境变量可能为空）
if not _keys:
    _key_file = Path(__file__).resolve().parent.parent / "data" / "api_key.json"
    if _key_file.exists():
        try:
            import json as _j
            _stored = _j.loads(_key_file.read_text()).get("api_key", "")
            _keys = [k.strip() for k in _stored.split(",") if k.strip()]
        except Exception as e:
            import logging
            logging.getLogger("lekai").warning("api_key.json 无法读取，将使用环境变量: %s", e)


def _get_api_key() -> str:
    global _key_counter
    with _key_lock:
        if not _keys:
            raise RuntimeError("请设置 DEEPSEEK_API_KEY")
        k = _keys[_key_counter % len(_keys)]
        _key_counter += 1
        return k


# 加载在线自定义 Prompt（管理员可修改，缓存+mtime检测）
import os as _os
_prompt_cache: dict = {}
_prompt_mtime: float = 0


def _load_custom_prompt(key: str) -> str | None:
    global _prompt_cache, _prompt_mtime
    if PROMPTS_FILE.exists():
        mtime = _os.path.getmtime(PROMPTS_FILE)
        if mtime != _prompt_mtime:
            try:
                import json
                _prompt_cache = json.loads(PROMPTS_FILE.read_text())
                _prompt_mtime = mtime
            except Exception:
                _prompt_cache = {}
        return _prompt_cache.get(key)
    return None


def reload_keys(api_key: str):
    """线程安全地重新加载 API Keys（setup完成后调用）"""
    global _keys
    with _key_lock:
        _keys[:] = [k.strip() for k in api_key.split(",") if k.strip()]


def _chat_completion_urls() -> list[str]:
    base = DEEPSEEK_BASE_URL.rstrip("/")
    if base.endswith("/chat/completions"):
        return [base]

    urls = []
    if base.endswith("/v1"):
        urls.append(f"{base}/chat/completions")
    else:
        urls.append(f"{base}/chat/completions")
        urls.append(f"{base}/v1/chat/completions")
    return list(dict.fromkeys(urls))


def _deepseek_error_message(resp: requests.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error", data)
        if isinstance(err, dict):
            return str(err.get("message") or err.get("detail") or err)
        return str(err)
    except ValueError:
        return resp.text[:300]


def _build_payload(
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    *,
    include_reasoning: bool = True,
    max_tokens: int | None = None,
    model: str | None = None,
    stream: bool = False,
) -> dict:
    payload = {
        "model": model or DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens or DEEPSEEK_MAX_TOKENS,
        "stream": stream,
    }
    if include_reasoning:
        # deepseek-v4-pro defaults to adaptive reasoning, which can spend most
        # completion tokens thinking before producing user-visible text. Lesson
        # generation is an authoring task, so keep reasoning off unless the
        # operator explicitly enables it.
        thinking_type = DEEPSEEK_THINKING or "disabled"
        payload["thinking"] = {"type": thinking_type}
        if thinking_type != "disabled" and DEEPSEEK_REASONING_EFFORT:
            payload["reasoning_effort"] = DEEPSEEK_REASONING_EFFORT
    return payload


def _post_deepseek(headers: dict, payload: dict, stream: bool = False) -> requests.Response:
    last_response = None
    last_error = None
    for url in _chat_completion_urls():
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=180, stream=stream)
        except requests.Timeout:
            raise RuntimeError("请求超时，请检查网络连接")
        except requests.ConnectionError as e:
            last_error = e
            continue
        if resp.status_code != 404:
            return resp
        last_response = resp

    if last_response is not None:
        return last_response
    if last_error is not None:
        raise RuntimeError("无法连接到 DeepSeek 服务，请检查网络")
    raise RuntimeError("DeepSeek 接口地址配置错误")


def call_deepseek(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    model: str | None = None,
) -> str:
    if not _keys:
        raise RuntimeError("请设置 DEEPSEEK_API_KEY")
    # 在线自定义 System Prompt（管理员可修改，仅替换 system_prompt）
    custom_sys = _load_custom_prompt("chat_prompt")
    if custom_sys:
        system_prompt = custom_sys

    headers = {"Authorization": f"Bearer {_get_api_key()}", "Content-Type": "application/json"}
    payload = _build_payload(system_prompt, user_prompt, temperature, max_tokens=max_tokens, model=model)
    resp = _post_deepseek(headers, payload)

    if resp.status_code == 400 and ("thinking" in resp.text or "reasoning" in resp.text):
        resp = _post_deepseek(headers, _build_payload(system_prompt, user_prompt, temperature, include_reasoning=False, max_tokens=max_tokens, model=model))

    if resp.status_code == 429:
        raise RuntimeError("API 请求过于频繁，请稍后重试")
    if resp.status_code == 401 or resp.status_code == 403:
        raise RuntimeError("API Key 无效或已过期")
    if resp.status_code == 402:
        raise RuntimeError("API 余额不足，请充值后重试")
    if resp.status_code >= 500:
        raise RuntimeError("DeepSeek 服务异常，请稍后重试")
    if resp.status_code >= 400:
        raise RuntimeError(f"DeepSeek 请求失败({resp.status_code}): {_deepseek_error_message(resp)}")
    try:
        return resp.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise RuntimeError("AI 返回数据异常，请稍后重试")


def stream_deepseek(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    model: str | None = None,
):
    """Yield OpenAI-compatible streaming content deltas."""
    if not _keys:
        raise RuntimeError("请设置 DEEPSEEK_API_KEY")
    custom_sys = _load_custom_prompt("chat_prompt")
    if custom_sys:
        system_prompt = custom_sys

    headers = {"Authorization": f"Bearer {_get_api_key()}", "Content-Type": "application/json"}
    payload = _build_payload(
        system_prompt,
        user_prompt,
        temperature,
        max_tokens=max_tokens,
        model=model,
        stream=True,
    )
    resp = _post_deepseek(headers, payload, stream=True)
    if resp.status_code == 400 and ("thinking" in resp.text or "reasoning" in resp.text):
        payload = _build_payload(
            system_prompt,
            user_prompt,
            temperature,
            include_reasoning=False,
            max_tokens=max_tokens,
            model=model,
            stream=True,
        )
        resp = _post_deepseek(headers, payload, stream=True)

    if resp.status_code == 429:
        raise RuntimeError("API 请求过于频繁，请稍后重试")
    if resp.status_code == 401 or resp.status_code == 403:
        raise RuntimeError("API Key 无效或已过期")
    if resp.status_code == 402:
        raise RuntimeError("API 余额不足，请充值后重试")
    if resp.status_code >= 500:
        raise RuntimeError("DeepSeek 服务异常，请稍后重试")
    if resp.status_code >= 400:
        raise RuntimeError(f"DeepSeek 请求失败({resp.status_code}): {_deepseek_error_message(resp)}")

    for raw_line in resp.iter_lines(decode_unicode=True):
        if not raw_line:
            continue
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            obj = json.loads(data)
            choice = (obj.get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            text = delta.get("content") or ""
            if text:
                yield text
        except json.JSONDecodeError:
            continue


def retrieve_structured(query: str, grade: str | None = None,
                        top_k: int = RETRIEVAL_TOP_K) -> tuple[str, dict]:
    """
    混合检索 + Evidence Pack 分层

    返回: (formatted_context, evidence_pack_dict)
    """
    results = search_hybrid(query, grade=grade, top_k=top_k * 2)
    pack = build_lesson_evidence(results, top_k_per_dim=3)
    context = format_lesson_evidence(pack)
    return context, pack


COMBINED_LESSON_SYSTEM = """你是一位资深小学语文教研员、命题专家和教案辅导员。
你的任务是一次性生成四个部分：考点分析、同行参考、完整教案、辅导说明。
必须严格使用指定 XML 标签包裹四个部分，不要输出标签以外的任何内容。"""


COMBINED_LESSON_USER = """请为《{lesson}》（{grade}{semester}册）生成完整备课结果。

## 用户需求
- 年级：{grade}
- 课题：《{lesson}》
- 课时：{class_hours}课时
- 特殊要求：{requirements}

## 知识库检索参考
{context}

## 输出格式
必须严格输出以下四个标签，每个标签内用 Markdown：

<exam_analysis>
# 《{lesson}》考点分析
## 一、字词考点
## 二、句型与修辞考点
## 三、阅读理解考点
## 四、写作迁移考点
## 五、高频易错点
</exam_analysis>

<peer_analysis>
# 《{lesson}》结构化教学参考
## 一、教材解读维度
## 二、教学目标维度
## 三、教学过程设计维度
## 四、板书/作业维度
## 五、避坑提醒
</peer_analysis>

<lesson_plan>
# 《{lesson}》教案
## 一、教材分析
## 二、学情分析
## 三、教学目标
### 知识与能力
### 过程与方法
### 情感态度与价值观
## 四、教学重难点
## 五、教学准备
## 六、教学过程
### 第一课时
#### （一）导入新课（X分钟）
#### （二）初读课文，整体感知（X分钟）
#### （三）精读品味，深入理解（X分钟）
#### （四）课堂小结（X分钟）
## 七、板书设计
## 八、作业布置
## 九、教学反思（留给老师填写）
</lesson_plan>

<teaching_guide>
# 《{lesson}》教案辅导说明
## 一、本课教学定位
## 二、教学设计亮点分析
## 三、考点覆盖检查
## 四、优秀教案的共性标准
## 五、实施建议与避坑指南
## 六、拓展与迁移
</teaching_guide>

要求：
1. 四个标签必须全部出现，标签名不能改。
2. 教案必须完整可直接使用，教学过程要有可执行活动。
3. 考点分析和教案中的练习设计要互相呼应。
4. 同行参考如知识库不足，要明确写“知识库参考不足”，再给通用建议。
5. 总输出尽量控制在 7000-9000 汉字以内。"""


def _extract_tag(text: str, tag: str) -> str:
    m = re.search(rf'<{tag}>\s*([\s\S]*?)\s*</{tag}>', text)
    return m.group(1).strip() if m else ""


def _generate_lesson_combined(
    grade: str,
    lesson: str,
    context: str,
    requirements: str,
    class_hours: str,
    semester: str,
) -> dict:
    prompt = COMBINED_LESSON_USER.format(
        grade=grade,
        lesson=lesson,
        semester=semester,
        class_hours=class_hours,
        requirements=requirements or "无特殊要求",
        context=context,
    )
    raw = call_deepseek(COMBINED_LESSON_SYSTEM, prompt, temperature=0.25, max_tokens=8192)
    result = {
        "exam_analysis": _extract_tag(raw, "exam_analysis"),
        "peer_analysis": _extract_tag(raw, "peer_analysis"),
        "lesson_plan": _extract_tag(raw, "lesson_plan"),
        "teaching_guide": _extract_tag(raw, "teaching_guide"),
    }
    missing = [k for k, v in result.items() if len(v.strip()) < 80]
    if missing:
        raise RuntimeError(f"AI 返回格式异常，缺少字段: {', '.join(missing)}")
    return result


FAST_LESSON_PLAN_SYSTEM = """你是一位资深小学语文教研员。
你的任务只生成“完整教案”，不要生成考点分析、同行参考或辅导说明。
要求结构完整、活动可执行、语言精炼，适合老师快速拿去上课。"""


FAST_LESSON_PLAN_USER = """请为《{lesson}》（{grade}{semester}册）生成一份可直接使用的教案。

## 用户需求
- 年级：{grade}
- 课题：《{lesson}》
- 课时：{class_hours}课时
- 特殊要求：{requirements}

## 规范性依据（只能作为教学目标、重难点、考点等判断的依据）
{normative_context}

## 方法参考（只能作为课堂活动设计参考，不能作为权威依据）
{method_context}

## 知识库规则
1. 教材、课标、考纲、单元目标等规范性依据不足时，不要伪造出处。
2. 教学设计指导和老教师案例只能内化为设计方法，不能写成“依据证明”。
3. 教案正文仍必须完整可用，依据不足处用稳妥表述处理。
4. 如果下面的“依据状态”提示缺少规范依据：
   - “教材分析”开头必须写明“依据提示：当前未检索到教材/课标原文，以下教材分析为待复核建议。”
   - 不得把方法参考中的“册次、单元、语文要素、课标要求、考点”写成确定的权威结论。
   - 教学目标和重难点要用“建议目标”“建议重点”等措辞，不得写“依据课标/教材要求”。

## 依据状态
{evidence_warning}

## 原始检索参考
{context}

## 输出要求
只输出 Markdown 教案，按以下结构：
# 《{lesson}》教案
## 一、教材分析
## 二、学情分析
## 三、教学目标
### 知识与能力
### 过程与方法
### 情感态度与价值观
## 四、教学重难点
## 五、教学准备
## 六、教学过程
按 {class_hours} 课时设计，用表格呈现，每个环节写清“时间 / 教师活动 / 学生活动 / 设计意图”，每格控制在 1-2 句话。
## 七、板书设计
## 八、作业布置
## 九、教学反思

控制在 1200-1700 汉字。不要输出教案以外内容。"""


def _generate_lesson_plan_fast(
    grade: str,
    lesson: str,
    context: str,
    requirements: str,
    class_hours: str,
    semester: str,
    normative_context: str = "（未检索到规范性依据）",
    method_context: str = "（未检索到方法参考）",
) -> str:
    prompt = _fast_lesson_plan_prompt(
        grade=grade,
        lesson=lesson,
        context=context,
        requirements=requirements,
        class_hours=class_hours,
        semester=semester,
        normative_context=normative_context,
        method_context=method_context,
    )
    lesson_plan = call_deepseek(FAST_LESSON_PLAN_SYSTEM, prompt, temperature=0.25, max_tokens=1900, model=DEEPSEEK_FAST_MODEL)
    if len(lesson_plan.strip()) < 500:
        raise RuntimeError("AI 返回教案过短，请稍后重试")
    return lesson_plan


def _fast_lesson_plan_prompt(
    grade: str,
    lesson: str,
    context: str,
    requirements: str,
    class_hours: str,
    semester: str,
    normative_context: str = "（未检索到规范性依据）",
    method_context: str = "（未检索到方法参考）",
) -> str:
    normative_missing = (
        "知识库没有检索到可用材料" in normative_context
        or "未检索到规范性依据" in normative_context
        or "缺少" in normative_context[:120]
    )
    evidence_warning = (
        "缺少教材、课标、考纲或单元目标等规范性依据。必须生成完整教案，但教材分析、教学目标、重难点只能作为待复核建议，不得写成权威结论。"
        if normative_missing
        else "已检索到规范性依据。教学目标、重难点和教材分析可以引用规范依据形成判断。"
    )
    return FAST_LESSON_PLAN_USER.format(
        grade=grade,
        lesson=lesson,
        semester=semester,
        class_hours=class_hours,
        requirements=requirements or "无特殊要求",
        normative_context=normative_context,
        method_context=method_context,
        evidence_warning=evidence_warning,
        context=context,
    )


def prepare_lesson_evidence(grade: str, lesson: str, semester: str, requirements: str = "") -> dict:
    evidence, missing = search_teaching_evidence(
        grade=grade,
        semester=semester,
        lesson=lesson,
        purpose="lesson_plan",
        max_items=16,
    )
    normative, method = split_evidence(evidence)
    return {
        "evidence": evidence,
        "normative": normative,
        "method": method,
        "missing": missing,
        "normative_context": format_evidence_context(normative),
        "method_context": format_evidence_context(method),
        "combined_context": format_evidence_context(evidence),
    }


def stream_lesson_plan(
    grade: str,
    lesson: str,
    requirements: str = "",
    class_hours: str = "2",
    semester: str = "上",
    evidence_bundle: dict | None = None,
):
    search_query = f"{grade} {semester}学期 《{lesson}》{requirements}"
    context, _ = retrieve_structured(search_query, grade=grade)
    evidence_bundle = evidence_bundle or prepare_lesson_evidence(grade, lesson, semester, requirements)
    prompt = _fast_lesson_plan_prompt(
        grade=grade,
        lesson=lesson,
        context=context,
        normative_context=evidence_bundle["normative_context"],
        method_context=evidence_bundle["method_context"],
        requirements=requirements,
        class_hours=class_hours,
        semester=semester,
    )
    yield from stream_deepseek(
        FAST_LESSON_PLAN_SYSTEM,
        prompt,
        temperature=0.25,
        max_tokens=1900,
        model=DEEPSEEK_FAST_MODEL,
    )


# ============================================================
# 生成 Pipeline（增强版）
# ============================================================

def generate_lesson(
    grade: str, lesson: str,
    requirements: str = "", class_hours: str = "2", semester: str = "上"
) -> dict:

    search_query = f"{grade} {semester}学期 《{lesson}》{requirements}"
    context, evidence_pack = retrieve_structured(search_query, grade=grade)
    evidence_bundle = prepare_lesson_evidence(grade, lesson, semester, requirements)
    lesson_plan = _generate_lesson_plan_fast(
        grade=grade,
        lesson=lesson,
        context=context,
        requirements=requirements,
        class_hours=class_hours,
        semester=semester,
        normative_context=evidence_bundle["normative_context"],
        method_context=evidence_bundle["method_context"],
    )
    blocks = build_generated_blocks(lesson_plan, evidence_bundle["normative"], evidence_bundle["method"])
    evidence = evidence_bundle["evidence"]
    return {
        "exam_analysis": "",
        "peer_analysis": "",
        "lesson_plan": lesson_plan,
        "teaching_guide": "",
        "generated_blocks": blocks,
        "teaching_evidence": evidence,
        "missing_evidence": evidence_bundle["missing"],
        "citation_errors": validate_block_citations(blocks, evidence_lookup(evidence)),
    }


def generate_exam_analysis(grade: str, lesson: str, semester: str = "上") -> str:
    return generate_exam_analysis_bundle(grade, lesson, semester)["text"]


def generate_exam_analysis_bundle(grade: str, lesson: str, semester: str = "上") -> dict:
    evidence, missing = search_teaching_evidence(
        grade=grade,
        semester=semester,
        lesson=lesson,
        purpose="exam_analysis",
        source_roles=["normative"],
        max_items=12,
    )
    if not evidence:
        text = (
            f"# 《{lesson}》考点分析\n\n"
            "## 依据不足\n"
            "知识库中缺少该课对应的教材、课标、考纲、单元目标或考试资料。"
            "为避免凭空生成，本系统暂不输出可追溯考点结论。\n\n"
            "## 建议补充资料\n"
            "- 教材原文或单元页\n- 课程标准/考纲\n- 单元目标\n- 试题或考试说明\n"
        )
        return {"text": text, "evidence": evidence, "generated_blocks": [{
            "id": "exam_insufficient",
            "block_type": "exam_point",
            "text": text,
            "evidence_ids": [],
            "reference_ids": [],
            "evidence_status": "insufficient",
        }], "missing": missing}
    context = format_evidence_context(evidence)
    prompt = EXAM_ANALYSIS_USER.format(grade=grade, lesson=lesson, semester=semester)
    prompt += "\n\n## 规范性依据\n" + context + "\n\n要求：所有考点结论必须来自上述规范性依据；依据不足处必须说明不足。"
    text = call_deepseek(EXAM_ANALYSIS_SYSTEM, prompt, temperature=0.2, max_tokens=1400, model=DEEPSEEK_FAST_MODEL)
    blocks = [{
        "id": "exam_supported",
        "block_type": "exam_point",
        "text": text[:1200],
        "evidence_ids": [e["id"] for e in evidence[:5]],
        "reference_ids": [],
        "evidence_status": "supported",
    }]
    return {"text": text, "evidence": evidence, "generated_blocks": blocks, "missing": missing}


def generate_peer_analysis(grade: str, lesson: str, semester: str = "上") -> str:
    return generate_peer_analysis_bundle(grade, lesson, semester)["text"]


def generate_peer_analysis_bundle(grade: str, lesson: str, semester: str = "上") -> dict:
    evidence, missing = search_teaching_evidence(
        grade=grade,
        semester=semester,
        lesson=lesson,
        purpose="peer_reference",
        source_roles=["method_case"],
        max_items=12,
    )
    if not evidence:
        text = (
            f"# 《{lesson}》同行参考\n\n"
            "## 参考不足\n"
            "知识库中缺少教学设计指导、老教师教案、本校案例或进修校案例。"
            "暂不输出同行做法，避免把模型经验误当作本校经验。\n"
        )
        return {"text": text, "evidence": evidence, "generated_blocks": [], "missing": missing}
    context = format_evidence_context(evidence)
    prompt = PEER_ANALYSIS_STRUCTURED_USER.format(
        grade=grade, lesson=lesson, semester=semester, context=context
    )
    prompt += "\n\n要求：以上材料只能称为“参考/做法/案例”，不得称为“权威依据”。"
    text = call_deepseek(PEER_ANALYSIS_STRUCTURED_SYSTEM, prompt, temperature=0.25, max_tokens=1700, model=DEEPSEEK_FAST_MODEL)
    blocks = [{
        "id": "peer_reference",
        "block_type": "guidance",
        "text": text[:1200],
        "evidence_ids": [],
        "reference_ids": [e["id"] for e in evidence[:6]],
        "evidence_status": "not_required",
    }]
    return {"text": text, "evidence": evidence, "generated_blocks": blocks, "missing": missing}


def generate_teaching_guide(
    lesson: str,
    lesson_plan: str,
    exam_analysis: str = "",
    peer_analysis: str = "",
) -> str:
    return generate_teaching_guide_bundle(lesson, lesson_plan, exam_analysis, peer_analysis)["text"]


def generate_teaching_guide_bundle(
    lesson: str,
    lesson_plan: str,
    exam_analysis: str = "",
    peer_analysis: str = "",
    grade: str = "",
    semester: str = "上",
) -> dict:
    evidence, missing = search_teaching_evidence(
        grade=grade,
        semester=semester,
        lesson=lesson,
        purpose="guidance",
        max_items=16,
    )
    normative, method = split_evidence(evidence)
    prompt = TEACHING_GUIDE_USER.format(
        lesson_plan=lesson_plan,
        exam_analysis=exam_analysis or "尚未生成考点分析。",
        peer_analysis=peer_analysis or "尚未生成同行参考。",
        lesson=lesson,
    )
    prompt += (
        "\n\n## 规范依据（可称为依据）\n" + format_evidence_context(normative) +
        "\n\n## 方法参考（只能称为参考）\n" + format_evidence_context(method) +
        "\n\n要求：必须把“依据”和“参考”分开表达；老教师案例和教学设计指导不得作为权威依据。"
        "如果没有规范依据，不得使用“符合课标/教材要求/单元语文要素”等权威判断，只能说“从当前教案文本看”或“参考做法显示”。"
    )
    text = call_deepseek(TEACHING_GUIDE_SYSTEM, prompt, temperature=0.25, max_tokens=1700, model=DEEPSEEK_FAST_MODEL)
    boundary = (
        "## 依据与参考边界\n"
        f"- 规范依据：{'已检索到，可用于目标、重难点和考点判断。' if normative else '依据不足，当前知识库缺少教材、课标、考纲或单元目标，以下不作权威教学结论。'}\n"
        f"- 方法参考：{'已检索到，只作为备课方法和活动设计参考。' if method else '参考不足，当前知识库缺少教学设计指导或老教师案例。'}\n\n"
    )
    text = boundary + text
    blocks = [{
        "id": "guide",
        "block_type": "guidance",
        "text": text[:1200],
        "evidence_ids": [e["id"] for e in normative[:5]],
        "reference_ids": [e["id"] for e in method[:5]],
        "evidence_status": "supported" if normative else "insufficient",
    }]
    return {"text": text, "evidence": evidence, "generated_blocks": blocks, "missing": missing}


def generate_unit_plan(grade: str, unit: str, semester: str = "上") -> str:
    """生成单元整体规划"""
    context, _ = retrieve_structured(f"{grade} {semester}册 {unit}", grade=grade)
    prompt = UNIT_PLAN_USER.format(grade=grade, semester=semester, unit=unit, context=context)
    return call_deepseek(UNIT_PLAN_SYSTEM, prompt, temperature=0.3)


def generate_reflection(lesson: str, lesson_plan: str) -> str:
    """生成课后反思引导"""
    prompt = REFLECTION_USER.format(lesson=lesson, lesson_plan=lesson_plan)
    return call_deepseek(REFLECTION_SYSTEM, prompt, temperature=0.4)


def revise_lesson(current_plan: str, revision_request: str, history: str = "") -> str:
    prompt = REVISE_USER.format(
        current_plan=current_plan, revision_request=revision_request,
        conversation_history=history or "（首次修改）"
    )
    return call_deepseek(REVISE_SYSTEM, prompt, temperature=0.3)
