import logging
import os
import sys
from datetime import datetime
import traceback

def setup_logger(verbose=False, log_file=None):
    """Sets up the logger for the application."""

    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(log_format, datefmt=date_format)

    logger = logging.getLogger('riceautomator')
    logger.setLevel(log_level)

    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger


def sanitize_path(path):
    """Sanitizes a path to prevent directory traversal."""
    return os.path.abspath(os.path.expanduser(path))

def sanitize_url(url):
    """Sanitizes a URL to check for basic validity."""
    if not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL format. URL must start with 'http://' or 'https://'")
    return url

def confirm_action(message, default=True):
    """Prompts the user for confirmation."""
    if default:
        prompt = f"{message} [Y/n]: "
    else:
        prompt = f"{message} [y/N]: "

    while True:
        choice = input(prompt).strip().lower()
        if choice == 'y' or choice == 'yes' :
            return True
        elif choice == 'n' or choice == 'no':
            return False
        elif choice == '' and default:
          return True
        elif choice == '' and not default:
          return False
        else:
          print("Please answer with 'yes' or 'no'.")

def create_timestamp():
    """Create timestamp for the configuration file."""
    now = datetime.now()
    return now.isoformat()

def exception_handler(exc_type, exc_value, exc_traceback):
    """Handles unhandled exceptions and logs the error before exiting."""
    logger = logging.getLogger('riceautomator')
    
    tb_list = traceback.extract_tb(exc_traceback)
    last_call = tb_list[-1]
    filename, lineno, function, code = last_call

    logger.error("An unhandled exception occurred:")
    logger.error(f"  Type: {exc_type.__name__}")
    logger.error(f"  Value: {exc_value}")
    logger.error(f"  File: {filename}, Line: {lineno}, Function: {function}")
    sys.exit(1)