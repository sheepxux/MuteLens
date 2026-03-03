"""
GISTER Content Value Scorer
============================
对每篇文章计算 5 个客观因子分，输出 0-1 综合得分。

因子：
  F1 - Timeliness  (T): 时效衰减分
  F2 - Authority   (A): 来源权威分
  F3 - Velocity    (V): 趋势速度分（需要多时间点数据，首次运行用关键词共现近似）
  F4 - Density     (D): 信息密度分
  F5 - Novelty     (N): 话题新颖分（TF-IDF 余弦距离）

用法：
  python3 scripts/scorer.py                        # 对 ground_truth_samples.csv 打分
  python3 scripts/scorer.py --input my.csv         # 指定输入文件
  python3 scripts/scorer.py --weights 0.3 0.3 0.15 0.15 0.1  # 自定义权重
"""

import argparse
import math
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from email.utils import parsedate_to_datetime

# ─── 权重默认值 ───────────────────────────────────────────────────────────────
DEFAULT_WEIGHTS = {
    "timeliness": 0.25,
    "authority":  0.25,
    "velocity":   0.20,
    "density":    0.15,
    "novelty":    0.15,
}

# ─── 来源权威分映射 ───────────────────────────────────────────────────────────
SOURCE_TIER_SCORE = {
    "high":   1.0,
    "medium": 0.6,
    "low":    0.2,
}

# 域名信任分白名单（未列出的默认 0.5）
DOMAIN_TRUST = {
    "arxiv.org": 1.0, "nature.com": 1.0, "science.org": 1.0,
    "deeplearning.ai": 0.95, "openai.com": 0.95, "deepmind.com": 0.95,
    "technologyreview.com": 0.9, "wired.com": 0.85, "arstechnica.com": 0.85,
    "bloomberg.com": 0.85, "ft.com": 0.85, "economist.com": 0.85,
    "techcrunch.com": 0.75, "theverge.com": 0.75, "scmp.com": 0.75,
    "36kr.com": 0.7, "infoq.cn": 0.7, "sspai.com": 0.7, "ifanr.com": 0.65,
    "reddit.com": 0.55, "medium.com": 0.5, "substack.com": 0.6,
    "nitter.net": 0.6,  # Twitter via nitter
    "ben-evans.com": 0.9, "interconnects.ai": 0.85,
    "pragmaticengineer.com": 0.9, "notboring.co": 0.8,
    "lastweekin.ai": 0.8, "exponentialview.co": 0.85,
    "importai.substack.com": 0.85, "sebastianraschka.com": 0.85,
    "restofworld.org": 0.85, "tldr.tech": 0.75,
    "jiqizhixin.com": 0.8, "geekpark.net": 0.7,
    "newsletter.pragmaticengineer.com": 0.95,
    "lastweekin.ai": 0.85, "tldr.tech": 0.8,
}

# 科技/AI 高价值关键词（命中一个加分）
HIGH_VALUE_KEYWORDS = {
    "ai", "llm", "gpt", "model", "agent", "research", "paper", "study",
    "launch", "release", "raises", "funding", "acquisition", "policy",
    "regulation", "breakthrough", "open source", "benchmark", "dataset",
    "neural", "transformer", "diffusion", "robotics", "chip", "semiconductor",
    "人工智能", "大模型", "发布", "研究", "政策", "监管", "融资", "收购",
    "开源", "芯片", "突破", "算法", "数据", "论文",
}


# ─── F1: 时效衰减分 ───────────────────────────────────────────────────────────
def score_timeliness(published_str: str, half_life_hours: float = 14.0) -> float:
    """指数衰减：half_life_hours 内得分 > 0.5，超过 72h 趋近 0."""
    if not published_str or str(published_str).strip() == "":
        return 0.3  # 无时间信息给中等分

    try:
        # 尝试多种格式解析
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

        age_hours = (now - ts).total_seconds() / 3600
        lam = math.log(2) / half_life_hours
        return round(math.exp(-lam * max(age_hours, 0)), 4)

    except Exception:
        return 0.3


# ─── F2: 来源权威分 ───────────────────────────────────────────────────────────
def score_authority(source_tier: str, url: str) -> float:
    """结合 tier 和域名白名单综合打分。"""
    tier_s = SOURCE_TIER_SCORE.get(str(source_tier).lower(), 0.4)

    domain = ""
    try:
        from urllib.parse import urlparse
        domain = urlparse(str(url)).netloc.lstrip("www.")
    except Exception:
        pass

    domain_s = DOMAIN_TRUST.get(domain, 0.5)

    return round((tier_s * 0.6 + domain_s * 0.4), 4)


