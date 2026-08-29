import json
import os
import re
import requests
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
TARGET_URL = "https://www.monster-strike.com.tw/news/"
CACHE_FILE = "last_news.json"


def fetch_news():
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
    }
    response = requests.get(TARGET_URL, headers=headers)
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")
    # 抓取最新一篇新聞區塊
    news_item = soup.select_one(".news_list_item") or soup.select_one("a[href*='/news/']")
    if not news_item:
        return None

    # 取得網址與標題
    link = news_item.get("href", "")
    if link and not link.startswith("http"):
        link = f"https://www.monster-strike.com.tw{link}"

    title = news_item.get_text(strip=True)
    # 清除多餘換行或空白
    title = re.sub(r"\s+", " ", title)

    return {"title": title, "link": link}


def get_last_news():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_last_news(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def send_discord(title, link):
    payload = {
        "content": "【怪物彈珠最新公告】",
        "embeds": [
            {
                "title": title,
                "url": link,
                "color": 5814783,
            }
        ],
    }
    requests.post(WEBHOOK_URL, json=payload)


if __name__ == "__main__":
    current_news = fetch_news()
    if current_news and current_news.get("link"):
        last_news = get_last_news()
        if not last_news or last_news.get("link") != current_news["link"]:
            send_discord(current_news["title"], current_news["link"])
            save_last_news(current_news)
            print("發送新公告通知成功！")
        else:
            print("沒有新公告。")
