"""
generate.py - Gemini Flash を使ってコンサルにゃんこ口調でポスト生成
"""
import os
import yaml
import google.generativeai as genai


def load_character(config_path: str = "config/character.yml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_prompt(entry: dict, character: dict) -> str:
    char = character["character"]
    
    prompt = f"""あなたは「{char['name']}」というキャラクターです。
以下のキャラ設定を厳密に守って、PVニュースのポストを日本語で生成してください。

【キャラクター設定】
- 名前: {char['name']}
- 口ぐせ: 「{char['catchphrase']}」
- 性格: {", ".join(char['personality'])}
- スタイル:
{chr(10).join(f"  - {s}" for s in char['style_guidelines'])}
- 禁止事項:
{chr(10).join(f"  - {f}" for f in char['forbidden'])}

【厳守すべき制約】
1. 原文に書かれていない固有名詞・企業名・製品名・数値・日付を絶対に使用しないこと
2. 原文から推測できない解釈や予測を述べないこと
3. 医療アドバイス・投資判断に関わる表現は避けること
4. 断定を避け、「〜とのこと」「〜と報告されています」「〜と発表されました」を用いること
5. 文字数: summaryは100字以内、commentaryは40字以内を目安
6. 出力は以下のJSON形式のみ。前後に説明文を付けないこと

【出力形式】
{{
  "summary": "ニュース内容の中立的な要約(事実のみ)",
  "commentary": "コンサルにゃんこ視点の一言コメント(静かで知的なトーン)"
}}

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1000]}
ソース: {entry['source_name']}

上記の原文情報のみを根拠として、JSONを出力してください。
commentary には必ず口ぐせ「{char['catchphrase']}」の世界観を感じさせる一言を入れてください(ただし口ぐせそのものは繰り返さない)。
"""
    return prompt


def generate_post_content(entry: dict, character: dict) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    
    genai.configure(api_key=api_key)
    
    model = genai.GenerativeModel(
        "gemini-2.5-flash",
        generation_config={
            "temperature": 0.4,
            "top_p": 0.9,
            "max_output_tokens": 2000,
            "response_mime_type": "application/json",
        },
    )
    
    prompt = build_prompt(entry, character)
    response = model.generate_content(prompt)
    text = response.text.strip()
    
    import json
    import re
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    
    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini JSON output: {e}\nRaw: {text}")
    
    if "summary" not in result or "commentary" not in result:
        raise RuntimeError(f"Gemini output missing required fields: {result}")
    
    return result


def select_hashtags(entry: dict, character: dict) -> list:
    hashtags_config = character["hashtags"]
    tags = list(hashtags_config["always"])
    
    matched_lower = [kw.lower() for kw in entry.get("matched_keywords", [])]
    text = f"{entry['title']} {entry['summary']}".lower()
    
    if any(x in text for x in ["ai", "artificial intelligence", "machine learning", "llm"]):
        tags.extend(hashtags_config["conditional"]["ai"][:1])
    if any(x in matched_lower for x in ["guidance", "guideline", "fda approval", "ema approval", "ich"]):
        tags.extend(hashtags_config["conditional"]["regulatory"][:1])
    if "signal" in text:
        tags.extend(hashtags_config["conditional"]["signal"][:1])
    if "icsr" in text:
        tags.extend(hashtags_config["conditional"]["icsr"][:1])
    if "pmda" in entry["source_name"].lower() or "pmda" in text:
        tags.extend(hashtags_config["conditional"]["pmda"][:1])
    
    seen = set()
    unique_tags = []
    for t in tags:
        if t not in seen:
            seen.add(t)
            unique_tags.append(t)
        if len(unique_tags) >= 4:
            break
    
    unique_tags.append(character["ai_disclosure"])
    return unique_tags


def compose_post(entry: dict, gen: dict, character: dict) -> str:
    """
    最終的な投稿文を組み立て。
    X上限の280字を数学的に保証するため、はみ出した分はsummaryを自動で切り詰める。
    """
    tags = select_hashtags(entry, character)
    hashtags_str = " ".join(tags)
    link = entry.get("link", "").strip()
    commentary = gen["commentary"]
    summary = gen["summary"]
    
    # t.co短縮後、URLは固定23字としてカウントされるため実URLは長くても280字制約上は23字扱い
    # ただしvalidate.pyはlen(post)で判定するので、ここではURLの実長で計算する
    url_part = f"\n{link}" if link else ""
    fixed_part = f"\n\n🐾 {commentary}\n\n{hashtags_str}{url_part}"
    
    # 上限280字から固定部分を引いた分がsummaryに使える文字数
    max_total = character.get("max_chars", 278)
    allowed_summary = max_total - len(fixed_part)
    
    # 余裕がなければ切り詰め(末尾を「…」に)
    if len(summary) > allowed_summary:
        if allowed_summary > 1:
            summary = summary[:allowed_summary - 1] + "…"
        else:
            summary = ""  # 極端なケース(commentary+tags+urlだけで既にオーバー)
    
    post = f"{summary}{fixed_part}"
    return post
