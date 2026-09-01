import json
import os
import requests
from bs4 import BeautifulSoup

# WEBHOOK 密鑰設定
WEBHOOK_URL = os.environ.get("GW_DISCORD_WEBHOOK") or os.environ.get("DISCORD_WEBHOOK")
GW_URL = "https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp/"
CACHE_FILE = "gamewith_news.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    )
}

# 排除非關卡攻略的選單連結
EXCLUDE_KEYWORDS = [
    "一覧", "掲示板", "Q&A", "最強", "リセマラ", "ガチャ", 
    "霸者", "未開", "天魔", "記事", "情報", "圖鑑", "回數"
]

def fetch_gw_collaborations():
    try:
        res = requests.get(GW_URL, headers=HEADERS, timeout=10)
        res.encoding = "utf-8"
        soup = BeautifulSoup(res.text, "html.parser")

        results = []

        # 直接搜尋全頁帶有「攻略」二字的關鍵連結
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            text = a_tag.get_text(strip=True)

            if "/article/show/" in href and "攻略" in text:
                # 過濾掉非關卡的選單連結
                if any(ex in text for ex in EXCLUDE_KEYWORDS):
                    continue

                full_link = href if href.startswith("http") else f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{href}"

                # 避免重複抓取
                if any(item["link"] == full_link for item in results):
                    continue

                # 嘗試抓取角色名稱（同個表格儲存格內的文字）
                char_name = ""
                parent_td = a_tag.find_parent("td")
                if parent_td:
                    names = [
                        t.get_text(strip=True)
                        for t in parent_td.find_all("a")
                        if "攻略" not in t.get_text() and not any(ex in t.get_text() for ex in EXCLUDE_KEYWORDS)
                    ]
                    if names:
                        char_name = names[0]

                display_title = f"{char_name} 【{text}】" if char_name else text
                detail_img_url = ""

                # 點進內頁獲取完整標題與關卡大圖
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

        print(f"成功抓取到 {len(results)} 個關卡攻略！")
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

    # 過濾未推送過的新關卡，若是第一次執行（或快取被清空）則發送最新 5 筆
    items_to_send = [item for item in gw_list if item["link"] not in cache]
    
    if not cache and gw_list:
        items_to_send = gw_list[:5]

    for gw_data in items_to_send[:5]:
        send_discord(gw_data)

    save_cache(current_links)
