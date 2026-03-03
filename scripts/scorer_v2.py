"""
GISTER Content Value Scorer V2.0
==================================
10 个维度 + Veto Gate + 连续 Sigmoid 调节 + 时序衰减 + 读者画像

完整公式：
  Step 0: Veto Gate    → 极端噪音直接归零
  Step 1: B = Σ(wᵢ·Dᵢ)  → 加权基础分（D1-D5，按内容类型动态权重）
  Step 2: P = sigmoid 连续标题一致性调节
          K = tanh 连续传播速度调节
  Step 3: V_raw = B × P × K × e^(-λt)  → 时序衰减
  Step 4: V_personalized = V_raw × R(u)  → 读者画像（可选）
  Step 5: V_final = sigmoid_norm × 100   → 归一化到 0-100

用法：
  python3 scripts/scorer_v2.py                        # 对 ground_truth_samples.csv 打分
  python3 scripts/scorer_v2.py --input my.csv
  python3 scripts/scorer_v2.py --user-profile ai,llm,openai  # 指定读者兴趣词
"""

import argparse
import math
import re
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from email.utils import parsedate_to_datetime

# ─── 内容类型识别 ──────────────────────────────────────────────────────────────
CONTENT_TYPE_MAP = {
    "research":       "academic",
    "social_twitter": "kol_tweet",
    "social_reddit":  "kol_tweet",
    "newsletter":     "newsletter",
    "tech_news":      "breaking_news",
    "business":       "breaking_news",
    "government_policy": "breaking_news",
    "medium":         "newsletter",
}

# ─── 权重矩阵（5种内容类型 × 5个基础维度 D1-D5）─────────────────────────────
#     D1:事实密度  D2:新颖性  D3:信源质量  D4:时效性  D5:可操作性
WEIGHT_MATRIX = {
    "breaking_news": [0.18, 0.24, 0.22, 0.24, 0.12],
    "academic":      [0.35, 0.27, 0.27, 0.05, 0.06],
    "kol_tweet":     [0.18, 0.27, 0.22, 0.12, 0.21],
    "product_launch":[0.22, 0.15, 0.18, 0.15, 0.30],
    "newsletter":    [0.25, 0.19, 0.19, 0.11, 0.26],
}

# ─── 时序衰减系数 λ（按内容类型）──────────────────────────────────────────────
LAMBDA_MAP = {
    "breaking_news":  0.08,   # 半衰期 ~8.7h
    "kol_tweet":      0.05,   # 半衰期 ~14h
    "product_launch": 0.02,   # 半衰期 ~35h
    "academic":       0.003,  # 半衰期 ~10天（常青内容）
    "newsletter":     0.01,   # 半衰期 ~3天
}

# ─── 域名权威分 ───────────────────────────────────────────────────────────────
DOMAIN_TRUST = {
    # 官方产品
    "openai.com": 1.0, "anthropic.com": 1.0, "deepmind.com": 1.0,
    "blog.google": 1.0, "ai.meta.com": 1.0, "huggingface.co": 0.95,
    "mistral.ai": 0.95, "stability.ai": 0.9,
    # 顶级学术
    "arxiv.org": 0.98, "nature.com": 1.0, "science.org": 1.0,
    "proceedings.neurips.cc": 0.98, "icml.cc": 0.95,
    # 顶级媒体
    "technologyreview.com": 0.92, "wired.com": 0.85, "arstechnica.com": 0.85,
    "bloomberg.com": 0.88, "economist.com": 0.88, "ft.com": 0.85,
    # 科技媒体
    "techcrunch.com": 0.75, "theverge.com": 0.75, "scmp.com": 0.75,
    "restofworld.org": 0.85,
    # Newsletter
    "newsletter.pragmaticengineer.com": 0.95, "ben-evans.com": 0.92,
    "interconnects.ai": 0.88, "notboring.co": 0.82,
    "exponentialview.co": 0.88, "lastweekin.ai": 0.85,
    "sebastianraschka.com": 0.88, "importai.substack.com": 0.88,
    "tldr.tech": 0.78,
    # 中文
    "36kr.com": 0.72, "infoq.cn": 0.72, "sspai.com": 0.72,
    "ifanr.com": 0.68, "jiqizhixin.com": 0.82,
    # 社交
    "nitter.net": 0.62, "reddit.com": 0.58, "medium.com": 0.52,
    "substack.com": 0.62,
}

