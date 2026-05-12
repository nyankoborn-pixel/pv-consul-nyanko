"""
generate.py - Gemini で要約+俳句+イラスト画像を生成
イラスト型: New Yorker satirical cartoon 風イラスト + 下部に 5-7-5 俳句オーバーレイ
PV関連性判定: 記事がPV/医薬品と無関係なら投稿スキップ
"""
import os
import io
import json
import re
import yaml
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

from paths import CHARACTER_YML


# ============================================================
# Pillow 描画設定
# ============================================================
IMAGE_W = 1200
IMAGE_H = 675
STRIP_RATIO = 0.48  # 下部俳句帯の開始位置 (画像高さに対する比)
HAIKU_FONT_SIZE = 70
HAIKU_LINE_GAP = 16
HAIKU_STROKE_WIDTH = 4

NOTO_FONT_PATHS = [
    # Ubuntu (GitHub Actions runner) — apt: fonts-noto-cjk
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJKjp-Bold.otf",
    "/usr/share/fonts/noto-cjk/NotoSansCJK-Bold.ttc",
    # Windows ローカル開発フォールバック
    r"C:\Windows\Fonts\NotoSansJP-VF.ttf",
    r"C:\Windows\Fonts\YuGothB.ttc",
]


# ============================================================
# 設定読み込み
# ============================================================
def load_character(config_path: str = CHARACTER_YML) -> dict:
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


# ============================================================
# Gemini クライアント
# ============================================================
def _get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    return genai.Client(api_key=api_key)


# ============================================================
# 投稿テキスト (summary) + 俳句 を生成するためのプロンプト
# ============================================================
def build_prompt(entry: dict, character: dict) -> str:
    char = character["character"]
    pc = character.get("prompt_config", {})

    domain_label = pc.get("domain_label", "PV(医薬品安全性監視)/医薬品/製薬業界")
    related_examples = pc.get("domain_related_examples", [])
    unrelated_examples = pc.get("domain_unrelated_examples", [])
    detection_keywords = pc.get("domain_detection_keywords", [])
    summary_audience = pc.get("summary_audience", "PV コンサル、製薬企業の安全性管理担当、規制当局関係者")
    acronym_rule = pc.get("acronym_rule",
                          "原文に明記されていない略語はフルスペルまたは一般用語で記述すること")

    related_block = "\n".join(f"- {x}" for x in related_examples) or "- (定義なし)"
    unrelated_block = "\n".join(f"- {x}" for x in unrelated_examples) or "- (定義なし)"
    detection_kw_block = ", ".join(f"「{k}」" for k in detection_keywords)

    prompt = f"""あなたは「{char['name']}」というキャラクターです。
このアカウントは「{domain_label}」関連ニュースを発信する X アカウントです。
ニュースの読者の手を止める日本語要約と、本質を切り取る 5-7-5 俳句を生成してください。

【キャラクター設定】
- 名前: {char['name']}
- 性格: {", ".join(char['personality'])}
- スタイル: 静かに本質を見抜く視点。データと業界知見で語る

【最初の判定 - 極めて重要】
このニュースが「{domain_label}」と直接関係あるかを判定してください。

関係ある例:
{related_block}

関係ない例:
{unrelated_block}

判定方法:
- 原文に {detection_kw_block} のいずれか、または該当領域の固有名詞が明示されている → "yes"
- 原文に上記がなく、強引にドメインに寄せないと書けない → "no"

【出力形式】
ドメインに関係ない場合:
{{
  "is_in_domain": false,
  "skip_reason": "なぜ無関係と判断したか短く記載"
}}

ドメインに関係ある場合:
{{
  "is_in_domain": true,
  "summary": "120-180字、フックのある日本語要約",
  "haiku": ["上句", "中句", "下句"]
}}

【summary 設計指針(is_pv_related=true の時のみ)- 極めて重要】
読者({summary_audience})の手をタイムライン上で止めることを最優先する。

書き方:
1. 冒頭1文目で「なぜこのニュースが面白いか」を提示する。
   役所主語(「○○省は」「PMDAは」等)で始めない。
   ニュースの主役(技術、企業、トレンド)を主語にする。
2. 数値・日付・固有名詞は原文に明記されている範囲で自由に使ってよい。
   {acronym_rule}
3. 末尾の汎用的な締め(「動向を注視」「今後に期待」等)は禁止。
4. 文末は「〜とのこと」「〜と報告されている」「〜と発表された」など。

【極めて重要な制約 - ハルシネーション防止】
summary には、原文に明示的に書かれている事実だけを記述すること。
以下を絶対に書かないこと:
- 原文に書かれていない「業界の見立て」「構造分析」「推測」「示唆」
- 原文に書かれていない他の事象との「連動」「影響」「波及」
- 原文に書かれていない「変化の可能性」「求められる対応」「今後の展開」
- 「示唆されている」「可能性がある」「求められる」「見られる」など
  推測を匂わせる表現で、原文にない内容を補完すること

原文が短いリード文しかなくても、それで書ける範囲だけで要約すること。
情報量が足りないと感じても、推測で補ってはならない。
要約が短くなる場合はそれでよい。

【厳守】
- 原文がドメインと無関係なら、無理に寄せず is_in_domain=false で返すこと。
- 投資・株価への直接的な誘導は禁止。
- 個別の医療行為アドバイス(「服用すべき」「投与中止」等)は禁止。

【haiku 設計指針】
- 3行 (上句 / 中句 / 下句) の俳句で記事本質を切り取る
- 目安は 5モーラ / 7モーラ / 5モーラ。拗音 (きゃ等) は1モーラ、促音と長音も1モーラ。
  厳密でなくとも良いが、各句は短く独立して読める形にすること。
- 季語不要、観察的・編集的視点
- summary と同じハルシネーション制約に従い、原文にない固有名詞・数値は使わない

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1500]}
ソース: {entry['source_name']}

最初に is_in_domain の判定をしてから、JSON形式で出力してください。
前後に説明文を付けないこと。
"""
    return prompt


