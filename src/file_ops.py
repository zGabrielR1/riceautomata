# dotfilemanager/file_ops.py

import shutil
from pathlib import Path
from typing import Optional, Callable, Any, List, Dict
import logging

from .exceptions import FileOperationError

class FileOperations:
    """
    Handles file operations like copying, removing, etc.
    """
    def __init__(self, backup_manager: 'BackupManager', logger: Optional[logging.Logger] = None):
        """
        Initializes the FileOperations.

        Args:
            backup_manager (BackupManager): Instance of BackupManager.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.backup_manager = backup_manager
        self.logger = logger or logging.getLogger('DotfileManager')

    def copy_files(self, source_dir: Path, target_dir: Path, backup_id: Optional[str] = None) -> bool:
        """
        Copies files from source to target directory.

        Args:
            source_dir (Path): Source directory.
            target_dir (Path): Target directory.
            backup_id (Optional[str]): Backup identifier.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if not source_dir.exists():
                self.logger.error(f"Source directory does not exist: {source_dir}")
                return False
            shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)
            self.logger.info(f"Copied files from {source_dir} to {target_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to copy files from {source_dir} to {target_dir}: {e}")
            return False

    def remove_files(self, target_dir: Path) -> bool:
        """
        Removes files from the target directory.

        Args:
            target_dir (Path): Target directory to remove.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if target_dir.is_symlink() or target_dir.is_file():
                target_dir.unlink()
                self.logger.info(f"Removed file/symlink: {target_dir}")
            elif target_dir.is_dir():
                shutil.rmtree(target_dir)
                self.logger.info(f"Removed directory: {target_dir}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to remove files from {target_dir}: {e}")
            return False

    def discover_scripts(self, local_dir: Path, custom_scripts: Optional[List[str]] = None) -> Dict[str, List[str]]:
        """
        Discovers scripts in the local directory and returns them categorized by phase.

        Args:
            local_dir (Path): Directory to search for scripts.
            custom_scripts (Optional[List[str]]): Additional scripts to include.

        Returns:
            Dict[str, List[str]]: Scripts categorized by phase.
        """
        scripts_by_phase = {
            'pre_clone': [],
            'post_clone': [],
            'pre_install_dependencies': [], 
            'post_install_dependencies': [], 
            'pre_apply': [], 
            'post_apply': [], 
            'pre_uninstall': [], 
            'post_uninstall': [],
            'custom_scripts': []
        }
        try:
            for script_file in local_dir.glob('**/*.sh'):
                script_name = script_file.name.lower()
                for phase in scripts_by_phase.keys():
                    if phase in script_name:
                        scripts_by_phase[phase].append(str(script_file.relative_to(local_dir)))
                        self.logger.debug(f"Discovered script {script_file} for phase {phase}")
            if custom_scripts:
                for script in custom_scripts:
                    scripts_by_phase['custom_scripts'].append(script)
                    self.logger.debug(f"Added custom script {script} for phase 'custom_scripts'")
            return scripts_by_phase
        except Exception as e:
            self.logger.error(f"Failed to discover scripts in {local_dir}: {e}")
            return scripts_by_phase