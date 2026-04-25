"""
generate.py - Gemini Flash でコンサルにゃんこ要約 + 画像プロンプトを生成
The Rundown AI 型: 親ポストに画像、自リプライにソースURL
"""
import os
import yaml
import google.generativeai as genai


def load_character(config_path: str = "config/character.yml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify_news_category(entry: dict) -> str:
    text = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('source_name', '')}".lower()
    
    recall_kw = ["回収", "副作用", "副反応", "死亡", "重篤", "recall", "withdrawal", 
                 "adverse event", "safety alert", "使用上の注意", "改訂指示"]
    if any(kw in text for kw in recall_kw):
        return "recall_safety"
    
    ai_kw = ["ai", "人工知能", "機械学習", "machine learning", "llm", "生成ai",
             "generative", "automation", "自動化", "デジタル"]
    if any(kw in text for kw in ai_kw):
        return "ai_tech"
    
    reg_kw = ["guidance", "guideline", "ガイダンス", "ガイドライン", "regulation",
              "規制", "fda", "ema", "pmda", "ich", "cioms", "通達", "通知", "発出"]
    if any(kw in text for kw in reg_kw):
        return "regulatory"
    
    market_kw = ["市場", "market", "億円", "億ドル", "billion", "million", "成長",
                 "growth", "シェア", "買収", "acquisition", "提携", "契約"]
    if any(kw in text for kw in market_kw):
        return "market_business"
    
    return "general"


def get_image_style_for_category(category: str) -> str:
    """カテゴリ別の画像スタイル指示(英語)"""
    styles = {
        "regulatory": "editorial illustration of regulatory documents, official seals, abstract law/compliance imagery, professional and serious tone",
        "ai_tech": "editorial illustration of abstract AI concepts, neural networks, data flows, modern technology imagery, clean and futuristic",
        "recall_safety": "editorial illustration of medical safety, careful and respectful tone, abstract pharmaceutical imagery, no graphic content",
        "market_business": "editorial illustration of business charts, growth curves, abstract financial imagery, professional corporate style",
        "general": "editorial illustration of abstract pharmaceutical industry concepts, professional and clean style",
    }
    return styles.get(category, styles["general"])


def build_prompt(entry: dict, character: dict) -> str:
    char = character["character"]
    category = classify_news_category(entry)
    image_style = get_image_style_for_category(category)
    
    prompt = f"""あなたは「{char['name']}」というキャラクターです。
PVニュースのXポスト用に、日本語要約と画像プロンプトを生成してください。

【キャラクター設定】
- 名前: {char['name']}
- 性格: {", ".join(char['personality'])}
- スタイル: 静かに本質を見抜く視点。事実を中立的に、しかし要点を逃さず伝える

【今回のニュースカテゴリ】 {category}

【厳守すべき制約】
1. 原文に書かれていない固有名詞・企業名・製品名・数値・日付を絶対に使用しないこと
2. 原文から推測できない事実は述べないこと
3. 医療アドバイス・投資判断に関わる表現は避けること
4. summaryは中立的な事実要約。断定を避け「〜とのこと」「〜と報告されています」「〜と発表されました」を使う
5. 文字数: summaryは150字以上180字以内(主体・出来事・重要点を必ず含めること)
6. 出力は以下のJSON形式のみ。前後に説明文を付けないこと

【出力形式】
{{
  "summary": "150-180字の事実要約",
  "image_prompt": "英語の画像生成プロンプト(下記の制約厳守)"
}}

【image_prompt の必須要件 - 厳守】
- Style: {image_style}
- Absolutely NO text, NO letters, NO numbers, NO characters in the image
- NO mascot characters, NO anthropomorphic animals, NO cartoon characters
- NO real human faces or identifiable people
- NO company logos, NO branded items
- Abstract and conceptual visualization of the news theme
- Color palette: navy blue, gold accents, clean professional
- Aspect ratio suggestion: 16:9 landscape
- Length: 30-60 English words

【image_prompt 良い例】
"editorial illustration of abstract regulatory documents floating in deep navy blue background with gold accents, clean professional style, no text, no characters, no logos, 16:9 aspect ratio, conceptual minimalist composition"

【image_prompt 悪い例(絶対避ける)】
- "Japanese text saying ..." (テキスト含む)
- "a cute mascot cat ..." (キャラクター含む)
- "person holding ..." (人物含む)
- "Pfizer logo ..." (ブランド含む)

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1500]}
ソース: {entry['source_name']}

上記の原文情報のみを根拠として、JSONを出力してください。
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
            "temperature": 0.7,
            "top_p": 0.95,
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
    
    if "summary" not in result or "image_prompt" not in result:
        raise RuntimeError(f"Gemini output missing required fields: {result}")
    
    result["_category"] = classify_news_category(entry)
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
    親ポストの本文を組み立て(画像とリプライURLは別途扱う)
    優先順位: summary > hashtags
    """
    tags = select_hashtags(entry, character)
    hashtags_str = " ".join(tags)
    summary = gen["summary"]
    max_total = character.get("max_chars", 278)
    
    # Step 1: 全部入りで試す
    full_post = f"{summary}\n\n{hashtags_str}"
    if len(full_post) <= max_total:
        return full_post
    
    # Step 2: ハッシュタグを必須3個に削減
    minimal_tags = " ".join([
        character["hashtags"]["always"][0],
        character["hashtags"]["always"][1],
        character["ai_disclosure"]
    ])
    minimal_post = f"{summary}\n\n{minimal_tags}"
    if len(minimal_post) <= max_total:
        return minimal_post
    
    # Step 3: 最終手段、summaryを切り詰める
    overhead = len(f"\n\n{minimal_tags}")
    allowed_summary = max_total - overhead
    if allowed_summary > 1:
        summary = summary[:allowed_summary - 1] + "…"
    return f"{summary}\n\n{minimal_tags}"


def generate_image(image_prompt: str, output_path: str = "/tmp/post_image.png") -> str:
    """
    Gemini 2.5 Flash Image (Nano Banana) で画像生成
    成功時: 保存したファイルパスを返す
    失敗時: None を返す(呼び出し元でテキストのみ投稿にフォールバック)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[image] GEMINI_API_KEY not set, skipping image generation")
        return None
    
    try:
        genai.configure(api_key=api_key)
        
        model = genai.GenerativeModel("gemini-2.5-flash-image")
        
        response = model.generate_content(
            image_prompt,
            generation_config={
                "response_modalities": ["IMAGE"],
            },
        )
        
        # レスポンスから画像バイナリを抽出
        for candidate in response.candidates:
            for part in candidate.content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    image_bytes = part.inline_data.data
                    with open(output_path, "wb") as f:
                        f.write(image_bytes)
                    print(f"[image] Saved to {output_path} ({len(image_bytes)} bytes)")
                    return output_path
        
        print("[image] No image data in response")
        return None
    
    except Exception as e:
        print(f"[image] Generation failed: {e}")
        return None
