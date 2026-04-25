"""
generate.py - Gemini で要約+画像プロンプト+画像を生成
The Rundown AI 型: 親ポストに画像、自リプライにソースURL
画像路線: 雑誌表紙風 + コンセプチュアル風刺(The Economist / The New Yorker 風)
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
    カテゴリ別の画像スタイル指示。
    路線: The Economist / The New Yorker 風の編集デザイン + コンセプチュアル風刺。
    雑誌表紙のような、強い隠喩を持つ一枚絵を狙う。
    """
    common_style = (
        "Style: Conceptual editorial cover illustration in the style of "
        "The Economist or The New Yorker. Strong metaphor, dramatic composition "
        "with strong contrast and depth. A single iconic visual symbol that "
        "tells the story at a glance. Bold use of negative space. "
        "Color palette: deep navy blue (#0E1B2E) as primary, gold (#C89D44) "
        "accents, with one bold accent color for emphasis. "
        "Modern, sophisticated, slightly surreal."
    )
    
    forbidden = (
        "AVOID: generic safety/medical iconography. AVOID cliché compositions "
        "like 'doctor with stethoscope', 'pills + warning sign', 'building + "
        "documents stacked', 'caduceus medical symbol', 'molecule + DNA helix'. "
        "AVOID flat infographic style. AVOID centered symmetrical layouts. "
        "AVOID generic 'professional business' clipart aesthetics."
    )
    
    category_metaphors = {
        "regulatory": (
            "Theme: regulatory power, oversight, governance shifting. "
            "Possible metaphors: a giant document casting a shadow over a city, "
            "scales tipping, threads connecting institutions, an oversized seal "
            "imprinting on industry, layers of paper forming a maze, ancient "
            "scrolls vs. digital screens. Find an unexpected angle."
        ),
        "ai_tech": (
            "Theme: AI transformation in pharma. Possible metaphors: a single "
            "AI eye scanning rows of pills, neural networks growing like roots "
            "from medication, a robot hand carefully holding a fragile vial, "
            "data streams flowing through medical environments, an algorithmic "
            "pattern emerging from chaos. Avoid generic 'brain + circuit' clichés."
        ),
        "market_business": (
            "Theme: corporate strategy, market dynamics, organizational shift. "
            "Possible metaphors: chess pieces on a pharmaceutical landscape, "
            "interlocking gears representing partnerships, a tower being "
            "rebuilt mid-air, paths diverging in a corporate landscape, "
            "weights tipping a balance. Should feel strategic and consequential."
        ),
        "china": (
            "Theme: China's pharmaceutical and regulatory rise. Possible "
            "metaphors: traditional Chinese pattern merging with modern AI "
            "elements, a dragon coiled around a pharmaceutical symbol, "
            "ascending steps in oriental aesthetic, ink wash style mixed with "
            "circuit patterns. Respectful, not stereotypical."
        ),
        "general": (
            "Theme: pharmaceutical industry shift or insight. Find a strong, "
            "specific visual metaphor for the news content. Avoid generic "
            "'health and medicine' imagery."
        ),
    }
    
    metaphor = category_metaphors.get(category, category_metaphors["general"])
    
    return f"{common_style} {metaphor} {forbidden}"


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
4. summaryは中立的な事実要約。断定を避け「〜とのこと」「〜と報告されています」「〜と発表されました」を用いる
5. 文字数: summaryは150字以上180字以内(主体・出来事・重要点を必ず含めること)
6. 出力は以下のJSON形式のみ。前後に説明文を付けないこと

【出力形式】
{{
  "summary": "150-180字の事実要約",
  "image_prompt": "英語の画像生成プロンプト(下記の制約厳守、80-120 words程度)"
}}

【image_prompt 設計指針 - 極めて重要】
このニュースの「本質」を視覚的に表現する**1つの強い隠喩シーン**を考案する。
平凡な医療シンボルの組み合わせ(薬+警告、医者+聴診器、ビル+書類)は禁止。
The Economist や The New Yorker の表紙のような、見る人を立ち止まらせる
コンセプチュアル・イラストを狙う。

スタイル指示:
{image_style}

【image_prompt の必須要件】
- ニュース内容を1つの具体的シーン・隠喩で表現すること
- "abstract" "professional" "clean" だけで終わらせず、何を描くか明確にすること
- Aspect ratio: 16:9 landscape
- NO text, NO letters, NO numbers, NO logos
- NO mascot characters, NO anthropomorphic animals
- NO real human faces or identifiable people (silhouettes or stylized figures OK)
- Length: 80-120 English words

【image_prompt 良い例】
ニュース: 「PMDA、シグナル検出にAI活用のガイダンス案を公表」
→ "Conceptual editorial cover illustration in the style of The Economist. 
   A single glowing AI eye scanning rows of pharmaceutical pills arranged 
   like an audience, with ripples of data emanating outward. Deep navy 
   background with gold accents and a single emerald glow from the eye. 
   Dramatic side lighting. Strong negative space on the right. 16:9. 
   No text, no characters, no logos. The AI eye should feel surveillant 
   yet not threatening — observing, classifying, reporting."

ニュース: 「武田薬品、PV部門を再編しグローバル統合」
→ "Conceptual editorial illustration in The New Yorker style. A massive 
   abstract globe made of interconnecting puzzle pieces, with one piece 
   floating above being slotted into place by an unseen hand. Deep navy 
   tones with gold seams between pieces. Cinematic dramatic lighting from 
   above. The composition emphasizes scale and consequence. 16:9. 
   No text, no faces, no logos."

【image_prompt 悪い例(絶対避ける)】
- "abstract pharmaceutical elements, clean professional style" (平凡で何も描かれない)
- "molecules and DNA helix in blue background" (使い古された医療クリシェ)
- "doctor holding stethoscope" (人物クリシェ)
- "pills with warning signs" (使い古された安全性クリシェ)
- "infographic of safety data" (フラットインフォグラフィック)

【原文情報】
タイトル: {entry['title']}
要約: {entry['summary'][:1500]}
ソース: {entry['source_name']}

上記の原文情報のみを根拠として、JSONを出力してください。
画像プロンプトでは、このニュースの本質を象徴する**1つの強い視覚的隠喩**を必ず考案してください。
"""
    return promp
