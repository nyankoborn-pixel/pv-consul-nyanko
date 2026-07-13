# CLAUDE.md — pv-consul-nyanko 運用ハンドブック

このリポジトリで作業を引き継ぐ Claude セッション向けの完全ガイド。
運用書 v4(`C:\Users\User\OneDrive\デスクトップ\過去PV記事の自動投稿機能メンテナンスマニュアル_v4.docx`)の内容を要約し、直近の実装状態を反映している。齟齬がある場合は本書のほうが新しい。

---

## 1. システム概要

X (旧 Twitter) に PV(医薬品安全性監視)関連ニュースを自動投稿する Bot。
現在稼働中のアカウント:

| アカウント | 用途 | 実運用状態 |
|---|---|---|
| **@NyankoPv** | PV / 医薬品 / 製薬業界ニュース | 稼働中(1日3回・朝08:00 / 昼13:00 / 夜21:00 JST) |
| **@AI_news2000** | AI / LLM / AIビジネスニュース | **停止中**(新規アカウントの X 側 Bot 判定 403 が連発、Premium 未契約のため運用停止) |

投稿形式は「日本語要約(120-180字) + ハッシュタグ + 5-7-5 俳句をオーバーレイした New Yorker 表紙風イラスト」。ソース URL は親ポストの自リプライで別送。

## 2. リポジトリ構成

```
pv-consul-nyanko/
├── .github/workflows/
│   └── post-nyanko.yml        # nyanko 用ワークフロー (workflow_dispatch のみ)
│                              # ※ post-ai.yml は 2026-05-16 に削除済
├── config/
│   ├── nyanko/
│   │   ├── character.yml      # キャラクター設定 + prompt_config (ドメイン判定)
│   │   ├── sources.yml        # RSS ソース定義 (Google News 検索 + FDA/EMA 公式)
│   │   ├── keywords.yml       # スコアリング用キーワード + 重み
│   │   └── restricted_domains.yml  # 会員専用ドメイン + blocked_domains + blocked_title_patterns
│   └── ai/                    # AI アカウント設定 (現在停止中でも保持)
│       ├── character.yml
│       ├── sources.yml
│       ├── keywords.yml
│       └── restricted_domains.yml
├── logs/
│   ├── nyanko/posted.jsonl    # 投稿履歴 (重複防止 + 監査用)
│   └── ai/posted.jsonl
├── src/
│   ├── paths.py               # ACCOUNT_NAME 環境変数でパス切替
│   ├── main.py                # オーケストレーター (fetch → score → generate → post)
│   ├── fetch_news.py          # RSS 収集 (User-Agent 偽装)
│   ├── score.py               # スコアリング + dedup + 除外フィルタ
│   ├── generate.py            # Gemini で要約+俳句+イラスト生成、Pillow 合成
│   ├── validate.py            # 固有名詞・文字数・禁止表現の検証
│   ├── post_x.py              # X API v2 で投稿 (tweepy)
│   └── filter_restricted.py   # 会員専用/blocked domain・title 判定
└── requirements.txt
```

## 3. パイプライン全体像

`src/main.py` の `run(dry_run)` が以下の順で処理する:

1. **fetch** — `fetch_news.fetch_all_sources()`:
   - `config/{ACCOUNT_NAME}/sources.yml` の RSS を全件取得(1ソース top10 件)
   - User-Agent は Chrome を偽装(Google News に弾かれないため)
   - 日付フィルタは補助的にのみ適用(古すぎる記事はスコア側で除外)
2. **score** — `score.score_entries()`(詳細は §4)
   - スコア降順で並び、上位 `MAX_RETRIES=15` 件が候補になる
3. **候補ループ**(main.py の for 内):
   - `filter_restricted.is_member_only_article()` で会員記事チェック
   - `generate.generate_post_content()` で LLM に投稿本文+俳句 JSON を生成させる
   - `validate.validate_post()` で固有名詞・文字数・禁止表現をチェック
   - `generate.generate_image()` で俳句 → イラストプロンプト → Gemini Image → Pillow 合成
   - 上記のどこかで落ちたら次候補へ。画像生成失敗もスキップ(テキストのみ投稿の救済はナシ)
4. **投稿**:
   - `post_x.post_to_x()` で親ポスト(画像付き)を投稿
   - 5秒待って `post_x.post_reply()` でソース URL を自リプライ
5. **ログ記録** — `logs/{ACCOUNT_NAME}/posted.jsonl` に追記
6. **workflow が git commit + push** して posted.jsonl を主枝に残す

