# -*- coding: utf-8 -*-
"""Graphical interface for viewing card price history.

This module defines :class:`StatsWindow` which loads card data from the
SQLite database created by :mod:`db_manager` and displays simple line
plots using Matplotlib. Users can filter data by product name, rarity,
price range, date range, feature and colour. Multiple selection is
available only for the product filter; other categories use drop-down
menus.

UI Layout: Filter(1) : Chart(5) : Card Image(2)
"""
from __future__ import annotations

import sys
import os
import platform
from pathlib import Path
from typing import Iterable
import re

import pandas as pd
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.ticker import ScalarFormatter, FuncFormatter

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
    QPushButton,
    QSizePolicy,
    QGroupBox,
    QScrollArea,
    QFrame,
    QToolTip,
)
from PyQt5 import QtCore
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap

from db_manager import DatabaseManager

from dotenv import load_dotenv
load_dotenv(Path(__file__).with_name('.env'))

__all__ = ["StatsWindow", "launch_gui"]

# 最大顯示卡片數量限制
MAX_CARDS_DISPLAY = 20


class StatsWindow(QMainWindow):
    """Card price viewer with filter, chart, and image display.

    Layout ratio - Filter(1) : Chart(5) : Image(2)
    """

    def __init__(self, db_path: str = "scraped_data.db") -> None:
        super().__init__()
        self.db_path = db_path
        self.db = DatabaseManager(db_path=db_path)
        self.setWindowTitle("OPTCG Card Price Viewer")
        self.resize(1400, 700)

        # Matplotlib canvas
        self.figure, self.ax = plt.subplots()
        self.canvas = FigureCanvas(self.figure)
        self.canvas.mpl_connect("pick_event", self._on_pick)
        self.canvas.mpl_connect("motion_notify_event", self._on_hover)

        # Store plot data for hover tooltip
        self._plot_data: dict = {}  # {line: (dates, prices, card_name, number)}

        # Right side: Card image display
        self.image_label = QLabel("點擊折線圖上的線條\n查看卡片圖片")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setStyleSheet("QLabel { background-color: #f0f0f0; border: 1px solid #ccc; }")
        self.image_label.setMinimumSize(200, 280)

        # Top-N filter settings (will be placed above chart)
        self.top_n_enabled = False
        self.top_n_value = 10

        # ============== LEFT: Filter Area ==============
        filter_widget = self._create_filter_area()

        # ============== CENTER: Chart Area ==============
        chart_widget = self._create_chart_area()

        # ============== RIGHT: Image Area ==============
        image_widget = self._create_image_area()

        # ============== Main Layout (1:5:2 ratio) ==============
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        main_layout.addWidget(filter_widget, 1)
        main_layout.addWidget(chart_widget, 5)
        main_layout.addWidget(image_widget, 2)

        self.setCentralWidget(central)

        # Data
        self.df: pd.DataFrame = pd.DataFrame()
        self.filtered_df: pd.DataFrame = pd.DataFrame()
        self.load_data()

    def _create_filter_area(self) -> QWidget:
        """Create the left filter panel."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(8)

        # Product filter (multi-select list)
        product_group = QGroupBox("產品名稱")
        product_layout = QVBoxLayout(product_group)
        self.product_list = QListWidget()
        self.product_list.setSelectionMode(QAbstractItemView.MultiSelection)
        self.product_list.setMinimumHeight(120)
        self.product_list.setMaximumHeight(180)
        product_layout.addWidget(self.product_list)
        layout.addWidget(product_group)

        # Card number filter
        number_group = QGroupBox("卡片編號")
        number_layout = QVBoxLayout(number_group)
        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("輸入編號 (例: OP01-001)")
        number_layout.addWidget(self.number_edit)
        layout.addWidget(number_group)

        # Card name filter
        name_group = QGroupBox("卡片名稱")
        name_layout = QVBoxLayout(name_group)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("輸入卡片名稱")
        name_layout.addWidget(self.name_edit)
        layout.addWidget(name_group)

        # Color filter
        color_group = QGroupBox("顏色")
        color_layout = QVBoxLayout(color_group)
        self.color_combo = QComboBox()
        self.color_combo.setMinimumWidth(100)
        color_layout.addWidget(self.color_combo)
        layout.addWidget(color_group)

        # Rarity filter
        rarity_group = QGroupBox("稀有度")
        rarity_layout = QVBoxLayout(rarity_group)
        self.rarity_combo = QComboBox()
        self.rarity_combo.setMinimumWidth(100)
        rarity_layout.addWidget(self.rarity_combo)
        layout.addWidget(rarity_group)

        # Price range filter
        price_group = QGroupBox("價格帶")
        price_layout = QVBoxLayout(price_group)

        min_row = QHBoxLayout()
        min_row.addWidget(QLabel("最低:"))
        self.min_price = QSpinBox()
        self.min_price.setRange(0, 1_000_000)
        self.min_price.setSuffix(" 円")
        min_row.addWidget(self.min_price)
        price_layout.addLayout(min_row)

        max_row = QHBoxLayout()
        max_row.addWidget(QLabel("最高:"))
        self.max_price = QSpinBox()
        self.max_price.setRange(0, 1_000_000)
        self.max_price.setSuffix(" 円")
        max_row.addWidget(self.max_price)
        price_layout.addLayout(max_row)

        layout.addWidget(price_group)

        # Buttons
        btn_layout = QVBoxLayout()
        self.update_btn = QPushButton("Update")
        self.update_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px; }")
        self.update_btn.clicked.connect(self.update_plot)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; font-weight: bold; padding: 8px; }")
        self.reset_btn.clicked.connect(self._reset_filters)

        btn_layout.addWidget(self.update_btn)
        btn_layout.addWidget(self.reset_btn)
        layout.addLayout(btn_layout)

        layout.addStretch()
        scroll.setWidget(container)
        return scroll

    def _create_chart_area(self) -> QWidget:
        """Create the center chart panel with top-N filter."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        # Top row: Top-N filter + Y-axis mode toggle
        top_row = QHBoxLayout()
        self.top_n_prefix_label = QLabel("顯示價格前")
        top_row.addWidget(self.top_n_prefix_label)
        self.top_n_spin = QSpinBox()
        self.top_n_spin.setRange(1, 100)
        self.top_n_spin.setValue(MAX_CARDS_DISPLAY)
        self.top_n_spin.valueChanged.connect(self._on_top_n_changed)
        top_row.addWidget(self.top_n_spin)
        self.top_n_suffix_label = QLabel("高的卡片")
        top_row.addWidget(self.top_n_suffix_label)

        # 漲跌幅模式的排序方向選擇（預設隱藏）
        self.change_sort_combo = QComboBox()
        self.change_sort_combo.addItem("高漲幅")
        self.change_sort_combo.addItem("高跌幅")
        self.change_sort_combo.currentIndexChanged.connect(lambda _: self.update_plot())
        self.change_sort_combo.hide()
        top_row.addWidget(self.change_sort_combo)

        top_row.addStretch()

        # Y-axis mode toggle
        top_row.addWidget(QLabel("Y軸:"))
        self.y_axis_combo = QComboBox()
        self.y_axis_combo.addItem("價格 (円)")
        self.y_axis_combo.addItem("漲跌幅 (%)")
        self.y_axis_combo.currentIndexChanged.connect(self._on_y_axis_changed)
        top_row.addWidget(self.y_axis_combo)

        # Card count label
        self.card_count_label = QLabel("")
        self.card_count_label.setStyleSheet("color: #666;")
        top_row.addWidget(self.card_count_label)

        layout.addLayout(top_row)

        # Chart canvas
        layout.addWidget(self.canvas, 1)

        return widget

    def _create_image_area(self) -> QWidget:
        """Create the right image display panel."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Title
        title = QLabel("卡片圖片")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(title)

        # Image display
        layout.addWidget(self.image_label, 1)

        # Card info label
        self.card_info_label = QLabel("")
        self.card_info_label.setAlignment(Qt.AlignCenter)
        self.card_info_label.setWordWrap(True)
        self.card_info_label.setStyleSheet("padding: 5px; background-color: #f9f9f9;")
        layout.addWidget(self.card_info_label)

        return widget

    def load_data(self) -> None:
        """Load data from the database and populate filter widgets."""
        self.df = self.db.fetch_dataframe()

        # Populate product list
        self.product_list.clear()
        products = sorted(self.df["product"].dropna().unique())
        for p in products:
            QListWidgetItem(str(p), self.product_list)

        # Populate color combo
        self.color_combo.clear()
        self.color_combo.addItem("")  # Empty option for "all"
        colors = sorted(self.df["color"].dropna().unique())
        for c in colors:
            self.color_combo.addItem(str(c))

        # Populate rarity combo
        self.rarity_combo.clear()
        self.rarity_combo.addItem("")  # Empty option for "all"
        rarities = sorted(self.df["rarity"].dropna().unique())
        for r in rarities:
            self.rarity_combo.addItem(str(r))

        # Setup completers for text inputs with popup on typing
        numbers = sorted(self.df["number"].dropna().unique())
        number_completer = QCompleter([str(n) for n in numbers])
        number_completer.setCaseSensitivity(Qt.CaseInsensitive)
        number_completer.setFilterMode(Qt.MatchContains)
        number_completer.setCompletionMode(QCompleter.PopupCompletion)
        number_completer.setMaxVisibleItems(10)
        self.number_edit.setCompleter(number_completer)

        names = sorted(self.df["card"].dropna().unique())
        name_completer = QCompleter([str(n) for n in names])
        name_completer.setCaseSensitivity(Qt.CaseInsensitive)
        name_completer.setFilterMode(Qt.MatchContains)
        name_completer.setCompletionMode(QCompleter.PopupCompletion)
        name_completer.setMaxVisibleItems(10)
        self.name_edit.setCompleter(name_completer)

        # Set price range
        if not self.df.empty:
            self.min_price.setValue(int(self.df["price"].min()))
            self.max_price.setValue(int(self.df["price"].max()))

        self.update_plot()

    def _reset_filters(self) -> None:
        """Reset all filter settings to default."""
        # Clear product selection
        self.product_list.clearSelection()

        # Clear text inputs
        self.number_edit.clear()
        self.name_edit.clear()

        # Reset combos to first item (empty)
        self.color_combo.setCurrentIndex(0)
        self.rarity_combo.setCurrentIndex(0)

        # Reset price range
        if not self.df.empty:
            self.min_price.setValue(int(self.df["price"].min()))
            self.max_price.setValue(int(self.df["price"].max()))

        # Reset top-N, Y-axis mode, and sort direction
        self.top_n_spin.setValue(MAX_CARDS_DISPLAY)
        self.y_axis_combo.setCurrentIndex(0)
        self.change_sort_combo.setCurrentIndex(0)

        # Clear image
        self.image_label.setText("點擊折線圖上的線條\n查看卡片圖片")
        self.image_label.setPixmap(QPixmap())
        self.card_info_label.setText("")

        self.update_plot()

    def _on_y_axis_changed(self, index: int) -> None:
        """Called when Y-axis mode changes. Update top-N labels accordingly."""
        if index == 0:
            # 價格模式
            self.top_n_prefix_label.setText("顯示價格前")
            self.top_n_suffix_label.setText("高的卡片")
            self.top_n_suffix_label.show()
            self.change_sort_combo.hide()
        else:
            # 漲跌幅模式
            self.top_n_prefix_label.setText("顯示前")
            self.top_n_suffix_label.hide()
            self.change_sort_combo.show()
        self.update_plot()

    def _on_top_n_changed(self, value: int) -> None:
        """Called when top-N spinner value changes."""
        self.update_plot()

    def _get_selected_products(self) -> list[str]:
        """Get list of selected product names."""
        return [item.text() for item in self.product_list.selectedItems()]

    def _apply_filters(self) -> pd.DataFrame:
        """Apply all filters to the dataframe."""
        if self.df.empty:
            return self.df

        df = self.df.copy()

        # Product filter
        selected_products = self._get_selected_products()
        if selected_products:
            df = df[df["product"].isin(selected_products)]

        # Number filter (partial match)
        number_text = self.number_edit.text().strip()
        if number_text:
            df = df[df["number"].str.contains(number_text, case=False, na=False)]

        # Name filter (partial match)
        name_text = self.name_edit.text().strip()
        if name_text:
            df = df[df["card"].str.contains(name_text, case=False, na=False)]

        # Color filter
        color = self.color_combo.currentText()
        if color:
            df = df[df["color"] == color]

        # Rarity filter
        rarity = self.rarity_combo.currentText()
        if rarity:
            df = df[df["rarity"] == rarity]

        # Price range filter
        min_p = self.min_price.value()
        max_p = self.max_price.value()
        df = df[(df["price"] >= min_p) & (df["price"] <= max_p)]

        return df

    def _get_image_path(self, product: str, card_name: str, number: str) -> Path:
        """Return the image file path for the given product/card.

        Image filename format: {number}_{card_name}.jpg
        """
        safe_prod = re.sub(r"[\\/:*?\"<>|]", "_", product)
        safe_number = re.sub(r"[\\/:*?\"<>|]", "_", number)
        safe_card = re.sub(r"[\\/:*?\"<>|]", "_", card_name)
        base = Path(self.db_path).parent
        return base / "picture" / safe_prod / f"{safe_number}_{safe_card}.jpg"

    def _on_pick(self, event) -> None:
        """Handle click on a line in the chart."""
        line = getattr(event, "artist", None)
        if line is None:
            return

        card_name = getattr(line, "card_name", "")
        card_number = getattr(line, "card_number", "")
        if not card_name or not card_number:
            return

        # Use both card name and number to find the exact card
        df = self.df[(self.df["card"] == card_name) & (self.df["number"] == card_number)]
        if df.empty:
            self.image_label.setText("無圖片")
            self.image_label.setPixmap(QPixmap())
            self.card_info_label.setText("")
            return

        row = df.iloc[0]
        product = str(row["product"])
        rarity = str(row["rarity"])
        number = str(row["number"])

        img_path = self._get_image_path(product, card_name, number)
        if img_path.is_file():
            pixmap = QPixmap(str(img_path))
            # Scale to fit while keeping aspect ratio
            scaled = pixmap.scaled(
                self.image_label.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.image_label.setPixmap(scaled)
            self.image_label.setText("")
        else:
            self.image_label.setPixmap(QPixmap())
            self.image_label.setText("圖片不存在")

        # Update card info
        self.card_info_label.setText(f"{number}\n{card_name}\n[{rarity}]")

    def _on_hover(self, event) -> None:
        """Handle mouse hover to show tooltip with price."""
        if event.inaxes != self.ax:
            QToolTip.hideText()
            return

        # Check each line for proximity to cursor
        for line, (dates, prices, card_name, number) in self._plot_data.items():
            if not line.get_visible():
                continue

            # Get line data in display coordinates
            xdata, ydata = line.get_data()
            if len(xdata) == 0:
                continue

            # Convert data to display coordinates
            try:
                display_coords = self.ax.transData.transform(list(zip(mdates.date2num(xdata), ydata)))
            except Exception:
                continue

            # Check distance to each point
            for i, (dx, dy) in enumerate(display_coords):
                dist = ((event.x - dx) ** 2 + (event.y - dy) ** 2) ** 0.5
                if dist < 10:  # Within 10 pixels
                    # Show tooltip
                    price = int(prices[i])
                    date_str = dates[i].strftime("%Y-%m-%d")
                    if self.y_axis_combo.currentIndex() == 1:
                        base = prices[0] if prices[0] != 0 else 1
                        pct = (price - prices[0]) / base * 100
                        tooltip_text = f"{number}\n{date_str}\n{price:,} 円 ({pct:+.1f}%)"
                    else:
                        tooltip_text = f"{number}\n{date_str}\n{price:,} 円"

                    # Convert to global coordinates for QToolTip (offset to top-right)
                    canvas_x = int(event.x) + 15  # Offset right
                    canvas_y = int(self.canvas.height() - event.y) - 40  # Offset up
                    global_pos = self.canvas.mapToGlobal(QtCore.QPoint(canvas_x, canvas_y))
                    QToolTip.showText(global_pos, tooltip_text)
                    return

        QToolTip.hideText()

    def update_plot(self) -> None:
        """Filter data and update the chart."""
        if self.df.empty:
            return

        df = self._apply_filters()
        self.filtered_df = df

        self.ax.clear()
        self._plot_data.clear()  # Clear stored plot data

        if df.empty:
            self.ax.set_title("無資料")
            self.card_count_label.setText("0 張卡片")
            self.canvas.draw()
            return

        # Group by card and date, handle missing dates properly (don't fill with 0)
        grouped = df.groupby(["card", "scraped_at"])["price"].mean().reset_index()

        # Get metadata for each card
        meta = (
            df[["card", "rarity", "number", "product"]]
            .drop_duplicates(subset=["card"])
            .set_index("card")
        )

        # Determine Y-axis mode: 0 = price, 1 = change %
        y_mode = self.y_axis_combo.currentIndex()

        if y_mode == 1:
            # 漲跌幅模式：計算每張卡片的漲跌幅，用於排序
            card_change: dict[str, float] = {}
            for card_name, data in grouped.groupby("card"):
                data = data.sort_values("scraped_at")
                prices = data["price"].tolist()
                base = prices[0]
                if base == 0:
                    card_change[card_name] = 0.0
                else:
                    card_change[card_name] = (prices[-1] - base) / base * 100
            change_series = pd.Series(card_change)
            # 排序方向：0=高漲幅（降序），1=高跌幅（升序）
            sort_ascending = self.change_sort_combo.currentIndex() == 1
            change_series = change_series.sort_values(ascending=sort_ascending)
            unique_cards = list(change_series.index)
        else:
            # 價格模式：按最高價排序
            card_max_prices = grouped.groupby("card")["price"].max().sort_values(ascending=False)
            unique_cards = list(card_max_prices.index)

        total_cards = len(unique_cards)

        # Apply top-N limit (防呆機制: 超過20張自動限制)
        top_n = self.top_n_spin.value()
        display_limit = min(top_n, MAX_CARDS_DISPLAY) if total_cards > MAX_CARDS_DISPLAY else top_n

        if total_cards > display_limit:
            cards_to_show = set(unique_cards[:display_limit])
            grouped = grouped[grouped["card"].isin(cards_to_show)]
            meta = meta.loc[meta.index.intersection(cards_to_show)]
            self.card_count_label.setText(f"顯示 {display_limit} / {total_cards} 張卡片")
        else:
            self.card_count_label.setText(f"{total_cards} 張卡片")

        # Plot each card's price history
        for card_name, data in grouped.groupby("card"):
            if card_name not in meta.index:
                continue

            number = meta.loc[card_name, "number"]
            # Legend only shows card number
            label = str(number)

            # Sort by date and plot (don't interpolate missing dates)
            data = data.sort_values("scraped_at")
            dates = data["scraped_at"].tolist()
            prices = data["price"].tolist()

            if y_mode == 1:
                # 漲跌幅模式：以第一筆價格為基準計算百分比變化
                base_price = prices[0]
                if base_price == 0:
                    y_values = [0.0] * len(prices)
                else:
                    y_values = [(p - base_price) / base_price * 100 for p in prices]
            else:
                y_values = prices

            line = self.ax.plot(
                dates,
                y_values,
                marker="o",
                label=label,
                linewidth=1.5,
                markersize=4,
            )[0]
            line.set_picker(True)
            line.set_pickradius(5)
            line.card_name = card_name
            line.card_number = number

            # Store data for hover tooltip (always store original prices too)
            self._plot_data[line] = (dates, prices, card_name, number)

        # Chart styling
        self.ax.set_xlabel("日期")
        if y_mode == 1:
            self.ax.set_ylabel("漲跌幅 (%)")
            self.ax.axhline(y=0, color="gray", linewidth=0.8, linestyle="--")
            self.ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f"{x:+.1f}%"))
        else:
            self.ax.set_ylabel("價格 (円)")
        self.ax.grid(True, alpha=0.3)

        # X-axis: one tick per day
        self.ax.xaxis.set_major_locator(mdates.DayLocator())
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d"))

        # Y-axis: use k format if price mode and max > 10000
        if y_mode == 0:
            max_price = grouped["price"].max() if not grouped.empty else 0
            if max_price > 10000:
                formatter = FuncFormatter(lambda x, p: f"{x/1000:.1f}k" if x >= 1000 else f"{x:.0f}")
                self.ax.yaxis.set_major_formatter(formatter)

        # Show legend if not too many lines
        displayed_count = len(grouped["card"].unique())
        if displayed_count <= 15:
            self.ax.legend(loc="upper left", fontsize=8)

        self.figure.autofmt_xdate()
        self.figure.tight_layout()
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
