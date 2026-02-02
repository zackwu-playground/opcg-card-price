# -*- coding: utf-8 -*-
"""scraper.py 的單元測試。"""
from __future__ import annotations

import logging
import time
from datetime import date
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

from models import Card


# ── Helper：建立 Scraper 但不啟動真正的 ChromeDriver ──────────────────
def _make_scraper(**kwargs):
    """建立 Scraper，預設 use_selenium=False 以避免需要 ChromeDriver。"""
    with patch("scraper.webdriver"):
        from scraper import Scraper

        defaults = {"url": "https://example.com", "use_selenium": False}
        defaults.update(kwargs)
        return Scraper(**defaults)


# =====================================================================
# 1. 預設值與初始化
# =====================================================================
class TestScraperInit:
    def test_default_timeout_is_30(self):
        s = _make_scraper()
        assert s.timeout == 30

    def test_rate_limiter_initialized(self):
        s = _make_scraper()
        assert hasattr(s, "_rate_lock")
        assert hasattr(s, "_last_request_time")
        assert s._last_request_time == 0.0

    def test_chromedriver_failure_logs_warning(self, caplog):
        """mock webdriver.Chrome 拋出例外，確認 driver is None 且有 warning。"""
        with patch("scraper.webdriver") as mock_wd:
            mock_wd.Chrome.side_effect = RuntimeError("no chromedriver")
            # 需要讓 webdriver is not None 為 True（預設 MagicMock 即可）
            from scraper import Scraper

            with caplog.at_level(logging.WARNING, logger="scraper"):
                s = Scraper("https://example.com", use_selenium=True)
            assert s.driver is None
            assert "ChromeDriver 啟動失敗" in caplog.text


# =====================================================================
# 2. Rate limiter
# =====================================================================
class TestRateLimiter:
    def test_rate_limit_enforces_interval(self):
        s = _make_scraper()
        s.request_interval = 0.05
        s._rate_limit()
        t0 = time.monotonic()
        s._rate_limit()
        elapsed = time.monotonic() - t0
        assert elapsed >= 0.04  # 容許少量浮點誤差

    def test_rate_limit_no_wait_when_interval_passed(self):
        s = _make_scraper()
        s.request_interval = 0.05
        s._last_request_time = time.monotonic() - 10  # 很早之前
        t0 = time.monotonic()
        s._rate_limit()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.04


# =====================================================================
# 3. fetch() / fetch_page() — requests 路徑
# =====================================================================
class TestFetchRequests:
    def test_fetch_uses_requests_when_no_selenium(self):
        s = _make_scraper()
        mock_resp = MagicMock()
        mock_resp.text = "<html>OK</html>"
        s.session.get = MagicMock(return_value=mock_resp)
        result = s.fetch()
        assert result == "<html>OK</html>"
        s.session.get.assert_called_once()

    def test_fetch_page_uses_requests_when_no_selenium(self):
        s = _make_scraper()
        mock_resp = MagicMock()
        mock_resp.text = "<html>page</html>"
        s.session.get = MagicMock(return_value=mock_resp)
        result = s.fetch_page("https://example.com/p")
        assert result == "<html>page</html>"


# =====================================================================
# 4. fetch() / fetch_page() — Selenium TimeoutException
# =====================================================================
class TestFetchSeleniumTimeout:
    def _make_selenium_scraper(self):
        s = _make_scraper(use_selenium=True)
        # 手動設定 driver mock
        s.use_selenium = True
        s.driver = MagicMock()
        return s

    def test_fetch_selenium_timeout_logs_warning(self, caplog):
        from selenium.common.exceptions import TimeoutException

        s = self._make_selenium_scraper()
        s.driver.get.side_effect = TimeoutException("timeout")
        s.driver.page_source = "<html>" + "x" * 600 + "</html>"
        with caplog.at_level(logging.WARNING, logger="scraper"):
            html = s.fetch()
        assert len(html) >= 500
        assert "TimeoutException" in caplog.text

    def test_fetch_selenium_short_page_raises(self):
        from selenium.common.exceptions import TimeoutException

        s = self._make_selenium_scraper()
        s.driver.get.side_effect = TimeoutException("timeout")
        s.driver.page_source = "<html>short</html>"
        with pytest.raises(RuntimeError, match="頁面過短"):
            s.fetch()

    def test_fetch_page_selenium_short_page_raises(self):
        from selenium.common.exceptions import TimeoutException

        s = self._make_selenium_scraper()
        s.driver.get.side_effect = TimeoutException("timeout")
        s.driver.page_source = "<html>short</html>"
        with pytest.raises(RuntimeError, match="頁面過短"):
            s.fetch_page("https://example.com/p")


