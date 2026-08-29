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

    # 定位新聞列表區塊中的第一篇文章
    article = soup.select_one(".news_list_item, .newsList_item, article, .p-newsList__item")
    
    if not article:
        for a in soup.select("a[href*='/news/']"):
            href = a.get("href", "")
            if href.endswith(".html") and a.select_one("img"):
                article = a
                break

    if not article:
        return None

    # 1. 取得連結
    link_tag = article if article.name == "a" else article.select_one("a[href*='/news/']")
    if not link_tag:
        return None
    
    link = link_tag.get("href", "")
    if link and not link.startswith("http"):
        link = f"https://www.monster-strike.com.tw{link}"

    # 2. 取得列表縮圖
    image_url = ""
    img_tag = article.select_one("img")
    if img_tag:
        image_url = img_tag.get("src") or img_tag.get("data-src") or ""
        if image_url and not image_url.startswith("http"):
            image_url = f"https://www.monster-strike.com.tw{image_url}"

    # 3. 取得文章標題並清理雜訊
    raw_title = link_tag.get_text(strip=True)
    if not raw_title and img_tag:
        raw_title = img_tag.get("alt", "")
    
    clean_title = re.sub(r"CHECK|NEW|\d{4}\.\d{2}\.\d{2}|活動|重要|維護", "", raw_title)
    clean_title = re.sub(r"\s+", " ", clean_title).strip()
    
    if not clean_title:
        clean_title = "怪物彈珠最新公告"

    # 4. 點進公告內文抓取簡介大綱 (前 150 字)
    summary = ""
    try:
        detail_res = requests.get(link, headers=headers)
        detail_res.encoding = "utf-8"
        detail_soup = BeautifulSoup(detail_res.text, "html.parser")
        
        # 抓取內文的主要段落 (p 標籤)
        paragraphs = detail_soup.select("main p, .article_body p, .news_detail p, #main p")
        text_list = []
        for p in paragraphs:
            text = p.get_text().strip()
            # 過濾掉空白或太短的裝飾字
            if text and len(text) > 5 and "monster-strike" not in text:
                text_list.append(text)
            if len("\n".join(text_list)) >= 150:
                break
        
        summary = "\n".join(text_list)[:200]  # 限制最大字數在大綱長度
    except Exception as e:
        print(f"抓取內文大綱失敗: {e}")

    return {"title": clean_title, "link": link, "image_url": image_url, "summary": summary}


def get_last_news():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_last_news(data):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def send_discord(title, link, image_url, summary):
    embed = {
        "title": title,
        "url": link,
        "color": 5814783
    }

    # 如果有抓到內文大綱，放入 description 欄位
    if summary:
        embed["description"] = summary

    if image_url:
        embed["image"] = {"url": image_url}

    payload = {
        "content": title,
        "embeds": [embed],
    }
    requests.post(WEBHOOK_URL, json=payload)


if __name__ == "__main__":
    current_news = fetch_news()
    if current_news and current_news.get("link"):
        last_news = get_last_news()
        if not last_news or last_news.get("link") != current_news["link"]:
            send_discord(
                current_news["title"],
                current_news["link"],
                current_news.get("image_url", ""),
                current_news.get("summary", ""),
            )
            save_last_news(current_news)
            print("發送帶內文大綱之公告成功！")
        else:
            print("沒有新公告。")
