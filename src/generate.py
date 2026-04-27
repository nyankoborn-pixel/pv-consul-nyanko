"""
generate.py - Gemini で要約+画像プロンプト+画像を生成
The Rundown AI 型: 親ポストに画像、自リプライにソースURL
画像路線: 夜景 × 歩き × 低めアングル × 高級ファッション写真
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
    画像スタイル: 夜景 × 歩き × 低めアングル × 高級ファッション写真
    """
def get_image_style_for_category(category: str) -> str:
    """
    画像スタイル: リアル寄せ強化版
    """

    base_style = """
STYLE:
Ultra-photorealistic cinematic studio photography.
Looks like a real high-end editorial photograph shot with a full-frame cinema camera.
Natural skin pores, subtle skin texture, realistic facial asymmetry, realistic hair strands,
real fabric wrinkles, believable body proportions, realistic hands and fingers.
No plastic skin, no doll-like face, no AI-glossy texture, no over-smoothed beauty filter.
NOT anime, NOT manga, NOT illustration, NOT 3D render, NOT cosplay poster.

SUBJECT:
A single East Asian woman, appears to be 25 years old or younger. She has a fresh, youthful, yet intelligent and confident original face.
She has an original face and must not resemble any real celebrity, model, public figure,
anime character, game character, or fictional character.
Her expression is calm, intelligent, confident, and professional.

WARDROBE:
A refined fashion outfit inspired by Japanese sailor-uniform design,
reinterpreted as an adult editorial fashion look.
Elegant, neat, tailored, modest, and non-explicit.
No fetish styling, no overly short skirt, no exposed underwear.

POSE:
Confident cinematic editorial pose.
Natural shoulder angle, relaxed hands, composed posture.
Elegant and professional, not provocative.

CAMERA:
Aspect ratio: 16:9 landscape.
Shot on an 85mm lens, full-frame camera, shallow depth of field.
Three-quarter body framing.
Camera slightly below eye level.
Subject occupies 40-55% of the frame.

LIGHTING:
Soft cinematic lighting.
Cool blue rim light + soft key light on the face.
Realistic reflections on glass and lab equipment.
Natural shadow falloff.

BACKGROUND:
Modern pharmaceutical AI laboratory at night.
Glass walls, city skyline, lab benches, beakers, sealed document folders.
Holographic-style panels (no readable text).
No logos, no letters, no numbers.

REALISM REQUIREMENTS:
Photorealistic original human face.
Realistic eyes with natural catchlights.
Correct anatomy, realistic hands, natural pose.
Professional cinematic color grading.

ABSOLUTE PROHIBITIONS:
No minors.
No anime, manga, cartoon, illustration, 3D rendering.
No readable text, no letters, no numbers, no logos.
No multiple people.
""".strip()

    category_scenes = {
        "regulatory": """
CATEGORY SCENE:
Subtle regulatory atmosphere with sealed document folders and corporate glass interiors.
The subject appears to be leaving a high-level regulatory meeting.
""".strip(),

        "ai_tech": """
CATEGORY SCENE:
Futuristic pharmaceutical AI environment with abstract data panels and lab equipment.
No readable text.
""".strip(),

        "market_business": """
CATEGORY SCENE:
Luxury corporate environment with high-rise buildings and executive interiors.
""".strip(),

        "china": """
CATEGORY SCENE:
Modern East Asian biotech city environment with glass research facilities.
""".strip(),

        "general": """
CATEGORY SCENE:
Modern pharmaceutical business environment at night.
Clean, cinematic, professional atmosphere.
""".strip(),
    }

    return f"{base_style}\n\n{category_scenes.get(category, category_scenes['general'])}"


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
  "image_prompt": "180-260 words、英語の画像プロンプト"
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
summary には、原文に明示的に書かれている事実だけを記述すること。
以下を絶対に書かないこと:
- 原文に書かれていない「業界の見立て」「構造分析」「推測」「示唆」
- 原文に書かれていない他の制度・施策との「連動」「影響」「波及」
- 原文に書かれていない「変化の可能性」「求められる対応」「今後の展開」
- 「示唆されている」「可能性がある」「求められる」「見られる」など
  推測を匂わせる表現で、原文にない内容を補完すること

原文が短いリード文しかなくても、それで書ける範囲だけで要約すること。
情報量が足りないと感じても、推測で補ってはならない。
要約が短くなる場合はそれでよい。

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
- Photorealistic original human face required
- NO text, NO letters, NO numbers, NO logos
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
    
    if result.get("is_pv_related") is False:
        skip_reason = result.get("skip_reason", "PVと無関係と判定")
        raise PVNotRelatedError(f"Skipped: {skip_reason}")
    
    if "summary" not in result or "image_prompt" not in result:
        raise RuntimeError(f"Gemini output missing required fields: {result}")
    
    result["_category"] = classify_news_category(entry)
    return result


class PVNotRelatedError(Exception):
    """記事がPVと無関係と判定された場合のエラー"""
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
    親ポストの本文を組み立て
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
    Gemini 2.5 Flash Image で画像生成
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
