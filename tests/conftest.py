# -*- coding: utf-8 -*-
"""共用 pytest fixtures。"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from models import Card, Product


@pytest.fixture
def scraper_no_selenium():
    """建立 use_selenium=False 的 Scraper，不需要 ChromeDriver。"""
    with patch("scraper.webdriver"):
        from scraper import Scraper

        s = Scraper("https://example.com", use_selenium=False)
    return s


@pytest.fixture
def tmp_db(tmp_path):
    """回傳暫存 SQLite 路徑字串。"""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_card() -> Card:
    return Card(
        name="TestCard",
        rarity="SR",
        url="https://example.com/card/1",
        image=b"\x89PNG_fake_image_data",
        number="OP01-001",
        price=500,
        quantity=3,
        scraped_at=date(2025, 1, 1),
        feature="速攻",
        color="赤",
    )


@pytest.fixture
def sample_product(sample_card) -> Product:
    return Product(
        name="TestProduct",
        url="https://example.com/product/1",
        cards=[sample_card],
    )