SOURCE_TIER_SCORE = {"high": 1.0, "medium": 0.65, "low": 0.25}

# ─── 高价值关键词 ──────────────────────────────────────────────────────────────
HIGH_VALUE_KW = {
    "ai", "llm", "gpt", "claude", "gemini", "openai", "deepmind", "anthropic",
    "agent", "model", "benchmark", "dataset", "research", "paper",
    "launch", "release", "funding", "acquisition", "regulation", "policy",
    "neural", "transformer", "diffusion", "robotics", "chip", "semiconductor",
    "open source", "autonomous", "startup", "breach", "quantum",
    "人工智能", "大模型", "智能体", "发布", "研究", "政策", "监管",
    "融资", "收购", "开源", "芯片", "突破", "算法", "数据", "安全",
}

# 情绪化词汇（触发 D10 扣分）
EMOTIONAL_TRIGGERS = {
    "shocking", "unbelievable", "insane", "destroyed", "explodes", "outrage",
    "terrifying", "disgusting", "evil", "stupid", "idiot", "moron",
    "!!!", "🔥🔥🔥", "must see", "you won't believe", "wake up",
    "暴跌", "崩盘", "末日", "完蛋", "震惊", "怒了", "炸了", "傻逼",
}

CLICKBAIT_PATTERNS = [
    r"\?$",                          # 标题以问号结尾（clickbait 常见）
    r"^\d+\s+(ways|things|reasons)", # "X ways to..."
    r"why .+ will .+ you",
    r"(secret|trick|hack) that",
    r"you (won't|need to|must)",
]


# ─── 工具函数 ──────────────────────────────────────────────────────────────────
def _get_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(str(url)).netloc.lstrip("www.")
    except Exception:
        return ""


def _get_content_type(source_type: str, title: str) -> str:
    ct = CONTENT_TYPE_MAP.get(str(source_type).lower(), "breaking_news")
    # 启发式：含 "launch" / "release" / "发布" 的推文归为产品发布
    tl = str(title).lower()
    if ct == "kol_tweet" and any(w in tl for w in ["launch", "release", "发布", "announce"]):
        ct = "product_launch"
    return ct


def _parse_age_hours(published_str: str) -> float:
    """返回文章发布距现在的小时数，解析失败返回 48（给中等惩罚）。"""
    if not published_str or str(published_str).strip() == "":
        return 48.0
    try:
        ts = None
        for fmt in [
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]:
            try:
                ts = datetime.strptime(str(published_str).strip(), fmt)
                break
            except ValueError:
                continue
        if ts is None:
            ts = parsedate_to_datetime(str(published_str))
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return max((now - ts).total_seconds() / 3600, 0.0)
    except Exception:
        return 48.0


# ─── 10 个维度计算 ────────────────────────────────────────────────────────────

def calc_d1_fact_density(content: str, title: str) -> float:
    """D1: 事实密度 — 数据、引用、可验证声明的密度。"""
    text = str(title) + " " + str(content)
    word_count = max(len(text.split()), 1)

    # 数字/百分比/货币
    numbers = len(re.findall(r"\b\d+\.?\d*\s*(%|million|billion|trillion|[kmb])\b|\$\d+|\d{4}年|\d+亿|\d+万", text, re.I))
    # 引用信号
    citations = len(re.findall(r"(according to|study|report|research|found|announced|said|per |源自|据|报告|研究|表示)", text, re.I))
    # 专业关键词命中
    kw_hits = sum(1 for kw in HIGH_VALUE_KW if kw in text.lower())

    score = (
        min(numbers / 3.0, 1.0) * 0.40
        + min(citations / 3.0, 1.0) * 0.35
        + min(kw_hits / 5.0, 1.0) * 0.25
    )
    return round(min(score * 10, 10.0), 2)  # 返回 0-10 分


