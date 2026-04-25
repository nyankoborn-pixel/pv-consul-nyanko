"""
generate.py - Gemini で要約+画像プロンプト+画像を生成
The Rundown AI 型: 親ポストに画像、自リプライにソースURL
画像路線: 雑誌表紙風 + コンセプチュアル風刺(The Economist / The New Yorker 風)
文章路線: フック重視、コンサル視点の解釈OK、医療アドバイスのみ禁止
"""
import os
import yaml
import google.generativeai as genai


def load_character(config_path: str = "config/character.yml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify_news_category(entry: dict) -> str:
    text = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('source_name', '')}".lower()
    
    ai_kw = ["ai", "人工知能", "機械学習", "machine learning", "llm", "生成ai",
             "generative", "automation", "自動化", "デジタル", "dx"]
    if any(kw in text for kw in ai_kw):
        return "ai_tech"
    
    reg_kw = ["guidance", "guideline", "ガイダンス", "ガイドライン", "regulation",
              "規制", "fda", "ema", "pmda", "ich", "cioms", "通達", "通知", "発出",
              "gvp", "薬機法", "rmp", "psur"]
    if any(kw in text for kw in reg_kw):
        return "regulatory"
    
    market_kw = ["市場", "market", "億円", "億ドル", "billion", "million", "成長",
                 "growth", "シェア", "買収", "acquisition", "提携", "契約",
                 "戦略", "組織", "再編", "アウトソース"]
    if any(kw in text for kw in market_kw):
        return "market_business"
    
    china_kw = ["中国", "nmpa", "cde", "china"]
    if any(kw in text for kw in china_kw):
        return "china"
    
    return "general"


def get_image_style_for_category(category: str) -> str:
    """
    画像スタイル: モダン・エディトリアル・コミック調
    The Rundown AI 寄りの、迫力ある一枚絵を狙う
    """
    common_style = (
        "Style: Modern editorial illustration with comic book influence. "
        "Vibrant, dramatic, cinematic lighting. Bold composition with a clear "
        "focal subject taking up significant canvas space. Rich color palette "
        "centered on deep navy blue (#0E1B2E) and warm gold (#C89D44), with "
        "ONE additional bold accent color (electric blue, crimson red, or "
        "emerald green) used dramatically. Strong shadows and highlights. "
        "Stylized but expressive — think editorial covers of WIRED, "
        "Bloomberg Businessweek, or Pop-Sci magazine. NOT minimalist, "
        "NOT flat-vector. Painterly digital illustration with depth."
    )
    
    figure_directive = (
        "INCLUDE a stylized human figure as the focal point. The figure should "
        "have a clear pose and expression conveying the news theme — confident, "
        "concerned, contemplative, or determined. Show the face, but stylize "
        "it (anime/comic/painterly style) so it doesn't look like a specific "
        "real person. The figure should occupy 30-50% of the canvas. They "
        "should be ACTIVELY DOING something (holding, examining, presenting, "
        "deciding) — not just standing."
    )
    
    background_directive = (
        "BACKGROUND must be richly described, not empty. Include a clear "
        "setting that adds context: institutional architecture, scientific "
        "environment, abstract symbolic space, or dramatic atmospheric scene. "
        "Use depth, shadows, and atmospheric lighting. The background should "
        "amplify the news theme."
    )
    
    hard_forbidden = (
        "DO NOT use: "
        "- Minimalist line art or simple geometric shapes "
        "- Empty white/cream backgrounds with negative space "
        "- Flat 2D vector illustration aesthetics "
        "- Silhouette-only figures without faces or expressions "
        "- Generic medical pills, capsules, molecular structures "
        "- Stethoscope, lab coat, white-coated doctor clichés "
        "- Caduceus, red cross, hospital cross "
        "- Round symmetrical centered compositions "
        "- Abstract data visualizations as the main subject"
    )
    
    category_scenes = {
        "regulatory": (
            "Scene: A determined regulator/official figure in a dramatic "
            "institutional setting — perhaps holding an oversized seal or "
            "document, gesturing toward a blueprint, or standing before "
            "monumental architectural columns. Strong sense of authority and "
            "consequence. Cinematic lighting from a window or overhead source. "
            "The composition should feel like a key scene in a political drama."
        ),
        "ai_tech": (
            "Scene: A scientist or engineer figure interacting with a "
            "spectacular AI manifestation — a glowing geometric construct, "
            "data tendrils, or a holographic interface. The figure should look "
            "fascinated, focused, or slightly awed. Dark dramatic environment "
            "with the AI element as the bright focal glow. Cinematic, slightly "
            "futuristic but grounded."
        ),
        "market_business": (
            "Scene: An executive figure in a moment of strategic action — "
            "moving large physical pieces (chess-like, or abstract architectural "
            "blocks), studying a complex map, or pointing decisively. Rich "
            "boardroom-like or abstract corporate landscape. The composition "
            "should convey high-stakes consequence."
        ),
        "china": (
            "Scene: A figure with East Asian features (stylized, respectful, "
            "not stereotypical) in a setting blending traditional Chinese "
            "architectural elements with modern pharmaceutical/technological "
            "aesthetics. Avoid cliché dragons, lanterns, or pandas. Use "
            "ink-wash inspired textures combined with sharp modern composition."
        ),
        "general": (
            "Scene: A pharmaceutical industry figure (researcher, executive, "
            "regulator) in a dramatic moment of action representing the news "
            "theme. Strong character pose, clear emotion, rich atmospheric "
            "background."
        ),
    }
    
    scene = category_scenes.get(category, category_scenes["general"])
    
    return f"{common_style} {figure_directive} {background_directive} {scene} {hard_forbidden}"


