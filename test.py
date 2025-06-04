import time
import requests
from bs4 import BeautifulSoup

# 模擬一般瀏覽器，降低被網站當機器人阻擋的機率
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/90.0.4430.85 Safari/537.36"
    )
}

def fetch_page(url: str, delay = 1) -> str | None:
    """
    發送 HTTP GET 請求取得原始 HTML，如果失敗回傳 None。
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()       # 若狀態碼非 200，拋出例外
        time.sleep(delay)
        return resp.text             # 回傳 HTML 原始碼
    except requests.RequestException as e:
        print(f"[Error] 無法取得頁面：{e}")
        return None

def parse_headers(html: str) -> list[str]:
    """
    解析 HTML，找到所有 <h2 class="accordion-header"> 節點，
    並回傳它們的純文字內容清單。

    本函式僅回傳所有標題文字，不進行篩選；
    後續印出時會用 ``txt.startswith("[")`` 再過濾。
    """
    # 1) 建立 BeautifulSoup 物件，使用內建解析器
    soup = BeautifulSoup(html, "html.parser")

    # 2) 用 CSS 選擇器抓出所有目標 h2 節點
    #    - “h2.accordion-header” 代表 <h2 class="accordion-header">
    header_tags = soup.select("h2.accordion-header")

    results: list[str] = []
    for h2 in header_tags:
        # 3) 取出該 h2 節點內所有文字，並移除前後空白
        #    get_text() 會把裡面所有子孫元素的文字都串在一起
        text = h2.get_text(strip=True)

        # 4) 如果你只想保留包含 [ST22] 的項目，可加上篩選條件：
        #    if text.startswith("[ST22]"):
        #        results.append(text)
        #
        #    這裡範例示範取出所有 h2 文字，若需過濾再加上上述條件。
        results.append(text)

    return results

if __name__ == "__main__":
    url = "https://yuyu-tei.jp/sell/opc/s/st22#newest"
    # 1) 取得 HTML
    html = fetch_page(url)
    if html is None:
        exit(1)

    # 2) 解析 <h2 class="accordion-header"> 文字
    header_texts = parse_headers(html)

    # 3) 印出結果 -- 只列出以 "[" 開頭的項目
    #    parse_headers 已回傳所有標題，這裡再用 txt.startswith("[") 過濾
    if header_texts:
        print("抓到以下 <h2 class=\"accordion-header\"> 內的文字：")
        for idx, txt in enumerate(header_texts, 1):
            # 只輸出開頭為 "[" 的標題
            if txt.startswith("["):
                print(f"{idx}. {txt}")
    else:
        print("找不到任何 <h2 class=\"accordion-header\"> 節點。")