def calc_d2_novelty(idx: int, titles: list[str], contents: list[str]) -> float:
    """D2: 新颖性 — TF-IDF 余弦距离（批量预计算后按 idx 取值）。"""
    # 实际由 batch 函数填充，此处占位
    return 5.0


def calc_d2_novelty_batch(titles: list[str], contents: list[str]) -> list[float]:
    """批量计算 D2，返回 0-10 分列表。"""
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [(str(t) + " " + str(c))[:600] for t, c in zip(titles, contents)]
        vec = TfidfVectorizer(max_features=3000, sublinear_tf=True)
        tfidf = vec.fit_transform(corpus)
        sim_matrix = cosine_similarity(tfidf)

        scores = []
        n = len(corpus)
        for i in range(n):
            row = sim_matrix[i].copy()
            row[i] = 0
            max_sim = row.max() if n > 1 else 0.0
            # novelty = 1 - max_sim，映射到 0-10
            scores.append(round((1.0 - float(max_sim)) * 10, 2))
        return scores
    except ImportError:
        return [5.0] * len(titles)


def calc_d3_source_quality(source_tier: str, url: str, source_type: str) -> float:
    """D3: 信源质量 — tier × 域名权威 × 类型加成。"""
    tier_s = SOURCE_TIER_SCORE.get(str(source_tier).lower(), 0.4)
    domain = _get_domain(url)
    domain_s = DOMAIN_TRUST.get(domain, 0.52)

    # 官方产品账号额外加成
    official_bonus = 0.0
    official_domains = {"openai.com", "anthropic.com", "deepmind.com", "blog.google",
                        "ai.meta.com", "mistral.ai", "stability.ai", "huggingface.co"}
    if domain in official_domains:
        official_bonus = 0.15

    raw = tier_s * 0.5 + domain_s * 0.5 + official_bonus
    return round(min(raw * 10, 10.0), 2)


def calc_d4_timeliness(published_str: str, content_type: str) -> float:
    """D4: 时效性 — 指数衰减，λ 按内容类型差异化。设置下限避免让 B 归零。"""
    age_h = _parse_age_hours(published_str)
    lam = LAMBDA_MAP.get(content_type, 0.05)
    score = math.exp(-lam * age_h)
    # 下限：newsletter/academic 常青内容最低 0.5 分，其余最低 0.1 分
    floor = 0.5 if content_type in ("newsletter", "academic") else 0.1
    return round(max(score, floor / 10.0) * 10, 2)


def calc_d5_actionability(content: str, title: str, content_type: str) -> float:
    """D5: 可操作性 — 包含具体步骤、工具、API、代码等信号。"""
    text = str(title) + " " + str(content)
    tl = text.lower()

    signals = [
        bool(re.search(r"\b(how to|guide|tutorial|step[\s-]by|install|setup|deploy|implement|use|try|get started)\b", tl)),
        bool(re.search(r"\b(api|sdk|library|framework|open source|github|pip install|npm)\b", tl)),
        bool(re.search(r"\b(available|released|download|access|sign up|free|open)\b", tl)),
        bool(re.search(r"(```|code|示例|教程|怎么用|如何|接入|部署)", tl)),
        # 产品发布/可用性
        content_type in ("product_launch",),
    ]

    score = sum(signals) / len(signals)
    # newsletter 和 kol_tweet 基础可操作性略低
    if content_type in ("newsletter", "kol_tweet"):
        score *= 0.85
    return round(min(score * 10, 10.0), 2)


def calc_d6_title_consistency(title: str, content: str) -> float:
    """
    D6: 标题一致性 — 检测标题党。
    综合：标题关键词在正文中的覆盖率 + clickbait 模式惩罚。
    返回 0-10 分。
    """
    title_str = str(title).lower()
    content_str = str(content).lower()

    # 内容过短（<200字）说明是摘要截断，无法判断标题一致性 → 中性分
    if len(content_str.strip()) < 200:
        return 5.0

    # 提取标题关键词（去停用词），跳过纯emoji/符号标题
    stopwords = {"the", "a", "an", "is", "in", "of", "to", "and", "or", "for",
                 "on", "at", "by", "with", "this", "that", "are", "was", "it",
                 "be", "as", "from", "but", "not", "have", "why", "how", "what"}
    title_words = [w for w in re.findall(r"\b\w{3,}\b", title_str) if w not in stopwords]

    # 标题提取不到有效词（全是emoji/数字/符号）→ 中性分
    if len(title_words) < 2:
        return 5.0

    # 标题词在正文中出现的比例
    coverage = sum(1 for w in title_words if w in content_str) / len(title_words)

    # 聚合型标题（Newsletter/Podcast 期号）天然覆盖率低，给基础分 0.4
    is_digest = bool(re.search(
        r"#\d+|\bpodcast\b|\bepisode\b|\broundup\b|\bdigest\b|\bweekly\b|\bnewsletter\b"
        r"|\b\w[\w\s]{0,20}\d{2,4}[:\-–]",  # "Import AI 430:", "Last Week in AI #327"
        title_str, re.I
    ))
    if is_digest and coverage < 0.4:
        coverage = 0.4

    # clickbait 模式检测
    clickbait_hits = sum(1 for p in CLICKBAIT_PATTERNS if re.search(p, title_str, re.I))
    clickbait_penalty = min(clickbait_hits * 0.15, 0.45)

    # 情绪化词汇（D6 也受标题情绪影响）
    emotional_hits = sum(1 for w in EMOTIONAL_TRIGGERS if w in title_str)
    emotion_penalty = min(emotional_hits * 0.1, 0.3)

    raw = coverage - clickbait_penalty - emotion_penalty
    return round(max(min(raw * 10, 10.0), 0.0), 2)


def calc_d7_velocity_batch(titles: list[str], sources: list[str]) -> list[float]:
    """
    D7: 传播速度 — 跨源独立报道数（优先用 trending.db 真实时序）。
    返回 0-10 分列表，以及 z-score 用于 K 计算。
    """
    # 先尝试 trending.db
    try:
        from trending import get_velocity_scores, DB_PATH
        if DB_PATH.exists():
            raw_scores = get_velocity_scores(titles, sources)
            # 已经是 0-1，×10 映射到 0-10
            d7_scores = [round(s * 10, 2) for s in raw_scores]
            return d7_scores
    except Exception:
        pass

    # 降级：跨源独立报道数近似
    n = len(titles)
    doc_kws = []
    for title in titles:
        kws = set(re.findall(r"\b[a-z\u4e00-\u9fff]{3,}\b", str(title).lower())) & HIGH_VALUE_KW
        doc_kws.append(kws)

    scores = []
    for i in range(n):
        kws_i = doc_kws[i]
        if not kws_i:
            scores.append(1.0)
            continue
        src_i = sources[i] if i < len(sources) else ""
        seen_srcs: set[str] = set()
        for j in range(n):
            if i == j:
                continue
            src_j = sources[j] if j < len(sources) else ""
            if src_j == src_i or src_j in seen_srcs:
                continue
            if doc_kws[j] & kws_i:
                seen_srcs.add(src_j)
        scores.append(round(min(len(seen_srcs) / 3.0 * 10, 10.0), 2))
    return scores


