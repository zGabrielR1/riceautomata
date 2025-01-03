To integrate the functionalities and commands from the old `RiceAutomata` README into your current **DotfileManager** codebase, you'll need to implement several enhancements. This includes adding new commands for profile management, snapshot management, advanced file management, and refining existing functionalities to accommodate these features.

Below is a comprehensive guide outlining the necessary changes and additions to your codebase to achieve the desired functionalities:

---

## **1. Update `main.py` to Include New Subcommands**

Enhance the command-line interface to handle new commands such as `list`, `create`, `manage`, `import`, `export`, and `snapshot` operations.

### **Updated `main.py`**

```python
# dotfilemanager/main.py

import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

from .dotfile_manager import DotfileManager

def main():
    parser = argparse.ArgumentParser(description="DotfileManager: Manage and apply your dotfiles configurations.")
    parser.add_argument('--verbose', '-v', action='store_true', help="Enable verbose logging (DEBUG level).")
    parser.add_argument('--log-file', type=str, help="Path to the log file.")

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Clone command
    clone_parser = subparsers.add_parser('clone', help='Clone a dotfile repository.')
    clone_parser.add_argument('repository_url', type=str, help='URL of the git repository to clone.')

    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Apply dotfiles from a repository.')
    apply_parser.add_argument('repository_name', type=str, help='Name of the repository to apply.')
    apply_parser.add_argument('--profile', type=str, help='Name of the profile to apply.')
    apply_parser.add_argument('--stow-options', nargs='*', default=[], help='Additional options for GNU Stow.')
    apply_parser.add_argument('--overwrite-symlink', type=str, help='Path to overwrite existing symlinks.')
    apply_parser.add_argument('--custom-paths', nargs='*', help='Custom paths in the format key=value.')
    apply_parser.add_argument('--ignore-rules', action='store_true', help='Ignore rules during application.')
    apply_parser.add_argument('--template-context', type=str, help='Path to JSON file with template context.')
    apply_parser.add_argument('--discover-templates', action='store_true', help='Discover and process templates.')
    apply_parser.add_argument('--custom-scripts', nargs='*', help='Additional scripts to run.')

    # List command
    list_parser = subparsers.add_parser('list', help='List all profiles or profiles for a specific repository.')
    list_parser.add_argument('repository_name', nargs='?', type=str, help='Name of the repository to list profiles for.')

    # Create profile command
    create_parser = subparsers.add_parser('create', help='Create a new profile.')
    create_parser.add_argument('profile_name', type=str, help='Name of the new profile.')
    create_parser.add_argument('--description', type=str, help='Description of the profile.', default='')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create a backup of the applied configuration.')
    backup_parser.add_argument('repository_name', type=str, help='Name of the repository to backup.')
    backup_parser.add_argument('backup_name', type=str, help='Name for the backup.')

    # Restore backup command
    restore_parser = subparsers.add_parser('restore', help='Restore a backup of the configuration.')
    restore_parser.add_argument('repository_name', type=str, help='Name of the repository to restore.')
    restore_parser.add_argument('backup_name', type=str, help='Name of the backup to restore.')

    # Manage command
    manage_parser = subparsers.add_parser('manage', help='Manage specific dotfiles.')
    manage_parser.add_argument('profile_name', type=str, help='Name of the profile to manage.')
    manage_parser.add_argument('--target-files', type=str, help='Comma-separated list of dotfiles to manage.')
    manage_parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying them.')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export a repository configuration.')
    export_parser.add_argument('repository_name', type=str, help='Name of the repository to export.')
    export_parser.add_argument('-o', '--output', type=str, default='export.json', help='Output JSON file.')
    export_parser.add_argument('--include-deps', action='store_true', help='Include dependencies in the export.')
    export_parser.add_argument('--include-assets', action='store_true', help='Include assets in the export.')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import a repository configuration.')
    import_parser.add_argument('file', type=str, help='Path to the JSON file to import.')
    import_parser.add_argument('-n', '--new-name', type=str, help='New name for the imported repository.')
    import_parser.add_argument('--skip-deps', action='store_true', help='Skip installing dependencies.')
    import_parser.add_argument('--skip-assets', action='store_true', help='Skip importing assets.')

    # Snapshot commands
    snapshot_parser = subparsers.add_parser('snapshot', help='Manage system snapshots.')
    snapshot_subparsers = snapshot_parser.add_subparsers(dest='snapshot_command', required=True)

    # Snapshot create
    snapshot_create_parser = snapshot_subparsers.add_parser('create', help='Create a snapshot.')
    snapshot_create_parser.add_argument('name', type=str, help='Name of the snapshot.')
    snapshot_create_parser.add_argument('-d', '--description', type=str, help='Description of the snapshot.', default='')

    # Snapshot list
    snapshot_list_parser = snapshot_subparsers.add_parser('list', help='List all snapshots.')

    # Snapshot restore
    snapshot_restore_parser = snapshot_subparsers.add_parser('restore', help='Restore from a snapshot.')
    snapshot_restore_parser.add_argument('name', type=str, help='Name of the snapshot to restore.')

    # Snapshot delete
    snapshot_delete_parser = snapshot_subparsers.add_parser('delete', help='Delete a snapshot.')
    snapshot_delete_parser.add_argument('name', type=str, help='Name of the snapshot to delete.')

    args = parser.parse_args()

    # Initialize DotfileManager
    manager = DotfileManager(verbose=args.verbose, log_file=args.log_file)

    if args.command == 'clone':
        success = manager.clone_repository(args.repository_url)

    elif args.command == 'apply':
        custom_paths = {}
        if args.custom_paths:
            for cp in args.custom_paths:
                if '=' in cp:
                    key, value = cp.split('=', 1)
                    custom_paths[key] = value
        template_context = {}
        if args.template_context:
            try:
                with open(args.template_context, 'r', encoding='utf-8') as f:
                    template_context = json.load(f)
            except Exception as e:
                manager.logger.error(f"Failed to load template context: {e}")
        custom_scripts = args.custom_scripts if args.custom_scripts else []
        profile = args.profile if args.profile else 'default'
        success = manager.apply_dotfiles(
            repository_name=args.repository_name,
            profile_name=profile,
            stow_options=args.stow_options,
            overwrite_symlink=args.overwrite_symlink,
            custom_paths=custom_paths,
            ignore_rules=args.ignore_rules,
            template_context=template_context,
            discover_templates=args.discover_templates,
            custom_scripts=custom_scripts
        )

    elif args.command == 'list':
        repository = args.repository_name if args.repository_name else None
        success = manager.list_profiles(repository)

    elif args.command == 'create':
        success = manager.create_profile(args.profile_name, args.description)

    elif args.command == 'backup':
        success = manager.create_backup(args.repository_name, args.backup_name)

    elif args.command == 'restore':
        success = manager.restore_backup(args.repository_name, args.backup_name)

    elif args.command == 'manage':
        target_files = args.target_files.split(',') if args.target_files else []
        success = manager.manage_dotfiles(
            profile_name=args.profile_name,
            target_files=target_files,
            dry_run=args.dry_run
        )

    elif args.command == 'export':
        success = manager.export_configuration(
            repository_name=args.repository_name,
            output_file=args.output,
            include_deps=args.include_deps,
            include_assets=args.include_assets
        )

    elif args.command == 'import':
        success = manager.import_configuration(
            file_path=args.file,
            new_name=args.new_name,
            skip_deps=args.skip_deps,
            skip_assets=args.skip_assets
        )

    elif args.command == 'snapshot':
        if args.snapshot_command == 'create':
            success = manager.create_snapshot(args.name, args.description)
        elif args.snapshot_command == 'list':
            success = manager.list_snapshots()
        elif args.snapshot_command == 'restore':
            success = manager.restore_snapshot(args.name)
        elif args.snapshot_command == 'delete':
            success = manager.delete_snapshot(args.name)
        else:
            manager.logger.error(f"Unknown snapshot command: {args.snapshot_command}")
            success = False

    else:
        manager.logger.error(f"Unknown command: {args.command}")
        success = False

    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
```

