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
from typing import Dict, List, Any, Optional, Set
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
import platform
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
import fnmatch
from collections import defaultdict

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
    """Manages dotfile operations including detection, backup, and installation."""
    
    def __init__(self, config_dir: str = None, verbose: bool = False):
        """Initialize DotfileManager with configuration directory."""
        self.config_dir = config_dir or os.path.expanduser("~/.config")
        self.os_type = platform.system()
        self.verbose = verbose
        
        # Load configurations
        config_path = os.path.join(os.path.dirname(__file__), "..", "configs")
        with open(os.path.join(config_path, "dependency_map.json")) as f:
            self.dependency_map = json.load(f)
        with open(os.path.join(config_path, "rules.json")) as f:
            self.rules = json.load(f)
        with open(os.path.join(config_path, "default_config.json")) as f:
            self.config = json.load(f)
            
        # Setup logging
        self._setup_logging()
        
    def _setup_logging(self):
        """Setup logging configuration."""
        log_config = self.config.get("logging", {})
        log_dir = os.path.expanduser(self.config.get("log_dir", "~/.config/riceautomata/logs"))
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, "riceautomata.log")
        self.logger = logging.getLogger("riceautomata")
        self.logger.setLevel(log_config.get("level", "INFO"))
        
        formatter = logging.Formatter(log_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        
        # File handler with rotation
        rotation_config = log_config.get("file_rotation", {})
        fh = RotatingFileHandler(
            log_file,
            maxBytes=rotation_config.get("max_bytes", 1048576),
            backupCount=rotation_config.get("backup_count", 3)
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

    def _detect_dotfiles(self, local_dir: str) -> Dict[str, List[str]]:
        """Detect dotfiles and their categories in the specified directory."""
        detected_configs = defaultdict(list)
        config_dirs = self.rules.get("config_dirs", {})
        
        for root, dirs, files in os.walk(local_dir):
            # Skip ignored patterns
            dirs[:] = [d for d in dirs if not any(fnmatch(d, pat) for pat in self.config["ignore_patterns"])]
            
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                rel_path = os.path.relpath(dir_path, local_dir)
                
                # Check each category
                for category, patterns in config_dirs.items():
                    if any(fnmatch(dir_name.lower(), pat) for pat in patterns):
                        detected_configs[category].append(rel_path)
                        self.logger.info(f"Detected {category} configuration: {rel_path}")
                        
        return detected_configs

    def _detect_required_packages(self, local_dir: str) -> Dict[str, set]:
        """Detect required packages based on dotfile structure."""
        required_packages = {
            'pacman': set(),
            'aur': set()
        }
        
        # Add base packages
        if self.os_type == 'Linux':
            base_pkgs = self.dependency_map.get("base", {})
            required_packages["pacman"].update(base_pkgs.get("pacman", []))
            required_packages["aur"].update(base_pkgs.get("aur", []))
        
        # Detect configurations and their required packages
        detected_configs = self._detect_dotfiles(local_dir)
        
        for category, configs in detected_configs.items():
            if category in self.dependency_map:
                category_deps = self.dependency_map[category]
                for config in configs:
                    config_name = os.path.basename(config).lower()
                    if config_name in category_deps:
                        pkg_deps = category_deps[config_name]
                        required_packages["pacman"].update(pkg_deps.get("pacman", []))
                        required_packages["aur"].update(pkg_deps.get("aur", []))
                        self.logger.info(f"Added dependencies for {config_name}")
        
        return required_packages

    def _install_packages(self, packages: Dict[str, set]) -> bool:
        """Install required packages using appropriate package manager."""
        if not any(packages.values()):
            self.logger.info("No packages to install")
            return True

        try:
            if self.os_type == 'Linux':
                pkg_config = self.config["package_managers"]["arch"]
                
                # Install official packages
                if packages["pacman"]:
                    pacman_cmd = pkg_config["install_cmd"]["pacman"].split()
                    pacman_cmd.extend(sorted(packages["pacman"]))
                    self.logger.info(f"Installing official packages: {' '.join(packages['pacman'])}")
                    subprocess.run(pacman_cmd, check=True)
                
                # Install AUR packages
                if packages["aur"]:
                    aur_helper = pkg_config["aur_helper"]
                    aur_cmd = pkg_config["install_cmd"]["aur"].split()
                    aur_cmd.extend(sorted(packages["aur"]))
                    self.logger.info(f"Installing AUR packages: {' '.join(packages['aur'])}")
                    subprocess.run(aur_cmd, check=True)
                
                return True
            else:
                self.logger.warning("Package installation is only supported on Arch Linux")
                return False
                
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error installing packages: {e}")
            return False

    def _create_backup(self, target_path: str) -> str:
        """Create backup of existing file or directory."""
        if not os.path.exists(target_path):
            return None
            
        backup_config = self.rules.get("backup", {})
        if not backup_config.get("enabled", True):
            return None
            
        backup_dir = os.path.expanduser(self.config["backup_dir"])
        os.makedirs(backup_dir, exist_ok=True)
        
        rel_path = os.path.relpath(target_path, os.path.expanduser("~"))
        backup_path = os.path.join(backup_dir, rel_path)
        
        if backup_config.get("timestamp", True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{backup_path}.{timestamp}{backup_config.get('suffix', '.bak')}"
        else:
            backup_path = f"{backup_path}{backup_config.get('suffix', '.bak')}"
            
        os.makedirs(os.path.dirname(backup_path), exist_ok=True)
        
        try:
            if os.path.isdir(target_path):
                shutil.copytree(target_path, backup_path)
            else:
                shutil.copy2(target_path, backup_path)
            self.logger.info(f"Created backup: {backup_path}")
            return backup_path
        except Exception as e:
            self.logger.error(f"Failed to create backup for {target_path}: {e}")
            return None

    def apply_dotfiles(self, local_dir: str, install_deps: bool = True) -> bool:
        """Apply dotfiles from local directory to user's home."""
        try:
            self.logger.info(f"Starting dotfile application from {local_dir}")
            
            # Detect and install required packages
            if install_deps:
                required_packages = self._detect_required_packages(local_dir)
                if not self._install_packages(required_packages):
                    self.logger.error("Failed to install required packages")
                    return False
            
            # Get detected configurations
            detected_configs = self._detect_dotfiles(local_dir)
            if not detected_configs:
                self.logger.warning("No configurations detected")
                return False
            
            # Process each detected configuration
            for category, configs in detected_configs.items():
                for config_path in configs:
                    src_path = os.path.join(local_dir, config_path)
                    
                    # Determine target path based on rules
                    if category in self.rules["symlink_rules"].get("home_dir", {}):
                        # Config goes directly in home directory
                        target_base = os.path.expanduser("~")
                        for target_file in self.rules["symlink_rules"]["home_dir"][category]:
                            target_path = os.path.join(target_base, target_file)
                            self._create_backup(target_path)
                            os.makedirs(os.path.dirname(target_path), exist_ok=True)
                            if os.path.exists(target_path):
                                os.remove(target_path)
                            os.symlink(src_path, target_path)
                            self.logger.info(f"Created symlink: {target_path} -> {src_path}")
                    else:
                        # Config goes in .config directory
                        target_path = os.path.join(self.config_dir, config_path)
                        self._create_backup(target_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        if os.path.exists(target_path):
                            os.remove(target_path)
                        os.symlink(src_path, target_path)
                        self.logger.info(f"Created symlink: {target_path} -> {src_path}")
            
            self.logger.info("Successfully applied dotfiles")
            return True
            
        except Exception as e:
            self.logger.error(f"Error applying dotfiles: {e}")
            return False