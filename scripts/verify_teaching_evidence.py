#!/usr/bin/env python3
"""Verify LeKai embedded teaching-evidence rules.

This is a lightweight business-logic check for the evidence refactor. It does
not call DeepSeek and does not require a separate DEE service.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = PROJECT_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(PROJECT_ROOT))

from teaching_evidence import (  # noqa: E402
    from_dee_evidence_object,
    search_teaching_evidence,
    split_evidence,
    validate_block_citations,
)


def check(name: str, ok: bool, detail: str = "") -> bool:
    marker = "PASS" if ok else "FAIL"
    print(f"[{marker}] {name}{': ' + detail if detail else ''}")
    return ok


def main() -> int:
    failures = 0

    normative = from_dee_evidence_object({
        "id": "verify_normative_1",
        "doc_type": "textbook",
        "source_role": "normative",
        "doc_title": "统编版三年级上册",
        "grade": "三年级",
        "semester": "上",
        "lesson": "秋天的雨",
        "page_num": 42,
        "page_width": 1200,
        "page_height": 1800,
        "bbox": [10, 20, 300, 80],
        "source_file_id": "textbook-demo",
        "source_hash": "sha256-demo",
        "content": "课文原文证据片段",
    })
    method = from_dee_evidence_object({
        "id": "verify_method_1",
        "doc_type": "local_case",
        "source_role": "method_case",
        "doc_title": "本校老教师教案",
        "grade": "三年级",
        "semester": "上",
        "lesson": "秋天的雨",
        "content": "课堂活动参考片段",
    })

    failures += 0 if check(
        "DEE EvidenceObject can be imported into embedded TeachingEvidence",
        normative["source_role"] == "normative"
        and normative["doc_type"] == "textbook"
        and normative["page_num"] == 42
        and normative["bbox"] == [10.0, 20.0, 300.0, 80.0],
    ) else 1

    citation_errors = validate_block_citations([
        {
            "id": "block_bad_goal",
            "block_type": "teaching_goal",
            "text": "错误地把方法案例当依据",
            "evidence_ids": [method["id"]],
            "reference_ids": [normative["id"]],
            "evidence_status": "supported",
        }
    ], {normative["id"]: normative, method["id"]: method})
    failures += 0 if check(
        "citation validation rejects role mixing",
        len(citation_errors) == 2,
        "；".join(citation_errors),
    ) else 1

    try:
        evidence, missing = search_teaching_evidence(
            grade="三年级",
            semester="上",
            lesson="秋天的雨",
            purpose="guidance",
            max_items=50,
        )
        normative_items, method_items = split_evidence(evidence)
        failures += 0 if check(
            "local embedded evidence search returns normative placeholders",
            len(normative_items) > 0,
            f"normative={len(normative_items)} method={len(method_items)}",
        ) else 1
        failures += 0 if check(
            "local embedded evidence search returns method references",
            len(method_items) > 0,
            f"method={len(method_items)} normative={len(normative_items)}",
        ) else 1
        failures += 0 if check(
            "placeholder library satisfies coverage presence checks",
            not missing,
            f"missing={missing}",
        ) else 1
    except Exception as exc:
        failures += 1
        check("local embedded evidence search", False, str(exc))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
