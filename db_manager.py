# -*- coding: utf-8 -*-
"""Data access layer using SQLAlchemy.

This module defines ORM models for scraped products and cards. Only the
price and quantity values change over time, so they are stored in a
separate table ``CardPrice``. Other card information is stored once in
``Card`` and linked to a ``Product``.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import List

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Date,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, relationship

from models import Product

__all__ = ["DatabaseManager"]

Base = declarative_base()


class ProductTable(Base):
    """ORM model for product information."""

    __tablename__ = "product"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(255), nullable=False, unique=True)
    url: str = Column(String(1024), nullable=False)


class RarityTable(Base):
    """Enumeration table for card rarity."""

    __tablename__ = "rarity"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(50), nullable=False, unique=True)


class CardTable(Base):
    """Static card information."""

    __tablename__ = "card"
    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uix_product_card_name"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    product_id: int = Column(Integer, ForeignKey("product.id"), nullable=False)
    name: str = Column(String(255), nullable=False)
    rarity_id: int = Column(Integer, ForeignKey("rarity.id"), nullable=False)
    rarity = relationship("RarityTable")
    url: str = Column(String(1024), nullable=False)
    number: str = Column(String(50), nullable=False)
    feature: str = Column(String(50), default="")
    color: str = Column(String(50), default="")


class CardPrice(Base):
    """Time series table for price/quantity."""

    __tablename__ = "card_price"
    __table_args__ = (
        UniqueConstraint("card_id", "scraped_at", name="uix_card_price_date"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    card_id: int = Column(Integer, ForeignKey("card.id"), nullable=False)
    price: int = Column(Integer, nullable=False)
    quantity: int = Column(Integer, nullable=False)
    scraped_at: date = Column(Date, default=date.today, nullable=False)


class DatabaseManager:
    """Wrapper around SQLite database operations."""

    def __init__(self, db_path: str | None = None):
        db_path = db_path or "scraped_data.db"
        self.db_path = Path(db_path)
        self.base_dir = self.db_path.parent
        # Picture files are stored under <db_dir>/picture/<product>/<card>.jpg
        self.picture_dir = self.base_dir / "picture"
        self.picture_dir.mkdir(exist_ok=True)

        self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False, future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    # ------------------------------------------------------------------
    def insert_products(self, products: List[Product]) -> None:
        """Insert scraped products and related data."""

        if not products:
            return
        with self.SessionLocal() as session:
            session: Session
            for product in products:
                prod_obj = (
                    session.query(ProductTable)
                    .filter_by(name=product.name, url=product.url)
                    .one_or_none()
                )
                if prod_obj is None:
                    prod_obj = ProductTable(name=product.name, url=product.url)
                    session.add(prod_obj)
                    session.flush()

                safe_prod = re.sub(r"[\\/:*?\"<>|]", "_", product.name)
                prod_dir = self.picture_dir / safe_prod
                prod_dir.mkdir(parents=True, exist_ok=True)

                for card in product.cards:
                    card_obj = (
                        session.query(CardTable)
                        .filter_by(product_id=prod_obj.id, name=card.name)
                        .one_or_none()
                    )
                    if card_obj is None:
                        rarity_obj = (
                            session.query(RarityTable)
                            .filter_by(name=card.rarity)
                            .one_or_none()
                        )
                        if rarity_obj is None:
                            rarity_obj = RarityTable(name=card.rarity)
                            session.add(rarity_obj)
                            session.flush()
                        if card.image:
                            safe_card = re.sub(r"[\\/:*?\"<>|]", "_", card.name)
                            file_path = prod_dir / f"{safe_card}.jpg"
                            if not file_path.exists():
                                file_path.write_bytes(card.image)

                        card_obj = CardTable(
                            product_id=prod_obj.id,
                            name=card.name,
                            rarity_id=rarity_obj.id,
                            url=card.url,
                            number=card.number,
                            feature=card.feature,
                            color=card.color,
                        )
                        session.add(card_obj)
                        session.flush()

                    # Skip insertion when a price for this card was already
                    # recorded on the same date.
                    existing_price = (
                        session.query(CardPrice)
                        .filter_by(card_id=card_obj.id, scraped_at=card.scraped_at)
                        .first()
                    )
                    if existing_price is None:
                        session.add(
                            CardPrice(
                                card_id=card_obj.id,
                                price=card.price,
                                quantity=card.quantity,
                                scraped_at=card.scraped_at,
                            )
                        )
            session.commit()

    def fetch_dataframe(self):
        """Return card price history as a pandas DataFrame."""

        try:
            import pandas as pd
        except ImportError as err:  # pragma: no cover - optional dependency
            raise RuntimeError("需要 pandas 才能取得 DataFrame") from err

        with self.SessionLocal() as session:
            data = (
                session.query(CardPrice, CardTable, ProductTable, RarityTable)
                .join(CardTable, CardPrice.card_id == CardTable.id)
                .join(ProductTable, CardTable.product_id == ProductTable.id)
                .join(RarityTable, CardTable.rarity_id == RarityTable.id)
                .order_by(CardPrice.scraped_at)
                .all()
            )
            df = pd.DataFrame(
                [
                    {
                        "product": prod.name,
                        "card": card.name,
                        "number": card.number,
                        "rarity": rarity.name,
                        "feature": card.feature,
                        "color": card.color,
                        "price": price.price,
                        "quantity": price.quantity,
                        "scraped_at": price.scraped_at,
                    }
                    for price, card, prod, rarity in data
                ]
            )
            return df
