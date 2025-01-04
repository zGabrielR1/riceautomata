# dotfilemanager/backup.py

import shutil
from pathlib import Path
from typing import Optional, List  # Added List here
import logging
from .exceptions import BackupError
from .utils import create_timestamp

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
        self._ensure_backup_dir()

    def _ensure_backup_dir(self):
        """Creates the backup directory if it doesn't exist."""
        try:
            self.backup_base_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured backup directory exists at {self.backup_base_dir}")
        except OSError as e:
            self.logger.error(f"Failed to create backup directory: {e}")
            raise BackupError(f"Failed to create backup directory: {e}")

    def create_backup(self, repository_name: str, backup_name: str) -> str:
        """
        Creates a backup for the given repository.

        Args:
            repository_name (str): Name of the repository.
            backup_name (str): Name for the backup.

        Returns:
            str: The full path to the created backup directory.
            
        Raises:
            BackupError: If backup creation fails.
        """
        try:
            backup_dir = self.backup_base_dir / repository_name / backup_name
            if backup_dir.exists():
                raise BackupError(f"Backup '{backup_name}' already exists for repository '{repository_name}'.")

            backup_dir.mkdir(parents=True)
            self.logger.debug(f"Created backup directory at {backup_dir}")
            # Additional backup logic can be added here (e.g., copying files to backup_dir)
            return str(backup_dir)  # Return the path as a string
        except OSError as e:
            self.logger.error(f"Failed to create backup '{backup_name}' for repository '{repository_name}': {e}")
            raise BackupError(f"Failed to create backup '{backup_name}' for repository '{repository_name}': {e}")

    def rollback_backup(self, repository_name: str, backup_name: str, target_dir: Path) -> bool:
        """
        Rolls back to a specific backup.

        Args:
            repository_name (str): Name of the repository.
            backup_name (str): Name of the backup.
            target_dir (Path): Directory to restore the backup to.

        Returns:
            bool: True if successful, False otherwise.

        Raises:
            BackupError: If the backup is not found or if the rollback fails.
        """
        try:
            backup_dir = self.backup_base_dir / repository_name / backup_name
            if not backup_dir.exists():
                raise BackupError(f"Backup '{backup_name}' does not exist for repository '{repository_name}'.")

            # Restore logic: copy backup contents to target_dir
            shutil.copytree(backup_dir, target_dir, dirs_exist_ok=True)
            self.logger.debug(f"Restored backup '{backup_name}' to {target_dir}")
            return True
        except (OSError, shutil.Error) as e:
            self.logger.error(f"Failed to restore backup '{backup_name}' for repository '{repository_name}': {e}")
            raise BackupError(f"Failed to restore backup '{backup_name}' for repository '{repository_name}': {e}")

    def list_backups(self, repository_name: str) -> List[str]:
        """
        Lists all backups for a given repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            List[str]: List of backup names.

        Raises:
            BackupError: If there is an error listing the backups.
        """
        try:
            repo_backup_dir = self.backup_base_dir / repository_name
            if not repo_backup_dir.exists():
                self.logger.warning(f"No backups found for repository '{repository_name}'.")
                return []  # Return an empty list if no backups are found

            backups = [backup.name for backup in repo_backup_dir.iterdir() if backup.is_dir()]
            self.logger.debug(f"Found backups for '{repository_name}': {backups}")
            return backups
        except OSError as e:
            self.logger.error(f"Failed to list backups for repository '{repository_name}': {e}")
            raise BackupError(f"Failed to list backups for repository '{repository_name}': {e}")