## 4. スコアリングロジック(`src/score.py`)

各エントリのスコア = `source_weight + keyword_score + recency_bonus`

- **source_weight**: `sources.yml` で各ソースに割り振った 5〜10 の重み
- **keyword_score**: `keywords.yml` の全キーワードを本文にマッチさせた合計。マイナス重みキーワードは実質除外
- **recency_bonus**:
  - 7日以内: +5
  - 8-30日: 0
  - 31-90日: -5
  - 91-365日: -15(実質除外扱い、`recency_bonus <= -25` で `too_old` にカウント)
  - >365日: -30

その後、以下の除外フィルタが順に適用される(2026-05-16 現在):

| 順序 | 除外理由 | 実装 |
|---|---|---|
| 1 | `blocked_domain` | URL のドメインが `restricted_domains.yml`.blocked_domains に含まれる |
| 2 | `blocked_title` | title が `restricted_domains.yml`.blocked_title_patterns の正規表現に一致 |
| 3 | `posted_link` | link が過去投稿 log に完全一致 |
| 4 | `posted_title` | title の正規化(NFKC → 末尾媒体名剥がし → 空白除去 → 小文字化)が過去投稿と一致 |
| 5 | `recent_entity` | title から抽出した固有名詞(GPT-5, F351, OpenAI 等)が直近 5 日の投稿 title と重複 |
| 6 | `too_short` | title + summary が 100 文字未満(会員リード文だけの記事) |
| 7 | `too_old` | recency_bonus <= -25 |
| 8 | `negative_score` | 合計スコアが負(除外キーワードが優勢) |

`ENTITY_DEDUPE_WINDOW_DAYS = 5`。業界共通略語(FDA / PMDA / GVP / LLM / AI / DX 等)は `_ENTITY_STOPWORDS` でエンティティ扱いしないよう除外(それらで dedup すると正常記事まで弾いてしまう)。

## 5. 除外設定(`config/{account}/restricted_domains.yml`)

`restricted_domains` は「該当ドメイン × summary 短文なら会員記事」判定用。
`blocked_domains` は「無条件で除外するドメイン」用。
`blocked_title_patterns` は「タイトルが正規表現マッチしたら無条件除外」用。

2026-05-16 現在の nyanko 側 blocked_domains:

```
finance.yahoo.co.jp    # 掲示板系
textream.yahoo.co.jp
5ch.net
bbs.kakaku.com
newscast.jp            # PR/リリース配信
prtimes.jp
dreamnews.jp
atpress.ne.jp
value-press.com
news2u.net
kabu-ir.com            # IR 集約
kabushiki.jp
```

blocked_title_patterns 抜粋:
- 掲示板系: `掲示板`
- セミナー/告知: `セミナー` `ウェビナー` `ウェビナ` `説明会` `勉強会` `オンライン講座` `【M/D 公開】` `【公開】` `公開予定`
- 市場調査レポート: `市場規模` `市場は…に達する` `に達する見込み` `年平均成長率` `CAGR` `市場調査レポート` `市場レポート` `予測.*XXXX年`
- 回顧記事: `N年前` `を振り返る` `あの時` `あのとき`

新たなゴミパターンが見つかったらここに正規表現を追加する運用。フィルタ変更時は必ずローカルで **正規記事4件が誤ブロックされないか** テストしてから push すること。

## 6. LLM プロンプト設計(`src/generate.py`)

### 6.1 build_prompt (要約 + 俳句)
- `character.yml` の `prompt_config` セクションでドメイン(PV / AI)を切替
- 出力形式(JSON):
  - `is_in_domain: false` の場合 → `skip_reason` を書いて `PVNotRelatedError` で次の候補へ
  - `is_in_domain: true` の場合 → `summary`(120-180字)+ `haiku`([上句, 中句, 下句])
- ハルシネーション防止のため「原文に書かれた事実のみ」と厳命
- 旧キー `is_pv_related` も互換受付
- 俳句は「目安 5-7-5」でモーラ厳密ではない(Gemini は日本語モーラを守れない)

### 6.2 画像生成
- 俳句を入力に、別の Gemini Flash 呼び出しで New Yorker 表紙風の英語 image_prompt を生成
- Gemini 2.5 Flash Image で 16:9 レンダリング
- Pillow で下部に俳句オーバーレイ:
  - フォント: Noto Sans JP Bold(Ubuntu では `fonts-noto-cjk` を apt で導入)
  - 70px 白文字 + 4px 黒 stroke(モバイル表示での視認性のため 42→70 に増強済)
  - グラデーション帯を下部 38% に敷いて可読性確保
