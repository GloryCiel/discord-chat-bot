"""
Logging utility implementation
"""

import logging
from typing import Optional
from pathlib import Path


def setup_logger(
    name: str, log_file: Optional[Path] = None, level: int = logging.INFO
) -> logging.Logger:
    """
    Set up and configure logger

    Args:
        name (str): Logger name
        log_file (Optional[Path]): Path to log file
        level (int): Logging level

    Returns:
        logging.Logger: Configured logger instance
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    if not any(
        isinstance(handler, logging.StreamHandler)
        and not isinstance(handler, logging.FileHandler)
        for handler in root_logger.handlers
    ):
        root_logger.addHandler(console_handler)

    # File handler if log file is specified
    if log_file and not any(
        isinstance(handler, logging.FileHandler) for handler in root_logger.handlers
    ):
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return logging.getLogger(name)
