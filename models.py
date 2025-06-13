# -*- coding: utf-8 -*-
"""Data models for scraped results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

__all__ = ["Card", "Product"]


@dataclass
class Card:
    """Represents a single card item scraped from the website."""

    name: str
    rarity: str
    url: str
    image: bytes
    number: str
    price: int
    quantity: int
    feature: str = ""
    color: str = ""


@dataclass
class Product:
    """Represents a product containing multiple cards."""

    name: str
    url: str
    cards: List[Card] = field(default_factory=list)
