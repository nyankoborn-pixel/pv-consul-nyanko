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
    画像スタイル: 完全限界写真風(ハイパーリアリスティック)
    妖艶で目を引く女性プロフェッショナル
    """
    common_style = (
        "Style: Hyperrealistic photography, ultra-detailed, 8K resolution, "
        "shot on a high-end full-frame camera (Sony A1, Canon R5, or "
        "equivalent) with a fast prime lens (50mm f/1.2 or 85mm f/1.4). "
        "Cinematic depth of field with gorgeous bokeh. Natural skin texture "
        "with fine details — visible pores, subtle imperfections, realistic "
        "fabric weaves, individual strands of hair. Documentary-meets-fashion "
        "photography aesthetic. Color grading: rich, slightly desaturated "
        "tones with deep navy shadows and warm golden highlights. The image "
        "should be indistinguishable from a real photograph. NOT painterly, "
        "NOT illustration, NOT 3D rendering, NOT anime."
    )
    
    figure_directive = (
        "MANDATORY: A single Japanese or East Asian woman in her late 20s "
        "to early 40s as the subject, occupying 40-60% of the frame. "
        "Her appearance should be striking and captivating — sharp "
        "intelligent eyes with a confident, slightly mischievous gaze "
        "directed toward the viewer or thoughtfully off-camera. Beautiful "
        "but distinctive features (NOT a generic 'AI beauty' face). "
        "Sophisticated mature elegance with a hint of allure. "
        "Hair: styled with intention — could be elegantly tied up "
        "exposing the neckline, or flowing loose with movement. "
        "Posture: confident and slightly relaxed, with a dynamic angle — "
        "leaning, turning, mid-gesture, or in a moment of focused action. "
        "Body language conveys intelligence and quiet command. "
        "Wardrobe: tailored, elegant, professional — sharp business suits, "
        "sophisticated dresses, or chic smart-casual appropriate to the "
        "scene. Accessories like statement watches, subtle jewelry. "
        "All clothing must be tasteful and professional — NOT revealing, "
        "NOT overtly sexual, NOT skin-baring beyond a normal professional "
        "context. The allure comes from her gaze, presence, and "
        "sophistication — not from clothing exposure."
    )
    
    background_directive = (
        "BACKGROUND: A real-world environment with cinematic atmosphere — "
        "modern Japanese pharmaceutical research lab at golden hour, "
        "high-floor corporate boardroom with Tokyo skyline visible at "
        "twilight, a regulatory agency office with formal architecture, "
        "or a high-end Tokyo hotel lobby. Soft focus background with "
        "shallow depth of field. Practical lighting from windows, "
        "monitors, or atmospheric ambient sources. The scene should feel "
        "like a key still from a sophisticated film noir or a Vogue "
        "Business editorial photoshoot."
    )
    
    hard_forbidden = (
        "DO NOT use: "
        "- Anime, manga, cartoon, or illustration styles "
        "- 3D CGI or video game rendering "
        "- Painted or graphic novel aesthetics "
        "- Generic stock photo poses (crossed arms, fake corporate smile) "
        "- Multiple people in the frame (single subject only) "
        "- Real, identifiable celebrities, politicians, or public figures "
        "  — face must be entirely original "
        "- Faces resembling specific known actresses or models "
        "- Any nudity, partial nudity, transparent clothing, or revealing "
        "  necklines/skirts beyond professional norms "
        "- Overtly sexualized poses, suggestive body angles "
        "- Subjects appearing under 25 years old "
        "- Generic medical clichés (stethoscope around neck, white coat "
        "  with crossed arms holding pills) "
        "- Text, logos, or readable signage in the image "
        "- Empty white backgrounds or studio gradients"
    )
    
    category_scenes = {
        "regulatory": (
            "Scene direction: A confident female regulatory professional in "
            "a moment of decisive presence — perhaps reviewing documents at "
            "an elegant desk with intense focus, standing in a stately "
            "institutional hallway with light streaming through tall "
            "windows, or speaking from a podium with quiet authority. "
            "Setting: a refined Japanese government building or regulatory "
            "agency interior with formal architecture, marble floors, "
            "or wood-paneled walls. Cinematic lighting with strong "
            "directional source. She wears an impeccably tailored business "
            "suit (perhaps with a silk blouse or statement collar). Her "
            "expression: focused, sharp, slightly knowing. Include "
            "atmospheric props: thick documents, official binders, an "
            "elegant pen, architectural columns."
        ),
        "ai_tech": (
            "Scene direction: A captivating female pharmaceutical AI "
            "researcher engaged with cutting-edge technology — examining a "
            "transparent holographic display with focused intensity, "
            "leaning over a sophisticated workstation as data reflects on "
            "her face, or in a thoughtful moment between an array of "
            "monitors. Setting: an ultra-modern AI lab with cool blue and "
            "warm gold ambient lighting from screens and architectural "
            "sources. She wears a stylish lab coat over a sophisticated "
            "outfit, or chic professional attire with rolled sleeves. "
            "Her expression: intensely focused, with a hint of fascination. "
            "Include atmospheric props: large monitors with data "
            "visualization (no readable text), advanced lab equipment, "
            "glass surfaces creating reflections."
        ),
        "market_business": (
            "Scene direction: A commanding female pharmaceutical executive "
            "in a moment of strategic presence — at the head of a boardroom "
            "table mid-presentation with confident posture, at a "
            "floor-to-ceiling window overlooking Tokyo skyline at twilight "
            "in contemplation, or in tense conversation with subtle "
            "intensity. Setting: a sleek modern corporate boardroom or "
            "executive suite with floor-to-ceiling windows showing the "
            "city skyline. Golden hour or evening blue hour lighting. "
            "She wears an elegant tailored business suit or sophisticated "
            "dress with a structured blazer. Her expression: composed, "
            "calculating, with a hint of strategic mischief. Include "
            "atmospheric props: sleek presentation materials, modernist "
            "furniture, the city skyline through the windows."
        ),
        "china": (
            "Scene direction: A sophisticated Chinese female pharmaceutical "
            "leader in a modern Chinese pharmaceutical or research "
            "environment — perhaps a cutting-edge Shanghai or Beijing "
            "research facility with subtle modern Chinese design elements. "
            "Cinematic lighting. She wears modern professional attire of "
            "elegant cut. Her expression: sharp, knowing, internationally "
            "polished. Include atmospheric props relevant to the news. "
            "Avoid traditional cultural cliché imagery."
        ),
        "general": (
            "Scene direction: A captivating female pharmaceutical "
            "professional in a striking moment representing the news "
            "theme. Strong professional pose with a touch of elegance. "
            "Photographically rendered atmospheric background. Her "
            "presence should immediately draw the viewer's eye."
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
