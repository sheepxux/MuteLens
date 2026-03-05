"""
Mutelens - Article Fetcher v3.0
================================
从 URL 提取文章标题、正文、发布时间、域名等元数据。

提取策略（按优先级）：
  1. 本地提取: trafilatura → BeautifulSoup → __NEXT_DATA__/JSON-LD
  2. Jina Reader API: 免费、支持 JS 渲染、突破大多数反爬
  3. 所有方法失败后，返回有意义的错误信息
"""

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import trafilatura
from bs4 import BeautifulSoup


REQUEST_TIMEOUT = 20
JINA_TIMEOUT = 30
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": DEFAULT_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    "Referer": "https://www.google.com/",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "no-cache",
}

MIN_WORD_COUNT = 80


def _make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update(BROWSER_HEADERS)
    return session


@dataclass
class ArticleData:
    url: str
    domain: str
    title: str
    content: str
    published: str
    author: str
    word_count: int
    language: str
    cover_image: str
    source_type: str
    source_tier: str


# ─── 域名 → 来源类型 & 层级映射 ─────────────────────────────────────────────
DOMAIN_TYPE_MAP: dict[str, tuple[str, str]] = {
    "arxiv.org": ("research", "high"),
    "nature.com": ("research", "high"),
    "science.org": ("research", "high"),
    "proceedings.neurips.cc": ("research", "high"),
    "openai.com": ("tech_news", "high"),
    "anthropic.com": ("tech_news", "high"),
    "deepmind.com": ("tech_news", "high"),
    "blog.google": ("tech_news", "high"),
    "ai.meta.com": ("tech_news", "high"),
    "huggingface.co": ("tech_news", "high"),
    "mistral.ai": ("tech_news", "high"),
    "technologyreview.com": ("tech_news", "high"),
    "wired.com": ("tech_news", "high"),
    "arstechnica.com": ("tech_news", "high"),
    "bloomberg.com": ("business", "high"),
    "economist.com": ("business", "high"),
    "ft.com": ("business", "high"),
    "reuters.com": ("business", "high"),
    "techcrunch.com": ("tech_news", "medium"),
    "theverge.com": ("tech_news", "medium"),
    "scmp.com": ("business", "medium"),
    "restofworld.org": ("tech_news", "high"),
    "newsletter.pragmaticengineer.com": ("newsletter", "high"),
    "ben-evans.com": ("newsletter", "high"),
    "interconnects.ai": ("newsletter", "high"),
    "notboring.co": ("newsletter", "high"),
    "exponentialview.co": ("newsletter", "high"),
    "lastweekin.ai": ("newsletter", "high"),
    "sebastianraschka.com": ("newsletter", "high"),
    "substack.com": ("newsletter", "medium"),
    "36kr.com": ("tech_news", "medium"),
    "infoq.cn": ("tech_news", "medium"),
    "sspai.com": ("tech_news", "high"),
    "ifanr.com": ("tech_news", "medium"),
    "jiqizhixin.com": ("tech_news", "high"),
    "twitter.com": ("social_twitter", "medium"),
    "x.com": ("social_twitter", "medium"),
    "reddit.com": ("social_reddit", "medium"),
    "medium.com": ("medium", "medium"),
    "gov.cn": ("government_policy", "high"),
    "miit.gov.cn": ("government_policy", "high"),
    "nist.gov": ("government_policy", "high"),
}

# 需要付费订阅的域名（提供更有意义的错误提示）
PAYWALL_HINT: dict[str, str] = {
    "wsj.com": "WSJ",
    "bloomberg.com": "Bloomberg",
    "ft.com": "Financial Times",
    "economist.com": "The Economist",
}


def _get_domain(url: str) -> str:
    try:
        return urlparse(str(url)).netloc.lstrip("www.")
    except Exception:
        return ""


def _detect_source_info(domain: str) -> tuple[str, str]:
    if domain in DOMAIN_TYPE_MAP:
        return DOMAIN_TYPE_MAP[domain]
    parts = domain.split(".")
    for i in range(len(parts)):
        parent = ".".join(parts[i:])
        if parent in DOMAIN_TYPE_MAP:
            return DOMAIN_TYPE_MAP[parent]
    return ("tech_news", "medium")


def _detect_language(text: str) -> str:
    if not text:
        return "en"
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    ratio = chinese_chars / max(len(text), 1)
    return "zh" if ratio > 0.2 else "en"


# ─── 本地提取方法 ────────────────────────────────────────────────────────────

def _fetch_html(url: str) -> str:
    session = _make_session()
    resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    raw = resp.content
    ct = resp.headers.get("content-type", "")
    charset = None
    if "charset=" in ct:
        charset = ct.split("charset=")[-1].split(";")[0].strip()
    if not charset:
        charset = resp.apparent_encoding or "utf-8"
    try:
        return raw.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _extract_with_trafilatura(html: str) -> tuple[str, str, str, str, str]:
    meta_obj = trafilatura.metadata.extract_metadata(html)
    content = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        output_format="txt",
        favor_precision=False,
        no_fallback=False,
    ) or ""
    title = (meta_obj.title if meta_obj and meta_obj.title else "") or ""
    published = (meta_obj.date if meta_obj and meta_obj.date else "") or ""
    author = (meta_obj.author if meta_obj and meta_obj.author else "") or ""
    cover_image = (meta_obj.image if meta_obj and meta_obj.image else "") or ""
    return title, content, published, author, cover_image


