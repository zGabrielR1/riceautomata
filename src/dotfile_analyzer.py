import os
import re
import math
from src.utils import setup_logger

class DotfileAnalyzer:
    """Handles the analysis and scoring of potential dotfile directories."""
    
    def __init__(self, rules_config=None, verbose=False):
        self.rules_config = rules_config or {}
        self.verbose = verbose
        self.logger = setup_logger(verbose)

    def _score_dir_name(self, dir_name):
        """
        Score a directory name based on how likely it is to contain dotfiles.
        Returns a tuple of (score, metadata) where metadata contains additional context.
        """
        score = 0
        metadata = {
            "category": None,
            "confidence": "low",
            "matched_rules": []
        }

        # Common dotfile directory patterns
        known_config_dirs = {
            # Desktop Environment / Window Manager configs
            "hypr": ("de/wm", 4), "sway": ("de/wm", 4), "i3": ("de/wm", 4),
            "awesome": ("de/wm", 4), "bspwm": ("de/wm", 4), "dwm": ("de/wm", 4),
            "xmonad": ("de/wm", 4), "qtile": ("de/wm", 4), "openbox": ("de/wm", 4),
            
            # Status bars and widgets
            "waybar": ("statusbar", 4), "polybar": ("statusbar", 4), 
            "eww": ("widgets", 4), "ags": ("widgets", 4),
            
            # Terminal emulators
            "alacritty": ("terminal", 4), "kitty": ("terminal", 4), 
            "wezterm": ("terminal", 4), "foot": ("terminal", 4),
            
            # Shell configurations
            "zsh": ("shell", 4), "bash": ("shell", 4), "fish": ("shell", 4),
            
            # Text editors and IDEs
            "nvim": ("editor", 4), "vim": ("editor", 4), "emacs": ("editor", 4),
            "vscode": ("editor", 4), "code": ("editor", 4),
            
            # System utilities
            "dunst": ("notification", 3), "rofi": ("launcher", 3),
            "picom": ("compositor", 3), "sxhkd": ("hotkeys", 3),
            
            # Theming and appearance
            "gtk-2.0": ("theme", 3), "gtk-3.0": ("theme", 3), "gtk-4.0": ("theme", 3),
            "themes": ("theme", 3), "icons": ("theme", 3), "fonts": ("theme", 3),
            
            # Common config directories
            "config": ("general", 2), ".config": ("general", 3),
            
            # Development tools
            "git": ("dev", 2), "npm": ("dev", 2), "yarn": ("dev", 2),
            "cargo": ("dev", 2), "pip": ("dev", 2)
        }

        # Check against known config directories
        if dir_name in known_config_dirs:
            category, points = known_config_dirs[dir_name]
            score += points
            metadata["category"] = category
            metadata["matched_rules"].append(f"known_config_dir:{dir_name}")
            metadata["confidence"] = "high" if points >= 4 else "medium"

        # Check custom rules from config
        for rule in self.rules_config.get('rules', []):
            if rule.get('regex'):
                try:
                    if re.search(rule['regex'], dir_name):
                        score += 3
                        metadata["matched_rules"].append(f"custom_rule:{rule['regex']}")
                except Exception as e:
                    self.logger.error(f"Error with rule regex: {rule['regex']}. Error: {e}")
            elif dir_name == rule.get('name'):
                score += 3
                metadata["matched_rules"].append(f"custom_rule_name:{rule['name']}")

        # Common naming patterns
        if dir_name.startswith('.'):
            score += 2
            metadata["matched_rules"].append("dotfile_prefix")
        elif dir_name.startswith('dot-'):
            score += 2
            metadata["matched_rules"].append("dot_prefix")
        elif dir_name.endswith('rc'):
            score += 2
            metadata["matched_rules"].append("rc_suffix")
        elif dir_name.endswith('config'):
            score += 2
            metadata["matched_rules"].append("config_suffix")

        # Update confidence based on final score
        if score >= 4:
            metadata["confidence"] = "high"
        elif score >= 2:
            metadata["confidence"] = "medium"

        return score, metadata

    def _score_dotfile_content(self, dir_path):
        """
        Score directory contents based on how likely they are to be dotfiles.
        Returns a tuple of (score, metadata) where metadata contains detailed analysis.
        """
        score = 0
        metadata = {
            "file_types": {},
            "config_matches": [],
            "potential_dependencies": set(),
            "matched_patterns": set()
        }

        # Common configuration file extensions
        config_extensions = {
            '.conf': 2, '.config': 2, '.cfg': 2, '.ini': 2,
            '.json': 1.5, '.yaml': 1.5, '.yml': 1.5, '.toml': 1.5,
            '.rc': 1.5, '.profile': 1.5
        }

        # Configuration keywords to look for
        config_keywords = {
            "config": 0.5, "settings": 0.5, "preferences": 0.5,
            "window": 0.3, "workspace": 0.3, "keybind": 0.3,
            "theme": 0.3, "color": 0.3, "font": 0.3,
            "alias": 0.3, "export": 0.3, "PATH": 0.3
        }

        try:
            for root, dirs, files in os.walk(dir_path):
                # Skip hidden directories except .config
                dirs[:] = [d for d in dirs if not d.startswith('.') or d == '.config']
                
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, dir_path)
                    
                    # Track file extension
                    ext = os.path.splitext(file)[1].lower()
                    metadata["file_types"][ext] = metadata["file_types"].get(ext, 0) + 1

                    # Score based on extension
                    if ext in config_extensions:
                        score += config_extensions[ext]
                        metadata["matched_patterns"].add(f"extension:{ext}")

                    # Analyze file content if it's a text file and not too large
                    if ext in config_extensions and os.path.getsize(file_path) < 500000:
                        try:
                            with open(file_path, 'r', errors='ignore') as f:
                                content = f.read(4096).lower()  # Read first 4KB
                                
                                # Look for config keywords
                                for keyword, points in config_keywords.items():
                                    if keyword in content:
                                        score += points
                                        metadata["config_matches"].append(f"{rel_path}:{keyword}")

                                # Look for potential dependencies
                                if re.search(r'(require|import|use|include)\s+[\'"]([^\'"])+[\'"]', content):
                                    metadata["potential_dependencies"].add(rel_path)
                                    score += 0.5

                        except (IOError, UnicodeDecodeError):
                            continue

        except Exception as e:
            self.logger.error(f"Error analyzing directory {dir_path}: {e}")
            return 0, metadata

        # Normalize score based on file count
        file_count = sum(metadata["file_types"].values())
        if file_count > 10:
            score = score / (math.log2(file_count) + 1)

        return score, metadata

    def analyze_directory(self, dir_path):
        """
        Analyze a directory to determine if it's likely to contain dotfiles.
        Returns a tuple of (is_likely, confidence, metadata)
        """
        dir_name = os.path.basename(dir_path)
        name_score, name_metadata = self._score_dir_name(dir_name)
        content_score, content_metadata = self._score_dotfile_content(dir_path)
        
        total_score = name_score + content_score
        
        # Combine metadata
        metadata = {
            "name_analysis": name_metadata,
            "content_analysis": content_metadata,
            "total_score": total_score,
            "name_score": name_score,
            "content_score": content_score
        }
        
        # Determine confidence level
        if total_score >= 6:
            confidence = "high"
        elif total_score >= 3:
            confidence = "medium"
        else:
            confidence = "low"
            
        metadata["confidence"] = confidence
        
        # Log detailed analysis if verbose
        if self.verbose:
            self.logger.debug(f"Dotfile directory analysis for {dir_path}:")
            self.logger.debug(f"Name score: {name_score} ({name_metadata['confidence']})")
            self.logger.debug(f"Content score: {content_score}")
            self.logger.debug(f"Total score: {total_score} ({confidence})")
            if name_metadata["matched_rules"]:
                self.logger.debug(f"Matched rules: {', '.join(name_metadata['matched_rules'])}")
            if content_metadata["matched_patterns"]:
                self.logger.debug(f"Matched patterns: {len(content_metadata['matched_patterns'])}")
            if content_metadata["config_matches"]:
                self.logger.debug(f"Config matches: {len(content_metadata['config_matches'])}")
            if content_metadata["potential_dependencies"]:
                self.logger.debug(f"Potential dependencies found in: {len(content_metadata['potential_dependencies'])} files")
        
        return total_score >= 2, confidence, metadata

    def categorize_directory(self, dir_path):
        """Categorize a dotfile directory based on its content and name."""
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
            return "config"
