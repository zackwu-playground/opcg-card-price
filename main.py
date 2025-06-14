# -*- coding: utf-8 -*-
"""main.py
程式進入點 – 組合 Scraper / DB / Scheduler / GUI
================================================
指令列參數：
    python main.py --url https://yuyu-tei.jp/top/opc --db scraped_data.db --hour 4 --minute 0 --gui
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from scraper import Scraper
from db_manager import DatabaseManager
from scheduler import setup_daily_job

# GUI 部分僅在需要時匯入，避免無頭環境出錯
try:
    from gui_app import StatsWindow  # noqa: F401
except ImportError:
    StatsWindow = None  # type: ignore


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily web scraper with optional GUI")
    parser.add_argument("--url", required=True, help="Target URL to scrape")
    parser.add_argument("--db", default="scraped_data.db", help="SQLite file path")
    parser.add_argument("--hour", type=int, default=4, help="Execution hour (0-23)")
    parser.add_argument("--minute", type=int, default=0, help="Execution minute (0-59)")
    parser.add_argument("--gui", action="store_true", help="Launch Qt GUI after scheduler starts")
    parser.add_argument("--once", action="store_true", help="Run once immediately and exit (debug)")
    return parser


def create_job(url: str, db_path: str) -> Callable[[], None]:
    """Closure：返回實際被 scheduler 呼叫的函式。"""

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

    if args.once:
        create_job(args.url, args.db)()
        sys.exit(0)

    # 建立排程 ------------------------------------------------------------
    scheduler = setup_daily_job(
        hour=args.hour,
        minute=args.minute,
        job_func=create_job(args.url, args.db),
        timezone="Asia/Taipei",
    )
    scheduler.start()
    print(f"[+] Scheduler started – next run at {scheduler.get_job('daily_scrape').next_run_time}")

    # optionally launch GUI ----------------------------------------------
    if args.gui:
        if StatsWindow is None:
            print("[!] PyQt5 / matplotlib not installed – cannot launch GUI")
            sys.exit(1)
        else:
            from PyQt5.QtWidgets import QApplication

            app = QApplication(sys.argv)
            window = StatsWindow(db_path=args.db)
            window.show()
            sys.exit(app.exec_())
    else:
        # 無 GUI 的話維持主執行緒常駐
        try:
            while True:
                scheduler._event.wait(1)  # type: ignore  # pylint:disable=protected-access
        except (KeyboardInterrupt, SystemExit):
            print("[x] Exiting…")


if __name__ == "__main__":
    main()
