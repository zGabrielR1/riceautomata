# src/dotfile.py
import os
import shutil
import subprocess
from src.utils import setup_logger, sanitize_path, create_timestamp, confirm_action
from src.config import ConfigManager
from src.script import ScriptRunner
from src.backup import BackupManager
from src.exceptions import (
    RiceAutomataError, ConfigurationError, GitOperationError,
    FileOperationError, ValidationError, RollbackError
)
import sys
import re
import json
from jinja2 import Environment, FileSystemLoader
from typing import Dict, List, Optional, Any
import time

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
            r'\.toml$',
            r'\.yaml$',
            r'\.yml$',
            r'\.json$',
            r'rc$',  # rc files
            r'config$',  # config files
            r'\.nix$',  # Nix configuration files
            r'flake\.nix$'  # Nix flakes
        ]
        self.known_config_dirs = {
            'nvim', 'alacritty', 'hypr', 'waybar', 'sway', 'i3',
            'polybar', 'kitty', 'rofi', 'dunst', 'picom', 'gtk-3.0',
            'gtk-4.0', 'zsh', 'bash', 'fish', 'tmux', 'neofetch',
            'fastfetch', 'eww', 'wezterm'
        }

    def build_tree(self, root_path: str) -> DotfileNode:
        """Build a tree structure of the dotfiles directory"""
        root = DotfileNode(root_path)
        self.root = root
        self._build_tree_recursive(root)
        return root

    def _is_dotfile(self, path: str) -> bool:
        """Check if a file or directory is a dotfile/config"""
        name = os.path.basename(path)
        
        # Check if it's a known config directory
        if os.path.isdir(path) and name.lower() in self.known_config_dirs:
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

    def find_dependencies(self, node: DotfileNode):
        """Find dependencies in configuration files with format-specific parsing."""
        if os.path.isfile(node.path):
            _, ext = os.path.splitext(node.path)
            try:
                with open(node.path, 'r', encoding='utf-8') as f:
                    if ext == '.json':
                        data = json.load(f)
                        # Example for package.json
                        if 'dependencies' in data:
                            node.dependencies.update(data['dependencies'].keys())
                    elif ext in ['.toml']:
                        # Use toml parser
                        import toml
                        data = toml.load(f)
                        if 'dependencies' in data:
                            node.dependencies.update(data['dependencies'].keys())
                    elif ext in ['.yaml', '.yml']:
                        # Use yaml parser
                        import yaml
                        data = yaml.safe_load(f)
                        if 'dependencies' in data:
                            node.dependencies.update(data['dependencies'].keys())
                    else:
                        content = f.read().lower()
                        # Fallback heuristic
                        if any(indicator in content for indicator in ['requires', 'depends', 'dependencies']):
                            packages = set(re.findall(r'[\w-]+(?:>=?[\d.]+)?', content))
                            node.dependencies.update(packages)
            except Exception as e:
                self.logger.warning(f"Could not analyze dependencies in {node.path}: {e}")

        for child in node.children:
            self.find_dependencies(child)

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
            if not os.path.exists(self.managed_rices_dir):
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
        """Clones a git repository with retry and rollback support.
        
        Args:
            repository_url (str): The URL of the git repository to clone. Supports various formats:
                - HTTPS URLs (https://...)
                - Git URLs (git://...)
                - SSH URLs (git@...)
                
        Returns:
            bool: True if cloning was successful, False otherwise
        """
        backup_id = None
        try:
            # Normalize repository URL
            if repository_url.startswith('git://'):
                repository_url = repository_url.replace('git://', 'https://')
            
            repo_name = repository_url.split('/')[-1].replace(".git", "")
            local_dir = os.path.join(self.managed_rices_dir, repo_name)
            
            if os.path.exists(local_dir):
                raise GitOperationError(f"Repository already exists at {local_dir}")

            # Start backup operation
            backup_id = self.backup_manager.start_operation_backup("clone_repository")
            
            self.logger.info(f"Cloning repository from {repository_url} into {local_dir}")
            
            # Configure git to handle credentials and SSL
            self.script_runner._run_command(["git", "config", "--global", "credential.helper", "store"])
            self.script_runner._run_command(["git", "config", "--global", "http.sslVerify", "true"])
            
            # Define the clone operation with specific options
            def clone_op():
                try:
                    # Use --progress for better output and --recursive for submodules
                    result = self.script_runner._run_command([
                        "git", "clone",
                        "--progress",
                        "--recursive",
                        repository_url,
                        local_dir
                    ])
                    return result
                except Exception as e:
                    error_msg = str(e).lower()
                    if "authentication failed" in error_msg:
                        self.logger.error("Authentication failed. Please ensure you have the correct credentials configured.")
                        raise GitOperationError("Authentication failed. Use SSH key or configure git credentials.")
                    elif "could not resolve host" in error_msg:
                        self.logger.error("Could not resolve host. Please check your internet connection and the repository URL.")
                        raise GitOperationError("Could not resolve host. Check internet connection and URL.")
                    elif "permission denied" in error_msg:
                        self.logger.error("Permission denied. Please check if you have access to this repository.")
                        raise GitOperationError("Permission denied. Verify repository access permissions.")
                    else:
                        raise
            
            # Attempt to clone the repository with retries
            clone_result = self._retry_operation(clone_op)

            if clone_result:
                self.logger.info(f"Repository cloned successfully to: {local_dir}")
                
                # Verify the clone was successful by checking for .git directory
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
                self.logger.error("Failed to clone repository. Check the logs for more details.")
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
            if os.path.exists(rules_path):
                with open(rules_path, 'r') as f:
                    return json.load(f)
            return {}
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in rules config: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load rules config: {e}")

    def _load_dependency_map(self):
        """Loads the dependency map to discover dependencies"""
        try:
            dependency_map_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "dependency_map.json")
            if os.path.exists(dependency_map_path):
                with open(dependency_map_path, 'r') as f:
                    return json.load(f)
            return {}
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in dependency map: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load dependency map: {e}")

    def _discover_scripts(self, local_dir: str) -> Dict[str, List[str]]:
        """Discovers executable files inside a "scriptdata" directory."""
        try:
            script_dir = os.path.join(local_dir, "scriptdata")
            if not os.path.exists(script_dir) or not os.path.isdir(script_dir):
                return {}

            script_phases = {
                "pre_clone": [], "post_clone": [],
                "pre_install_dependencies": [], "post_install_dependencies": [],
                "pre_apply": [], "post_apply": [],
                "pre_uninstall": [], "post_uninstall": []
            }

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

    def _validate_dotfile_directory(self, dir_path: str) -> None:
        """Validates a dotfile directory."""
        try:
            if not os.path.exists(dir_path):
                raise ValidationError(f"Directory does not exist: {dir_path}")
            if not os.path.isdir(dir_path):
                raise ValidationError(f"Path is not a directory: {dir_path}")
            if not os.access(dir_path, os.R_OK):
                raise ValidationError(f"Directory is not readable: {dir_path}")
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Failed to validate directory {dir_path}: {e}")

    def _backup_file(self, file_path: str, operation_name: str) -> Optional[str]:
        """Creates a backup of a file before modification."""
        try:
            if os.path.exists(file_path):
                backup_id = self.backup_manager.start_operation_backup(operation_name)
                self.backup_manager.backup_file(file_path)
                return backup_id
            return None
        except Exception as e:
            raise FileOperationError(f"Failed to backup file {file_path}: {e}")

    def _safe_file_operation(self, operation_name: str, operation, *args, **kwargs):
        """Executes a file operation with backup and rollback support."""
        backup_id = None
        try:
            backup_id = self.backup_manager.start_operation_backup(operation_name)
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
        """Calculates score based on directory name and defined rules."""
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
        """Calculates score based on the content of files in directory."""
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
                        content = file.read(1024)  # Read first 1KB for performance
                        for keyword in config_keywords:
                            if keyword in content.lower():
                                score += 0.5
                except:
                   pass
        return score

    def _is_likely_dotfile_dir(self, dir_path):
        """Checks if the directory is likely to contain dotfiles based on its name, content, and rules."""
        dir_name = os.path.basename(dir_path)
        name_score = self._score_dir_name(dir_name)
        content_score = self._score_dotfile_content(dir_path)
        
        return name_score + content_score >= 2  # Adjust threshold as needed

    def _categorize_dotfile_directory(self, dir_path):
        """Categorizes a dotfile directory as 'config', 'wallpaper', 'script', etc."""
        dir_name = os.path.basename(dir_path)

        if dir_name in ["wallpapers", "wallpaper", "backgrounds"]:
           return "wallpaper"
        elif dir_name in ["scripts", "bin"]:
          return "script"
        elif dir_name in ["icons", "cursors"]:
            return "icon"
        elif dir_name == "cache":
           return "cache"
        elif dir_name == ".local":
           return "local"
        else:
           return "config" # If not specified, consider as a config directory

    def _discover_dotfile_directories(self, local_dir, target_packages = None, custom_paths = None, ignore_rules = False):
        """Detects dotfile directories using the improved heuristics, and categorizes them."""
        dotfile_dirs = {}
        if custom_paths: # If the user is using a custom folder
            for path in custom_paths:
                full_path = os.path.join(local_dir, path)
                if os.path.exists(full_path):
                    if os.path.isdir(full_path):
                        for root, _, files in os.walk(full_path):
                             for item in files:
                                item_path = os.path.join(root, item)
                                category = self._categorize_dotfile_directory(item_path)
                                dotfile_dirs[os.path.relpath(item_path, local_dir)] = category
                    elif os.path.isfile(full_path):
                        category = self._categorize_dotfile_directory(full_path)
                        dotfile_dirs[path] = category
                else:
                    self.logger.warning(f"Could not find custom path: {path}")
            return dotfile_dirs

        for item in os.listdir(local_dir):
           item_path = os.path.join(local_dir, item)
           if os.path.isdir(item_path):
              if target_packages:
                if item in target_packages:
                     category = self._categorize_dotfile_directory(item_path)
                     dotfile_dirs[item] = category
                if item == ".config":
                  for sub_item in os.listdir(item_path):
                    sub_item_path = os.path.join(item_path, sub_item)
                    if os.path.isdir(sub_item_path) and (ignore_rules or self._is_likely_dotfile_dir(sub_item_path)) and sub_item in target_packages:
                      category = self._categorize_dotfile_directory(sub_item_path)
                      dotfile_dirs[os.path.join(item, sub_item)] = category
                elif os.path.exists(os.path.join(item_path, ".config")):
                   for sub_item in os.listdir(os.path.join(item_path, ".config")):
                     sub_item_path = os.path.join(item_path, ".config", sub_item)
                     if os.path.isdir(sub_item_path) and (ignore_rules or self._is_likely_dotfile_dir(sub_item_path)) and sub_item in target_packages:
                        category = self._categorize_dotfile_directory(sub_item_path)
                        dotfile_dirs[os.path.join(item, ".config", sub_item)] = category
              else:
                  if item == ".config":
                      for sub_item in os.listdir(item_path):
                          sub_item_path = os.path.join(item_path, sub_item)
                          if os.path.isdir(sub_item_path) and (ignore_rules or self._is_likely_dotfile_dir(sub_item_path)):
                              category = self._categorize_dotfile_directory(sub_item_path)
                              dotfile_dirs[os.path.join(item, sub_item)] = category
                  elif os.path.exists(os.path.join(item_path, ".config")):
                      for sub_item in os.listdir(os.path.join(item_path, ".config")):
                          sub_item_path = os.path.join(item_path, ".config", sub_item)
                          if os.path.isdir(sub_item_path) and (ignore_rules or self._is_likely_dotfile_dir(sub_item_path)):
                              category = self._categorize_dotfile_directory(sub_item_path)
                              dotfile_dirs[os.path.join(item, ".config", sub_item)] = category
                  elif (ignore_rules or self._is_likely_dotfile_dir(item_path)):
                      category = self._categorize_dotfile_directory(item_path)
                      dotfile_dirs[item] = category
        return dotfile_dirs

    def _discover_dependencies(self, local_dir, dotfile_dirs):
        """Detects dependencies based on the dotfile directories, dependency files and package definitions."""
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

        # Check for package manager specific dependency files
        for pm, files in package_managers.items():
            for file in files:
                dep_file_path = os.path.join(local_dir, file)
                if os.path.exists(dep_file_path) and os.path.isfile(dep_file_path):
                    try:
                        if file == 'package.json':
                            with open(dep_file_path, 'r') as f:
                                data = json.load(f)
                                deps = data.get('dependencies', {})
                                deps.update(data.get('devDependencies', {}))
                                for pkg in deps.keys():
                                    dependencies.append(f"npm:{pkg}")
                        elif file == 'Cargo.toml':
                            # Parse TOML file for Rust dependencies
                            with open(dep_file_path, 'r') as f:
                                for line in f:
                                    if '=' in line and '[dependencies]' in open(dep_file_path).read():
                                        pkg = line.split('=')[0].strip()
                                        dependencies.append(f"cargo:{pkg}")
                        else:
                            with open(dep_file_path, 'r') as f:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith('#'):
                                        dependencies.append(f"{pm}:{line}")
                    except Exception as e:
                        self.logger.warning(f"Error parsing dependency file {file}: {e}")

        # Check common config directories for implicit dependencies
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
            'ags': ['npm:yarn', 'npm:esbuild', 'npm:sass', 'gtk4'],
            'foot': ['foot'],
            'fuzzel': ['fuzzel']
        }

        for dir_name in dotfile_dirs:
            base_name = os.path.basename(dir_name)
            if base_name in common_deps:
                dependencies.extend(f"auto:{dep}" for dep in common_deps[base_name])
        #Check dependency map
        for dep, packages in self.dependency_map.get('dependencies', {}).items():
            if dep in dotfile_dirs or any(dep in dir for dir in dotfile_dirs):
                dependencies.extend(packages)


        # Check arch-packages directory
        arch_packages_dir = os.path.join(local_dir, "arch-packages")
        if os.path.exists(arch_packages_dir) and os.path.isdir(arch_packages_dir):
            for item in os.listdir(arch_packages_dir):
                item_path = os.path.join(arch_packages_dir, item)
                if os.path.isdir(item_path):
                    dependencies.append(f"aur:{item}")

        # Check for custom dependency files
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

        return list(set(dependencies))  # Remove duplicates

    def _check_nix_config(self, local_dir):
      """Checks if a font file exists."""
      def _is_font_file(filename):
        font_extensions = [".ttf", ".otf", ".woff", ".woff2"]
        return any(filename.lower().endswith(ext) for ext in font_extensions)
      """Checks if the repository contains a NixOS configuration."""
      nix_files = ["flake.nix", "configuration.nix"]
      for file in nix_files:
        if os.path.exists(os.path.join(local_dir, file)):
          return True
      return False

    def _install_fonts(self, local_dir, package_manager):
      """Installs any font files it finds in a font folder."""
      def _is_font_file(filename):
        font_extensions = [".ttf", ".otf", ".woff", ".woff2"]
        return any(filename.lower().endswith(ext) for ext in font_extensions)
      
      fonts_dir = os.path.join(local_dir, "fonts")
      if not os.path.exists(fonts_dir) or not os.path.isdir(fonts_dir):
         return True # No fonts directory, so no fonts to install.
      for item in os.listdir(fonts_dir):
        item_path = os.path.join(fonts_dir, item)
        if os.path.isfile(item_path) and _is_font_file(item):
          font_name = os.path.basename(item).split(".")[0]
          if not package_manager.is_installed(font_name) or not any(font_name in package for package in package_manager.installed_packages):
            self.logger.info(f"Installing font {font_name}")
            if not package_manager.install_package(f"auto:{font_name}"): # Install using system package manager, if its a package
             self.logger.info(f"{font_name} not found as package, trying to install manually.")
             if not package_manager._install_font_manually(item_path): # If not, we'll try to install it manually
               self.logger.error(f"Failed to install font: {font_name}")
               return False
          else:
            self.logger.debug(f"Font: {font_name} is already installed")
      return True


    def _apply_nix_config(self, local_dir, package_manager):
       """Applies a NixOS configuration."""
       if not package_manager.nix_installed:
            if not package_manager._install_nix():
                self.logger.error("Nix is required, and failed to install. Aborting.")
                return False
       self.logger.info("Applying nix configuration.")
       try:
        nix_apply_command = ["nix", "build", ".#system", "--print-out-paths"]
        nix_apply_result = self.script_runner._run_command(nix_apply_command, cwd = local_dir)
        if not nix_apply_result:
           return False
        profile_path = nix_apply_result.stdout.strip()
        nix_switch_command = ["sudo", "nix-env", "-p", "/nix/var/nix/profiles/system", "-i", profile_path]
        switch_result = self.script_runner._run_command(nix_switch_command)
        if not switch_result:
            return False
        return True

       except Exception as e:
         self.logger.error(f"Error applying nix configuration: {e}")
         return False

    def _apply_directory_with_stow(self, local_dir, directory, stow_options=[], overwrite_destination=None):
        """Applies the directory using GNU Stow with overwriting logic."""
        if overwrite_destination:
            target_path = os.path.expanduser(overwrite_destination)
            self._overwrite_symlinks(target_path, local_dir, directory)
            return True

        stow_command = ["stow", "-v"]
        stow_command.extend(stow_options)
        stow_command.append(os.path.basename(directory))
        stow_result = self.script_runner._run_command(stow_command, check=False, cwd=local_dir)
        if not stow_result or stow_result.returncode != 0:
            self.logger.error(f"Failed to stow directory: {directory}. Check if Stow is installed, and if the options are correct: {stow_options}")
            return False
        return True


    def _apply_config_directory(self, local_dir, directory, stow_options = [], overwrite_destination=None):
      """Applies the dotfiles using GNU Stow."""
      if overwrite_destination and overwrite_destination.startswith("~"):
           stow_dir = os.path.join(os.path.expanduser(overwrite_destination), os.path.basename(directory))
      else:
         stow_dir = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
      if os.path.basename(directory) != ".config" and not os.path.exists(stow_dir):
          os.makedirs(stow_dir, exist_ok = True)
      return self._apply_directory_with_stow(local_dir, directory, stow_options, overwrite_destination)

    def _overwrite_symlinks(self, target_path, local_dir, directory):
      """Overwrites symlinks when the user specifies a custom folder to install."""
      dir_path = os.path.join(local_dir, directory)
      if not os.path.exists(dir_path):
        self.logger.warning(f"Could not find directory {dir_path} when trying to overwrite")
        return False
      
      target_dir = os.path.join(target_path, os.path.basename(directory))
      if os.path.exists(target_dir):
        stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
        self.script_runner._run_command(stow_command, check=False, cwd=local_dir)

    def _apply_cache_directory(self, local_dir, directory, stow_options = [], overwrite_destination = None):
        """Applies a cache directory using GNU Stow."""
        return self._apply_directory_with_stow(local_dir, directory, stow_options, overwrite_destination)

    def _apply_local_directory(self, local_dir, directory, stow_options = [], overwrite_destination = None):
       """Applies a local directory using GNU Stow."""
       return self._apply_directory_with_stow(local_dir, directory, stow_options, overwrite_destination)

    def _apply_other_directory(self, local_dir, directory):
       """Applies files that aren't configs (wallpaper, scripts) into the home directory"""
       dir_path = os.path.join(local_dir, directory)
       target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
       if os.path.exists(target_path): # if a folder already exists, abort.
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
       """Applies files from the Extras directory to a custom path"""
       dir_path = os.path.join(local_dir, directory)
       target_path = os.path.join(target_base, os.path.basename(directory))

       if not os.path.exists(target_base):
         os.makedirs(target_base, exist_ok=True) #create root folder if it does not exists.

       try:
           if os.path.exists(target_path): # if a folder already exists, abort.
               self.logger.warning(f"Path {target_path} already exists, skipping...")
               return False
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
    
    def _apply_custom_extras_directories(self, local_dir, custom_extras_paths):
      """Applies the extra directories based on the configuration."""
      for path, target in custom_extras_paths.items():
          full_path = os.path.join(local_dir, path)
          if os.path.exists(full_path):
            self._apply_extra_directory(local_dir, path, target)
          else:
            self.logger.warning(f"Custom extras directory not found: {full_path}")
    
    def _process_template_file(self, template_path, context):
       """Renders a template file with the given context."""
       try:
          template = self.template_env.get_template(template_path)
          return template.render(context)
       except Exception as e:
         self.logger.error(f"Error processing template: {template_path}. Error: {e}")
         return None

    def plates(self, local_dir, dotfile_dirs, context):
        """Applies all the templates with the correct context."""
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
        """Applies template variables to files."""
        try:
            if not template_context:
                return

            def process_template(file_path: str) -> None:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        template_str = f.read()
                    
                    # Check if file contains any Jinja2 template syntax
                    if '{{' in template_str or '{%' in template_str:
                        template = self.template_env.from_string(template_str)
                        rendered = template.render(**template_context)
                        
                        # Backup before modifying
                        backup_id = self._backup_file(file_path, "template_processing")
                        
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(rendered)
                except Exception as e:
                    raise FileOperationError(f"Failed to process template {file_path}: {e}")

            def walk_directory(current_dir: str) -> None:
                try:
                    for root, _, files in os.walk(current_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path):
                                process_template(file_path)
                except Exception as e:
                    raise FileOperationError(f"Failed to walk directory {current_dir}: {e}")

            self._safe_file_operation(
                "apply_templates",
                walk_directory,
                source_dir
            )
        except Exception as e:
            raise FileOperationError(f"Failed to apply templates in {source_dir}: {e}")

    def _copy_dotfiles(self, source_dir: str, target_dir: str, backup_id: Optional[str] = None) -> None:
        """Copies dotfiles with backup and rollback support."""
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
        """Removes dotfiles with backup support."""
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
        """Discovers executable files inside a "scriptdata" directory."""
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
            
            if not self.plates(local_dir, rice_config.get('dotfile_directories', {}), template_context, discover_templates):
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
              stow_result = self.script_runner._run_command(stow_command, check = False, cwd = local_dir)
              if not stow_result or stow_result.returncode != 0:
                  unlinked_all = False
                  self.logger.error(f"Failed to unstow config: {directory} from {target_path}")
            elif category == "cache":
              stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
              stow_result = self.script_runner._run_command(stow_command, check = False, cwd=local_dir)
              if not stow_result or stow_result.returncode != 0:
                 unlinked_all = False
                 self.logger.error(f"Failed to unstow cache: {directory}")
            elif category == "local":
               stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
               stow_result = self.script_runner._run_command(stow_command, check=False, cwd=local_dir)
               if not stow_result or stow_result.returncode != 0:
                  unlinked_all = False
                  self.logger.error(f"Failed to unstow local files: {directory}")
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

    def _read_package_list(self, file):
        """Read a package list from a file."""
        # Implement logic to read package list
        return []

    def _install_packages(self, packages):
        """Install a list of packages."""
        # Implement package installation logic
        pass

    def _handle_assets(self, asset_directories):
        """Handle asset management for directories."""
        for directory in asset_directories:
            self._process_assets(directory)

    def _process_assets(self, directory):
        """Process assets in a given directory."""
        # Implement logic to process assets
        pass

    def _apply_complex_structure(self, structure):
        """Apply configurations from complex directory structures."""
        # Implement logic to navigate and apply configurations
        pass

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
        tree = self.dotfile_tree.build_tree(rice_path)
        self.dotfile_tree.find_dependencies(tree)
        
        # Collect all dotfiles and their dependencies
        dotfiles = []
        nix_configs = []
        all_dependencies = set()
        
        def traverse(node):
            if node.is_dotfile:
                dotfiles.append(node.path)
                all_dependencies.update(node.dependencies)
            if node.is_nix_config:
                nix_configs.append(node.path)
            for child in node.children:
                traverse(child)
        
        traverse(tree)
        
        return {
            'dotfiles': dotfiles,
            'dependencies': list(all_dependencies),
            'has_nix': bool(nix_configs),
            'nix_configs': nix_configs
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
            subprocess.run(['nix', '--version'], capture_output=True)
            return True
        except FileNotFoundError:
            self.logger.info("Nix is required, and not installed. Installing Nix...")
            try:
                # Add Nix installation logic here
                return True
            except Exception as e:
                self.logger.error(f"Failed to install Nix: {e}")
                return False

class ConfigManager:
    def __init__(self):
        self.config_dir = os.path.join(os.path.expanduser("~"), ".config", "rice-automata")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self.config_data = {}
        self.logger = setup_logger()

        if not os.path.exists(self.config_dir):
            try:
                os.makedirs(self.config_dir, exist_ok=True)
                self.logger.info(f"Created configuration directory at {self.config_dir}")
            except Exception as e:
                self.logger.error(f"Failed to create config directory: {e}")
                raise ConfigurationError(f"Could not create config directory: {e}")

        if not os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'w') as f:
                    json.dump({}, f)
                self.logger.info(f"Created configuration file at {self.config_file}")
            except Exception as e:
                self.logger.error(f"Failed to create config file: {e}")
                raise ConfigurationError(f"Could not create config file: {e}")

        try:
            with open(self.config_file, 'r') as f:
                self.config_data = json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load config file: {e}")
            raise ConfigurationError(f"Could not load config file: {e}")

    def get_rice_config(self, repository_name):
        """Retrieve the configuration for a given rice repository."""
        config_path = os.path.join(self.config_dir, repository_name, 'rice_config.json')
        self.logger.debug(f"Looking for configuration at: {config_path}")

        if not os.path.exists(config_path):
            # If config doesn't exist, try to generate one from the repository structure
            self.logger.info(f"No existing configuration found for {repository_name}, generating from structure...")
            return self._generate_config_from_structure(repository_name)

        try:
            with open(config_path, 'r') as config_file:
                config = json.load(config_file)
                self.logger.debug(f"Loaded configuration for {repository_name}: {config}")
                return config
        except Exception as e:
            self.logger.error(f"Error reading configuration file for {repository_name}: {e}")
            return None

    def _generate_config_from_structure(self, repository_name):
        """Generate a configuration based on the repository structure."""
        repo_path = os.path.expanduser(repository_name)
        if not os.path.exists(repo_path):
            self.logger.error(f"Repository path does not exist: {repo_path}")
            return None

        config = {
            "name": os.path.basename(repo_path),
            "dotfile_dirs": [],
            "dependencies": [],
            "scripts": []
        }

        # Check for common configuration directories
        if os.path.exists(os.path.join(repo_path, "config")):
            config["dotfile_dirs"].append({
                "path": "config",
                "type": "config",
                "stow_target": "~/.config"
            })

        # Check for install scripts
        for script_name in ["install", "install.sh", "install.conf.yaml", "install.conf"]:
            if os.path.exists(os.path.join(repo_path, script_name)):
                config["scripts"].append(script_name)

        # Check for post-install scripts
        if os.path.exists(os.path.join(repo_path, "post-install")):
            for root, _, files in os.walk(os.path.join(repo_path, "post-install")):
                for file in files:
                    if os.access(os.path.join(root, file), os.X_OK):
                        config["scripts"].append(os.path.join("post-install", file))

        # Try to detect dependencies from various config files
        dependency_files = [
            "install.conf.yaml",
            "requirements.txt",
            "package.json",
            "Cargo.toml"
        ]

        for dep_file in dependency_files:
            dep_path = os.path.join(repo_path, dep_file)
            if os.path.exists(dep_path):
                try:
                    with open(dep_path, 'r') as f:
                        content = f.read().lower()
                        # Basic dependency detection - can be improved
                        deps = re.findall(r'(?:depends?(?:_?on)?|requires?|packages?)\s*:?\s*([\w-]+)', content)
                        config["dependencies"].extend(deps)
                except Exception as e:
                    self.logger.warning(f"Error reading dependency file {dep_file}: {e}")

        # Save the generated config
        config_dir = os.path.join(self.config_dir, repository_name)
        os.makedirs(config_dir, exist_ok=True)
        
        config_path = os.path.join(config_dir, 'rice_config.json')
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            self.logger.info(f"Generated and saved configuration for {repository_name}")
            return config
        except Exception as e:
            self.logger.error(f"Error saving generated configuration: {e}")
            return None

    def add_rice_config(self, repository_name, config):
        """Add or update the configuration for a given rice repository."""
        config_path = os.path.join(self.config_dir, repository_name, 'rice_config.json')
        self.logger.debug(f"Updating configuration at: {config_path}")

        try:
            with open(config_path, 'w') as config_file:
                json.dump(config, config_file, indent=4)
                self.logger.debug(f"Updated configuration for {repository_name}: {config}")
        except Exception as e:
            self.logger.error(f"Error updating configuration file for {repository_name}: {e}")