# =====================================================================
# 5. _fetch_page_requests()
# =====================================================================
class TestFetchPageRequests:
    def test_fetch_page_requests_uses_session(self):
        s = _make_scraper()
        s.request_interval = 0  # 加速測試
        mock_resp = MagicMock()
        mock_resp.text = "<html>worker</html>"
        s.session.get = MagicMock(return_value=mock_resp)
        result = s._fetch_page_requests("https://example.com/card")
        assert result == "<html>worker</html>"
        s.session.get.assert_called_once()

    def test_fetch_page_requests_raises_on_error(self):
        s = _make_scraper()
        s.request_interval = 0
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = requests.HTTPError("500")
        s.session.get = MagicMock(return_value=mock_resp)
        with pytest.raises(requests.HTTPError):
            s._fetch_page_requests("https://example.com/card")


# =====================================================================
# 6. parse_card_page()
# =====================================================================
# 完整的 HTML fixture，模仿實際網頁結構
CARD_PAGE_HTML = """
<html><body>
<section class="product-detail" id="product-detail">
  <div class="col-lg-5">
    <img class="vimg" src="https://img.yuyu-tei.jp/card_image/opc/test.jpg" />
  </div>
  <div class="col-lg-7">
    <div class="table-responsive">
      <table><tr>
        <td class="text-dark">速攻</td>
        <td class="text-dark">赤</td>
      </tr></table>
    </div>
    <div class="d-flex">
      <span class="border">OP01-001</span>
    </div>
    <div class="d-flex">
      <h4 class="fw-bold">500円</h4>
      <label class="form-check-label">在庫 : 3 点</label>
    </div>
  </div>
</section>
</body></html>
"""


class TestParseCardPage:
    def test_parse_card_page_full_html(self):
        s = _make_scraper()
        s.request_interval = 0
        # mock 圖片下載
        mock_resp = MagicMock()
        mock_resp.content = b"imgdata"
        s.session.get = MagicMock(return_value=mock_resp)

        card = s.parse_card_page(CARD_PAGE_HTML)
        assert card.number == "OP01-001"
        assert card.price == 500
        assert card.quantity == 3
        assert card.feature == "速攻"
        assert card.color == "赤"
        assert card.image == b"imgdata"

    def test_parse_card_page_empty_container(self):
        s = _make_scraper()
        card = s.parse_card_page("<html><body></body></html>")
        assert card.number == ""
        assert card.price == 0
        assert card.quantity == 0

    def test_parse_card_page_image_download_failure(self, caplog):
        s = _make_scraper()
        s.request_interval = 0
        s.session.get = MagicMock(side_effect=requests.RequestException("fail"))

        with caplog.at_level(logging.WARNING, logger="scraper"):
            card = s.parse_card_page(CARD_PAGE_HTML)
        assert card.image == b""
        assert "圖片下載失敗" in caplog.text


# =====================================================================
# 7. parse_product_page()
# =====================================================================
PRODUCT_PAGE_HTML_WITH_CU = """
<html><body>
<div class="col-12 mb-5 pb-5">
  <div id="card-list3" class="py-4">
    <div class="py-2">C</div>
    <div class="row"><div class="col-md">
      <a href="https://example.com/c1"><span class="text-primary">Common Card</span></a>
    </div></div>
  </div>
  <div id="card-list3" class="py-4">
    <div class="py-2">UC</div>
    <div class="row"><div class="col-md">
      <a href="https://example.com/uc1"><span class="text-primary">Uncommon Card</span></a>
    </div></div>
  </div>
  <div id="card-list3" class="py-4">
    <div class="py-2">SR</div>
    <div class="row"><div class="col-md">
      <a href="https://example.com/sr1"><span class="text-primary">SR Card</span></a>
    </div></div>
  </div>
</div>
</body></html>
"""


