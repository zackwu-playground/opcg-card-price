# -*- coding: utf-8 -*-
"""db_manager.py 的單元測試。"""
from __future__ import annotations

from datetime import date

from models import Card, Product
from db_manager import DatabaseManager, CardTable, CardPrice


def _card(
    name="TestCard",
    number="OP01-001",
    rarity="SR",
    url="https://example.com/c",
    image=b"",
    price=100,
    quantity=1,
    feature="",
    color="",
    scraped_at=None,
) -> Card:
    return Card(
        name=name,
        rarity=rarity,
        url=url,
        image=image,
        number=number,
        price=price,
        quantity=quantity,
        scraped_at=scraped_at or date(2025, 1, 1),
        feature=feature,
        color=color,
    )


def _product(name="TestProduct", url="https://example.com/p", cards=None) -> Product:
    return Product(name=name, url=url, cards=cards or [])


# =====================================================================
# 9. 唯一鍵 (product_id, name, number)
# =====================================================================
class TestUniqueKey:
    def test_same_name_different_number_creates_two_cards(self, tmp_db):
        db = DatabaseManager(tmp_db)
        c1 = _card(name="Card", number="OP01-001")
        c2 = _card(name="Card", number="OP01-002")
        db.insert_products([_product(cards=[c1, c2])])

        with db.SessionLocal() as session:
            count = session.query(CardTable).count()
        assert count == 2

    def test_same_name_same_number_no_duplicate(self, tmp_db):
        db = DatabaseManager(tmp_db)
        c1 = _card(name="Card", number="OP01-001")
        db.insert_products([_product(cards=[c1])])
        # 再次插入相同的卡片
        c2 = _card(name="Card", number="OP01-001")
        db.insert_products([_product(cards=[c2])])

        with db.SessionLocal() as session:
            count = session.query(CardTable).count()
        assert count == 1


# =====================================================================
# 10. 既有 card 靜態欄位更新
# =====================================================================
class TestStaticFieldUpdate:
    def test_existing_card_updates_static_fields(self, tmp_db):
        db = DatabaseManager(tmp_db)
        c1 = _card(feature="速攻", color="赤", url="https://old.com")
        db.insert_products([_product(cards=[c1])])

        # 同 name + number，不同 url/feature/color
        c2 = _card(feature="ブロッカー", color="青", url="https://new.com")
        db.insert_products([_product(cards=[c2])])

        with db.SessionLocal() as session:
            card_obj = session.query(CardTable).one()
        assert card_obj.url == "https://new.com"
        assert card_obj.feature == "ブロッカー"
        assert card_obj.color == "青"


# =====================================================================
# 11. 圖片覆寫
# =====================================================================
class TestImageOverwrite:
    def test_image_overwrite_when_new_image(self, tmp_db):
        db = DatabaseManager(tmp_db)
        c1 = _card(image=b"old_image")
        db.insert_products([_product(cards=[c1])])

        # 確認圖片存在 (檔名格式: {number}_{name}.jpg)
        prod_dir = db.picture_dir / "TestProduct"
        img_path = prod_dir / "OP01-001_TestCard.jpg"
        assert img_path.exists()
        assert img_path.read_bytes() == b"old_image"

        # 插入新圖片
        c2 = _card(image=b"new_image")
        db.insert_products([_product(cards=[c2])])
        assert img_path.read_bytes() == b"new_image"

    def test_no_image_does_not_create_file(self, tmp_db):
        db = DatabaseManager(tmp_db)
        c1 = _card(image=b"")
        db.insert_products([_product(cards=[c1])])

        prod_dir = db.picture_dir / "TestProduct"
        img_path = prod_dir / "OP01-001_TestCard.jpg"
        assert not img_path.exists()


# =====================================================================
# 12. CardPrice 不重複
# =====================================================================
class TestCardPriceNoDuplicate:
    def test_same_date_no_duplicate_price(self, tmp_db):
        db = DatabaseManager(tmp_db)
        d = date(2025, 1, 1)
        c1 = _card(scraped_at=d, price=100)
        db.insert_products([_product(cards=[c1])])
        # 再次插入同日期
        c2 = _card(scraped_at=d, price=200)
        db.insert_products([_product(cards=[c2])])

        with db.SessionLocal() as session:
            count = session.query(CardPrice).count()
        assert count == 1


# =====================================================================
# 13. 空產品清單
# =====================================================================
class TestEmptyProducts:
    def test_insert_empty_products_no_error(self, tmp_db):
        db = DatabaseManager(tmp_db)
        db.insert_products([])  # 不應報錯


# =====================================================================
# 14. get_existing_images
# =====================================================================
class TestGetExistingImages:
    def test_returns_empty_set_when_no_product_dir(self, tmp_db):
        db = DatabaseManager(tmp_db)
        result = db.get_existing_images("NonExistent")
        assert result == set()

    def test_returns_image_keys_from_existing_files(self, tmp_db):
        db = DatabaseManager(tmp_db)
        # 建立產品目錄與假圖片
        prod_dir = db.picture_dir / "TestProduct"
        prod_dir.mkdir(parents=True, exist_ok=True)
        (prod_dir / "OP01-001_CardA.jpg").write_bytes(b"img1")
        (prod_dir / "OP01-002_CardB.jpg").write_bytes(b"img2")

        result = db.get_existing_images("TestProduct")
        assert result == {"OP01-001_CardA", "OP01-002_CardB"}

    def test_ignores_non_jpg_files(self, tmp_db):
        db = DatabaseManager(tmp_db)
        prod_dir = db.picture_dir / "TestProduct"
        prod_dir.mkdir(parents=True, exist_ok=True)
        (prod_dir / "OP01-001_CardA.jpg").write_bytes(b"img")
        (prod_dir / "OP01-002_CardB.png").write_bytes(b"png")
        (prod_dir / "readme.txt").write_text("txt")

        result = db.get_existing_images("TestProduct")
        assert result == {"OP01-001_CardA"}

    def test_sanitizes_product_name(self, tmp_db):
        db = DatabaseManager(tmp_db)
        # 產品名稱含特殊字元
        prod_name = "Product:Test/Name"
        safe_name = "Product_Test_Name"
        prod_dir = db.picture_dir / safe_name
        prod_dir.mkdir(parents=True, exist_ok=True)
        (prod_dir / "OP01-001_Card.jpg").write_bytes(b"img")

        result = db.get_existing_images(prod_name)
        assert result == {"OP01-001_Card"}