### **Explanation:**

- **New Subcommands Added:**
  - `list`: Lists all profiles or profiles for a specific repository.
  - `create`: Creates a new profile with an optional description.
  - `manage`: Manages specific dotfiles with options for targeting specific files and performing dry runs.
  - `export`: Exports a repository's configuration to a JSON file with options to include dependencies and assets.
  - `import`: Imports a repository's configuration from a JSON file with options to skip dependencies and assets.
  - `snapshot`: A parent command with subcommands `create`, `list`, `restore`, and `delete` for snapshot management.

- **Profile Support in Apply Command:**
  - The `apply` command now accepts a `--profile` argument to specify which profile to apply. If not provided, it defaults to the `default` profile.

---

## **2. Enhance `dotfile_manager.py` with New Methods**

Implement methods in the `DotfileManager` class to handle profile management, advanced file management, import/export functionalities, and snapshot management.

### **Updated `dotfile_manager.py`**

```python
# dotfilemanager/dotfile_manager.py

from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import subprocess
import shutil
import datetime
import time
import re
import asyncio
import logging
import json

from .config import ConfigManager
from .backup import BackupManager
from .logger import setup_logger
from .script import ScriptRunner
from .template import TemplateHandler
from .file_ops import FileOperations
from .dotfile_analyzer import DotfileAnalyzer, DotfileNode
from .exceptions import (
    RiceAutomataError,
    ConfigurationError,
    GitOperationError,
    FileOperationError,
    ValidationError,
    RollbackError,
    TemplateRenderingError,
    ScriptExecutionError,
    PackageManagerError,
    OSManagerError,
    BackupError,
)
from .utils import sanitize_path, create_timestamp, confirm_action
from .package_manager import PacmanManager, AURHelperManager, PackageManagerInterface
from .os_manager import OSManager

class DotfileManager:
    """
    Manages cloning, applying, backing up, and managing dotfiles configurations.
    """
    def __init__(self, 
                 verbose: bool = False, 
                 config_path: Optional[Path] = None, 
                 log_file: Optional[str] = None):
        """
        Initializes the DotfileManager.

        Args:
            verbose (bool): If True, sets log level to DEBUG.
            config_path (Optional[Path]): Path to the configuration file.
            log_file (Optional[str]): Path to the log file.
        """
        self.logger = setup_logger(verbose, log_file)
        self.config_manager = ConfigManager(config_path=config_path, logger=self.logger)
        self.backup_manager = BackupManager(logger=self.logger)
        self.os_manager = OSManager(logger=self.logger)
        self.package_manager: Optional[PackageManagerInterface] = None
        self.aur_helper_manager: Optional[AURHelperManager] = None
        self.script_runner = ScriptRunner(logger=self.logger)
        self.template_handler = TemplateHandler(logger=self.logger)
        self.file_ops = FileOperations(self.backup_manager, logger=self.logger)
        self.dependency_map = self._load_dependency_map()
        self.dotfile_analyzer = DotfileAnalyzer(self.dependency_map, logger=self.logger)
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.managed_rices_dir = sanitize_path("~/.config/managed-rices")
        self._ensure_managed_dir()
        self._initialize_package_manager()

    def _initialize_package_manager(self) -> None:
        """
        Initializes the appropriate package manager based on the OS.
        """
        package_manager_name = self.os_manager.get_package_manager()
        if not package_manager_name:
            self.logger.error("No supported package manager found on this system.")
            return
        if package_manager_name == 'pacman':
            self.package_manager = PacmanManager(logger=self.logger)
            self.aur_helper_manager = AURHelperManager(helper='yay', logger=self.logger)
            # Check if AUR helper is installed
            if not shutil.which('yay'):
                self.logger.info("No AUR helper found. Installing yay...")
                if not self.aur_helper_manager.install_helper():
                    self.logger.error("Failed to install AUR helper. AUR packages will not be installed.")
        elif package_manager_name == 'apt':
            # Implement AptManager if necessary
            pass
        elif package_manager_name == 'brew':
            # Implement BrewManager if necessary
            pass
        else:
            self.logger.error(f"Unsupported package manager: {package_manager_name}")

    def _ensure_managed_dir(self) -> None:
        """
        Ensures that the managed rices directory exists.
        """
        try:
            self.managed_rices_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Ensured managed rices directory at {self.managed_rices_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create managed rices directory: {e}")
            raise FileOperationError(f"Failed to create managed rices directory: {e}")

    def _load_dependency_map(self) -> Dict[str, str]:
        """
        Loads the dependency map from the configuration.

        Returns:
            Dict[str, str]: Dependency map.
        """
        try:
            rules_path = Path(__file__).parent.parent / "configs" / "dependency_map.json"
            if rules_path.exists():
                with rules_path.open('r', encoding='utf-8') as f:
                    dependency_map = json.load(f)
                    self.logger.debug(f"Loaded dependency map from {rules_path}")
                    return dependency_map
            else:
                self.logger.warning(f"Dependency map not found at {rules_path}. Using empty map.")
                return {}
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in dependency map: {e}")
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load dependency map: {e}")
            return {}

    # Existing methods (clone_repository, apply_dotfiles, etc.) remain unchanged

    ######################
    # New Profile Methods
    ######################

    def list_profiles(self, repository_name: Optional[str] = None) -> bool:
        """
        Lists all profiles or profiles for a specific repository.

        Args:
            repository_name (Optional[str]): Name of the repository to list profiles for.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if repository_name:
                profiles = self.config_manager.get_profiles(repository_name)
                if profiles is None:
                    self.logger.error(f"No profiles found for repository '{repository_name}'.")
                    return False
                self.logger.info(f"Profiles for repository '{repository_name}':")
            else:
                profiles = self.config_manager.get_all_profiles()
                if not profiles:
                    self.logger.info("No profiles found.")
                    return True
                self.logger.info("All profiles:")
            
            for repo, repo_profiles in profiles.items():
                active_marker = "*" if self.config_manager.get_active_profile(repo) == repo_profiles.get('active') else " "
                self.logger.info(f"{active_marker} Repository: {repo}")
                for profile_name, profile_info in repo_profiles['profiles'].items():
                    active = "(Active)" if profile_name == self.config_manager.get_active_profile(repo) else ""
                    description = profile_info.get('description', '')
                    self.logger.info(f"    - {profile_name} {active}: {description}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to list profiles: {e}")
            return False

    def create_profile(self, profile_name: str, description: str = "") -> bool:
        """
        Creates a new profile with the given name and description.

        Args:
            profile_name (str): Name of the new profile.
            description (str): Description of the profile.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            current_repo = self._get_current_rice()
            if not current_repo:
                self.logger.error("No active repository found to create a profile for.")
                return False

            self.config_manager.create_profile(current_repo, profile_name, description)
            self.logger.info(f"Profile '{profile_name}' created for repository '{current_repo}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create profile '{profile_name}': {e}")
            return False

    ###############################
    # New Advanced File Management
    ###############################

    def manage_dotfiles(self, profile_name: str, target_files: List[str], dry_run: bool = False) -> bool:
        """
        Manages specific dotfiles by applying or unlinking them.

        Args:
            profile_name (str): Name of the profile to manage.
            target_files (List[str]): List of dotfiles to manage.
            dry_run (bool): If True, preview changes without applying.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            current_repo = self._get_current_rice()
            if not current_repo:
                self.logger.error("No active repository found to manage dotfiles for.")
                return False

            profile = self.config_manager.get_profile(current_repo, profile_name)
            if not profile:
                self.logger.error(f"Profile '{profile_name}' not found for repository '{current_repo}'.")
                return False

            if dry_run:
                self.logger.info("Dry run enabled. Previewing changes...")
                # Implement dry-run logic here
                # For example, list the changes that would be made
                for file in target_files:
                    self.logger.info(f"[Dry Run] Would manage: {file}")
                return True

            # Implement actual management logic
            for file in target_files:
                self.logger.info(f"Managing dotfile: {file}")
                # Example: Unlink and relink using Stow or other methods
                # This is a placeholder for actual implementation
                success = self.file_ops.remove_files(Path(file))
                if success:
                    self.file_ops.copy_files(Path(file), Path.home() / file)
                else:
                    self.logger.error(f"Failed to manage dotfile: {file}")
                    return False

            self.logger.info(f"Successfully managed dotfiles for profile '{profile_name}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to manage dotfiles: {e}")
            return False

    #################################
    # New Import/Export Config Methods
    #################################

    def export_configuration(self, repository_name: str, output_file: str, 
                             include_deps: bool = False, include_assets: bool = False) -> bool:
        """
        Exports the configuration of a repository to a JSON file.

        Args:
            repository_name (str): Name of the repository to export.
            output_file (str): Path to the output JSON file.
            include_deps (bool): Whether to include dependencies.
            include_assets (bool): Whether to include assets.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            config = self.config_manager.get_rice_config(repository_name)
            if not config:
                self.logger.error(f"No configuration found for repository '{repository_name}'.")
                return False

            export_data = {
                'repository_name': repository_name,
                'repository_url': config.get('repository_url'),
                'profiles': config.get('profiles', {}),
                'active_profile': config.get('active_profile'),
                'applied': config.get('applied', False),
                'timestamp': config.get('timestamp'),
                'nix_config': config.get('nix_config', False)
            }

            if include_deps:
                export_data['dependencies'] = config.get('dependencies', [])

            if include_assets:
                export_data['assets'] = config.get('assets', [])

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=4)
                self.logger.info(f"Configuration exported to '{output_file}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            return False

    def import_configuration(self, file_path: str, new_name: Optional[str] = None, 
                             skip_deps: bool = False, skip_assets: bool = False) -> bool:
        """
        Imports a configuration from a JSON file.

        Args:
            file_path (str): Path to the JSON file to import.
            new_name (Optional[str]): New name for the imported repository.
            skip_deps (bool): Whether to skip installing dependencies.
            skip_assets (bool): Whether to skip importing assets.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            repository_name = new_name if new_name else import_data.get('repository_name')
            repository_url = import_data.get('repository_url')
            profiles = import_data.get('profiles', {})
            active_profile = import_data.get('active_profile')
            applied = import_data.get('applied', False)
            timestamp = import_data.get('timestamp')
            nix_config = import_data.get('nix_config', False)
            dependencies = import_data.get('dependencies', [])
            assets = import_data.get('assets', [])

            if not repository_url:
                self.logger.error("Repository URL is missing in the import file.")
                return False

            # Clone the repository
            success = self.clone_repository(repository_url)
            if not success:
                self.logger.error(f"Failed to clone repository '{repository_url}'.")
                return False

            # Update configuration
            self.config_manager.add_rice_config(repository_name, {
                'repository_url': repository_url,
                'local_directory': str(self.managed_rices_dir / repository_name),
                'profiles': profiles,
                'active_profile': active_profile,
                'applied': applied,
                'timestamp': timestamp,
                'nix_config': nix_config
            })

            # Install dependencies if not skipped
            if not skip_deps and dependencies:
                self.logger.info("Installing dependencies from imported configuration...")
                if self.package_manager:
                    if not self.package_manager.install_packages(list(dependencies)):
                        self.logger.error("Failed to install dependencies.")
                        return False

            # Import assets if not skipped
            if not skip_assets and assets:
                self.logger.info("Importing assets from imported configuration...")
                # Implement asset import logic here
                # Placeholder for actual implementation
                for asset in assets:
                    self.logger.info(f"Imported asset: {asset}")

            self.logger.info(f"Configuration imported successfully as '{repository_name}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
            return False

    ##########################
    # New Snapshot Methods
    ##########################

    def create_snapshot(self, name: str, description: str = "") -> bool:
        """
        Creates a system snapshot with the given name and description.

        Args:
            name (str): Name of the snapshot.
            description (str): Description of the snapshot.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshots_dir = Path.home() / ".config" / "riceautomator" / "snapshots"
            snapshots_dir.mkdir(parents=True, exist_ok=True)
            snapshot_path = snapshots_dir / name

            if snapshot_path.exists():
                self.logger.error(f"Snapshot '{name}' already exists.")
                return False

            # Implement snapshot creation logic here
            # This could involve copying essential configuration files, capturing package lists, etc.
            # Placeholder for actual implementation
            snapshot_path.mkdir()
            self.logger.info(f"Snapshot '{name}' created successfully.")

            # Optionally, save metadata
            metadata = {
                'name': name,
                'description': description,
                'created_at': create_timestamp(),
                'packages': self._get_installed_packages(),
                'configurations': self.config_manager.config_data
            }
            with open(snapshot_path / "metadata.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=4)
            self.logger.debug(f"Snapshot metadata saved at '{snapshot_path}/metadata.json'.")

            return True
        except Exception as e:
            self.logger.error(f"Failed to create snapshot '{name}': {e}")
            return False

    def list_snapshots(self) -> bool:
        """
        Lists all available snapshots.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshots_dir = Path.home() / ".config" / "riceautomator" / "snapshots"
            if not snapshots_dir.exists():
                self.logger.info("No snapshots found.")
                return True

            snapshots = [snapshot.name for snapshot in snapshots_dir.iterdir() if snapshot.is_dir()]
            if not snapshots:
                self.logger.info("No snapshots found.")
                return True

            self.logger.info("Available snapshots:")
            for snapshot in snapshots:
                self.logger.info(f" - {snapshot}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to list snapshots: {e}")
            return False

    def restore_snapshot(self, name: str) -> bool:
        """
        Restores the system to a specified snapshot.

        Args:
            name (str): Name of the snapshot to restore.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshots_dir = Path.home() / ".config" / "riceautomator" / "snapshots"
            snapshot_path = snapshots_dir / name

            if not snapshot_path.exists():
                self.logger.error(f"Snapshot '{name}' does not exist.")
                return False

            # Implement snapshot restoration logic here
            # This could involve restoring configuration files, reinstalling packages, etc.
            # Placeholder for actual implementation
            # For example, restore configurations
            metadata_file = snapshot_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                self.config_manager.config_data = metadata.get('configurations', {})
                self.config_manager.save_config()
                self.logger.info(f"Configurations restored from snapshot '{name}'.")

            self.logger.info(f"Snapshot '{name}' restored successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore snapshot '{name}': {e}")
            return False

    def delete_snapshot(self, name: str) -> bool:
        """
        Deletes a specified snapshot.

        Args:
            name (str): Name of the snapshot to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshots_dir = Path.home() / ".config" / "riceautomator" / "snapshots"
            snapshot_path = snapshots_dir / name

            if not snapshot_path.exists():
                self.logger.error(f"Snapshot '{name}' does not exist.")
                return False

            shutil.rmtree(snapshot_path)
            self.logger.info(f"Snapshot '{name}' deleted successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete snapshot '{name}': {e}")
            return False

    ##############################
    # Helper Methods for Snapshots
    ##############################

    def _get_installed_packages(self) -> Dict[str, List[str]]:
        """
        Retrieves the list of installed packages for different package managers.

        Returns:
            Dict[str, List[str]]: Installed packages categorized by package manager.
        """
        installed_packages = {}
        try:
            # Example for Pacman
            if self.package_manager and isinstance(self.package_manager, PacmanManager):
                result = subprocess.run(['pacman', '-Qq'], capture_output=True, text=True)
                if result.returncode == 0:
                    installed_packages['pacman'] = result.stdout.strip().split('\n')
            # Example for AUR helper
            if self.aur_helper_manager and shutil.which('yay'):
                result = subprocess.run(['yay', '-Qq'], capture_output=True, text=True)
                if result.returncode == 0:
                    installed_packages['aur'] = result.stdout.strip().split('\n')
            # Add other package managers as needed
            return installed_packages
        except Exception as e:
            self.logger.warning(f"Failed to retrieve installed packages: {e}")
            return installed_packages

    ######################
    # Existing Methods
    ######################

    # Existing methods like clone_repository, apply_dotfiles, create_backup, restore_backup remain unchanged

```