def calc_d8_audience_match(title: str, content: str, user_interests: list[str]) -> float:
    """
    D8: 受众匹配度 — 内容与用户兴趣词的语义重叠。
    user_interests: 用户设定的话题词列表，如 ["ai", "openai", "llm"]
    无用户设定时返回中性分 5.0。
    """
    if not user_interests:
        return 5.0
    text = (str(title) + " " + str(content)).lower()
    hits = sum(1 for kw in user_interests if kw.lower() in text)
    score = min(hits / max(len(user_interests) * 0.3, 1), 1.0)
    return round(score * 10, 2)


def calc_d9_verification(content: str) -> float:
    """
    D9: 独立验证度 — 内容中有多少来自独立第二方来源的信号。
    打击"一手消息"谣言、未经核实的爆料，以及广告/赞助内容。
    """
    text = str(content).lower()

    # 广告/赞助内容直接返回极低分（触发 Veto）
    sponsor_hits = len(re.findall(
        r"\b(sponsor(ed)?|advertisement|advertorial|paid post|promoted|affiliate)"
        r"|赞助|广告\.?\.?\.?"
        r"|(click here|sign up now|free trial|limited time offer)",
        text, re.I
    ))
    if sponsor_hits >= 2:
        return 1.0  # 触发 Veto Gate

    # 正向信号：有引用来源
    positive = len(re.findall(
        r"(according to|confirmed by|verified|cited|source:|via |reported by|"
        r"独家|据.*?报道|证实|来源|引用|参考文献|\[[\d]+\])",
        text, re.I
    ))

    # 负向信号：未经核实的语言
    negative = len(re.findall(
        r"(rumor|allegedly|unconfirmed|sources say|i heard|breaking:|传言|据说|"
        r"消息人士|有消息称|匿名|据悉|疑似)",
        text, re.I
    ))

    raw = (min(positive, 3) - min(negative, 2)) / 3.0 + 0.5
    return round(max(min(raw * 10, 10.0), 0.0), 2)


def calc_d10_neutrality(title: str, content: str) -> float:
    """
    D10: 情绪中立度 — 语言是否客观，过滤情绪操控内容。
    这是最关键的反噪音维度之一。
    """
    text = (str(title) + " " + str(content)).lower()

    # 情绪化词汇命中
    emotional_hits = sum(1 for w in EMOTIONAL_TRIGGERS if w in text)
    # 全大写词（视觉冲击）
    caps_words = len(re.findall(r"\b[A-Z]{3,}\b", str(title) + " " + str(content)))
    # 多感叹号
    exclamation = len(re.findall(r"!{2,}", text))

    penalty = (
        min(emotional_hits * 0.15, 0.6)
        + min(caps_words * 0.05, 0.2)
        + min(exclamation * 0.1, 0.2)
    )
    raw = max(1.0 - penalty, 0.0)
    return round(raw * 10, 2)


# ─── Veto Gate ────────────────────────────────────────────────────────────────
def veto_gate(d1: float, d3: float, d6: float, d9: float, d10: float) -> tuple[bool, str]:
    """
    硬性否决：满足任一条件则直接归零，不进入后续计算。
    返回 (is_vetoed, reason)
    """
    if d6 < 2.0:
        return True, f"极端标题党 D6={d6:.1f}<2"
    if d10 < 2.0:
        return True, f"极端情绪化 D10={d10:.1f}<2"
    if d1 < 2.0 and d3 < 2.0:
        return True, f"无事实无信源 D1={d1:.1f}<2 且 D3={d3:.1f}<2"
    # 广告内容：D9 极低
    if d9 < 1.5:
        return True, f"广告/赞助内容 D9={d9:.1f}<1.5"
    return False, ""


# ─── 连续调节函数 ──────────────────────────────────────────────────────────────
def penalty_p(d6: float) -> float:
    """P(D6): 连续 Sigmoid 标题一致性调节，替代三级阶梯。"""
    return 0.25 + 0.75 / (1 + math.exp(-0.8 * (d6 - 5)))


