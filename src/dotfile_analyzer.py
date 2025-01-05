# src/dotfile_analyzer.py

import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set
import logging
import toml
import yaml

from .exceptions import ValidationError

class DotfileNode:
    def __init__(self, path: Path, is_dotfile: bool = False):
        self.path = path
        self.name = path.name
        self.is_dotfile = is_dotfile
        self.children = []
        self.dependencies: Set[str] = set()
        self.is_nix_config = False

class DotfileAnalyzer:
    """
    Analyzes dotfile directories to determine structure and dependencies.
    """
    def __init__(self, dependency_map: Dict[str, Any], logger: Optional[logging.Logger] = None):
        """
        Initializes the DotfileAnalyzer.

        Args:
            dependency_map (Dict[str, Any]): Mapping of configurations to packages.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.dependency_map = dependency_map
        self.logger = logger or logging.getLogger('DotfileManager')
        # Precompile regex patterns
        self.package_regex = re.compile(r'[\w-]+(?:>=?[\d.]+)?')

    def build_tree(self, root_path: Path) -> DotfileNode:
        """
        Builds a tree structure of the dotfiles directory.

        Args:
            root_path (Path): Root path of the dotfiles.

        Returns:
            DotfileNode: Root node of the tree.
        """
        root = DotfileNode(root_path)
        stack = [root]

        while stack:
            current_node = stack.pop()
            if not current_node.path.exists():
                continue

            if self._is_dotfile(current_node.path):
                current_node.is_dotfile = True

            if current_node.path.suffix == '.nix':
                current_node.is_nix_config = True

            if current_node.path.is_dir():
                for item in current_node.path.iterdir():
                    # Avoid infinite recursion in case of symlinks pointing upwards
                    if item.is_symlink() and item.resolve().is_dir():
                        continue
                    child_node = DotfileNode(item)
                    current_node.children.append(child_node)
                    stack.append(child_node)

        return root

    def _is_dotfile(self, path: Path) -> bool:
        """
        Determines if a given path is a dotfile or config.

        Args:
            path (Path): Path to check.

        Returns:
            bool: True if dotfile/config, False otherwise.
        """
        name = path.name.lower()
        known_config_dirs = {
            'oh-my-zsh', 'zsh', 'bash', 'fish', 'tmux', 'kitty', 'alacritty', 'wezterm',
            'i3', 'hypr', 'sway', 'awesome', 'polybar', 'waybar',
            'nvim', 'neofetch', 'rofi', 'dunst', 'picom', 'flameshot',
            'gtk-3.0', 'gtk-4.0', 'themes', 'icons',
            'fontconfig', 'swaylock', 'hyprlock', 'hypridle'
        }
        asset_dirs = {
            'wallpapers', 'backgrounds', 'icons', 'themes', 'fonts', 'assets',
            'styles', 'shaders', 'images', 'readme_resources', 'stickers'
        }
        shell_config_dirs = {
            'plugins', 'themes', 'custom', 'lib', 'tools', 'templates'
        }
        dotfile_patterns = [
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
        # Check known config directories
        if name in known_config_dirs:
            return True
        # Check asset directories
        if name in asset_dirs:
            return True
        # Check shell config directories
        parent = path.parent.name.lower()
        if parent in known_config_dirs and name in shell_config_dirs:
            return True
        # Check if parent is .config or config
        if parent in ['.config', 'config']:
            return True
        # Check against dotfile patterns
        for pattern in dotfile_patterns:
            if re.search(pattern, name):
                return True
        return False

    def find_dependencies(self, node: DotfileNode) -> None:
        """
        Recursively finds dependencies in the tree.

        Args:
            node (DotfileNode): Node to analyze.
        """
        if node.path.is_file():
            dependencies = self._parse_dependencies(node.path)
            node.dependencies.update(dependencies)

        for child in node.children:
            self.find_dependencies(child)

    def _parse_dependencies(self, file_path: Path) -> Set[str]:
        """
        Parses a file to find dependencies based on its format.

        Args:
            file_path (Path): Path to the file.

        Returns:
            Set[str]: Set of dependencies found.
        """
        dependencies = set()
        try:
            if file_path.suffix == '.json':
                dependencies = self.parse_json_dependencies(file_path)
            elif file_path.suffix == '.toml':
                dependencies = self.parse_toml_dependencies(file_path)
            elif file_path.suffix in ['.yaml', '.yml']:
                dependencies = self.parse_yaml_dependencies(file_path)
            else:
                content = file_path.read_text(encoding='utf-8').lower()
                if any(indicator in content for indicator in ['requires', 'depends', 'dependencies']):
                    packages = set(self.package_regex.findall(content))
                    dependencies.update(packages)
        except Exception as e:
            self.logger.warning(f"Could not analyze dependencies in {file_path}: {e}")
        return dependencies

    def parse_json_dependencies(self, file_path: Path) -> Set[str]:
        """
        Parses JSON files for dependencies.

        Args:
            file_path (Path): Path to the JSON file.

        Returns:
            Set[str]: Set of dependencies found.
        """
        dependencies = set()
        try:
            data = json.loads(file_path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                for key in ['dependencies', 'devDependencies']:
                    if key in data and isinstance(data[key], dict):
                        dependencies.update(data[key].keys())
        except json.JSONDecodeError as e:
            self.logger.warning(f"JSON decode error in {file_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Error parsing JSON dependencies in {file_path}: {e}")
        return dependencies

    def parse_toml_dependencies(self, file_path: Path) -> Set[str]:
        """
        Parses TOML files for dependencies.

        Args:
            file_path (Path): Path to the TOML file.

        Returns:
            Set[str]: Set of dependencies found.
        """
        dependencies = set()
        try:
            data = toml.loads(file_path.read_text(encoding='utf-8'))
            for section in ['dependencies', 'build-dependencies', 'dev-dependencies']:
                if section in data and isinstance(data[section], dict):
                    dependencies.update(data[section].keys())
        except toml.TomlDecodeError as e:
            self.logger.warning(f"TOML decode error in {file_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Error parsing TOML dependencies in {file_path}: {e}")
        return dependencies

    def parse_yaml_dependencies(self, file_path: Path) -> Set[str]:
        """
        Parses YAML files for dependencies.

        Args:
            file_path (Path): Path to the YAML file.

        Returns:
            Set[str]: Set of dependencies found.
        """
        dependencies = set()
        try:
            data = yaml.safe_load(file_path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                for key in ['dependencies', 'requires']:
                    if key in data:
                        if isinstance(data[key], list):
                            dependencies.update(data[key])
                        elif isinstance(data[key], dict):
                            dependencies.update(data[key].keys())
        except yaml.YAMLError as e:
            self.logger.warning(f"YAML parse error in {file_path}: {e}")
        except Exception as e:
            self.logger.warning(f"Error parsing YAML dependencies in {file_path}: {e}")
        return dependencies
