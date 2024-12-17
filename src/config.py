from src.exceptions import ConfigurationError, ValidationError
import json
import os
from src.utils import sanitize_path, setup_logger
from typing import Dict, Any, Optional
import jsonschema

logger = setup_logger()
DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/riceautomator")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, "config.json")

# Configuration schema for validation
CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "package_managers": {
            "type": "object",
            "properties": {
                "preferred": {"type": ["string", "null"]},
                "installed": {"type": "array", "items": {"type": "string"}},
                "auto_install": {"type": "boolean"}
            },
            "required": ["preferred", "installed", "auto_install"]
        },
        "rices": {
            "type": "object",
            "additionalProperties": {
                "type": "object",
                "properties": {
                    "repository_url": {"type": "string"},
                    "local_directory": {"type": "string"},
                    "profile": {"type": "string", "default": "default"},
                    "active_profile": {"type": "string", "default": "default"},
                    "profiles": {
                        "type": "object",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "dotfile_directories": {"type": "object"},
                                "dependencies": {"type": "array"},
                                "script_config": {"type": "object"},
                                "custom_extras_paths": {"type": "object"}
                            }
                        }
                    }
                },
                "required": ["repository_url", "local_directory"]
            }
        }
    },
    "required": ["package_managers", "rices"]
}

class ConfigManager:

    def __init__(self, config_dir=DEFAULT_CONFIG_DIR, config_file=DEFAULT_CONFIG_FILE):
        self.config_dir = sanitize_path(config_dir)
        self.config_file = sanitize_path(config_file)
        self.config_data = {}
        self._ensure_config_dir()
        self._load_config()

    def _ensure_config_dir(self):
        """Creates the config directory if it doesn't exist."""
        try:
            if not os.path.exists(self.config_dir):
                os.makedirs(self.config_dir, exist_ok=True)
        except Exception as e:
            raise ConfigurationError(f"Failed to create config directory: {e}")

    def _validate_config(self, config_data: Dict[str, Any]) -> None:
        """Validates the configuration data against the schema."""
        try:
            jsonschema.validate(instance=config_data, schema=CONFIG_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Configuration validation failed: {e.message}")

    def _load_config(self):
        """Loads the configuration data from the JSON file with validation."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config_data = json.load(f)
                    self._validate_config(self.config_data)
            else:
                self.config_data = {
                    'package_managers': {
                        'preferred': None,
                        'installed': [],
                        'auto_install': False
                    },
                    'rices': {}
                }
                self._save_config()
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def _save_config(self):
        """Saves the configuration data to the JSON file with validation."""
        try:
            self._validate_config(self.config_data)
            with open(self.config_file, 'w') as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def create_profile(self, repository_name: str, profile_name: str) -> None:
        """Creates a new profile for a repository."""
        try:
            if repository_name not in self.config_data['rices']:
                raise ConfigurationError(f"Repository {repository_name} not found")
            
            rice_config = self.config_data['rices'][repository_name]
            if 'profiles' not in rice_config:
                rice_config['profiles'] = {}
            
            if profile_name in rice_config['profiles']:
                raise ConfigurationError(f"Profile {profile_name} already exists")
            
            rice_config['profiles'][profile_name] = {
                'dotfile_directories': {},
                'dependencies': [],
                'script_config': {},
                'custom_extras_paths': {}
            }
            self._save_config()
        except Exception as e:
            raise ConfigurationError(f"Failed to create profile: {e}")

    def switch_profile(self, repository_name: str, profile_name: str) -> None:
        """Switches to a different profile for a repository."""
        try:
            if repository_name not in self.config_data['rices']:
                raise ConfigurationError(f"Repository {repository_name} not found")
            
            rice_config = self.config_data['rices'][repository_name]
            if 'profiles' not in rice_config or profile_name not in rice_config['profiles']:
                raise ConfigurationError(f"Profile {profile_name} not found")
            
            rice_config['active_profile'] = profile_name
            self._save_config()
        except Exception as e:
            raise ConfigurationError(f"Failed to switch profile: {e}")

    def get_active_profile(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """Gets the active profile configuration for a repository."""
        try:
            rice_config = self.config_data['rices'].get(repository_name)
            if not rice_config:
                return None
            
            active_profile = rice_config.get('active_profile', 'default')
            return rice_config.get('profiles', {}).get(active_profile)
        except Exception as e:
            raise ConfigurationError(f"Failed to get active profile: {e}")

    def get_rice_config(self, repository_name):
        """Gets configuration data for a given repository."""
        return self.config_data.get('rices', {}).get(repository_name)

    def add_rice_config(self, repository_name, config):
        """Adds or updates configuration data for a repository."""
        if 'rices' not in self.config_data:
            self.config_data['rices'] = {}
        self.config_data['rices'][repository_name] = config
        self._save_config()

    def get_package_manager_config(self):
        """Gets the package manager configuration."""
        if 'package_managers' not in self.config_data:
            self.config_data['package_managers'] = {
                'preferred': None,
                'installed': [],
                'auto_install': False
            }
            self._save_config()
        return self.config_data['package_managers']

    def set_package_manager_config(self, preferred=None, installed=None, auto_install=None):
        """Updates the package manager configuration."""
        if 'package_managers' not in self.config_data:
             self.config_data['package_managers'] = {
                'preferred': None,
                'installed': [],
                'auto_install': False
            }
        config = self.config_data['package_managers']
        if preferred is not None:
            config['preferred'] = preferred
        if installed is not None:
            config['installed'] = installed
        if auto_install is not None:
            config['auto_install'] = auto_install
        self._save_config()
    
    def set_rice_config(self, repository_name, key, value):
        """Sets a value for a specific key for the rice configuration."""
        if 'rices' not in self.config_data:
            self.config_data['rices'] = {}
        if repository_name not in self.config_data['rices']:
            self.config_data['rices'][repository_name] = {}
        self.config_data['rices'][repository_name][key] = value
        self._save_config()