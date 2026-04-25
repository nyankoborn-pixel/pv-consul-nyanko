"""
validate.py - 生成された投稿の検証
- 文字数チェック(X仕様: URLはt.coで23字に短縮されるためその換算で計算)
- 禁止表現チェック(医療アドバイス・投資誘導など炎上リスク表現のブロック)
- 固有名詞マッチングは警告のみ(新方針: コンサル目線の解釈・推測を許容)
"""
import re


# X (Twitter) の URL 短縮ルール
TCO_LENGTH = 23


# 固有名詞候補の正規表現パターン(警告ログ用、ブロックには使わない)
PROPER_NOUN_PATTERNS = [
    r'\b[A-Z][a-zA-Z0-9\-]{2,}(?:\s+[A-Z][a-zA-Z0-9\-]+)*\b',
    r'\b[A-Z]{2,}(?:\-\d+)?\b',
    r'\d+(?:\.\d+)?\s*(?:mg|ml|mL|%|年|月|日|件)',
    r'\b(?:19|20)\d{2}\b',
]


def extract_proper_nouns(text: str) -> set:
    nouns = set()
    for pattern in PROPER_NOUN_PATTERNS:
        for match in re.finditer(pattern, text):
            nouns.add(match.group(0).strip())
    return nouns


def detect_proper_noun_mismatches(generated_text: str, source_text: str) -> list:
    """
    生成文中の固有名詞のうち、原文に存在しないものを返す(警告用、ブロックしない)
    """
    gen_nouns = extract_proper_nouns(generated_text)
    source_lower = source_text.lower()
    mismatches = []
    for noun in gen_nouns:
        if noun.lower() not in source_lower:
            mismatches.append(noun)
    return mismatches


def calculate_x_length(post: str) -> int:
    """X 上での実消費文字数(URL は t.co で 23 字に短縮)"""
    url_pattern = r'https?://\S+'
    urls = re.findall(url_pattern, post)
    text_without_urls = re.sub(url_pattern, '', post)
    return len(text_without_urls) + TCO_LENGTH * len(urls)


def validate_char_count(post: str, max_chars: int = 278) -> tuple:
    length = calculate_x_length(post)
    if length > max_chars:
        return False, f"Post too long: {length} > {max_chars} (X-counted)"
    if length < 30:
        return False, f"Post too short: {length} (X-counted)"
    return True, None


def validate_forbidden_expressions(post: str, character: dict) -> tuple:
    """
    禁止表現チェック: 炎上リスクの高い表現のみブロック
    - 医療アドバイス断定(服用すべき等)
    - 投資誘導(株を買う等)
    - 絶対安全/絶対危険の断定
    """
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
    - 文字数: 必須(超過したらリジェクト)
    - 禁止表現: 必須(該当したらリジェクト)
    - 固有名詞: 警告のみ(リジェクトしない)
    """
    source_text = f"{entry['title']} {entry['summary']} {entry['source_name']}"
    body = re.split(r'\n\n#', post)[0]
    
    # 固有名詞は警告のみ(passed の判定には影響しない)
    noun_mismatches = detect_proper_noun_mismatches(body, source_text)
    
    char_ok, char_msg = validate_char_count(post, character["max_chars"])
    forbid_ok, forbid_violations = validate_forbidden_expressions(post, character)
    
    # passed 判定: 文字数 + 禁止表現のみが必須
    all_ok = char_ok and forbid_ok
    
    return {
        "passed": all_ok,
        "proper_noun": {
            "ok": True,  # 警告のみのため常に True
            "mismatches_warning": noun_mismatches,
            "violations": [],  # 後方互換のため空リストを残す
        },
        "char_count": {
            "ok": char_ok,
            "message": char_msg,
            "length_local": len(post),
            "length_x": calculate_x_length(post),
        },
        "forbidden": {"ok": forbid_ok, "violations": forbid_violations},
    }


if __name__ == "__main__":
    test_post = "アスピリンは100年以上の歴史を持つが、副作用情報は今も更新されている。\n\n#Pharmacovigilance #DrugSafety #AI生成"
    test_entry = {
        "title": "アスピリンの使用上の注意改訂",
        "summary": "アスピリンに副作用追加",
        "source_name": "厚労省",
    }
    character = {"max_chars": 278}
    result = validate_post(test_post, test_entry, character)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
