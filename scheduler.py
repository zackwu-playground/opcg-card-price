# -*- coding: utf-8 -*-
"""scheduler.py
排程設定模組
===========================
• 使用 APScheduler BackgroundScheduler
• 提供 setup_daily_job() 方便在指定時刻執行工作
"""
from __future__ import annotations

from typing import Callable

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

__all__ = ["setup_daily_job"]


def setup_daily_job(*, hour: int, minute: int, job_func: Callable[[], None], timezone: str = "Asia/Taipei") -> BackgroundScheduler:
    ...
