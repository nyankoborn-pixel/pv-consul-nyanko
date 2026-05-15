"""
filter_restricted.py - 低品質記事の判定・除外

3 種類のフィルタ:
(1) is_member_only_article — restricted_domains × summary 短文 → 会員専用と推定
(2) is_blocked_domain      — blocked_domains に該当 → 無条件除外 (掲示板等)
(3) is_blocked_title       — blocked_title_patterns に該当 → 無条件除外 (セミナー告知/回顧記事等)
"""
import os
import re
import yaml
from urllib.parse import urlparse

from paths import RESTRICTED_DOMAINS_YML


_CONFIG_CACHE = None
_BLOCKED_TITLE_RES = None


def _load_config(config_path: str = RESTRICTED_DOMAINS_YML) -> dict:
    global _CONFIG_CACHE, _BLOCKED_TITLE_RES
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if not os.path.exists(config_path):
        # 設定ファイルがなければフィルタしない
        _CONFIG_CACHE = {
            "restricted_domains": [], "min_summary_length": 350,
            "blocked_domains": [], "blocked_title_patterns": [],
        }
        _BLOCKED_TITLE_RES = []
        return _CONFIG_CACHE

    with open(config_path, "r", encoding="utf-8") as f:
        _CONFIG_CACHE = yaml.safe_load(f) or {}

    _CONFIG_CACHE.setdefault("restricted_domains", [])
    _CONFIG_CACHE.setdefault("min_summary_length", 350)
    _CONFIG_CACHE.setdefault("blocked_domains", [])
    _CONFIG_CACHE.setdefault("blocked_title_patterns", [])

    _BLOCKED_TITLE_RES = []
    for pat in _CONFIG_CACHE["blocked_title_patterns"]:
        try:
            _BLOCKED_TITLE_RES.append(re.compile(pat))
        except re.error as e:
            print(f"[filter] invalid blocked_title_pattern: {pat!r} ({e})")
    return _CONFIG_CACHE


def _extract_domain(url: str) -> str:
    """URLからドメイン部分を抽出(www.は除去)"""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def is_restricted_domain(url: str, config: dict = None) -> bool:
    """URLが要注意ドメイン(会員専用の可能性あり)かどうか判定"""
    if config is None:
        config = _load_config()

    domain = _extract_domain(url)
    if not domain:
        return False

    for restricted in config.get("restricted_domains", []):
        # 部分一致で判定(サブドメインも含めて)
        if restricted.lower() in domain:
            return True
    return False


def is_member_only_article(entry: dict, config_path: str = RESTRICTED_DOMAINS_YML) -> bool:
    """
    記事が会員専用と推定されるか判定する。

    True を返す条件:
    - 記事のリンクが restricted_domains に該当する
    - かつ summary の文字数が min_summary_length 未満

    上記以外はすべて False(通常処理対象)。
    """
    config = _load_config(config_path)

    url = entry.get("link", "") or entry.get("url", "")
    if not is_restricted_domain(url, config):
        # 要注意ドメインでなければ常に False
        return False

    summary = entry.get("summary", "") or ""
    min_len = config.get("min_summary_length", 350)

    if len(summary) < min_len:
        return True

    return False


def is_blocked_domain(url: str, config_path: str = RESTRICTED_DOMAINS_YML) -> bool:
    """URL が blocked_domains に該当すれば True (掲示板等の無条件除外)"""
    config = _load_config(config_path)
    domain = _extract_domain(url)
    if not domain:
        return False
    for blocked in config.get("blocked_domains", []):
        if str(blocked).lower() in domain:
            return True
    return False


def is_blocked_title(title: str, config_path: str = RESTRICTED_DOMAINS_YML) -> bool:
    """title が blocked_title_patterns のどれかにマッチすれば True"""
    _load_config(config_path)  # populates _BLOCKED_TITLE_RES
    if not title or not _BLOCKED_TITLE_RES:
        return False
    for r in _BLOCKED_TITLE_RES:
        if r.search(title):
            return True
    return False
