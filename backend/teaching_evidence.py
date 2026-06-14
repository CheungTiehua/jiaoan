"""Embedded teaching evidence layer.

DEE is integrated into LeKai as the evidence model and provenance metadata
rules, not as a separate runtime service. This module keeps teaching-domain
evidence rules out of generic RAG code, adapts local indexed chunks into
TeachingEvidence, and accepts DEE EvidenceObject-shaped data during import.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

from search_engine import get_collection, search_hybrid

SourceRole = Literal["normative", "method_case"]
EvidenceStatus = Literal["supported", "insufficient", "not_required"]

NORMATIVE_DOC_TYPES = {
    "textbook", "curriculum_standard", "exam_outline", "unit_goal", "exam_material",
}
METHOD_DOC_TYPES = {
    "teaching_guidance", "teacher_case", "local_case", "training_case",
}
ALL_DOC_TYPES = NORMATIVE_DOC_TYPES | METHOD_DOC_TYPES

PURPOSE_DEFAULTS: dict[str, tuple[list[SourceRole], list[str]]] = {
    "lesson_plan": (["normative", "method_case"], ["textbook", "curriculum_standard", "unit_goal", "teaching_guidance", "teacher_case", "local_case", "training_case"]),
    "exam_analysis": (["normative"], ["textbook", "curriculum_standard", "exam_outline", "unit_goal", "exam_material"]),
    "peer_reference": (["method_case"], ["teaching_guidance", "teacher_case", "local_case", "training_case"]),
    "guidance": (["normative", "method_case"], ["textbook", "curriculum_standard", "exam_outline", "unit_goal", "exam_material", "teaching_guidance", "teacher_case", "local_case", "training_case"]),
}

DOC_TYPE_LABELS = {
    "textbook": "教材",
    "curriculum_standard": "课标",
    "exam_outline": "考纲",
    "unit_goal": "单元目标",
    "exam_material": "考试资料",
    "teaching_guidance": "教学设计指导",
    "teacher_case": "老教师案例",
    "local_case": "本校案例",
    "training_case": "进修校案例",
}


class TeachingEvidence(TypedDict, total=False):
    id: str
    source_role: SourceRole
    doc_type: str
    doc_title: str
    grade: str
    semester: str
    unit: str
    lesson: str
    page_num: int
    page_width: int
    page_height: int
    bbox: list[float]
    content: str
    confidence: float
    source_file_id: str
    source_file_name: str
    source_hash: str
    page_image_url: str
    dee_url: str


class GeneratedBlock(TypedDict):
    id: str
    block_type: str
    text: str
    evidence_ids: list[str]
    reference_ids: list[str]
    evidence_status: EvidenceStatus


def infer_doc_type(meta: dict[str, Any], text: str = "") -> str:
    explicit = str(meta.get("doc_type") or meta.get("document_type") or "").strip()
    if explicit in ALL_DOC_TYPES:
        return explicit

    locator = " ".join(str(meta.get(k, "")) for k in ["source", "source_file", "doc_title", "source_file_name"]).lower()
    lesson_type = str(meta.get("lesson_type") or meta.get("type") or "").lower()
    body_head = text[:500].lower()
    if any(k in locator for k in ["课标", "课程标准", "curriculum"]):
        return "curriculum_standard"
    if any(k in locator for k in ["考纲", "考试说明", "exam_outline"]):
        return "exam_outline"
    if any(k in locator for k in ["单元目标", "unit_goal"]):
        return "unit_goal"
    if any(k in locator for k in ["题库", "试题", "考点", "exam_material"]):
        return "exam_material"
    if any(k in locator for k in ["教材", "课文原文", "textbook"]):
        return "textbook"

    if "教案" in body_head or "教学过程" in body_head or lesson_type.endswith("课"):
        return "local_case"

    haystack = f"{locator}\n{body_head}"
    if any(k in haystack for k in ["教学设计与指导", "教学指导", "teaching_guidance"]):
        return "teaching_guidance"
    if any(k in haystack for k in ["进修校", "training"]):
        return "training_case"
    if any(k in haystack for k in ["老教师", "teacher_case"]):
        return "teacher_case"
    return "local_case"


def infer_source_role(meta: dict[str, Any], doc_type: str) -> SourceRole:
    explicit = str(meta.get("source_role") or "").strip()
    if explicit in ("normative", "method_case"):
        return explicit  # type: ignore[return-value]
    return "normative" if doc_type in NORMATIVE_DOC_TYPES else "method_case"


def to_teaching_evidence(result: dict[str, Any]) -> TeachingEvidence:
    meta = result.get("meta") or {}
    text = result.get("text") or ""
    doc_type = infer_doc_type(meta, text)
    source_role = infer_source_role(meta, doc_type)
    source_file = str(meta.get("source_file_id") or meta.get("source_file") or result.get("id") or "")
    source_file_name = str(meta.get("source_file_name") or meta.get("source_file") or source_file)
    page_num = int(meta.get("page_num") or meta.get("page") or 0)
    page_image_url = str(meta.get("page_image_url") or meta.get("image_url") or "")
    dee_url = str(meta.get("dee_url") or meta.get("source_url") or "")
    return {
        "id": str(result.get("id") or meta.get("id") or source_file),
        "source_role": source_role,
        "doc_type": doc_type,
        "doc_title": str(meta.get("doc_title") or source_file_name or meta.get("lesson") or source_file or "知识库材料"),
        "grade": str(meta.get("grade") or ""),
        "semester": str(meta.get("semester") or ""),
        "unit": str(meta.get("unit") or ""),
        "lesson": str(meta.get("lesson") or ""),
        "page_num": page_num,
        "page_width": int(meta.get("page_width") or 0),
        "page_height": int(meta.get("page_height") or 0),
        "bbox": _parse_bbox(meta.get("bbox")),
        "content": text,
        "confidence": float(meta.get("confidence") or 1.0),
        "source_file_id": source_file,
        "source_file_name": source_file_name,
        "source_hash": str(meta.get("source_hash") or ""),
        "page_image_url": page_image_url,
        "dee_url": dee_url,
    }


def from_dee_evidence_object(
    obj: dict[str, Any],
    *,
    source_role: str | None = None,
    doc_type: str | None = None,
) -> TeachingEvidence:
    """Convert a DEE EvidenceObject/EvidencePack item into TeachingEvidence."""
    evidence_obj = obj.get("evidence") if isinstance(obj.get("evidence"), dict) else obj
    meta = evidence_obj.get("metadata") or evidence_obj.get("meta") or {}
    text = str(
        evidence_obj.get("content")
        or evidence_obj.get("text")
        or evidence_obj.get("quote")
        or obj.get("content")
        or ""
    )
    merged = {
        **meta,
        "doc_type": doc_type or obj.get("doc_type") or evidence_obj.get("doc_type") or meta.get("doc_type"),
        "source_role": source_role or obj.get("source_role") or evidence_obj.get("source_role") or meta.get("source_role"),
        "source_file_id": evidence_obj.get("source_file_id") or obj.get("source_file_id") or meta.get("source_file_id"),
        "source_file_name": evidence_obj.get("source_file_name") or obj.get("source_file_name") or meta.get("source_file_name"),
        "source_hash": evidence_obj.get("source_hash") or obj.get("source_hash") or meta.get("source_hash"),
        "page_num": evidence_obj.get("page_num") or obj.get("page_num") or meta.get("page_num"),
        "page_width": evidence_obj.get("page_width") or obj.get("page_width") or meta.get("page_width"),
        "page_height": evidence_obj.get("page_height") or obj.get("page_height") or meta.get("page_height"),
        "bbox": evidence_obj.get("bbox") or obj.get("bbox") or meta.get("bbox"),
        "page_image_url": evidence_obj.get("page_image_url") or obj.get("page_image_url") or meta.get("page_image_url"),
        "dee_url": evidence_obj.get("dee_url") or obj.get("dee_url") or meta.get("dee_url"),
        "doc_title": obj.get("doc_title") or evidence_obj.get("doc_title") or meta.get("doc_title"),
        "grade": obj.get("grade") or evidence_obj.get("grade") or meta.get("grade"),
        "semester": obj.get("semester") or evidence_obj.get("semester") or meta.get("semester"),
        "unit": obj.get("unit") or evidence_obj.get("unit") or meta.get("unit"),
        "lesson": obj.get("lesson") or evidence_obj.get("lesson") or meta.get("lesson"),
        "confidence": obj.get("confidence") or evidence_obj.get("confidence") or meta.get("confidence") or obj.get("relevance"),
    }
    return to_teaching_evidence({
        "id": evidence_obj.get("id") or obj.get("id") or obj.get("evidence_id"),
        "text": text,
        "meta": merged,
        "score": obj.get("score") or obj.get("relevance") or 1.0,
    })


def _parse_bbox(value: Any) -> list[float]:
    if isinstance(value, list):
        return [float(v) for v in value if isinstance(v, (int, float))]
    if isinstance(value, str) and value.strip():
        try:
            import json
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [float(v) for v in parsed if isinstance(v, (int, float))]
        except Exception:
            return []
    return []


def search_teaching_evidence(
    *,
    grade: str,
    semester: str,
    lesson: str,
    purpose: str,
    source_roles: list[str] | None = None,
    doc_types: list[str] | None = None,
    max_items: int = 20,
) -> tuple[list[TeachingEvidence], list[str]]:
    default_roles, default_types = PURPOSE_DEFAULTS.get(purpose, PURPOSE_DEFAULTS["lesson_plan"])
    role_filter = set(source_roles or default_roles)
    type_filter = set(doc_types or default_types)
    scan_limit = max(max_items * 3, 10)
    raw = _scan_local_chunks(grade=grade, semester=semester, lesson=lesson, max_items=scan_limit)
    if not raw:
        query = f"{grade} {semester}册 《{lesson}》 {purpose}"
        try:
            raw = search_hybrid(query, grade=grade, top_k=scan_limit)
        except Exception as exc:
            import logging
            logging.getLogger("lekai").warning("混合检索失败，本地元数据也没有命中: %s", exc)
            raw = []
    evidence = [
        item for item in (to_teaching_evidence(r) for r in raw)
        if item["source_role"] in role_filter and item["doc_type"] in type_filter
    ][:max_items]

    missing: list[str] = []
    if "normative" in role_filter and not any(e["source_role"] == "normative" for e in evidence):
        missing.append("缺少教材、课标、考纲或单元目标等规范性依据")
    if "method_case" in role_filter and not any(e["source_role"] == "method_case" for e in evidence):
        missing.append("缺少教学设计指导、老教师案例或本校案例等方法参考")
    return evidence, missing


def _scan_local_chunks(*, grade: str, semester: str, lesson: str, max_items: int) -> list[dict[str, Any]]:
    """Fallback retrieval that does not require an embedding model."""
    collection = get_collection()
    if collection.count() == 0:
        return []
    result = collection.get(include=["documents", "metadatas"], limit=2000)
    rows: list[dict[str, Any]] = []
    lesson_key = lesson.strip()
    for cid, doc, meta in zip(
        result.get("ids") or [],
        result.get("documents") or [],
        result.get("metadatas") or [],
    ):
        meta = meta or {}
        meta_grade = str(meta.get("grade") or "")
        meta_semester = str(meta.get("semester") or "")
        meta_lesson = str(meta.get("lesson") or meta.get("doc_title") or "")
        if grade and meta_grade and meta_grade != grade:
            continue
        if semester and meta_semester and meta_semester != semester:
            continue
        if lesson_key and lesson_key not in meta_lesson and lesson_key not in str(doc or "")[:500]:
            continue
        score = 1.0
        if lesson_key and lesson_key == meta_lesson:
            score += 1.0
        if grade and meta_grade == grade:
            score += 0.2
        if semester and meta_semester == semester:
            score += 0.2
        rows.append({"id": cid, "text": doc or "", "meta": meta, "score": score})
    rows.sort(key=lambda item: item["score"], reverse=True)
    return rows[:max_items]


def split_evidence(evidence: list[TeachingEvidence]) -> tuple[list[TeachingEvidence], list[TeachingEvidence]]:
    normative = [e for e in evidence if e["source_role"] == "normative"]
    method = [e for e in evidence if e["source_role"] == "method_case"]
    return normative, method


def format_evidence_context(evidence: list[TeachingEvidence]) -> str:
    if not evidence:
        return "（知识库没有检索到可用材料）"
    lines = []
    for idx, item in enumerate(evidence, start=1):
        role_label = "依据" if item["source_role"] == "normative" else "参考"
        doc_label = DOC_TYPE_LABELS.get(item["doc_type"], item["doc_type"])
        page = f"第{item['page_num']}页" if item.get("page_num") else "页码待补"
        lines.append(
            f"[{role_label}{idx}][{item['id']}][{doc_label}] {item['doc_title']} · {page}\n"
            f"{item['content'][:900]}"
        )
    return "\n\n".join(lines)


def evidence_lookup(evidence: list[TeachingEvidence]) -> dict[str, TeachingEvidence]:
    return {item["id"]: item for item in evidence}


def validate_block_citations(blocks: list[GeneratedBlock], evidence_map: dict[str, TeachingEvidence]) -> list[str]:
    errors: list[str] = []
    for block in blocks:
        for eid in block.get("evidence_ids", []):
            if evidence_map.get(eid, {}).get("source_role") != "normative":
                errors.append(f"{block['id']} 的 evidence_id {eid} 不是规范性依据")
        for rid in block.get("reference_ids", []):
            if evidence_map.get(rid, {}).get("source_role") != "method_case":
                errors.append(f"{block['id']} 的 reference_id {rid} 不是方法样本")
    return errors


def build_generated_blocks(
    lesson_plan: str,
    normative: list[TeachingEvidence],
    method: list[TeachingEvidence],
) -> list[GeneratedBlock]:
    evidence_ids = [e["id"] for e in normative[:3]]
    reference_ids = [e["id"] for e in method[:3]]
    sections = _split_markdown_sections(lesson_plan)
    block_specs = [
        ("textbook_analysis", ["教材分析"], True, False),
        ("student_analysis", ["学情分析"], False, False),
        ("teaching_goal", ["教学目标"], True, False),
        ("key_point", ["教学重难点", "教学重点"], True, False),
        ("teaching_activity", ["教学过程"], False, True),
        ("board_design", ["板书设计"], False, True),
        ("homework", ["作业布置", "作业"], False, False),
        ("guidance", ["教学反思"], False, True),
    ]
    blocks: list[GeneratedBlock] = []
    for index, (block_type, names, requires_evidence, uses_reference) in enumerate(block_specs, start=1):
        text = _find_section_text(sections, names)
        if not text:
            continue
        block_evidence = evidence_ids if requires_evidence and evidence_ids else []
        status: EvidenceStatus
        if requires_evidence:
            status = "supported" if block_evidence else "insufficient"
        else:
            status = "not_required"
        blocks.append({
            "id": f"block_{index}_{block_type}",
            "block_type": block_type,
            "text": text[:1200],
            "evidence_ids": block_evidence,
            "reference_ids": reference_ids if uses_reference and reference_ids else [],
            "evidence_status": status,
        })
    if not blocks:
        blocks.append({
            "id": "block_1_lesson_plan",
            "block_type": "teaching_activity",
            "text": lesson_plan[:1200],
            "evidence_ids": [],
            "reference_ids": reference_ids,
            "evidence_status": "not_required",
        })
    return blocks


def _split_markdown_sections(text: str) -> dict[str, str]:
    import re
    matches = list(re.finditer(r"^#{1,3}\s*(?:[一二三四五六七八九十]+、)?\s*(.+?)\s*$", text, re.M))
    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        title = match.group(1).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[title] = text[start:end].strip()
    return sections


def _find_section_text(sections: dict[str, str], names: list[str]) -> str:
    for title, body in sections.items():
        if any(name in title for name in names):
            return f"## {title}\n{body}".strip()
    return ""


def get_teaching_evidence_by_id(evidence_id: str) -> TeachingEvidence | None:
    collection = get_collection()
    result = collection.get(ids=[evidence_id], include=["documents", "metadatas"])
    if not result or not result.get("ids"):
        return None
    return to_teaching_evidence({
        "id": result["ids"][0],
        "text": (result.get("documents") or [""])[0],
        "meta": (result.get("metadatas") or [{}])[0],
        "score": 1.0,
    })
