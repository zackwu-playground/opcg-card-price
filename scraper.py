# -*- coding: utf-8 -*-
"""scraper.py
核心爬蟲模組
===============================
• 功能：下載並解析 https://yuyu-tei.jp/top/opc
• 輸出：List[Product] -> [Product(name=..., url=..., cards=[...]), ...]

此模組僅專注『抓資料』，不負責資料庫或排程。
"""
from __future__ import annotations

import re
from typing import List
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date

from models import Product, Card

import requests
from bs4 import BeautifulSoup, Tag

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

__all__ = ["Scraper"]


class Scraper:
    """負責下載 HTML 與解析指定元素。"""

    def __init__(
        self, url: str, timeout: int = 10, max_workers: int = 5, use_selenium: bool = True
    ) -> None:
        self.url = url
        self.timeout = timeout
        self.max_workers = max_workers
        self.use_selenium = use_selenium
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
        self.driver = None
        if self.use_selenium and webdriver is not None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
                self.driver.implicitly_wait(self.timeout)
            except Exception:
                self.driver = None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def run(self) -> List[Product]:
        """一次完成 *下載 ➜ 解析* 並返回結果。"""
        html = self.fetch()
        return self.parse(html)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def fetch(self) -> str:
        """下載目標頁面 HTML。"""
        if self.use_selenium and self.driver is not None:
            self.driver.get(self.url)
            return self.driver.page_source
        resp = self.session.get(self.url, timeout=self.timeout)
        resp.raise_for_status()  # 若非 2xx 會拋出 HTTPError
        return resp.text

    def fetch_page(self, url: str) -> str:
        """下載指定產品頁面 HTML。"""
        if self.use_selenium and self.driver is not None:
            self.driver.get(url)
            return self.driver.page_source
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def parse_card_page(self, html: str) -> Card:
        """解析單一卡片頁面以取得詳細資訊 (不含卡片名稱)。"""
        soup = BeautifulSoup(html, "html.parser")

        img_bytes = b""
        number = ""
        price = 0
        quantity = 0
        feature = ""
        color = ""
        container = soup.find(
            "section", class_="product-detail", id="product-detail"
        )
        if container:
            img_col = container.find(class_="col-lg-5")
            if img_col:
                img_elem = img_col.find("img", class_="vimg", src=True)
                if img_elem:
                    img_url = img_elem["src"]
                    if (
                        img_url.endswith(".jpg")
                        and img_url
                        != "https://img.yuyu-tei.jp/card_image/noimage_front.jpg"
                    ):
                        try:
                            resp = self.session.get(img_url, timeout=self.timeout)
                            resp.raise_for_status()
                            img_bytes = resp.content
                        except requests.RequestException:
                            img_bytes = b""

            info_col = container.find(class_="col-lg-7")
            if info_col:
                table_div = info_col.find(class_="table-responsive")
                if table_div:
                    first_tr = table_div.find("tr")
                    if first_tr:
                        td_elems = first_tr.find_all("td", class_="text-dark")
                        if len(td_elems) >= 1:
                            feature = td_elems[0].get_text(strip=True)
                        if len(td_elems) >= 2:
                            color = td_elems[1].get_text(strip=True)

                d_flex_list = info_col.find_all(class_="d-flex")
                if d_flex_list:
                    border_elem = d_flex_list[0].find(class_="border")
                    if border_elem:
                        number = border_elem.get_text(strip=True)
                if len(d_flex_list) >= 2:
                    second_flex = d_flex_list[1]
                    price_elem = second_flex.find("h4", class_="fw-bold")
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        try:
                            price = int(re.sub(r"[^0-9]", "", price_text))
                        except ValueError:
                            price = 0

                    label_elem = second_flex.find("label", class_="form-check-label")
                    if label_elem:
                        label_text = label_elem.get_text(strip=True)
                        m = re.search(r"在庫\s*:\s*(\S+)\s*点", label_text)
                        if m:
                            qty_str = m.group(1)
                            try:
                                quantity = int(qty_str)
                            except ValueError:
                                quantity = 0


        return Card(
            name="",
            rarity="",
            url="",
            image=img_bytes,
            number=number,
            price=price,
            quantity=quantity,
            scraped_at=date.today(),
            feature=feature,
            color=color,
        )

    def parse_product_page(self, html: str) -> List[Card]:
        """解析產品頁面以取得卡片清單，依稀有度排序。"""
        soup = BeautifulSoup(html, "html.parser")

        # ▸ 主要卡片列表區塊
        container = soup.find(class_="col-12 mb-5 pb-5")
        if not container:
            return []

        cards: List[Card] = []
        card_lists = container.find_all("div", id="card-list3", class_="py-4")
        if not card_lists:
            return cards

        # Precollect all card links so we know the total for progress output
        entries: List[tuple[str, str, str]] = []
        for card_list in card_lists:
            rarity_elem = card_list.find(class_="py-2")
            rarity = rarity_elem.get_text(strip=True) if rarity_elem else ""
            # Skip common/uncommon cards
            if rarity.strip().upper() in {"C", "U", "UC"}:
                continue
            for row in card_list.select("div.row"):
                for col in row.select("div.col-md"):
                    link = col.find("a", href=True)
                    if not link:
                        continue
                    card_url = link["href"]
                    name_tag = col.find(class_="text-primary")
                    card_name = name_tag.get_text(strip=True) if name_tag else ""
                    entries.append((card_url, card_name, rarity))

        total = len(entries)

        def worker(entry: tuple[str, str, str]) -> Card | None:
            card_url, card_name, rarity = entry
            try:
                card_html = self.fetch_page(card_url)
                card = self.parse_card_page(card_html)
                if not card.number:
                    return None
                card.rarity = rarity
                card.url = card_url
                card.name = card_name
                return card
            except requests.RequestException:
                return None

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(worker, e) for e in entries]
            for idx, f in enumerate(as_completed(futures), 1):
                card = f.result()
                if card:
                    cards.append(card)
                print(
                    f"[parse_product_page] {idx}/{total} {card.name if card else ''}",
                    flush=True,
                )

        return cards

    def parse(self, html: str) -> List[Product]:
        """解析 HTML 取得 button 文字與網址並組成 ``Product`` 物件。"""
        soup = BeautifulSoup(html, "html.parser")

        # ▸ 僅抓取 <div class="tab-content"> 內的 <div class="accordion accordion-flush"> 區塊
        accordion_divs: List[Tag] = soup.select(
            "div.tab-content div.accordion.accordion-flush"
        )
        results: List[Product] = []

        # Precollect product buttons so progress can be shown
        buttons: List[Tag] = []
        for div in accordion_divs:
            for btn in div.select(
                "div#side-sell-single h2.accordion-header > button[onclick]"
            ):
                if btn.find_parent(id="side-sell-target-11"):
                    continue
                buttons.append(btn)

        total = len(buttons)
        for idx, btn in enumerate(buttons, 1):
            onclick_attr = btn.get("onclick", "")
            m = re.search(r"location\.href=['\"]([^'\"]+)['\"]", onclick_attr)
            if not m:
                continue

            print(f"[parse] {idx}/{total} {btn.get_text(strip=True)}", flush=True)
            product = Product(
                name=btn.get_text(strip=True),
                url=m.group(1),
            )
            try:
                product_html = self.fetch_page(product.url)
                product.cards = self.parse_product_page(product_html)
            except requests.RequestException:
                product.cards = []
            results.append(product)
        return results

    def __del__(self) -> None:  # pragma: no cover - cleanup
        if self.driver is not None:
            try:
                self.driver.quit()
            except Exception:
                pass


if __name__ == "__main__":  # Quick manual test
    import json

    scraper = Scraper("https://yuyu-tei.jp/top/opc", use_selenium=True)
    data = scraper.run()
    print(json.dumps([p.__dict__ for p in data], ensure_ascii=False, indent=2))
