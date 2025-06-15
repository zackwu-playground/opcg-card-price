# -*- coding: utf-8 -*-
"""Graphical interface for viewing card price history.

This module defines :class:`StatsWindow` which loads card data from the
SQLite database created by :mod:`db_manager` and displays simple line
plots using Matplotlib.  Users can filter data by product name, rarity,
price range, date range, feature and colour.  Multiple selections are
allowed for the categorical filters.
"""
from __future__ import annotations

import sys
from typing import Iterable

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QAbstractItemView,
    QLabel,
    QSpinBox,
    QDateEdit,
    QPushButton,
)
from PyQt5.QtCore import QDate

from db_manager import DatabaseManager

__all__ = ["StatsWindow", "launch_gui"]


class StatsWindow(QMainWindow):
    """Simple statistics viewer with filter options."""

    def __init__(self, db_path: str = "scraped_data.db") -> None:
        super().__init__()
        self.db_path = db_path
        self.db = DatabaseManager(db_path=db_path)
        self.setWindowTitle("Card Price Stats")

        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)

        # Filter widgets -------------------------------------------------
        self.product_list = self._create_list_widget()
        self.rarity_list = self._create_list_widget()
        self.feature_list = self._create_list_widget()
        self.color_list = self._create_list_widget()

        self.min_price = QSpinBox()
        self.max_price = QSpinBox()
        for spin in (self.min_price, self.max_price):
            spin.setRange(0, 1_000_000)

        self.start_date = QDateEdit(calendarPopup=True)
        self.end_date = QDateEdit(calendarPopup=True)

        self.refresh_btn = QPushButton("Refresh")
        self.plot_btn = QPushButton("Plot")

        self.refresh_btn.clicked.connect(self.load_data)
        self.plot_btn.clicked.connect(self.update_plot)

        filter_row1 = QHBoxLayout()
        filter_row1.addWidget(QLabel("Product"))
        filter_row1.addWidget(self.product_list)
        filter_row1.addWidget(QLabel("Rarity"))
        filter_row1.addWidget(self.rarity_list)

        filter_row2 = QHBoxLayout()
        filter_row2.addWidget(QLabel("Feature"))
        filter_row2.addWidget(self.feature_list)
        filter_row2.addWidget(QLabel("Color"))
        filter_row2.addWidget(self.color_list)

        filter_row3 = QHBoxLayout()
        filter_row3.addWidget(QLabel("Min price"))
        filter_row3.addWidget(self.min_price)
        filter_row3.addWidget(QLabel("Max price"))
        filter_row3.addWidget(self.max_price)
        filter_row3.addWidget(QLabel("Start"))
        filter_row3.addWidget(self.start_date)
        filter_row3.addWidget(QLabel("End"))
        filter_row3.addWidget(self.end_date)
        filter_row3.addWidget(self.refresh_btn)
        filter_row3.addWidget(self.plot_btn)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addLayout(filter_row1)
        layout.addLayout(filter_row2)
        layout.addLayout(filter_row3)
        layout.addWidget(self.canvas)
        self.setCentralWidget(central)

        self.df: pd.DataFrame = pd.DataFrame()
        self.load_data()

    # ------------------------------------------------------------------
    def _create_list_widget(self) -> QListWidget:
        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.MultiSelection)
        lst.setMinimumWidth(150)
        return lst

    # ------------------------------------------------------------------
    def load_data(self) -> None:
        """Load data from the database and populate filter widgets."""
        self.df = self.db.fetch_dataframe()

        for widget, column in [
            (self.product_list, "product"),
            (self.rarity_list, "rarity"),
            (self.feature_list, "feature"),
            (self.color_list, "color"),
        ]:
            widget.clear()
            for value in sorted(self.df[column].dropna().unique()):
                QListWidgetItem(str(value), widget)

        if not self.df.empty:
            self.min_price.setValue(int(self.df["price"].min()))
            self.max_price.setValue(int(self.df["price"].max()))
            min_date = self.df["scraped_at"].min()
            max_date = self.df["scraped_at"].max()
            self.start_date.setDate(QDate(min_date.year, min_date.month, min_date.day))
            self.end_date.setDate(QDate(max_date.year, max_date.month, max_date.day))

        self.update_plot()

    # ------------------------------------------------------------------
    def _selected_values(self, widget: QListWidget) -> Iterable[str]:
        return [item.text() for item in widget.selectedItems()]

    # ------------------------------------------------------------------
    def update_plot(self) -> None:
        """Filter ``self.df`` based on UI selections and update the chart."""
        if self.df.empty:
            return

        df = self.df.copy()

        selections = self._selected_values(self.product_list)
        if selections:
            df = df[df["product"].isin(selections)]

        selections = self._selected_values(self.rarity_list)
        if selections:
            df = df[df["rarity"].isin(selections)]

        selections = self._selected_values(self.feature_list)
        if selections:
            df = df[df["feature"].isin(selections)]

        selections = self._selected_values(self.color_list)
        if selections:
            df = df[df["color"].isin(selections)]

        df = df[(df["price"] >= self.min_price.value()) & (df["price"] <= self.max_price.value())]

        start = self.start_date.date().toPyDate()
        end = self.end_date.date().toPyDate()
        df = df[(df["scraped_at"] >= start) & (df["scraped_at"] <= end)]

        self.ax.clear()
        if df.empty:
            self.ax.set_title("No data")
            self.canvas.draw()
            return

        grouped = df.groupby(["card", "scraped_at"])["price"].mean().reset_index()
        for card_name, data in grouped.groupby("card"):
            self.ax.plot(data["scraped_at"], data["price"], marker="o", label=card_name)

        self.ax.legend()
        self.ax.set_xlabel("Date")
        self.ax.set_ylabel("Price")
        self.figure.autofmt_xdate()
        self.canvas.draw()


def launch_gui(db_path: str) -> None:
    """Convenience function to launch :class:`StatsWindow`."""
    app = QApplication(sys.argv)
    win = StatsWindow(db_path)
    win.show()
    app.exec_()


if __name__ == "__main__":  # pragma: no cover - manual launch
    launch_gui("scraped_data.db")