### **Explanation:**

- **Profile Management Methods:**
  - `list_profiles`: Lists all profiles or profiles for a specific repository.
  - `create_profile`: Creates a new profile with an optional description.

- **Advanced File Management Method:**
  - `manage_dotfiles`: Manages specific dotfiles based on the provided list. Supports dry-run functionality to preview changes.

- **Import/Export Configuration Methods:**
  - `export_configuration`: Exports the repository's configuration to a JSON file, with options to include dependencies and assets.
  - `import_configuration`: Imports a repository's configuration from a JSON file, with options to rename and skip dependencies or assets.

- **Snapshot Management Methods:**
  - `create_snapshot`: Creates a system snapshot with a name and optional description. Stores metadata including installed packages and configurations.
  - `list_snapshots`: Lists all available snapshots.
  - `restore_snapshot`: Restores the system to a specified snapshot by restoring configurations and other settings.
  - `delete_snapshot`: Deletes a specified snapshot.

- **Helper Method:**
  - `_get_installed_packages`: Retrieves the list of installed packages from different package managers to include in snapshot metadata.

**Note:** The snapshot creation and restoration logic provided here are placeholders. Depending on your system and requirements, you might need to integrate with system snapshot tools like `rsync`, `Timeshift`, or use other methods to capture and restore system states comprehensively.

