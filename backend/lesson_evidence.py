"""
教案 Evidence Pack — 按教学维度分层检索结果

借鉴 zhishiku evidence_pack.py 的设计，将检索到的教案 chunk
按教学维度分类：教材分析/教学目标/教学过程/板书/作业/反思
"""

from typing import List, Dict, Tuple

# 教学维度定义
DIMENSION_KEYWORDS: Dict[str, List[str]] = {
    "教材分析": [
        "教材分析", "课文", "单元", "编排", "文体", "结构特点",
        "语文要素", "统编版", "主题"
    ],
    "教学目标": [
        "教学目标", "知识与能力", "过程与方法", "情感态度", "核心素养",
        "识字", "写字", "朗读", "理解", "体会", "感受"
    ],
    "教学过程": [
        "教学过程", "导入", "初读", "精读", "研读", "品读", "感悟",
        "第一课时", "第二课时", "环节", "活动", "探究", "小组合作",
        "指名读", "齐读", "默读", "范读", "练笔", "仿写"
    ],
    "板书设计": [
        "板书设计", "板书", "结构图", "思维导图"
    ],
    "作业布置": [
        "作业", "课后", "练习", "背诵", "阅读", "搜集", "预习"
    ],
    "教学反思": [
        "教学反思", "反思", "不足", "改进", "建议", "注意"
    ],
}


def classify_chunk(text: str) -> Tuple[str, float]:
    """基于关键词匹配的教学维度分类"""
    best_dim = "其他"
    best_score = 0.0
    for dim, keywords in DIMENSION_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        score = hits / max(len(keywords), 1)
        if score > best_score:
            best_score = score
            best_dim = dim
    return best_dim, min(best_score * 4, 1.0)


def build_lesson_evidence(
    search_results: List[dict],
    top_k_per_dim: int = 3,
) -> Dict[str, List[dict]]:
    """
    将检索结果按教学维度分组，每组保留 top-k

    参数:
        search_results: [{"text": str, "meta": dict, "score": float}, ...]
        top_k_per_dim: 每个维度最多保留的 chunk 数

    返回:
        {"教材分析": [...], "教学目标": [...], ...}
    """
    classified: Dict[str, List[dict]] = {}
    for r in search_results:
        dim, _ = classify_chunk(r["text"])
        if dim not in classified:
            classified[dim] = []
        classified[dim].append(r)

    # 每类内按原始分数排序，取 top-k
    pack = {}
    for dim, chunks in classified.items():
        chunks.sort(key=lambda x: x.get("score", 0), reverse=True)
        pack[dim] = chunks[:top_k_per_dim]

    return pack


def format_lesson_evidence(
    pack: Dict[str, List[dict]],
    max_chars: int = 600,
) -> str:
    """将 Evidence Pack 格式化为 Prompt 文本"""
    if not pack:
        return "（当前知识库中缺少该课参考教案，系统仅基于通用教学经验和统编版教材要求生成。建议联系管理员导入相关教案以提升质量。）"

    lines = []
    for dim, chunks in pack.items():
        lines.append(f"\n### {dim}参考")
        for i, c in enumerate(chunks, 1):
            lesson = c["meta"].get("lesson", "未知")
            text = c["text"][:max_chars]
            score = c.get("score", 0)
            source_info = f"《{lesson}》" if lesson else ""
            lines.append(f"\n【{dim}{i}】{source_info} (相关度:{score:.2f})\n{text}")

    return "\n".join(lines)
