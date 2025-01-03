# dotfilemanager/utils.py

import re
import shutil
import time
from pathlib import Path
from typing import Optional
import logging

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