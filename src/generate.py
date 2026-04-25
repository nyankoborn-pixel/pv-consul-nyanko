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
    画像スタイル: ハイパーリアル写真 + 妖艶演出フル投入版
    視線・表情・衣装・ポーズ・メイクを最大限強化
    """
    common_style = (
        "Style: Hyperrealistic cinematic photography, ultra-detailed, 8K "
        "resolution, shot on a Sony A1 or Canon R5 with a 50mm f/1.2 or "
        "85mm f/1.4 prime lens. Cinematic shallow depth of field with "
        "gorgeous bokeh. Natural skin texture with fine pores, individual "
        "hair strands, realistic luxurious fabric with sheen. Aesthetic: "
        "high-fashion editorial photography meets film noir glamour — like "
        "a Vogue cover, a James Bond film still, or a sophisticated "
        "perfume advertisement. The image MUST be indistinguishable from "
        "a real photograph. NOT illustration, NOT anime, NOT painted art, "
        "NOT 3D rendering."
    )
    
    composition_directive = (
        "MANDATORY COMPOSITION (absolute, never compromise):\n"
        "1. CAMERA ANGLE: LOW ANGLE shot from below the subject's waist, "
        "looking up. The viewer feels they are looking up at her.\n"
        "2. FRAMING: FULL BODY or 3/4 body shot showing legs and feet. "
        "Subject occupies 40-60% of vertical canvas. NEVER bust-up, "
        "NEVER headshot, NEVER seated at desk, NEVER waist-up only.\n"
        "3. LIGHTING: STRONG RIM LIGHT from behind defining her silhouette "
        "dramatically. Backlight should be brighter than fill light, "
        "creating clear edge glow on her hair, shoulders, and arms. "
        "Vibrant accent colored lights (neon magenta, electric blue, "
        "amber, deep red) from background sources.\n"
        "4. SURFACES: Wet-look glossy reflections on the floor capturing "
        "the colored lights. Atmospheric haze for cinematic depth."
    )
    
    expression_directive = (
        "MANDATORY EXPRESSION (this is critical — never compromise):\n"
        "She MUST look DIRECTLY AT THE CAMERA with a confident, sultry, "
        "slightly seductive gaze. Eyes locked on the viewer with magnetic "
        "intensity. Lips slightly parted, OR a subtle knowing smile, OR a "
        "slight smirk of confident allure. Chin slightly lowered, eyes "
        "looking up at the camera through her lashes — the classic "
        "femme fatale gaze. NEVER looking away from camera, NEVER serious "
        "business expression, NEVER focused on a task, NEVER neutral or "
        "professional."
    )
    
    pose_directive = (
        "MANDATORY POSE (specific actions required):\n"
        "Choose ONE of these specific glamorous poses (do not do generic "
        "standing):\n"
        "A) Hand on hip with weight shifted to one leg, hip prominently "
        "out to the side creating dramatic S-curve\n"
        "B) One hand touching her hair or running through it, the other "
        "hand on her waist or hip\n"
        "C) Arms slightly crossed below the bustline creating a confident "
        "fashion-model stance, hip shifted\n"
        "D) Mid-stride walking toward camera with one leg crossing the "
        "other, hip rotation visible\n"
        "E) Leaning against architecture (pillar, wall, bar) with hip "
        "out, shoulder dropped, arm extended\n"
        "Body language must read as confidently sensual — model-like, "
        "magazine-cover-like. NEVER static military stance, NEVER both "
        "feet flat together, NEVER hands hanging straight."
    )
    
    wardrobe_directive = (
        "MANDATORY WARDROBE (glamorous evening attire required):\n"
        "Choose from: a slit evening gown showing one leg through a high "
        "thigh slit, a satin/silk cocktail dress with elegant cut, an "
        "off-shoulder structured dress, a backless sophisticated dress, "
        "or a fitted bodycon dress with statement design. Fabric MUST "
        "have visible sheen and luxurious quality (silk, satin, leather "
        "accents). Statement neckline (tasteful V-neck or boat neck — "
        "elegant, not vulgar). MUST show legs (slit, knee-length, or "
        "shorter elegant cut). Statement high heels visible (stilettos, "
        "ankle straps). NEVER trench coats, NEVER business suits, NEVER "
        "covered-up office attire, NEVER lab coats. This is glamour-shoot "
        "wardrobe, not office wardrobe."
    )
    
    hair_makeup_directive = (
        "MANDATORY HAIR & MAKEUP (full glamour required):\n"
        "MAKEUP: Smoky eye makeup with defined eyeliner and dramatic "
        "lashes. Defined contoured cheekbones. Bold lip color (deep red, "
        "wine, nude-glossy, or rose). Dewy luminous skin finish. Editorial-"
        "level makeup throughout — this is high-fashion glamour, NEVER "
        "natural/no-makeup look. "
        "HAIR: Voluminous styled hair — long flowing waves with movement, "
        "an elegant updo with face-framing strands, or sleek-and-bold "
        "modern style. Hair catches the rim light dramatically with "
        "highlight reflections. NEVER simple ponytail, NEVER plain "
        "office hair. "
        "JEWELRY: Statement large earrings (chandelier or geometric "
        "drops). Necklace catching the light. Optional sleek bracelet "
        "or rings. Jewelry should sparkle and add visual interest."
    )
    
    color_palette = (
        "COLOR PALETTE: Black base with deep red, neon purple/magenta, "
        "electric blue, metallic gold, dark navy. Cinematic noir grading. "
        "Saturated accent lights against deep shadows."
    )
    
    figure_directive = (
        "SUBJECT: A single Japanese or East Asian woman, 28-40 years old. "
        "International, mysterious, captivating presence — sophisticated "
        "femme fatale or international agent vibe. Beautiful with "
        "distinctive authentic features — NOT a generic AI beauty. "
        "Mature sophisticated allure. Striking, magnetic, the kind of "
        "presence that stops you mid-scroll."
    )
    
    hard_forbidden = (
        "ABSOLUTE PROHIBITIONS: "
        "- Anime, manga, cartoon, illustration, painted, or 3D CGI styles "
        "- Sitting at desk, working at computer, hunched over papers, "
        "  bust-up framing, headshot framing, waist-up only framing "
        "- Business suits, trench coats, lab coats, office attire "
        "- Static/stationary poses with both feet together "
        "- Looking away from camera or focused on tasks "
        "- Serious/professional expression "
        "- Multiple people in frame (single subject only) "
        "- Real, identifiable celebrities, actresses, models, or public "
        "  figures — face must be entirely original "
        "- Recognizable Lupin III characters (Fujiko, Lupin, Jigen, "
        "  Goemon, Zenigata) "
        "- Full nudity or transparent clothing "
        "- Subjects appearing under 28 years old "
        "- Generic medical clichés (stethoscope, white coat, pills) "
        "- Text, logos, or readable signage in the image"
    )
    
    category_scenes = {
        "regulatory": (
            "Setting: a stately government building interior at night — "
            "vast marble corridor with tall pillars, deep red carpet, "
            "ornate chandelier overhead. Polished marble floor reflects "
            "warm light. Atmospheric haze. She stands in this opulent "
            "space looking absolutely out of place yet completely in command."
        ),
        "ai_tech": (
            "Setting: an ultra-modern dark research environment with a "
            "wall of large monitors displaying abstract data visualizations. "
            "Monitors backlight her in cool electric blue and magenta. "
            "Glossy floor reflects the colored lights. Glass and metal "
            "architecture creates dramatic geometric backdrop."
        ),
        "market_business": (
            "Setting: a high-floor luxurious Tokyo executive lounge or "
            "hotel suite at night. Floor-to-ceiling windows show Tokyo "
            "skyline with neon city lights creating bokeh. Strong backlight "
            "from city lights creates dramatic rim around her silhouette. "
            "Polished marble or wood floor reflects warm light. Maybe a "
            "champagne flute on a nearby surface."
        ),
        "china": (
            "Setting: a Shanghai or Hong Kong luxurious atmospheric "
            "interior at night — Bund-area old-money hotel lobby, retro "
            "art deco interior, or high-floor terrace overlooking Pudong "
            "skyline. Warm amber lighting mixed with neon city glow. "
            "Glossy reflective surfaces."
        ),
        "general": (
            "Setting: an upscale atmospheric night setting — luxurious "
            "lounge interior, marble corridor, rain-slick city street with "
            "neon reflections, or glamorous penthouse. Strong rim lighting, "
            "colored accent lights, glossy reflections."
        ),
    }
    
    scene = category_scenes.get(category, category_scenes["general"])
    
    return (
        f"{common_style}\n\n"
        f"{composition_directive}\n\n"
        f"{expression_directive}\n\n"
        f"{pose_directive}\n\n"
        f"{wardrobe_directive}\n\n"
        f"{hair_makeup_directive}\n\n"
        f"{color_palette}\n\n"
        f"{figure_directive}\n\n"
        f"{scene}\n\n"
        f"{hard_forbidden}"
    )


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
