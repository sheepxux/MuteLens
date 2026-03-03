"""
GISTER - Ground Truth Sample Fetcher
=====================================
从多个 RSS 源抓取文章，清洗 HTML，导出 ground_truth_samples.csv
供人工标注使用（标注列 label: 1=高价值保留, 0=垃圾抛弃）

依赖安装:
    pip install feedparser requests beautifulsoup4 pandas

运行:
    python scripts/fetch_samples.py
"""

import csv
import hashlib
import os
import re
import time
from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional

import feedparser
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dotenv import dotenv_values

# ─── 信源配置 ──────────────────────────────────────────────────────────────────

SOURCES = [
    # ──────────────────────────────────────────────────────────
    # 英文高质量正样本：科技深度 & Newsletter
    # ──────────────────────────────────────────────────────────
    {"name": "Hacker News",             "url": "https://news.ycombinator.com/rss",                               "lang": "en", "tier": "high", "type": "tech_news"},
    {"name": "MIT Technology Review",   "url": "https://www.technologyreview.com/feed/",                         "lang": "en", "tier": "high", "type": "tech_news"},
    {"name": "Wired",                   "url": "https://www.wired.com/feed/rss",                                 "lang": "en", "tier": "high", "type": "tech_news"},
    {"name": "Ars Technica",            "url": "https://feeds.arstechnica.com/arstechnica/index",                 "lang": "en", "tier": "high", "type": "tech_news"},
    {"name": "The Verge",               "url": "https://www.theverge.com/rss/index.xml",                          "lang": "en", "tier": "medium", "type": "tech_news"},
    {"name": "TechCrunch",              "url": "https://techcrunch.com/feed/",                                   "lang": "en", "tier": "medium", "type": "tech_news"},
    # ── 顶级 AI/研究 Newsletter ──
    {"name": "The Pragmatic Engineer",  "url": "https://newsletter.pragmaticengineer.com/feed",                  "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Benedict Evans",          "url": "https://www.ben-evans.com/benedictevans/rss.xml",                "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Import AI (Jack Clark)",  "url": "https://importai.substack.com/feed",                             "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Ahead of AI",             "url": "https://magazine.sebastianraschka.com/feed",                     "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "TLDR Newsletter",         "url": "https://tldr.tech/api/rss/tech",                                 "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Not Boring",              "url": "https://www.notboring.co/feed",                                  "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Exponential View",        "url": "https://www.exponentialview.co/feed",                             "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "AI Supremacy",            "url": "https://www.aisupremacy.org/feed",                                "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Last Week in AI",         "url": "https://lastweekin.ai/feed",                                      "lang": "en", "tier": "high", "type": "newsletter"},
    {"name": "Interconnects",           "url": "https://www.interconnects.ai/feed",                               "lang": "en", "tier": "high", "type": "newsletter"},
    # ── 前沿研究 ──
    {"name": "arXiv cs.AI",             "url": "https://arxiv.org/rss/cs.AI",                                    "lang": "en", "tier": "high", "type": "research"},
    {"name": "arXiv cs.LG",             "url": "https://arxiv.org/rss/cs.LG",                                    "lang": "en", "tier": "high", "type": "research"},
    {"name": "Papers With Code",        "url": "https://paperswithcode.com/sota/rss.xml",                          "lang": "en", "tier": "high", "type": "research"},
    # ── 商业宏观 ──
    {"name": "Bloomberg Technology",    "url": "https://feeds.bloomberg.com/technology/news.rss",                 "lang": "en", "tier": "high", "type": "business"},
    {"name": "Reuters Technology",      "url": "https://feeds.reuters.com/reuters/technologyNews",                  "lang": "en", "tier": "high", "type": "business"},
    {"name": "The Economist Tech",      "url": "https://www.economist.com/science-and-technology/rss.xml",        "lang": "en", "tier": "high", "type": "business"},
    {"name": "Rest of World",           "url": "https://restofworld.org/feed/",                                   "lang": "en", "tier": "high", "type": "business"},
    {"name": "SCMP Technology",         "url": "https://www.scmp.com/rss/5/feed",                                 "lang": "en", "tier": "medium", "type": "business"},
    # ── Medium ──
    {"name": "Medium: AI",              "url": "https://medium.com/feed/tag/artificial-intelligence",             "lang": "en", "tier": "medium", "type": "medium"},
    {"name": "Medium: Technology",      "url": "https://medium.com/feed/tag/technology",                          "lang": "en", "tier": "medium", "type": "medium"},
    {"name": "Medium: Startup",         "url": "https://medium.com/feed/tag/startup",                             "lang": "en", "tier": "medium", "type": "medium"},
    {"name": "Medium: Programming",     "url": "https://medium.com/feed/tag/programming",                         "lang": "en", "tier": "medium", "type": "medium"},
    # ──────────────────────────────────────────────────────────
    # 中文高质量正样本
    # ──────────────────────────────────────────────────────────
    {"name": "少数派",               "url": "https://sspai.com/feed",                                         "lang": "zh", "tier": "high", "type": "tech_news"},
    {"name": "36氪深度",             "url": "https://36kr.com/feed",                                          "lang": "zh", "tier": "medium", "type": "tech_news"},
    {"name": "InfoQ China",             "url": "https://www.infoq.cn/feed",                                      "lang": "zh", "tier": "medium", "type": "tech_news"},
    {"name": "机器之心",               "url": "https://www.jiqizhixin.com/rss",                                   "lang": "zh", "tier": "high", "type": "tech_news"},
    {"name": "爱范儿",                 "url": "https://www.ifanr.com/feed",                                      "lang": "zh", "tier": "medium", "type": "tech_news"},
    # ── 中国政府政策 ──
    {"name": "中国政府网(政策原文)", "url": "https://www.gov.cn/zhengce/zuixin/index.htm",              "lang": "zh", "tier": "high", "type": "government_policy"},
    {"name": "工信部政策",             "url": "https://www.miit.gov.cn/jgsj/index.html",                       "lang": "zh", "tier": "high", "type": "government_policy"},
    # ── 美国政府政策 ──
    {"name": "EU AI Policy",            "url": "https://digital-strategy.ec.europa.eu/en/rss.xml",                "lang": "en", "tier": "high", "type": "government_policy"},
    {"name": "NIST Cybersecurity",      "url": "https://www.nist.gov/news-events/news/rss.xml",                    "lang": "en", "tier": "high", "type": "government_policy"},
    # ── Twitter/X 即时动态（nitter.net 代理，无需 Key）──
    {"name": "Twitter @sama",           "url": "https://nitter.net/sama/rss",                                    "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @karpathy",       "url": "https://nitter.net/karpathy/rss",                                "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @ylecun",         "url": "https://nitter.net/ylecun/rss",                                  "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @GaryMarcus",     "url": "https://nitter.net/GaryMarcus/rss",                              "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @benedictevans",  "url": "https://nitter.net/benedictevans/rss",                           "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @paulg",          "url": "https://nitter.net/paulg/rss",                                   "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @naval",          "url": "https://nitter.net/naval/rss",                                   "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @balajis",        "url": "https://nitter.net/balajis/rss",                                 "lang": "en", "tier": "high", "type": "social_twitter"},
    {"name": "Twitter @elonmusk",       "url": "https://nitter.net/elonmusk/rss",                                "lang": "en", "tier": "medium", "type": "social_twitter"},
    {"name": "Twitter @satyanadella",   "url": "https://nitter.net/satyanadella/rss",                            "lang": "en", "tier": "high", "type": "social_twitter"},
    # ── Reddit 社区 ──
    {"name": "Reddit r/MachineLearning","url": "https://www.reddit.com/r/MachineLearning/top/.rss?t=week",       "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/technology",     "url": "https://www.reddit.com/r/technology/top/.rss?t=week",           "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/artificial",     "url": "https://www.reddit.com/r/artificial/top/.rss?t=week",           "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/singularity",    "url": "https://www.reddit.com/r/singularity/top/.rss?t=week",          "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/Entrepreneur",   "url": "https://www.reddit.com/r/Entrepreneur/top/.rss?t=week",         "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/geopolitics",    "url": "https://www.reddit.com/r/geopolitics/top/.rss?t=week",          "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/ChatGPT",        "url": "https://www.reddit.com/r/ChatGPT/top/.rss?t=week",              "lang": "en", "tier": "medium", "type": "social_reddit"},
    {"name": "Reddit r/LocalLLaMA",     "url": "https://www.reddit.com/r/LocalLLaMA/top/.rss?t=week",           "lang": "en", "tier": "medium", "type": "social_reddit"},
    # ── 低质量对照组（负样本池）──
    {"name": "新浪科技",               "url": "https://rss.sina.com.cn/tech/internet/index.xml",              "lang": "zh", "tier": "low", "type": "tech_news"},
    {"name": "虎嗅网",                 "url": "https://www.huxiu.com/rss/0.xml",                               "lang": "zh", "tier": "low", "type": "tech_news"},
    {"name": "Reddit r/news",           "url": "https://www.reddit.com/r/news/top/.rss?t=week",                  "lang": "en", "tier": "low", "type": "social_reddit"},
]

# ── RSSHub Twitter/X 接入配置 ────────────────────────────────────────────
# Twitter 路由需要账号 Cookie 认证，在 .env 文件中配置。
# 配置方法见 scripts/.env.example
# TikTok/小红书：暂不接入。

_env = dotenv_values(os.path.join(os.path.dirname(__file__), ".env"))
RSSHUB_BASE = _env.get("RSSHUB_BASE", "https://rsshub.app")  # 可替换为自托管实例

# ── Twitter/X 高价值账号（AI / 科技 / 商业 / 政策）──
TWITTER_ACCOUNTS = [
    # AI & 研究
    "sama",           # Sam Altman
    "karpathy",       # Andrej Karpathy
    "ylecun",         # Yann LeCun
    "demishassabis",  # Demis Hassabis
    "danielgross",    # Daniel Gross
    # 科技商业
    "benedictevans",  # Benedict Evans
    "paulg",          # Paul Graham
    "elonmusk",       # Elon Musk（争议大，但信息密度高）
    "satyanadella",   # Satya Nadella
    # 政策 & 宏观
    "balajis",        # Balaji Srinivasan
    "naval",          # Naval Ravikant
    # 中文科技圈
    "chuangtianya",   # 按需替换为实际高质量中文账号
]

def build_rsshub_sources() -> list[dict]:
    """动态生成 RSSHub Twitter/X 信源列表。"""
    sources = []
    twitter_cookie = _env.get("TWITTER_COOKIE", "")

    if twitter_cookie:
        for account in TWITTER_ACCOUNTS:
            sources.append({
                "name": f"Twitter @{account}",
                "url": f"{RSSHUB_BASE}/twitter/user/{account}",
                "lang": "en",
                "tier": "high",
                "type": "social_twitter",
                "headers": {"Cookie": twitter_cookie},
            })
    else:
        print("⚠ 未配置 TWITTER_COOKIE，跳过 Twitter 信源。见 scripts/.env.example")

    return sources

MAX_PER_SOURCE = 25       # 每个源最多抓取条数
TARGET_TOTAL = 600        # 总目标条数（去重后取前500）
REQUEST_TIMEOUT = 10      # HTTP 请求超时秒数
REQUEST_DELAY = 0.5       # 每次请求间隔（避免被封）
MIN_CONTENT_CHARS = 100   # 正文最少字符数（过短则跳过）

OUTPUT_PATH = "ground_truth_samples.csv"

# ─── 数据结构 ──────────────────────────────────────────────────────────────────

@dataclass
class Article:
    id: str               # MD5(url)，用于去重
    source_name: str
    source_tier: str      # high / medium / low
    source_type: str      # tech_news / newsletter / government_policy / social_reddit
    lang: str
    title: str
    url: str
    published: str
    content: str          # 清洗后的纯文本正文
    word_count: int
    cover_pic_url: str    # og:image，爬虫层直接解析，不走 LLM
    label: str            # 留空，人工填写: 1 或 0

# ─── 工具函数 ──────────────────────────────────────────────────────────────────

def make_id(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()[:12]


def clean_html(raw: str) -> str:
    """去除 HTML 标签，合并多余空白，返回纯文本。"""
    soup = BeautifulSoup(raw or "", "html.parser")
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def fetch_cover_pic(url: str) -> str:
    """解析页面 og:image / twitter:image meta tag，0 成本，不调 LLM。"""
    try:
        resp = requests.get(url, timeout=REQUEST_TIMEOUT, headers={
            "User-Agent": "Mozilla/5.0 (compatible; GisterBot/0.1)"
        })
        soup = BeautifulSoup(resp.text, "html.parser")
        for prop in ["og:image", "twitter:image"]:
            tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if tag and tag.get("content"):
                return tag["content"].strip()
    except Exception:
        pass
    return ""


def parse_date(entry) -> str:
    """尝试从 feedparser entry 提取发布时间。"""
    for attr in ("published", "updated", "created"):
        val = getattr(entry, attr, None)
        if val:
            return val
    return ""


def fetch_full_content(entry, article_url: str) -> tuple[str, str]:
    """
    优先取 RSS entry 中的全文字段；
    若只有摘要，则回退到抓取原始页面正文。
    返回 (clean_text, cover_pic_url)
    """
    raw = ""
    if hasattr(entry, "content") and entry.content:
        raw = entry.content[0].get("value", "")
    if not raw and hasattr(entry, "summary"):
        raw = entry.summary or ""

    content = clean_html(raw)

    # 若内容太短，尝试抓取原始页面
    if len(content) < MIN_CONTENT_CHARS:
        try:
            time.sleep(REQUEST_DELAY)
            resp = requests.get(article_url, timeout=REQUEST_TIMEOUT, headers={
                "User-Agent": "Mozilla/5.0 (compatible; GisterBot/0.1)"
            })
            soup = BeautifulSoup(resp.text, "html.parser")
            # 优先取 <article> 标签
            article_tag = soup.find("article")
            body = article_tag or soup.find("body")
            if body:
                content = clean_html(str(body))
            # 顺手拿封面图
            cover = ""
            for prop in ["og:image", "twitter:image"]:
                tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
                if tag and tag.get("content"):
                    cover = tag["content"].strip()
                    break
            return content, cover
        except Exception:
            pass

    return content, ""

# ─── 核心抓取逻辑 ─────────────────────────────────────────────────────────────

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def fetch_source(source: dict) -> list[Article]:
    print(f"  → 抓取: {source['name']} ({source['url']})")
    articles = []
    seen_ids = set()

    headers = {"User-Agent": DEFAULT_UA}
    headers.update(source.get("headers", {}))

    try:
        resp = requests.get(source["url"], headers=headers, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
    except Exception as e:
        print(f"    ✗ 请求失败: {e}")
        return articles

    entries = feed.entries[:MAX_PER_SOURCE]
    print(f"    找到 {len(entries)} 条 entry")

    for entry in entries:
        url = getattr(entry, "link", "") or getattr(entry, "id", "")
        if not url:
            continue

        article_id = make_id(url)
        if article_id in seen_ids:
            continue
        seen_ids.add(article_id)

        title = clean_html(getattr(entry, "title", ""))
        if not title:
            continue

        is_twitter = source.get("type") == "social_twitter"
        content, cover_from_page = fetch_full_content(entry, url)
        min_chars = 10 if is_twitter else MIN_CONTENT_CHARS
        if len(content) < min_chars:
            print(f"    ⚠ 跳过（内容过短 {len(content)} chars）: {title[:40]}")
            continue

        # 封面图：优先从 meta 标签取（已在 fetch_full_content 中处理）
        cover = cover_from_page  # 如需单独抓取可调用 fetch_cover_pic(url)

        articles.append(Article(
            id=article_id,
            source_name=source["name"],
            source_tier=source["tier"],
            source_type=source.get("type", "unknown"),
            lang=source["lang"],
            title=title,
            url=url,
            published=parse_date(entry),
            content=content[:3000],  # 截断，够标注用
            word_count=len(content),
            cover_pic_url=cover,
            label="",  # 人工填写
        ))

        time.sleep(REQUEST_DELAY)

    print(f"    ✓ 收集 {len(articles)} 篇有效文章")
    return articles


def deduplicate(articles: list[Article]) -> list[Article]:
    """基于 id（URL MD5）去重。SimHash 去重在 Stage 2 评测阶段引入。"""
    seen = set()
    result = []
    for a in articles:
        if a.id not in seen:
            seen.add(a.id)
            result.append(a)
    return result


def main():
    print("=" * 60)
    print("GISTER Ground Truth Fetcher")
    print(f"目标: 500 篇文章（抓取上限 {TARGET_TOTAL}）→ {OUTPUT_PATH}")
    print("=" * 60)

    all_articles: list[Article] = []

    all_sources = SOURCES + build_rsshub_sources()
    for source in all_sources:
        if len(all_articles) >= TARGET_TOTAL:
            break
        fetched = fetch_source(source)
        all_articles.extend(fetched)

    all_articles = deduplicate(all_articles)
    total_fetched = len(all_articles)
    all_articles = all_articles[:500]

    print(f"\n去重后共 {total_fetched} 篇，取前 {len(all_articles)} 篇写入 {OUTPUT_PATH} ...")

    field_names = [f.name for f in fields(Article)]
    df = pd.DataFrame([vars(a) for a in all_articles], columns=field_names)

    # 打乱顺序，避免标注者因来源顺序产生先入为主的偏见
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df.insert(0, "row_num", range(1, len(df) + 1))

    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")  # utf-8-sig 兼容 Excel 中文

    try:
        from trending import record_batch
        record_batch(df["title"].fillna("").tolist(), df["source_name"].fillna("").tolist())
    except Exception as _e:
        print(f"  ⚠ trending 记录失败（不影响主流程）: {_e}")

    print("\n✅ 完成！文件已保存。")
    print("\n📊 来源分布:")
    print(df.groupby(["source_name", "source_tier"])["row_num"].count().to_string())
    print(f"\n📝 下一步：用 Excel / Numbers 打开 {OUTPUT_PATH}")
    print("   在 'label' 列填写: 1 = 高价值保留, 0 = 垃圾抛弃")
    print("   标注完成后运行 eval_classifier.py 计算 F1 分数")


if __name__ == "__main__":
    main()
