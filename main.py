import json
import os
import re
import requests
from bs4 import BeautifulSoup

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK")
TW_URL = "https://www.monster-strike.com.tw/news/"
GW_URL = "https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp/"
CACHE_FILE = "last_news.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}


# --- 1. 台版官網抓取 ---
def fetch_tw_news():
    try:
        res = requests.get(TW_URL, headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        article = soup.select_one(
            ".news_list_item, .newsList_item, article, .p-newsList__item"
        )
        if not article:
            for a in soup.select("a[href*='/news/']"):
                if a.get("href", "").endswith(".html") and a.select_one("img"):
                    article = a
                    break
        if not article:
            return None

        link_tag = (
            article
            if article.name == "a"
            else article.select_one("a[href*='/news/']")
        )
        if not link_tag:
            return None

        link = link_tag.get("href", "")
        if link and not link.startswith("http"):
            link = f"https://www.monster-strike.com.tw{link}"

        image_url = ""
        img_tag = article.select_one("img")
        if img_tag:
            image_url = img_tag.get("src") or img_tag.get("data-src") or ""
            if image_url and not image_url.startswith("http"):
                image_url = f"https://www.monster-strike.com.tw{image_url}"

        raw_title = link_tag.get_text(strip=True) or (
            img_tag.get("alt", "") if img_tag else ""
        )
        clean_title = re.sub(
            r"CHECK|NEW|\d{4}\.\d{2}\.\d{2}|活動|重要|維護", "", raw_title
        )
        clean_title = re.sub(r"\s+", " ", clean_title).strip() or "怪物彈珠最新公告"

        summary = ""
        try:
            d_res = requests.get(link, headers=HEADERS, timeout=10)
            d_res.encoding = "utf-8"
            d_soup = BeautifulSoup(d_res.text, "html.parser")
            paras = [
                p.get_text().strip()
                for p in d_soup.select(
                    "main p, .article_body p, .news_detail p, #main p"
                )
                if len(p.get_text().strip()) > 5
            ]
            summary = "\n".join(paras)[:180]
        except Exception:
            pass

        return {
            "type": "TW",
            "title": clean_title,
            "link": link,
            "image_url": image_url,
            "summary": summary,
        }
    except Exception as e:
        print(f"台版抓取失敗: {e}")
        return None


# --- 2. 日版 GameWith（僅抓取「注目の最新イベント」前兩格超究極）---
def fetch_gw_events():
    try:
        res = requests.get(GW_URL, headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        # 精準定位「注目の最新イベント」標題旁的表格
        items = []
        for a in soup.select("table a[href*='/article/show/']"):
            title = a.get_text(strip=True)
            link = a.get("href", "")
            img = a.select_one("img")
            img_url = img.get("src") if img else ""

            if title and link:
                items.append(
                    {"title": title, "link": link, "image_url": img_url}
                )

        if not items:
            return []

        # 僅取前 2 個項目（即超究極卡片）
        top_2_items = items[:2]
        results = []
        for item in top_2_items:
            results.append(
                {
                    "type": "GW",
                    "title": f"【日版 GameWith 攻略】{item['title']}",
                    "link": item["link"],
                    "image_url": item["image_url"],
                    "summary": f"超究極關卡攻略頁面：{item['title']}",
                }
            )

        return results
    except Exception as e:
        print(f"日版 GameWith 抓取失敗: {e}")
        return []


# --- 快取管理 ---
def get_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"TW": "", "GW": []}


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


# --- Discord 發送 ---
def send_discord(data):
    embed = {
        "title": data["title"],
        "url": data["link"],
        "color": 5814783 if data["type"] == "TW" else 15105570,
    }

    if data.get("summary"):
        embed["description"] = data["summary"]

    if data.get("image_url"):
        embed["image"] = {"url": data["image_url"]}

    payload = {
        "content": data["title"],
        "embeds": [embed],
    }
    requests.post(WEBHOOK_URL, json=payload)


if __name__ == "__main__":
    cache = get_cache()

    # 1. 檢查台版
    tw_data = fetch_tw_news()
    if tw_data and cache.get("TW") != tw_data["link"]:
        send_discord(tw_data)
        cache["TW"] = tw_data["link"]
        print("台版最新公告推播成功！")

    # 2. 檢查日版（僅前兩格）
    gw_list = fetch_gw_events()
    gw_cache = cache.get("GW", [])
    current_gw_links = [item["link"] for item in gw_list]

    # 比對是否有新的超究極連結
    for gw_data in gw_list:
        if gw_data["link"] not in gw_cache:
            send_discord(gw_data)
            print(f"日版推播成功: {gw_data['title']}")

    cache["GW"] = current_gw_links
    save_cache(cache)
