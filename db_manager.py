# -*- coding: utf-8 -*-
"""db_manager.py
資料庫存取層 (Data Access Layer)
=================================
• 使用 SQLAlchemy 2.0 ORM + SQLite
• 提供 insert_records() / fetch_dataframe() 等方便方法
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Dict

from sqlalchemy import create_engine, Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, Session

__all__ = ["DatabaseManager"]

Base = declarative_base()


class ScrapedData(Base):
    """ORM Model 對應到 scraped_data 資料表"""

    __tablename__ = "scraped_data"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    product_name: str = Column(String(255), nullable=False)
    url: str = Column(String(1024), nullable=False)
    scraped_at: datetime = Column(DateTime, default=datetime.utcnow, nullable=False)


class DatabaseManager:
    """封裝與 SQLite 的互動，降低不同層次耦合"""

    def __init__(self, db_path: str | None = None):
        # 若未指定路徑則使用預設檔案名稱
        db_path = db_path or "scraped_data.db"
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False, future=True)
        Base.metadata.create_all(self.engine)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False, future=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def insert_records(self, records: List[Dict[str, str]]) -> None:
        """批量插入解析結果。"""
        if not records:
            return
        with self.SessionLocal() as session:
            session: Session
            objs = [ScrapedData(**r) for r in records]
            session.add_all(objs)
            session.commit()

    def fetch_dataframe(self):
        """取得所有資料為 pandas DataFrame (供 GUI / 分析用)。"""
        try:
            import pandas as pd
        except ImportError as err:
            raise RuntimeError("需要 pandas 才能取得 DataFrame") from err

        with self.SessionLocal() as session:
            data = session.query(ScrapedData).order_by(ScrapedData.scraped_at).all()
            df = pd.DataFrame([
                {
                    "id": d.id,
                    "product_name": d.product_name,
                    "url": d.url,
                    "scraped_at": d.scraped_at,
                }
                for d in data
            ])
            return df