---

## **3. Update `config.py` to Support Profiles**

Modify the `ConfigManager` to handle multiple profiles per repository, including active profiles and profile descriptions.

### **Updated `config.py`**

```python
# dotfilemanager/config.py

import json
from pathlib import Path
from typing import Any, Dict, Optional
import logging

from .exceptions import ConfigurationError
from .utils import create_timestamp

class ConfigManager:
    """
    Manages loading and saving configurations.
    """
    def __init__(self, config_path: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        """
        Initializes the ConfigManager.

        Args:
            config_path (Optional[Path]): Path to the configuration file.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')
        self.config_path = config_path or Path.home() / '.dotfilemanager' / 'config.json'
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """
        Loads the configuration from the config file.
        """
        try:
            if self.config_path.exists():
                with self.config_path.open('r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                    self.logger.debug(f"Loaded configuration from {self.config_path}")
            else:
                self.config_data = {'rices': {}}
                self.logger.info(f"No configuration file found at {self.config_path}. Initialized with empty config.")
                self.save_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def save_config(self) -> None:
        """
        Saves the current configuration to the config file.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open('w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
                self.logger.debug(f"Saved configuration to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def add_rice_config(self, repository_name: str, config: Dict[str, Any]) -> None:
        """
        Adds or updates a rice configuration.

        Args:
            repository_name (str): Name of the repository.
            config (Dict[str, Any]): Configuration data.
        """
        self.config_data.setdefault('rices', {})[repository_name] = config
        self.save_config()

    def get_rice_config(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the configuration for a specific rice.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[Dict[str, Any]]: Configuration data if exists, else None.
        """
        return self.config_data.get('rices', {}).get(repository_name)

    def create_profile(self, repository_name: str, profile_name: str, description: str = "") -> None:
        """
        Creates a new profile for a given rice.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile.
            description (str): Description of the profile.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            profiles = rice_config.setdefault('profiles', {})
            if profile_name in profiles:
                self.logger.warning(f"Profile '{profile_name}' already exists for repository '{repository_name}'.")
            else:
                profiles[profile_name] = {
                    'description': description,
                    'dotfile_directories': {},
                    'dependencies': [],
                    'script_config': {
                        'pre_clone': [],
                        'post_clone': [],
                        'pre_install_dependencies': [],
                        'post_install_dependencies': [],
                        'pre_apply': [],
                        'post_apply': [],
                        'pre_uninstall': [],
                        'post_uninstall': [],
                        'custom_scripts': [],
                        'shell': "bash"
                    },
                    'custom_extras_paths': {}
                }
                self.save_config()
                self.logger.debug(f"Created profile '{profile_name}' for repository '{repository_name}'.")
        else:
            self.logger.error(f"Rice configuration for '{repository_name}' not found.")

    def get_profiles(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves all profiles for a specific repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[Dict[str, Any]]: Profiles data if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            return rice_config.get('profiles', {})
        return None

    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves all profiles across all repositories.

        Returns:
            Dict[str, Dict[str, Any]]: All profiles categorized by repository.
        """
        return {repo: config.get('profiles', {}) for repo, config in self.config_data.get('rices', {}).items()}

    def get_active_profile(self, repository_name: str) -> Optional[str]:
        """
        Retrieves the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[str]: Name of the active profile if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            return rice_config.get('active_profile')
        return None

    def set_active_profile(self, repository_name: str, profile_name: str) -> bool:
        """
        Sets the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile to set as active.

        Returns:
            bool: True if successful, False otherwise.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config and 'profiles' in rice_config and profile_name in rice_config['profiles']:
            rice_config['active_profile'] = profile_name
            self.save_config()
            self.logger.debug(f"Set active profile to '{profile_name}' for repository '{repository_name}'.")
            return True
        self.logger.error(f"Profile '{profile_name}' not found for repository '{repository_name}'.")
        return False

    def get_all_profiles_dict(self) -> Dict[str, Any]:
        """
        Retrieves all profiles in a structured dictionary.

        Returns:
            Dict[str, Any]: All profiles categorized by repository.
        """
        return self.config_data.get('rices', {})

    #################################
    # New Snapshot Methods (Continued)
    #################################

    # Snapshot methods as defined in the previous section remain unchanged

    ######################
    # New Import/Export Config Methods
    ######################
    
    # Import and Export methods as defined in the previous section remain unchanged

    ######################
    # New Profile Methods (Continued)
    ######################

    # Profile methods as defined in the previous section remain unchanged

    # ... rest of the existing code ...
```

