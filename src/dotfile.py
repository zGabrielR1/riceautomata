import subprocess
from .utils import setup_logger, sanitize_path, create_timestamp, confirm_action
from .config import ConfigManager
from .script import ScriptRunner
from .backup import BackupManager
from .exceptions import (
    RiceAutomataError, ConfigurationError, GitOperationError,
    FileOperationError, ValidationError, RollbackError, TemplateRenderingError, ScriptExecutionError
)
import sys
import os
import re
import json
import shutil
from typing import Dict, List, Any, Optional, Tuple
from jinja2 import Environment, FileSystemLoader
import toml
import yaml
import asyncio
import shutil
from .file_operations import FileOperations
import traceback
from contextlib import contextmanager
import datetime
import glob

from .utils import setup_logger, sanitize_path, create_timestamp, confirm_action
from .config import ConfigManager
from .script import ScriptRunner
from .backup import BackupManager
from .dotfile_analyzer import DotfileAnalyzer
from .template_handler import TemplateHandler

logger = setup_logger()

class ValidationError(Exception):
    pass

class ConfigurationError(Exception):
    pass

class DotfileNode:
    def __init__(self, path: str, is_dotfile: bool = False):
        self.path = path
        self.name = os.path.basename(path)
        self.is_dotfile = is_dotfile
        self.children = []
        self.dependencies = set()
        self.is_nix_config = False

class DotfileTree:
    def __init__(self):
        self.root = None
        self.dotfile_patterns = [
            r'^\.',  # Traditional dot files
            r'^dot_',  # Chezmoi style
            r'\.conf$',  # Configuration files
            r'\.toml$', r'\.yaml$', r'\.yml$', r'\.json$',
            r'rc$',  # rc files
            r'config$',  # config files
            r'\.nix$',  # Nix configuration files
            r'flake\.nix$',  # Nix flakes
            r'\.ini$',  # INI configs
            r'\.ron$',  # RON configs
            r'\.css$',  # Style files
            r'\.scss$',  # SASS files
            r'\.js$',  # JavaScript configs (like for ags)
            r'\.ts$',  # TypeScript configs
            r'zshrc$',  # Zsh config files
            r'bashrc$',  # Bash config files
            r'\.zsh$',  # Zsh plugin files
            r'\.sh$'   # Shell scripts
        ]
        self.known_config_dirs = {
            # Shell and terminal
            'oh-my-zsh', 'zsh', 'bash', 'fish', 'tmux', 'kitty', 'alacritty', 'wezterm',
            # Window managers and desktop
            'i3', 'hypr', 'sway', 'awesome', 'polybar', 'waybar',
            # System utilities
            'nvim', 'neofetch', 'rofi', 'dunst', 'picom', 'flameshot',
            # GTK and theming
            'gtk-3.0', 'gtk-4.0', 'themes', 'icons',
            # Additional tools
            'fontconfig', 'swaylock', 'hyprlock', 'hypridle'
        }
        self.asset_dirs = {
            'wallpapers', 'backgrounds', 'icons', 'themes', 'fonts', 'assets',
            'styles', 'shaders', 'images', 'readme_ressources', 'stickers'
        }
        self.shell_config_dirs = {
            'plugins', 'themes', 'custom', 'lib', 'tools', 'templates'
        }

    def build_tree(self, root_path: str) -> DotfileNode:
        """Build a tree structure of the dotfiles directory with enhanced detection"""
        self.root = DotfileNode(root_path)
        self._build_tree_recursive(self.root)
        return self.root

    def _is_dotfile(self, path: str) -> bool:
        """Enhanced check if a file or directory is a dotfile/config"""
        name = os.path.basename(path)
        parent = os.path.basename(os.path.dirname(path))
        
        # Check if it's a known config directory
        if name in self.known_config_dirs:
            return True
            
        # Check if it's an asset directory
        if name.lower() in self.asset_dirs:
            return True
            
        # Check if it's part of shell configuration
        if parent in self.known_config_dirs and name in self.shell_config_dirs:
            return True
            
        # Check if parent is .config or config
        if parent == '.config' or parent == 'config':
            return True
            
        # Check against dotfile patterns
        for pattern in self.dotfile_patterns:
            if re.search(pattern, name):
                return True
                
        return False

    def _build_tree_recursive(self, node: DotfileNode):
        """Recursively build the tree structure with improved detection"""
        try:
            if not os.path.exists(node.path):
                return

            # Mark as dotfile if it matches patterns
            if self._is_dotfile(node.path):
                node.is_dotfile = True

            # Check for Nix configurations
            if os.path.basename(node.path).endswith('.nix'):
                node.is_nix_config = True

            if os.path.isdir(node.path):
                for item in os.listdir(node.path):
                    item_path = os.path.join(node.path, item)
                    child = DotfileNode(item_path)
                    node.children.append(child)
                    self._build_tree_recursive(child)

        except Exception as e:
            logger.error(f"Error building tree at {node.path}: {e}")

    def parse_json_dependencies(self, file):
        data = json.load(file)
        dependencies = set()
        if isinstance(data, dict):
            if 'dependencies' in data:
                dependencies.update(data['dependencies'].keys())
            if 'devDependencies' in data:
                dependencies.update(data['devDependencies'].keys())
        return dependencies

    def parse_toml_dependencies(self, file):
        data = toml.load(file)
        dependencies = set()
        if isinstance(data, dict):
            for section in ['dependencies', 'build-dependencies', 'dev-dependencies']:
                if section in data and isinstance(data[section], dict):
                    dependencies.update(data[section].keys())
        return dependencies

    def parse_yaml_dependencies(self, file):
        data = yaml.safe_load(file)
        dependencies = set()
        if isinstance(data, dict):
            for key in ['dependencies', 'requires']:
                if key in data and isinstance(data[key], list):
                    dependencies.update(data[key])
                elif key in data and isinstance(data[key], dict):
                    dependencies.update(data[key].keys())
        return dependencies

    def find_dependencies(self, node: DotfileNode):
        """Find dependencies in configuration files with format-specific parsing."""
        if os.path.isfile(node.path):
            _, ext = os.path.splitext(node.path)
            try:
                with open(node.path, 'r', encoding='utf-8') as f:
                    if ext == '.json':
                        node.dependencies.update(self.parse_json_dependencies(f))
                    elif ext in ['.toml']:
                        node.dependencies.update(self.parse_toml_dependencies(f))
                    elif ext in ['.yaml', '.yml']:
                        node.dependencies.update(self.parse_yaml_dependencies(f))
                    else:
                        content = f.read().lower()
                        if any(indicator in content for indicator in ['requires', 'depends', 'dependencies']):
                            packages = set(re.findall(r'[\w-]+(?:>=?[\d.]+)?', content))
                            node.dependencies.update(packages)
            except Exception as e:
                logger.warning(f"Could not analyze dependencies in {node.path}: {e}")

        for child in node.children:
            self.find_dependencies(child)

    def _categorize_dotfile_directory(self, path: str) -> str:
        """Categorize the type of dotfile directory"""
        name = os.path.basename(path).lower()
        
        if name in self.asset_dirs:
            return "asset"
        if name in {'bin', 'scripts', 'scriptdata'}:
            return "script"
        if name in {'themes', 'styles', 'gtk-3.0', 'gtk-4.0'}:
            return "theme"
        if name in self.known_config_dirs:
            return "config"
        if 'nix' in name or name.endswith('.nix'):
            return "nix"
            
        return "other"

