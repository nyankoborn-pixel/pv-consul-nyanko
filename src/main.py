"""
main.py - オーケストレーター
実行フロー: fetch → score → generate → validate → post → log
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from fetch_news import fetch_all_sources
from score import score_entries
from generate import load_character, generate_post_content, compose_post
from validate import validate_post
from post_x import post_to_x


POSTED_LOG = Path("logs/posted.jsonl")
MAX_RETRIES = 3  # 検証失敗時のリトライ上限(上位候補を順に試す)


def log_post(record: dict):
    """投稿結果をログファイルに追記"""
    POSTED_LOG.parent.mkdir(exist_ok=True)
    with open(POSTED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def try_generate_and_validate(entry: dict, character: dict) -> dict:
    """1件のエントリに対してポスト生成と検証を試みる"""
    gen = generate_post_content(entry, character)
    post = compose_post(entry, gen, character)
    validation = validate_post(post, entry, character)
    return {
        "post": post,
        "generated": gen,
        "validation": validation,
    }


def run(dry_run: bool = False) -> int:
    """
    メイン処理
    dry_run: True の場合、X投稿は行わず結果を出力するのみ
    """
    print(f"=== コンサルにゃんこ PVポスト実行 {datetime.now(timezone.utc).isoformat()} ===")
    
    character = load_character()
    
    # 1. ニュース収集
    entries = fetch_all_sources(max_age_hours=48)
    if not entries:
        print("⚠ No entries fetched. Exiting.")
        return 1
    
    # 2. スコアリング
    scored = score_entries(entries)
    if not scored:
        print("⚠ No scorable entries (all duplicates?). Exiting.")
        return 1
    
    print(f"\n=== Top 5 candidates ===")
    for e in scored[:5]:
        print(f"  [{e['score']:.1f}] [{e['source_name']}] {e['title'][:80]}")
    
    # 3. 上位候補を順に生成・検証(検証失敗時は次候補へ)
    successful_entry = None
    successful_post = None
    
    for i, entry in enumerate(scored[:MAX_RETRIES]):
        print(f"\n--- Attempt {i+1}: {entry['title'][:80]} ---")
        try:
            result = try_generate_and_validate(entry, character)
        except Exception as e:
            print(f"  ⚠ Generation failed: {e}")
            continue
        
        validation = result["validation"]
        print(f"  Validation: {'PASSED' if validation['passed'] else 'FAILED'}")
        
        if not validation["passed"]:
            print(f"    Proper noun violations: {validation['proper_noun']['violations']}")
            print(f"    Char count: {validation['char_count']}")
            print(f"    Forbidden: {validation['forbidden']['violations']}")
            continue
        
        successful_entry = entry
        successful_post = result
        break
    
    if not successful_post:
        print("\n⚠ No valid post could be generated from top candidates. Exiting.")
        return 1
    
    # 4. 投稿
    post_text = successful_post["post"]
    print(f"\n=== Final Post ({len(post_text)} chars) ===")
    print(post_text)
    print("=" * 50)
    
    if dry_run:
        print("\n[DRY RUN] Skipping actual X post.")
        return 0
    
    try:
        result = post_to_x(post_text)
        print(f"\n✓ Posted: {result['url']}")
    except Exception as e:
        print(f"⚠ X post failed: {e}")
        return 1
    
    # 5. ログ記録
    log_post({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "link": successful_entry["link"],
        "source": successful_entry["source_name"],
        "title": successful_entry["title"],
        "score": successful_entry["score"],
        "post_text": post_text,
        "tweet_id": result["tweet_id"],
        "tweet_url": result["url"],
    })
    
    print("\n✓ Done.")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(run(dry_run=dry))