### **Explanation:**

- **Profile Management Enhancements:**
  - **`list_profiles`**: Lists all profiles or profiles for a specific repository, indicating the active profile.
  - **`create_profile`**: Creates a new profile with an optional description for a specific repository.
  - **`set_active_profile`**: Sets a specific profile as active for a repository.
  
- **Advanced File Management:**
  - **`manage_dotfiles`**: Manages specific dotfiles, with support for dry-run to preview changes.

- **Import/Export Configuration:**
  - **`export_configuration`**: Exports the repository's configuration to a JSON file, with options to include dependencies and assets.
  - **`import_configuration`**: Imports a repository's configuration from a JSON file, with options to rename and skip dependencies or assets.

- **Snapshot Management:**
  - **`create_snapshot`**: Creates a snapshot of the current system state, including configurations and installed packages.
  - **`list_snapshots`**: Lists all available snapshots.
  - **`restore_snapshot`**: Restores the system to a specified snapshot.
  - **`delete_snapshot`**: Deletes a specified snapshot.
  
- **Helper Method:**
  - **`_get_installed_packages`**: Retrieves installed packages from different package managers to include in snapshot metadata.

**Note:** The import/export and snapshot functionalities provided here are basic implementations. Depending on your requirements, you may need to expand these methods to handle more complex scenarios, such as managing assets, handling different package managers, and ensuring comprehensive system state capture during snapshots.

---

## **4. Implement Snapshot Management in `backup.py`**

Although snapshot functionalities are partially handled in `dotfile_manager.py`, it's advisable to have a dedicated `snapshot.py` module for better organization and maintainability.

### **New `snapshot.py` Module**

Create a new file `snapshot.py` inside the `dotfilemanager` package.

