"""
GISTER Trending Velocity Tracker
==================================
记录每次抓取的关键词频率到 SQLite，计算真实的"飙升速度"。

原理：
  velocity(kw, t) = freq(kw, last_1h) / (freq(kw, last_24h) + ε)
  值 > 1 表示近 1h 比昨天同期更热；值越大飙升越快。

用法：
  # 每次抓取后自动调用（记录 + 返回当前热词）
  from scripts.trending import record_and_score

  # 独立查询当前热词
  python3 scripts/trending.py --top 20
"""

import argparse
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

DB_PATH = Path("data/trending.db")

HIGH_VALUE_KEYWORDS = {
    # 英文
    "ai", "llm", "gpt", "claude", "gemini", "openai", "deepmind", "anthropic",
    "agent", "model", "benchmark", "dataset", "research", "paper",
    "launch", "release", "funding", "acquisition", "ipo", "regulation", "policy",
    "neural", "transformer", "diffusion", "robotics", "chip", "semiconductor",
    "quantum", "open source", "autonomous", "startup", "breach", "hack",
    # 中文
    "人工智能", "大模型", "智能体", "发布", "研究", "政策", "监管",
    "融资", "收购", "开源", "芯片", "突破", "算法", "数据", "安全",
}


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keyword_freq (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword   TEXT    NOT NULL,
            source    TEXT    NOT NULL,
            count     INTEGER NOT NULL DEFAULT 1,
            recorded_at TEXT  NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_kw_time ON keyword_freq(keyword, recorded_at)")
    conn.commit()


def _extract_keywords(text: str) -> list[str]:
    words = set(re.findall(r"\b[a-z\u4e00-\u9fff]{2,}\b", str(text).lower()))
    return list(words & HIGH_VALUE_KEYWORDS)


def record_batch(titles: list[str], sources: list[str]):
    """将一批文章的关键词频率写入 DB。每次抓取后调用一次。"""
    DB_PATH.parent.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).isoformat()

    freq: dict[tuple[str, str], int] = {}
    for title, source in zip(titles, sources):
        for kw in _extract_keywords(title):
            key = (kw, source)
            freq[key] = freq.get(key, 0) + 1

    with sqlite3.connect(DB_PATH) as conn:
        _init_db(conn)
        conn.executemany(
            "INSERT INTO keyword_freq(keyword, source, count, recorded_at) VALUES(?,?,?,?)",
            [(kw, src, cnt, now) for (kw, src), cnt in freq.items()]
        )
        conn.commit()

    print(f"[trending] 记录 {len(freq)} 条关键词频率 @ {now[:16]}", flush=True)


def get_velocity_scores(titles: list[str], sources: list[str]) -> list[float]:
    """
    计算每篇文章标题关键词的飙升速度分。
    velocity = log(1 + freq_1h) / log(1 + freq_24h)
    返回 0-1 之间的分数列表。
    """
    if not DB_PATH.exists():
        return [0.3] * len(titles)

    now = datetime.now(timezone.utc)
    t_1h  = (now - timedelta(hours=1)).isoformat()
    t_24h = (now - timedelta(hours=24)).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        _init_db(conn)

        # 过去 1h 各关键词总频率
        freq_1h = dict(conn.execute(
            "SELECT keyword, SUM(count) FROM keyword_freq WHERE recorded_at > ? GROUP BY keyword",
            (t_1h,)
        ).fetchall())

        # 过去 24h 各关键词总频率
        freq_24h = dict(conn.execute(
            "SELECT keyword, SUM(count) FROM keyword_freq WHERE recorded_at > ? GROUP BY keyword",
            (t_24h,)
        ).fetchall())

    import math
    # 判断是否有足够历史数据（24h 内有 baseline）
    has_history = bool(freq_24h)

    # 归一化用的最大频率（避免绝对值模式下溢出）
    max_freq_1h  = max(freq_1h.values(),  default=1)
    max_freq_24h = max(freq_24h.values(), default=1)

    scores = []
    for title in titles:
        kws = _extract_keywords(title)
        if not kws:
            scores.append(0.1)
            continue

        max_vel = 0.0
        for kw in kws:
            f1  = freq_1h.get(kw, 0)
            f24 = freq_24h.get(kw, 0)

            if has_history and f24 > 0:
                # 真实飙升速度：近1h 相对 24h 基线的增长比
                vel = math.log1p(f1) / math.log1p(f24)
                vel = min(vel / 3.0, 1.0)  # 3x 增长 = 满分
            else:
                # 无历史数据：用绝对频率归一化（出现越多 = 越热）
                vel = math.log1p(f1) / math.log1p(max_freq_1h + 1)

            max_vel = max(max_vel, vel)
        scores.append(round(min(max_vel, 1.0), 4))

    return scores


