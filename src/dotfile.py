import subprocess
from src.utils import setup_logger, sanitize_path, create_timestamp, confirm_action
from src.config import ConfigManager
from src.script import ScriptRunner
from src.backup import BackupManager
from src.exceptions import (
    RiceAutomataError, ConfigurationError, GitOperationError,
    FileOperationError, ValidationError, RollbackError, TemplateRenderingError, ScriptExecutionError
)
import sys
import os
import re
import json
from jinja2 import Environment, FileSystemLoader
from typing import Dict, List, Optional, Any
import time
import toml
import yaml
import asyncio
import shutil

logger = setup_logger()

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
            r'\.ts$'  # TypeScript configs
        ]
        self.known_config_dirs = {
            'nvim', 'alacritty', 'hypr', 'waybar', 'sway', 'i3', 'polybar', 'kitty',
            'rofi', 'dunst', 'picom', 'gtk-3.0', 'gtk-4.0', 'zsh', 'bash', 'fish',
            'tmux', 'neofetch', 'fastfetch', 'eww', 'wezterm', 'ags', 'anyrun',
            'foot', 'fuzzel', 'mpv', 'qt5ct', 'wlogout', 'fontconfig', 'swaylock',
            'hyprlock', 'hypridle'
        }
        self.asset_dirs = {
            'wallpapers', 'backgrounds', 'icons', 'themes', 'fonts', 'assets',
            'styles', 'shaders', 'images'
        }

    def build_tree(self, root_path: str) -> DotfileNode:
        """Build a tree structure of the dotfiles directory"""
        root = DotfileNode(root_path)
        self.root = root
        self._build_tree_recursive(root)
        return root

    def _is_dotfile(self, path: str) -> bool:
        """Enhanced check if a file or directory is a dotfile/config"""
        name = os.path.basename(path)
        
        # Check if it's a known config directory
        if os.path.isdir(path):
            if name.lower() in self.known_config_dirs:
                return True
            if name.lower() in self.asset_dirs:
                return True
            # Check for nested config structures (like .config/something)
            if os.path.basename(os.path.dirname(path)) == '.config':
                return True

        # Check against patterns
        for pattern in self.dotfile_patterns:
            if re.search(pattern, name):
                return True

        return False

    def _build_tree_recursive(self, node: DotfileNode):
        """Recursively build the tree structure"""
        try:
            items = os.listdir(node.path)
            for item in items:
                full_path = os.path.join(node.path, item)
                is_dotfile = self._is_dotfile(full_path)
                child_node = DotfileNode(full_path, is_dotfile)

                # Check for Nix configurations
                if item.endswith('.nix') or item == 'flake.nix':
                    child_node.is_nix_config = True

                if os.path.isdir(full_path):
                    self._build_tree_recursive(child_node)

                node.children.append(child_node)
        except (PermissionError, OSError) as e:
            logger.warning(f"Could not access {node.path}: {e}")

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
        self.template_env = Environment(loader=FileSystemLoader('/'))
        self.max_retries = 3
        self.retry_delay = 2  # seconds
        self.dotfile_tree = DotfileTree()

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
                    return result
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.lower()
                    if "authentication failed" in error_msg:
                        raise GitOperationError("Authentication failed.")
                    elif "could not resolve host" in error_msg:
                        raise GitOperationError("Could not resolve host.")
                    elif "permission denied" in error_msg:
                        raise GitOperationError("Permission denied.")
                    else:
                        raise
            clone_result = self._retry_operation(clone_op)

            if clone_result:
                self.logger.info(f"Repository cloned successfully to: {local_dir}")
                if not os.path.exists(os.path.join(local_dir, ".git")):
                    raise GitOperationError("Repository appears to be empty or not properly cloned")

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
                self.logger.error("Failed to clone repository.")
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

    def _validate_dotfile_directory(self, dir_path: str) -> None:
        """Validates a dotfile directory."""
        if not os.path.exists(dir_path):
            raise ValidationError(f"Directory does not exist: {dir_path}")
        if not os.path.isdir(dir_path):
            raise ValidationError(f"Path is not a directory: {dir_path}")
        if not os.access(dir_path, os.R_OK):
            raise ValidationError(f"Directory is not readable: {dir_path}")

    def _safe_file_operation(self, operation_name: str, operation, *args, **kwargs):
        """Executes a file operation with backup and rollback support."""
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

    def _score_dir_name(self, dir_name):
        score = 0
        for rule in self.rules_config.get('rules', []):
            if rule.get('regex'):
                try:
                    if re.search(rule['regex'], dir_name):
                        score += 3
                except Exception as e:
                    self.logger.error(f"Error with rule regex: {rule['regex']}. Check your rules.json file. Error: {e}")
            elif dir_name == rule.get('name'):
                score += 3

        de_wm_names = [
            "nvim", "zsh", "hypr", "waybar", "alacritty", "dunst", "rofi", "sway",
            "gtk-3.0", "fish", "kitty", "i3", "bspwm", "awesome", "polybar", "picom",
            "qtile", "xmonad", "openbox", "dwm", "eww", "wezterm", "foot", "ags"
        ]
        if dir_name in de_wm_names:
            score += 2
        return score

    def _score_dotfile_content(self, dir_path):
        score = 0
        dotfile_extensions = [".conf", ".toml", ".yaml", ".yml", ".json", ".config",
                            ".sh", ".bash", ".zsh", ".fish", ".lua", ".vim", ".el", ".ini", ".ron", ".scss", ".js", ".xml"]
        config_keywords = [
            "nvim", "hyprland", "waybar", "zsh", "alacritty", "dunst", "rofi",
            "sway", "gtk", "fish", "kitty", "config", "theme", "colorscheme",
            "keybind", "workspace", "window", "border", "font", "opacity", "ags"
        ]

        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isfile(item_path):
                if any(item.endswith(ext) for ext in dotfile_extensions):
                    score += 1
                try:
                    with open(item_path, 'r', errors='ignore') as file:
                        content = file.read(1024).lower()
                        for keyword in config_keywords:
                            if keyword in content:
                                score += 0.5
                except:
                   pass
        return score

    def _is_likely_dotfile_dir(self, dir_path):
        dir_name = os.path.basename(dir_path)
        name_score = self._score_dir_name(dir_name)
        content_score = self._score_dotfile_content(dir_path)
        return name_score + content_score >= 2

    def _discover_dotfile_directories(self, local_dir, target_packages = None, custom_paths = None, ignore_rules = False):
        dotfile_dirs = {}
        paths_to_check = []

        if custom_paths:
            for path in custom_paths:
                full_path = os.path.join(local_dir, path)
                if os.path.exists(full_path):
                    paths_to_check.append(full_path)
                else:
                    self.logger.warning(f"Could not find custom path: {path}")
        else:
            paths_to_check.append(local_dir)

        for base_path in paths_to_check:
            for item in os.listdir(base_path):
                item_path = os.path.join(base_path, item)
                rel_path = os.path.relpath(item_path, local_dir)
                if os.path.isdir(item_path):
                    if target_packages:
                        if item in target_packages:
                            category = self._categorize_dotfile_directory(item_path)
                            dotfile_dirs[rel_path] = category
                        elif item == ".config":
                            for sub_item in os.listdir(item_path):
                                sub_item_path = os.path.join(item_path, sub_item)
                                if os.path.isdir(sub_item_path) and sub_item in target_packages:
                                    category = self._categorize_dotfile_directory(sub_item_path)
                                    dotfile_dirs[os.path.join(rel_path, sub_item)] = category
                    else:
                        if ignore_rules or self._is_likely_dotfile_dir(item_path):
                            category = self._categorize_dotfile_directory(item_path)
                            dotfile_dirs[rel_path] = category
        return dotfile_dirs

    def _discover_dependencies(self, local_dir, dotfile_dirs):
        dependencies = []
        package_managers = {
            'pacman': ['pkglist.txt', 'packages.txt', 'arch-packages.txt'],
            'apt': ['apt-packages.txt', 'debian-packages.txt'],
            'dnf': ['fedora-packages.txt', 'rpm-packages.txt'],
            'brew': ['brewfile', 'Brewfile'],
            'pip': ['requirements.txt', 'python-packages.txt'],
            'cargo': ['Cargo.toml'],
            'npm': ['package.json']
        }

        for pm, files in package_managers.items():
            for file in files:
                dep_file_path = os.path.join(local_dir, file)
                if os.path.exists(dep_file_path) and os.path.isfile(dep_file_path):
                    try:
                        with open(dep_file_path, 'r') as f:
                            if file == 'package.json':
                                data = json.load(f)
                                deps = data.get('dependencies', {})
                                deps.update(data.get('devDependencies', {}))
                                for pkg in deps.keys():
                                    dependencies.append(f"npm:{pkg}")
                            elif file == 'Cargo.toml':
                                with open(dep_file_path, 'r') as f:
                                    content = f.read()
                                    data = toml.loads(content)
                                    if 'dependencies' in data:
                                        for pkg in data['dependencies'].keys():
                                            dependencies.append(f"cargo:{pkg}")
                            else:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith('#'):
                                        dependencies.append(f"{pm}:{line}")
                    except Exception as e:
                        self.logger.warning(f"Error parsing dependency file {file}: {e}")

        common_deps = {
            'nvim': ['neovim'],
            'zsh': ['zsh'],
            'hypr': ['hyprland'],
            'waybar': ['waybar'],
            'alacritty': ['alacritty'],
            'dunst': ['dunst'],
            'rofi': ['rofi'],
            'sway': ['sway'],
            'fish': ['fish'],
            'kitty': ['kitty'],
            'i3': ['i3-wm'],
            'bspwm': ['bspwm'],
            'polybar': ['polybar'],
            'picom': ['picom'],
            'qtile': ['qtile'],
            'xmonad': ['xmonad'],
            'eww': ['eww-wayland'],
            'ags': ['yarn', 'esbuild', 'sass', 'gtk4'],
            'foot': ['foot'],
            'fuzzel': ['fuzzel']
        }

        for dir_name in dotfile_dirs:
            base_name = os.path.basename(dir_name)
            if base_name in common_deps:
                dependencies.extend(f"auto:{dep}" for dep in common_deps[base_name])

        for dep, packages in self.dependency_map.get('dependencies', {}).items():
            if dep in dotfile_dirs or any(dep in dir for dir in dotfile_dirs):
                dependencies.extend(packages)

        arch_packages_dir = os.path.join(local_dir, "arch-packages")
        if os.path.exists(arch_packages_dir) and os.path.isdir(arch_packages_dir):
            for item in os.listdir(arch_packages_dir):
                item_path = os.path.join(arch_packages_dir, item)
                if os.path.isdir(item_path):
                    dependencies.append(f"aur:{item}")

        custom_deps_file = os.path.join(local_dir, "scriptdata", "dependencies.conf")
        if os.path.exists(custom_deps_file) and os.path.isfile(custom_deps_file):
           try:
              with open(custom_deps_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                       dependencies.append(line)
           except Exception as e:
               self.logger.error(f"Error reading custom dependency file {custom_deps_file}: {e}")

        return list(set(dependencies))

    def _check_nix_config(self, local_dir):
      nix_files = ["flake.nix", "configuration.nix"]
      for file in nix_files:
        if os.path.exists(os.path.join(local_dir, file)):
          return True
      return False

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

    def _overwrite_symlinks(self, target_path, local_dir, directory):
      dir_path = os.path.join(local_dir, directory)
      if not os.path.exists(dir_path):
        self.logger.warning(f"Could not find directory {dir_path} when trying to overwrite")
        return False

      target_dir = os.path.join(target_path, os.path.basename(directory))
      if os.path.exists(target_dir):
        stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
        self.script_runner._run_command(stow_command, check=False, cwd=local_dir)

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

    def _apply_templates(self, source_dir: str, template_context: Optional[Dict[str, Any]] = None) -> None:
        if not template_context:
            return

        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith(".tpl"):
                    template_path = os.path.join(root, file)
                    try:
                        self.logger.debug(f"Processing template: {template_path}")
                        template = self.template_env.get_template(os.path.relpath(template_path, source_dir))
                        rendered_content = template.render(**template_context)
                        output_path = template_path.replace(".tpl", "")
                        with open(output_path, 'w', encoding='utf-8'):
                            f.write(rendered_content)
                        self.logger.info(f"Rendered template: {output_path}")
                    except Exception as e:
                        self.logger.error(f"Failed to render template {template_path}: {e}")
                        raise TemplateRenderingError(f"Error rendering template {template_path}")

    def _copy_dotfiles(self, source_dir: str, target_dir: str, backup_id: Optional[str] = None) -> None:
        try:
            self._validate_dotfile_directory(source_dir)

            def copy_operation():
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

            self._safe_file_operation(
                "copy_dotfiles",
                copy_operation
            )
        except Exception as e:
            raise FileOperationError(f"Failed to copy dotfiles from {source_dir} to {target_dir}: {e}")

    def _remove_dotfiles(self, target_dir: str) -> None:
        try:
            self._validate_dotfile_directory(target_dir)

            def remove_operation():
                backup_id = self.backup_manager.start_operation_backup("remove_dotfiles")

                for item in os.listdir(target_dir):
                    path = os.path.join(target_dir, item)
                    if os.path.exists(path):
                        if os.path.isdir(path):
                            self.backup_manager.backup_file(path)
                            shutil.rmtree(path)
                        else:
                            self.backup_manager.backup_file(path)
                            os.remove(path)

                return backup_id

            self._safe_file_operation(
                "remove_dotfiles",
                remove_operation
            )
        except Exception as e:
            raise FileOperationError(f"Failed to remove dotfiles from {target_dir}: {e}")

    def _discover_scripts(self, local_dir: str, custom_scripts = None) -> Dict[str, List[str]]:
        try:
            script_phases = {
                "pre_clone": [], "post_clone": [],
                "pre_install_dependencies": [], "post_install_dependencies": [],
                "pre_apply": [], "post_apply": [],
                "pre_uninstall": [], "post_uninstall": []
            }
            if custom_scripts:
                for script in custom_scripts:
                   script_path = os.path.join(local_dir, script)
                   if os.path.exists(script_path) and os.path.isfile(script_path) and os.access(script_path, os.X_OK):
                       for phase in script_phases:
                        if script.startswith(phase):
                            script_phases[phase].append(script)
                            break
            script_dir = os.path.join(local_dir, "scriptdata")
            if not os.path.exists(script_dir) or not os.path.isdir(script_dir):
                return script_phases

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

    def apply_dotfiles(self, repository_name, stow_options=[], package_manager=None, target_packages=None, overwrite_symlink=None, custom_paths=None, ignore_rules=False, template_context={}, discover_templates=False, custom_scripts=None):
        """Applies dotfiles from a repository using GNU Stow."""
        try:
            rice_config = self.config_manager.get_rice_config(repository_name)
            if not rice_config:
                self.logger.error(f"No configuration found for repository: {repository_name}")
                return False

            local_dir = rice_config['local_directory']

            if not self.plates(local_dir, rice_config.get('dotfile_directories', {}), template_context):
                return False

            nix_config = self._check_nix_config(local_dir)
            rice_config['nix_config'] = nix_config
            self.config_manager.add_rice_config(repository_name, rice_config)

            script_config = self._discover_scripts(local_dir, custom_scripts)
            rice_config['script_config'].update(script_config)
            self.config_manager.add_rice_config(repository_name, rice_config)

            env = os.environ.copy()
            env['RICE_DIRECTORY'] = local_dir
            if not self.script_runner.run_scripts_by_phase(local_dir, 'pre_clone', rice_config.get('script_config'), env):
                return False

            if nix_config:
                if not self._apply_nix_config(local_dir, package_manager):
                    return False
                rice_config['applied'] = True
                self.config_manager.add_rice_config(repository_name, rice_config)
                self.logger.info("Nix configuration applied successfully")
                return True

            if target_packages:
                if not isinstance(target_packages, list):
                    target_packages = [target_packages]

                if len(target_packages) == 1 and os.path.basename(target_packages[0]) != ".config":
                    self.logger.info(f"Applying dots for: {target_packages[0]}")
                else:
                    self.logger.info(f"Applying dots for: {', '.join(target_packages)}")

            if not self.script_runner.run_scripts_by_phase(local_dir, 'post_clone', rice_config.get('script_config'), env):
                return False

            dotfile_dirs = self._discover_dotfile_directories(local_dir, target_packages, custom_paths, ignore_rules)
            if not dotfile_dirs:
                self.logger.warning("No dotfile directories found. Aborting")
                return False

            top_level_dirs = [os.path.basename(dir) for dir in dotfile_dirs if not os.path.dirname(dir)]
            if len(top_level_dirs) > 1 and not target_packages:
                chosen_rice = self._prompt_multiple_rices(top_level_dirs)
                if not chosen_rice:
                    self.logger.warning("Installation aborted.")
                    return False
                dotfile_dirs = {dir: category for dir, category in dotfile_dirs.items() if os.path.basename(dir).startswith(chosen_rice)}
                if not dotfile_dirs:
                    self.logger.error("No dotfiles were found with the specified rice name.")
                    return False

            rice_config['dotfile_directories'] = dotfile_dirs
            dependencies = self._discover_dependencies(local_dir, dotfile_dirs)
            rice_config['dependencies'] = dependencies
            self.config_manager.add_rice_config(repository_name, rice_config)

            if not self._check_nix_config(local_dir):
                if not self._install_fonts(local_dir, package_manager):
                    return False

            if not self.script_runner.run_scripts_by_phase(local_dir, 'pre_install_dependencies', rice_config.get('script_config'), env):
                return False

            if not package_manager.install(dependencies, local_dir=local_dir):
                return False

            if not self.script_runner.run_scripts_by_phase(local_dir, 'post_install_dependencies', rice_config.get('script_config'), env):
                return False

            if not self.script_runner.run_scripts_by_phase(local_dir, 'pre_apply', rice_config.get('script_config'), env):
                return False

            self._apply_templates(local_dir, template_context)

            applied_all = True
            for directory, category in dotfile_dirs.items():
                dir_path = os.path.join(local_dir, directory)
                if not os.path.exists(dir_path):
                    self.logger.warning(f"Could not find directory {dir_path}")
                    continue
                if category == "config":
                    if not self._apply_config_directory(local_dir, directory, stow_options, overwrite_symlink):
                        applied_all = False
                elif category == "cache":
                    if not self._apply_cache_directory(local_dir, directory, stow_options, overwrite_symlink):
                        applied_all = False
                elif category == "local":
                    if not self._apply_local_directory(local_dir, directory, stow_options, overwrite_symlink):
                        applied_all = False
                elif category == "script":
                    if not self._apply_other_directory(local_dir, directory):
                        applied_all = False
                else:
                    if not self._apply_other_directory(local_dir, directory):
                        applied_all = False

            custom_extras_paths = self.config_manager.get_rice_config(repository_name).get('custom_extras_paths')
            if custom_extras_paths:
                self._apply_custom_extras_directories(local_dir, custom_extras_paths)

            extras_dir = os.path.join(local_dir, "Extras")
            if os.path.exists(extras_dir) and os.path.isdir(extras_dir):
                self.logger.info("Found Extras folder, applying the files now.")
                for item in os.listdir(extras_dir):
                    item_path = os.path.join(extras_dir, item)
                    if os.path.isdir(item_path):
                        if not self._apply_extra_directory(local_dir, item_path):
                            applied_all = False

            if not self.script_runner.run_scripts_by_phase(local_dir, 'post_apply', rice_config.get('script_config'), env):
                return False

            if applied_all:
                self.logger.info(f"Successfully applied dotfiles from {repository_name}")
                rice_config['applied'] = True
                self.config_manager.add_rice_config(repository_name, rice_config)
                return True
            else:
                self.logger.error(f"Failed to apply all dotfiles")
                return False
        except Exception as e:
            self.logger.error(f"An error occurred while applying dotfiles: {e}")
            return False

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

    def manage_dotfiles(self, repository_name, stow_options = [], package_manager = None, target_packages = None, custom_paths = None, ignore_rules = False, template_context = {}):
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
            for child in node.children:
                traverse(child)

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

    def _detect_package_dependencies(self, config_file: str) -> List[str]:
        """Detect package dependencies from various config file formats"""
        dependencies = set()
        
        if not os.path.exists(config_file):
            return list(dependencies)
            
        with open(config_file, 'r') as f:
            content = f.read()
            
        # Common package patterns
        patterns = [
            r'requires\s*=\s*[\'"](.*?)[\'"]',  # Python style
            r'depends\s*=\s*[\'"](.*?)[\'"]',   # PKGBUILD style
            r'package\s*:\s*(.*?)$',            # YAML style
            r'\"dependencies\":\s*{([^}]*)}',   # package.json style
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                deps = match.group(1).split()
                dependencies.update(deps)
                
        return list(dependencies)

    def _check_system_compatibility(self) -> Dict[str, bool]:
        """Check system compatibility for the rice installation"""
        compatibility = {
            'nix_support': False,
            'stow_available': False,
            'xorg_present': False,
            'wayland_present': False,
            'package_manager': None
        }
        
        # Check for Nix
        try:
            subprocess.run(['nix', '--version'], capture_output=True)
            compatibility['nix_support'] = True
        except FileNotFoundError:
            pass
            
        # Check for GNU Stow
        try:
            subprocess.run(['stow', '--version'], capture_output=True)
            compatibility['stow_available'] = True
        except FileNotFoundError:
            pass
            
        # Detect display server
        if os.environ.get('WAYLAND_DISPLAY'):
            compatibility['wayland_present'] = True
        elif os.environ.get('DISPLAY'):
            compatibility['xorg_present'] = True
            
        # Detect package manager
        for pm in ['pacman', 'apt', 'dnf', 'zypper']:
            try:
                subprocess.run([pm, '--version'], capture_output=True)
                compatibility['package_manager'] = pm
                break
            except FileNotFoundError:
                continue
                
        return compatibility

    async def _parallel_install_dependencies(self, dependencies: List[str]):
        """Install dependencies in parallel for faster deployment"""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        async def install_pkg(pkg: str):
            try:
                if self.system_info['package_manager'] == 'pacman':
                    cmd = ['pacman', '-S', '--noconfirm', pkg]
                elif self.system_info['package_manager'] == 'apt':
                    cmd = ['apt', 'install', '-y', pkg]
                else:
                    return False
                    
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                return proc.returncode == 0
            except Exception as e:
                self.logger.error(f"Failed to install {pkg}: {str(e)}")
                return False
                
        with ThreadPoolExecutor() as executor:
            tasks = [install_pkg(dep) for dep in dependencies]
            results = await asyncio.gather(*tasks)
            
        return all(results)

    def apply_rice_automated(self, rice_path: str):
        """Fully automated rice installation process"""
        try:
            # 1. System compatibility check
            self.system_info = self._check_system_compatibility()
            
            # 2. Analyze rice structure
            rice_analysis = self.analyze_rice_directory(rice_path)
            
            # 3. Detect and collect all dependencies
            all_deps = set()
            for config_file in rice_analysis['config_files']:
                deps = self._detect_package_dependencies(config_file)
                all_deps.update(deps)
                
            # 4. Install dependencies
            if all_deps:
                asyncio.run(self._parallel_install_dependencies(list(all_deps)))
                
            # 5. Determine installation strategy
            if self.system_info['nix_support'] and rice_analysis['has_nix_config']:
                self._apply_nix_config(rice_path, self.system_info['package_manager'])
            elif self.system_info['stow_available']:
                # We need to analyze the dotfile structure before using stow
                tree = DotfileTree()
                root = tree.build_tree(rice_path)

                dotfile_dirs = {}
                def traverse_tree(node):
                   if node.is_dotfile:
                      rel_path = os.path.relpath(node.path, rice_path)
                      category = self._categorize_dotfile_directory(node.path)
                      dotfile_dirs[rel_path] = category
                   for child in node.children:
                      traverse_tree(child)
                traverse_tree(root)

                # Apply directories
                for directory, category in dotfile_dirs.items():
                     if category == "config":
                        self._apply_config_directory(rice_path, directory)
                     elif category == "cache":
                        self._apply_cache_directory(rice_path, directory)
                     elif category == "local":
                        self._apply_local_directory(rice_path, directory)
                     else:
                         self._apply_other_directory(rice_path, directory)
            else:
                #Apply a complex structure
                self._apply_complex_structure(rice_path)
                
            # 6. Apply post-installation configuration
            if rice_analysis['post_install_scripts']:
                self._execute_scripts(rice_analysis['post_install_scripts'])
                
            return True
                
        except Exception as e:
            self.logger.error(f"Failed to install rice: {str(e)}")
            self._rollback_changes()
            return False

    def _apply_config_directory(self, rice_path: str, directory: str):
        """Apply configuration directory with enhanced handling"""
        src = os.path.join(rice_path, directory)
        category = self._categorize_dotfile_directory(src)
        
        if category == "asset":
            # Handle assets (wallpapers, icons, etc.)
            target_dir = os.path.expanduser(f"~/.local/share/{os.path.basename(src)}")
            os.makedirs(target_dir, exist_ok=True)
            self._copy_assets(src, target_dir)
        elif category == "theme":
            # Handle themes and styles
            self._apply_theme_directory(src)
        elif category == "nix":
            # Handle Nix configurations
            self._apply_nix_config(src)
        else:
            # Default config handling
            target = os.path.expanduser(f"~/.config/{os.path.basename(src)}")
            self._create_symlink(src, target)

    def _copy_assets(self, src_dir: str, target_dir: str):
        """Copy asset files while preserving structure"""
        try:
            for root, _, files in os.walk(src_dir):
                rel_path = os.path.relpath(root, src_dir)
                target_path = os.path.join(target_dir, rel_path)
                os.makedirs(target_path, exist_ok=True)
                
                for file in files:
                    src_file = os.path.join(root, file)
                    target_file = os.path.join(target_path, file)
                    shutil.copy2(src_file, target_file)
                    
            self.logger.info(f"Copied assets from {src_dir} to {target_dir}")
        except Exception as e:
            self.logger.error(f"Failed to copy assets: {e}")
            raise FileOperationError(f"Failed to copy assets: {e}")

    def _apply_theme_directory(self, theme_dir: str):
        """Apply theme configurations"""
        name = os.path.basename(theme_dir).lower()
        
        if name in {'gtk-3.0', 'gtk-4.0'}:
            target = os.path.expanduser(f"~/.config/{name}")
        else:
            # Handle other theme types
            target = os.path.expanduser("~/.local/share/themes")
            
        os.makedirs(target, exist_ok=True)
        self._create_symlink(theme_dir, target)