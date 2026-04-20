"""Central Loguru configuration."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.config import config


def setup_logger():
    """Configure a lightweight logger that works in restricted environments."""

    logger.remove()

    logger.add(
        sys.stdout,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{module}</cyan>.<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        level="DEBUG" if config.debug else "INFO",
        colorize=True,
        backtrace=config.debug,
        diagnose=config.debug,
    )

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "app.log",
        rotation="5 MB",
        retention="7 days",
        encoding="utf-8",
        enqueue=False,
        backtrace=config.debug,
        diagnose=config.debug,
        level="INFO",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {module}.{function}:{line} | {message}",
    )


setup_logger()
