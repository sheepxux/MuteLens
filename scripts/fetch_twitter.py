"""单独抓取 Twitter/X KOL 推文，生成 twitter_samples.csv"""
import requests
import feedparser
import hashlib
import csv
import time
from bs4 import BeautifulSoup

TWITTER_ACCOUNTS = [
    "sama", "karpathy", "ylecun", "GaryMarcus",
    "benedictevans", "paulg", "naval", "balajis",
    "elonmusk", "satyanadella",
]

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
OUTPUT = "twitter_samples.csv"
TIMEOUT = 8

rows = []

def try_fetch(acc: str) -> list[dict]:
    for base in NITTER_INSTANCES:
        url = f"{base}/{acc}/rss"
        print(f"  试 {url} ...", flush=True)
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=TIMEOUT)
            if r.status_code != 200:
                print(f"    status={r.status_code}, 跳过", flush=True)
                continue
            feed = feedparser.parse(r.text)
            if not feed.entries:
                print(f"    0 条 entry，跳过", flush=True)
                continue
            result = []
            for e in feed.entries[:20]:
                link = getattr(e, "link", "") or getattr(e, "id", "")
                title = BeautifulSoup(getattr(e, "title", ""), "html.parser").get_text().strip()
                summary = BeautifulSoup(getattr(e, "summary", ""), "html.parser").get_text().strip()
                content = summary or title
                if len(content) < 10:
                    continue
                result.append({
                    "id": hashlib.md5(link.encode()).hexdigest(),
                    "source_name": f"Twitter @{acc}",
                    "source_tier": "high",
                    "source_type": "social_twitter",
                    "lang": "en",
                    "title": title,
                    "url": link,
                    "content": content[:500],
                    "label": "",
                })
            print(f"    ✓ {len(result)} 条有效", flush=True)
            return result
        except Exception as ex:
            print(f"    ✗ {ex}", flush=True)
    return []

for acc in TWITTER_ACCOUNTS:
    print(f"→ @{acc}", flush=True)
    fetched = try_fetch(acc)
    rows.extend(fetched)
    time.sleep(0.5)

print(f"\n共 {len(rows)} 条，写入 {OUTPUT}", flush=True)

if rows:
    with open(OUTPUT, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)
    print("✅ 完成", flush=True)
else:
    print("⚠ 没有抓到任何内容", flush=True)
