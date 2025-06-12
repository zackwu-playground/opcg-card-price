# -*- coding: utf-8 -*-
"""scraper.py
核心爬蟲模組
===============================
• 功能：下載並解析 https://yuyu-tei.jp/top/opc
• 輸出：List[Dict[str, str]] -> [{"name": ..., "url": ...}, ...]

此模組僅專注『抓資料』，不負責資料庫或排程。
"""
from __future__ import annotations

import re
from typing import List, Dict

import requests
from bs4 import BeautifulSoup, Tag

__all__ = ["Scraper"]


class Scraper:
    """負責下載 HTML 與解析指定元素。"""

    def __init__(self, url: str, timeout: int = 10) -> None:
        self.url = url
        self.timeout = timeout
        # 改用 Session 可重複利用 TCP 連線並設定通用 headers
        self.session: requests.Session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def run(self) -> List[Dict[str, str]]:
        """一次完成 *下載 ➜ 解析* 並返回結果。"""
        html = self.fetch()
        return self.parse(html)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def fetch(self) -> str:
        """下載目標頁面 HTML。"""
        resp = self.session.get(self.url, timeout=self.timeout)
        resp.raise_for_status()  # 若非 2xx 會拋出 HTTPError
        return resp.text

    def parse(self, html: str) -> List[Dict[str, str]]:
        """解析 HTML 取得 button 文字與網址。"""
        soup = BeautifulSoup(html, "html.parser")

        # ▸ 抓取 <div class="accordion"> 區塊
        accordion_divs: List[Tag] = soup.select("div.accordion")
        results: List[Dict[str, str]] = []

        for div in accordion_divs:
            # ▸ 於每個 .accordion 內部尋找 h2.accordion-header > button[onclick]
            for btn in div.select("h2.accordion-header > button[onclick]"):
                onclick_attr = btn.get("onclick", "")
                # onclick="location.href='https://yuyu-tei.jp/sell/opc/s/op12'"
                m = re.search(r"location\.href=['\"]([^'\"]+)['\"]", onclick_attr)
                if not m:
                    continue  # 跳過 parse 失敗

                results.append(
                    {
                        "name": btn.get_text(strip=True),
                        "url": m.group(1),
                    }
                )
        return results


if __name__ == "__main__":  # Quick manual test
    import json

    scraper = Scraper("https://yuyu-tei.jp/top/opc")
    data = scraper.run()
    print(json.dumps(data, ensure_ascii=False, indent=2))
