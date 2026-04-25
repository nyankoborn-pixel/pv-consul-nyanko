"""
generate.py - Gemini で要約+画像プロンプト+画像を生成
The Rundown AI 型: 親ポストに画像、自リプライにソースURL
画像路線: Alex Ross 風アメコミ painted comic art
PV関連性判定: 記事がPV/医薬品と無関係なら投稿スキップ
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
              "gvp", "薬機法"]
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
    画像スタイル: Alex Ross 風アメコミ・1枚絵
    Marvel/DC 系のヒーロー的・派手・劇画調・彩度高
    """
    common_style = (
        "Style: Painterly American comic book illustration in the style of "
        "Alex Ross. Hyper-realistic painted comic art with dramatic chiaroscuro "
        "lighting. Vibrant saturated colors. Heroic, cinematic composition with "
        "strong perspective and depth. The image should feel like a key panel "
        "from a major Marvel or DC comic book — epic, consequential, charged "
        "with emotion. Rich detail in clothing, environment, and lighting. "
        "Color palette: deep navy blue and warm gold as base, with bold accent "
        "colors (crimson, electric blue, emerald) used dramatically. "
        "Painterly brushwork visible, NOT flat vector or thin line art."
    )
    
    figure_directive = (
        "MANDATORY: Include a clearly rendered human figure as the heroic "
        "focal point, occupying 40-60% of the canvas. Show their FACE clearly "
        "with a strong, dramatic expression — determined, contemplative, "
        "alarmed, triumphant, or commanding. Stylized in painted comic style "
        "(NOT photorealistic, NOT anime). The figure should be in a strong, "
        "cinematic pose: gesturing, holding something significant, mid-action, "
        "or in a moment of decision. Their costume/clothing should match the "
        "context (lab coat, business suit, regulator uniform, etc.) but "
        "stylized heroically."
    )
    
    background_directive = (
        "BACKGROUND: Fully painted, never empty. Include richly detailed "
        "context — institutional architecture, scientific environment, "
        "boardroom, urban skyline, or symbolic setting. Use dramatic light "
        "sources (sunbeams, monitor glow, spotlights) creating strong shadows. "
        "Background can include supporting objects directly relevant to the "
        "news theme."
    )
    
    hard_forbidden = (
        "DO NOT use: "
        "- Minimalist line art or simple geometric shapes "
        "- Empty white backgrounds with negative space "
        "- Flat 2D vector illustration aesthetics "
        "- Silhouette figures without faces "
        "- Anime or manga style "
        "- Photorealistic 3D rendering "
        "- Generic stock medical clichés (pills + warning, stethoscope, "
        "  caduceus, DNA helix as main subject) "
        "- Cute or chibi character styles"
    )
    
    category_scenes = {
        "regulatory": (
            "Scene direction: A determined regulator/official figure as the "
            "hero — perhaps holding aloft an oversized seal or document, "
            "standing before towering institutional pillars, or signing a "
            "consequential decree. Lighting from above creating heroic "
            "shadows. Include specific objects from the news theme (documents, "
            "pens, official seals, building architecture)."
        ),
        "ai_tech": (
            "Scene direction: A scientist or engineer figure in heroic pose, "
            "facing or commanding a spectacular AI manifestation — a glowing "
            "holographic interface, a massive data construct, or a powerful "
            "neural network visualization. The AI element glows dramatically "
            "with electric blue or gold light. Include specific objects from "
            "the news theme (lab equipment, screens, pharmaceutical bottles "
            "in background)."
        ),
        "market_business": (
            "Scene direction: An executive figure in a dramatic boardroom or "
            "corporate setting, in a moment of strategic command — perhaps "
            "moving a large symbolic object, gesturing toward a complex "
            "strategy display. Cinematic lighting through large windows. "
            "Include specific objects from the news theme."
        ),
        "china": (
            "Scene direction: A Chinese researcher or executive figure as "
            "the hero, in a setting blending modern Chinese pharmaceutical/"
            "research architecture with traditional aesthetic elements "
            "(stylized respectfully). Strong dramatic lighting. Avoid "
            "stereotypical imagery (no dragons, lanterns, pandas)."
        ),
        "general": (
            "Scene direction: A pharmaceutical industry hero figure "
            "(researcher, executive, regulator) in a dramatic moment of "
            "action representing the news theme. Strong heroic pose, clear "
            "powerful emotion, fully rendered atmospheric background. "
            "Include specific objects from the news theme."
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

【最初の判定 - 極めて重要】
このニュースが「PV(医薬品安全性監視)/医薬品/製薬業界」と
直接関係あるかを判定してください。

PVに関係ある例:
- 医薬品の安全性管理、副作用監視、ICSR、シグナル検出
- 製薬企業の戦略、組織変更、AI/DX導入
- 規制制度(GVP省令、ICH ガイドライン、PMDA/FDA/EMA の発出)
- 医薬品AI、製薬AI、医療AIの中で薬と関わるもの

PVに関係ない例:
- 一般的なIT企業のAIガバナンス
- 物理学・化学の研究
- 医療機関(病院)の運営の話で薬と無関係
- 食品、化粧品、サプリメント
- 一般的なAI規制の話で医薬品と無関係

判定方法:
- 原文に「医薬品」「製薬」「PV」「ファーマコビジランス」「副作用」
  「ICSR」「シグナル検出」「FDA/EMA/PMDA」のいずれか、または
  製薬企業名・医薬品関連の固有名詞が明示されている → "yes"
- 原文に上記がなく、強引にPVに寄せないと書けない → "no"

【出力形式】
PVに関係ない場合(is_pv_related=false):
{{
  "is_pv_related": false,
  "skip_reason": "なぜPVと無関係と判断したか短く記載"
}}

PVに関係ある場合(is_pv_related=true):
{{
  "is_pv_related": true,
  "summary": "120-180字、フックのある日本語要約",
  "image_prompt": "100-150 words、英語の画像プロンプト"
}}

【summary 設計指針(is_pv_related=true の時のみ)】
読者(PVコンサル、製薬企業の安全性管理担当、規制当局関係者)の手を
タイムライン上で止めることを最優先する。

書き方:
1. 冒頭1文目で「なぜこのニュースが面白いか」を提示する。
   役所主語(「○○省は」「PMDAは」)で始めない。
   ニュースの主役(薬、技術、企業、トレンド)を主語にする。
2. コンサル目線の解釈、業界の見立て、構造分析を加えてよい。
3. 数値・日付・固有名詞は原文に明記されている範囲で自由に使ってよい。
   ただし**原文に書かれていないPV略語(ICSR/PSUR/RMP/PBRER等)を
   無理に入れない**。原文がそれらに言及していなければ、フルスペル
   または一般用語で記述する。
4. 末尾の汎用的な締め(「医療従事者は確認すべき」「動向を注視」等)は禁止。
5. 文末は「〜とのこと」「〜と報告されている」「〜と発表された」など。

【厳守】
- 原文が医薬品/PVと無関係なら、無理に医薬品の話に寄せず
  is_pv_related=false で返すこと。これが最も重要。
- 個別の医療行為アドバイス(「○○を服用すべき」「投与中止」など)は禁止。

【image_prompt 設計指針(is_pv_related=true の時のみ)】
ニュース内容を視覚化するため、3ステップを実行する:
ステップ1: ニュースから「具体的なオブジェクト」を5つ以上抽出
ステップ2: 「人物が何をしている瞬間」を決める
ステップ3: ステップ1とステップ2を組み合わせて image_prompt を書く

スタイル指示:
{image_style}

【image_prompt 必須要件】
- 具体的なオブジェクトを3つ以上、画像内に配置
- 「抽象的」「シンボリック」だけで終わらせず、具体的に何が映るかを書く
- Aspect ratio: 16:9 landscape
- NO text, NO letters, NO numbers, NO logos
- NO mascot characters, NO anthropomorphic animals
- NO real human faces (stylized comic-style faces OK)
- Length: 100-150 English words

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1500]}
ソース: {entry['source_name']}

最初に is_pv_related の判定をしてから、JSON形式で出力してください。
前後に説明文を付けないこと。
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
    
    # PV関連性判定
    if result.get("is_pv_related") is False:
        skip_reason = result.get("skip_reason", "PVと無関係と判定")
        raise PVNotRelatedError(f"Skipped: {skip_reason}")
    
    if "summary" not in result or "image_prompt" not in result:
        raise RuntimeError(f"Gemini output missing required fields: {result}")
    
    result["_category"] = classify_news_category(entry)
    return result


class PVNotRelatedError(Exception):
    """記事がPVと無関係と判定された場合のエラー(次の候補に進むためのシグナル)"""
    pass


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
