"""
main.py - オーケストレーター
フロー: fetch → score → generate(text+image_prompt) → validate → 
       generate_image → post(parent with image) → post_reply(source URL) → log

PV関連性判定により無関係な記事はスキップして次の候補に進む。
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fetch_news import fetch_all_sources
from score import score_entries
from generate import (
    load_character,
    generate_post_content,
    compose_post,
    generate_image,
    PVNotRelatedError,
)
from validate import validate_post
from post_x import post_to_x, post_reply


POSTED_LOG = Path("logs/posted.jsonl")
MAX_RETRIES = 15  # PV無関係スキップが増える可能性があるため拡大
REPLY_DELAY_SEC = 5


def log_post(record: dict):
    POSTED_LOG.parent.mkdir(exist_ok=True)
    with open(POSTED_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def try_generate_and_validate(entry: dict, character: dict) -> dict:
    """1件のエントリに対してテキスト生成と検証を試みる"""
    gen = generate_post_content(entry, character)
    post = compose_post(entry, gen, character)
    validation = validate_post(post, entry, character)
    return {
        "post": post,
        "generated": gen,
        "validation": validation,
    }


def run(dry_run: bool = False) -> int:
    print(f"=== コンサルにゃんこ PVポスト実行 {datetime.now(timezone.utc).isoformat()} ===")
    
    character = load_character()
    
    # 1. ニュース収集
    entries = fetch_all_sources()
    if not entries:
        print("⚠ No entries fetched. Exiting.")
        return 1
    
    # 2. スコアリング
    scored = score_entries(entries)
    if not scored:
        print("⚠ No scorable entries. Exiting.")
        return 1
    
    print(f"\n=== Top {MAX_RETRIES} candidates ===")
    for e in scored[:MAX_RETRIES]:
        print(f"  [{e['score']:.1f}] [{e['source_name']}] {e['title'][:80]}")
    
    # 3. 上位候補で生成・検証
    successful_entry = None
    successful_post = None
    skip_count = 0
    
    for i, entry in enumerate(scored[:MAX_RETRIES]):
        print(f"\n--- Attempt {i+1}: {entry['title'][:80]} ---")
        try:
            result = try_generate_and_validate(entry, character)
        except PVNotRelatedError as e:
            print(f"  ⊘ Skipped (PV無関係): {e}")
            skip_count += 1
            continue
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
        print(f"\n⚠ No valid post could be generated. Skipped(PV無関係)={skip_count}件. Exiting.")
        return 1
    
    post_text = successful_post["post"]
    image_prompt = successful_post["generated"].get("image_prompt", "")
    source_url = successful_entry.get("link", "").strip()
    
    print(f"\n=== Final Post ({len(post_text)} chars) ===")
    print(post_text)
    print(f"\n=== Image prompt ===")
    print(image_prompt)
    print(f"\n=== Source URL ===")
    print(source_url)
    print("=" * 50)
    
    # 4. 画像生成
    image_path = None
    if image_prompt:
        print("\n[image] Generating...")
        image_path = generate_image(image_prompt)
        if image_path:
            print(f"[image] Generated: {image_path}")
        else:
            print("[image] Failed, will post text-only")
    
    if dry_run:
        print("\n[DRY RUN] Skipping actual X post.")
        return 0
    
    # 5. 親ポストを投稿
    try:
        result = post_to_x(post_text, image_path=image_path)
        parent_id = result["tweet_id"]
        print(f"\n✓ Parent posted: {result['url']} (image={result['has_image']})")
    except Exception as e:
        print(f"⚠ Parent post failed: {e}")
        return 1
    
    # 6. 自リプライ投稿
    reply_result = None
    if source_url:
        time.sleep(REPLY_DELAY_SEC)
        reply_text = f"Read more:\n{source_url}"
        try:
            reply_result = post_reply(parent_id, reply_text)
            print(f"✓ Reply posted: {reply_result['url']}")
        except Exception as e:
            print(f"⚠ Reply post failed (parent post is fine): {e}")
    
    # 7. ログ記録
    log_post({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "link": successful_entry["link"],
        "source": successful_entry["source_name"],
        "title": successful_entry["title"],
        "score": successful_entry["score"],
        "category": successful_post["generated"].get("_category"),
        "post_text": post_text,
        "image_prompt": image_prompt,
        "had_image": bool(image_path),
        "skipped_pv_unrelated": skip_count,
        "parent_tweet_id": parent_id,
        "parent_tweet_url": result["url"],
        "reply_tweet_id": reply_result["tweet_id"] if reply_result else None,
        "reply_tweet_url": reply_result["url"] if reply_result else None,
    })
    
    print("\n✓ Done.")
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    sys.exit(run(dry_run=dry))
