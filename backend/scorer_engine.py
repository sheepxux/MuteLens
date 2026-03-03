"""
ArticleRadar - Scoring Engine
================================
基于 GISTER scorer_v2.py 改造，适配单篇文章实时评分。
10 个维度 + Veto Gate + 连续 Sigmoid 调节 + 归一化到 0-100。

完整公式：
  Step 0: Veto Gate    → 极端噪音直接归零
  Step 1: B = Σ(wᵢ·Dᵢ)  → 加权基础分（D1-D5，按内容类型动态权重）
  Step 2: P = sigmoid 连续标题一致性调节
          K = 传播速度调节（单篇模式下使用域名权威替代）
  Step 3: V_raw = B × P × K
  Step 4: V_final = sigmoid_norm × 100 → 归一化到 0-100
"""

import math
import re
from dataclasses import dataclass


# ─── 内容类型识别 ──────────────────────────────────────────────────────────────
CONTENT_TYPE_MAP = {
    "research":          "academic",
    "social_twitter":    "kol_tweet",
    "social_reddit":     "kol_tweet",
    "newsletter":        "newsletter",
    "tech_news":         "tech_article",
    "business":          "tech_article",
    "government_policy": "tech_article",
    "medium":            "newsletter",
}

# ─── 权重矩阵（6种内容类型 × 5个基础维度 D1-D5）─────────────────────────────
WEIGHT_MATRIX = {
    "breaking_news":  [0.18, 0.20, 0.22, 0.28, 0.12],
    "tech_article":   [0.22, 0.22, 0.22, 0.18, 0.16],
    "academic":       [0.35, 0.27, 0.27, 0.05, 0.06],
    "kol_tweet":      [0.18, 0.27, 0.22, 0.12, 0.21],
    "product_launch": [0.22, 0.15, 0.18, 0.15, 0.30],
    "newsletter":     [0.25, 0.19, 0.19, 0.11, 0.26],
}

# ─── 域名权威分 ───────────────────────────────────────────────────────────────
DOMAIN_TRUST: dict[str, float] = {
    "openai.com": 1.0, "anthropic.com": 1.0, "deepmind.com": 1.0,
    "blog.google": 1.0, "ai.meta.com": 1.0, "huggingface.co": 0.95,
    "mistral.ai": 0.95, "stability.ai": 0.9,
    "arxiv.org": 0.98, "nature.com": 1.0, "science.org": 1.0,
    "proceedings.neurips.cc": 0.98, "icml.cc": 0.95,
    "technologyreview.com": 0.92, "wired.com": 0.85, "arstechnica.com": 0.85,
    "bloomberg.com": 0.88, "economist.com": 0.88, "ft.com": 0.85,
    "techcrunch.com": 0.75, "theverge.com": 0.75, "scmp.com": 0.75,
    "restofworld.org": 0.85,
    "newsletter.pragmaticengineer.com": 0.95, "ben-evans.com": 0.92,
    "interconnects.ai": 0.88, "notboring.co": 0.82,
    "exponentialview.co": 0.88, "lastweekin.ai": 0.85,
    "sebastianraschka.com": 0.88, "importai.substack.com": 0.88,
    "tldr.tech": 0.78,
    "36kr.com": 0.72, "infoq.cn": 0.72, "sspai.com": 0.72,
    "ifanr.com": 0.68, "jiqizhixin.com": 0.82,
    "nitter.net": 0.62, "reddit.com": 0.58, "medium.com": 0.52,
    "substack.com": 0.62, "twitter.com": 0.62, "x.com": 0.62,
}

SOURCE_TIER_SCORE = {"high": 1.0, "medium": 0.65, "low": 0.25}

# ─── 高价值关键词 ──────────────────────────────────────────────────────────────
HIGH_VALUE_KW: set[str] = {
    "ai", "llm", "gpt", "claude", "gemini", "openai", "deepmind", "anthropic",
    "agent", "model", "benchmark", "dataset", "research", "paper",
    "launch", "release", "funding", "acquisition", "regulation", "policy",
    "neural", "transformer", "diffusion", "robotics", "chip", "semiconductor",
    "open source", "autonomous", "startup", "breach", "quantum",
    "人工智能", "大模型", "智能体", "发布", "研究", "政策", "监管",
    "融资", "收购", "开源", "芯片", "突破", "算法", "数据", "安全",
}