# ─── F3: 趋势速度分 ───────────────────────────────────────────────────────────
def score_velocity_batch(titles: list[str], sources: list[str]) -> list[float]:
    """
    跨源独立报道数：同一话题关键词在不同 source_name 中出现的来源数。
    多个独立媒体同时报道同一关键词话题 → 真实热点信号。
    避免单一来源（如 arXiv）批量论文堆关键词刷分。
    3 个不同来源同时出现 = 满分。
    """
    n = len(titles)
    doc_kws: list[set] = []
    for title in titles:
        kws = set(re.findall(r"\b[a-z\u4e00-\u9fff]{3,}\b", str(title).lower())) \
              & HIGH_VALUE_KEYWORDS
        doc_kws.append(kws)

    scores = []
    for i in range(n):
        kws_i = doc_kws[i]
        if not kws_i:
            scores.append(0.1)
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
        scores.append(round(min(len(seen_srcs) / 3.0, 1.0), 4))
    return scores


# ─── F4: 信息密度分 ───────────────────────────────────────────────────────────
def score_density(content: str) -> float:
    """
    综合评估：
    - 有效词密度
    - 含数字（数据支撑）
    - 含引用关键词（"according to", "said", "报告"等）
    - 命中高价值关键词数量
    """
    text = str(content)
    if len(text) < 20:
        return 0.0

    words = re.findall(r"\b\w+\b", text.lower())
    word_count = max(len(words), 1)

    # 有效词密度（去除停用词后的词数比）
    stopwords = {"the", "a", "an", "is", "in", "of", "to", "and", "or",
                 "for", "on", "at", "by", "with", "this", "that", "are",
                 "was", "it", "be", "as", "from", "but", "not", "have"}
    meaningful = [w for w in words if w not in stopwords and len(w) > 2]
    density_ratio = len(meaningful) / word_count

    # 含数字
    has_number = 1 if re.search(r"\d+", text) else 0

    # 含引用/数据来源信号
    has_citation = 1 if re.search(
        r"(according to|study|report|research|found that|said|announced|"
        r"percent|%|million|billion|据|报告|研究|发现|宣布|亿|万)", text, re.I
    ) else 0

    # 高价值关键词命中数
    kw_hits = sum(1 for kw in HIGH_VALUE_KEYWORDS if kw in text.lower())
    kw_score = min(kw_hits / 5.0, 1.0)

    score = (
        density_ratio * 0.3
        + has_number * 0.25
        + has_citation * 0.25
        + kw_score * 0.2
    )
    return round(min(score, 1.0), 4)


