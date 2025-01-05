# src/dotfile_manager.py

from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import subprocess
import shutil
import datetime
import time
import re
import logging
import json
from contextlib import contextmanager

from .config import ConfigManager, RepositoryConfig
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
from .package_manager import PackageManager, PackageManagerInterface
from .os_manager import OSManager


class DotfileManager:
    """
    Manages cloning, applying, backing up, and managing dotfiles configurations.
    """

    def __init__(
        self,
        verbose: bool = False,
        config_path: Optional[Path] = None,
        log_file: Optional[str] = None
    ):
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
        self.package_manager = PackageManager(logger=self.logger)
        self.aur_helper_manager = self.package_manager.aur_helper_manager
        self.script_runner = ScriptRunner(logger=self.logger)
        self.template_handler = TemplateHandler(logger=self.logger)
        self.file_ops = FileOperations(self.backup_manager, logger=self.logger)
        self.dependency_map = self._load_dependency_map()
        self.dotfile_analyzer = DotfileAnalyzer(self.dependency_map, logger=self.logger)
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.managed_rices_dir = sanitize_path("~/.config/managed-rices")
        self._ensure_managed_dir()

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

    def _load_dependency_map(self) -> Dict[str, Any]:
        """
        Loads the dependency map from the configuration.

        Returns:
            Dict[str, Any]: Dependency map.
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

    def clone_repository(self, repository_url: str) -> bool:
        """
        Clones a git repository with retry and rollback support.

        Args:
            repository_url (str): URL of the git repository.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Normalize the repository URL
            repository_url = self._normalize_repo_url(repository_url)
            repo_name = self._extract_repo_name(repository_url)
            local_dir = self.managed_rices_dir / repo_name

            if local_dir.exists():
                self.logger.warning(f"Repository already exists at {local_dir}")
                return False

            backup_id = None
            try:
                with self._transactional_operation("clone_repository"):
                    backup_id = self.backup_manager.create_backup(repository_name=repo_name, backup_name=create_timestamp())
                    self.logger.info(f"Cloning repository from {repository_url} into {local_dir}")
                    subprocess.run(['git', 'clone', '--recursive', repository_url, str(local_dir)], check=True)
                    self.logger.info(f"Repository cloned successfully to: {local_dir}")
            except subprocess.CalledProcessError as e:
                self.logger.error(f"An error occurred during clone_repository: {e}")
                if backup_id:
                    self.backup_manager.rollback_backup(repository_name=repo_name, backup_name=backup_id, target_dir=local_dir)
                return False

            # Check for repository-specific configuration
            config = self._load_or_create_repo_config(repo_name, repository_url, local_dir)
            if config is None:
                self.logger.error(f"Failed to load or create configuration for repository '{repo_name}'.")
                return False

            # Add configuration to ConfigManager
            self.config_manager.add_rice_config(repo_name, config)
            self.logger.debug(f"Configuration for '{repo_name}' added: {config}")
            return True

        except GitOperationError as e:
            self.logger.error(f"Git operation failed: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during repository cloning: {e}")
            return False

    def _normalize_repo_url(self, repository_url: str) -> str:
        """
        Normalizes the repository URL to ensure it uses HTTPS.

        Args:
            repository_url (str): Original repository URL.

        Returns:
            str: Normalized repository URL.
        """
        if repository_url.startswith('git://'):
            repository_url = repository_url.replace('git://', 'https://')
            self.logger.debug(f"Updated repository URL to HTTPS: {repository_url}")

        if not any(repository_url.startswith(prefix) for prefix in ['http://', 'https://']):
            if 'github.com' in repository_url:
                repository_url = f'https://{repository_url}'
                self.logger.debug(f"Updated GitHub repository URL: {repository_url}")
            else:
                self.logger.warning(f"Repository URL '{repository_url}' may be invalid or unsupported.")
        return repository_url

    def _extract_repo_name(self, repository_url: str) -> str:
        """
        Extracts the repository name from its URL.

        Args:
            repository_url (str): Repository URL.

        Returns:
            str: Repository name.
        """
        repo_name = Path(repository_url.rstrip('.git')).name
        self.logger.debug(f"Extracted repository name: {repo_name}")
        return repo_name

    def _load_or_create_repo_config(self, repo_name: str, repository_url: str, local_dir: Path) -> Optional[Dict[str, Any]]:
        """
        Loads the repository configuration if it exists, otherwise creates a default one.

        Args:
            repo_name (str): Name of the repository.
            repository_url (str): URL of the repository.
            local_dir (Path): Local directory of the cloned repository.

        Returns:
            Optional[Dict[str, Any]]: Repository configuration dictionary or None if failed.
        """
        try:
            config_file = local_dir / "rice.json"
            if config_file.exists():
                with config_file.open('r', encoding='utf-8') as f:
                    repo_config = json.load(f)
                    self.logger.debug(f"Loaded existing configuration from {config_file}")
            else:
                self.logger.info(f"No configuration file found in {local_dir}. Creating default configuration.")
                repo_config = self._create_default_repo_config(repository_url, local_dir)
                with config_file.open('w', encoding='utf-8') as f:
                    json.dump(repo_config, f, indent=4)
                    self.logger.debug(f"Default configuration written to {config_file}")

            return repo_config

        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in {config_file}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to load or create repository configuration: {e}")
            return None

    def _create_default_repo_config(self, repository_url: str, local_dir: Path) -> Dict[str, Any]:
        """
        Creates a default repository configuration based on standard directories.

        Args:
            repository_url (str): URL of the repository.
            local_dir (Path): Local directory of the repository.

        Returns:
            Dict[str, Any]: Default repository configuration.
        """
        timestamp = create_timestamp()
        config = {
            'repository_url': repository_url,
            'local_directory': str(local_dir),
            'profiles': {
                'default': {
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
            },
            'active_profile': 'default',
            'applied': False,
            'timestamp': timestamp,
            'nix_config': False
        }
        self.logger.debug(f"Created default configuration: {config}")
        return config

    def apply_dotfiles(
        self,
        repository_name: str,
        stow_options: Optional[List[str]] = None,
        package_manager: Optional[PackageManagerInterface] = None,
        target_packages: Optional[List[str]] = None,
        overwrite_symlink: bool = False,
        custom_paths: Optional[Dict[str, str]] = None,
        ignore_rules: bool = False,
        template_context: Dict[str, Any] = {},
        discover_templates: bool = False,
        custom_scripts: Optional[List[str]] = None
    ) -> bool:
        """
        Applies dotfiles from a repository using GNU Stow.
        """
        try:
            # 1. Get rice configuration
            rice_config = self.config_manager.get_rice_config(repository_name)
            if not rice_config:
                self.logger.error(f"No configuration found for repository: {repository_name}")
                return False

            local_dir = Path(rice_config["local_directory"])
            if not local_dir.exists():
                self.logger.error(f"Repository directory not found: {local_dir}")
                return False

            # 2. Create necessary directories
            config_dirs = self._get_standard_config_dirs()

            for dir_path in config_dirs.values():
                dir_path.mkdir(parents=True, exist_ok=True)

            # 3. Load or create repository-specific configuration
            repo_config = self.config_manager.get_repository_config(local_dir)
            if not repo_config:
                self.logger.info(f"No 'rice.json' found for repository '{repository_name}'. Using automatic detection.")
                repo_config = RepositoryConfig(logger=self.logger)

            # 4. Install required packages if any are detected
            if not self._install_required_packages(local_dir, repo_config):
                return False

            # 5. Discover dotfile directories
            dotfile_dirs = self._discover_dotfile_directories(
                local_dir,
                repo_config=repo_config,
                target_packages=target_packages,
                custom_paths=custom_paths,
                ignore_rules=ignore_rules
            )

            if not dotfile_dirs:
                self.logger.error(
                    "No dotfile directories found to apply. "
                    "Please ensure the repository contains dotfiles in standard locations "
                    "(e.g., .config/, .local/, etc.) or create a rice.json configuration file."
                )
                return False

            # 6. Backup existing configurations
            for item_path_str, category in dotfile_dirs.items():
                item_path = Path(item_path_str)
                target_dir = config_dirs.get(category, Path.home())
                target_path = target_dir / item_path.name

                if target_path.exists() or target_path.is_symlink():
                    self._backup_existing_config(target_path)

            # 7. Apply dotfiles using Stow
            stow_opts = list(stow_options) if stow_options else []
            if overwrite_symlink:
                stow_opts.extend(['--adopt', '--no-folding'])

            for item_path_str, category in dotfile_dirs.items():
                item_path = Path(item_path_str)
                target_dir = config_dirs.get(category, Path.home())

                # Create target directory if it doesn't exist
                target_dir.mkdir(parents=True, exist_ok=True)

                # Stow item with target directory
                if not self._stow_item(local_dir, item_path, stow_opts):
                    self.logger.error(f"Failed to stow {item_path}. Aborting.")
                    return False

                # Record the applied item in config
                rice_config.setdefault("dotfile_directories", {})[str(item_path)] = category
                rice_config.setdefault("profiles", {}).setdefault("default", {}).setdefault("configs", []).append({
                    "name": item_path.name,
                    "path": str(target_dir / item_path.name),
                    "type": category,
                    "applied_at": create_timestamp(),
                })

            # 8. Handle templates if requested
            if discover_templates:
                if not self._handle_templates(local_dir, template_context):
                    return False

            # 9. Run custom scripts if provided
            if custom_scripts:
                if not self._run_custom_scripts(local_dir, custom_scripts):
                    return False

            # 10. Update rice config
            self._update_rice_config(repository_name, rice_config)
            return True

        except Exception as e:
            self.logger.error(f"Error applying dotfiles: {str(e)}")
            return False

    def _get_standard_config_dirs(self) -> Dict[str, Path]:
        """
        Returns a dictionary of standard configuration directories.

        Returns:
            Dict[str, Path]: Mapping of directory names to their paths.
        """
        standard_targets = {
            'config': Path.home() / '.config',
            'local': Path.home() / '.local',
            'themes': Path.home() / '.themes',
            'icons': Path.home() / '.icons',
            'wallpapers': Path.home() / '.local/share/wallpapers',
            'fonts': Path.home() / '.local/share/fonts',
            'bin': Path.home() / '.local/bin',
            'scripts': Path.home() / '.local/bin',
        }
        return standard_targets

    def _install_required_packages(self, local_dir: Path, repo_config: RepositoryConfig) -> bool:
        """
        Detects and installs required packages.

        Args:
            local_dir (Path): Directory to analyze.
            repo_config (RepositoryConfig): Repository configuration.

        Returns:
            bool: True if successful, False otherwise.
        """
        required_packages = self._detect_required_packages(local_dir, repo_config)
        if required_packages and (required_packages.get('pacman') or required_packages.get('aur') or required_packages.get('apt')):
            self.logger.info("Installing required packages for the rice configuration...")
            if not self._install_packages(required_packages):
                self.logger.error("Failed to install required packages")
                return False
        return True

    def _handle_templates(self, local_dir: Path, template_context: Dict[str, Any]) -> bool:
        """
        Processes template files if discover_templates is True.

        Args:
            local_dir (Path): Local repository directory.
            template_context (Dict[str, Any]): Context for template rendering.

        Returns:
            bool: True if successful, False otherwise.
        """
        self.logger.info("Processing templates...")
        template_dir = local_dir / "templates"
        target_template_dir = Path.home() / ".config"
        if template_dir.exists():
            if not self.template_handler.render_templates(template_dir, target_template_dir, template_context):
                self.logger.error("Failed to process templates.")
                return False
        else:
            self.logger.warning(f"Template directory '{template_dir}' does not exist.")
        return True

    def _run_custom_scripts(self, local_dir: Path, custom_scripts: List[str]) -> bool:
        """
        Executes custom scripts.

        Args:
            local_dir (Path): Local repository directory.
            custom_scripts (List[str]): List of custom scripts to run.

        Returns:
            bool: True if successful, False otherwise.
        """
        if custom_scripts:
            self.logger.info("Executing custom scripts...")
            if not self.script_runner.run_scripts_by_phase(local_dir, 'custom_scripts', {'custom_scripts': custom_scripts}, env=None):
                self.logger.error("Failed to execute custom scripts.")
                return False
        return True

    def _update_rice_config(self, repository_name: str, rice_config: Dict[str, Any]) -> None:
        """
        Updates the rice configuration in the config manager.

        Args:
            repository_name (str): Name of the repository.
            rice_config (Dict[str, Any]): Updated rice configuration.
        """
        rice_config['applied'] = True
        self.config_manager.add_rice_config(repository_name, rice_config)
        self.logger.info(f"Successfully applied all configurations from {repository_name}")

    def _get_current_rice(self) -> Optional[str]:
        """
        Retrieves the currently applied rice.

        Returns:
            Optional[str]: Name of the current rice if exists, else None.
        """
        try:
            for repo_name, config in self.config_manager.config_data.get('rices', {}).items():
                if config.get('applied', False):
                    self.logger.debug(f"Current rice is: {repo_name}")
                    return repo_name
            self.logger.debug("No current rice found.")
            return None
        except Exception as e:
            self.logger.error(f"Error retrieving current rice: {e}")
            return None

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
                active_profile = self.config_manager.get_active_profile(repo)
                active_marker = "*" if active_profile else " "
                self.logger.info(f"{active_marker} Repository: {repo}")
                for profile_name, profile_info in repo_profiles.get('profiles', {}).items():
                    active = "(Active)" if profile_name == active_profile else ""
                    description = profile_info.get('description', '')
                    self.logger.info(f"    - {profile_name} {active}: {description}")
            return True
        except ConfigurationError as e:
            self.logger.error(f"Configuration error while listing profiles: {e}")
            return False
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
        except ValidationError as e:
            self.logger.error(f"Validation error while creating profile '{profile_name}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create profile '{profile_name}': {e}")
            return False

    def export_configuration(
        self,
        repository_name: str,
        output_file: str,
        include_deps: bool = False,
        include_assets: bool = False
    ) -> bool:
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
        except IOError as e:
            self.logger.error(f"I/O error while exporting configuration: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to export configuration: {e}")
            return False

    def import_configuration(
        self,
        file_path: str,
        new_name: Optional[str] = None,
        skip_deps: bool = False,
        skip_assets: bool = False
    ) -> bool:
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
                required_packages = {'pacman': set(dependencies), 'aur': set()}
                if not self._install_packages(required_packages):
                    self.logger.error("Failed to install dependencies.")
                    return False

            # Import assets if not skipped
            if not skip_assets and assets:
                self.logger.info("Importing assets from imported configuration...")
                # Implement asset import logic here
                for asset in assets:
                    self.logger.info(f"Imported asset: {asset}")
                    # Placeholder for actual implementation

            self.logger.info(f"Configuration imported successfully as '{repository_name}'.")
            return True
        except FileNotFoundError as e:
            self.logger.error(f"Import file not found: {e}")
            return False
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in import file: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to import configuration: {e}")
            return False

    def _backup_existing_config(self, target_path: Path) -> Optional[Path]:
        """
        Backs up an existing configuration file or directory.

        Args:
            target_path (Path): Path to the existing config.

        Returns:
            Optional[Path]: Path to the backup if created, else None.
        """
        if target_path.exists() or target_path.is_symlink():
            backup_path = target_path.with_suffix(f'.bak.{create_timestamp()}')
            try:
                if target_path.is_symlink():
                    target_path.unlink()
                    self.logger.info(f"Removed existing symlink: {target_path}")
                else:
                    shutil.move(str(target_path), str(backup_path))
                    self.logger.info(f"Backed up existing config to {backup_path}")
                return backup_path
            except Exception as e:
                self.logger.error(f"Failed to backup {target_path}: {e}")
                raise FileOperationError(f"Failed to backup {target_path}: {e}")
        return None

    def _stow_item(self, local_dir: Path, item_path: Path, stow_options: List[str]) -> bool:
        """
        Applies a single item using GNU Stow.

        Args:
            local_dir (Path): Base directory containing the dotfiles.
            item_path (Path): Path to the item to stow, relative to local_dir.
            stow_options (List[str]): Additional options for stow.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Ensure paths are absolute
            local_dir = local_dir.resolve()
            item_path = (local_dir / item_path).resolve()

            if not item_path.exists():
                self.logger.error(f"Item path does not exist: {item_path}")
                return False

            # Standard XDG and dotfile directories with their target paths
            standard_targets = self._get_standard_config_dirs()

            # Determine target directory based on item path
            target_dir = None
            for dir_name, target in standard_targets.items():
                if dir_name in item_path.parts:
                    target_dir = target
                    break

            # Default to home directory if no specific target found
            if not target_dir:
                target_dir = Path.home()

            # Create target directory if it doesn't exist
            target_dir.mkdir(parents=True, exist_ok=True)

            # Prepare stow command
            stow_cmd = ['stow']
            stow_cmd.extend(stow_options)
            stow_cmd.extend([
                '--dir', str(local_dir),
                '--target', str(target_dir),
                '--verbose=3',  # Maximum verbosity for debugging
                str(item_path.relative_to(local_dir))
            ])

            self.logger.info(f"Stowing {item_path.name} to {target_dir}")
            self.logger.debug(f"Running stow command: {' '.join(stow_cmd)}")

            # Run stow
            result = subprocess.run(
                stow_cmd,
                capture_output=True,
                text=True,
                check=False  # Don't raise exception, we'll handle errors
            )

            if result.returncode != 0:
                self.logger.error(f"Stow failed with return code {result.returncode}")
                self.logger.error(f"Stow stderr: {result.stderr}")
                return False

            self.logger.debug(f"Stow stdout: {result.stdout}")
            self.logger.info(f"Successfully stowed {item_path.name} to {target_dir}")
            return True

        except Exception as e:
            self.logger.error(f"Error in _stow_item: {str(e)}")
            return False

    def _discover_dotfile_directories(
        self,
        local_dir: Path,
        repo_config: Optional[RepositoryConfig] = None,
        target_packages: Optional[List[str]] = None,
        custom_paths: Optional[Dict[str, str]] = None,
        ignore_rules: bool = False
    ) -> Dict[str, str]:
        """
        Discovers dotfile directories recursively.
        Prioritizes standard XDG and dotfile directories (.config, .local, etc).

        Args:
            local_dir (Path): Local repository directory.
            repo_config (Optional[RepositoryConfig]): Repository configuration.
            target_packages (Optional[List[str]]): List of target packages.
            custom_paths (Optional[Dict[str, str]]): Custom paths to include.
            ignore_rules (bool): Whether to ignore predefined rules.

        Returns:
            Dict[str, str]: Mapping of dotfile directories to their categories.
        """
        self.logger.info(f"Discovering dotfiles in {local_dir}")
        dotfile_dirs = {}

        # Standard XDG and dotfile directories with their categories
        standard_dirs = {
            '.config': 'config',
            '.local': 'local',
            '.themes': 'themes',
            '.icons': 'icons',
            '.walls': 'wallpapers',
            '.wallpapers': 'wallpapers',
            '.fonts': 'fonts',
            '.bin': 'bin',
            '.scripts': 'scripts',
        }

        # First, check for standard directories
        for dir_name, category in standard_dirs.items():
            dir_path = local_dir / dir_name
            if dir_path.exists() and dir_path.is_dir():
                dotfile_dirs[dir_name] = category
                self.logger.info(f"Found standard dotfile directory: {dir_name} ({category})")

        # If no standard directories found, try repository config
        if not dotfile_dirs and repo_config:
            config_dirs = repo_config.get_dotfile_directories()
            categories = repo_config.get_dotfile_categories()

            for dir_path in config_dirs:
                dir_path = Path(dir_path)
                if (local_dir / dir_path).exists():
                    category = categories.get(str(dir_path), "config")
                    dotfile_dirs[str(dir_path)] = category
                    self.logger.debug(f"Found dotfile from config: {dir_path} of type {category}")

        # Add custom paths if provided
        if custom_paths:
            for path, category in custom_paths.items():
                path = Path(path)
                if (local_dir / path).exists():
                    dotfile_dirs[str(path)] = category
                    self.logger.debug(f"Added custom path: {path} of type {category}")

        # If still no dotfiles found, use DotfileAnalyzer as fallback
        if not dotfile_dirs:
            root_node = self.dotfile_analyzer.build_tree(local_dir)

            def traverse(node: DotfileNode) -> None:
                if node.is_dotfile:
                    # Get the target path where this dotfile should be installed
                    if node.target_path:
                        relative_path = node.path.relative_to(local_dir)
                        dotfile_dirs[str(relative_path)] = node.config_type or "config"
                        self.logger.debug(f"Found dotfile: {relative_path} of type {node.config_type}")

                for child in node.children:
                    traverse(child)

            traverse(root_node)

        if not dotfile_dirs:
            self.logger.warning(
                "No dotfiles found through automatic detection or configuration. "
                "Please ensure the repository contains dotfiles in standard locations "
                "(e.g., .config/, .local/, etc.) or create a rice.json configuration file."
            )

        # Log all discovered directories
        for path, category in dotfile_dirs.items():
            self.logger.info(f"Will apply dotfile: {path} as {category}")

        return dotfile_dirs

    def _get_standard_config_dirs(self) -> Dict[str, Path]:
        """
        Returns a dictionary of standard configuration directories.

        Returns:
            Dict[str, Path]: Mapping of directory names to their paths.
        """
        return {
            'config': Path.home() / '.config',
            'local': Path.home() / '.local',
            'themes': Path.home() / '.themes',
            'icons': Path.home() / '.icons',
            'wallpapers': Path.home() / '.local/share/wallpapers',
            'fonts': Path.home() / '.local/share/fonts',
            'bin': Path.home() / '.local/bin',
            'scripts': Path.home() / '.local/bin',
        }

    def _handle_templates(self, local_dir: Path, template_context: Dict[str, Any]) -> bool:
        """
        Processes template files if discover_templates is True.

        Args:
            local_dir (Path): Local repository directory.
            template_context (Dict[str, Any]): Context for template rendering.

        Returns:
            bool: True if successful, False otherwise.
        """
        self.logger.info("Processing templates...")
        template_dir = local_dir / "templates"
        target_template_dir = Path.home() / ".config"
        if template_dir.exists():
            if not self.template_handler.render_templates(template_dir, target_template_dir, template_context):
                self.logger.error("Failed to process templates.")
                return False
        else:
            self.logger.warning(f"Template directory '{template_dir}' does not exist.")
        return True

    def _install_packages(self, packages: Dict[str, Set[str]]) -> bool:
        """
        Install detected packages using appropriate package managers.

        Args:
            packages (Dict[str, Set[str]]): Packages to install categorized by manager.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            # Update package databases if necessary
            if 'pacman' in packages and isinstance(self.package_manager.manager, PacmanPackageManager):
                pacman_packages = list(packages['pacman'])
                if pacman_packages:
                    self.logger.info(f"Installing pacman packages: {', '.join(pacman_packages)}")
                    if not self.package_manager.install_packages(pacman_packages):
                        self.logger.error("Failed to install pacman packages.")
                        return False

            if 'aur' in packages and self.aur_helper_manager:
                aur_packages = list(packages['aur'])
                if aur_packages:
                    self.logger.info(f"Installing AUR packages: {', '.join(aur_packages)}")
                    if not self.aur_helper_manager.install_packages(aur_packages):
                        self.logger.error("Failed to install AUR packages.")
                        return False

            if 'apt' in packages and isinstance(self.package_manager.manager, AptPackageManager):
                apt_packages = list(packages['apt'])
                if apt_packages:
                    self.logger.info(f"Installing apt packages: {', '.join(apt_packages)}")
                    if not self.package_manager.install_packages(apt_packages):
                        self.logger.error("Failed to install apt packages.")
                        return False

            return True
        except PackageManagerError as e:
            self.logger.error(f"Package manager error during installation: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error installing packages: {e}")
            return False

    def _create_snapshot(self, name: str, description: str = "") -> bool:
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
        except IOError as e:
            self.logger.error(f"I/O error while creating snapshot '{name}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to create snapshot '{name}': {e}")
            return False

    def _get_installed_packages(self) -> Dict[str, List[str]]:
        """
        Retrieves the list of installed packages for different package managers.

        Returns:
            Dict[str, List[str]]: Installed packages categorized by package manager.
        """
        installed_packages: Dict[str, List[str]] = {}
        try:
            # Example for Pacman
            if isinstance(self.package_manager.manager, PacmanPackageManager):
                result = subprocess.run(['pacman', '-Qq'], capture_output=True, text=True)
                if result.returncode == 0:
                    installed_packages['pacman'] = result.stdout.strip().split('\n')

            # Example for AUR helper
            if self.aur_helper_manager and shutil.which(self.aur_helper_manager.helper_name):
                result = subprocess.run([self.aur_helper_manager.helper_name, '-Qq'], capture_output=True, text=True)
                if result.returncode == 0:
                    installed_packages['aur'] = result.stdout.strip().split('\n')

            # Example for Apt
            if isinstance(self.package_manager.manager, AptPackageManager):
                result = subprocess.run(['dpkg-query', '-f', '${binary:Package}\n', '-W'], capture_output=True, text=True)
                if result.returncode == 0:
                    installed_packages['apt'] = result.stdout.strip().split('\n')

            # Add other package managers as needed
            return installed_packages
        except subprocess.SubprocessError as e:
            self.logger.warning(f"Subprocess error while retrieving installed packages: {e}")
            return installed_packages
        except Exception as e:
            self.logger.warning(f"Failed to retrieve installed packages: {e}")
            return installed_packages

    def create_snapshot(self, name: str, description: str = "") -> bool:
        """
        Creates a system snapshot with the given name and description.

        Args:
            name (str): Name of the snapshot.
            description (str): Description of the snapshot.

        Returns:
            bool: True if successful, False otherwise.
        """
        return self._create_snapshot(name, description)

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
            metadata_file = snapshot_path / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                self.config_manager.config_data = metadata.get('configurations', {})
                self.config_manager.save_config()
                self.logger.info(f"Configurations restored from snapshot '{name}'.")

            self.logger.info(f"Snapshot '{name}' restored successfully.")
            return True
        except IOError as e:
            self.logger.error(f"I/O error while restoring snapshot '{name}': {e}")
            return False
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
        except shutil.Error as e:
            self.logger.error(f"Shutil error while deleting snapshot '{name}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to delete snapshot '{name}': {e}")
            return False

    def manage_dotfiles(
        self,
        profile_name: str,
        target_files: List[str],
        dry_run: bool = False
    ) -> bool:
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
                for file in target_files:
                    self.logger.info(f"[Dry Run] Would manage: {file}")
                return True

            # Implement actual management logic
            for file in target_files:
                self.logger.info(f"Managing dotfile: {file}")
                target_path = Path.home() / file
                if target_path.exists() or target_path.is_symlink():
                    self._backup_existing_config(target_path)

                # Assuming copying from managed directory
                source_path = self.managed_rices_dir / current_repo / file
                if source_path.exists():
                    try:
                        if source_path.is_dir():
                            shutil.copytree(source_path, target_path, dirs_exist_ok=True)
                        else:
                            shutil.copy2(source_path, target_path)
                        self.logger.info(f"Copied {source_path} to {target_path}")
                    except Exception as e:
                        self.logger.error(f"Failed to copy {source_path} to {target_path}: {e}")
                        return False
                else:
                    self.logger.warning(f"Source file {source_path} does not exist. Skipping.")

            self.logger.info(f"Successfully managed dotfiles for profile '{profile_name}'.")
            return True
        except ConfigurationError as e:
            self.logger.error(f"Configuration error while managing dotfiles: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to manage dotfiles: {e}")
            return False

    def _transactional_operation(self, operation_name: str):
        """
        Context manager for transactional operations with rollback.

        Args:
            operation_name (str): Name of the operation.

        Yields:
            None
        """
        try:
            yield
        except Exception as e:
            self.logger.error(f"An error occurred during {operation_name}: {e}")
            # Placeholder for rollback logic
            # Example: self.rollback(operation_name)
            raise RollbackError(f"Rollback due to error in {operation_name}: {e}")

    def _backup_existing_configs(self, config_home: Path, dotfile_dirs: Dict[str, str]) -> None:
        """
        Backs up existing configuration files/directories before applying.

        Args:
            config_home (Path): Home directory for configurations.
            dotfile_dirs (Dict[str, str]): Mapping of dotfile directories to categories.
        """
        for item_name, item_category in dotfile_dirs.items():
            if item_category == 'config':
                item_path = Path(item_name)
                target_path = config_home / item_path.name
                self._backup_existing_config(target_path)



    # Additional methods (e.g., _handle_templates, _run_custom_scripts, etc.) remain unchanged or are optimized above.

    # Implement other methods as needed, ensuring they follow similar improvements.

