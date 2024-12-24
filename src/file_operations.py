import os
import shutil
from typing import Optional, Dict, List
from src.utils import setup_logger
from src.backup import BackupManager

class FileOperationError(Exception):
    pass

class FileOperations:
    """Handles file operations like copying, removing, and script discovery."""
    
    def __init__(self, backup_manager: BackupManager, verbose: bool = False):
        self.backup_manager = backup_manager
        self.verbose = verbose
        self.logger = setup_logger(verbose)

    def validate_directory(self, dir_path: str) -> None:
        """Validates a directory."""
        if not os.path.exists(dir_path):
            raise FileOperationError(f"Directory does not exist: {dir_path}")
        if not os.path.isdir(dir_path):
            raise FileOperationError(f"Path is not a directory: {dir_path}")
        if not os.access(dir_path, os.R_OK):
            raise FileOperationError(f"Directory is not readable: {dir_path}")

    def copy_files(self, source_dir: str, target_dir: str, backup_id: Optional[str] = None) -> None:
        """Copy files from source to target directory with backup support."""
        try:
            self.validate_directory(source_dir)

            if not os.path.exists(target_dir):
                os.makedirs(target_dir, exist_ok=True)

            for item in os.listdir(source_dir):
                src = os.path.join(source_dir, item)
                dst = os.path.join(target_dir, item)

                if os.path.exists(dst):
                    self.backup_manager.backup_file(dst)

                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

        except Exception as e:
            raise FileOperationError(f"Failed to copy files from {source_dir} to {target_dir}: {e}")

    def remove_files(self, target_dir: str) -> None:
        """Remove files from target directory with backup support."""
        try:
            self.validate_directory(target_dir)
            backup_id = self.backup_manager.start_operation_backup("remove_files")

            for item in os.listdir(target_dir):
                path = os.path.join(target_dir, item)
                if os.path.exists(path):
                    if os.path.isdir(path):
                        self.backup_manager.backup_file(path)
                        shutil.rmtree(path)
                    else:
                        self.backup_manager.backup_file(path)
                        os.remove(path)

        except Exception as e:
            raise FileOperationError(f"Failed to remove files from {target_dir}: {e}")

    def discover_scripts(self, local_dir: str, custom_scripts: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """Discover and categorize scripts in the given directory."""
        try:
            script_phases = {
                "pre_clone": [], "post_clone": [],
                "pre_install_dependencies": [], "post_install_dependencies": [],
                "pre_apply": [], "post_apply": [],
                "pre_uninstall": [], "post_uninstall": []
            }

            # Handle custom scripts
            if custom_scripts:
                for script in custom_scripts:
                    script_path = os.path.join(local_dir, script)
                    if os.path.exists(script_path) and os.path.isfile(script_path) and os.access(script_path, os.X_OK):
                        for phase in script_phases:
                            if script.startswith(phase):
                                script_phases[phase].append(script)
                                break

            # Check scripts directory
            script_dir = os.path.join(local_dir, "scriptdata")
            if os.path.exists(script_dir) and os.path.isdir(script_dir):
                for item in os.listdir(script_dir):
                    item_path = os.path.join(script_dir, item)
                    if os.path.isfile(item_path) and os.access(item_path, os.X_OK):
                        script_path = os.path.join("scriptdata", item)
                        for phase in script_phases:
                            if item.startswith(phase):
                                script_phases[phase].append(script_path)
                                break

            return script_phases

        except Exception as e:
            raise FileOperationError(f"Failed to discover scripts in {local_dir}: {e}")

    def safe_file_operation(self, operation_name: str, operation, *args, **kwargs):
        """Execute a file operation with backup and rollback support."""
        backup_id = self.backup_manager.start_operation_backup(operation_name)
        try:
            result = operation(*args, **kwargs)
            return result
        except Exception as e:
            if backup_id:
                try:
                    self.backup_manager.rollback_operation(backup_id)
                except Exception as rollback_error:
                    self.logger.error(f"Failed to rollback operation: {rollback_error}")
            raise