# ─── F5: 话题新颖分 ───────────────────────────────────────────────────────────
def score_novelty_batch(titles: list[str], contents: list[str]) -> list[float]:
    """
    用 TF-IDF 向量化后计算每篇与其他篇的最大余弦相似度，
    novelty = 1 - max_similarity（越独特分越高）。
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [
            (str(t) + " " + str(c))[:500]
            for t, c in zip(titles, contents)
        ]
        vec = TfidfVectorizer(max_features=2000, sublinear_tf=True)
        tfidf = vec.fit_transform(corpus)
        sim_matrix = cosine_similarity(tfidf)

        scores = []
        n = len(corpus)
        for i in range(n):
            row = sim_matrix[i].copy()
            row[i] = 0  # 排除自身
            max_sim = row.max() if n > 1 else 0
            scores.append(round(1.0 - float(max_sim), 4))
        return scores

    except ImportError:
        # sklearn 未安装时降级为全部给 0.5
        return [0.5] * len(titles)


# ─── 综合评分 ─────────────────────────────────────────────────────────────────
def score_dataframe(df: pd.DataFrame, weights: dict) -> pd.DataFrame:
    df = df.copy()
    all_titles = df["title"].fillna("").tolist()

    print("计算 F1 时效分 ...", flush=True)
    df["f1_timeliness"] = df["published"].apply(score_timeliness)

    print("计算 F2 权威分 ...", flush=True)
    df["f2_authority"] = df.apply(
        lambda r: score_authority(r.get("source_tier", ""), r.get("url", "")), axis=1
    )

    print("计算 F3 趋势分 ...", flush=True)
    try:
        from scripts.trending import get_velocity_scores, DB_PATH
        if DB_PATH.exists():
            velocity_scores = get_velocity_scores(
                df["title"].fillna("").tolist(),
                df["source_name"].fillna("").tolist(),
            )
            print("    使用真实时序 velocity (SQLite)", flush=True)
        else:
            raise FileNotFoundError
    except Exception:
        velocity_scores = score_velocity_batch(
            df["title"].fillna("").tolist(),
            df["source_name"].fillna("").tolist(),
        )
        print("    使用跨源近似 velocity（首次运行，无历史数据）", flush=True)
    df["f3_velocity"] = velocity_scores

    print("计算 F4 密度分 ...", flush=True)
    df["f4_density"] = df["content"].apply(score_density)

    print("计算 F5 新颖分 ...", flush=True)
    novelty_scores = score_novelty_batch(
        df["title"].fillna("").tolist(),
        df["content"].fillna("").tolist(),
    )
    df["f5_novelty"] = novelty_scores

    w = weights
    df["value_score"] = (
        w["timeliness"] * df["f1_timeliness"]
        + w["authority"]  * df["f2_authority"]
        + w["velocity"]   * df["f3_velocity"]
        + w["density"]    * df["f4_density"]
        + w["novelty"]    * df["f5_novelty"]
    ).round(4)

    # 来源类型系数：纯学术摘要 / 推文 对普通用户价值打折
    TYPE_MULTIPLIER = {
        "research":       0.75,  # arXiv 论文摘要，专业门槛高
        "social_twitter": 0.85,  # 推文，信息量有限
        "social_reddit":  0.90,  # Reddit 帖子
        "medium":         0.88,  # Medium 博客质量参差
    }
    src_type = df.get("source_type", pd.Series([""] * len(df)))
    multiplier = src_type.map(lambda t: TYPE_MULTIPLIER.get(str(t), 1.0))
    df["value_score"] = (df["value_score"] * multiplier).round(4)

    return df


# ─── 主函数 ──────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GISTER Content Value Scorer")
    parser.add_argument("--input",   default="ground_truth_samples.csv")
    parser.add_argument("--output",  default=None, help="输出文件名，默认在原文件名加 _scored")
    parser.add_argument("--weights", nargs=5, type=float, metavar=("T", "A", "V", "D", "N"),
                        help="5个权重: T A V D N (需加和为1)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ 找不到文件: {input_path}")
        return

    output_path = Path(args.output) if args.output else \
        input_path.with_name(input_path.stem + "_scored.csv")

    weights = DEFAULT_WEIGHTS.copy()
    if args.weights:
        keys = list(DEFAULT_WEIGHTS.keys())
        weights = dict(zip(keys, args.weights))
        total = sum(weights.values())
        if abs(total - 1.0) > 0.01:
            print(f"⚠ 权重之和={total:.2f}，已自动归一化")
            weights = {k: v / total for k, v in weights.items()}

    print(f"读取: {input_path}  ({len(pd.read_csv(input_path))} 行)")
    df = pd.read_csv(input_path)

    df = score_dataframe(df, weights)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n✅ 已写入: {output_path}")

    # 分布统计
    print("\n📊 value_score 分布:")
    print(df["value_score"].describe().round(3).to_string())

    print("\n🏆 Top 10 高分文章:")
    cols = ["title", "source_name", "value_score",
            "f1_timeliness", "f2_authority", "f3_velocity", "f4_density", "f5_novelty"]
    top = df.nlargest(10, "value_score")[cols]
    for _, row in top.iterrows():
        print(f"  [{row['value_score']:.3f}] {str(row['title'])[:60]}  ({row['source_name']})")

    print("\n📉 Bottom 10 低分文章:")
    bot = df.nsmallest(10, "value_score")[cols]
    for _, row in bot.iterrows():
        print(f"  [{row['value_score']:.3f}] {str(row['title'])[:60]}  ({row['source_name']})")

    # 如果有 label 列，计算与人工标注的相关性
    if "label" in df.columns:
        labeled = df[df["label"].notna() & (df["label"] != "")]
        if len(labeled) > 10:
            from scipy.stats import pointbiserialr
            try:
                labels = labeled["label"].astype(int)
                corr, pval = pointbiserialr(labels, labeled["value_score"])
                print(f"\n📈 与人工标注相关性: r={corr:.3f}, p={pval:.4f} (n={len(labeled)})")
            except Exception:
                pass


if __name__ == "__main__":
    main()
