"""
post_x.py - X (Twitter) API v2 でポスト投稿
"""
import os
import tweepy


def post_to_x(text: str) -> dict:
    """
    X API v2 でツイートを投稿
    Free tier でも投稿は可能(月500件まで)
    """
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
    
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    
    response = client.create_tweet(text=text)
    
    return {
        "tweet_id": response.data["id"],
        "text": response.data["text"],
        "url": f"https://x.com/i/web/status/{response.data['id']}",
    }


if __name__ == "__main__":
    # テスト用(実際には投稿されるので注意)
    # result = post_to_x("テスト投稿 from コンサルにゃんこ")
    # print(result)
    print("post_x module loaded. Run from main.py for actual posting.")
