"""
Centralized logging setup used by every module in the project.

Kept in one place so every phase (data gen, ETL, features, modeling) logs
in the same format to both the console and a rotating file under logs/.
"""

import logging
import sys
from pathlib import Path


def get_logger(name: str, log_file: str = "logs/pipeline.log") -> logging.Logger:
    """Return a configured logger that writes to console + a shared file.

    Idempotent: calling this multiple times for the same `name` will not
    duplicate handlers.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
