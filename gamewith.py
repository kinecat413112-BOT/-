import json
import os
import requests
from bs4 import BeautifulSoup

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

        # 1. 尋找包含「最新クエスト」字樣的標題元件
        target_heading = None
        for el in soup.find_all(["h2", "h3", "div", "span"]):
            if "最新クエスト" in el.get_text():
                target_heading = el
                break

        if not target_heading:
            print("找不到『最新クエスト』標題區塊")
            return []

        # 2. 定位該標題下方的第一個 table 區塊
        parent_container = target_heading.find_parent(["div", "section"]) or target_heading.parent
        target_table = parent_container.find("table") if parent_container else None

        if not target_table:
            print("找不到最新關卡的表格 (Table)")
            return []

        # 3. 解析表格格子 (td) 內的關卡資訊
        for td in target_table.find_all("td"):
            links = td.find_all("a", href=True)
            if not links:
                continue

            quest_link = ""
            quest_text = ""
            char_name = ""

            for a in links:
                text = a.get_text(strip=True)
                href = a["href"]

                if "攻略" in text and "/article/show/" in href:
                    quest_link = href
                    quest_text = text
                elif text and not text.startswith("http"):
                    char_name = text

            if quest_link:
                full_link = quest_link if quest_link.startswith("http") else f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{quest_link}"

                if any(item["link"] == full_link for item in results):
                    continue

                display_title = f"{char_name} 【{quest_text}】" if char_name else quest_text
                detail_img_url = ""

                # 點進關卡內頁抓取大圖與正確完整標題
                try:
                    d_res = requests.get(full_link, headers=HEADERS, timeout=5)
                    d_res.encoding = "utf-8"
                    d_soup = BeautifulSoup(d_res.text, "html.parser")

                    title_tag = d_soup.select_one("h1, .g-article-title")
                    if title_tag:
                        display_title = title_tag.get_text(strip=True)

                    img = d_soup.select_one(".g-article-img img, .article-body img, #article-body img")
                    if img:
                        img_src = img.get("src") or img.get("data-original") or img.get("data-src") or ""
                        if img_src:
                            if img_src.startswith("//"):
                                detail_img_url = f"https:{img_src}"
                            elif not img_src.startswith("http"):
                                detail_img_url = f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{img_src}"
                            else:
                                detail_img_url = img_src
                except Exception as e:
                    print(f"內頁解析失敗 [{full_link}]: {e}")

                results.append({
                    "title": f"【日版 GameWith】{display_title}",
                    "link": full_link,
                    "image_url": detail_img_url
                })

        print(f"成功精準抓取到 {len(results)} 個最新關卡攻略！")
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
        json.dump(cache, f, ensure_ascii=False, indent=2)

def send_discord(data):
    if not WEBHOOK_URL:
        print("錯誤：找不到 GW_DISCORD_WEBHOOK 密鑰，請確認 Secrets 設定！")
        return

    embed = {
        "title": data["title"],
        "url": data["link"],
        "color": 15105570
    }

    if data.get("image_url"):
        embed["image"] = {"url": data["image_url"]}

    payload = {
        "content": data["title"],
        "embeds": [embed]
    }

    try:
        res = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        print(f"已推送至 Discord: {data['title']}")
    except Exception as e:
        print(f"Discord 發送失敗: {e}")

if __name__ == "__main__":
    cache = get_cache()
    gw_list = fetch_gw_collaborations()

    current_links = [item["link"] for item in gw_list]

    # 找出不在快取的項目；若快取已被手動清空，則發送最上方前 5 筆
    items_to_send = [item for item in gw_list if item["link"] not in cache]
    if not cache and gw_list:
        items_to_send = gw_list[:5]

    for gw_data in items_to_send[:5]:
        send_discord(gw_data)

    save_cache(current_links)
