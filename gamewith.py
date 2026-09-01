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

# 排除無關頁面關鍵字
EXCLUDE_KEYWORDS = ["一覧", "掲示板", "Q&A", "最強", "リセマラ", "ガチャ", "霸者", "未開"]

def fetch_gw_collaborations():
    try:
        res = requests.get(GW_URL, headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        results = []

        # 1. 尋找「最新クエスト」標題
        target_table = None
        for heading in soup.find_all(["h2", "h3", "div"]):
            if "最新クエスト" in heading.get_text():
                # 尋找該標題下方的第一個 table 表格
                parent = heading.find_parent(["div", "section"]) or heading.parent
                if parent:
                    target_table = parent.find("table")
                break

        # 如果沒找到對應區塊，退而求其次找頁面中第一個 table
        if not target_table:
            target_table = soup.find("table")

        if not target_table:
            print("未找到最新關卡表格！")
            return []

        # 2. 遍歷表格中的每一個儲存格 (td)
        for td in target_table.find_all("td"):
            links = td.find_all("a[href*='/article/show/']")
            if not links:
                continue

            # 提取角色名稱與攻略連結
            char_name = ""
            quest_link = ""
            quest_text = ""

            for a in links:
                text = a.get_text(strip=True)
                href = a.get("href", "")

                if any(ex in text for ex in EXCLUDE_KEYWORDS):
                    continue

                if "攻略" in text:
                    quest_link = href
                    quest_text = text
                else:
                    char_name = text

            if quest_link:
                if not quest_link.startswith("http"):
                    quest_link = f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{quest_link}"

                # 組合標題
                display_title = f"{char_name} 【{quest_text}】" if char_name else quest_text

                # 點進內頁抓取完整大圖與詳細標題
                detail_title = display_title
                detail_img_url = ""
                try:
                    d_res = requests.get(quest_link, headers=HEADERS, timeout=5)
                    d_res.encoding = "utf-8"
                    d_soup = BeautifulSoup(d_res.text, "html.parser")

                    title_tag = d_soup.select_one("h1, .g-article-title")
                    if title_tag:
                        detail_title = title_tag.get_text(strip=True)

                    img = d_soup.select_one(".g-article-img img, .article-body img, #article-body img")
                    if img:
                        detail_img_url = img.get("src") or img.get("data-original") or img.get("data-src") or ""
                        if detail_img_url and not detail_img_url.startswith("http"):
                            detail_img_url = f"https:{detail_img_url}" if detail_img_url.startswith("//") else f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{detail_img_url}"
                except Exception as e:
                    print(f"內頁解析失敗 [{quest_link}]: {e}")

                if not any(item["link"] == quest_link for item in results):
                    results.append({
                        "title": f"【日版 GameWith】{detail_title}",
                        "link": quest_link,
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
        json.dump(cache, f, ensure_ascii=False)


def send_discord(data):
    if not WEBHOOK_URL:
        print("錯誤：找不到 GW_DISCORD_WEBHOOK 密鑰！")
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

    # 過濾未推送過的新關卡，若無快取則發送最新 5 筆
    items_to_send = [item for item in gw_list if item["link"] not in cache] or gw_list[:5]

    for gw_data in items_to_send[:5]:
        send_discord(gw_data)

    save_cache(current_links)