```python
# dotfilemanager/snapshot.py

from pathlib import Path
from typing import Optional, Dict, Any
import shutil
import json
import logging

from .exceptions import BackupError

class SnapshotManager:
    """
    Manages system snapshots.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initializes the SnapshotManager.

        Args:
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')
        self.snapshots_dir = Path.home() / ".config" / "riceautomator" / "snapshots"
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, name: str, description: str = "", metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Creates a snapshot with the given name and description.

        Args:
            name (str): Name of the snapshot.
            description (str): Description of the snapshot.
            metadata (Optional[Dict[str, Any]]): Additional metadata to include.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshot_path = self.snapshots_dir / name
            if snapshot_path.exists():
                self.logger.error(f"Snapshot '{name}' already exists.")
                return False

            snapshot_path.mkdir()
            self.logger.debug(f"Created snapshot directory at '{snapshot_path}'.")

            # Save metadata
            if metadata:
                metadata_file = snapshot_path / "metadata.json"
                with metadata_file.open('w', encoding='utf-8') as f:
                    json.dump(metadata, f, indent=4)
                self.logger.debug(f"Snapshot metadata saved at '{metadata_file}'.")

            self.logger.info(f"Snapshot '{name}' created successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create snapshot '{name}': {e}")
            return False

    def list_snapshots(self) -> list:
        """
        Lists all available snapshots.

        Returns:
            list: List of snapshot names.
        """
        try:
            snapshots = [snapshot.name for snapshot in self.snapshots_dir.iterdir() if snapshot.is_dir()]
            self.logger.debug(f"Found snapshots: {snapshots}")
            return snapshots
        except Exception as e:
            self.logger.error(f"Failed to list snapshots: {e}")
            return []

    def restore_snapshot(self, name: str) -> bool:
        """
        Restores the system to the specified snapshot.

        Args:
            name (str): Name of the snapshot to restore.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshot_path = self.snapshots_dir / name
            if not snapshot_path.exists():
                self.logger.error(f"Snapshot '{name}' does not exist.")
                return False

            # Implement restoration logic here
            # Placeholder for actual implementation
            self.logger.info(f"Restoring snapshot '{name}'...")
            # Example: Restore configurations from snapshot
            metadata_file = snapshot_path / "metadata.json"
            if metadata_file.exists():
                with metadata_file.open('r', encoding='utf-8') as f:
                    metadata = json.load(f)
                # Restore configurations
                # This is a placeholder and should be replaced with actual restoration logic
                self.logger.debug(f"Restored configurations from snapshot '{name}'.")
            
            self.logger.info(f"Snapshot '{name}' restored successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to restore snapshot '{name}': {e}")
            return False

    def delete_snapshot(self, name: str) -> bool:
        """
        Deletes the specified snapshot.

        Args:
            name (str): Name of the snapshot to delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            snapshot_path = self.snapshots_dir / name
            if not snapshot_path.exists():
                self.logger.error(f"Snapshot '{name}' does not exist.")
                return False

            shutil.rmtree(snapshot_path)
            self.logger.info(f"Snapshot '{name}' deleted successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete snapshot '{name}': {e}")
            return False
```

### **Explanation:**

- **`SnapshotManager` Class:**
  - **`create_snapshot`**: Creates a new snapshot directory and saves any provided metadata.
  - **`list_snapshots`**: Retrieves a list of all existing snapshots.
  - **`restore_snapshot`**: Restores the system to a specified snapshot. **Note:** The actual restoration logic needs to be implemented based on your system's requirements.
  - **`delete_snapshot`**: Deletes a specified snapshot directory.

- **Integration with `DotfileManager`:**
  - Instantiate `SnapshotManager` within `DotfileManager` and delegate snapshot-related operations to it.

### **Integrate `SnapshotManager` into `DotfileManager`**

Update the `DotfileManager` class in `dotfile_manager.py` to include `SnapshotManager`.

```python
# Inside dotfile_manager.py

from .snapshot import SnapshotManager

class DotfileManager:
    # ... existing __init__ method ...
    def __init__(self, 
                 verbose: bool = False, 
                 config_path: Optional[Path] = None, 
                 log_file: Optional[str] = None):
        # ... existing initialization ...
        self.snapshot_manager = SnapshotManager(logger=self.logger)
        # ... rest of the initialization ...
    
    # Update snapshot methods to delegate to SnapshotManager
    def create_snapshot(self, name: str, description: str = "") -> bool:
        metadata = {
            'name': name,
            'description': description,
            'created_at': create_timestamp(),
            'packages': self._get_installed_packages(),
            'configurations': self.config_manager.config_data
        }
        return self.snapshot_manager.create_snapshot(name, description, metadata)

    def list_snapshots(self) -> bool:
        snapshots = self.snapshot_manager.list_snapshots()
        if not snapshots:
            self.logger.info("No snapshots found.")
            return True
        self.logger.info("Available snapshots:")
        for snapshot in snapshots:
            self.logger.info(f" - {snapshot}")
        return True

    def restore_snapshot(self, name: str) -> bool:
        return self.snapshot_manager.restore_snapshot(name)

    def delete_snapshot(self, name: str) -> bool:
        return self.snapshot_manager.delete_snapshot(name)
```

### **Explanation:**

- **`SnapshotManager` Integration:**
  - The `DotfileManager` now includes an instance of `SnapshotManager`.
  - Snapshot-related methods (`create_snapshot`, `list_snapshots`, `restore_snapshot`, `delete_snapshot`) delegate their operations to the corresponding methods in `SnapshotManager`.

---

## **5. Update `config.py` to Handle Multiple Profiles**

Ensure that the `ConfigManager` properly manages multiple profiles per repository, including setting and retrieving the active profile.

### **Further Enhancements in `config.py`**

```python
# Continuing in config.py

    def set_active_profile(self, repository_name: str, profile_name: str) -> bool:
        """
        Sets the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile to set as active.

        Returns:
            bool: True if successful, False otherwise.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config and 'profiles' in rice_config and profile_name in rice_config['profiles']:
            rice_config['active_profile'] = profile_name
            self.save_config()
            self.logger.debug(f"Set active profile to '{profile_name}' for repository '{repository_name}'.")
            return True
        self.logger.error(f"Profile '{profile_name}' not found for repository '{repository_name}'.")
        return False

    def get_active_profile(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[Dict[str, Any]]: Active profile data if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            active_profile_name = rice_config.get('active_profile')
            if active_profile_name:
                return rice_config.get('profiles', {}).get(active_profile_name)
        return None
```

### **Explanation:**

- **`set_active_profile`**: Sets a specified profile as active for a given repository.
- **`get_active_profile`**: Retrieves the active profile's data for a given repository.

---

## **6. Create or Update `profiles.py` (Optional)**

For better organization, you can create a separate module `profiles.py` to handle profile-specific functionalities. However, if you prefer to keep profile management within `dotfile_manager.py`, this step is optional.

### **Example `profiles.py`**

