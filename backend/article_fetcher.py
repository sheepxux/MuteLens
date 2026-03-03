"""
ArticleRadar - Article Fetcher
================================
从 URL 提取文章标题、正文、发布时间、域名等元数据。
优先使用 trafilatura，降级到 BeautifulSoup。
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
    # 学术
    "arxiv.org": ("research", "high"),
    "nature.com": ("research", "high"),
    "science.org": ("research", "high"),
    "proceedings.neurips.cc": ("research", "high"),
    # 官方产品博客
    "openai.com": ("tech_news", "high"),
    "anthropic.com": ("tech_news", "high"),
    "deepmind.com": ("tech_news", "high"),
    "blog.google": ("tech_news", "high"),
    "ai.meta.com": ("tech_news", "high"),
    "huggingface.co": ("tech_news", "high"),
    "mistral.ai": ("tech_news", "high"),
    # 顶级媒体
    "technologyreview.com": ("tech_news", "high"),
    "wired.com": ("tech_news", "high"),
    "arstechnica.com": ("tech_news", "high"),
    "bloomberg.com": ("business", "high"),
    "economist.com": ("business", "high"),
    "ft.com": ("business", "high"),
    "reuters.com": ("business", "high"),
    # 科技媒体
    "techcrunch.com": ("tech_news", "medium"),
    "theverge.com": ("tech_news", "medium"),
    "scmp.com": ("business", "medium"),
    "restofworld.org": ("tech_news", "high"),
    # Newsletter
    "newsletter.pragmaticengineer.com": ("newsletter", "high"),
    "ben-evans.com": ("newsletter", "high"),
    "interconnects.ai": ("newsletter", "high"),
    "notboring.co": ("newsletter", "high"),
    "exponentialview.co": ("newsletter", "high"),
    "lastweekin.ai": ("newsletter", "high"),
    "sebastianraschka.com": ("newsletter", "high"),
    "substack.com": ("newsletter", "medium"),
    # 中文
    "36kr.com": ("tech_news", "medium"),
    "infoq.cn": ("tech_news", "medium"),
    "sspai.com": ("tech_news", "high"),
    "ifanr.com": ("tech_news", "medium"),
    "jiqizhixin.com": ("tech_news", "high"),
    # 社交
    "twitter.com": ("social_twitter", "medium"),
    "x.com": ("social_twitter", "medium"),
    "reddit.com": ("social_reddit", "medium"),
    "medium.com": ("medium", "medium"),
    # 政策
    "gov.cn": ("government_policy", "high"),
    "miit.gov.cn": ("government_policy", "high"),
    "nist.gov": ("government_policy", "high"),
}


def _get_domain(url: str) -> str:
    try:
        return urlparse(str(url)).netloc.lstrip("www.")
    except Exception:
        return ""


def _detect_source_info(domain: str) -> tuple[str, str]:
    """根据域名检测 source_type 和 source_tier。"""
    if domain in DOMAIN_TYPE_MAP:
        return DOMAIN_TYPE_MAP[domain]
    # 尝试匹配子域名
    parts = domain.split(".")
    for i in range(len(parts)):
        parent = ".".join(parts[i:])
        if parent in DOMAIN_TYPE_MAP:
            return DOMAIN_TYPE_MAP[parent]
    # 默认
    return ("tech_news", "medium")


def _detect_language(text: str) -> str:
    """简单语言检测：中文字符占比 > 20% 则为 zh，否则 en。"""
    if not text:
        return "en"
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    ratio = chinese_chars / max(len(text), 1)
    return "zh" if ratio > 0.2 else "en"


BLOCKED_DOMAINS = {
    "medium.com": "Medium 对服务器端请求设有访问限制，建议改用其他来源的文章链接",
    "bloomberg.com": "Bloomberg 需要订阅，无法提取文章内容",
    "ft.com": "FT 需要订阅，无法提取文章内容",
    "economist.com": "The Economist 需要订阅，无法提取文章内容",
    "wsj.com": "WSJ 需要订阅，无法提取文章内容",
    "openai.com": "OpenAI 网站对爬虫设有访问限制，无法提取文章内容",
    "reuters.com": "Reuters 需要认证，无法提取文章内容",
}


def _check_blocked(domain: str) -> None:
    if domain in BLOCKED_DOMAINS:
        raise ValueError(BLOCKED_DOMAINS[domain])
    for blocked in BLOCKED_DOMAINS:
        if domain.endswith("." + blocked):
            raise ValueError(BLOCKED_DOMAINS[blocked])


def _fetch_html(url: str) -> str:
    """使用浏览器 headers 获取 HTML，返回原始文本。"""
    session = _make_session()
    resp = session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    # Decode bytes directly — do NOT rely on apparent_encoding which can truncate
    raw = resp.content
    # Respect charset from Content-Type, fall back to chardet/utf-8
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
    """用 trafilatura 从 HTML 提取 (title, content, published, author, cover_image)。"""
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
    """BeautifulSoup 降级提取，尽量找 <article> 主体。"""
    soup = BeautifulSoup(html, "html.parser")

    # title
    title = ""
    for sel in [("meta", {"property": "og:title"}), ("meta", {"name": "twitter:title"})]:
        tag = soup.find(*sel)
        if tag and tag.get("content"):
            title = tag["content"].strip()
            break
    if not title:
        t = soup.find("title")
        title = t.get_text(strip=True) if t else ""

    # published
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

    # author
    author = ""
    for prop in ["author", "article:author"]:
        tag = soup.find("meta", attrs={"name": prop}) or soup.find("meta", property=prop)
        if tag and tag.get("content"):
            author = tag["content"].strip()
            break

    # cover
    cover_image = ""
    for prop in ["og:image", "twitter:image"]:
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        if tag and tag.get("content"):
            cover_image = tag["content"].strip()
            break

    # content — prefer <article>, then <main>, then <body>
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
    """递归地将嵌套 JSON 对象中的字符串拼接为纯文本。"""
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
    """安全地从嵌套字典中取值。"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _extract_with_next_data(html: str) -> tuple[str, str, str, str, str]:
    """从 __NEXT_DATA__ (Next.js) 或 JSON-LD 中提取文章内容。"""
    soup = BeautifulSoup(html, "html.parser")

    # ── 1. __NEXT_DATA__ (Next.js SSR) ──────────────────────────────────────
    nd_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if nd_tag:
        try:
            data = json.loads(nd_tag.get_text())
            props = _deep_get(data, "props", "pageProps") or {}

            # Try common key patterns across different Next.js sites
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

                # Content field — try multiple keys
                raw_content = ""
                for ck in ("content", "body", "description", "summary",
                           "articleContent", "htmlContent", "text"):
                    raw_content = article.get(ck, "")
                    if raw_content and len(str(raw_content)) > 100:
                        break

                if raw_content:
                    # Strip HTML tags if content is HTML
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

    # ── 2. JSON-LD (Schema.org Article) ─────────────────────────────────────
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


