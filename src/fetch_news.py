"""
fetch_news.py - RSS feedからPVニュースを収集
"""
import feedparser
import yaml
import time
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from pathlib import Path


def load_sources(config_path: str = "config/sources.yml") -> list:
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["sources"]


def parse_entry_date(entry) -> datetime:
    """RSSエントリから公開日時をパース。失敗時は現在時刻を返す。"""
    for key in ("published", "updated", "created"):
        if hasattr(entry, key):
            try:
                return date_parser.parse(getattr(entry, key)).astimezone(timezone.utc)
            except (ValueError, TypeError):
                continue
    return datetime.now(timezone.utc)


def fetch_all_sources(max_age_hours: int = 48) -> list:
    """
    全ソースから記事を取得。max_age_hours以内のもののみ返す。
    """
    sources = load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_entries = []
    
    for source in sources:
        print(f"[fetch] {source['name']} ...")
        try:
            feed = feedparser.parse(source["url"])
            if feed.bozo and not feed.entries:
                print(f"  ⚠ Failed to parse: {source['url']}")
                continue
            
            for entry in feed.entries[:20]:  # 各ソース上位20件まで
                published = parse_entry_date(entry)
                if published < cutoff:
                    continue
                
                summary = ""
                if hasattr(entry, "summary"):
                    summary = entry.summary
                elif hasattr(entry, "description"):
                    summary = entry.description
                
                all_entries.append({
                    "title": entry.get("title", "").strip(),
                    "summary": summary.strip()[:1500],  # 長すぎる要約は制限
                    "link": entry.get("link", ""),
                    "published": published.isoformat(),
                    "source_name": source["name"],
                    "source_weight": source["weight"],
                    "source_category": source["category"],
                })
            print(f"  ✓ {len([e for e in feed.entries[:20] if parse_entry_date(e) >= cutoff])} recent entries")
        except Exception as e:
            print(f"  ⚠ Error fetching {source['name']}: {e}")
            continue
        
        time.sleep(0.5)  # ソース間の待機
    
    print(f"[fetch] Total recent entries: {len(all_entries)}")
    return all_entries


if __name__ == "__main__":
    entries = fetch_all_sources()
    for e in entries[:5]:
        print(f"- [{e['source_name']}] {e['title']}")
