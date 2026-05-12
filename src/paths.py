"""
paths.py - アカウント別の設定/ログパスを ACCOUNT_NAME 環境変数で切替

GitHub Actions の workflow ごとに `ACCOUNT_NAME` を指定し、
`config/{ACCOUNT_NAME}/` 配下の設定ファイルと
`logs/{ACCOUNT_NAME}/posted.jsonl` を読み書きする。
未設定時は `nyanko`(既存運用)にフォールバック。
"""
import os
from pathlib import Path


ACCOUNT_NAME = os.environ.get("ACCOUNT_NAME", "nyanko")

CONFIG_DIR = Path("config") / ACCOUNT_NAME
LOG_DIR = Path("logs") / ACCOUNT_NAME

CHARACTER_YML = str(CONFIG_DIR / "character.yml")
SOURCES_YML = str(CONFIG_DIR / "sources.yml")
KEYWORDS_YML = str(CONFIG_DIR / "keywords.yml")
RESTRICTED_DOMAINS_YML = str(CONFIG_DIR / "restricted_domains.yml")
POSTED_LOG = LOG_DIR / "posted.jsonl"
