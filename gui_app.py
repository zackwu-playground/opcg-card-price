# -*- coding: utf-8 -*-
"""Graphical interface for viewing card price history.

This module defines :class:`StatsWindow` which loads card data from the
SQLite database created by :mod:`db_manager` and displays simple line
plots using Matplotlib. Users can filter data by product name, rarity,
price range, date range, feature and colour. Multiple selection is
available only for the product filter; other categories use drop-down
menus.
"""
from __future__ import annotations

import sys, os, platform
from pathlib import Path
from typing import Iterable
import re

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

# Use a font that supports CJK characters so card names display correctly
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = [
    "Noto Sans CJK JP",
    "Microsoft JhengHei",
    "SimHei",
    "Source Han Sans",
    "Arial Unicode MS",
    "DejaVu Sans",
]
plt.rcParams["axes.unicode_minus"] = False
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QComboBox,
    QLineEdit,
    QCompleter,
    QAbstractItemView,
    QLabel,
    QSpinBox,
    QDateEdit,
    QPushButton,
    QSizePolicy,
)
from PyQt5 import QtCore
from PyQt5.QtCore import QDate
from PyQt5.QtCore import QLibraryInfo
from PyQt5.QtGui import QPixmap

from db_manager import DatabaseManager

from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name('.env'))

__all__ = ["StatsWindow", "launch_gui"]

