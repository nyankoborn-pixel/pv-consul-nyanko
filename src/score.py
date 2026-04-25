"""
score.py - ニュース記事のスコアリング
- ソース重み + キーワード重み + 日付による補正
- マイナス重みのキーワードがあれば実質除外
- 重複(過去投稿済み)も除外
"""
import json
import re
import yaml
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dateutil import parser as date_parser

POSTED_LOG = Path("logs/posted.jsonl")


def load_keywords(config_path: str = "config/keywords.yml") -> list:
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("high_impact", [])


def load_posted_links() -> set:
    """過去に投稿済みの記事リンクを集合で返す(重複防止)"""
    if not POSTED_LOG.exists():
        return set()
    links = set()
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                rec = json.loads(line)
                if "link" in rec:
                    links.add(rec["link"])
            except json.JSONDecodeError:
                continue
    return links


def calculate_keyword_score(text: str, keywords: list) -> tuple:
    """
    キーワード重みを合算してスコア計算
    マイナス重みは「除外信号」として機能(合計に含める)
    Returns: (score, matched_keywords)
    """
    text_lower = text.lower()
    score = 0.0
    matched = []
    
    for entry in keywords:
        keyword = entry["keyword"]
        weight = entry["weight"]
        
        # 大文字小文字無視
        if keyword.lower() in text_lower:
            score += weight
            matched.append(keyword)
    
    return score, matched


def calculate_recency_bonus(published_str: str) -> tuple:
    """
    記事の新しさによる補正
    Returns: (bonus_score, age_label)
    
    7日以内:    +5  (新鮮)
    7-30日:    +0  (基準)
    30-90日:   -5  (やや古い)
    90-365日:  -15 (古い)
    365日超:   -30 (実質除外)
    日付不明:  -10 (古い扱いだが完全除外はしない)
    """
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
    
    except (ValueError, TypeError) as e:
        return -10.0, f"日付パース失敗"


def score_entries(entries: list, config_path: str = "config/keywords.yml") -> list:
    """
    エントリ一覧をスコアリングして降順ソートで返す。
    マイナススコアの記事は除外。
    過去投稿済みの記事も除外。
    """
    keywords = load_keywords(config_path)
    posted_links = load_posted_links()
    
    scored = []
    excluded_count = {"posted": 0, "negative_score": 0, "too_old": 0}
    
    for entry in entries:
        # 重複チェック
        link = entry.get("link", "")
        if link in posted_links:
            excluded_count["posted"] += 1
            continue
        
        # ソース重み
        source_weight = float(entry.get("source_weight", 5))
        
        # キーワードスコア
        text = f"{entry.get('title', '')} {entry.get('summary', '')}"
        kw_score, matched = calculate_keyword_score(text, keywords)
        
        # 日付補正
        published = entry.get("published", "")
        recency_bonus, age_label = calculate_recency_bonus(published)
        
        # 合計スコア
        total = source_weight + kw_score + recency_bonus
        
        # 経年で除外
        if recency_bonus <= -25:
            excluded_count["too_old"] += 1
            continue
        
        # マイナススコア(除外キーワード優位)で除外
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
    
    # スコア降順ソート
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"[score] Scored: {len(scored)} entries")
    print(f"[score] Excluded: posted={excluded_count['posted']}, "
          f"negative_score={excluded_count['negative_score']}, "
          f"too_old={excluded_count['too_old']}")
    
    return scored


if __name__ == "__main__":
    print("score module loaded.")