def generate_post_content(entry: dict, character: dict) -> dict:
    client = _get_client()
    prompt = build_prompt(entry, character)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.85,
            top_p=0.95,
            max_output_tokens=4000,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    text = response.text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        result = json.loads(text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse Gemini JSON output: {e}\nRaw: {text}")

    # 旧キー is_pv_related も互換のため受け付ける
    in_domain = result.get("is_in_domain", result.get("is_pv_related"))
    if in_domain is False:
        skip_reason = result.get("skip_reason", "ドメイン外と判定")
        raise PVNotRelatedError(f"Skipped: {skip_reason}")

    if "summary" not in result or "haiku" not in result:
        raise RuntimeError(f"Gemini output missing required fields: {result}")

    haiku = result["haiku"]
    if not isinstance(haiku, list) or len(haiku) != 3:
        raise RuntimeError(f"haiku must be a list of 3 strings: {haiku}")
    if not all(isinstance(line, str) and line.strip() for line in haiku):
        raise RuntimeError(f"haiku lines must be non-empty strings: {haiku}")

    result["_category"] = classify_news_category(entry)
    return result


class PVNotRelatedError(Exception):
    """記事がPVと無関係と判定された場合のエラー"""
    pass


# ============================================================
# ハッシュタグ・親ポスト本文 (変更なし)
# ============================================================
def select_hashtags(entry: dict, character: dict) -> list:
    hashtags_config = character["hashtags"]
    tags = list(hashtags_config["always"])

    search_text = " ".join([
        entry.get("title", ""),
        entry.get("summary", ""),
        entry.get("source_name", ""),
    ]).lower()

    for rule in hashtags_config.get("conditional", []) or []:
        if not isinstance(rule, dict):
            continue
        triggers = [str(t).lower() for t in rule.get("triggers", [])]
        if not triggers:
            continue
        if any(t in search_text for t in triggers):
            rule_tags = rule.get("tags", [])
            if rule_tags:
                tags.append(rule_tags[0])

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


# ============================================================
# 画像生成: 俳句 → イラストプロンプト → Gemini Image → Pillow 合成
# ============================================================
_STYLE_LOCK = (
    "editorial illustration in the style of The New Yorker cover art, "
    "satirical cartoon, limited color palette of 2 to 4 muted colors, "
    "flat colors, hand-drawn line work, slightly textured paper feel"
)
_EXTRA_PROHIBIT = (
    "NO photo-realism, NO 3D CG, NO anime, NO manga, NO stock illustration look. "
    "Use only abstract, universal metaphors. Politically neutral composition"
)


def _build_image_prompt_request(haiku: list) -> str:
    return f"""You are commissioning a magazine cover illustration based on a Japanese haiku.

The haiku:
Line 1: {haiku[0]}
Line 2: {haiku[1]}
Line 3: {haiku[2]}

Style:
{_STYLE_LOCK}

Requirements:
1. Begin the image_prompt with this exact style string:
   "{_STYLE_LOCK}"
2. Include "16:9 landscape composition"
3. Composition must visually express the imagery and metaphor of the haiku above.
4. Stylized silhouette figures only for any humans; faces without realistic detail.
5. End with this exact prohibition block:
   "NO readable text, NO letters, NO numbers, NO logos, NO real brand names,
   NO real persons, NO national flags, NO political symbols, NO maps with country borders.
   {_EXTRA_PROHIBIT}."
6. 100-180 English words.

Output the image_prompt body only. No JSON, no markdown, no explanation."""


def _gen_image_prompt_from_haiku(client: genai.Client, haiku: list) -> str:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=_build_image_prompt_request(haiku),
        config=types.GenerateContentConfig(
            temperature=0.85,
            max_output_tokens=6000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    return response.text.strip()


def _gen_image_bytes(client: genai.Client, image_prompt: str) -> Optional[Image.Image]:
    response = client.models.generate_content(
        model="gemini-2.5-flash-image",
        contents=image_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio="16:9"),
        ),
    )
    if not response.candidates:
        return None
    cand = response.candidates[0]
    if not cand.content or not cand.content.parts:
        return None
    for part in cand.content.parts:
        if part.inline_data and part.inline_data.data:
            img = Image.open(io.BytesIO(part.inline_data.data)).convert("RGBA")
            return img.resize((IMAGE_W, IMAGE_H), Image.LANCZOS)
    return None


