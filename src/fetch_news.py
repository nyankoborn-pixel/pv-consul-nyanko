"""
fetch_news.py - RSS feedからPVニュースを収集
- User-Agent付きリクエストでGoogle News RSSのbotブロックを回避
- googlenewsdecoderでGoogle News URLを実記事URLに解決(X OGPカード表示のため)
"""
import feedparser
import yaml
import time
import requests
from datetime import datetime, timezone, timedelta
from dateutil import parser as date_parser
from googlenewsdecoder import gnewsdecoder

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"


def load_sources(config_path: str = "config/sources.yml") -> list:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


def parse_entry_date(entry) -> datetime:
    for key in ("published", "updated", "created"):
        if hasattr(entry, key):
            try:
                return date_parser.parse(getattr(entry, key)).astimezone(timezone.utc)
            except (ValueError, TypeError):
                continue
    return datetime.now(timezone.utc)


def resolve_google_news_url(google_url: str) -> str:
    """
    Google News RSSのリダイレクトURLを実記事URLに解決。
    X側でOGPカード(画像/動画/タイトル)を自動表示させるために必要。
    
    googlenewsdecoder ライブラリを使用。Google News の batchexecute API を
    叩いて Base64 エンコードされた URL をデコードする。
    
    解決失敗時は元URLをそのまま返す(投稿は継続される)。
    Google News URL以外はそのまま返す。
    """
    if not google_url or "news.google.com" not in google_url:
        return google_url
    try:
        # interval=1 で Google API の rate limit (HTTP 429) を回避
        result = gnewsdecoder(google_url, interval=1)
        if result.get("status") and result.get("decoded_url"):
            return result["decoded_url"]
        else:
            print(f"  [resolve] decode failed: {result.get('message', 'unknown')}")
            return google_url
    except Exception as e:
        print(f"  [resolve] exception: {e}")
        return google_url


def fetch_all_sources(max_age_hours: int = 168) -> list:
    sources = load_sources()
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_entries = []
    
    for source in sources:
        print(f"[fetch] {source['name']} ...")
        try:
            resp = requests.get(source["url"], headers={"User-Agent": UA}, timeout=15)
            feed = feedparser.parse(resp.content)
            raw = len(feed.entries)
            
            kept = 0
            for entry in feed.entries[:20]:
                published = parse_entry_date(entry)
                if published < cutoff:
                    continue
                summary = entry.get("summary", "") or entry.get("description", "")
                raw_link = entry.get("link", "")
                resolved_link = resolve_google_news_url(raw_link)
                
                all_entries.append({
                    "title": entry.get("title", "").strip(),
                    "summary": summary.strip()[:1500],
                    "link": resolved_link,
                    "published": published.isoformat(),
                    "source_name": source["name"],
                    "source_weight": source["weight"],
                    "source_category": source["category"],
                })
                kept += 1
            print(f"  raw={raw}, kept={kept}")
        except Exception as e:
            print(f"  Error: {e}")
        time.sleep(0.5)
    
    print(f"[fetch] Total: {len(all_entries)}")
    return all_entries


if __name__ == "__main__":
    for e in fetch_all_sources()[:5]:
        print(f"- [{e['source_name']}] {e['title']}")
        print(f"  {e['link']}")
