"""
Mutelens - Scoring Engine v3.0
================================
基于 LLM 语义评估的文章质量评分引擎。
6 个核心维度 + 前置 Veto Gate，加权求和，透明公正。

公式：
  Step 0: Veto Gate    → 极端噪音直接归零（节省 LLM 调用）
  Step 1: LLM 评估     → 6 个维度各 1-10 分
  Step 2: Final = Σ(wᵢ × Dᵢ) × 10 → 归一化到 0-100
"""

import re
from dataclasses import dataclass

from llm_evaluator import LLMEvaluation


# ─── 维度权重 ────────────────────────────────────────────────────────────────

DIMENSION_WEIGHTS: dict[str, float] = {
    "d1": 0.22,   # 原创洞见
    "d2": 0.20,   # 论证质量
    "d3": 0.15,   # 信息密度
    "d4": 0.20,   # 前瞻性
    "d5": 0.18,   # 内容深度
    "d6": 0.05,   # 信源可信度
}

DIMENSION_META: list[dict] = [
    {"key": "d1", "label": "原创洞见", "label_en": "Original Insight"},
    {"key": "d2", "label": "论证质量", "label_en": "Argument Quality"},
    {"key": "d3", "label": "信息密度", "label_en": "Information Density"},
    {"key": "d4", "label": "前瞻性", "label_en": "Forward-Looking"},
    {"key": "d5", "label": "内容深度", "label_en": "Analytical Depth"},
    {"key": "d6", "label": "信源可信度", "label_en": "Source Credibility"},
]


# ─── Veto Gate 关键词 ────────────────────────────────────────────────────────

EMOTIONAL_TRIGGERS: set[str] = {
    "shocking", "unbelievable", "insane", "destroyed", "explodes", "outrage",
    "terrifying", "disgusting", "evil", "stupid", "idiot", "moron",
    "!!!", "must see", "you won't believe", "wake up",
    "暴跌", "崩盘", "末日", "完蛋", "震惊", "怒了", "炸了",
}

CLICKBAIT_PATTERNS: list[str] = [
    r"\b\d+\s+(ways|things|reasons)",
    r"why .+ will .+ you",
    r"(secret|trick|hack) that",
    r"you (won't|need to|must)",
]


@dataclass
class DimensionScore:
    key: str
    label: str
    label_en: str
    score: float
    max_score: float
    description: str
    weight: float


@dataclass
class ScoringResult:
    overall_score: float
    grade: str
    vetoed: bool
    veto_reason: str
    dimensions: list[DimensionScore]
    weights: dict[str, float]
    analysis_summary: str


# ─── Veto Gate ────────────────────────────────────────────────────────────────

def veto_gate(title: str, content: str) -> tuple[bool, str]:
    """前置启发式检查，过滤明显垃圾内容以节省 LLM 调用成本。"""
    tl = str(title).lower()
    cl = str(content).lower()

    word_count = len(content.split())
    if word_count < 100:
        return True, f"正文过短（仅约 {word_count} 词），无法进行有效评估"

    clickbait_hits = sum(1 for p in CLICKBAIT_PATTERNS if re.search(p, tl, re.I))
    emotional_in_title = sum(1 for w in EMOTIONAL_TRIGGERS if w in tl)
    if clickbait_hits >= 2 and emotional_in_title >= 1:
        return True, f"极端标题党（{clickbait_hits} 个标题党模式 + {emotional_in_title} 个情绪操控词）"

    sponsor_hits = len(re.findall(
        r"\b(sponsor(ed)?|advertisement|advertorial|paid post|promoted|affiliate)\b"
        r"|赞助内容|广告推广"
        r"|\b(click here|sign up now|free trial|limited time offer)\b",
        cl, re.I,
    ))
    if sponsor_hits >= 3:
        return True, f"疑似广告/赞助内容（检测到 {sponsor_hits} 个广告信号）"

    emotional_in_content = sum(1 for w in EMOTIONAL_TRIGGERS if w in cl)
    if emotional_in_content >= 5:
        return True, f"极端情绪操控（正文中检测到 {emotional_in_content} 个情绪化词汇）"

    return False, ""


# ─── 评分等级 ─────────────────────────────────────────────────────────────────

def _get_grade(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B+"
    if score >= 60:
        return "B"
    if score >= 50:
        return "C"
    if score >= 40:
        return "D"
    return "F"


# ─── 主评分逻辑 ──────────────────────────────────────────────────────────────

def compute_score(llm_eval: LLMEvaluation) -> ScoringResult:
    """根据 LLM 评估结果计算最终分数。"""
    llm_scores = {
        "d1": llm_eval.d1_original_insight,
        "d2": llm_eval.d2_argument_quality,
        "d3": llm_eval.d3_information_density,
        "d4": llm_eval.d4_forward_looking,
        "d5": llm_eval.d5_analytical_depth,
        "d6": llm_eval.d6_source_credibility,
    }

    dims: list[DimensionScore] = []
    for meta in DIMENSION_META:
        key = meta["key"]
        llm_dim = llm_scores[key]
        dims.append(DimensionScore(
            key=key,
            label=meta["label"],
            label_en=meta["label_en"],
            score=llm_dim.score,
            max_score=10,
            description=llm_dim.reasoning,
            weight=DIMENSION_WEIGHTS[key],
        ))

    weighted_sum = sum(d.score * d.weight for d in dims)
    overall = round(weighted_sum * 10, 1)
    overall = max(0.0, min(100.0, overall))

    return ScoringResult(
        overall_score=overall,
        grade=_get_grade(overall),
        vetoed=False,
        veto_reason="",
        dimensions=dims,
        weights=DIMENSION_WEIGHTS,
        analysis_summary=llm_eval.summary,
    )


def create_vetoed_result(veto_reason: str) -> ScoringResult:
    """为被 Veto Gate 否决的文章创建结果。"""
    dims = [
        DimensionScore(
            key=meta["key"],
            label=meta["label"],
            label_en=meta["label_en"],
            score=0,
            max_score=10,
            description="已被 Veto Gate 否决",
            weight=DIMENSION_WEIGHTS[meta["key"]],
        )
        for meta in DIMENSION_META
    ]
    return ScoringResult(
        overall_score=0.0,
        grade="F",
        vetoed=True,
        veto_reason=veto_reason,
        dimensions=dims,
        weights=DIMENSION_WEIGHTS,
        analysis_summary=f"[VETO] 该文章被 Veto Gate 否决：{veto_reason}。内容存在严重质量问题，不建议阅读。",
    )
