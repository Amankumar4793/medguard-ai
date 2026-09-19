"""Utilities package for logging, time helpers, validation, and snapshot storage."""
import os
import logging
from pathlib import Path


def setup_logger(name='healthcare_security', log_level=logging.INFO):
    """Configure structured logger."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(log_level)
    return logger


def ensure_directories(*paths):
    """Ensure that specified directory paths exist."""
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)
