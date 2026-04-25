"""
post_x.py - X (Twitter) API で画像付き投稿 + 自リプライ
"""
import os
import tweepy


def _get_clients():
    """X API v1.1 (画像アップロード用) と v2 (投稿用) のクライアントを返す"""
    api_key = os.environ.get("X_API_KEY")
    api_secret = os.environ.get("X_API_SECRET")
    access_token = os.environ.get("X_ACCESS_TOKEN")
    access_token_secret = os.environ.get("X_ACCESS_TOKEN_SECRET")
    
    required = {
        "X_API_KEY": api_key,
        "X_API_SECRET": api_secret,
        "X_ACCESS_TOKEN": access_token,
        "X_ACCESS_TOKEN_SECRET": access_token_secret,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise RuntimeError(f"Missing X API credentials: {missing}")
    
    # v2 クライアント (投稿用)
    client_v2 = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    
    # v1.1 API (画像アップロード用)
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    api_v1 = tweepy.API(auth)
    
    return client_v2, api_v1


def upload_image(image_path: str) -> str:
    """
    X API v1.1 で画像をアップロードして media_id を取得
    成功時: media_id (文字列)
    失敗時: None
    """
    if not image_path or not os.path.exists(image_path):
        print(f"[x] Image not found: {image_path}")
        return None
    
    try:
        _, api_v1 = _get_clients()
        media = api_v1.media_upload(filename=image_path)
        print(f"[x] Image uploaded, media_id={media.media_id}")
        return str(media.media_id)
    except Exception as e:
        print(f"[x] Image upload failed: {e}")
        return None


def post_to_x(text: str, image_path: str = None) -> dict:
    """
    親ポストを投稿(画像があれば添付)
    """
    client_v2, _ = _get_clients()
    
    media_ids = None
    if image_path:
        media_id = upload_image(image_path)
        if media_id:
            media_ids = [media_id]
    
    if media_ids:
        response = client_v2.create_tweet(text=text, media_ids=media_ids)
    else:
        response = client_v2.create_tweet(text=text)
    
    tweet_id = response.data["id"]
    return {
        "tweet_id": tweet_id,
        "text": response.data["text"],
        "url": f"https://x.com/i/web/status/{tweet_id}",
        "has_image": bool(media_ids),
    }


def post_reply(parent_tweet_id: str, text: str) -> dict:
    """
    親ポストへの自リプライを投稿
    """
    client_v2, _ = _get_clients()
    
    response = client_v2.create_tweet(
        text=text,
        in_reply_to_tweet_id=parent_tweet_id,
    )
    
    tweet_id = response.data["id"]
    return {
        "tweet_id": tweet_id,
        "text": response.data["text"],
        "url": f"https://x.com/i/web/status/{tweet_id}",
    }


if __name__ == "__main__":
    print("post_x module loaded.")
