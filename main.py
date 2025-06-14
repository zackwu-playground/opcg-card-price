# -*- coding: utf-8 -*-
"""main.py
程式進入點 – 組合 Scraper / DB / GUI
=====================================
執行範例：
    python main.py --url https://yuyu-tei.jp/top/opc --db scraped_data.db --gui
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from scraper import Scraper
from db_manager import DatabaseManager


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily web scraper with optional GUI")
    parser.add_argument("--url", required=True, help="Target URL to scrape")
    parser.add_argument("--db", default="scraped_data.db", help="SQLite file path")
    parser.add_argument("--gui", action="store_true", help="Launch Qt GUI after scraping")
    return parser


def create_job(url: str, db_path: str) -> Callable[[], None]:
    """Closure：返回實際執行爬蟲的函式。"""

    def job():
        scr = Scraper(url)
        html = scr.fetch()
        data = scr.parse(html)
        if data:
            db = DatabaseManager(db_path)
            db.insert_products(data)
            print(f"[✓] {len(data)} records inserted.")
        else:
            print("[!] No data scraped – check selectors?")

    return job


def main():
    args = build_arg_parser().parse_args()

    # 先確認 DB 檔存在與否，不存在會自動建立
    Path(args.db).touch(exist_ok=True)

    # 直接執行一次 --------------------------------------------------------
    create_job(args.url, args.db)()
    print("[✓] Scraping completed.")