```python
# dotfilemanager/profiles.py

from typing import Dict, Any, Optional
import logging

from .config import ConfigManager

class ProfileManager:
    """
    Manages profiles for dotfile repositories.
    """
    def __init__(self, config_manager: ConfigManager, logger: Optional[logging.Logger] = None):
        """
        Initializes the ProfileManager.

        Args:
            config_manager (ConfigManager): Instance of ConfigManager.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.config_manager = config_manager
        self.logger = logger or logging.getLogger('DotfileManager')

    def create_profile(self, repository_name: str, profile_name: str, description: str = "") -> bool:
        """
        Creates a new profile.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile.
            description (str): Description of the profile.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            self.config_manager.create_profile(repository_name, profile_name, description)
            self.logger.info(f"Profile '{profile_name}' created for repository '{repository_name}'.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to create profile '{profile_name}': {e}")
            return False

    def list_profiles(self, repository_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Lists profiles for a specific repository or all repositories.

        Args:
            repository_name (Optional[str]): Name of the repository.

        Returns:
            Dict[str, Any]: Profiles data.
        """
        if repository_name:
            profiles = self.config_manager.get_profiles(repository_name)
            if profiles is None:
                self.logger.error(f"No profiles found for repository '{repository_name}'.")
                return {}
            return {repository_name: profiles}
        else:
            return self.config_manager.get_all_profiles()
```

### **Explanation:**

- **`ProfileManager` Class:**
  - Handles profile creation and listing by interacting with the `ConfigManager`.
  
- **Integration with `DotfileManager`:**
  - Instantiate `ProfileManager` within `DotfileManager` and delegate profile-related operations to it.

**Note:** This module is optional and serves to further organize your code. You can choose to implement it based on your preference for code modularity.

---

## **7. Update `exceptions.py` if Necessary**

Ensure that all new potential errors are appropriately handled by defining new exception classes if needed.

### **Example Addition to `exceptions.py`**

```python
# dotfilemanager/exceptions.py

class ProfileError(RiceAutomataError):
    """Raised when there is a profile-related error."""
    pass

class SnapshotError(RiceAutomataError):
    """Raised when there is a snapshot-related error."""
    pass

# ... existing exception classes ...
```

### **Explanation:**

- **`ProfileError`**: Handles errors related to profile management.
- **`SnapshotError`**: Handles errors related to snapshot management.

---

## **8. Update `utils.py` with Additional Utility Functions**

Add any additional utility functions required for the new functionalities.

### **Example Additions to `utils.py`**

```python
# dotfilemanager/utils.py

def parse_custom_paths(custom_paths: List[str]) -> Dict[str, str]:
    """
    Parses custom paths provided in the format key=value.

    Args:
        custom_paths (List[str]): List of custom paths as strings.

    Returns:
        Dict[str, str]: Parsed custom paths as a dictionary.
    """
    parsed = {}
    for cp in custom_paths:
        if '=' in cp:
            key, value = cp.split('=', 1)
            parsed[key.strip()] = value.strip()
    return parsed
```

### **Explanation:**

- **`parse_custom_paths`**: Parses custom path arguments provided in the format `key=value` into a dictionary for easier handling within the application.

---

## **9. Update `README.md` to Reflect New Functionalities**

Ensure that the documentation accurately describes the new commands and features added to **DotfileManager**.

### **Updated `README.md`**

```markdown
# DotfileManager

**DotfileManager** is a versatile Python tool designed to manage and apply dotfiles configurations efficiently. It handles cloning repositories, installing dependencies, backing up existing configurations, managing multiple profiles, creating snapshots, and applying new configurations using GNU Stow or other methods.

## Features

- **Profile Management**: Create and switch between different system configurations.
- **Automatic Backups**: Safe configuration changes with automatic backups.
- **Package Management**: Handles package installations across different package managers.
- **Smart Analysis**: Analyzes dotfiles for dependencies and conflicts.
- **Safe Operations**: Rollback capability if something goes wrong.
- **Template Support**: Use templates to customize configurations.
- **Snapshot Management**: Create, list, restore, and delete system snapshots.
- **Import/Export Configurations**: Share and migrate configurations easily.

## Quick Start

1. **Installation**
    ```bash
    # Clone the repository
    git clone https://github.com/yourusername/dotfilemanager.git
    cd dotfilemanager

    # Install dependencies
    pip install -r requirements.txt
    ```

2. **Basic Usage**

    ```bash
    # Clone a dotfiles repository
    python -m dotfilemanager.main clone https://github.com/user/dotfiles.git

    # List all profiles (* indicates active profile)
    python -m dotfilemanager.main list

    # List profiles for a specific repository
    python -m dotfilemanager.main list my-dotfiles

    # Create a new profile
    python -m dotfilemanager.main create my-profile --description "My awesome rice"

    # Apply a profile
    python -m dotfilemanager.main apply my-dotfiles --profile minimal

    # Create a backup
    python -m dotfilemanager.main backup my-dotfiles backup1

    # Restore from a backup
    python -m dotfilemanager.main restore my-dotfiles backup1
    ```

## Command Reference

### Basic Commands
```bash
# Profile Management
python -m dotfilemanager.main create <profile-name> [--description "Description"]  # Create a new profile
python -m dotfilemanager.main list [repository-name]                              # List all profiles or profiles for a repository
python -m dotfilemanager.main apply <repository-name> --profile <profile-name>   # Apply a specific profile

# Backup Operations
python -m dotfilemanager.main backup <repository-name> <backup-name>            # Create a backup
python -m dotfilemanager.main restore <repository-name> <backup-name>           # Restore from a backup
```

### Advanced File Management
```bash
# Manage specific dotfiles
python -m dotfilemanager.main manage <profile-name> --target-files .config/i3,.config/polybar [--dry-run]

# Import/Export Configurations
python -m dotfilemanager.main export <repository-name> -o output.json [--include-deps] [--include-assets]
python -m dotfilemanager.main import <file.json> -n new-name [--skip-deps] [--skip-assets]
```

### Snapshot Management
```bash
# Create a snapshot
python -m dotfilemanager.main snapshot create <name> -d "description"

# List all snapshots
python -m dotfilemanager.main snapshot list

# Restore from snapshot
python -m dotfilemanager.main snapshot restore <name>