class StatsWindow(QMainWindow):
    """Simple statistics viewer with filter options."""

    def __init__(self, db_path: str = "scraped_data.db") -> None:
        super().__init__()
        self.db_path = db_path
        self.db = DatabaseManager(db_path=db_path)
        self.setWindowTitle("Card Price Stats")
        self.resize(1000, 600)

        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("pick_event", self._on_pick)

        self.image_label = QLabel("No image")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.image_label.setScaledContents(True)

        # Filter widgets -------------------------------------------------
        self.product_list = self._create_list_widget(min_width=120)
        self.product_list.setFixedHeight(self.height() // 2)
        self.product_list.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.rarity_list = self._create_combo_box()
        self.color_list = self._create_combo_box()
        self.number_edit = QLineEdit()
        self.number_edit.setMinimumWidth(150)

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

        # Left side - product filter
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Product"))
        left_layout.addWidget(self.product_list)

        # Right side - other filters
        num_row = QHBoxLayout()
        self._add_labeled(num_row, "Number", self.number_edit)

        date_row = QHBoxLayout()
        self._add_labeled(date_row, "Start", self.start_date)
        self._add_labeled(date_row, "End", self.end_date)

        price_row = QHBoxLayout()
        self._add_labeled(price_row, "Min price", self.min_price)
        self._add_labeled(price_row, "Max price", self.max_price)

        rarity_row = QHBoxLayout()
        rarity_row.addWidget(QLabel("Rarity"))
        rarity_row.addWidget(self.rarity_list)

        color_row = QHBoxLayout()
        color_row.addWidget(QLabel("Color"))
        color_row.addWidget(self.color_list)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.refresh_btn)
        btn_row.addWidget(self.plot_btn)

        right_layout = QVBoxLayout()
        right_layout.addLayout(num_row)
        right_layout.addLayout(date_row)
        right_layout.addLayout(price_row)
        right_layout.addLayout(rarity_row)
        right_layout.addLayout(color_row)
        right_layout.addLayout(btn_row)

        filters_layout = QHBoxLayout()
        filters_layout.addLayout(left_layout)
        filters_layout.addLayout(right_layout)

        filter_top_widget = QWidget()
        filter_top_widget.setLayout(filters_layout)
        filter_top_widget.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

        filter_area_layout = QVBoxLayout()
        filter_area_layout.addWidget(filter_top_widget)
        filter_area_layout.addWidget(self.image_label)
        filter_area_layout.setStretch(0, 0)
        filter_area_layout.setStretch(1, 1)

        filters_widget = QWidget()
        filters_widget.setLayout(filter_area_layout)
        filters_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        filters_widget.setFixedWidth(filter_top_widget.sizeHint().width())

        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.addWidget(filters_widget)
        main_layout.addWidget(self.canvas)
        main_layout.setStretch(0, 0)
        main_layout.setStretch(1, 1)
        self.setCentralWidget(central)

        self.df: pd.DataFrame = pd.DataFrame()
        self.load_data()

    # ------------------------------------------------------------------
    def _create_list_widget(self, min_width: int = 150) -> QListWidget:
        lst = QListWidget()
        lst.setSelectionMode(QAbstractItemView.MultiSelection)
        lst.setMinimumWidth(min_width)
        return lst

    # ------------------------------------------------------------------
    def _create_combo_box(self) -> QComboBox:
        box = QComboBox()
        box.setMinimumWidth(150)
        box.setEditable(False)
        return box

    # ------------------------------------------------------------------
    def _add_labeled(self, layout: QHBoxLayout, text: str, widget: QWidget) -> None:
        """Helper to place a label next to a widget with minimal spacing."""
        container = QHBoxLayout()
        container.setSpacing(2)
        container.setContentsMargins(0, 0, 0, 0)
        container.addWidget(QLabel(text))
        container.addWidget(widget)
        layout.addLayout(container)

    # ------------------------------------------------------------------
    def load_data(self) -> None:
        """Load data from the database and populate filter widgets."""
        self.df = self.db.fetch_dataframe()

        for widget, column in [
            (self.product_list, "product"),
            (self.rarity_list, "rarity"),
            (self.color_list, "color"),
        ]:
            widget.clear()
            values = [str(v) for v in sorted(self.df[column].dropna().unique())]
            if isinstance(widget, QListWidget):
                for value in values:
                    QListWidgetItem(value, widget)
            elif isinstance(widget, QComboBox):
                widget.addItem("")
                for value in values:
                    widget.addItem(value)

        # Fixed width for product list based on longest item
        if not self.df.empty:
            metrics = self.product_list.fontMetrics()
            products = [str(v) for v in sorted(self.df["product"].dropna().unique())]
            if products:
                width = max(metrics.boundingRect(p).width() for p in products) + 20
                self.product_list.setFixedWidth(width)

        # Completer for card number entry
        numbers = [str(v) for v in sorted(self.df["number"].dropna().unique())]
        completer = QCompleter(numbers)
        completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        completer.setFilterMode(QtCore.Qt.MatchContains)
        self.number_edit.setCompleter(completer)

        if not self.df.empty:
            self.min_price.setValue(int(self.df["price"].min()))
            self.max_price.setValue(int(self.df["price"].max()))
            min_date = self.df["scraped_at"].min()
            max_date = self.df["scraped_at"].max()
            self.start_date.setDate(QDate(min_date.year, min_date.month, min_date.day))
            self.end_date.setDate(QDate(max_date.year, max_date.month, max_date.day))

        self.update_plot()

    # ------------------------------------------------------------------
    def _selected_values(self, widget: QWidget) -> Iterable[str]:
        if isinstance(widget, QListWidget):
            return [item.text() for item in widget.selectedItems()]
        if isinstance(widget, QComboBox):
            text = widget.currentText()
            return [text] if text else []
        return []

    # ------------------------------------------------------------------
    def _get_image_path(self, product: str, card_name: str) -> Path:
        """Return the image file path for the given product/card."""
        safe_prod = re.sub(r"[\\/:*?\"<>|]", "_", product)
        safe_card = re.sub(r"[\\/:*?\"<>|]", "_", card_name)
        base = Path(self.db_path).parent
        return base / "picture" / safe_prod / f"{safe_card}.jpg"

    # ------------------------------------------------------------------
    def _on_pick(self, event) -> None:
        line = getattr(event, "artist", None)
        if line is None:
            return
        card_name = getattr(line, "get_label", lambda: "")()
        if not card_name:
            return
        df = self.df[self.df["card"] == card_name]
        if df.empty:
            self.image_label.setText("No image")
            self.image_label.setPixmap(QPixmap())
            return
        product = str(df.iloc[0]["product"])
        img_path = self._get_image_path(product, card_name)
        if img_path.is_file():
            self.image_label.setPixmap(QPixmap(str(img_path)))
            self.image_label.setText("")
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("No image")

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

        number_text = self.number_edit.text().strip()
        if number_text:
            df = df[df["number"].str.contains(number_text, na=False)]

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
        line_count = 0
        for card_name, data in grouped.groupby("card"):
            line = self.ax.plot(
                data["scraped_at"],
                data["price"],
                marker="o",
                label=card_name,
            )[0]
            line.set_picker(True)
            line_count += 1

        if line_count <= 10:
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


def main() -> None:  # pragma: no cover - manual launch
    """Launch the GUI with optional DB path from command line."""
    db_path = sys.argv[1] if len(sys.argv) > 1 else "scraped_data.db"
    Path(db_path).touch(exist_ok=True)
    launch_gui(db_path)


if __name__ == "__main__":
    main()
