# -*- coding: utf-8 -*-
"""Data access layer using SQLAlchemy.

This module defines ORM models for scraped products and cards. Only the
price and quantity values change over time, so they are stored in a
separate table ``CardPrice``. Other card information is stored once in
``Card`` and linked to a ``Product``.
"""
from __future__ import annotations

from datetime import date
from typing import List

from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Date,
    LargeBinary,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from models import Product

__all__ = ["DatabaseManager"]

Base = declarative_base()


class ProductTable(Base):
    """ORM model for product information."""

    __tablename__ = "product"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    name: str = Column(String(255), nullable=False, unique=True)
    url: str = Column(String(1024), nullable=False)


class CardTable(Base):
    """Static card information."""

    __tablename__ = "card"
    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uix_product_card_name"),
    )

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    product_id: int = Column(Integer, ForeignKey("product.id"), nullable=False)
    name: str = Column(String(255), nullable=False)
    rarity: str = Column(String(50), nullable=False)
    url: str = Column(String(1024), nullable=False)
    image: bytes = Column(LargeBinary)
    number: str = Column(String(50), nullable=False)
    feature: str = Column(String(50), default="")
    color: str = Column(String(50), default="")


class CardPrice(Base):
    """Time series table for price/quantity."""

    __tablename__ = "card_price"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    card_id: int = Column(Integer, ForeignKey("card.id"), nullable=False)
    price: int = Column(Integer, nullable=False)
    quantity: int = Column(Integer, nullable=False)
    scraped_at: date = Column(Date, default=date.today, nullable=False)


class DatabaseManager:
    """Wrapper around SQLite database operations."""

    def __init__(self, db_path: str | None = None):
        db_path = db_path or "scraped_data.db"
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
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

                for card in product.cards:
                    card_obj = (
                        session.query(CardTable)
                        .filter_by(product_id=prod_obj.id, name=card.name)
                        .one_or_none()
                    )
                    if card_obj is None:
                        card_obj = CardTable(
                            product_id=prod_obj.id,
                            name=card.name,
                            rarity=card.rarity,
                            url=card.url,
                            image=card.image,
                            number=card.number,
                            feature=card.feature,
                            color=card.color,
                        )
                        session.add(card_obj)
                        session.flush()

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
                session.query(CardPrice, CardTable, ProductTable)
                .join(CardTable, CardPrice.card_id == CardTable.id)
                .join(ProductTable, CardTable.product_id == ProductTable.id)
                .order_by(CardPrice.scraped_at)
                .all()
            )
            df = pd.DataFrame(
                [
                    {
                        "product": prod.name,
                        "card": card.name,
                        "number": card.number,
                        "price": price.price,
                        "quantity": price.quantity,
                        "scraped_at": price.scraped_at,
                    }
                    for price, card, prod in data
                ]
            )
            return df
