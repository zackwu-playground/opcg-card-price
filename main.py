# -*- coding: utf-8 -*-
"""main.py
程式進入點 – 組合 Scraper 與資料庫
===============================
執行範例：
    python main.py --url https://yuyu-tei.jp/top/opc --db scraped_data.db
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Callable

from scraper import Scraper
from db_manager import DatabaseManager

logger = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily web scraper")
    parser.add_argument("--url", required=True, help="Target URL to scrape")
    parser.add_argument("--db", default="scraped_data.db", help="SQLite file path")
    return parser


def create_job(url: str, db_path: str) -> Callable[[], None]:
    """Closure：返回實際執行爬蟲的函式。"""

    def job():
        # 先建立 db 以便取得已存在圖片
        db = DatabaseManager(db_path)

        scr = Scraper(url)
        html = scr.fetch()
        # 傳入 get_existing_images callback，讓 scraper 跳過已存在的圖片
        data = scr.parse(html, get_existing_images=db.get_existing_images)

        # 防禦性過濾：排除沒有卡片的產品
        data = [p for p in data if p.cards]

        if data:
            db.insert_products(data)
            logger.info("[job] %d 筆產品已寫入資料庫。", len(data))
        else:
            logger.warning("[job] 未爬取到任何資料，請檢查選擇器或網站狀態。")

    return job


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    args = build_arg_parser().parse_args()

    # 先確認 DB 檔存在與否，不存在會自動建立
    Path(args.db).touch(exist_ok=True)

    # 直接執行一次 --------------------------------------------------------
    create_job(args.url, args.db)()
    logger.info("[main] 爬蟲作業完成。")


if __name__ == "__main__":
    main()
