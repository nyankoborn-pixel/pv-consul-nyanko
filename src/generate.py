"""
generate.py - Gemini で要約+画像プロンプト+画像を生成
The Rundown AI 型: 親ポストに画像、自リプライにソースURL
画像路線: ルパン三世風アニメ(Monkey Punch / TMS Entertainment 1970s-90s)
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
    画像スタイル: ルパン三世風アニメ + 峰不二子レベルの妖艶演出
    Monkey Punch / TMS Entertainment 1970s-90s 系
    ボディコン衣装、ローアングル、ネオン背景、動きのあるポーズで存在感最大化
    """
    common_style = (
        "Style: Classic Japanese anime illustration inspired by Lupin III "
        "(Monkey Punch / TMS Entertainment, 1970s-1990s era). Hand-drawn "
        "cel animation aesthetic with bold black ink lines and confident "
        "brushstrokes. Flat color shading with dramatic cel-style "
        "highlights and shadows. Saturated cinematic color palette: "
        "deep blacks, vivid magenta and hot pink neons, electric blues, "
        "crimson red, metallic gold accents, and rich purples. The "
        "atmosphere should feel like a key still from a stylish anime "
        "thriller — sleek, sexy, charged with adrenaline. Cel-shaded "
        "animation aesthetic, NOT photorealistic, NOT modern digital "
        "painting, NOT 3D rendering."
    )
    
    composition_directive = (
        "MANDATORY COMPOSITION (absolute, never compromise):\n"
        "1. CAMERA ANGLE: Extreme LOW ANGLE shot from below the subject's "
        "hips, looking up at her dramatically.\n"
        "2. FRAMING: FULL BODY shot showing her from head to high-heeled "
        "feet. Subject occupies 50-70% of vertical canvas. Heels and "
        "long legs MUST be visible.\n"
        "3. POSE: Dynamic motion — she is mid-stride walking forward, "
        "turning with attitude, OR in a sultry mid-action pose with "
        "strong S-curve body line. Hair swept by movement. Hip "
        "dramatically out to one side. NEVER static, NEVER both feet "
        "together, NEVER simply standing.\n"
        "4. LIGHTING: STRONG backlight from neon sources behind her — "
        "vivid magenta, hot pink, electric blue, or crimson neon. "
        "Backlight brighter than fill light, creating intense rim light "
        "on her hair, shoulders, and silhouette. Neon glow spills onto "
        "her cheekbones and skin in colored highlights."
    )
    
    figure_directive = (
        "MANDATORY SUBJECT: An ORIGINAL anime-style mature woman as the "
        "focal point. Confident, mysterious, captivating presence — like "
        "a sophisticated international agent or femme fatale. Sharp "
        "intelligent eyes with a knowing, slightly seductive gaze. "
        "Striking adult features with elegant cheekbones and full lips. "
        "Long flowing hair caught in motion or wind. ORIGINAL CHARACTER "
        "ONLY — not Fujiko, Lupin, Jigen, Goemon, Zenigata, or any "
        "copyrighted character.\n"
        "EXPRESSION: Confident smirk, knowing smile, intense focus, "
        "OR mysterious half-smile. NEVER serious frown, NEVER blank "
        "expression, NEVER child-like big eyes.\n"
        "ADULT PROPORTIONS: Tall, mature adult figure — clearly an adult "
        "professional in her late 20s to 30s. NOT chibi, NOT teen, NOT "
        "kawaii proportions."
    )
    
    wardrobe_directive = (
        "MANDATORY WARDROBE (this is critical for impact):\n"
        "Glamorous bold attire — choose ONE:\n"
        "- A glossy black or red form-fitting evening dress with high "
        "thigh slit exposing one leg, plunging neckline, and statement "
        "shoulder cut\n"
        "- A tight bodycon dress with cutout details at the waist or "
        "side, glossy fabric finish\n"
        "- A satin slip dress with thin straps and asymmetric hem\n"
        "- A sleek catsuit or fitted leather/vinyl outfit with heroic "
        "spy aesthetic\n"
        "Statement high heels with ankle straps, heels visible.\n"
        "Bold accessories: large drop earrings, fine necklace catching "
        "the neon light, slim leather gloves optional.\n"
        "Hair: long, flowing dramatically in the wind or motion, with "
        "rim light highlights catching the neon.\n"
        "NEVER business suits, NEVER trench coats, NEVER lab coats, "
        "NEVER conservative office attire, NEVER covered modest "
        "clothing. This is high-impact glamour wardrobe."
    )
    
    setting_directive = (
        "SETTING: Nighttime urban environment — neon-lit Tokyo or Shibuya "
        "street with vertical neon signs, a rain-slicked city corner with "
        "glowing puddle reflections, a high-floor balcony overlooking a "
        "neon city, OR a luxurious nightclub-lounge interior with "
        "dramatic accent lighting. Wet glossy reflections on the ground "
        "capturing the colored neon. Atmospheric haze for cinematic depth. "
        "Neon signs in the background (no readable text, just neon shapes "
        "and colors)."
    )
    
    hard_forbidden = (
        "ABSOLUTE PROHIBITIONS: "
        "- Modern anime style (Demon Slayer, Jujutsu Kaisen, Naruto-era look) "
        "- Soft kawaii/moe style or chibi proportions, child-like big eyes "
        "- Photorealistic rendering or 3D CGI "
        "- Western comic book painted style (Alex Ross, Marvel) "
        "- Minimalist line art or flat vector illustration "
        "- Any copyrighted Lupin III characters (Lupin, Jigen, Goemon, "
        "Fujiko, Zenigata, Inspector Zenigata) "
        "- Conservative office attire, business suits, trench coats, "
        "lab coats, covered modest clothing "
        "- Static stationary poses with both feet together "
        "- Daylight settings, bright sunny scenes, daytime offices "
        "- Bust-up framing, headshot framing, waist-up only "
        "- Sitting at desks, working at computers "
        "- Multiple people in frame "
        "- Generic medical clichés (pills, stethoscope, caduceus, DNA) "
        "- Text, letters, numbers, logos, readable signage in image "
        "- Full nudity, transparent clothing, exposed nipples or genitals "
        "- Subjects appearing under 25 years old"
    )
    
    return f"{common_style}\n\n{composition_directive}\n\n{figure_directive}\n\n{wardrobe_directive}\n\n{setting_directive}\n\n{hard_forbidden}"


