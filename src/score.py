"""
score.py - ニュース記事のスコアリング
- ソース重み + キーワード重み + 日付による補正
- マイナス重みのキーワードがあれば実質除外
- 重複(過去投稿済み)も除外
- summary が短すぎる(会員限定記事のリード文のみ)記事を除外
"""
import json
import re
import unicodedata
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dateutil import parser as date_parser

from paths import POSTED_LOG, KEYWORDS_YML

MIN_SUMMARY_LENGTH = 100

# 末尾のソース表記を剥がすためのセパレータ
# NFKC 後は ／→/, ｜→| になるので半角の '-' '|' '/' '—' '–' を対象にする。
_TITLE_TAIL_SEP = re.compile(r"\s*[\-|/—–]\s*[^\-|/—–]+$")


def normalize_title(title: str) -> str:
    """
    タイトル重複判定用の正規化:
    - NFKC 統一 (全角英数→半角、機種依存合字解体)
    - 末尾のソース表記 (" - 日経..." / "／PMDA" 等) を 1 回剥がす
    - 全空白除去・小文字化
    """
    if not title:
        return ""
    s = unicodedata.normalize("NFKC", title)
    s = _TITLE_TAIL_SEP.sub("", s, count=1)
    s = re.sub(r"\s+", "", s)
    return s.lower()


def load_keywords(config_path: str = KEYWORDS_YML) -> list:
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("high_impact", [])


def load_posted_signatures() -> tuple[set, set]:
    """
    過去の投稿履歴を読み込み、(リンク集合, 正規化タイトル集合) を返す。
    Google News の RSS リンクはアクセス毎にパラメータが変わるため、
    タイトル正規化で同記事を検出する 2 段判定にしている。
    """
    if not POSTED_LOG.exists():
        return set(), set()
    links = set()
    titles = set()
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("link"):
                links.add(rec["link"])
            t = rec.get("title", "")
            nt = normalize_title(t)
            if nt:
                titles.add(nt)
    return links, titles


# 後方互換のためエイリアス保持
def load_posted_links() -> set:
    links, _ = load_posted_signatures()
    return links


def calculate_keyword_score(text: str, keywords: list) -> tuple:
    text_lower = text.lower()
    score = 0.0
    matched = []
    for entry in keywords:
        keyword = entry["keyword"]
        weight = entry["weight"]
        if keyword.lower() in text_lower:
            score += weight
            matched.append(keyword)
    return score, matched


def calculate_recency_bonus(published_str: str) -> tuple:
    if not published_str:
        return -10.0, "日付不明"
    try:
        published = date_parser.parse(published_str)
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age_days = (now - published).days
        if age_days <= 7:
            return 5.0, f"{age_days}日前(新鮮)"
        elif age_days <= 30:
            return 0.0, f"{age_days}日前"
        elif age_days <= 90:
            return -5.0, f"{age_days}日前(やや古い)"
        elif age_days <= 365:
            return -15.0, f"{age_days}日前(古い)"
        else:
            return -30.0, f"{age_days}日前(実質除外)"
    except (ValueError, TypeError):
        return -10.0, "日付パース失敗"


def is_summary_too_short(entry: dict) -> bool:
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    combined = f"{title} {summary}".strip()
    return len(combined) < MIN_SUMMARY_LENGTH


def score_entries(entries: list, config_path: str = KEYWORDS_YML) -> list:
    keywords = load_keywords(config_path)
    posted_links, posted_titles = load_posted_signatures()

    scored = []
    excluded_count = {
        "posted_link": 0,
        "posted_title": 0,
        "negative_score": 0,
        "too_old": 0,
        "too_short": 0,
    }

    for entry in entries:
        link = entry.get("link", "")
        if link in posted_links:
            excluded_count["posted_link"] += 1
            continue

        norm_title = normalize_title(entry.get("title", ""))
        if norm_title and norm_title in posted_titles:
            excluded_count["posted_title"] += 1
            continue

        if is_summary_too_short(entry):
            excluded_count["too_short"] += 1
            continue

        source_weight = float(entry.get("source_weight", 5))
        text = f"{entry.get('title', '')} {entry.get('summary', '')}"
        kw_score, matched = calculate_keyword_score(text, keywords)

        published = entry.get("published", "")
        recency_bonus, age_label = calculate_recency_bonus(published)

        total = source_weight + kw_score + recency_bonus

        if recency_bonus <= -25:
            excluded_count["too_old"] += 1
            continue

        if total < 0:
            excluded_count["negative_score"] += 1
            continue

        entry_scored = dict(entry)
        entry_scored["score"] = total
        entry_scored["source_weight"] = source_weight
        entry_scored["keyword_score"] = kw_score
        entry_scored["recency_bonus"] = recency_bonus
        entry_scored["matched_keywords"] = matched
        entry_scored["age_label"] = age_label
        scored.append(entry_scored)

    scored.sort(key=lambda x: x["score"], reverse=True)

    print(f"[score] Scored: {len(scored)} entries")
    print(
        f"[score] Excluded: posted_link={excluded_count['posted_link']}, "
        f"posted_title={excluded_count['posted_title']}, "
        f"negative_score={excluded_count['negative_score']}, "
        f"too_old={excluded_count['too_old']}, "
        f"too_short={excluded_count['too_short']}"
    )

    return scored


if __name__ == "__main__":
    print("score module loaded.")