EMOTIONAL_TRIGGERS: set[str] = {
    "shocking", "unbelievable", "insane", "destroyed", "explodes", "outrage",
    "terrifying", "disgusting", "evil", "stupid", "idiot", "moron",
    "!!!", "🔥🔥🔥", "must see", "you won't believe", "wake up",
    "暴跌", "崩盘", "末日", "完蛋", "震惊", "怒了", "炸了", "傻逼",
}

CLICKBAIT_PATTERNS = [
    r"\?$",
    r"^\d+\s+(ways|things|reasons)",
    r"why .+ will .+ you",
    r"(secret|trick|hack) that",
    r"you (won't|need to|must)",
]


@dataclass
class DimensionScore:
    key: str
    label: str
    label_en: str
    score: float  # 0-10
    max_score: float  # 10
    description: str


@dataclass
class ScoringResult:
    overall_score: float  # 0-100
    grade: str
    vetoed: bool
    veto_reason: str
    content_type: str
    content_type_label: str
    dimensions: list[DimensionScore]
    intermediate: dict[str, float]
    analysis_summary: str


# ─── 维度计算 ────────────────────────────────────────────────────────────────

def calc_d1_fact_density(content: str, title: str) -> tuple[float, str]:
    """D1: 事实密度 — 数据、引用、可验证声明的密度。"""
    text = str(title) + " " + str(content)
    word_count = max(len(text.split()), 1)

    numbers = len(re.findall(
        r"\b\d+\.?\d*\s*(%|million|billion|trillion|thousand|[kmb])\b"
        r"|\$[\d,]+|\d{4}年|\d+亿|\d+万|\d+倍"
        r"|\b\d+\s*(times|x\b|fold|percent)"
        r"|\b(zero|one|two|three|four|five|six|seven|eight|nine|ten)\s+\w+",
        text, re.I,
    ))
    citations = len(re.findall(
        r"\b(according to|cited by|study (shows|finds|found)|research(ers)? (found|show|suggest)|"
        r"report(s|ed)?|survey|data (show|suggest)|evidence|experiment|"
        r"announced|confirmed|stated|told|wrote|published|"
        r"源自|据.*?(?:报道|称|表示|指出)|报告|研究(?:表明|发现|显示)|"
        r"实验|数据|证实|引用|参考文献|\[[\d]+\]|et al\.)",
        text, re.I,
    ))
    kw_hits = sum(1 for kw in HIGH_VALUE_KW if kw in text.lower())

    # Normalize by article length so short articles aren't unfairly penalized
    density_factor = min(word_count / 400.0, 1.0)

    score = (
        min(numbers / 4.0, 1.0) * 0.35
        + min(citations / 4.0, 1.0) * 0.40
        + min(kw_hits / 5.0, 1.0) * 0.25
    ) * (0.7 + 0.3 * density_factor)

    final = round(min(score * 10, 10.0), 2)

    detail_parts = []
    if numbers > 0:
        detail_parts.append(f"检测到 {numbers} 个数据/统计引用")
    if citations > 0:
        detail_parts.append(f"检测到 {citations} 个来源引用信号")
    if kw_hits > 0:
        detail_parts.append(f"命中 {kw_hits} 个高价值关键词")
    if not detail_parts:
        detail_parts.append("未检测到显著事实数据或引用")

    return final, "；".join(detail_parts)


