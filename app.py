# -*- coding: utf-8 -*-
"""app.py
Launches the Qt GUI for browsing scraped data.

This script only opens the existing SQLite database and shows the GUI.
"""
from __future__ import annotations

import sys
from pathlib import Path

# GUI 部分僅在需要時匯入，避免無頭環境出錯
try:
    from gui_app import StatsWindow  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    StatsWindow = None  # type: ignore


def main() -> None:
    """Start the GUI using the provided DB path."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "scraped_data.db"
    Path(db_path).touch(exist_ok=True)

    if StatsWindow is None:
        print("[!] PyQt5 / matplotlib not installed – cannot launch GUI")
        sys.exit(1)

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = StatsWindow(db_path=db_path)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
