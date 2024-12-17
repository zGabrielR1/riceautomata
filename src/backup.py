import os
import shutil
import json
from datetime import datetime
from typing import Dict, List, Optional
from src.exceptions import FileOperationError, RollbackError
from src.utils import setup_logger, create_timestamp

logger = setup_logger()

class BackupManager:
    def __init__(self, backup_dir: str = "~/.config/riceautomator/backups"):
        self.backup_dir = os.path.expanduser(backup_dir)
        self._ensure_backup_dir()
        self.current_operation_backup = None

    def _ensure_backup_dir(self) -> None:
        """Creates the backup directory if it doesn't exist."""
        try:
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir, exist_ok=True)
        except Exception as e:
            raise FileOperationError(f"Failed to create backup directory: {e}")

    def start_operation_backup(self, operation_name: str) -> str:
        """Starts a new backup for an operation."""
        try:
            timestamp = create_timestamp()
            backup_id = f"{operation_name}_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_id)
            os.makedirs(backup_path)
            
            self.current_operation_backup = {
                'id': backup_id,
                'path': backup_path,
                'files': {},
                'timestamp': timestamp
            }
            
            # Save backup metadata
            with open(os.path.join(backup_path, 'metadata.json'), 'w') as f:
                json.dump(self.current_operation_backup, f, indent=4)
            
            return backup_id
        except Exception as e:
            raise FileOperationError(f"Failed to start backup operation: {e}")

    def backup_file(self, file_path: str) -> None:
        """Creates a backup of a file before modification."""
        if not self.current_operation_backup:
            raise RollbackError("No active backup operation")
        
        try:
            if os.path.exists(file_path):
                backup_path = os.path.join(
                    self.current_operation_backup['path'],
                    os.path.basename(file_path)
                )
                shutil.copy2(file_path, backup_path)
                self.current_operation_backup['files'][file_path] = backup_path
                
                # Update metadata
                with open(os.path.join(self.current_operation_backup['path'], 'metadata.json'), 'w') as f:
                    json.dump(self.current_operation_backup, f, indent=4)
        except Exception as e:
            raise FileOperationError(f"Failed to backup file {file_path}: {e}")

    def rollback_operation(self, backup_id: str) -> None:
        """Rolls back all changes made during an operation."""
        try:
            backup_path = os.path.join(self.backup_dir, backup_id)
            if not os.path.exists(backup_path):
                raise RollbackError(f"Backup {backup_id} not found")
            
            # Load backup metadata
            with open(os.path.join(backup_path, 'metadata.json'), 'r') as f:
                backup_data = json.load(f)
            
            # Restore files
            for original_path, backup_path in backup_data['files'].items():
                if os.path.exists(backup_path):
                    # Create parent directory if it doesn't exist
                    os.makedirs(os.path.dirname(original_path), exist_ok=True)
                    shutil.copy2(backup_path, original_path)
                    logger.info(f"Restored file: {original_path}")
                else:
                    logger.warning(f"Backup file not found: {backup_path}")
            
            logger.info(f"Successfully rolled back operation: {backup_id}")
        except Exception as e:
            raise RollbackError(f"Failed to rollback operation: {e}")

    def cleanup_old_backups(self, max_age_days: int = 7) -> None:
        """Removes backups older than specified days."""
        try:
            current_time = datetime.now()
            for item in os.listdir(self.backup_dir):
                backup_path = os.path.join(self.backup_dir, item)
                if os.path.isdir(backup_path):
                    metadata_path = os.path.join(backup_path, 'metadata.json')
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'r') as f:
                            metadata = json.load(f)
                        backup_time = datetime.strptime(metadata['timestamp'], "%Y%m%d_%H%M%S")
                        age = (current_time - backup_time).days
                        if age > max_age_days:
                            shutil.rmtree(backup_path)
                            logger.info(f"Removed old backup: {item}")
        except Exception as e:
            logger.error(f"Failed to cleanup old backups: {e}")
