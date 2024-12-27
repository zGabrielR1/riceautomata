import os
import re
import json
from typing import Dict, List, Tuple
from src.utils import setup_logger

logger = setup_logger()

class DotfileAnalyzer:
    """Handles the analysis and scoring of potential dotfile directories."""
    
    def __init__(self, rules_config=None, verbose=False):
        self.rules_config = rules_config or {}
        self.verbose = verbose
        self.logger = logger
        self.dependency_db = {}  # Initialize dependency database
        self._init_scoring_rules()
        
    def _init_scoring_rules(self):
        """Initialize scoring rules with default values."""
        self.name_patterns = {
            r'^\.(config|conf)$': 10,
            r'^\.(vim|emacs|bash|zsh)$': 8,
            r'^\..*rc$': 7,
            r'^\.[A-Za-z0-9-_]+$': 5
        }
        
        self.content_patterns = {
            r'(vim|emacs|bash|zsh)rc': 8,
            r'config\.(yaml|json|toml)': 7,
            r'\.gitconfig': 6,
            r'environment': 5
        }
        
        # Update with custom rules if provided
        if self.rules_config:
            self.name_patterns.update(self.rules_config.get('name_patterns', {}))
            self.content_patterns.update(self.rules_config.get('content_patterns', {}))
            
    def analyze_directory(self, directory: str) -> Dict[str, Dict]:
        """
        Analyze a directory and its contents to identify potential dotfile directories.
        
        Args:
            directory: Path to the directory to analyze
            
        Returns:
            Dict containing analysis results for each subdirectory
        """
        results = {}
        try:
            for root, dirs, files in os.walk(directory):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    score = self._score_directory(dir_path)
                    metadata = self._collect_metadata(dir_path)
                    
                    if score > 0:
                        results[dir_path] = {
                            'score': score,
                            'metadata': metadata,
                            'confidence': self._calculate_confidence(score, metadata),
                            'dependencies': self._extract_dependencies(dir_path),
                            'themes': self._detect_themes(dir_path)
                        }
                        
                        if self.verbose:
                            self.logger.debug(f"Directory {dir_path} scored {score} points")
                            
        except Exception as e:
            self.logger.error(f"Error analyzing directory {directory}: {e}")
            
        return results
        
    def _score_directory(self, directory: str) -> float:
        """
        Calculate a score for a directory based on its name and contents.
        
        Args:
            directory: Path to the directory to score
            
        Returns:
            Float score indicating likelihood of being a dotfile directory
        """
        score = 0.0
        
        # Score based on directory name
        dir_name = os.path.basename(directory)
        score += self._score_dir_name(dir_name)
        
        # Score based on contents
        score += self._score_dotfile_content(directory)
        
        return score
        
    def _score_dir_name(self, dir_name: str) -> float:
        """Score a directory name based on patterns."""
        score = 0.0
        for pattern, points in self.name_patterns.items():
            if re.search(pattern, dir_name, re.IGNORECASE):
                score += points
                if self.verbose:
                    self.logger.debug(f"Directory name {dir_name} matched pattern {pattern} (+{points} points)")
        return score
        
    def _score_dotfile_content(self, directory: str) -> float:
        """Score directory contents based on patterns."""
        score = 0.0
        try:
            for root, _, files in os.walk(directory):
                for file_name in files:
                    file_path = os.path.join(root, file_name)
                    
                    # Score based on file name patterns
                    for pattern, points in self.content_patterns.items():
                        if re.search(pattern, file_name, re.IGNORECASE):
                            score += points
                            if self.verbose:
                                self.logger.debug(f"File {file_name} matched pattern {pattern} (+{points} points)")
                            
                    # Score based on file content (first few lines)
                    score += self._analyze_file_content(file_path)
                    
        except Exception as e:
            self.logger.error(f"Error scoring directory contents {directory}: {e}")
            
        return score
        
    def _analyze_file_content(self, file_path: str, max_lines: int = 10) -> float:
        """Analyze the content of a file for dotfile indicators."""
        score = 0.0
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f):
                    if i >= max_lines:
                        break
                    
                    # Look for common dotfile indicators in content
                    if re.search(r'(export|alias|source|set\s+[-\w]+)', line):
                        score += 2
                    elif re.search(r'(config|settings|preferences)', line, re.IGNORECASE):
                        score += 1
                        
        except Exception as e:
            if self.verbose:
                self.logger.debug(f"Could not analyze file {file_path}: {e}")
                
        return score
        
    def _collect_metadata(self, directory: str) -> Dict:
        """Collect metadata about the directory."""
        try:
            return {
                'file_count': sum(len(files) for _, _, files in os.walk(directory)),
                'total_size': sum(
                    os.path.getsize(os.path.join(root, file))
                    for root, _, files in os.walk(directory)
                    for file in files
                ),
                'last_modified': max(
                    os.path.getmtime(os.path.join(root, file))
                    for root, _, files in os.walk(directory)
                    for file in files
                ) if any(os.walk(directory))[2] else 0,
                'depth': len(os.path.relpath(directory).split(os.sep))
            }
        except Exception as e:
            self.logger.error(f"Error collecting metadata for {directory}: {e}")
            return {}
            
    def _calculate_confidence(self, score: float, metadata: Dict) -> float:
        """Calculate confidence score based on directory score and metadata."""
        confidence = min(score / 100.0, 1.0)  # Base confidence on score
        
        # Adjust confidence based on metadata
        if metadata.get('file_count', 0) > 10:
            confidence *= 1.2
        if metadata.get('depth', 0) > 3:
            confidence *= 0.8
            
        return min(confidence, 1.0)  # Ensure confidence is between 0 and 1

    def _extract_dependencies(self, dir_path: str) -> List[str]:
        """Extract potential dependencies from files in a directory using more robust methods."""
        dependencies = set()
        patterns = {
            "import_require": r"(?:require|import)\s*\(?\s*['\"]([\w-]+)['\"]\s*\)?",
            "depends_on": r"depends_on\s+['\"]([\w-]+)['\"]",
            "install_use_package": r"(?:install|use)_package\s*\(\s*['\"]([\w-]+)['\"]\s*\)",
            "executables": r"\b(fzf|rg|ag|npm|pip|cargo)\b",
        }

        for root, _, files in os.walk(dir_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        for pattern_name, pattern in patterns.items():
                            matches = re.findall(pattern, content, re.IGNORECASE)
                            for match in matches:
                                if match in self.dependency_db:
                                    dependencies.add(self.dependency_db[match])
                                else:
                                    dependencies.add(match)
                except UnicodeDecodeError:
                    if self.verbose:
                        self.logger.debug(f"Skipping binary file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error analyzing file {file_path}: {e}")

        return list(dependencies)

    def _detect_themes(self, dir_path: str) -> List[str]:
        """
        Detect potential themes based on directory structure and file names.
        """
        themes = []
        if os.path.basename(dir_path).lower() in ("themes", "colors", "styles"):
            for item in os.listdir(dir_path):
                if os.path.isdir(os.path.join(dir_path, item)):
                    themes.append(item)
        return themes

    def analyze_dependencies(self, config_file: str) -> Dict[str, List[str]]:
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
        
    def _parse_json_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
            
    def _parse_yaml_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
            
    def _parse_toml_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
            
    def _analyze_shell_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
                
    def _detect_de_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
                
    def _detect_font_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
                
    def _detect_service_dependencies(self, content: str, dependencies: Dict[str, set]) -> None:
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
