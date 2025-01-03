# dotfilemanager/backup.py

import shutil
from pathlib import Path
from typing import Optional
import logging
from .exceptions import BackupError

class BackupManager:
    """
    Manages backups of configurations.
    """
    def __init__(self, backup_base_dir: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        """
        Initializes the BackupManager.

        Args:
            backup_base_dir (Optional[Path]): Base directory for backups.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')
        self.backup_base_dir = backup_base_dir or Path.home() / '.dotfilemanager' / 'backups'
        self.backup_base_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, repository_name: str, backup_name: str) -> bool:
        """
        Creates a backup for the given repository.

        Args:
            repository_name (str): Name of the repository.
            backup_name (str): Name for the backup.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            backup_dir = self.backup_base_dir / repository_name / backup_name
            if backup_dir.exists():
                self.logger.error(f"Backup '{backup_name}' already exists for repository '{repository_name}'.")
                return False
            backup_dir.mkdir(parents=True)
            self.logger.debug(f"Created backup directory at {backup_dir}")
            # Additional backup logic can be added here
            return True
        except Exception as e:
            self.logger.error(f"Failed to create backup '{backup_name}' for repository '{repository_name}': {e}")
            return False

    def rollback_backup(self, repository_name: str, backup_name: str, target_dir: Path) -> bool:
        """
        Rolls back to a specific backup.

        Args:
            repository_name (str): Name of the repository.
            backup_name (str): Name of the backup.
            target_dir (Path): Directory to restore the backup to.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            backup_dir = self.backup_base_dir / repository_name / backup_name
            if not backup_dir.exists():
                self.logger.error(f"Backup '{backup_name}' does not exist for repository '{repository_name}'.")
                return False
            # Restore logic: copy backup contents to target_dir
            shutil.copytree(backup_dir, target_dir, dirs_exist_ok=True)
            self.logger.debug(f"Restored backup '{backup_name}' to {target_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore backup '{backup_name}' for repository '{repository_name}': {e}")
            return False

    def list_backups(self, repository_name: str) -> list:
        """
        Lists all backups for a given repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            list: List of backup names.
        """
        try:
            repo_backup_dir = self.backup_base_dir / repository_name
            if not repo_backup_dir.exists():
                self.logger.warning(f"No backups found for repository '{repository_name}'.")
                return []
            backups = [backup.name for backup in repo_backup_dir.iterdir() if backup.is_dir()]
            self.logger.debug(f"Found backups for '{repository_name}': {backups}")
            return backups
        except Exception as e:
            self.logger.error(f"Failed to list backups for repository '{repository_name}': {e}")
            return []