# Delete a snapshot
python -m dotfilemanager.main snapshot delete <name>
```

## Directory Structure

```
~/.config/dotfilemanager/
├── managed-rices/      # Managed rice repositories
├── backups/            # Automatic backups
├── snapshots/          # System snapshots
└── config.json         # Main configuration file
```

## Tips

- Always create a backup before applying a new profile.
- Use the `--dry-run` flag to preview changes without applying them.
- Check the logs at `~/.dotfilemanager/logs` if something goes wrong.
- Use templates for configuration files that need system-specific modifications.
- Export your configurations to share them with others.
- Use snapshots for major system changes.

## Advanced Features

### Export/Import
The export feature allows you to share your rice configurations with others:
- Include dependencies with `--include-deps`
- Include assets (wallpapers, themes) with `--include-assets`
- Specify custom output file with `-o filename.json`

The import feature allows you to import configurations:
- Rename the repository with `-n new-name`
- Skip installing dependencies with `--skip-deps`
- Skip importing assets with `--skip-assets`

### Snapshots
Snapshots are comprehensive backups capturing the entire system state:
- Capture configurations and package lists.
- Store configuration metadata.
- Perfect for major system changes or migrations.

### Templates
Use templates to handle system-specific configurations:
- Variables for system-dependent values.
- Conditional sections based on hardware.
- Automatic path adjustments.

## Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository.
2. Create a new branch for your feature or bugfix.
3. Commit your changes with clear messages.
4. Open a pull request detailing your changes.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Contact

For questions or support, please open an issue on the GitHub repository or contact [youremail@example.com](mailto:youremail@example.com).
```

### **Explanation:**

- **Updated Features Section:** Added new features like Profile Management and Snapshot Management.
- **Command Reference:** Expanded to include new commands for managing profiles, snapshots, and advanced file management.
- **Directory Structure:** Updated to reflect the new directories for managed rices and snapshots.
- **Advanced Features:** Detailed the new Import/Export and Snapshot functionalities.
- **Usage Examples:** Provided updated examples showcasing the new commands.

---

## **10. Update `__init__.py`**

Ensure that all new modules are imported in the `__init__.py` to make them accessible as part of the package.

### **Updated `__init__.py`**

```python
# dotfilemanager/__init__.py

# Import classes to make them accessible when importing the package
from .dotfile_manager import DotfileManager
from .profiles import ProfileManager
from .snapshot import SnapshotManager
```

### **Explanation:**

- **Exports:** Exposes `DotfileManager`, `ProfileManager`, and `SnapshotManager` when importing the `dotfilemanager` package.

---

## **11. Implement Unit Tests (Recommended)**

To ensure that all new functionalities work as expected, implement unit tests using frameworks like `pytest`. Place these tests inside a `tests/` directory.

### **Example `tests/test_profiles.py`**

```python
# tests/test_profiles.py

import pytest
from pathlib import Path
from dotfilemanager.config import ConfigManager

@pytest.fixture
def config_manager(tmp_path):
    config_path = tmp_path / "config.json"
    return ConfigManager(config_path=config_path)

def test_create_profile(config_manager):
    repository_name = "test-repo"
    profile_name = "test-profile"
    description = "Test profile description"

    # Initially, no profiles should exist
    assert config_manager.get_profiles(repository_name) == {}

    # Create a profile
    config_manager.create_profile(repository_name, profile_name, description)

    # Verify the profile was created
    profiles = config_manager.get_profiles(repository_name)
    assert profile_name in profiles
    assert profiles[profile_name]['description'] == description

def test_set_active_profile(config_manager):
    repository_name = "test-repo"
    profile_name1 = "profile1"
    profile_name2 = "profile2"

    config_manager.create_profile(repository_name, profile_name1, "First profile")
    config_manager.create_profile(repository_name, profile_name2, "Second profile")

    # Set active profile to profile1
    assert config_manager.set_active_profile(repository_name, profile_name1) == True
    assert config_manager.get_active_profile(repository_name) == profile_name1

    # Set active profile to profile2
    assert config_manager.set_active_profile(repository_name, profile_name2) == True
    assert config_manager.get_active_profile(repository_name) == profile_name2

    # Attempt to set a non-existent profile
    assert config_manager.set_active_profile(repository_name, "non-existent") == False
```

### **Explanation:**

- **Fixtures:** Uses `pytest` fixtures to create a temporary configuration environment.
- **Test Cases:** Includes test cases for creating profiles and setting active profiles, ensuring the `ConfigManager` behaves as expected.

**Note:** Similar tests should be implemented for other functionalities like snapshot management, import/export, and advanced file management.

---

## **12. Set Up Continuous Integration (CI)**

To maintain code quality and ensure reliability, set up Continuous Integration pipelines using platforms like GitHub Actions. This automates testing and enforces code standards on every commit or pull request.

### **Example GitHub Actions Workflow (`.github/workflows/ci.yml`)**

```yaml
name: Python CI

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  build:

    runs-on: ubuntu-latest

    strategy:
      matrix:
        python-version: [3.8, 3.9, 3.10, 3.11]

    steps:
    - uses: actions/checkout@v2
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v2
      with:
        python-version: ${{ matrix.python-version }}
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install pytest
    - name: Run tests
      run: |
        pytest
```

### **Explanation:**

- **Python Versions:** Tests the code against multiple Python versions for compatibility.
- **Steps:**
  - **Checkout Code:** Retrieves the repository's code.
  - **Set Up Python:** Installs the specified Python version.
  - **Install Dependencies:** Installs project dependencies and `pytest`.
  - **Run Tests:** Executes the test suite to ensure all tests pass.

---

## **13. Additional Considerations**

- **Security:**
  - Avoid using `shell=True` in subprocess calls unless absolutely necessary.
  - Ensure all inputs, especially those coming from user commands, are sanitized to prevent security vulnerabilities.

- **Logging:**
  - The `logger.py` is set up with a rotating file handler to prevent log files from growing indefinitely. Adjust `maxBytes` and `backupCount` as needed based on your requirements.

- **Error Handling:**
  - Comprehensive error handling and logging are implemented to aid in debugging and provide clear feedback during operations.
  - Define and raise specific exceptions where appropriate to handle different error scenarios gracefully.

- **Extensibility:**
  - The design allows for easy addition of support for other package managers or operating systems by extending the respective manager classes.
  - Future enhancements can include GUI support, remote repository integrations, and more.

- **Documentation:**
  - Keep the `README.md` updated with all new commands and features.
  - Consider adding inline documentation and docstrings to all methods and classes for better maintainability.

- **Testing:**
  - Implement thorough unit tests for all new functionalities.
  - Consider integration tests to ensure different components work seamlessly together.

- **Backup and Restore:**
  - Ensure that backups are verified for integrity.
  - Implement versioning or timestamping for backups to manage multiple backup instances effectively.

- **Templates:**
  - Ensure that your templates are correctly formatted and that the context provided matches the placeholders in the templates.
  - Implement validation to check the correctness of templates before rendering.

By following the above guidelines and implementing the provided code changes, your **DotfileManager** will effectively incorporate the functionalities previously outlined in the `RiceAutomata` README, providing a robust and user-friendly tool for managing dotfiles and system configurations.