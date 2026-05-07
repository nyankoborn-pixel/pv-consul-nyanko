# 一時切替リバート手順 (2026/5/7 → 2026/5/14)

## 経緯

2026年5月7日、ユーザー指示により @NyankoPv の自動投稿テーマを通常の
PV(医薬品安全性監視)領域からハンタウイルス感染症情報に1週間切り替えた。

切替直前の状態は git tag **`pre-hantavirus-2026-05-07`** に保存済み。

## 影響を受けたファイル

| ファイル | 変更内容 |
|---|---|
| `config/sources.yml` | RSSソース全置換(ハンタウイルス・感染症系のみ) |
| `config/keywords.yml` | スコアリングキーワード全置換 |
| `config/character.yml` | always ハッシュタグを `#ハンタウイルス #感染症` に変更 / forbidden に「不安を煽る表現」追加 |
| `config/url_override.yml` | 新規追加(初回起動時のJIHSリスク評価URL指定用、投稿後 `enabled: false` に自動書換) |
| `src/main.py` | `url_override` モード追加 |
| `src/generate.py` | `classify_news_category` に "outbreak" カテゴリ追加 / `is_pv_related` 判定プロンプトを「感染症 OR PV」に拡張 / 画像スタイルに outbreak シーン追加 / `_url_override` フラグ時は判定スキップ |
| `src/validate.py` | WHITELIST に `ECDC, CDC, PAHO, JIHS, FORTH, PublicHealth, Outbreak, DiseaseOutbreakNews` 追加 |

## リバート手順 (2026/5/14 以降に実施)

### 方法1: タグからファイルを復元(推奨)

```bash
git checkout main
git pull
git checkout pre-hantavirus-2026-05-07 -- \
  config/sources.yml \
  config/keywords.yml \
  config/character.yml \
  src/main.py \
  src/generate.py \
  src/validate.py
git rm config/url_override.yml
git rm REVERT_NOTES.md
git commit -m "revert: end hantavirus 1-week special, restore PV defaults"
git push origin main
```

### 方法2: 個別に手動で戻す

`pre-hantavirus-2026-05-07` タグの各ファイルを GitHub 上で表示してコピペ。

## チェックリスト (リバート後)

- [ ] `config/sources.yml` の sources が PV関連 (PMDA / GVP / 製薬企業) に戻っている
- [ ] `config/keywords.yml` の `ハンタウイルス` 単独加点が除去されている
- [ ] `config/character.yml` の always が `#Pharmacovigilance #DrugSafety` に戻っている
- [ ] `src/main.py` から url_override 関連コードを残しても良いが、`config/url_override.yml` は削除してよい
- [ ] dry_run で1回確認
- [ ] 通常cronで本番投稿が PV ニュースになっていることを目視確認

## 残課題

- ハンタウイルス特集中に投稿した記事は `logs/posted.jsonl` に通常通り蓄積される。
  リバート後に重複投稿は発生しない(既投稿リンクは自動除外される)。
- `is_pv_related` 判定プロンプトを「PV専業」に厳格化したい場合は、
  generate.py の `relevance_block` を pre-hantavirus 版に戻すこと。
