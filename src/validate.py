"""
validate.py - 生成された投稿の検証(防御策のコア)
- 固有名詞マッチング: 生成文中の固有名詞が原文にあるか照合
- 文字数チェック(X仕様: URLはt.coで23字に短縮されるためその換算で計算)
- 禁止表現チェック
"""
import re
import yaml


# X (Twitter) の URL 短縮ルール: どんな URL も t.co で 23 文字としてカウントされる
TCO_LENGTH = 23


# 固有名詞候補の正規表現パターン
PROPER_NOUN_PATTERNS = [
    # 英語の大文字始まり2連続以上(会社名、製品名、規制名)
    r'\b[A-Z][a-zA-Z0-9\-]{2,}(?:\s+[A-Z][a-zA-Z0-9\-]+)*\b',
    # 頭字語(FDA, EMA, ICSR, GVP など)
    r'\b[A-Z]{2,}(?:\-\d+)?\b',
    # 数字+単位(mg, mL, %, 日, 年 等)
    r'\d+(?:\.\d+)?\s*(?:mg|ml|mL|%|年|月|日|件)',
    # 年号
    r'\b(?:19|20)\d{2}\b',
]

# ホワイトリスト(PV領域の一般用語で、原文になくても使ってよいもの)
WHITELIST = {
    # 一般的なPV用語(キャラ解説で使える)
    "PV", "AI", "ICH", "GxP", "GVP", "GCP", "GLP", "GMP",
    "FDA", "EMA", "PMDA", "MHRA", "WHO", "CIOMS",
    "ICSR", "PSUR", "PBRER", "DSUR", "RMP",
    # キャラ関連
    "コンサルにゃんこ",
    # ハッシュタグ用英字(generate.pyで付与するため除外)
    "Pharmacovigilance", "DrugSafety", "PharmaAI", "AIinPharma",
    "RegulatoryAffairs", "SignalDetection",
}


def extract_proper_nouns(text: str) -> set:
    """テキストから固有名詞候補を抽出"""
    nouns = set()
    for pattern in PROPER_NOUN_PATTERNS:
        for match in re.finditer(pattern, text):
            nouns.add(match.group(0).strip())
    return nouns


def validate_proper_nouns(generated_text: str, source_text: str) -> tuple:
    """
    生成文中の固有名詞が原文にすべて含まれているか検証
    Returns: (is_valid, list_of_violations)
    """
    gen_nouns = extract_proper_nouns(generated_text)
    source_lower = source_text.lower()
    
    violations = []
    for noun in gen_nouns:
        if noun in WHITELIST:
            continue
        # 原文に(大文字小文字無視で)含まれているかチェック
        if noun.lower() not in source_lower:
            violations.append(noun)
    
    return len(violations) == 0, violations


def calculate_x_length(post: str) -> int:
    """
    X (Twitter) 上での実消費文字数を計算。
    URL は t.co で 23 文字に短縮されるルールに準拠。
    
    例:
      "テスト https://very-long-url.example.com/article/12345"
      → ローカル len() では 50字超
      → X 上では 4(テスト + 半角スペース) + 23(URL) = 27字
    """
    # URLを検出する正規表現(http/httpsで始まる連続する非空白文字)
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, post)
    
    # URL を一旦削除してから残りの文字数を計算し、URL分は固定23字 × URL個数で加算
    text_without_urls = re.sub(url_pattern, '', post)
    return len(text_without_urls) + TCO_LENGTH * len(urls)


def validate_char_count(post: str, max_chars: int = 278) -> tuple:
    """
    X投稿の文字数チェック(t.co短縮を考慮)
    """
    length = calculate_x_length(post)
    if length > max_chars:
        return False, f"Post too long: {length} > {max_chars} (X-counted)"
    if length < 30:
        return False, f"Post too short: {length} (X-counted)"
    return True, None


def validate_forbidden_expressions(post: str, character: dict) -> tuple:
    """禁止表現チェック(最小限の基本パターン)"""
    # 特に医療アドバイス・投資誘導を厳格にブロック
    # 注: 「死亡例」「重篤」などは PV 領域で正当な用語のため、扇情的な使い方のみブロック
    forbidden_patterns = [
        (r'(買[いう]|売[りる])[^。]*株', "投資誘導表現"),
        (r'服用(すべき|しないで|中止)', "医療アドバイス断定"),
        (r'(絶対|必ず)安全', "断定的安全性主張"),
        (r'(絶対|必ず)危険', "断定的危険性主張"),
    ]
    
    violations = []
    for pattern, reason in forbidden_patterns:
        if re.search(pattern, post):
            violations.append(reason)
    
    return len(violations) == 0, violations


def validate_post(post: str, entry: dict, character: dict) -> dict:
    """
    全検証を実行し、結果を返す
    """
    # 原文(タイトル + 要約)を検証用ソースとする
    source_text = f"{entry['title']} {entry['summary']} {entry['source_name']}"
    
    # 固有名詞検証(本文のみ、ハッシュタグ部分は除外)
    # ハッシュタグ以前の部分を抽出
    body = re.split(r'\n\n#', post)[0]
    
    noun_ok, noun_violations = validate_proper_nouns(body, source_text)
    char_ok, char_msg = validate_char_count(post, character["max_chars"])
    forbid_ok, forbid_violations = validate_forbidden_expressions(post, character)
    
    all_ok = noun_ok and char_ok and forbid_ok
    
    return {
        "passed": all_ok,
        "proper_noun": {"ok": noun_ok, "violations": noun_violations},
        "char_count": {
            "ok": char_ok,
            "message": char_msg,
            "length_local": len(post),
            "length_x": calculate_x_length(post),
        },
        "forbidden": {"ok": forbid_ok, "violations": forbid_violations},
    }


if __name__ == "__main__":
    # テスト
    test_post = "FDAが医薬品安全性に関する新しいガイダンスを発表しました。\n\n🐾 重要な動きです\n\n#Pharmacovigilance #AI生成\nhttps://very-long-google-news-url.example.com/articles/CBMiT0FVX31xTE1qX2VKQnFSQ3FnYXkyUm1wM1B3R2ctR21ERXo2QWNENF9hSGRCdDR1az11ajh6SjRCdUpWTk1xUlVWUldVRkliVXBFWlVKT0xWcFNRbk0"
    test_entry = {
        "title": "FDA issues new guidance on drug safety",
        "summary": "The FDA released new guidance.",
        "source_name": "FDA",
    }
    character = {"max_chars": 278}
    result = validate_post(test_post, test_entry, character)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
