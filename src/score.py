"""
score.py - 記事の話題性をスコアリング
スコア = ソース重み + キーワード重み合計 + 新しさボーナス
"""
import yaml
import json
import re
from datetime import datetime, timezone
from dateutil import parser as date_parser
from pathlib import Path


POSTED_LOG = Path("logs/posted.jsonl")


def load_keywords(config_path: str = "config/keywords.yml") -> list:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["high_impact"]


def load_posted_links() -> set:
    """既に投稿済みの記事URLを読み込み、重複投稿を防ぐ"""
    if not POSTED_LOG.exists():
        return set()
    links = set()
    with open(POSTED_LOG, "r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
                if "link" in record:
                    links.add(record["link"])
            except json.JSONDecodeError:
                continue
    return links


def calculate_keyword_score(text: str, keywords: list) -> tuple:
    """テキスト中のキーワード出現からスコアを計算。(score, matched_keywords)を返す"""
    text_lower = text.lower()
    total_score = 0
    matched = []
    for kw in keywords:
        keyword = kw["keyword"].lower()
        # 単語境界を考慮(日本語は単純包含、英語は word boundary)
        if re.search(r'[a-zA-Z]', keyword):
            pattern = r'\b' + re.escape(keyword) + r'\b'
            if re.search(pattern, text_lower):
                total_score += kw["weight"]
                matched.append(kw["keyword"])
        else:
            if keyword in text_lower:
                total_score += kw["weight"]
                matched.append(kw["keyword"])
    return total_score, matched


def calculate_freshness_bonus(published_iso: str) -> float:
    """24時間以内なら+5, 48時間以内なら+2, それ以上は0"""
    try:
        published = date_parser.parse(published_iso).astimezone(timezone.utc)
        age_hours = (datetime.now(timezone.utc) - published).total_seconds() / 3600
        if age_hours <= 24:
            return 5
        elif age_hours <= 48:
            return 2
        return 0
    except (ValueError, TypeError):
        return 0


def score_entries(entries: list) -> list:
    """全エントリをスコアリングし、スコア降順でソート"""
    keywords = load_keywords()
    posted_links = load_posted_links()
    
    scored = []
    for entry in entries:
        # 重複チェック
        if entry["link"] in posted_links:
            continue
        
        text = f"{entry['title']} {entry['summary']}"
        kw_score, matched = calculate_keyword_score(text, keywords)
        fresh_bonus = calculate_freshness_bonus(entry["published"])
        
        total = entry["source_weight"] + kw_score + fresh_bonus
        
        scored.append({
            **entry,
            "score": total,
            "score_breakdown": {
                "source": entry["source_weight"],
                "keywords": kw_score,
                "freshness": fresh_bonus,
            },
            "matched_keywords": matched,
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


if __name__ == "__main__":
    from fetch_news import fetch_all_sources
    entries = fetch_all_sources()
    scored = score_entries(entries)
    print("\n=== Top 5 ===")
    for e in scored[:5]:
        print(f"[{e['score']:.1f}] [{e['source_name']}] {e['title']}")
        print(f"  keywords: {e['matched_keywords']}")