def calc_d2_novelty(content: str, title: str) -> tuple[float, str]:
    """D2: 内容新颖性 — 单篇模式下基于内容丰富度和独特性信号估算。"""
    text = (str(title) + " " + str(content)).lower()
    words = text.split()
    unique_words = set(words)
    word_count = max(len(words), 1)

    # 词汇丰富度 — longer texts naturally have lower diversity, normalize
    raw_diversity = len(unique_words) / word_count
    # Scale: short text inflates diversity, penalize; normalize toward 0.5 target
    lexical_diversity = min(raw_diversity * (1.0 + min(word_count / 500.0, 1.0)), 1.0)

    # 专业术语密度 — broader coverage
    tech_terms = len(re.findall(
        r"\b(algorithm|architect|framework|infrastructure|protocol|"
        r"benchmark|latency|throughput|scalab|fine-tun|pretrain|"
        r"inference|embedding|tokeniz|attention|parameter|gradient|"
        r"multimodal|autonomous|reinforcement|transformer|diffusion|"
        r"neural|quantiz|distill|pruning|lora|rlhf|sft|"
        r"api|sdk|model|dataset|evaluation|ablation|baseline|"
        r"算法|架构|框架|协议|延迟|吞吐|推理|嵌入|参数|梯度|"
        r"多模态|强化学习|微调|量化|蒸馏|注意力|基准)\b",
        text, re.I,
    ))

    # 原创观点 / 分析性表达
    opinion_signals = len(re.findall(
        r"\b(i think|i believe|in my opinion|our analysis|we found|"
        r"we propose|our approach|novel|new method|first time|"
        r"this suggests|this indicates|it appears|notably|importantly|"
        r"interestingly|surprisingly|significantly|crucially|"
        r"我认为|我们发现|我们提出|首次|创新|新方法|值得注意|重要的是)\b",
        text, re.I,
    ))

    # Product / announcement novelty bonus (new things are inherently novel)
    novelty_signals = len(re.findall(
        r"\b(first|new|novel|breakthrough|introducing|launch|release|"
        r"unveil|announce|debut|pioneer|revolutioniz|"
        r"首次|首发|全新|突破|发布|推出|开创)\b",
        text, re.I,
    ))

    score = (
        min(lexical_diversity, 1.0) * 0.25
        + min(tech_terms / 6.0, 1.0) * 0.35
        + min(opinion_signals / 3.0, 1.0) * 0.25
        + min(novelty_signals / 3.0, 1.0) * 0.15
    )
    final = round(min(score * 10, 10.0), 2)

    details = [f"词汇丰富度 {raw_diversity:.0%}"]
    if tech_terms > 0:
        details.append(f"{tech_terms} 个专业术语")
    if opinion_signals > 0:
        details.append(f"{opinion_signals} 个原创观点信号")
    if novelty_signals > 0:
        details.append(f"{novelty_signals} 个新颖性信号")
    if final < 3:
        details.append("内容缺乏独特视角")

    return final, "；".join(details)


def calc_d3_source_quality(source_tier: str, domain: str, source_type: str) -> tuple[float, str]:
    """D3: 信源质量 — tier × 域名权威 × 类型加成。"""
    tier_s = SOURCE_TIER_SCORE.get(str(source_tier).lower(), 0.4)
    domain_s = DOMAIN_TRUST.get(domain, 0.52)

    official_bonus = 0.0
    official_domains = {
        "openai.com", "anthropic.com", "deepmind.com", "blog.google",
        "ai.meta.com", "mistral.ai", "stability.ai", "huggingface.co",
    }
    if domain in official_domains:
        official_bonus = 0.15

    raw = tier_s * 0.5 + domain_s * 0.5 + official_bonus
    final = round(min(raw * 10, 10.0), 2)

    tier_label = {"high": "高", "medium": "中", "low": "低"}.get(source_tier, "中")
    desc = f"域名 {domain} 信任分 {domain_s:.2f}，来源层级「{tier_label}」"
    if official_bonus > 0:
        desc += "，官方产品博客加成"

    return final, desc


