import os
import shutil
import json
from datetime import datetime
from typing import Dict, List, Optional
from src.exceptions import FileOperationError, RollbackError
from src.utils import setup_logger, create_timestamp
from src.package import PackageManager

logger = setup_logger()

class BackupManager:
    def __init__(self, backup_dir: str = "~/.config/riceautomator/backups"):
        self.backup_dir = os.path.expanduser(backup_dir)
        self.snapshots_dir = os.path.join(self.backup_dir, "snapshots")
        self.metadata_file = os.path.join(self.snapshots_dir, "snapshots.json")
        self._ensure_backup_dir()
        self.current_operation_backup = None
        self.package_manager = PackageManager()

    def _ensure_backup_dir(self) -> None:
        """Creates the backup directory if it doesn't exist."""
        try:
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir, exist_ok=True)
            if not os.path.exists(self.snapshots_dir):
                os.makedirs(self.snapshots_dir, exist_ok=True)
            if not os.path.exists(self.metadata_file):
                self._save_metadata({})
        except OSError as e:
            raise FileOperationError(f"Failed to create backup directory: {str(e)}")

    def _save_metadata(self, metadata: Dict) -> None:
        """Save snapshot metadata to JSON file."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=4)
        except OSError as e:
            raise FileOperationError(f"Failed to save metadata: {str(e)}")

    def _load_metadata(self) -> Dict:
        """Load snapshot metadata from JSON file."""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            return {}
        except OSError as e:
            raise FileOperationError(f"Failed to load metadata: {str(e)}")

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

    def create_snapshot(self, name: str, description: Optional[str] = None) -> bool:
        """
        Create a new snapshot of the current system configuration.
        
        Args:
            name: Name of the snapshot
            description: Optional description of the snapshot
        
        Returns:
            bool: True if snapshot was created successfully
        """
        metadata = self._load_metadata()
        
        if name in metadata:
            logger.error(f"Snapshot '{name}' already exists")
            return False

        snapshot_dir = os.path.join(self.snapshots_dir, name)
        try:
            os.makedirs(snapshot_dir, exist_ok=True)

            # Save dotfiles
            config_dir = os.path.expanduser("~/.config")
            if os.path.exists(config_dir):
                shutil.copytree(config_dir, os.path.join(snapshot_dir, ".config"), dirs_exist_ok=True)

            # Save package list
            packages = self.package_manager.get_installed_packages()
            with open(os.path.join(snapshot_dir, "packages.txt"), 'w') as f:
                f.write('\n'.join(packages))

            # Update metadata
            metadata[name] = {
                "created_at": datetime.now().isoformat(),
                "description": description,
                "packages": packages
            }
            self._save_metadata(metadata)
            logger.info(f"Successfully created snapshot '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to create snapshot '{name}': {str(e)}")
            if os.path.exists(snapshot_dir):
                shutil.rmtree(snapshot_dir)
            return False

    def restore_snapshot(self, name: str) -> bool:
        """
        Restore system to a previous snapshot.
        
        Args:
            name: Name of the snapshot to restore
        
        Returns:
            bool: True if snapshot was restored successfully
        """
        metadata = self._load_metadata()
        if name not in metadata:
            logger.error(f"Snapshot '{name}' does not exist")
            return False

        snapshot_dir = os.path.join(self.snapshots_dir, name)
        if not os.path.exists(snapshot_dir):
            logger.error(f"Snapshot directory for '{name}' not found")
            return False

        try:
            # Restore dotfiles
            config_backup = os.path.expanduser("~/.config_backup")
            config_dir = os.path.expanduser("~/.config")
            
            # Backup current config
            if os.path.exists(config_dir):
                shutil.move(config_dir, config_backup)
            
            # Restore snapshot config
            shutil.copytree(os.path.join(snapshot_dir, ".config"), config_dir)

            # Restore packages
            current_packages = set(self.package_manager.get_installed_packages())
            snapshot_packages = set(metadata[name]["packages"])
            
            # Remove packages not in snapshot
            to_remove = current_packages - snapshot_packages
            if to_remove:
                self.package_manager.remove_packages(list(to_remove))
            
            # Install missing packages
            to_install = snapshot_packages - current_packages
            if to_install:
                self.package_manager.install_packages(list(to_install))

            logger.info(f"Successfully restored snapshot '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to restore snapshot '{name}': {str(e)}")
            # Try to restore backup if it exists
            if os.path.exists(config_backup):
                if os.path.exists(config_dir):
                    shutil.rmtree(config_dir)
                shutil.move(config_backup, config_dir)
            return False

    def list_snapshots(self) -> Dict:
        """List all available snapshots."""
        return self._load_metadata()

    def delete_snapshot(self, name: str) -> bool:
        """Delete a snapshot."""
        metadata = self._load_metadata()
        if name not in metadata:
            logger.error(f"Snapshot '{name}' does not exist")
            return False

        try:
            snapshot_dir = os.path.join(self.snapshots_dir, name)
            if os.path.exists(snapshot_dir):
                shutil.rmtree(snapshot_dir)

            del metadata[name]
            self._save_metadata(metadata)
            logger.info(f"Successfully deleted snapshot '{name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete snapshot '{name}': {str(e)}")
            return False
