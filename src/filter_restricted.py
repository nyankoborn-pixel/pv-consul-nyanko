"""
filter_restricted.py - 会員専用記事の判定・除外

使い方:
    from filter_restricted import is_member_only_article

    if is_member_only_article(entry):
        print(f"Skipped (member-only): {entry['title']}")
        continue
    # 通常処理に進む

判定ロジック:
- restricted_domains.yml で定義したドメインの記事のみ判定対象
- そのドメインの記事で、summary の文字数が min_summary_length 未満なら
  会員限定記事と推定して True を返す
- それ以外は False(通常処理対象)
"""
import os
import yaml
from urllib.parse import urlparse


_CONFIG_CACHE = None


def _load_config(config_path: str = "config/restricted_domains.yml") -> dict:
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if not os.path.exists(config_path):
        # 設定ファイルがなければフィルタしない
        _CONFIG_CACHE = {"restricted_domains": [], "min_summary_length": 350}
        return _CONFIG_CACHE

    with open(config_path, "r", encoding="utf-8") as f:
        _CONFIG_CACHE = yaml.safe_load(f) or {}

    _CONFIG_CACHE.setdefault("restricted_domains", [])
    _CONFIG_CACHE.setdefault("min_summary_length", 350)
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


def is_member_only_article(entry: dict, config_path: str = "config/restricted_domains.yml") -> bool:
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