- セーフティフィルタで空応答なら None を返し、main.py が次候補へ

## 7. スケジューリング

**GitHub Actions の schedule cron は本リポで安定発火しない**(2026-04-26 以降ほぼ発火せず)。
そのため cron-job.org の **workflow_dispatch トリガー呼び出し**運用に回帰済(2026-05-13)。

cron-job.org 現在のジョブ一覧(2026-05-16):

| ジョブ名 | 発火時刻 (JST) | ターゲット | 状態 |
|---|---|---|---|
| X Auto Post (Morning) | 08:00 | post-nyanko.yml | Active |
| X Auto Post (Noon) | 13:00 | post-nyanko.yml | Active |
| X Auto Post (Night) | 21:00 | post-nyanko.yml | Active |
| AI News Auto Post (Morning) | 08:00 | (削除済ワークフロー) | **Disabled** |
| Video Auto Post (Morning/Noon/Night) | 20:00 | pv-consul-nyanko-video/auto_post.yml | Active |
| TechGossip Auto Post (4 times daily) | 19:00 | pv-consul-nyanko-video/auto_post_techgossip.yml | Active |
| Trend Clipper Auto Post | — | 別リポ | Inactive |

投稿時刻を変えるのは **cron-job.org のダッシュボード**で操作すること。post-nyanko.yml の schedule ブロックは削除済で workflow_dispatch のみ。

## 8. GitHub Secrets(pv-consul-nyanko リポ)

| Secret 名 | 用途 | 状態 |
|---|---|---|
| `GEMINI_API_KEY` | Gemini text + image 両方 | Active |
| `X_API_KEY` / `X_API_SECRET` | @NyankoPv の X OAuth 1.0a コンシューマー | Active |
| `X_ACCESS_TOKEN` / `X_ACCESS_TOKEN_SECRET` | 同アクセストークン | Active |
| `X_API_KEY_AI` / `X_API_SECRET_AI` | @AI_news2000 用(現在未使用、保持だけ) | Active |
| `X_ACCESS_TOKEN_AI` / `X_ACCESS_TOKEN_SECRET_AI` | 同上 | Active |

`post-nyanko.yml` は前者4本を `X_API_KEY` 等の env 名で `post_x.py` に渡す。AI 用は post-ai.yml 削除で参照者不在。

## 9. 依存関係(`requirements.txt`)

```
feedparser==6.0.11
requests==2.32.3
tweepy==4.14.0
PyYAML==6.0.2
python-dateutil==2.9.0
google-genai>=1.0.0        # text + image 両方これに統一(google-generativeai は削除済)
Pillow>=10.0.0             # 俳句オーバーレイ合成
```

Ubuntu runner では `fonts-noto-cjk` を apt-install するステップが post-nyanko.yml に含まれている(Pillow の日本語描画に必須)。

## 10. コスト(月額目安)

| 項目 | 月額 | 備考 |
|---|---|---|
| X Premium (@NyankoPv) | ¥1,380 | 投稿制限回避のため必要 |
| X API PPU (@NyankoPv) | $1〜$2(¥150〜¥300) | 投稿1件 $0.01-0.02 × 90/月 |
| Gemini API | ¥0 | 無料枠 500 RPD 内(1投稿あたり text 2 コール + image 1 コール = 3 コール、90投稿 × 3 = 270/月) |
| GitHub Actions | ¥0 | Public リポなので無制限 |
| cron-job.org | ¥0 | 無料プラン |
| **合計** | **約 ¥1,500〜¥1,700** | ほぼ X Premium |

## 11. 関連リポジトリ

### pv-consul-nyanko-video(YouTube Shorts 生成)
- ローカル: `C:\Users\User\Documents\GitHub\pv-consul-nyanko-video`
- pv-consul-nyanko の `logs/nyanko/posted.jsonl` を fetch して動画スクリプトを生成
- 2026-05-12 のマルチアカウント refactor 直後、旧パス `logs/posted.jsonl` を fetch していて 404 で落ちた実績あり(現在は修正済)
- 立ち絵 emotion 切替を実装(コンサルにゃんこの動画版)

### pv-consul-nyanko(本体、このリポ)
- X 投稿のオリジナル

## 12. 直近の重要な変更履歴

