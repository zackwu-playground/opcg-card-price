# -*- coding: utf-8 -*-
"""gui_app.py
統計圖形化介面 (Qt5 + Matplotlib)
================================
• 從 SQLite 載入資料 -> pandas.DataFrame -> 折線圖
• 可手動 refresh 資料 (示範用)
"""
from __future__ import annotations

import sys
from typing import Optional

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QPushButton

from db_manager import DatabaseManager

__all__ = ["StatsWindow", "launch_gui"]


class StatsWindow(QMainWindow):
    """簡易統計視窗：每日抓取...
