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
        self.config_type: Optional[str] = None  # Stores the type of config (e.g., 'config', 'local', 'themes')
        self.target_path: Optional[Path] = None  # Where this dotfile should be installed

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
        
        # Common configuration locations
        self.config_locations = {
            'config': Path.home() / '.config',
            'local': Path.home() / '.local',
            'home': Path.home(),
            'themes': Path.home() / '.themes',
            'icons': Path.home() / '.icons',
            'fonts': Path.home() / '.local/share/fonts',
            'wallpapers': Path.home() / '.local/share/wallpapers',
        }
        
        # Known configuration directories and their target locations
        self.known_config_dirs = {
            # Shell configs
            'oh-my-zsh': ('home', '.oh-my-zsh'),
            'zsh': ('home', '.zsh'),
            'bash': ('home', '.bash'),
            'fish': ('config', 'fish'),
            
            # Terminal emulators
            'kitty': ('config', 'kitty'),
            'alacritty': ('config', 'alacritty'),
            'wezterm': ('config', 'wezterm'),
            
            # Window managers and desktop environment
            'i3': ('config', 'i3'),
            'hypr': ('config', 'hypr'),
            'sway': ('config', 'sway'),
            'awesome': ('config', 'awesome'),
            'polybar': ('config', 'polybar'),
            'waybar': ('config', 'waybar'),
            
            # Applications
            'nvim': ('config', 'nvim'),
            'neofetch': ('config', 'neofetch'),
            'rofi': ('config', 'rofi'),
            'dunst': ('config', 'dunst'),
            'picom': ('config', 'picom'),
            'flameshot': ('config', 'flameshot'),
            
            # Theme related
            'gtk-3.0': ('config', 'gtk-3.0'),
            'gtk-4.0': ('config', 'gtk-4.0'),
            'themes': ('themes', ''),
            'icons': ('icons', ''),
            'wallpapers': ('wallpapers', ''),
            
            # System configs
            'fontconfig': ('config', 'fontconfig'),
            'swaylock': ('config', 'swaylock'),
            'hyprlock': ('config', 'hyprlock'),
            'hypridle': ('config', 'hypridle'),
        }
        
        # Asset directories that should be preserved
        self.asset_dirs = {
            'wallpapers', 'backgrounds', 'icons', 'themes', 'fonts', 'assets',
            'styles', 'shaders', 'images', 'readme_resources', 'stickers'
        }
        
        # Shell configuration directories
        self.shell_config_dirs = {
            'plugins', 'themes', 'custom', 'lib', 'tools', 'templates'
        }
        
        # Dotfile patterns to match
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
            r'\.js$',  # JavaScript configs
            r'\.ts$',  # TypeScript configs
            r'zshrc$',  # Zsh config files
            r'bashrc$',  # Bash config files
            r'\.zsh$',  # Zsh plugin files
            r'\.sh$'   # Shell scripts
        ]

    def build_tree(self, root_path: Path) -> DotfileNode:
        """
        Builds a tree structure of the dotfiles directory.

        Args:
            root_path (Path): Root path of the dotfiles.

        Returns:
            DotfileNode: Root node of the tree.
        """
        root = DotfileNode(root_path)
        stack = [(root, None)]  # (node, parent_type)

        while stack:
            current_node, parent_type = stack.pop()
            if not current_node.path.exists():
                continue

            # Determine if this is a dotfile and its type
            is_dotfile, config_type = self._analyze_path(current_node.path, parent_type)
            current_node.is_dotfile = is_dotfile
            current_node.config_type = config_type

            # Set target path if this is a dotfile
            if is_dotfile:
                current_node.target_path = self._determine_target_path(current_node.path, config_type)

            if current_node.path.is_dir():
                for item in current_node.path.iterdir():
                    # Skip version control directories
                    if item.name in {'.git', '.svn', '.hg'}:
                        continue
                    
                    # Avoid infinite recursion with symlinks
                    if item.is_symlink() and item.resolve().is_dir():
                        resolved_path = item.resolve()
                        if resolved_path.is_relative_to(root_path):
                            continue
                            
                    child_node = DotfileNode(item)
                    current_node.children.append(child_node)
                    stack.append((child_node, config_type or current_node.config_type))

        return root

    def _analyze_path(self, path: Path, parent_type: Optional[str] = None) -> tuple[bool, Optional[str]]:
        """
        Analyzes a path to determine if it's a dotfile and its configuration type.

        Args:
            path (Path): Path to analyze
            parent_type (Optional[str]): Configuration type of the parent directory

        Returns:
            tuple[bool, Optional[str]]: (is_dotfile, config_type)
        """
        name = path.name.lower()
        
        # Check if it's in known config directories
        if name in self.known_config_dirs:
            return True, self.known_config_dirs[name][0]
            
        # Check if it's an asset directory
        if name in self.asset_dirs:
            return True, name
            
        # Check if it's under a known config parent
        if parent_type:
            return True, parent_type
            
        # Check if it's a directory containing .config
        if path.is_dir():
            config_dir = path / '.config'
            if config_dir.exists() and config_dir.is_dir():
                return True, 'config'

        # Check if it's under .config or config
        if '.config' in path.parts or any(part.lower() == 'config' for part in path.parts):
            return True, 'config'
            
        # Check if it's under .local
        if '.local' in path.parts:
            return True, 'local'
            
        # Check against dotfile patterns
        for pattern in self.dotfile_patterns:
            if re.search(pattern, name):
                return True, self._infer_config_type(path)
                
        return False, None

    def _infer_config_type(self, path: Path) -> str:
        """
        Infers the configuration type based on the path structure.

        Args:
            path (Path): Path to analyze

        Returns:
            str: Inferred configuration type
        """
        parts = path.parts
        
        # Check for common locations
        if '.config' in parts:
            return 'config'
        if '.local' in parts:
            return 'local'
        if '.themes' in parts:
            return 'themes'
        if '.icons' in parts:
            return 'icons'
        if any(x.lower() in {'wallpapers', 'backgrounds'} for x in parts):
            return 'wallpapers'
        
        # Default to home directory
        return 'home'

    def _determine_target_path(self, source_path: Path, config_type: Optional[str]) -> Path:
        """
        Determines the target installation path for a dotfile.

        Args:
            source_path (Path): Source path of the dotfile
            config_type (Optional[str]): Type of configuration

        Returns:
            Path: Target installation path
        """
        if not config_type:
            return Path.home() / source_path.name
            
        base_path = self.config_locations.get(config_type, Path.home())
        
        # Handle known config directories
        name = source_path.name.lower()
        if name in self.known_config_dirs:
            config_type, subpath = self.known_config_dirs[name]
            base_path = self.config_locations[config_type]
            if subpath:
                return base_path / subpath
                
        # For .config directory contents
        if config_type == 'config':
            return base_path / source_path.name
            
        # For .local directory contents
        if config_type == 'local':
            if 'share' in source_path.parts:
                return base_path / 'share' / source_path.name
            return base_path / source_path.name
            
        # For theme-related contents
        if config_type in {'themes', 'icons', 'wallpapers'}:
            return base_path / source_path.name
            
        # Default to the base path
        return base_path / source_path.name

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
