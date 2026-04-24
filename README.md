# PV Consul Nyanko - PVニュース自動投稿システム

「コンサルにゃんこ」キャラクターで、PV(ファーマコビジランス)関連ニュースを朝昼夜自動投稿するシステム。

## 特徴

- **完全無料構成**: GitHub Actions + Gemini Flash + RSS + X API Free
- **一次情報優先**: FDA / EMA / PMDA / RAPS / PubMed のRSSのみ利用
- **4段階の防御策**:
  1. ニュースソースを信頼できる一次情報のみに限定
  2. LLMプロンプトで原文ベースの生成を厳命
  3. 固有名詞マッチング検証(原文にない企業名・製品名を使ったらリジェクト)
  4. 禁止表現・文字数チェック
- **キャラクター**: コンサルにゃんこ(静かで知的なPV執事猫)
- **AI生成明示**: 全投稿に `#AI生成` ハッシュタグ自動付与

## 投稿スケジュール

- 朝 8:00 JST
- 昼 12:30 JST
- 夜 21:00 JST

## セットアップ手順

### 1. GitHubリポジトリ作成

1. このフォルダをそのままGitHubの新規リポジトリにpush
2. Public推奨(GitHub Actions無料枠が2000分/月で十分)
3. **⚠ 重要**: APIキーをコードに書かないこと(Secretsで管理)

### 2. APIキー取得

#### X (Twitter) API - Free tier
1. https://developer.x.com/ でデベロッパー登録
2. Project → App 作成
3. **App permissions を "Read and Write" に変更**(必須)
4. Keys and tokens から以下を取得:
   - API Key & Secret
   - Access Token & Secret (Read and Write権限で再生成)

#### Gemini API
1. https://aistudio.google.com/ でAPIキー作成
2. 無料枠で十分(Gemini 2.0 Flash Experimental)

### 3. GitHub Secrets登録

リポジトリの `Settings → Secrets and variables → Actions` に登録:

| Secret名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Gemini APIキー |
| `X_API_KEY` | X API Key |
| `X_API_SECRET` | X API Secret |
| `X_ACCESS_TOKEN` | X Access Token |
| `X_ACCESS_TOKEN_SECRET` | X Access Token Secret |

### 4. 動作確認

GitHub Actionsの `Actions` タブから `PV Consul Nyanko Auto Post` を選び、
`Run workflow` → `dry_run: true` で手動実行。

ログを確認し、生成されたポスト文に問題がなければ、`dry_run: false` で実際投稿をテスト。

## ローカルテスト

```bash
# 依存インストール
pip install -r requirements.txt

# 環境変数設定(.envファイルを作成するか、直接export)
export GEMINI_API_KEY=...
export X_API_KEY=...
# ... (他のX関連キー)

# Dry run(X投稿なし、生成内容だけ確認)
python src/main.py --dry-run

# 本番投稿
python src/main.py
```

## ディレクトリ構成

```
pv-consul-nyanko/
├── .github/workflows/post.yml    # スケジューラ
├── src/
│   ├── main.py                    # オーケストレーター
│   ├── fetch_news.py              # RSS収集
│   ├── score.py                   # 話題性スコアリング
│   ├── generate.py                # Gemini Flash生成
│   ├── validate.py                # 防御策: 検証ロジック
│   └── post_x.py                  # X投稿
├── config/
│   ├── sources.yml                # ニュースソース設定
│   ├── keywords.yml               # スコアリング用キーワード
│   └── character.yml              # キャラ設定
├── logs/
│   └── posted.jsonl               # 投稿履歴(重複防止に利用)
└── requirements.txt
```

## カスタマイズ

### キーワード調整
`config/keywords.yml` で関心領域の重みを調整。

### ニュースソース追加
`config/sources.yml` に新しいRSSを追加。ソースの重みは1-10で設定。

### キャラトーン調整
`config/character.yml` の `style_guidelines` / `forbidden` を編集。

### 投稿時刻変更
`.github/workflows/post.yml` の cron 式を編集。**UTC指定であることに注意**。

## 制限事項・注意点

1. **X API Free tier**: 月500ポストまで。日3件 × 30日 = 90件で余裕だが、Retweet/Like/Readは不可
2. **Gemini無料枠**: リクエスト制限あり。日3回なら余裕
3. **PV領域の固有名詞精度**: Gemini Flashはたまに固有名詞を取り違えるが、validate.pyで弾く設計
4. **GitHub Actions cron遅延**: 数分〜十数分の遅延が発生することあり(GitHub側の仕様)
5. **X API仕様変更リスク**: Muskの方針で仕様が変わる可能性あり。エラー時はログで確認

## トラブルシューティング

### 投稿が止まっている
- GitHub Actions の `Actions` タブで失敗ログを確認
- X APIの利用状況を Developer Portal で確認
- `logs/posted.jsonl` の最終エントリを確認

### 検証で常にリジェクトされる
- `validate.py` の `WHITELIST` に許可する用語を追加
- Geminiのプロンプトを調整(`generate.py`)

### キャラトーンがブレる
- `config/character.yml` の制約を明確化
- Geminiの `temperature` を下げる(`generate.py`)

## ライセンス

社内利用前提。
