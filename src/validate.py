"""
validate.py - 生成された投稿の検証
- 文字数チェック(X仕様: URLはt.coで23字に短縮)
- 禁止表現チェック(医療アドバイス・投資誘導など)
- 略語・年号の原文照合(ハルシネーション防止)
- 一般単語、業界解釈、推測表現は許容
"""
import re


# X (Twitter) の URL 短縮ルール
TCO_LENGTH = 23


# ホワイトリスト(原文になくても使ってよい一般PV用語・キャラ用語)
WHITELIST = {
    # 一般的なPV用語
    "PV", "AI", "ICH", "GxP", "GVP", "GCP", "GLP", "GMP",
    "FDA", "EMA", "PMDA", "MHRA", "WHO", "CIOMS", "NMPA", "CDE",
    "ICSR", "PSUR", "PBRER", "DSUR", "RMP",
    "DX", "IT", "API",
    # キャラ関連
    "コンサルにゃんこ",
    # ハッシュタグ用英字(generate.pyで付与するため)
    "Pharmacovigilance", "DrugSafety", "PharmaAI", "AIinPharma",
    "RegulatoryAffairs", "SignalDetection",
}


def extract_acronyms(text: str) -> set:
    """
    2-5文字の大文字略語を抽出(企業名・規制名・製品名の検出)
    """
    pattern = r'\b[A-Z]{2,5}(?:\-?\d{1,2})?\b'
    return set(re.findall(pattern, text))


def extract_years(text: str) -> set:
    """年号(19xx, 20xx)を抽出"""
    pattern = r'\b(?:19|20)\d{2}\b'
    return set(re.findall(pattern, text))


def detect_acronym_violations(generated_text: str, source_text: str) -> list:
    """
    生成文中の略語のうち、原文・ホワイトリストのいずれにも含まれないものを返す。
    これは厳格な violation(リジェクト対象)。
    """
    gen_acronyms = extract_acronyms(generated_text)
    source_lower = source_text.lower()
    violations = []
    for acro in gen_acronyms:
        if acro in WHITELIST:
            continue
        if acro.lower() not in source_lower:
            violations.append(acro)
    return violations


def detect_year_violations(generated_text: str, source_text: str) -> list:
    """
    生成文中の年号で、原文にないものを返す。
    これは厳格な violation(リジェクト対象)。
    """
    gen_years = extract_years(generated_text)
    source_years = extract_years(source_text)
    violations = []
    for year in gen_years:
        if year not in source_years:
            violations.append(year)
    return violations


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
    """禁止表現チェック: 炎上リスク表現のみブロック"""
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
    全検証を実行
    - 文字数: 必須(超過したらリジェクト)
    - 禁止表現: 必須(該当したらリジェクト)
    - 略語の原文照合: 必須(原文にない略語はハルシネーションリスク)
    - 年号の原文照合: 必須(原文にない年号は捏造の可能性)
    """
    source_text = f"{entry['title']} {entry['summary']} {entry['source_name']}"
    body = re.split(r'\n\n#', post)[0]
    
    # 厳格チェック
    acronym_violations = detect_acronym_violations(body, source_text)
    year_violations = detect_year_violations(body, source_text)
    char_ok, char_msg = validate_char_count(post, character["max_chars"])
    forbid_ok, forbid_violations = validate_forbidden_expressions(post, character)
    
    # passed 判定
    proper_noun_ok = (len(acronym_violations) == 0 and len(year_violations) == 0)
    all_ok = char_ok and forbid_ok and proper_noun_ok
    
    return {
        "passed": all_ok,
        "proper_noun": {
            "ok": proper_noun_ok,
            "violations": acronym_violations + year_violations,
            "acronym_violations": acronym_violations,
            "year_violations": year_violations,
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
    # テスト1: 健全な投稿
    test_post1 = "アスピリンは長い歴史を持つが、副作用情報は今も更新されている。\n\n#Pharmacovigilance #AI生成"
    test_entry1 = {
        "title": "アスピリンの使用上の注意改訂",
        "summary": "アスピリンに副作用追加",
        "source_name": "厚労省",
    }
    
    # テスト2: ハルシネーション例(原文にPSURと書かれていないのに使う)
    test_post2 = "韓国の物理研究がRMP/PSURの新潮流を作っている。\n\n#Pharmacovigilance #AI生成"
    test_entry2 = {
        "title": "韓国の2次元磁性研究",
        "summary": "ソウル大学が物理学レビューを掲載",
        "source_name": "ChosunBiz",
    }
    
    character = {"max_chars": 278}
    
    import json
    print("=== Test 1: 健全な投稿 ===")
    print(json.dumps(validate_post(test_post1, test_entry1, character), ensure_ascii=False, indent=2))
    print("\n=== Test 2: ハルシネーション例 ===")
    print(json.dumps(validate_post(test_post2, test_entry2, character), ensure_ascii=False, indent=2))