class TestParseProductPage:
    def test_parse_product_page_skips_common_uncommon(self):
        s = _make_scraper()
        s.request_interval = 0

        # mock _fetch_page_requests 回傳 card HTML
        def fake_fetch(url):
            return CARD_PAGE_HTML

        s._fetch_page_requests = MagicMock(side_effect=fake_fetch)
        # mock session.get 以處理圖片下載
        mock_resp = MagicMock()
        mock_resp.content = b"img"
        s.session.get = MagicMock(return_value=mock_resp)

        cards = s.parse_product_page(PRODUCT_PAGE_HTML_WITH_CU)
        # C 和 UC 被跳過，只有 SR 的 1 張卡
        assert len(cards) == 1
        assert cards[0].rarity == "SR"
        # _fetch_page_requests 只被呼叫 1 次（SR card）
        assert s._fetch_page_requests.call_count == 1

    def test_parse_product_page_uses_requests_not_selenium(self):
        s = _make_scraper()
        s.request_interval = 0

        s._fetch_page_requests = MagicMock(return_value=CARD_PAGE_HTML)
        mock_resp = MagicMock()
        mock_resp.content = b"img"
        s.session.get = MagicMock(return_value=mock_resp)

        # 建立一個簡單的 product HTML，有 1 張 SR 卡
        html = """
        <html><body>
        <div class="col-12 mb-5 pb-5">
          <div id="card-list3" class="py-4">
            <div class="py-2">SR</div>
            <div class="row"><div class="col-md">
              <a href="https://example.com/sr1"><span class="text-primary">SR1</span></a>
            </div></div>
          </div>
        </div>
        </body></html>
        """
        cards = s.parse_product_page(html)
        s._fetch_page_requests.assert_called_once()

    def test_parse_product_page_worker_failure_returns_none(self, caplog):
        s = _make_scraper()
        s.request_interval = 0
        s._fetch_page_requests = MagicMock(
            side_effect=requests.RequestException("network error")
        )

        html = """
        <html><body>
        <div class="col-12 mb-5 pb-5">
          <div id="card-list3" class="py-4">
            <div class="py-2">SR</div>
            <div class="row"><div class="col-md">
              <a href="https://example.com/sr1"><span class="text-primary">SR1</span></a>
            </div></div>
          </div>
        </div>
        </body></html>
        """
        with caplog.at_level(logging.WARNING, logger="scraper"):
            cards = s.parse_product_page(html)
        assert len(cards) == 0
        assert "卡片頁面下載失敗" in caplog.text


# =====================================================================
# 8. parse() — 過濾空產品
# =====================================================================
class TestParse:
    def test_parse_skips_empty_products(self):
        s = _make_scraper()

        # 模擬 parse 的 HTML 含有 2 個 product button
        html = """
        <html><body>
        <div class="tab-content">
          <div class="accordion accordion-flush">
            <div id="side-sell-single">
              <h2 class="accordion-header">
                <button onclick="location.href='https://example.com/p1'">Product1</button>
              </h2>
              <h2 class="accordion-header">
                <button onclick="location.href='https://example.com/p2'">Product2</button>
              </h2>
            </div>
          </div>
        </div>
        </body></html>
        """
        # fetch_page 回傳虛擬 HTML
        s.fetch_page = MagicMock(return_value="<html></html>")
        # 第一個產品有卡片，第二個回傳空 list
        call_count = [0]

        def mock_parse_product(h):
            call_count[0] += 1
            if call_count[0] == 1:
                return [
                    Card(
                        name="C1",
                        rarity="SR",
                        url="",
                        image=b"",
                        number="OP01-001",
                        price=100,
                        quantity=1,
                        scraped_at=date.today(),
                    )
                ]
            return []

        s.parse_product_page = MagicMock(side_effect=mock_parse_product)
        results = s.parse(html)
        # 只有第一個產品有卡片
        assert len(results) == 1
        assert results[0].name == "Product1"

    def test_parse_logs_skipped_products(self, caplog):
        s = _make_scraper()

        html = """
        <html><body>
        <div class="tab-content">
          <div class="accordion accordion-flush">
            <div id="side-sell-single">
              <h2 class="accordion-header">
                <button onclick="location.href='https://example.com/p1'">EmptyProduct</button>
              </h2>
            </div>
          </div>
        </div>
        </body></html>
        """
        s.fetch_page = MagicMock(return_value="<html></html>")
        s.parse_product_page = MagicMock(return_value=[])

        with caplog.at_level(logging.INFO, logger="scraper"):
            results = s.parse(html)
        assert len(results) == 0
        assert "跳過空產品" in caplog.text
