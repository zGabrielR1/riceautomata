# src/utils.py

import logging
import sys
import re
from pathlib import Path
from typing import Optional
import time

def sanitize_path(path_str: str) -> Path:
    """
    Sanitizes a given path string and returns a Path object.

    Args:
        path_str (str): The path string to sanitize.

    Returns:
        Path: Sanitized Path object.
    """
    path = Path(path_str).expanduser().resolve()
    # Additional sanitization rules can be added here
    return path

def create_timestamp() -> str:
    """
    Creates a timestamp string.

    Returns:
        str: Timestamp in YYYYMMDD_HHMMSS format.
    """
    return time.strftime("%Y%m%d_%H%M%S")

def confirm_action(prompt: str) -> bool:
    """
    Prompts the user for confirmation.

    Args:
        prompt (str): The prompt message.

    Returns:
        bool: True if user confirms, False otherwise.
    """
    while True:
        choice = input(f"{prompt} (y/n): ").strip().lower()
        if choice in ['y', 'yes']:
            return True
        elif choice in ['n', 'no']:
            return False
        else:
            print("Please respond with 'y' or 'n'.")

def sanitize_url(url: str) -> str:
    """
    Sanitizes a URL by removing unnecessary parts.

    Args:
        url (str): The URL to sanitize.

    Returns:
        str: Sanitized URL.
    """
    # Example sanitization: remove trailing slashes and unwanted query parameters
    sanitized = re.sub(r'https?://', '', url)  # Remove http:// or https://
    sanitized = sanitized.rstrip('/')            # Remove trailing slash
    # Add more sanitization rules as needed
    return sanitized

def exception_handler(exc_type, exc_value, exc_traceback):
    """
    Global exception handler.

    Args:
        exc_type: Exception type.
        exc_value: Exception value.
        exc_traceback: Exception traceback.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
