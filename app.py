import os
import requests
import time
from bs4 import BeautifulSoup
import hashlib
from flask import Flask
from threading import Thread

# Flaskアプリケーションのインスタンスを作成
app = Flask(__name__)

# --- 設定項目 (環境変数から読み込む) ---
# DiscordのWebhook URLはKoyebのSecretsで設定
WEBHOOK_URL = os.environ.get('WEBHOOK_URL')
# 監視したい掲示板のURL
TARGET_URL = os.environ.get('TARGET_URL', 'https://132628.peta2.jp/1961877.html') # デフォルト値を設定
# チェック間隔（秒）
CHECK_INTERVAL_SECONDS = int(os.environ.get('CHECK_INTERVAL_SECONDS', 60))


# --- グローバル変数 ---
last_post_hash = ""

def get_latest_post_content():
    """ウェブページから最新の投稿を取得して、その内容（テキストと投稿者）を返す関数。"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(TARGET_URL, headers=headers)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        soup = BeautifulSoup(response.text, 'html.parser')
        all_posts = soup.find_all('article')
        if not all_posts:
            print("投稿が見つかりませんでした。")
            return None, None
        latest_post_article = all_posts[-1]
        post_content_div = latest_post_article.find('div', class_='post-content')
        post_content = post_content_div.get_text(strip=True) if post_content_div else "本文の取得に失敗しました。"
        post_name_span = latest_post_article.find('span', class_='post-name')
        post_name = post_name_span.get_text(strip=True) if post_name_span else "名無しさん"
        return post_content, post_name
    except requests.exceptions.RequestException as e:
        print(f"エラー: ウェブページにアクセスできませんでした - {e}")
        return None, None
    except Exception as e:
        print(f"予期せぬエラーが発生しました: {e}")
        return None, None

def send_discord_notification(content, author):
    """新しい投稿をDiscordに通知する関数。"""
    if not WEBHOOK_URL:
        print("エラー: WEBHOOK_URLが設定されていません。")
        return
    embed = {
        "title": "掲示板に新しい書き込みがありました！",
        "description": content,
        "url": TARGET_URL,
        "color": 5814783,
        "author": {"name": f"投稿者: {author}"},
        "footer": {"text": "掲示板監視ボット (on Koyeb)"}
    }
    payload = {"username": "掲示板ウォッチャー", "embeds": [embed]}
    try:
        response = requests.post(WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("Discordに通知を送信しました。")
    except requests.exceptions.RequestException as e:
        print(f"エラー: Discordへの通知に失敗しました - {e}")

def get_hash(text):
    """テキストからハッシュ値を計算する。"""
    if not text: return None
    return hashlib.md5(text.encode()).hexdigest()

def background_monitor_task():
    """バックグラウンドで掲示板を監視し続ける関数。"""
    global last_post_hash
    print("バックグラウンド監視タスクを開始します...")
    
    # 最初に現在の最新投稿を取得して基準とする
    initial_content, _ = get_latest_post_content()
    last_post_hash = get_hash(initial_content)
    if last_post_hash:
        print(f"監視開始時の最新投稿を基準に設定しました。")
    else:
        print("初回の投稿取得に失敗。次のチェックから通知を開始します。")

    while True:
        try:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 新しい投稿をチェック中...")
            current_content, current_author = get_latest_post_content()
            current_hash = get_hash(current_content)

            if current_hash and current_hash != last_post_hash:
                print("新しい投稿を発見しました！")
                send_discord_notification(current_content, current_author)
                last_post_hash = current_hash
            elif not current_hash:
                print("今回のチェックでは投稿を取得できませんでした。")
            else:
                print("新しい投稿はありませんでした。")
            
            time.sleep(CHECK_INTERVAL_SECONDS)

        except Exception as e:
            print(f"監視ループでエラーが発生しました: {e}")
            time.sleep(300) # エラー発生時は5分待機

# Koyebのヘルスチェックに応答するためのルート
@app.route('/')
def index():
    return "Bot is running!"

if __name__ == "__main__":
    # バックグラウンドタスクを開始
    monitor_thread = Thread(target=background_monitor_task)
    monitor_thread.daemon = True # メインスレッドが終了したら一緒に終了
    monitor_thread.start()

    # Flaskアプリケーションを起動
    # PORTはKoyebが自動的に設定してくれる
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)