def _extract_with_bs4(html: str) -> tuple[str, str, str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    title = ""
    for sel in [("meta", {"property": "og:title"}), ("meta", {"name": "twitter:title"})]:
        tag = soup.find(*sel)
        if tag and tag.get("content"):
            title = tag["content"].strip()
            break
    if not title:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else ""

    published = ""
    for prop in ["article:published_time", "datePublished", "date", "article:modified_time"]:
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            published = tag["content"].strip()
            break
    if not published:
        tag = soup.find("time")
        if tag:
            published = tag.get("datetime", tag.get_text(strip=True))

    author = ""
    for prop in ["author", "article:author"]:
        tag = soup.find("meta", attrs={"name": prop}) or soup.find("meta", property=prop)
        if tag and tag.get("content"):
            author = tag["content"].strip()
            break

    cover_image = ""
    for prop in ["og:image", "twitter:image"]:
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            cover_image = tag["content"].strip()
            break

    for remove in soup.find_all(["script", "style", "nav", "header", "footer",
                                  "aside", "noscript", "iframe", "form"]):
        remove.decompose()

    body = (soup.find("article") or soup.find("main") or
            soup.find("div", {"id": re.compile(r"content|article|post|story", re.I)}) or
            soup.find("body"))
    content = ""
    if body:
        content = re.sub(r"\s+", " ", body.get_text(separator=" ")).strip()

    return title, content, published, author, cover_image


def _flatten(obj: object, depth: int = 0) -> str:
    if depth > 8:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, list):
        return " ".join(_flatten(i, depth + 1) for i in obj)
    if isinstance(obj, dict):
        return " ".join(_flatten(v, depth + 1) for v in obj.values())
    return ""


def _deep_get(d: dict, *keys: str) -> object:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _extract_with_next_data(html: str) -> tuple[str, str, str, str, str]:
    soup = BeautifulSoup(html, "html.parser")

    nd_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if nd_tag:
        try:
            data = json.loads(nd_tag.get_text())
            props = _deep_get(data, "props", "pageProps") or {}

            article = None
            for key in ("article", "post", "data", "detail", "newsDetail",
                        "articleDetail", "content", "story"):
                candidate = props.get(key)
                if isinstance(candidate, dict):
                    article = candidate
                    break

            if article:
                title = (article.get("title") or article.get("name") or
                         article.get("headline") or "")
                published = (article.get("publishedAt") or article.get("pubDate") or
                             article.get("createdAt") or article.get("date") or "")
                author_raw = article.get("author") or article.get("authors") or ""
                if isinstance(author_raw, list):
                    author = ", ".join(
                        a.get("name", a) if isinstance(a, dict) else str(a)
                        for a in author_raw
                    )
                elif isinstance(author_raw, dict):
                    author = author_raw.get("name", "")
                else:
                    author = str(author_raw)

                cover_image = (article.get("coverImage") or article.get("image") or
                               article.get("thumbnail") or "")
                if isinstance(cover_image, dict):
                    cover_image = cover_image.get("url", "")

                raw_content = ""
                for ck in ("content", "body", "description", "summary",
                           "articleContent", "htmlContent", "text"):
                    raw_content = article.get(ck, "")
                    if raw_content and len(str(raw_content)) > 100:
                        break

                if raw_content:
                    content_str = str(raw_content)
                    if "<" in content_str:
                        content_soup = BeautifulSoup(content_str, "html.parser")
                        content = re.sub(r"\s+", " ", content_soup.get_text(" ")).strip()
                    else:
                        content = re.sub(r"\s+", " ", _flatten(raw_content)).strip()

                    if content and len(content.split()) >= 50:
                        return str(title), content, str(published), str(author), str(cover_image)
        except (json.JSONDecodeError, AttributeError, TypeError):
            pass

    for ld_tag in soup.find_all("script", {"type": "application/ld+json"}):
        try:
            data = json.loads(ld_tag.get_text())
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                if item.get("@type") not in ("Article", "NewsArticle",
                                              "BlogPosting", "TechArticle"):
                    continue
                title = item.get("headline", item.get("name", ""))
                published = item.get("datePublished", item.get("dateCreated", ""))
                author_raw = item.get("author", "")
                if isinstance(author_raw, list):
                    author = ", ".join(
                        a.get("name", "") if isinstance(a, dict) else str(a)
                        for a in author_raw
                    )
                elif isinstance(author_raw, dict):
                    author = author_raw.get("name", "")
                else:
                    author = str(author_raw)
                cover_raw = item.get("image", "")
                cover_image = (cover_raw.get("url", "") if isinstance(cover_raw, dict)
                               else str(cover_raw) if cover_raw else "")
                raw_body = item.get("articleBody", item.get("description", ""))
                if raw_body and len(str(raw_body)) > 100:
                    content = re.sub(r"\s+", " ", str(raw_body)).strip()
                    return str(title), content, str(published), str(author), str(cover_image)
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue

    return "", "", "", "", ""