def fetch_article(url: str) -> ArticleData:
    """从 URL 提取文章全部信息。"""
    domain = _get_domain(url)
    source_type, source_tier = _detect_source_info(domain)

    _check_blocked(domain)

    # Always fetch HTML ourselves with browser headers
    try:
        html = _fetch_html(url)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else "?"
        raise ValueError(f"无法访问该页面（HTTP {status}），请检查链接是否有效")
    except requests.exceptions.Timeout:
        raise ValueError("请求超时，该网站响应过慢，请稍后重试")
    except requests.exceptions.ConnectionError:
        raise ValueError("无法连接到该网站，请检查链接或网络状态")
    except Exception as e:
        raise ValueError(f"无法获取页面内容: {e}")

    # Pass 1: trafilatura (best quality)
    try:
        title, content, published, author, cover_image = _extract_with_trafilatura(html)
        if content and len(content.split()) >= 80:
            return ArticleData(
                url=url, domain=domain, title=title, content=content,
                published=published, author=author,
                word_count=len(content.split()), language=_detect_language(content),
                cover_image=cover_image, source_type=source_type, source_tier=source_tier,
            )
    except Exception:
        title, content, published, author, cover_image = "", "", "", "", ""

    # Pass 2: BeautifulSoup fallback
    try:
        title2, content2, published2, author2, cover2 = _extract_with_bs4(html)
        title = title or title2
        published = published or published2
        author = author or author2
        cover_image = cover_image or cover2
        if len(content2.split()) > len(content.split()):
            content = content2
    except Exception:
        pass

    # Pass 3: __NEXT_DATA__ / JSON-LD (for Next.js SPAs with embedded data)
    if not content or len(content.split()) < 80:
        try:
            title3, content3, published3, author3, cover3 = _extract_with_next_data(html)
            title = title or title3
            published = published or published3
            author = author or author3
            cover_image = cover_image or cover3
            if len(content3.split()) > len(content.split()):
                content = content3
        except Exception:
            pass

    if not content or len(content.split()) < 50:
        raise ValueError("无法从该页面提取有效文章内容，该页面可能需要登录、依赖 JavaScript 渲染或内容较少")

    return ArticleData(
        url=url, domain=domain, title=title, content=content[:15000],
        published=published, author=author,
        word_count=len(content.split()), language=_detect_language(content),
        cover_image=cover_image, source_type=source_type, source_tier=source_tier,
    )