def build_prompt(entry: dict, character: dict) -> str:
    char = character["character"]
    category = classify_news_category(entry)
    image_style = get_image_style_for_category(category)
    
    prompt = f"""あなたは「{char['name']}」というキャラクターです。
PVニュースのXポスト用に、読者の手を止める日本語要約と、
雑誌表紙のような画像プロンプトを生成してください。

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

【summary 設計指針(is_pv_related=true の時のみ)- 極めて重要】
読者(PVコンサル、製薬企業の安全性管理担当、規制当局関係者)の手を
タイムライン上で止めることを最優先する。

書き方:
1. 冒頭1文目で「なぜこのニュースが面白いか」を提示する。
   役所主語(「○○省は」「PMDAは」)で始めない。
   ニュースの主役(薬、技術、企業、トレンド)を主語にする。
2. 数値・日付・固有名詞は原文に明記されている範囲で自由に使ってよい。
   原文がPV略語(ICSR/PSUR/RMP/PBRER等)に言及していなければ、
   フルスペルまたは一般用語で記述すること。
3. 末尾の汎用的な締め(「医療従事者は確認すべき」「動向を注視」等)は禁止。
4. 文末は「〜とのこと」「〜と報告されている」「〜と発表された」など。

【極めて重要な制約 - ハルシネーション防止】
**summary には、原文に明示的に書かれている事実だけを記述すること。**
以下を絶対に書かないこと:
- 原文に書かれていない「業界の見立て」「構造分析」「推測」「示唆」
- 原文に書かれていない他の制度・施策との「連動」「影響」「波及」
- 原文に書かれていない「変化の可能性」「求められる対応」「今後の展開」
- 「示唆されている」「可能性がある」「求められる」「見られる」など
  推測を匂わせる表現で、原文にない内容を補完すること

原文が短いリード文しかなくても、それで書ける範囲だけで要約すること。
情報量が足りないと感じても、推測で補ってはならない。
要約が短くなる場合はそれでよい(120字未満でも可)。

【厳守】
- 原文が医薬品/PVと無関係なら、無理に医薬品の話に寄せず
  is_pv_related=false で返すこと。これが最も重要。
- 個別の医療行為アドバイス(「○○を服用すべき」「投与中止」など)は禁止。

【image_prompt 設計指針】
ニュース内容を視覚化するため、3ステップを実行する:
ステップ1: ニュースから具体的なオブジェクトを5つ以上抽出
ステップ2: 人物が何をしている瞬間かを決める
ステップ3: ステップ1とステップ2を組み合わせて image_prompt を書く

スタイル指示(必ず以下の内容を image_prompt に含めること):
{image_style}

【image_prompt 必須要件】
- 具体的なオブジェクトを3つ以上、画像内に配置
- 「抽象的」「シンボリック」だけで終わらせず、具体的に何が映るかを書く
- Aspect ratio: 16:9 landscape
- NO text, NO letters, NO numbers, NO logos
- NO real human faces (stylized anime-style faces required)
- NO copyrighted Lupin III characters (Fujiko, Lupin, Jigen, Goemon, Zenigata)
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