def get_top_trending(top_n: int = 20, window_hours: int = 6) -> pd.DataFrame:
    """返回过去 window_hours 内飙升最快的热词排行。"""
    if not DB_PATH.exists():
        print("⚠ 尚无趋势数据，请先运行 fetch_samples.py 至少两次。")
        return pd.DataFrame()

    now = datetime.now(timezone.utc)
    t_window = (now - timedelta(hours=window_hours)).isoformat()
    t_prev   = (now - timedelta(hours=window_hours * 4)).isoformat()  # 对比基准：4倍窗口之前

    with sqlite3.connect(DB_PATH) as conn:
        _init_db(conn)

        recent = dict(conn.execute(
            "SELECT keyword, SUM(count) FROM keyword_freq WHERE recorded_at > ? GROUP BY keyword",
            (t_window,)
        ).fetchall())

        baseline = dict(conn.execute(
            "SELECT keyword, SUM(count) FROM keyword_freq "
            "WHERE recorded_at > ? AND recorded_at <= ? GROUP BY keyword",
            (t_prev, t_window)
        ).fetchall())

    import math
    has_history = any(v > 0 for v in baseline.values()) if baseline else False
    max_recent = max(recent.values(), default=1)

    rows = []
    for kw, cnt in recent.items():
        base = baseline.get(kw, 0)
        if has_history and base > 0:
            # 真实飙升速度
            velocity = math.log1p(cnt) / math.log1p(base)
        else:
            # 无历史：按绝对频率归一化
            velocity = math.log1p(cnt) / math.log1p(max_recent + 1)
        rows.append({
            "keyword": kw,
            "recent_count": cnt,
            "baseline_count": base,
            "velocity": round(velocity, 3),
            "mode": "realtime" if (has_history and base > 0) else "absolute",
        })

    df = pd.DataFrame(rows).sort_values("velocity", ascending=False).head(top_n)
    return df.reset_index(drop=True)


def record_from_csv(csv_path: str):
    """从已有的 CSV 文件中读取标题和来源，写入 trending DB。"""
    df = pd.read_csv(csv_path)
    titles  = df["title"].fillna("").tolist()
    sources = df["source_name"].fillna("").tolist()
    record_batch(titles, sources)
    print(f"[trending] 从 {csv_path} 导入 {len(titles)} 条记录完成")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GISTER Trending Velocity Tracker")
    parser.add_argument("--top",    type=int, default=20, help="显示前 N 个热词")
    parser.add_argument("--window", type=int, default=6,  help="统计窗口小时数")
    parser.add_argument("--record", type=str, default=None, help="从指定 CSV 导入记录")
    args = parser.parse_args()

    if args.record:
        record_from_csv(args.record)

    print(f"\n📈 过去 {args.window}h 飙升最快的热词 TOP {args.top}:")
    df = get_top_trending(args.top, args.window)
    if not df.empty:
        print(df.to_string(index=False))
    else:
        print("  (数据不足，需要多次抓取后才能计算趋势)")
