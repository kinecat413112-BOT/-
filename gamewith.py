import json
import os
import requests
from bs4 import BeautifulSoup

# 自動相容 DISCORD_WEBHOOK 或 GW_DISCORD_WEBHOOK
WEBHOOK_URL = os.environ.get("GW_DISCORD_WEBHOOK") or os.environ.get("DISCORD_WEBHOOK")
GW_URL = "https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp/"
CACHE_FILE = "gamewith_news.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}


def fetch_gw_collaborations():
    try:
        res = requests.get(GW_URL, headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        results = []
        for a_tag in soup.select("table a[href*='/article/show/']"):
            link_text = a_tag.get_text(strip=True)

            if "攻略" in link_text or "の" in link_text:
                link = a_tag.get("href", "")
                if not link:
                    continue

                if not link.startswith("http"):
                    link = f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{link}"

                detail_title = link_text
                detail_img_url = ""
                try:
                    d_res = requests.get(link, headers=HEADERS, timeout=10)
                    d_res.encoding = "utf-8"
                    d_soup = BeautifulSoup(d_res.text, "html.parser")

                    title_tag = d_soup.select_one("h1, .g-article-title")
                    if title_tag:
                        detail_title = title_tag.get_text(strip=True)

                    img = d_soup.select_one(
                        ".g-article-img img, .article-body img, #article-body img"
                    )
                    if img:
                        detail_img_url = (
                            img.get("src")
                            or img.get("data-original")
                            or img.get("data-src")
                            or ""
                        )
                        if detail_img_url and not detail_img_url.startswith(
                            "http"
                        ):
                            detail_img_url = (
                                f"https:{detail_img_url}"
                                if detail_img_url.startswith("//")
                                else f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{detail_img_url}"
                            )
                except Exception as e:
                    print(f"解析內頁失敗 [{link}]: {e}")

                results.append(
                    {
                        "title": f"【日版 GameWith 攻略】{detail_title}",
                        "link": link,
                        "image_url": detail_img_url,
                    }
                )

        return results
    except Exception as e:
        print(f"日版 GameWith 抓取失敗: {e}")
        return []


def get_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)


def send_discord(data):
    if not WEBHOOK_URL:
        print("未找到 Discord Webhook 網址，跳過發送。")
        return

    embed = {
        "title": data["title"],
        "url": data["link"],
        "color": 15105570,
    }

    if data.get("image_url"):
        embed["image"] = {"url": data["image_url"]}

    payload = {
        "content": data["title"],
        "embeds": [embed],
    }
    
    try:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
    except Exception as e:
        print(f"Discord 發送失敗: {e}")


if __name__ == "__main__":
    cache = get_cache()
    gw_list = fetch_gw_collaborations()

    current_links = [item["link"] for item in gw_list]

    for gw_data in gw_list[:3]:
        if gw_data["link"] not in cache:
            send_discord(gw_data)
            print(f"日版攻略推播成功: {gw_data['title']}")

    save_cache(current_links)