def _find_font_path() -> str:
    for p in NOTO_FONT_PATHS:
        if os.path.exists(p):
            return p
    raise RuntimeError(
        "No CJK font found. Install fonts-noto-cjk (Ubuntu) "
        f"or place a Noto Sans JP file. Tried: {NOTO_FONT_PATHS}"
    )


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    path = _find_font_path()
    f = ImageFont.truetype(path, size)
    try:
        f.set_variation_by_name("Bold")
    except Exception:
        pass
    return f


def _compose_with_haiku(illust: Image.Image, haiku: list) -> Image.Image:
    """イラストの下部にグラデーション帯を重ね、3行の俳句を白文字+黒輪郭で配置。"""
    canvas = illust.copy()
    W, H = canvas.size
    strip_top = int(H * STRIP_RATIO)

    layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    for y in range(strip_top, H):
        alpha = int(210 * ((y - strip_top) / (H - strip_top)))
        ld.line([(0, y), (W, y)], fill=(8, 8, 12, alpha))
    canvas = Image.alpha_composite(canvas, layer)

    d = ImageDraw.Draw(canvas)
    font = _load_font(HAIKU_FONT_SIZE)
    line_h = HAIKU_FONT_SIZE + HAIKU_LINE_GAP
    block_h = line_h * 3 - HAIKU_LINE_GAP
    y0 = strip_top + ((H - strip_top) - block_h) // 2
    for i, line in enumerate(haiku):
        tw = d.textlength(line, font=font)
        d.text(
            ((W - tw) // 2, y0 + i * line_h), line,
            fill=(252, 248, 232, 255), font=font,
            stroke_width=HAIKU_STROKE_WIDTH, stroke_fill=(0, 0, 0, 255),
        )
    return canvas


def generate_image(haiku: list, output_path: str = "/tmp/post_image.png") -> Optional[str]:
    """
    俳句から画像を生成する。
    1. Gemini Flash で俳句に基づく英語イラストプロンプトを生成
    2. Gemini 2.5 Flash Image でイラスト描画
    3. Pillow で下部に俳句オーバーレイ
    成功時は output_path を返す。失敗 (セーフティブロック等) は None。
    """
    if not haiku or not isinstance(haiku, list) or len(haiku) != 3:
        print(f"[image] invalid haiku input: {haiku}")
        return None

    try:
        client = _get_client()
    except RuntimeError as e:
        print(f"[image] {e}")
        return None

    try:
        image_prompt = _gen_image_prompt_from_haiku(client, haiku)
        print(f"[image] prompt[:140]: {image_prompt[:140]}...")
    except Exception as e:
        print(f"[image] image_prompt generation failed: {e}")
        return None

    try:
        illust = _gen_image_bytes(client, image_prompt)
    except Exception as e:
        print(f"[image] image generation failed: {e}")
        return None

    if illust is None:
        print("[image] empty response from image model (possible safety filter)")
        return None

    try:
        final = _compose_with_haiku(illust, haiku)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        final.convert("RGB").save(output_path, "PNG")
        print(f"[image] Saved to {output_path}")
        return output_path
    except Exception as e:
        print(f"[image] composition failed: {e}")
        return None
