# dotfilemanager/logger.py

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

def setup_logger(verbose: bool = False, log_file: Optional[str] = None) -> logging.Logger:
    """
    Sets up the logger with optional log file and verbosity.

    Args:
        verbose (bool): If True, set log level to DEBUG. Otherwise, INFO.
        log_file (Optional[str]): Path to the log file.

    Returns:
        logging.Logger: Configured logger.
    """
    logger = logging.getLogger('DotfileManager')
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.propagate = False  # Prevent logging from propagating to the root logger multiple times.

    # Formatter
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler with rotation
    if log_file:
        fh = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=3)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger