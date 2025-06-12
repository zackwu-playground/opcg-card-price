# -*- coding: utf-8 -*-
"""
專業爬蟲工具 (範例骨架)
========================
Python 3.11+
核心功能：
1. 每日定時抓取指定網站資料
2. 以 SQLite 儲存結果
3. 內建 GUI (PyQt5) 顯示統計與曲線圖

必要套件 (requirements.txt)：
    requests
    beautifulsoup4
    sqlalchemy
    apscheduler
    pandas
    matplotlib
    PyQt5

安裝：
    pip install -r requirements.txt

啟動範例 (含 GUI)：
    python web_scraper_tool.py --url https://example.com --hour 4 --minute 0 --gui
"""

import sys
from datetime import datetime
from typing import List, Dict

import pandas as pd
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from bs4 import BeautifulSoup
from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# -----------------------------
# 資料庫設定
# -----------------------------
Base = declarative_base()


class ScrapedData(Base):
    """對應 scraped_data 資料表的 ORM 模型。"""

    __tablename__ = "scraped_data"

    id = Column(Integer, primary_key=True)
    title = Column(String(255))
    content = Column(Text)
    scraped_at = Column(DateTime, default=datetime.utcnow)


class DatabaseManager:
    """封裝所有與 SQLite 互動的細節。"""

    def __init__(self, db_url: str = "sqlite:///data.db") -> None:
        self.engine = create_engine(db_url, echo=False, future=True)
        Base.metadata.create_all(self.engine)
        self._Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    def add_records(self, records: List[Dict]) -> None:
        """批次寫入多筆資料。"""
        with self._Session() as session:
            session.add_all([ScrapedData(**rec) for rec in records])
            session.commit()

    def load_dataframe(self) -> pd.DataFrame:
        """以 pandas DataFrame 形式載入全部資料，方便後續統計。"""
        with self.engine.connect() as conn:
            return pd.read_sql_table("scraped_data", conn)


# -----------------------------
# 爬蟲核心
# -----------------------------
class Scraper:
    """單一網站爬蟲實作，可自行擴充多站點。"""

    def __init__(self, target_url: str) -> None:
        self.url = target_url

    def fetch(self) -> str:
        """發送 HTTP GET 並回傳 HTML 字串。"""
        resp = requests.get(self.url, timeout=10)
        resp.raise_for_status()
        return resp.text

    def parse(self, html: str) -> List[Dict]:
        """將 HTML 解析成資料列 (dict)。

        TODO: 依實際網站結構修改 CSS Selector / XPath。
        """
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article")  # 假設每筆資料包在 <article>
        records: List[Dict] = []
        for art in articles:
            title_tag = art.select_one("h2")
            if not title_tag:
                continue
            title = title_tag.get_text(strip=True)
            content = art.get_text(" ", strip=True)
            records.append(
                {
                    "title": title,
                    "content": content,
                    "scraped_at": datetime.utcnow(),
                }
            )
        return records

    def run(self, db: "DatabaseManager") -> None:
        """高階整合：抓取 → 解析 → 寫入 DB。"""
        html = self.fetch()
        records = self.parse(html)
        if records:
            db.add_records(records)
            print(f"{len(records)} records saved @ {datetime.utcnow().isoformat()}")
        else:
            print("[WARN] No records parsed – check selectors.")


# -----------------------------
# GUI (PyQt5 + Matplotlib)
# -----------------------------
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class StatsWindow(QMainWindow):
    """簡易統計介面，可依需求擴充多圖表/控制項。"""

    def __init__(self, db: "DatabaseManager") -> None:
        super().__init__()
        self.setWindowTitle("Scraped Data Statistics")
        self.resize(900, 600)

        self.db = db
        self._init_ui()
        self.refresh_plot()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        self.fig = Figure(figsize=(5, 4))
        self.canvas = FigureCanvas(self.fig)
        layout.addWidget(self.canvas)

    def refresh_plot(self) -> None:
        df = self.db.load_dataframe()
        if df.empty:
            return

        df["date"] = pd.to_datetime(df["scraped_at"]).dt.date
        daily_counts = df.groupby("date").size()

        ax = self.fig.subplots()
        ax.clear()
        daily_counts.plot(kind="line", ax=ax, marker="o")
        ax.set_title("Daily Article Count")
        ax.set_xlabel("Date")
        ax.set_ylabel("Articles")
        self.canvas.draw()


# -----------------------------
# 定時排程 (APScheduler)
# -----------------------------

def schedule_job(scraper: "Scraper", db: "DatabaseManager", hour: int = 3, minute: int = 0):
    """建立每天固定時間 (Asia/Taipei) 的排程工作。"""
    scheduler = BackgroundScheduler(timezone="Asia/Taipei")
    scheduler.add_job(
        scraper.run,
        "cron",
        args=[db],
        hour=hour,
        minute=minute,
        id="daily_scrape",
        replace_existing=True,
    )
    scheduler.start()
    print(f"Scheduler started: daily job at {hour:02d}:{minute:02d} Asia/Taipei")
    return scheduler


# -----------------------------
# 入口函式
# -----------------------------

def main() -> None:
    import argparse
    import time

    parser = argparse.ArgumentParser(description="Professional Web Scraping Tool")
    parser.add_argument("--url", required=True, help="Target website URL")
    parser.add_argument("--hour", type=int, default=3, help="Daily scrape hour (0-23)")
    parser.add_argument("--minute", type=int, default=0, help="Daily scrape minute")
    parser.add_argument("--gui", action="store_true", help="Launch GUI after scheduler start")
    args = parser.parse_args()

    db = DatabaseManager()
    scraper = Scraper(args.url)

    # 立即先跑一次 (避免等待排程)；可視需求移除
    scraper.run(db)

    scheduler = schedule_job(scraper, db, args.hour, args.minute)

    if args.gui:
        app = QApplication(sys.argv)
        win = StatsWindow(db)
        win.show()
        sys.exit(app.exec())
    else:
        try:
            while True:  # 保持主執行緒存活
                time.sleep(60)
        except (KeyboardInterrupt, SystemExit):
            scheduler.shutdown()


if __name__ == "__main__":
    main()
