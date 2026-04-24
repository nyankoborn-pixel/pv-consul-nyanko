"""
generate.py - Gemini Flash を使ってコンサルにゃんこ口調でポスト生成
防御策: 原文に含まれない固有名詞の使用を禁止するプロンプト設計
"""
import os
import yaml
import google.generativeai as genai


def load_character(config_path: str = "config/character.yml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_prompt(entry: dict, character: dict) -> str:
    """
    厳格なガードレール付きプロンプト
    - 原文にない固有名詞・数字を生成しない
    - キャラトーンを厳守
    - 文字数制限を明示
    """
    char = character["character"]
    max_chars = character["max_chars"]
    
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

【厳守すべき制約 - 極めて重要】
1. 原文に書かれていない固有名詞・企業名・製品名・数値・日付を絶対に使用しないこと
2. 原文から推測できない解釈や予測を述べないこと
3. 医療アドバイス・投資判断に関わる表現は避けること
4. 断定を避け、「〜とのこと」「〜と報告されています」「〜と発表されました」を用いること
5. 文字数制限(厳守): summaryは120字以内、commentaryは50字以内。合計170字以内に必ず収めてください
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
    """
    Gemini FlashでJSON形式のポスト内容を生成
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    
    genai.configure(api_key=api_key)
    
    # Gemini 2.5 Flash (無料枠利用可能)
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
    
    # JSON抽出
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
    """マッチしたキーワードに応じて動的にハッシュタグを選定"""
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
        tags.extend