def build_prompt(entry: dict, character: dict) -> str:
    char = character["character"]
    category = classify_news_category(entry)
    image_style = get_image_style_for_category(category)
    
    prompt = f"""あなたは「{char['name']}」というキャラクターです。
PVニュースのXポスト用に、読者の手を止める日本語要約と、雑誌表紙のような
画像プロンプトを生成してください。

【キャラクター設定】
- 名前: {char['name']}
- 性格: {", ".join(char['personality'])}
- スタイル: 静かに本質を見抜くPVコンサルの視点。データと業界知見で語る

【今回のニュースカテゴリ】 {category}

【summary 設計指針 - 重要】
読者(PVコンサル、製薬企業の安全性管理担当、規制当局関係者)の手を
タイムライン上で止めることを最優先する。

書き方の指針:
1. 冒頭1文目で「なぜこのニュースが面白いか」を提示する。
   役所主語(「○○省は」「PMDAは」)で始めるのは避ける。
   ニュースの主役(薬、技術、企業、トレンド)を主語にする。
2. コンサル目線の解釈、業界の見立て、構造分析を加えてよい。
   一般常識レベルの背景・歴史・対比はむしろ歓迎する。
3. 数値・日付・固有名詞は、原文に明記されている範囲で自由に使ってよい。
   業界トレンドや一般常識(「ICH-GCPは古くから運用されている」等)も使ってよい。
4. 末尾に汎用的な締め(「医薬品の安全性は重要」「動向を注視」「医療従事者は
   確認すべき」)を入れない。これらの表現は禁止。
5. 文末は「〜とのこと」「〜と報告されている」「〜と発表された」など
   ニュース感のある語尾を使う。

【唯一の禁止事項】
- 個別の医療行為アドバイス(「○○を服用すべき」「○○の投与を止めるべき」など)
  は絶対に書かないこと。読者は専門家だが、X上での医療誘導はトラブルの元。
- それ以外、業界の解釈、推測、見立て、コンサル視点のコメントは自由に書いてよい。

【summary 文字数】
120字以上180字以内。情報密度を最優先。汎用的な締めで文字数を稼がない。

【summary の良い例】
ニュース: 「PMDA、シグナル検出にAI活用のガイダンス案を公表」
→ "シグナル検出にAIを活用する時代がついに公式入りしつつあるとのこと。
   PMDAがガイダンス案を公表し、安全性データの解析プロセスにAIを組み込む
   方向性が示された。実務部門は「AI使うなら検証どうする」という
   次の論点に直面する構図となる。"

ニュース: 「アスピリンの使用上の注意改訂、急性冠症候群を追記」
→ "100年以上使われてきたアスピリンに、新たな副作用が追記された。
   厚労省が「アレルギー反応に伴う急性冠症候群」を重大な副作用として
   加えたとのこと。長く使われてきた薬ほど、データが蓄積し添付文書が
   厚くなる構図が今回も繰り返された。"

【summary の悪い例(避ける)】
- 「厚生労働省は、〜を発表しました。これは医薬品の安全性確保のため重要な
   情報であり、医療従事者は確認すべきです」(役所主語+汎用的な締め)
- 「動向を注視する必要があるでしょう」(誰でも書ける一般論)

【image_prompt 設計指針 - 重要】
このニュースの「本質」を1つの強い隠喩シーンで表現する。
平凡な医療シンボルの組み合わせ(薬+警告、医者+聴診器、ビル+書類)は禁止。
The Economist や The New Yorker の表紙のような、一目で物語を伝える
コンセプチュアル・イラストを狙う。

スタイル指示:
{image_style}

【image_prompt 必須要件】
- ニュース内容を1つの具体的シーン・隠喩で表現
- "abstract" "professional" "clean" だけで終わらせず、何を描くか明確に
- Aspect ratio: 16:9 landscape
- NO text, NO letters, NO numbers, NO logos
- NO mascot characters, NO anthropomorphic animals
- NO real human faces or identifiable people (silhouettes or stylized figures OK)
- Length: 80-120 English words

【image_prompt 良い例】
"Conceptual editorial cover illustration in the style of The Economist. 
A single glowing AI eye scanning rows of pharmaceutical pills arranged 
like an audience, with ripples of data emanating outward. Deep navy 
background with gold accents and a single emerald glow from the eye. 
Dramatic side lighting. Strong negative space on the right. 16:9. 
No text, no characters, no logos."

【image_prompt 悪い例(避ける)】
- "abstract pharmaceutical elements, clean professional style" (何も描かれない)
- "molecules and DNA helix in blue background" (使い古された医療クリシェ)
- "doctor holding stethoscope" (人物クリシェ)
- "pills with warning signs" (使い古された安全性クリシェ)

【出力形式】
{{
  "summary": "120-180字、フックのある日本語要約",
  "image_prompt": "80-120 words、英語の画像プロンプト"
}}

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1500]}
ソース: {entry['source_name']}

上記の原文情報をベースに、コンサル目線の解釈や業界知見を加えながら、
読者の手を止める要約と、雑誌表紙のような画像プロンプトを生成してください。
JSON形式のみを出力し、前後に説明文を付けないこと。
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
            "temperature": 0.85,
            "top_p": 0.95,
            "max_output_tokens": 4000,
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
    
    full_post = f"{summary}\n\n{hashtags_str}"
    if len(full_post) <= max_total:
        return full_post
    
    minimal_tags = " ".join([
        character["hashtags"]["always"][0],
        character["hashtags"]["always"][1],
        character["ai_disclosure"]
    ])
    minimal_post = f"{summary}\n\n{minimal_tags}"
    if len(minimal_post) <= max_total:
        return minimal_post
    
    overhead = len(f"\n\n{minimal_tags}")
    allowed_summary = max_total - overhead
    if allowed_summary > 1:
        summary = summary[:allowed_summary - 1] + "…"
    return f"{summary}\n\n{minimal_tags}"


def generate_image(image_prompt: str, output_path: str = "/tmp/post_image.png") -> str:
    """
    Gemini 2.5 Flash Image (Nano Banana) で画像生成 (新SDK使用)
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[image] GEMINI_API_KEY not set, skipping image generation")
        return None
    
    try:
        from google import genai as new_genai
        from google.genai import types
        
        client = new_genai.Client(api_key=api_key)
        
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=image_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio="16:9",
                ),
            ),
        )
        
        for part in response.parts:
            if part.inline_data and part.inline_data.data:
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
