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

        # 1. 精準搜尋頁面中含有「最新クエスト」的標題區塊
        target_section = None
        for heading in soup.find_all(["h2", "h3", "div"]):
            if "最新クエスト" in heading.get_text():
                # 找到標題後，抓取它後方相鄰的表格或容器
                target_section = heading.find_parent("div") or heading.parent
                break

        # 若沒找到專屬區塊則搜尋全頁表格
        search_scope = target_section if target_section else soup

        # 2. 抓取表格內所有包含「攻略」的連結（例如：究極の攻略、超究極の攻略）
        for a_tag in search_scope.select("a[href*='/article/show/']"):
            link_text = a_tag.get_text(strip=True)

            # 確保是攻略連結，並排除純數字或無關連結
            if "攻略" in link_text:
                link = a_tag.get("href", "")
                if not link:
                    continue

                if not link.startswith("http"):
                    link = f"https://xn--eckwa2aa3a9c8j8bve9d.gamewith.jp{link}"

                # 試圖抓取角色名稱（連結前一個文字標籤或上方文字）
                char_name = ""
                parent_td = a_tag.find_parent("td")
                if parent_td:
                    names = [
                        t.get_text(strip=True)
                        for t in parent_td.find_all("a")
                        if "攻略" not in t.get_text()
                    ]
                    if names:
                        char_name = names[0]

                # 點進內頁抓取大圖與完整關卡標題
                detail_title = (
                    f"{char_name} 【{link_text}】" if char_name else link_text
                )
                detail_img_url = ""
                try:
                    d_res = requests.get(link, headers=HEADERS, timeout=5)
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
                    print(f"內頁解析失敗 [{link}]: {e}")

                if not any(item["link"] == link for item in results):
                    results.append(
                        {
                            "title": f"【日版 GameWith】{detail_title}",
                            "link": link,
                            "image_url": detail_img_url,
                        }
                    )

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
        json.dump(cache, f, ensure_ascii=False)


def send_discord(data):
    if not WEBHOOK_URL:
        print("錯誤：找不到 WEBHOOK_URL 密鑰，請確認 Secrets 設定！")
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
        print(f"已推送至 Discord: {data['title']}")
    except Exception as e:
        print(f"Discord 發送失敗: {e}")


if __name__ == "__main__":
    cache = get_cache()
    gw_list = fetch_gw_collaborations()

    current_links = [item["link"] for item in gw_list]

    # 強制推送最新 3 筆測試
    items_to_send = [
        item for item in gw_list if item["link"] not in cache
    ] or gw_list[:3]

    for gw_data in items_to_send[:3]:
        send_discord(gw_data)

    save_cache(current_links)