def boost_k(d7_zscore: float) -> float:
    """K(D7): 连续 tanh 传播速度调节。"""
    return 1.0 + 0.3 * math.tanh(d7_zscore)


def calc_d7_zscore(d7_scores: list[float]) -> list[float]:
    """将 D7 分数转为 z-score 用于 K 计算。"""
    arr = np.array(d7_scores, dtype=float)
    mean, std = arr.mean(), arr.std()
    if std < 1e-9:
        return [0.0] * len(d7_scores)
    return ((arr - mean) / std).tolist()


# ─── 读者画像 ──────────────────────────────────────────────────────────────────
def reader_profile_r(d8: float) -> float:
    """R(u): 读者画像调节因子，基于 D8 映射到 [0.5, 1.5]。"""
    # D8=0 → R=0.5, D8=5 → R=1.0, D8=10 → R=1.5
    return round(0.5 + d8 / 10.0, 3)


# ─── 归一化到 100 ──────────────────────────────────────────────────────────────
def sigmoid_norm(x: float, scale: float = 10.0) -> float:
    """将 V_raw (0-10) 平滑映射到 0-100，避免线性截断。"""
    return round(100 / (1 + math.exp(-0.5 * (x - 5))), 1)


# ─── 主评分函数 ───────────────────────────────────────────────────────────────
def score_dataframe_v2(df: pd.DataFrame, user_interests: list[str] = None) -> pd.DataFrame:
    df = df.copy()
    user_interests = user_interests or []
    n = len(df)

    titles   = df["title"].fillna("").tolist()
    contents = df["content"].fillna("").tolist()
    sources  = df.get("source_name", pd.Series([""] * n)).fillna("").tolist()

    # 确定内容类型
    src_types = df.get("source_type", pd.Series([""] * n)).fillna("").tolist()
    content_types = [_get_content_type(st, t) for st, t in zip(src_types, titles)]
    df["content_type"] = content_types

    # ── 批量计算 D2, D7 ──
    print("计算 D2 新颖性（TF-IDF）...", flush=True)
    d2_scores = calc_d2_novelty_batch(titles, contents)

    print("计算 D7 传播速度 ...", flush=True)
    d7_scores = calc_d7_velocity_batch(titles, sources)
    d7_zscores = calc_d7_zscore(d7_scores)

    # ── 逐行计算其余维度 ──
    print("计算 D1/D3/D4/D5/D6/D8/D9/D10 ...", flush=True)

    records = []
    for i in range(n):
        row = df.iloc[i]
        ct = content_types[i]

        d1  = calc_d1_fact_density(contents[i], titles[i])
        d2  = d2_scores[i]
        d3  = calc_d3_source_quality(row.get("source_tier", ""), row.get("url", ""), src_types[i])
        d4  = calc_d4_timeliness(row.get("published_at", row.get("published", "")), ct)
        d5  = calc_d5_actionability(contents[i], titles[i], ct)
        d6  = calc_d6_title_consistency(titles[i], contents[i])
        d7  = d7_scores[i]
        d8  = calc_d8_audience_match(titles[i], contents[i], user_interests)
        d9  = calc_d9_verification(contents[i])
        d10 = calc_d10_neutrality(titles[i], contents[i])

        # Step 0: Veto Gate
        vetoed, veto_reason = veto_gate(d1, d3, d6, d9, d10)
        if vetoed:
            records.append({
                "d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5,
                "d6": d6, "d7": d7, "d8": d8, "d9": d9, "d10": d10,
                "veto": True, "veto_reason": veto_reason,
                "B": 0, "P": 0, "K": 0, "T": 0, "R": 0,
                "value_score": 0.0,
            })
            continue

        # Step 1: 加权基础分 B（D1-D5）
        weights = WEIGHT_MATRIX.get(ct, WEIGHT_MATRIX["breaking_news"])
        B = (weights[0]*d1 + weights[1]*d2 + weights[2]*d3
             + weights[3]*d4 + weights[4]*d5)

        # Step 2: 连续调节
        P = penalty_p(d6)
        K = boost_k(d7_zscores[i])

        # Step 3: 时序衰减已在 D4 中体现（避免双重衰减，这里不再额外乘 e^-λt）
        # 但传播速度和标题一致性通过乘法调节
        V_raw = B * P * K

        # Step 4: 读者画像调节
        R = reader_profile_r(d8)
        V_personalized = V_raw * R

        # Step 5: 归一化
        V_final = sigmoid_norm(V_personalized)

        records.append({
            "d1": d1, "d2": d2, "d3": d3, "d4": d4, "d5": d5,
            "d6": d6, "d7": d7, "d8": d8, "d9": d9, "d10": d10,
            "veto": False, "veto_reason": "",
            "B": round(B, 3), "P": round(P, 3), "K": round(K, 3),
            "T": round(d4 / 10, 3), "R": round(R, 3),
            "value_score": V_final,
        })

    result_df = pd.DataFrame(records)
    for col in result_df.columns:
        df[col] = result_df[col].values

    return df


