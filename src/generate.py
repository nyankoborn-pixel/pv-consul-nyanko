"""
generate.py - Gemini Flash を使ってコンサルにゃんこ口調でポスト生成
ニュース種別に応じてトーンを使い分ける(洞察ジョーク混ぜ版)
"""
import os
import yaml
import google.generativeai as genai


def load_character(config_path: str = "config/character.yml") -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def classify_news_category(entry: dict) -> str:
    """
    ニュースを5つのカテゴリに分類してトーンを決定する。
    返り値: 'regulatory' / 'ai_tech' / 'recall_safety' / 'market_business' / 'general'
    """
    text = f"{entry.get('title', '')} {entry.get('summary', '')} {entry.get('source_name', '')}".lower()
    
    # 回収・副作用は最優先(軽口NG領域)
    recall_kw = ["回収", "副作用", "副反応", "死亡", "重篤", "recall", "withdrawal", 
                 "adverse event", "safety alert", "使用上の注意", "改訂指示"]
    if any(kw in text for kw in recall_kw):
        return "recall_safety"
    
    # AI・技術
    ai_kw = ["ai", "人工知能", "機械学習", "machine learning", "llm", "生成ai",
             "generative", "automation", "自動化", "デジタル"]
    if any(kw in text for kw in ai_kw):
        return "ai_tech"
    
    # 規制・ガイダンス
    reg_kw = ["guidance", "guideline", "ガイダンス", "ガイドライン", "regulation",
              "規制", "fda", "ema", "pmda", "ich", "cioms", "通達", "通知", "発出"]
    if any(kw in text for kw in reg_kw):
        return "regulatory"
    
    # 市場・ビジネス
    market_kw = ["市場", "market", "億円", "億ドル", "billion", "million", "成長",
                 "growth", "シェア", "買収", "acquisition", "提携", "契約"]
    if any(kw in text for kw in market_kw):
        return "market_business"
    
    return "general"


def get_tone_instruction(category: str) -> str:
    """カテゴリ別のコメントトーン指示"""
    tones = {
        "regulatory": """
このニュースは規制・ガイダンス系です。commentary には以下のような
「コンサルあるある」「規制文書の読み方の裏読み」を軽く効かせてください:
 - 規制用語(検討する、適切に、速やかに等)に対する業界人的な穿った視点
 - 霞が関・DC・Brussels の温度感ジョーク
 - 「また添付文書が厚くなる」系の業界感覚
ただし、特定の役所・当局を直接揶揄する表現は避けること。
""",
        "ai_tech": """
このニュースはAI・技術系です。commentary には以下のような
「現場と経営層の温度差」「PoC疲れ」「実装の現実」を軽く効かせてください:
 - 「AIの前にまず紙とExcelが...」系の現場あるある
 - バズワードと実装ギャップへのゆるい皮肉
 - パイロット止まりの多さへの静かなツッコミ
""",
        "recall_safety": """
このニュースは回収・副作用・安全性の重大情報です。commentary は軽口を避け、
患者・医療関係者への配慮を示しつつ、静かで誠実なトーンで書いてください:
 - 「添付文書が一行増える」のような業界ならではの静かな感慨
 - 運用現場(安全性部門・MR)の実務への想像
軽いジョーク・ギャグ・自嘲は絶対に入れないこと。
""",
        "market_business": """
このニュースは市場・ビジネス系です。commentary には以下のような
「コンサル食い扶持ジョーク」「市場予測の常套句への軽い皮肉」を混ぜてください:
 - 「XX億ドル」「2033年までに」のような予測に対するゆるい距離感
 - 「我らコンサルの食い扶持」系の自嘲
 - 業界内で共通認識の「市場予測は外れるのが常」感
""",
        "general": """
commentary には、コンサル目線の静かな洞察や、業界人がニヤッとする一言を
混ぜてください。抽象的な一般論(「重要な課題です」等)は避け、
何か具体的な観点・角度を一つ入れること。
""",
    }
    return tones.get(category, tones["general"])


def build_prompt(entry: dict, character: dict) -> str:
    char = character["character"]
    category = classify_news_category(entry)
    tone_instruction = get_tone_instruction(category)
    
    prompt = f"""あなたは「{char['name']}」というキャラクターです。
以下のキャラ設定を厳密に守って、PVニュースのポストを日本語で生成してください。

【キャラクター設定】
- 名前: {char['name']}
- 口ぐせ: 「{char['catchphrase']}」
- 性格: {", ".join(char['personality'])} (ただし、"やさしい"は甘やかしではなく、業界人への共感を含む)
- スタイル: 静かに本質を見抜く執事猫。抽象的な一般論より、具体的な観点・業界あるあるを選ぶ
- 禁止事項:
{chr(10).join(f"  - {f}" for f in char['forbidden'])}

【今回のニュースカテゴリ】 {category}
{tone_instruction}

【厳守すべき制約】
1. 原文に書かれていない固有名詞・企業名・製品名・数値・日付を絶対に使用しないこと
2. 原文から推測できない事実は述べないこと
3. 特定の企業・役所・個人への誹謗中傷は避けること
4. 医療アドバイス・投資判断に関わる表現は避けること
5. summary部分は中立的な事実要約、断定を避け「〜とのこと」「〜と報告されています」を使う
6. 文字数: summaryは100字以内、commentaryは40字以内を目安
7. 出力は以下のJSON形式のみ。前後に説明文を付けないこと

【出力形式】
{{
  "summary": "ニュース内容の中立的な要約(事実のみ)",
  "commentary": "コンサルにゃんこ視点の一言コメント(カテゴリに応じたトーンで、抽象一般論を避ける)"
}}

【commentary 書き方のNG例】
  ❌ "医薬品の安全性確保は重要な課題です" (抽象一般論、面白みなし)
  ❌ "引き続き注視が必要でしょう" (誰でも書ける常套句)
  ❌ "本質を見極める必要があるでしょう" (口ぐせの劣化コピー)

【commentary 書き方のOK例(カテゴリ別)】
  ✓ (regulatory) "『適切に対応』と書かれるたび、実務部門の夜が長くなります"
  ✓ (ai_tech) "AI導入より先に、手作業Excelの棚卸しが必要かもしれません"
  ✓ (market_business) "『2033年までに』は、だいたい前倒しか延期のどちらかです"
  ✓ (recall_safety) "添付文書に一行追加。現場の対応表もまた更新ですね"

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1000]}
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
            "temperature": 0.7,  # 多様性を少し上げる
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
    
    if "summary" not in result or "commentary" not in result:
        raise RuntimeError(f"Gemini output missing required fields: {result}")
    
    # カテゴリ情報を付与(ログで確認できるように)
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
    最終的な投稿文を組み立て。
    X上限280字を保証するため、はみ出した分はsummaryを自動で切り詰める。
    """
    tags = select_hashtags(entry, character)
    hashtags_str = " ".join(tags)
    link = entry.get("link", "").strip()
    commentary = gen["commentary"]
    summary = gen["summary"]
    
    url_part = f"\n{link}" if link else ""
    fixed_part = f"\n\n🐾 {commentary}\n\n{hashtags_str}{url_part}"
    
    max_total = character.get("max_chars", 278)
    allowed_summary = max_total - len(fixed_part)
    
    if len(summary) > allowed_summary:
        if allowed_summary > 1:
            summary = summary[:allowed_summary - 1] + "…"
        else:
            summary = ""
    
    post = f"{summary}{fixed_part}"
    return post
