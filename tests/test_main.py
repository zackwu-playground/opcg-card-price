# -*- coding: utf-8 -*-
"""main.py 的單元測試。"""
from __future__ import annotations

import logging
from datetime import date
from unittest.mock import patch, MagicMock

from models import Card, Product


# =====================================================================
# 14. logging 設定
# =====================================================================
class TestMainLogging:
    def test_main_configures_logging(self):
        with (
            patch("main.logging.basicConfig") as mock_basic,
            patch("main.build_arg_parser") as mock_parser,
            patch("main.create_job") as mock_job,
            patch("main.Path"),
        ):
            mock_args = MagicMock()
            mock_args.url = "https://example.com"
            mock_args.db = "test.db"
            mock_parser.return_value.parse_args.return_value = mock_args
            mock_job.return_value = MagicMock()

            from main import main

            main()
            mock_basic.assert_called_once()


# =====================================================================
# 15. job() 防禦性過濾
# =====================================================================
def _card(**kwargs):
    defaults = dict(
        name="C1",
        rarity="SR",
        url="",
        image=b"",
        number="OP01-001",
        price=100,
        quantity=1,
        scraped_at=date(2025, 1, 1),
    )
    defaults.update(kwargs)
    return Card(**defaults)


class TestJob:
    def test_job_filters_empty_products(self, tmp_db):
        p_with_cards = Product(name="P1", url="u1", cards=[_card()])
        p_empty = Product(name="P2", url="u2", cards=[])

        with (
            patch("main.Scraper") as MockScraper,
            patch("main.DatabaseManager") as MockDB,
        ):
            mock_scr = MockScraper.return_value
            mock_scr.fetch.return_value = "<html></html>"
            mock_scr.parse.return_value = [p_with_cards, p_empty]

            from main import create_job

            job = create_job("https://example.com", tmp_db)
            job()

            # DB 只應收到有卡片的產品
            MockDB.return_value.insert_products.assert_called_once()
            products_arg = MockDB.return_value.insert_products.call_args[0][0]
            assert len(products_arg) == 1
            assert products_arg[0].name == "P1"

    def test_job_logs_warning_when_no_data(self, caplog, tmp_db):
        with patch("main.Scraper") as MockScraper:
            mock_scr = MockScraper.return_value
            mock_scr.fetch.return_value = "<html></html>"
            mock_scr.parse.return_value = []

            from main import create_job

            job = create_job("https://example.com", tmp_db)
            with caplog.at_level(logging.WARNING, logger="main"):
                job()

        assert "未爬取到任何資料" in caplog.text