# ─── 主函数 ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GISTER Content Value Scorer V2.0")
    parser.add_argument("--input",        default="ground_truth_samples.csv")
    parser.add_argument("--output",       default=None)
    parser.add_argument("--user-profile", default="", help="逗号分隔的用户兴趣词，如 ai,openai,llm")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 找不到文件: {input_path}")
        return

    output_path = Path(args.output) if args.output else \
        input_path.with_name(input_path.stem + "_v2scored.csv")

    user_interests = [w.strip() for w in args.user_profile.split(",") if w.strip()]

    print(f"读取: {input_path}  ({len(pd.read_csv(input_path))} 行)")
    if user_interests:
        print(f"读者画像: {user_interests}")
    df = pd.read_csv(input_path)

    df = score_dataframe_v2(df, user_interests)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 已写入: {output_path}")

    # ── 统计报告 ──
    vetoed = df[df["veto"] == True]
    passed = df[df["veto"] == False]

    print(f"\n🚫 Veto Gate 归零: {len(vetoed)} 篇 ({len(vetoed)/len(df)*100:.1f}%)")
    if len(vetoed) > 0:
        reasons = vetoed["veto_reason"].value_counts()
        for reason, cnt in reasons.items():
            print(f"   {cnt}篇 → {reason}")

    print(f"\n📊 通过内容 value_score 分布 (n={len(passed)}):")
    print(passed["value_score"].describe().round(1).to_string())

    print("\n🏆 Top 10 高分文章:")
    cols = ["title", "source_name", "content_type", "value_score", "d1", "d3", "d6", "d10"]
    for _, row in df.nlargest(10, "value_score")[cols].iterrows():
        print(f"  [{row['value_score']:5.1f}] [{row['content_type'][:8]}] "
              f"{str(row['title'])[:55]}  ({row['source_name']})")

    print("\n📉 Bottom 10（未被 Veto 的最低分）:")
    bottom = passed.nsmallest(10, "value_score")[cols]
    for _, row in bottom.iterrows():
        print(f"  [{row['value_score']:5.1f}] [{row['content_type'][:8]}] "
              f"{str(row['title'])[:55]}  ({row['source_name']})")

    print("\n📈 各内容类型平均分:")
    print(df.groupby("content_type")["value_score"].agg(["mean", "min", "max", "count"])
          .round(1).to_string())

    # 如果有 label 列，计算相关性
    if "label" in df.columns:
        labeled = df[df["label"].notna() & (df["label"] != "")]
        if len(labeled) > 10:
            try:
                from scipy.stats import pointbiserialr
                labels = labeled["label"].astype(int)
                corr, pval = pointbiserialr(labels, labeled["value_score"])
                print(f"\n📈 与人工标注相关性: r={corr:.3f}, p={pval:.4f} (n={len(labeled)})")
            except Exception:
                pass


if __name__ == "__main__":
    main()