def _try_local_extraction(url: str) -> ArticleData | None:
    """尝试本地提取（trafilatura → BS4 → NEXT_DATA），失败返回 None。"""
    domain = _get_domain(url)
    source_type, source_tier = _detect_source_info(domain)

    try:
        html = _fetch_html(url)
    except Exception:
        return None

    title, content, published, author, cover_image = "", "", "", "", ""

    try:
        title, content, published, author, cover_image = _extract_with_trafilatura(html)
        if content and len(content.split()) >= MIN_WORD_COUNT:
            return ArticleData(
                url=url, domain=domain, title=title, content=content,
                published=published, author=author,
                word_count=len(content.split()), language=_detect_language(content),
                cover_image=cover_image, source_type=source_type, source_tier=source_tier,
            )
    except Exception:
        pass

    try:
        t2, c2, p2, a2, img2 = _extract_with_bs4(html)
        title = title or t2
        published = published or p2
        author = author or a2
        cover_image = cover_image or img2
        if len(c2.split()) > len(content.split()):
            content = c2
    except Exception:
        pass

    if not content or len(content.split()) < MIN_WORD_COUNT:
        try:
            t3, c3, p3, a3, img3 = _extract_with_next_data(html)
            title = title or t3
            published = published or p3
            author = author or a3
            cover_image = cover_image or img3
            if len(c3.split()) > len(content.split()):
                content = c3
        except Exception:
            pass

    if content and len(content.split()) >= 50:
        return ArticleData(
            url=url, domain=domain, title=title, content=content[:15000],
            published=published, author=author,
            word_count=len(content.split()), language=_detect_language(content),
            cover_image=cover_image, source_type=source_type, source_tier=source_tier,
        )

    return None


# ─── Jina Reader API ─────────────────────────────────────────────────────────

def _extract_with_jina(url: str) -> ArticleData | None:
    """
    使用 Jina Reader API 提取文章内容。
    免费、支持 JS 渲染、能突破大多数反爬机制。
    返回 JSON 格式的结构化数据。
    """
    domain = _get_domain(url)
    source_type, source_tier = _detect_source_info(domain)

    try:
        resp = requests.get(
            f"https://r.jina.ai/{url}",
            headers={
                "Accept": "application/json",
                "X-No-Cache": "true",
            },
            timeout=JINA_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception:
        return None

    try:
        data = resp.json().get("data", {})
    except (ValueError, AttributeError):
        return None

    content = str(data.get("content", "")).strip()
    if not content or len(content.split()) < 50:
        return None

    title = str(data.get("title", "")).strip()
    published = str(data.get("publishedTime", "")).strip()
    author = ""
    cover_image = ""

    if isinstance(data.get("images"), list) and data["images"]:
        first_img = data["images"][0]
        if isinstance(first_img, dict):
            cover_image = first_img.get("src", first_img.get("url", ""))
        elif isinstance(first_img, str):
            cover_image = first_img

    return ArticleData(
        url=url,
        domain=domain,
        title=title,
        content=content[:15000],
        published=published,
        author=author,
        word_count=len(content.split()),
        language=_detect_language(content),
        cover_image=cover_image,
        source_type=source_type,
        source_tier=source_tier,
    )


# ─── 主入口 ──────────────────────────────────────────────────────────────────

def fetch_article(url: str) -> ArticleData:
    """
    从 URL 提取文章，多层降级策略：
    1. 本地提取（trafilatura → BS4 → NEXT_DATA）
    2. Jina Reader API（JS 渲染 + 反爬突破）
    """
    domain = _get_domain(url)

    # Pass 1: 本地提取
    result = _try_local_extraction(url)
    if result and result.word_count >= MIN_WORD_COUNT:
        return result

    # Pass 2: Jina Reader API
    jina_result = _extract_with_jina(url)
    if jina_result and jina_result.word_count >= 50:
        if result:
            jina_result.published = jina_result.published or result.published
            jina_result.author = jina_result.author or result.author
            jina_result.cover_image = jina_result.cover_image or result.cover_image
            if result.title and not jina_result.title:
                jina_result.title = result.title
        return jina_result

    # Pass 3: 如果本地至少拿到了一些内容，也接受
    if result and result.word_count >= 50:
        return result

    # 所有方法都失败了
    paywall_name = None
    for pw_domain, pw_name in PAYWALL_HINT.items():
        if domain == pw_domain or domain.endswith("." + pw_domain):
            paywall_name = pw_name
            break

    if paywall_name:
        raise ValueError(
            f"{paywall_name} 为付费订阅内容，无法提取完整文章。"
            f"建议尝试该文章的免费摘要版本或其他来源。"
        )

    raise ValueError(
        "无法从该页面提取有效文章内容。"
        "可能的原因：页面需要登录、依赖特殊 JavaScript 渲染、或内容较少。"
    )