class DotfileManager:

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.config_manager = ConfigManager()
        self.backup_manager = BackupManager()
        self.logger = setup_logger(verbose)
        self.managed_rices_dir = sanitize_path("~/.config/managed-rices")
        self._ensure_managed_dir()
        self.rules_config = self._load_rules()
        self.dependency_map = self._load_dependency_map()
        self.nix_installed = False
        self.script_runner = ScriptRunner(verbose)
        self.analyzer = DotfileAnalyzer(self.rules_config, verbose)
        self.template_handler = TemplateHandler(verbose)
        self.file_ops = FileOperations(self.backup_manager, verbose)
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.dotfile_tree = DotfileTree()

    @contextmanager
    def _error_context(self, phase):
        """Context manager for handling errors in specific phases."""
        try:
            yield
        except Exception as e:
            self.logger.error(f"An error occurred during {phase}: {str(e)}")
            raise

    def _ensure_managed_dir(self):
        """Create managed rices directory if it does not exist."""
        try:
            os.makedirs(self.managed_rices_dir, exist_ok=True)
        except Exception as e:
            raise FileOperationError(f"Failed to create managed directory: {e}")

    def _retry_operation(self, operation, *args, **kwargs):
        """Retry an operation with exponential backoff."""
        for attempt in range(self.max_retries):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
                wait_time = self.retry_delay * (2 ** attempt)
                self.logger.warning(f"Operation failed, retrying in {wait_time} seconds... Error: {e}")
                time.sleep(wait_time)

    def clone_repository(self, repository_url: str) -> bool:
        """Clones a git repository with retry and rollback support."""
        backup_id = None
        try:
            if repository_url.startswith('git://'):
                repository_url = repository_url.replace('git://', 'https://')

            repo_name = os.path.basename(repository_url).replace(".git", "")
            local_dir = os.path.join(self.managed_rices_dir, repo_name)

            if os.path.exists(local_dir):
                self.logger.warning(f"Repository already exists at {local_dir}")
                return False

            backup_id = self.backup_manager.start_operation_backup("clone_repository")

            self.logger.info(f"Cloning repository from {repository_url} into {local_dir}")

            def clone_op():
                try:
                    result = self.script_runner._run_command([
                        "git", "clone",
                        "--progress",
                        "--recursive",
                        repository_url,
                        local_dir
                    ])
                    return True  # If command succeeds, return True
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.decode('utf-8').lower() if e.stderr else ""
                    if "authentication failed" in error_msg:
                        raise GitOperationError("Authentication failed.")
                    elif "could not resolve host" in error_msg:
                        raise GitOperationError("Could not resolve host.")
                    elif "permission denied" in error_msg:
                        raise GitOperationError("Permission denied.")
                    else:
                        raise
                    return False

            clone_result = self._retry_operation(clone_op)

            if clone_result and os.path.exists(os.path.join(local_dir, ".git")):
                self.logger.info(f"Repository cloned successfully to: {local_dir}")
                timestamp = create_timestamp()
                config = {
                    'repository_url': repository_url,
                    'local_directory': local_dir,
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
                self.config_manager.add_rice_config(repo_name, config)
                return True
            else:
                self.logger.error("Failed to clone repository or repository is empty.")
                if os.path.exists(local_dir):
                    import shutil
                    shutil.rmtree(local_dir)
                return False
        except GitOperationError as e:
            self.logger.error(f"Git operation failed: {str(e)}")
            if backup_id:
                try:
                    self.backup_manager.rollback_operation(backup_id)
                except Exception as rollback_error:
                    self.logger.error(f"Failed to rollback after clone error: {rollback_error}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error during repository cloning: {str(e)}")
            if backup_id:
                try:
                    self.backup_manager.rollback_operation(backup_id)
                except Exception as rollback_error:
                    self.logger.error(f"Failed to rollback after clone error: {rollback_error}")
            return False

    def _load_rules(self):
        """Loads the rules to discover the dotfile directories"""
        try:
            rules_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "rules.json")
            with open(rules_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in rules config: {e}")
        except FileNotFoundError:
            return {}
        except Exception as e:
            raise ConfigurationError(f"Failed to load rules config: {e}")

    def _load_dependency_map(self):
        """Loads the dependency map to discover dependencies"""
        try:
            dependency_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "dependency_map.json")
            with open(dependency_map_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in dependency map: {e}")
        except FileNotFoundError:
            return {}
        except Exception as e:
            raise ConfigurationError(f"Failed to load dependency map: {e}")

    def _validate_dotfile_directory(self, dir_path: str) -> bool:
        """Validate if a directory contains dotfiles or rice configurations."""
        if not os.path.exists(dir_path):
            self.logger.error(f"Directory does not exist: {dir_path}")
            return False

        # Check for known config directories at root level
        for item in os.listdir(dir_path):
            if item in self.dotfile_tree.known_config_dirs or item.startswith('.'):
                self.logger.info(f"Found config directory: {item}")
                return True

        # If no direct matches, check subdirectories
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                for subitem in os.listdir(item_path):
                    if (subitem in self.dotfile_tree.known_config_dirs or 
                        subitem.startswith('.') or 
                        any(re.search(pattern, subitem) for pattern in self.dotfile_tree.dotfile_patterns)):
                        self.logger.info(f"Found config in subdirectory: {subitem}")
                        return True

        self.logger.warning(f"No configuration directories found in: {dir_path}")
        return False

    def _discover_dotfile_directories(self, local_dir: str, target_packages=None, custom_paths=None, ignore_rules=False) -> Dict[str, str]:
        """Discover dotfile directories with enhanced detection."""
        dotfile_dirs = {}
        
        if not os.path.exists(local_dir):
            self.logger.error(f"Local directory does not exist: {local_dir}")
            return dotfile_dirs

        # First check if this is a direct dotfile directory
        if self._validate_dotfile_directory(local_dir):
            dotfile_dirs[local_dir] = "config"
            return dotfile_dirs

        # Then check for rice variants
        variants = []
        for item in os.listdir(local_dir):
            item_path = os.path.join(local_dir, item)
            if os.path.isdir(item_path):
                if self._validate_dotfile_directory(item_path):
                    variants.append(item)

        if variants:
            if len(variants) > 1 and not target_packages:
                chosen_variant = self._prompt_multiple_rices(variants)
                if not chosen_variant:
                    return dotfile_dirs
                variants = [chosen_variant]

            for variant in variants:
                variant_path = os.path.join(local_dir, variant)
                dotfile_dirs[variant_path] = "config"

        return dotfile_dirs

    def _safe_file_operation(self, operation_name: str, operation, *args, **kwargs):
        """Delegate to FileOperations."""
        return self.file_ops.safe_file_operation(operation_name, operation, *args, **kwargs)

    def _copy_dotfiles(self, source_dir: str, target_dir: str, backup_id: Optional[str] = None) -> None:
        """Delegate to FileOperations."""
        return self.file_ops.copy_files(source_dir, target_dir, backup_id)

    def _remove_dotfiles(self, target_dir: str) -> None:
        """Delegate to FileOperations."""
        return self.file_ops.remove_files(target_dir)

    def _discover_scripts(self, local_dir: str, custom_scripts = None) -> Dict[str, List[str]]:
        """Delegate to FileOperations."""
        return self.file_ops.discover_scripts(local_dir, custom_scripts)

    def _install_fonts(self, local_dir, package_manager):
      def _is_font_file(filename):
        font_extensions = [".ttf", ".otf", ".woff", ".woff2"]
        return any(filename.lower().endswith(ext) for ext in font_extensions)

      fonts_dir = os.path.join(local_dir, "fonts")
      if not os.path.exists(fonts_dir) or not os.path.isdir(fonts_dir):
         return True
      for item in os.listdir(fonts_dir):
        item_path = os.path.join(fonts_dir, item)
        if os.path.isfile(item_path) and _is_font_file(item):
          font_name = os.path.splitext(item)[0]
          if not package_manager.is_installed(font_name):
            self.logger.info(f"Installing font {font_name}")
            if not package_manager.install_package(f"auto:{font_name}"):
             self.logger.info(f"{font_name} not found as package, trying to install manually.")
             if not package_manager._install_font_manually(item_path):
               self.logger.error(f"Failed to install font: {font_name}")
               return False
          else:
            self.logger.debug(f"Font: {font_name} is already installed")
      return True

    def _apply_nix_config(self, nix_path: str):
        """Apply Nix configuration"""
        try:
            if os.path.isfile(nix_path) and nix_path.endswith('flake.nix'):
                # Handle flake.nix
                target_dir = os.path.expanduser("~/.config/nixos")
                os.makedirs(target_dir, exist_ok=True)
                self._create_symlink(nix_path, os.path.join(target_dir, "flake.nix"))
                
                # Copy flake.lock if it exists
                lock_path = os.path.join(os.path.dirname(nix_path), "flake.lock")
                if os.path.exists(lock_path):
                    self._create_symlink(lock_path, os.path.join(target_dir, "flake.lock"))
            else:
                # Handle other Nix configs
                target_dir = os.path.expanduser("~/.config/nixpkgs")
                os.makedirs(target_dir, exist_ok=True)
                
                if os.path.isdir(nix_path):
                    for root, _, files in os.walk(nix_path):
                        for file in files:
                            if file.endswith('.nix'):
                                src_file = os.path.join(root, file)
                                rel_path = os.path.relpath(root, nix_path)
                                target = os.path.join(target_dir, rel_path)
                                os.makedirs(target, exist_ok=True)
                                self._create_symlink(src_file, os.path.join(target, file))
                else:
                    self._create_symlink(nix_path, os.path.join(target_dir, os.path.basename(nix_path)))
                
            self.logger.info(f"Applied Nix configuration from {nix_path}")
        except Exception as e:
            self.logger.error(f"Failed to apply Nix configuration: {e}")
            raise FileOperationError(f"Failed to apply Nix configuration: {e}")

    def _apply_directory_with_stow(self, local_dir, directory, stow_options=[], overwrite_destination=None):
        if overwrite_destination:
            target_path = os.path.expanduser(overwrite_destination)
            self._overwrite_symlinks(target_path, local_dir, directory)
            return True

        stow_command = ["stow", "-v"]
        stow_command.extend(stow_options)
        stow_command.append(os.path.basename(directory))
        stow_result = self.script_runner._run_command(stow_command, check=False, cwd=local_dir)
        if not stow_result or stow_result.returncode != 0:
            self.logger.error(f"Failed to stow directory: {directory}. Stow output: {stow_result.stderr}")
            return False
        return True

    def _apply_config_directory(self, local_dir, directory, stow_options = [], overwrite_destination=None):
      if overwrite_destination and overwrite_destination.startswith("~"):
           stow_dir = os.path.join(os.path.expanduser(overwrite_destination), os.path.basename(directory))
      else:
         stow_dir = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
      if os.path.basename(directory) != ".config" and not os.path.exists(stow_dir):
          os.makedirs(stow_dir, exist_ok = True)
      return self._apply_directory_with_stow(local_dir, directory, stow_options, overwrite_destination)

    def _apply_cache_directory(self, local_dir, directory, stow_options = [], overwrite_destination = None):
        return self._apply_directory_with_stow(local_dir, directory, stow_options, overwrite_destination)

    def _apply_local_directory(self, local_dir, directory, stow_options = [], overwrite_destination = None):
       return self._apply_directory_with_stow(local_dir, directory, stow_options, overwrite_destination)

    def _apply_other_directory(self, local_dir, directory):
       dir_path = os.path.join(local_dir, directory)
       target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
       if os.path.exists(target_path):
         self.logger.warning(f"Path {target_path} already exists, skipping...")
         return False
       try:
        shutil.copytree(dir_path, target_path)
        self.logger.info(f"Copied directory {dir_path} to {target_path}")
       except NotADirectoryError:
         try:
           shutil.copy2(dir_path, target_path)
           self.logger.info(f"Copied file {dir_path} to {target_path}")
         except Exception as e:
            self.logger.error(f"Error copying file {dir_path} to {target_path}: {e}")
            return False
       except Exception as e:
          self.logger.error(f"Error copying directory {dir_path} to {target_path}: {e}")
          return False
       return True

    def _apply_extra_directory(self, local_dir, directory, target_base = "/"):
       dir_path = os.path.join(local_dir, directory)
       target_path = os.path.join(target_base, os.path.basename(directory))

       if not os.path.exists(target_base):
         os.makedirs(target_base, exist_ok=True)

       try:
           if os.path.exists(target_path):
               self.logger.warning(f"Path {target_path} already exists, skipping...")
               return False
           shutil.copytree(dir_path, target_path, dirs_exist_ok=True)
           self.logger.info(f"Copied directory {dir_path} to {target_path}")
       except NotADirectoryError:
           try:
               shutil.copy2(dir_path, target_path)
               self.logger.info(f"Copied file {dir_path} to {target_path}")
           except Exception as e:
               self.logger.error(f"Error copying file {dir_path} to {target_path}: {e}")
               return False
       except Exception as e:
           self.logger.error(f"Error copying directory {dir_path} to {target_path}: {e}")
           return False
       return True

    def _apply_custom_extras_directories(self, local_dir, custom_extras_paths):
      for path, target in custom_extras_paths.items():
          full_path = os.path.join(local_dir, path)
          if os.path.exists(full_path):
            self._apply_extra_directory(local_dir, path, target)
          else:
            self.logger.warning(f"Custom extras directory not found: {full_path}")

    def plates(self, local_dir, dotfile_dirs, context):
        for directory, category in dotfile_dirs.items():
           dir_path = os.path.join(local_dir, directory)
           if not os.path.exists(dir_path):
                continue
           for item in os.listdir(dir_path):
              item_path = os.path.join(dir_path, item)
              if os.path.isfile(item_path):
                 if item.endswith(".tpl"):
                    template_content = self._process_template_file(item_path, context)
                    if template_content:
                         output_path = item_path.replace(".tpl", "")
                         try:
                           with open(output_path, 'w') as f:
                            f.write(template_content)
                            self.logger.debug(f"Template {item_path} processed and saved in {output_path}")
                         except Exception as e:
                           self.logger.error(f"Error saving the processed template: {output_path}. Error: {e}")
        return True

    def apply_dotfiles(self, repository_name, stow_options=[], package_manager=None, target_packages=None, overwrite_symlink=None, custom_paths=None, ignore_rules=False, template_context={}, discover_templates=False, custom_scripts=None):
        """Applies dotfiles from a repository using GNU Stow."""
        with self._error_context("applying dotfiles"):
            # Initialize rice config
            rice_config = {
                'name': repository_name,
                'local_directory': repository_name if os.path.isabs(repository_name) else os.path.abspath(repository_name),
                'dotfile_directories': {},
                'script_config': {},
                'applied': False
            }
            self.config_manager.add_rice_config(repository_name, rice_config)

            local_dir = rice_config['local_directory']
            config_home = os.path.expanduser("~/.config")
            os.makedirs(config_home, exist_ok=True)

            # Discover and apply all configs
            for item in os.listdir(local_dir):
                item_path = os.path.join(local_dir, item)
                if os.path.isdir(item_path):
                    target_path = os.path.join(config_home, item)
                    
                    # Backup existing config if needed
                    if os.path.exists(target_path) or os.path.islink(target_path):
                        backup_path = f"{target_path}.bak.{int(time.time())}"
                        if os.path.islink(target_path):
                            os.unlink(target_path)
                        else:
                            shutil.move(target_path, backup_path)
                            self.logger.info(f"Backed up existing config to {backup_path}")
                    
                    # Create symlink
                    os.symlink(item_path, target_path, target_is_directory=True)
                    self.logger.info(f"Applied {item} to ~/.config/")
                    rice_config['dotfile_directories'][item] = 'config'

            # Update rice config
            rice_config['applied'] = True
            self.config_manager.add_rice_config(repository_name, rice_config)
            self.logger.info(f"Successfully applied all configurations from {repository_name}")
            return True

    async def _install_package_async(self, package: str, package_manager, local_dir: str) -> bool:
        """Install a single package asynchronously."""
        try:
            self.logger.info(f"Installing package: {package}")
            return await package_manager.install_async(package, local_dir=local_dir)
        except Exception as e:
            self.logger.error(f"Failed to install package {package}: {e}")
            return False

    async def _install_missing_packages(self, packages: List[str], package_manager, local_dir: str) -> bool:
        """Install missing packages in parallel."""
        if not packages:
            return True

        tasks = []
        for package in packages:
            if not package_manager.is_installed(package):
                task = self._install_package_async(package, package_manager, local_dir)
                tasks.append(task)

        if not tasks:
            return True

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success = all(isinstance(r, bool) and r for r in results)
        
        if not success:
            self.logger.error("Some packages failed to install")
            return False
            
        return True

    def _check_installed_packages(self, packages):
        """Checks if the specified packages are installed."""
        installed = []
        for package in packages:
            if self.package_manager.is_installed(package):
                installed.append(package)
        return installed

    def _install_missing_packages(self, packages):
        """Installs any missing packages from the list."""
        missing_packages = [pkg for pkg in packages if pkg not in self._check_installed_packages(packages)]
        if missing_packages:
            self.logger.info(f"Installing missing packages: {', '.join(missing_packages)}")
            return self.package_manager.install(missing_packages, None)
        return True

    def _install_packages(self, packages):
        """Install a list of packages using the appropriate package manager."""
        if not packages:
            self.logger.debug("No packages to install")
            return True

        try:
            # Check if packages are already installed
            missing_packages = [pkg for pkg in packages if not self._check_installed_packages([pkg])]
            
            if not missing_packages:
                self.logger.info("All packages are already installed")
                return True

            if not confirm_action(f"The following packages will be installed: {', '.join(missing_packages)}"):
                return False

            # Install missing packages
            return self._install_missing_packages(missing_packages)
        except Exception as e:
            self.logger.error(f"Failed to install packages: {e}")
            return False

    def _read_package_list(self, file):
        """Read a package list from a file.
        
        Supports various formats:
        - Plain text (one package per line)
        - JSON (array of package names)
        - YAML/TOML (list of package names)
        """
        try:
            file_ext = os.path.splitext(file)[1].lower()
            with open(file, 'r') as f:
                if file_ext == '.json':
                    packages = json.load(f)
                elif file_ext in ['.yaml', '.yml']:
                    packages = yaml.safe_load(f)
                elif file_ext == '.toml':
                    packages = toml.load(f)
                else:
                    # Plain text format, one package per line
                    packages = [line.strip() for line in f if line.strip() and not line.startswith('#')]

            # Ensure the result is a list of strings
            if isinstance(packages, list):
                return [str(pkg) for pkg in packages if pkg]
            elif isinstance(packages, dict) and 'packages' in packages:
                return [str(pkg) for pkg in packages['packages'] if pkg]
            else:
                self.logger.error(f"Invalid package list format in {file}")
                return []
        except Exception as e:
            self.logger.error(f"Error reading package list from {file}: {e}")
            return []

    def _process_assets(self, directory):
        """Process assets in a given directory.
        
        This includes:
        - Copying assets to appropriate locations
        - Setting correct permissions
        - Creating necessary directories
        """
        if not os.path.exists(directory):
            self.logger.warning(f"Asset directory does not exist: {directory}")
            return False

        try:
            target_dir = os.path.expanduser("~/.local/share")
            
            # Create target directory if it doesn't exist
            os.makedirs(target_dir, exist_ok=True)

            # Copy assets while preserving permissions
            for root, _, files in os.walk(directory):
                for file in files:
                    src_path = os.path.join(root, file)
                    # Calculate relative path from the asset directory
                    rel_path = os.path.relpath(src_path, directory)
                    dst_path = os.path.join(target_dir, rel_path)
                    
                    # Create parent directories if they don't exist
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                    
                    # Copy the file while preserving metadata
                    shutil.copy2(src_path, dst_path)
                    
                    # Set appropriate permissions (readable by user and group)
                    os.chmod(dst_path, 0o644)

            self.logger.info(f"Successfully processed assets from {directory}")
            return True
        except Exception as e:
            self.logger.error(f"Error processing assets from {directory}: {e}")
            return False

    def _manage_profiles(self, profiles):
        """Manage different profiles or environments.
        
        Profiles can include:
        - Different package sets
        - Different configurations
        - Environment-specific settings
        """
        if not profiles:
            self.logger.debug("No profiles to manage")
            return True

        try:
            for profile_name, profile_data in profiles.items():
                self.logger.info(f"Processing profile: {profile_name}")
                
                # Create profile in config manager
                self.config_manager.create_profile(profile_data.get('repository', ''), profile_name)
                
                # Process profile-specific packages
                if 'packages' in profile_data:
                    self._install_packages(profile_data['packages'])
                
                # Process profile-specific configurations
                if 'config' in profile_data:
                    config_dir = os.path.expanduser(profile_data['config'].get('target_dir', '~/.config'))
                    os.makedirs(config_dir, exist_ok=True)
                    
                    for config_file, config_content in profile_data['config'].get('files', {}).items():
                        target_path = os.path.join(config_dir, config_file)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        
                        with open(target_path, 'w') as f:
                            if isinstance(config_content, dict):
                                json.dump(config_content, f, indent=2)
                            else:
                                f.write(str(config_content))
            
                # Process profile-specific assets
                if 'assets' in profile_data:
                    self._process_assets(profile_data['assets'])

            self.logger.info("Successfully managed all profiles")
            return True
        except Exception as e:
            self.logger.error(f"Error managing profiles: {e}")
            return False

    def manage_dotfiles(self, repository_name, stow_options = [], package_manager = None, target_packages = None, custom_paths = None, ignore_rules = False, template_context = {}, discover_templates=False, custom_scripts=None):
         """Manages the dotfiles, uninstalling the previous rice, and applying the new one."""
         current_rice = None
         for key, value in self.config_manager.config_data.get('rices', {}).items():
            if value.get('applied', False):
              current_rice = key
              break

         if current_rice:
           if not self._uninstall_dotfiles(current_rice):
             return False

         if not self.apply_dotfiles(repository_name, stow_options, package_manager, target_packages, custom_paths = custom_paths, ignore_rules = ignore_rules, template_context = template_context):
           return False
         return True

    def _uninstall_dotfiles(self, repository_name):
      """Uninstalls all the dotfiles, from a previous rice."""
      try:
          rice_config = self.config_manager.get_rice_config(repository_name)
          if not rice_config:
              self.logger.error(f"No config found for repository: {repository_name}")
              return False
          local_dir = rice_config['local_directory']
          dotfile_dirs = rice_config['dotfile_directories']
          unlinked_all = True

          # Execute pre uninstall scripts
          env = os.environ.copy()
          env['RICE_DIRECTORY'] = local_dir
          with self._error_context('pre_uninstall'):
              if not self.script_runner.run_scripts_by_phase(local_dir, 'pre_uninstall', rice_config.get('script_config'), env):
                  return False

          for directory, category in dotfile_dirs.items():
            if category == "config":
              target_path = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
              if not os.path.exists(target_path):
                 self.logger.warning(f"Could not find config directory: {target_path}. Skipping...")
                 continue
              stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
              stow_result = self.script_runner._run_command(stow_command, check=False, cwd=local_dir)
              if not stow_result or stow_result.returncode != 0:
                  unlinked_all = False
                  self.logger.error(f"Failed to unstow config: {directory} from {target_path}. Stow output: {stow_result.stderr}")
            elif category == "cache":
              stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
              stow_result = self.script_runner._run_command(stow_command, check = False, cwd=local_dir)
              if not stow_result or stow_result.returncode != 0:
                 unlinked_all = False
                 self.logger.error(f"Failed to unstow cache: {directory}. Stow output: {stow_result.stderr}")
            elif category == "local":
               stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
               stow_result = self.script_runner._run_command(stow_command, check=False, cwd=local_dir)
               if not stow_result or stow_result.returncode != 0:
                  unlinked_all = False
                  self.logger.error(f"Failed to unstow local files: {directory}. Stow output: {stow_result.stderr}")
            else: #Other directories (wallpapers, scripts, etc).
                target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
                if os.path.exists(target_path):
                   try:
                     shutil.rmtree(target_path)
                     self.logger.debug(f"Removed directory: {target_path}")
                   except NotADirectoryError:
                     try:
                      os.remove(target_path)
                      self.logger.debug(f"Removed file: {target_path}")
                     except Exception as e:
                       self.logger.error(f"Error removing file: {target_path}. Error: {e}")
                   except Exception as e:
                       self.logger.error(f"Error removing directory {target_path}: {e}")
                else:
                  self.logger.warning(f"Could not find other directory: {target_path}. Skipping...")

          # Uninstall Extras
          extras_dir = os.path.join(local_dir, "Extras")
          if os.path.exists(extras_dir) and os.path.isdir(extras_dir):
              for item in os.listdir(extras_dir):
                item_path = os.path.join(extras_dir, item)
                target_path = os.path.join("/", item)
                if os.path.exists(target_path):
                    try:
                      shutil.rmtree(target_path)
                      self.logger.debug(f"Removed extra directory: {target_path}")
                    except NotADirectoryError:
                      try:
                        os.remove(target_path)
                        self.logger.debug(f"Removed extra file: {target_path}")
                      except Exception as e:
                        self.logger.error(f"Error removing file from Extras: {target_path}. Error: {e}")
                    except Exception as e:
                       self.logger.error(f"Error removing extra directory: {target_path}. Error: {e}")
                else:
                   self.logger.warning(f"Could not find extra directory: {target_path}. Skipping...")

          # Execute post uninstall scripts
          with self._error_context('post_uninstall'):
              if not self.script_runner.run_scripts_by_phase(local_dir, 'post_uninstall', rice_config.get('script_config'), env):
                  return False

          if unlinked_all:
                self.logger.info(f"Successfully uninstalled the dotfiles for: {repository_name}")
                rice_config['applied'] = False
                self.config_manager.add_rice_config(repository_name, rice_config)
                return True
          else:
            self.logger.error("Failed to unlink all the symlinks.")
            return False
      except Exception as e:
        self.logger.error(f"An error ocurred while uninstalling dotfiles: {e}")
        return False

    def create_backup(self, repository_name, backup_name):
       """Creates a backup of the applied configuration."""
       try:
            rice_config = self.config_manager.get_rice_config(repository_name)
            if not rice_config or not rice_config.get('applied', False):
                self.logger.error(f"No rice applied for {repository_name}. Can't create backup.")
                return False
            backup_dir = os.path.join(rice_config['local_directory'], "backups", backup_name)
            if os.path.exists(backup_dir):
              self.logger.error(f"Backup with the name {backup_name} already exists. Aborting.")
              return False

            os.makedirs(backup_dir, exist_ok=True)

            for directory, category in rice_config['dotfile_directories'].items():
              if category == "config":
                target_path = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
                if not os.path.exists(target_path):
                   continue
              elif category == "cache":
                target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory)) #Cache files into home.
                if not os.path.exists(target_path):
                   continue
              elif category == "local":
                target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory)) # local files into home.
                if not os.path.exists(target_path):
                    continue
              else:
                target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
                if not os.path.exists(target_path):
                    continue
              backup_target = os.path.join(backup_dir, os.path.basename(directory))
              try:
                shutil.copytree(target_path, backup_target)
                self.logger.debug(f"Copied {target_path} to {backup_target}")
              except NotADirectoryError:
                   try:
                       shutil.copy2(target_path, backup_target)
                       self.logger.debug(f"Copied file {target_path} to {backup_target}")
                   except Exception as e:
                       self.logger.error(f"Error copying file {target_path}: {e}")
              except Exception as e:
                    self.logger.error(f"Error copying directory {target_path}: {e}")
              rice_config['config_backup_path'] = backup_dir
              self.config_manager.add_rice_config(repository_name, rice_config)

            self.logger.info(f"Backup created successfully at {backup_dir}")
            return True
       except Exception as e:
        self.logger.error(f"An error occurred while creating backup: {e}")
        return False

    def _prompt_multiple_rices(self, rice_names):
        """Prompts the user to choose which rice to install from multiple options."""
        self.logger.warning(f"Multiple rices detected: {', '.join(rice_names)}. Please choose which one you would like to install.")
        while True:
           prompt = f"Which rice do you want to install? ({', '.join(rice_names)}, N to cancel): "
           choice = input(prompt).strip()
           if choice in rice_names:
            return choice
           elif choice.lower() == 'n':
             return None
           else:
            self.logger.warning("Invalid choice, please type the exact name of a rice, or type N to cancel")

    def _execute_scripts(self, scripts):
        """Execute a list of scripts in order."""
        for script in scripts:
            self._run_script(script)

    def _run_script(self, script):
        """Run a single script file."""
        try:
            self.logger.info(f"Executing script: {script}")
            result = subprocess.run([script], check=True, shell=True, capture_output=True, text=True)
            self.logger.debug(f"Script output: {result.stdout}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Script {script} failed with error: {e.stderr}")
            raise ScriptExecutionError(f"Script {script} failed.")

    def _process_package_lists(self, package_list_files):
        """Install packages from package list files."""
        for file in package_list_files:
            packages = self._read_package_list(file)
            self._install_packages(packages)

    def _handle_assets(self, asset_directories):
        """Handle asset management for directories."""
        for directory in asset_directories:
            self._process_assets(directory)

    def _apply_complex_structure(self, structure):
        """Apply configurations from complex directory structures."""
        
        if not os.path.exists(structure):
            self.logger.error(f"Structure path does not exist: {structure}")
            return False

        if os.path.isfile(structure):
            self.logger.error(f"Structure path is a file, not a directory: {structure}")
            return False
        
        top_level_dirs = [item for item in os.listdir(structure) if os.path.isdir(os.path.join(structure, item))]

        if not top_level_dirs:
            self.logger.warning(f"No subdirectories found in: {structure}")
            return False
        
        if len(top_level_dirs) > 1:
             chosen_rice = self._prompt_multiple_rices(top_level_dirs)
             if not chosen_rice:
                 self.logger.warning("Installation aborted.")
                 return False
             structure = os.path.join(structure, chosen_rice)

        if len(top_level_dirs) == 1:
            structure = os.path.join(structure, top_level_dirs[0])
            
        def apply_recursive(base_dir, target_base="~"):
          for item in os.listdir(base_dir):
                full_path = os.path.join(base_dir, item)
                target_path = os.path.join(os.path.expanduser(target_base), item)
                
                if os.path.isdir(full_path):
                     if item == ".config":
                         self._apply_config_directory(base_dir, item)
                     elif item == ".cache":
                         self._apply_cache_directory(base_dir, item)
                     elif item == ".local":
                         self._apply_local_directory(base_dir, item)
                     elif item == "wallpapers" or item == "wallpaper" or item == "backgrounds":
                        self._apply_other_directory(base_dir, item) #Handle wallpaper folder
                     elif item == "Extras": #Handle extra folder
                       for extra_item in os.listdir(full_path):
                           extra_item_path = os.path.join(full_path, extra_item)
                           if os.path.isdir(extra_item_path):
                              self._apply_extra_directory(full_path, extra_item, "/")
                           else:
                              self._apply_extra_directory(full_path, extra_item, "/") #Handle single files in extras.
                     else:
                         apply_recursive(full_path, target_path)
                elif os.path.isfile(full_path):
                    try:
                        shutil.copy2(full_path, target_path)
                        self.logger.info(f"Copied file {full_path} to {target_path}")
                    except Exception as e:
                        self.logger.error(f"Error copying file {full_path} to {target_path}: {e}")

        apply_recursive(structure)
        return True
    
    def _enhance_error_handling(self):
        """Improve error handling and logging."""
        # Implement enhanced error handling
        pass

    def _manage_profiles(self, profiles):
        """Manage different profiles or environments."""
        # Implement profile management logic
        pass

    def analyze_rice_directory(self, rice_path: str) -> Dict[str, Any]:
        """Analyze a rice directory and return its structure and requirements"""
        tree = DotfileTree()
        root = tree.build_tree(rice_path)
        tree.find_dependencies(root)

        is_nix_config = False
        def traverse(node):
            nonlocal is_nix_config
            if node.is_nix_config:
                is_nix_config = True
                return True
            for child in node.children:
                if traverse(child):
                    return True
            return False
        
        traverse(root)

        return {
            'is_nix_config': is_nix_config,
            'dependencies': list(root.dependencies)
        }

    def detect_rice_variants(self, rice_path: str) -> List[str]:
        """Detect if the rice directory contains multiple rice variants"""
        variants = []

        # Check common patterns for rice variants
        for item in os.listdir(rice_path):
            full_path = os.path.join(rice_path, item)
            if os.path.isdir(full_path):
                # Check if directory contains dotfiles
                analysis = self.analyze_rice_directory(full_path)
                if analysis['dotfiles']:
                    variants.append(item)

        return variants

    def install_nix_if_needed(self, rice_analysis: Dict[str, Any]) -> bool:
        """Install Nix if the rice requires it and it's not installed"""
        if not rice_analysis['has_nix']:
            return True

        try:
            subprocess.run(['nix', '--version'], capture_output=True, check=True)
            return True
        except FileNotFoundError:
            self.logger.info("Nix is required, and not installed. Installing Nix...")
            try:
                # Placeholder for Nix installation logic (platform-dependent)
                if sys.platform == "linux":
                    command = "sh <(curl -L https://nixos.org/nix/install)"
                    result = subprocess.run(command, shell=True, capture_output=True, text=True)
                    if result.returncode == 0:
                        self.logger.info("Nix installed successfully. Please restart your shell or source the nix-profile/etc/profile.d/nix.sh.")
                        return True
                    else:
                        self.logger.error(f"Nix installation failed: {result.stderr}")
                        return False
                else:
                    self.logger.warning(f"Automatic Nix installation is not implemented for {sys.platform}. Please install it manually.")
                    return False
            except Exception as e:
                self.logger.error(f"Failed to install Nix: {e}")
                return False

    def apply_rice_automated(self, rice_path: str) -> bool:
        """Fully automated rice installation process with enhanced detection and validation"""
        try:
            # 1. System compatibility check
            self.logger.info("Checking system compatibility...")
            compatibility = self._check_system_compatibility()
            
            # Validate minimum requirements
            if not self._validate_minimum_requirements(compatibility):
                return False
            
            # 2. Analyze rice structure and dependencies
            self.logger.info("Analyzing rice configuration...")
            analyzer = DotfileAnalyzer()
            rice_analysis = analyzer.analyze_rice_directory(rice_path)
            
            # 3. Detect and collect all dependencies
            self.logger.info("Detecting dependencies...")
            all_deps = {
                'system': set(),  # System-level dependencies
                'packages': set(),  # Package manager dependencies
                'fonts': set(),  # Font dependencies
                'services': set(),  # System services
                'optional': set()  # Optional enhancements
            }
            
            for config_file in rice_analysis['config_files']:
                deps = analyzer.analyze_dependencies(config_file)
                for key in all_deps:
                    all_deps[key].update(deps.get(key, []))
            
            # 4. Validate dependencies against system compatibility
            self.logger.info("Validating dependencies...")
            if not self._validate_dependencies(all_deps, compatibility):
                return False
            
            # 5. Create backup of existing configuration
            self.logger.info("Creating backup of existing configuration...")
            if not self._backup_existing_config(rice_path):
                return False
            
            # 6. Install system dependencies first
            if all_deps['system']:
                self.logger.info("Installing system dependencies...")
                if not self._install_system_dependencies(list(all_deps['system']), compatibility):
                    self._rollback_changes()
                    return False
            
            # 7. Install package dependencies
            if all_deps['packages']:
                self.logger.info("Installing package dependencies...")
                if not self._install_package_dependencies(list(all_deps['packages']), compatibility):
                    self._rollback_changes()
                    return False
            
            # 8. Install and configure fonts
            if all_deps['fonts']:
                self.logger.info("Setting up fonts...")
                if not self._setup_fonts(list(all_deps['fonts']), compatibility):
                    self._rollback_changes()
                    return False
            
            # 9. Determine and apply installation strategy
            self.logger.info("Applying rice configuration...")
            if compatibility['nix_support'] and rice_analysis['has_nix_config']:
                if not self._apply_nix_config(rice_path, compatibility['package_manager']):
                    self._rollback_changes()
                    return False
            elif compatibility['stow_available']:
                if not self._apply_stow_configuration(rice_path, rice_analysis):
                    self._rollback_changes()
                    return False
            else:
                if not self._apply_manual_configuration(rice_path, rice_analysis):
                    self._rollback_changes()
                    return False
            
            # 10. Setup and enable required services
            if all_deps['services']:
                self.logger.info("Setting up system services...")
                if not self._setup_services(list(all_deps['services']), compatibility):
                    self._rollback_changes()
                    return False
            
            # 11. Apply post-installation configuration
            if rice_analysis['post_install_scripts']:
                self.logger.info("Running post-installation scripts...")
                if not self._execute_scripts(rice_analysis['post_install_scripts']):
                    self._rollback_changes()
                    return False
            
            # 12. Verify installation
            self.logger.info("Verifying installation...")
            if not self._verify_installation(rice_path, rice_analysis, all_deps):
                self._rollback_changes()
                return False
            
            self.logger.info("Rice installation completed successfully!")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install rice: {str(e)}")
            self._rollback_changes()
            return False
            
    def _validate_minimum_requirements(self, compatibility: Dict[str, Any]) -> bool:
        """Validate minimum system requirements"""
        # Check for display server
        if not (compatibility['xorg_present'] or compatibility['wayland_present']):
            self.logger.error("No display server detected. X11 or Wayland is required.")
            return False
            
        # Check for package manager
        if not compatibility['package_manager']:
            self.logger.error("No supported package manager found.")
            return False
            
        # Check for minimum disk space (1GB)
        if compatibility['available_disk_space'] and compatibility['available_disk_space'] < 1_000_000_000:
            self.logger.error("Insufficient disk space. At least 1GB is required.")
            return False
            
        return True
        
    def _validate_dependencies(self, dependencies: Dict[str, set], compatibility: Dict[str, Any]) -> bool:
        """Validate dependencies against system compatibility"""
        # Check if Nix is required but not available
        if any('nix' in dep.lower() for dep in dependencies['system']) and not compatibility['nix_support']:
            self.logger.error("Rice requires Nix but Nix is not available on the system.")
            return False
            
        # Check if systemd services are required but systemd is not available
        if dependencies['services'] and not compatibility['systemd_available']:
            self.logger.error("Rice requires systemd services but systemd is not available.")
            return False
            
        # Check desktop environment compatibility
        de_deps = {dep for dep in dependencies['packages'] if any(de in dep.lower() for de in ['gnome', 'kde', 'xfce', 'i3', 'awesome'])}
        if de_deps and not compatibility['desktop_environment']:
            self.logger.warning("Rice includes desktop environment components but no desktop environment detected.")
            
        return True
        
    def _backup_existing_config(self, rice_path: str) -> bool:
        """Create backup of existing configuration"""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = os.path.expanduser(f"~/.config/riceautomata/backups/{timestamp}")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Backup existing config files
            config_dirs = ['.config', '.local/share', '.themes', '.icons']
            for dir_name in config_dirs:
                src_dir = os.path.expanduser(f"~/{dir_name}")
                if os.path.exists(src_dir):
                    dst_dir = os.path.join(backup_dir, dir_name)
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            
            return True
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False
            
    def _verify_installation(self, rice_path: str, rice_analysis: Dict[str, Any], dependencies: Dict[str, set]) -> bool:
        """Verify the rice installation"""
        # Check if all required files are in place
        for config_file in rice_analysis['config_files']:
            target_path = os.path.expanduser(f"~/.config/{os.path.basename(config_file)}")
            if not os.path.exists(target_path):
                self.logger.error(f"Configuration file not installed: {target_path}")
                return False
        
        # Verify package installations
        for package in dependencies['packages']:
            if not self._check_package_installed(package):
                self.logger.error(f"Package not properly installed: {package}")
                return False
        
        # Verify services
        for service in dependencies['services']:
            if not self._check_service_active(service):
                self.logger.error(f"Service not properly enabled: {service}")
                return False
        
        return True
    
    def _detect_package_dependencies(self, config_file: str) -> Dict[str, list]:
        """Enhanced detection of package dependencies from various config file formats"""
        dependencies = {
            'system': set(),  # System-level dependencies
            'packages': set(),  # Package manager dependencies
            'fonts': set(),  # Font dependencies
            'services': set(),  # System services
            'optional': set()  # Optional enhancements
        }
        
        if not os.path.exists(config_file):
            return {k: list(v) for k, v in dependencies.items()}
            
        try:
            with open(config_file, 'r') as f:
                content = f.read()
                
            file_ext = os.path.splitext(config_file)[1].lower()
            
            # Parse based on file type
            if file_ext in ['.json', '.jsonc']:
                self._parse_json_dependencies(content, dependencies)
            elif file_ext in ['.yaml', '.yml']:
                self._parse_yaml_dependencies(content, dependencies)
            elif file_ext == '.toml':
                self._parse_toml_dependencies(content, dependencies)
            elif file_ext in ['.conf', '.ini']:
                self._parse_ini_dependencies(content, dependencies)
            elif 'pkgbuild' in os.path.basename(config_file).lower():
                self._parse_pkgbuild_dependencies(content, dependencies)
            elif file_ext == '.nix':
                self._parse_nix_dependencies(content, dependencies)
            
            # Analyze shell scripts for common package usage patterns
            if file_ext in ['.sh', '.bash', '.zsh']:
                self._analyze_shell_dependencies(content, dependencies)
            
            # Check for common desktop environment dependencies
            self._detect_de_dependencies(content, dependencies)
            
            # Check for font dependencies
            self._detect_font_dependencies(content, dependencies)
            
            # Check for service dependencies
            self._detect_service_dependencies(content, dependencies)
            
        except Exception as e:
            self.logger.warning(f"Error parsing dependencies in {config_file}: {e}")
            
        return {k: list(v) for k, v in dependencies.items()}
        
    def _parse_json_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Parse JSON-format dependency declarations"""
        try:
            data = json.loads(content)
            # Check package.json style dependencies
            if isinstance(data, dict):
                for key in ['dependencies', 'devDependencies', 'peerDependencies']:
                    if key in data and isinstance(data[key], dict):
                        dependencies['packages'].update(data[key].keys())
                        
                # Check for system requirements
                if 'system' in data:
                    dependencies['system'].update(data.get('system', []))
                    
                # Check for optional enhancements
                if 'optional' in data:
                    dependencies['optional'].update(data.get('optional', []))
        except:
            pass
            
    def _parse_yaml_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Parse YAML-format dependency declarations"""
        try:
            import yaml
            data = yaml.safe_load(content)
            if isinstance(data, dict):
                # Common YAML dependency keys
                dep_keys = ['dependencies', 'requires', 'packages', 'system']
                for key in dep_keys:
                    if key in data:
                        if isinstance(data[key], list):
                            dependencies['packages'].update(data[key])
                        elif isinstance(data[key], dict):
                            dependencies['packages'].update(data[key].keys())
        except:
            pass
            
    def _parse_toml_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Parse TOML-format dependency declarations"""
        try:
            import toml
            data = toml.loads(content)
            if isinstance(data, dict):
                # Check for dependencies table
                if 'dependencies' in data:
                    dependencies['packages'].update(data['dependencies'].keys())
                # Check for build-dependencies
                if 'build-dependencies' in data:
                    dependencies['packages'].update(data['build-dependencies'].keys())
        except:
            pass
                
    def _analyze_shell_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Analyze shell scripts for package usage patterns"""
        # Common package manager commands
        pm_patterns = {
            'apt': r'apt-get\s+install\s+([^\n]+)',
            'pacman': r'pacman\s+-S\s+([^\n]+)',
            'dnf': r'dnf\s+install\s+([^\n]+)',
            'yum': r'yum\s+install\s+([^\n]+)',
            'brew': r'brew\s+install\s+([^\n]+)'
        }
        
        for pattern in pm_patterns.values():
            matches = re.finditer(pattern, content)
            for match in matches:
                packages = match.group(1).split()
                dependencies['packages'].update(packages)
                
    def _detect_de_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Detect desktop environment related dependencies"""
        de_patterns = {
            'i3': ['i3-wm', 'i3status', 'i3blocks', 'i3lock'],
            'awesome': ['awesome', 'awesome-extra'],
            'xfce': ['xfce4', 'xfce4-goodies'],
            'kde': ['plasma-desktop', 'kde-standard'],
            'gnome': ['gnome-shell', 'gnome-session']
        }
        
        for de, deps in de_patterns.items():
            if de.lower() in content.lower():
                dependencies['packages'].update(deps)
                
    def _detect_font_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Detect font dependencies"""
        font_patterns = [
            r'font-family:\s*[\'"]([^\'"]+)[\'"]',
            r'fonts-\w+',
            r'ttf-\w+',
            r'otf-\w+'
        ]
        
        for pattern in font_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                dependencies['fonts'].add(match.group(1))
                
    def _detect_service_dependencies(self, content: str, dependencies: Dict[str, set]):
        """Detect system service dependencies"""
        service_patterns = [
            r'systemctl\s+(?:start|enable)\s+(\w+)',
            r'service\s+(\w+)\s+start',
            r'initctl\s+start\s+(\w+)'
        ]
        
        for pattern in service_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                dependencies['services'].add(match.group(1))