"""
validate.py - 生成された投稿の検証(防御策のコア)
- 固有名詞マッチング: 生成文中の固有名詞が原文にあるか照合
- 文字数チェック
- 禁止表現チェック
"""
import re
import yaml


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


def validate_char_count(post: str, max_chars: int = 270) -> tuple:
    """X投稿の文字数チェック"""
    # URLは t.co で短縮されるが、今回URLは含めないので素直にlen
    length = len(post)
    if length > max_chars:
        return False, f"Post too long: {length} > {max_chars}"
    if length < 30:
        return False, f"Post too short: {length}"
    return True, None


def validate_forbidden_expressions(post: str, character: dict) -> tuple:
    """禁止表現チェック(最小限の基本パターン)"""
    # 特に医療アドバイス・投資誘導を厳格にブロック
    forbidden_patterns = [
        (r'(買[いう]|売[りる])[^。]*株', "投資誘導表現"),
        (r'服用(すべき|しないで|中止)', "医療アドバイス断定"),
        (r'(絶対|必ず)安全', "断定的安全性主張"),
        (r'(絶対|必ず)危険', "断定的危険性主張"),
        (r'(死亡|死ぬ|殺[すし])', "扇情的表現"),
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
        "char_count": {"ok": char_ok, "message": char_msg, "length": len(post)},
        "forbidden": {"ok": forbid_ok, "violations": forbid_violations},
    }


if __name__ == "__main__":
    # テスト
    test_post = "FDAが医薬品安全性に関する新しいガイダンスを発表しました。\n\n🐾 Pfizer社の重要な動きです\n\n#Pharmacovigilance #AI生成"
    test_entry = {
        "title": "FDA issues new guidance on drug safety",
        "summary": "The FDA released new guidance.",
        "source_name": "FDA",
    }
    character = {"max_chars": 270}
    result = validate_post(test_post, test_entry, character)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