| 日付 | 変更内容 | 実施理由 |
|---|---|---|
| 2026-05-12 | マルチアカウント refactor + 俳句イラスト化 + AI アカウント追加 | 元の女性写真を刷新、新アカウント運用開始 |
| 2026-05-12 | タイトル正規化 dedup 追加 | Google News RSS が同記事に別 URL を返すため |
| 2026-05-13 | GitHub Actions schedule → cron-job.org へ回帰 | schedule が安定発火しない |
| 2026-05-15 20:20 | blocked_domains / blocked_title / recent_entity dedup 追加 | 掲示板・セミナー告知・回顧記事・F351 連投対策 |
| 2026-05-16 13:56 | post-ai.yml 削除 + cron-job.org の AI News ジョブ無効化 | @AI_news2000 の X Bot 判定 403 が連発、Premium 未契約のため完全停止 |
| 2026-05-16 | PR配信ドメイン (newscast.jp / prtimes.jp 等)と市場調査レポート系タイトル(CAGR / 市場規模等)を除外リストに追加 | 5/16 朝の Newscast.jp「医薬品市場規模2034年」広告投稿対策 |

## 13. 定期メンテナンス

| 頻度 | タスク |
|---|---|
| 毎日(自動) | GitHub Actions の失敗通知メールを確認、失敗ならログ確認 |
| 週1 | @NyankoPv の直近投稿を目視確認、変な投稿・低品質ソースが混入していないかチェック |
| 月1 | X Developer Console でクレジット残高確認($1 切ったら再チャージ) |
| 月1 | Google AI Studio で Gemini 使用量確認 |
| 随時 | 新種のゴミが投稿されたら `blocked_domains` / `blocked_title_patterns` に追加(パターンが増えるモグラ叩き運用は許容) |

## 14. トラブルシューティング

### 14.1 X API 402 Payment Required
- X Developer Console でクレジット残高を確認、$0 なら入金
- 「自動チャージ」を有効にしておくと再発しない

### 14.2 X API 403 Forbidden(新規アカウント)
- 運用書 v3 付録 C に記録あり。新規アカウントの Bot 判定で発生
- 解決策: X Premium 契約(該当アカウントで)
- @AI_news2000 はこのパターンで運用停止済

### 14.3 Google Actions schedule が発火しない
- 既知問題。本リポは cron-job.org 経由で workflow_dispatch を叩く運用
- schedule ブロックは post-nyanko.yml から削除済

### 14.4 Gemini Image 空応答(セーフティフィルタ)
- 政治・地名・企業固有名詞で稀に発生
- main.py の MAX_RETRIES=15 で次候補に自動遷移
- 15件全滅は稀

### 14.5 GitHub Actions 失敗メールが出るがログを見ると成功
- ワークフロー内の Post Setup 系ステップの warning が誤誘導している可能性
- 実際のエラーは `Run post (nyanko)` ステップの exit code で判定

### 14.6 ゴミ記事が投稿される
- sources / keywords / スコアロジックは変更しないのが原則
- 対応は `blocked_domains` / `blocked_title_patterns` への追加で対処
- パターンを追加した後、既知の正規記事4件くらいで誤ブロックしないか regex テストを回してから push すること

## 15. 引き継ぎ時の注意点(Claude セッション向け)

1. **本 CLAUDE.md はローカルの手元コピー(`C:\Users\User\Documents\GitHub\pv-consul-nyanko-work\CLAUDE.md`)にある。リポの main にも push すること。**
2. **sources.yml / keywords.yml / スコアリング係数は理由なく変更しない**(2026-05-12 以降ノータッチ、フィルタ追加のみで対応してきた)
3. **schedule cron は追加しない**(post-nyanko.yml に schedule ブロックが復活していたら削除する。cron-job.org と二重発火する)
4. **@AI_news2000 の投稿再開には X Premium 契約 → post-ai.yml 復活 → cron-job.org ジョブ有効化 の3手順が必要**
5. **posted.jsonl は末尾追記のみ、既存行を削除・編集しない**(dedup キーとして機能している)
6. **フィルタ変更後は必ずローカルで regex テスト**(過去のゴミがブロックされるかつ正規記事4件が通過するか確認、`python -c` で1-shot)
7. **Boss(ユーザー)への応答は丁寧語**、簡潔(冗長な表・見出しを避ける)、確認は最低限まとめて即実行、結果は 1-2 行で報告
8. **メモリの `feedback_*.md` にも Boss のスタイル・NG事項が記録されている**ので参照すること

---

最終更新: 2026-05-16 by Claude Opus 4.7