def calc_d4_timeliness(published_str: str, content_type: str) -> tuple[float, str]:
    """D4: 时效性 — 基于发布时间的指数衰减。"""
    from datetime import datetime, timezone
    from email.utils import parsedate_to_datetime

    LAMBDA_MAP = {
        "breaking_news":  0.08,
        "tech_article":   0.015,
        "kol_tweet":      0.05,
        "product_launch": 0.02,
        "academic":       0.003,
        "newsletter":     0.01,
    }

    # Default age when no date — assume recent for evergreen types
    DEFAULT_AGE_MAP = {
        "breaking_news":  48.0,
        "tech_article":   72.0,
        "kol_tweet":      24.0,
        "product_launch": 72.0,
        "academic":       720.0,
        "newsletter":     120.0,
    }
    age_h = DEFAULT_AGE_MAP.get(content_type, 72.0)
    if published_str and str(published_str).strip():
        try:
            ts = None
            for fmt in [
                "%a, %d %b %Y %H:%M:%S %z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f%z",
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
            age_h = max((now - ts).total_seconds() / 3600, 0.0)
        except Exception:
            age_h = DEFAULT_AGE_MAP.get(content_type, 72.0)

    lam = LAMBDA_MAP.get(content_type, 0.015)
    score_raw = math.exp(-lam * age_h)
    floor = 0.5 if content_type in ("newsletter", "academic", "tech_article") else 0.1
    final = round(max(score_raw, floor / 10.0) * 10, 2)

    if age_h < 1:
        desc = "刚刚发布（< 1小时），时效性极高"
    elif age_h < 24:
        desc = f"发布于 {age_h:.0f} 小时前，时效性良好"
    elif age_h < 72:
        desc = f"发布于 {age_h / 24:.1f} 天前，时效性中等"
    else:
        desc = f"发布于 {age_h / 24:.0f} 天前，时效性较低"

    if not published_str or not str(published_str).strip():
        desc = "未检测到发布时间，按默认 48h 计算"

    return final, desc


def calc_d5_actionability(content: str, title: str, content_type: str) -> tuple[float, str]:
    """D5: 可操作性 — 包含具体步骤、工具、API、代码等信号。"""
    text = str(title) + " " + str(content)
    tl = text.lower()

    signals = {
        "教程/指南": bool(re.search(
            r"\b(how to|guide|tutorial|step[\s-]by|install|setup|deploy|implement|use|try|get started)\b", tl,
        )),
        "技术工具": bool(re.search(
            r"\b(api|sdk|library|framework|open source|github|pip install|npm)\b", tl,
        )),
        "可用性": bool(re.search(
            r"\b(available|released|download|access|sign up|free|open)\b", tl,
        )),
        "代码/示例": bool(re.search(r"(```|code|示例|教程|怎么用|如何|接入|部署)", tl)),
        "产品发布": content_type in ("product_launch",),
    }

    hit_count = sum(signals.values())
    score = hit_count / len(signals)
    if content_type in ("newsletter", "kol_tweet"):
        score *= 0.85
    final = round(min(score * 10, 10.0), 2)

    matched = [k for k, v in signals.items() if v]
    desc = f"命中信号: {', '.join(matched)}" if matched else "未检测到可操作性信号"

    return final, desc


def calc_d6_title_consistency(title: str, content: str) -> tuple[float, str]:
    """D6: 标题一致性 — 检测标题党。"""
    title_str = str(title).lower()
    content_str = str(content).lower()

    if len(content_str.strip()) < 200:
        return 6.0, "正文过短，按默认中等评分"

    stopwords = {
        "the", "a", "an", "is", "in", "of", "to", "and", "or", "for",
        "on", "at", "by", "with", "this", "that", "are", "was", "it",
        "be", "as", "from", "but", "not", "have", "why", "how", "what",
        "its", "has", "are", "our", "their", "his", "her", "new", "get",
    }
    title_words = [w for w in re.findall(r"\b\w{3,}\b", title_str) if w not in stopwords]

    if len(title_words) < 2:
        return 6.0, "标题关键词过少，按默认中等评分"

    # Stem-lite: also check first 5 chars prefix match (catches plurals, verb forms)
    def _word_in_content(word: str, text: str) -> bool:
        if word in text:
            return True
        # prefix match for root similarity (e.g. "reshape" matches "reshaping")
        prefix = word[:5]
        if len(prefix) >= 4 and prefix in text:
            return True
        return False

    matched = sum(1 for w in title_words if _word_in_content(w, content_str))
    coverage = matched / len(title_words)

    is_digest = bool(re.search(
        r"#\d+|\bpodcast\b|\bepisode\b|\broundup\b|\bdigest\b|\bweekly\b|\bnewsletter\b"
        r"|\b\w[\w\s]{0,20}\d{2,4}[:\-–]",
        title_str, re.I,
    ))
    if is_digest and coverage < 0.4:
        coverage = 0.4

    clickbait_hits = sum(1 for p in CLICKBAIT_PATTERNS if re.search(p, title_str, re.I))
    clickbait_penalty = min(clickbait_hits * 0.15, 0.40)

    emotional_hits = sum(1 for w in EMOTIONAL_TRIGGERS if w in title_str)
    emotion_penalty = min(emotional_hits * 0.10, 0.25)

    # Base: coverage maps to 0-10, then apply penalties
    # Use a softer scale: 0% coverage → 3.0, 100% → 10.0
    base = 3.0 + coverage * 7.0
    raw = (base - clickbait_penalty * 10 - emotion_penalty * 10) / 10.0
    final = round(max(min(raw * 10, 10.0), 0.0), 2)

    details = [f"标题词正文覆盖率 {coverage:.0%}（{matched}/{len(title_words)} 词命中）"]
    if clickbait_hits > 0:
        details.append(f"检测到 {clickbait_hits} 个标题党模式")
    if emotional_hits > 0:
        details.append(f"检测到 {emotional_hits} 个情绪化词汇")

    return final, "；".join(details)


def calc_d7_reach_potential(domain: str, content: str, title: str) -> tuple[float, str]:
    """D7: 传播潜力 — 单篇模式下基于域名权威 + 内容可分享性估算。"""
    domain_score = DOMAIN_TRUST.get(domain, 0.52)

    text = (str(title) + " " + str(content)).lower()
    share_signals = len(re.findall(
        r"\b(breaking|exclusive|first|new|major|significant|important|"
        r"突破|首次|重大|独家|最新|重磅)\b",
        text, re.I,
    ))

    has_data = bool(re.search(r"\d+%|\$\d+|\d+亿|\d+万", text))
    has_quote = bool(re.search(r'("|said|announced|表示|称)', text, re.I))

    score = (
        domain_score * 0.50
        + min(share_signals / 4.0, 1.0) * 0.25
        + (0.15 if has_data else 0)
        + (0.10 if has_quote else 0)
    )
    final = round(min(score * 10, 10.0), 2)

    details = [f"域名权威 {domain_score:.2f}"]
    if share_signals > 0:
        details.append(f"{share_signals} 个传播信号词")
    if has_data:
        details.append("包含数据支撑")
    if has_quote:
        details.append("包含引用/声明")

    return final, "；".join(details)


def calc_d8_depth(content: str, title: str) -> tuple[float, str]:
    """D8: 内容深度 — 替代受众匹配，衡量文章分析深度。"""
    text = str(content)
    word_count = len(text.split())

    # 段落结构 — trafilatura 输出是空格分隔的连续文本，用句号+空格分割
    # 同时保留传统 \n 换行段落（bs4 路径）
    sentences = re.split(r'(?<=[.!?。！？])\s+', text)
    # 每段约 40+ 词算一个完整段落
    long_sentences = [s for s in sentences if len(s.split()) >= 40]
    para_count = max(len(long_sentences), len([p for p in text.split("\n") if len(p.strip()) > 50]))

    # 因果/分析性语言
    analysis_signals = len(re.findall(
        r"\b(because|therefore|however|although|moreover|furthermore|"
        r"as a result|in contrast|on the other hand|this means|that means|"
        r"which means|this suggests|this indicates|this demonstrates|"
        r"implies|suggests|indicates|demonstrates|consequently|"
        r"because of|due to|given that|despite|even though|"
        r"因为|因此|然而|尽管|此外|不过|但是|结果|这意味着|表明|说明|"
        r"由于|尽管如此|值得注意|需要指出)\b",
        text, re.I,
    ))

    # 结构化内容（列表、编号、标题等）— 同时匹配换行和空格分隔
    structure_signals = len(re.findall(
        r"(\n#{1,3}\s|\n\d+\.|\s\d+\.\s[A-Z]|•|►|▸|■|[\u25CF\u2022\u2023]"
        r"|\bfirst(ly)?,\s|\bsecond(ly)?,\s|\bthird(ly)?,\s"
        r"|\bone,\s|\btwo,\s|\bthree,\s"
        r"|首先[，,]|其次[，,]|最后[，,]|第一[，,、]|第二[，,、])",
        text, re.I,
    ))

    # Sub-heading signals (lines that look like section titles)
    subheading_signals = len(re.findall(
        r"(^|\n)[A-Z][^\n.!?]{5,60}(\n|$)",
        text,
    ))

    length_score = min(word_count / 1200.0, 1.0)
    analysis_score = min(analysis_signals / 6.0, 1.0)
    structure_score = min((structure_signals + subheading_signals) / 5.0, 1.0)
    para_score = min(para_count / 8.0, 1.0)

    score = (
        length_score * 0.30
        + analysis_score * 0.35
        + structure_score * 0.15
        + para_score * 0.20
    )
    final = round(min(score * 10, 10.0), 2)

    details = [f"全文约 {word_count} 词"]
    if analysis_signals > 0:
        details.append(f"{analysis_signals} 个分析性语言信号")
    if structure_signals + subheading_signals > 0:
        details.append(f"检测到 {structure_signals + subheading_signals} 个结构化元素")
    if para_count > 0:
        details.append(f"约 {para_count} 个内容段落")
    if final < 3:
        details.append("内容较浅，缺乏深度分析")

    return final, "；".join(details)


def calc_d9_verification(content: str) -> tuple[float, str]:
    """D9: 独立验证度 — 检测引用来源和广告内容。"""
    text = str(content).lower()

    sponsor_hits = len(re.findall(
        r"\b(sponsor(ed)?|advertisement|advertorial|paid post|promoted|affiliate)"
        r"|赞助|广告\.?\.?\.?"
        r"|(click here|sign up now|free trial|limited time offer)",
        text, re.I,
    ))
    if sponsor_hits >= 2:
        return 1.0, f"检测到 {sponsor_hits} 个广告/赞助信号，内容可信度极低"

    positive = len(re.findall(
        r"(according to|confirmed by|verified|cited|source:|via |reported by|"
        r"独家|据.*?报道|证实|来源|引用|参考文献|\[[\d]+\])",
        text, re.I,
    ))

    negative = len(re.findall(
        r"(rumor|allegedly|unconfirmed|sources say|i heard|breaking:|传言|据说|"
        r"消息人士|有消息称|匿名|据悉|疑似)",
        text, re.I,
    ))

    raw = (min(positive, 3) - min(negative, 2)) / 3.0 + 0.5
    final = round(max(min(raw * 10, 10.0), 0.0), 2)

    details = []
    if positive > 0:
        details.append(f"{positive} 个可验证来源引用")
    if negative > 0:
        details.append(f"{negative} 个未经核实信号")
    if sponsor_hits > 0:
        details.append(f"{sponsor_hits} 个广告/赞助痕迹")
    if not details:
        details.append("信源验证信号中等")

    return final, "；".join(details)


def calc_d10_neutrality(title: str, content: str) -> tuple[float, str]:
    """D10: 情绪中立度 — 语言是否客观。"""
    text = (str(title) + " " + str(content)).lower()

    emotional_hits = sum(1 for w in EMOTIONAL_TRIGGERS if w in text)
    caps_words = len(re.findall(r"\b[A-Z]{3,}\b", str(title) + " " + str(content)))
    exclamation = len(re.findall(r"!{2,}", text))

    penalty = (
        min(emotional_hits * 0.15, 0.6)
        + min(caps_words * 0.05, 0.2)
        + min(exclamation * 0.1, 0.2)
    )
    raw = max(1.0 - penalty, 0.0)
    final = round(raw * 10, 2)

    details = []
    if emotional_hits > 0:
        details.append(f"{emotional_hits} 个情绪化词汇")
    if caps_words > 0:
        details.append(f"{caps_words} 个全大写词")
    if exclamation > 0:
        details.append(f"{exclamation} 个多感叹号")
    if not details:
        details.append("语言客观中立")

    return final, "；".join(details)


# ─── Veto Gate ────────────────────────────────────────────────────────────────

def veto_gate(d1: float, d3: float, d6: float, d9: float, d10: float) -> tuple[bool, str]:
    if d6 < 1.5:
        return True, f"极端标题党 (D6={d6:.1f}<1.5)"
    if d10 < 1.5:
        return True, f"极端情绪化 (D10={d10:.1f}<1.5)"
    if d1 < 1.5 and d3 < 2.0:
        return True, f"无事实无信源 (D1={d1:.1f}<1.5 且 D3={d3:.1f}<2)"
    if d9 < 1.5:
        return True, f"广告/赞助内容 (D9={d9:.1f}<1.5)"
    return False, ""


# ─── 连续调节函数 ──────────────────────────────────────────────────────────────

def penalty_p(d6: float) -> float:
    """P(D6): 连续 Sigmoid 标题一致性调节。"""
    return 0.25 + 0.75 / (1 + math.exp(-0.8 * (d6 - 5)))


def boost_k(d7: float) -> float:
    """K(D7): 传播潜力调节，单篇模式用 tanh 平滑。"""
    z = (d7 - 5.0) / 3.0
    return 1.0 + 0.3 * math.tanh(z)


def sigmoid_norm(x: float) -> float:
    """将 V_raw 平滑映射到 0-100。"""
    return round(100 / (1 + math.exp(-0.5 * (x - 5))), 1)


def _get_grade(score: float) -> str:
    if score >= 90:
        return "A+"
    elif score >= 85:
        return "A"
    elif score >= 80:
        return "A-"
    elif score >= 75:
        return "B+"
    elif score >= 70:
        return "B"
    elif score >= 65:
        return "B-"
    elif score >= 60:
        return "C+"
    elif score >= 55:
        return "C"
    elif score >= 50:
        return "C-"
    elif score >= 40:
        return "D"
    else:
        return "F"


CONTENT_TYPE_LABELS = {
    "breaking_news":  "突发新闻",
    "tech_article":   "深度科技",
    "academic":       "学术研究",
    "kol_tweet":      "KOL 动态",
    "product_launch": "产品发布",
    "newsletter":     "Newsletter",
}

# ─── 域名 → 内容类型直接映射（高优先级） ─────────────────────────────────────
DOMAIN_CONTENT_TYPE: dict[str, str] = {
    "arxiv.org": "academic",
    "nature.com": "academic",
    "science.org": "academic",
    "proceedings.neurips.cc": "academic",
    "icml.cc": "academic",
    "scholar.google.com": "academic",
    "ieee.org": "academic",
    "anthropic.com": "product_launch",
    "openai.com": "product_launch",
    "deepmind.google": "product_launch",
    "deepmind.com": "product_launch",
    "mistral.ai": "product_launch",
    "huggingface.co": "tech_article",
    "blog.google": "product_launch",
    "ai.meta.com": "product_launch",
    "technologyreview.com": "tech_article",
    "wired.com": "tech_article",
    "arstechnica.com": "tech_article",
    "theverge.com": "tech_article",
    "restofworld.org": "tech_article",
    "techcrunch.com": "tech_article",
    "ben-evans.com": "newsletter",
    "interconnects.ai": "newsletter",
    "sebastianraschka.com": "newsletter",
    "importai.substack.com": "newsletter",
    "exponentialview.co": "newsletter",
    "notboring.co": "newsletter",
    "tldr.tech": "newsletter",
    "newsletter.pragmaticengineer.com": "newsletter",
    "reddit.com": "kol_tweet",
    "news.ycombinator.com": "kol_tweet",
    "twitter.com": "kol_tweet",
    "x.com": "kol_tweet",
}

# ─── 标题 / 内容关键词 → 内容类型信号 ───────────────────────────────────────
_ACADEMIC_RE = re.compile(
    r"\b(abstract|arxiv|preprint|paper|journal|conference|proceedings|"
    r"doi:|dataset|benchmark|experiment|baseline|sota|state.of.the.art|"
    r"摘要|论文|期刊|会议|实验|基准|数据集)\b",
    re.I,
)
_PRODUCT_RE = re.compile(
    r"\b(launch(es|ed|ing)?|release[sd]?|announc(e[sd]?|ing)|"
    r"introduc(e[sd]?|ing)|now available|api access|sign up|"
    r"发布|上线|推出|宣布|开放|测试版|正式版)\b",
    re.I,
)
_BREAKING_RE = re.compile(
    r"\b(breaking|just in|developing|urgent|alert|breaking news|"
    r"突发|快讯|紧急|最新消息|刚刚)\b",
    re.I,
)
_NEWSLETTER_RE = re.compile(
    r"\b(weekly|digest|roundup|newsletter|edition|issue #?\d+|"
    r"周报|月报|简报|精选|汇总)\b",
    re.I,
)


def _get_content_type(source_type: str, title: str, content: str = "", domain: str = "") -> str:
    tl = str(title).lower()
    cl = str(content[:500]).lower()
    combined = tl + " " + cl

    # 1. Domain override (highest priority)
    if domain and domain in DOMAIN_CONTENT_TYPE:
        ct = DOMAIN_CONTENT_TYPE[domain]
        # Even domain-level override can be bumped to product_launch by strong title signal
        if ct in ("tech_article", "newsletter") and _PRODUCT_RE.search(tl):
            return "product_launch"
        return ct

    # 2. Base from source_type
    ct = CONTENT_TYPE_MAP.get(str(source_type).lower(), "tech_article")

    # 3. Content/title signal refinement
    if _BREAKING_RE.search(tl):
        return "breaking_news"
    if _ACADEMIC_RE.search(combined):
        return "academic"
    if _NEWSLETTER_RE.search(tl):
        return "newsletter"
    if _PRODUCT_RE.search(tl):
        return "product_launch"

    # 4. Word-count heuristic: long articles are rarely breaking news
    word_count = len(str(content).split())
    if ct == "breaking_news" and word_count > 600:
        ct = "tech_article"

    return ct


def _generate_summary(
    score: float,
    grade: str,
    vetoed: bool,
    veto_reason: str,
    dims: list[DimensionScore],
    content_type: str,
) -> str:
    if vetoed:
        return f"[VETO] 该文章被 Veto Gate 否决：{veto_reason}。内容存在严重质量问题，不建议阅读或转发。"

    strengths = sorted(
        [d for d in dims if d.score >= 7.0],
        key=lambda x: x.score,
        reverse=True,
    )[:3]
    weaknesses = sorted(
        [d for d in dims if d.score < 4.0],
        key=lambda x: x.score,
    )[:3]

    parts = []
    if score >= 75:
        parts.append(f"综合评级 {grade}（{score:.1f}/100），这是一篇高质量文章。")
    elif score >= 55:
        parts.append(f"综合评级 {grade}（{score:.1f}/100），文章质量中等。")
    else:
        parts.append(f"综合评级 {grade}（{score:.1f}/100），文章质量偏低。")

    ct_label = CONTENT_TYPE_LABELS.get(content_type, content_type)
    parts.append(f"内容类型识别为「{ct_label}」。")

    if strengths:
        s_list = "、".join([f"{d.label}({d.score:.1f})" for d in strengths])
        parts.append(f"优势维度：{s_list}。")

    if weaknesses:
        w_list = "、".join([f"{d.label}({d.score:.1f})" for d in weaknesses])
        parts.append(f"薄弱维度：{w_list}。")

    return " ".join(parts)


# ─── 主评分入口 ───────────────────────────────────────────────────────────────

def score_article(
    title: str,
    content: str,
    domain: str,
    published: str,
    source_type: str,
    source_tier: str,
) -> ScoringResult:
    """对单篇文章进行多维度评分，返回完整评分结果。"""
    content_type = _get_content_type(source_type, title, content, domain)

    # 计算 10 个维度
    d1, d1_desc = calc_d1_fact_density(content, title)
    d2, d2_desc = calc_d2_novelty(content, title)
    d3, d3_desc = calc_d3_source_quality(source_tier, domain, source_type)
    d4, d4_desc = calc_d4_timeliness(published, content_type)
    d5, d5_desc = calc_d5_actionability(content, title, content_type)
    d6, d6_desc = calc_d6_title_consistency(title, content)
    d7, d7_desc = calc_d7_reach_potential(domain, content, title)
    d8, d8_desc = calc_d8_depth(content, title)
    d9, d9_desc = calc_d9_verification(content)
    d10, d10_desc = calc_d10_neutrality(title, content)

    dimensions = [
        DimensionScore("d1", "事实密度", "Fact Density", d1, 10, d1_desc),
        DimensionScore("d2", "内容新颖性", "Novelty", d2, 10, d2_desc),
        DimensionScore("d3", "信源质量", "Source Quality", d3, 10, d3_desc),
        DimensionScore("d4", "时效性", "Timeliness", d4, 10, d4_desc),
        DimensionScore("d5", "可操作性", "Actionability", d5, 10, d5_desc),
        DimensionScore("d6", "标题一致性", "Title Consistency", d6, 10, d6_desc),
        DimensionScore("d7", "传播潜力", "Reach Potential", d7, 10, d7_desc),
        DimensionScore("d8", "内容深度", "Content Depth", d8, 10, d8_desc),
        DimensionScore("d9", "可验证度", "Verification", d9, 10, d9_desc),
        DimensionScore("d10", "情绪中立度", "Neutrality", d10, 10, d10_desc),
    ]

    # Veto Gate
    vetoed, veto_reason = veto_gate(d1, d3, d6, d9, d10)
    if vetoed:
        result = ScoringResult(
            overall_score=0.0,
            grade="F",
            vetoed=True,
            veto_reason=veto_reason,
            content_type=content_type,
            content_type_label=CONTENT_TYPE_LABELS.get(content_type, content_type),
            dimensions=dimensions,
            intermediate={"B": 0, "P": 0, "K": 0, "V_raw": 0},
            analysis_summary="",
        )
        result.analysis_summary = _generate_summary(
            0, "F", True, veto_reason, dimensions, content_type,
        )
        return result

    # Step 1: 加权基础分 B
    weights = WEIGHT_MATRIX.get(content_type, WEIGHT_MATRIX["breaking_news"])
    B = weights[0] * d1 + weights[1] * d2 + weights[2] * d3 + weights[3] * d4 + weights[4] * d5

    # Step 2: 连续调节
    P = penalty_p(d6)
    K = boost_k(d7)

    # Step 3: V_raw
    V_raw = B * P * K

    # Step 4: 深度和验证度加成
    depth_bonus = 1.0 + 0.1 * math.tanh((d8 - 5) / 3)
    V_adjusted = V_raw * depth_bonus

    # Step 5: 归一化
    V_final = sigmoid_norm(V_adjusted)

    grade = _get_grade(V_final)

    result = ScoringResult(
        overall_score=V_final,
        grade=grade,
        vetoed=False,
        veto_reason="",
        content_type=content_type,
        content_type_label=CONTENT_TYPE_LABELS.get(content_type, content_type),
        dimensions=dimensions,
        intermediate={
            "B": round(B, 3),
            "P": round(P, 3),
            "K": round(K, 3),
            "depth_bonus": round(depth_bonus, 3),
            "V_raw": round(V_raw, 3),
            "V_adjusted": round(V_adjusted, 3),
        },
        analysis_summary="",
    )
    result.analysis_summary = _generate_summary(
        V_final, grade, False, "", dimensions, content_type,
    )
    return result
