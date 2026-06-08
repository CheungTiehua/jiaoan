"""
LeKai 教案质量评测脚本
借鉴 zhishiku eval_rag.py 模式：30题评测集，检查关键词覆盖 + 结构完整性
用法: python scripts/eval_lesson.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.rag import generate_lesson

EVAL_FILE = Path(__file__).resolve().parent.parent / "data" / "eval_questions.json"


def run():
    if not EVAL_FILE.exists():
        print(f"评测文件不存在: {EVAL_FILE}")
        return

    questions = json.loads(EVAL_FILE.read_text())["questions"]
    print(f"评测集: {len(questions)} 题\n{'='*70}")

    results = []
    by_cat = {}
    for i, q in enumerate(questions):
        t0 = time.time()
        try:
            result = generate_lesson(q["grade"], q["lesson"], q.get("req", ""), "2", "上")
        except Exception as e:
            print(f"  ❌ {q['id']} 生成失败: {e}")
            continue

        elapsed = int((time.time() - t0) * 1000)
        plan = result.get("lesson_plan", "")
        guide = result.get("teaching_guide", "")
        exam = result.get("exam_analysis", "")
        peer = result.get("peer_analysis", "")
        checks_kw = q.get("check", [])

        # 评分
        has_plan = len(plan) > 500
        has_guide = len(guide) > 500
        has_exam = len(exam) > 200
        has_peer = len(peer) > 200
        kw_hits = sum(1 for kw in checks_kw if kw in plan)
        kw_rate = kw_hits / len(checks_kw) if checks_kw else 1.0

        passed = has_plan and has_guide and has_exam and has_peer and kw_rate >= 0.5
        status = "✅" if passed else "⚠️" if has_plan else "❌"

        r = {
            "id": q["id"], "category": q["category"], "status": status,
            "lesson": q["lesson"], "plan_len": len(plan), "guide_len": len(guide),
            "exam_len": len(exam), "peer_len": len(peer),
            "kw_hit": f"{kw_hits}/{len(checks_kw)}", "elapsed_ms": elapsed,
        }
        results.append(r)
        cat = q["category"]
        if cat not in by_cat:
            by_cat[cat] = {"total": 0, "pass": 0}
        by_cat[cat]["total"] += 1
        if passed:
            by_cat[cat]["pass"] += 1

        print(f"  {status} {q['id']} [{q['category']:5s}] 《{q['lesson']}》 "
              f"plan={len(plan)}c exam={len(exam)}c peer={len(peer)}c "
              f"kw={kw_hits}/{len(checks_kw)} {elapsed}ms")

    # 汇总
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "✅")
    warned = sum(1 for r in results if r["status"] == "⚠️")
    failed = sum(1 for r in results if r["status"] == "❌")

    print(f"\n{'='*70}")
    print(f"  总计: {total}  通过: {passed}  部分: {warned}  失败: {failed}")
    print(f"  通过率: {passed/total*100:.1f}%" if total else "")
    print(f"\n  按类别:")
    for cat, stats in sorted(by_cat.items()):
        pct = stats["pass"] / stats["total"] * 100 if stats["total"] else 0
        bar = "█" * int(pct / 10) + "░" * (10 - int(pct / 10))
        print(f"    {cat:6s} {bar} {stats['pass']}/{stats['total']} ({pct:.0f}%)")

    # 保存
    outfile = EVAL_FILE.parent / "eval_results.json"
    json.dump({
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {"total": total, "passed": passed, "warned": warned, "failed": failed,
                     "pass_rate": round(passed/total*100, 1) if total else 0},
        "by_category": {c: {"pass": s["pass"], "total": s["total"],
                            "rate": round(s["pass"]/s["total"]*100, 1)} for c, s in by_cat.items()},
        "results": results,
    }, open(outfile, "w"), ensure_ascii=False, indent=2)
    print(f"\n  结果已保存: {outfile}")


if __name__ == "__main__":
    run()
