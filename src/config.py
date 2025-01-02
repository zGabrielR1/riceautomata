# src/config.py
from .exceptions import ConfigurationError, ValidationError
import json
import os
from .utils import sanitize_path, setup_logger
from typing import Dict, Any, Optional
import jsonschema
from datetime import datetime

logger = setup_logger()
DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/riceautomator")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, "config.json")

# Configuration schema for validation
PACKAGE_MANAGERS_SCHEMA = {
    "type": "object",
    "properties": {
        "preferred": {"type": ["string", "null"]},
        "installed": {"type": "array", "items": {"type": "string"}},
        "auto_install": {"type": "boolean"}
    },
    "required": ["preferred", "installed", "auto_install"]
}
RICE_SCHEMA = {
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


CONFIG_SCHEMA = {
    "type": "object",
    "properties": {
        "package_managers": PACKAGE_MANAGERS_SCHEMA,
        "rices": {
            "type": "object",
            "additionalProperties": RICE_SCHEMA
         }
    },
    "required": ["package_managers", "rices"]
}

class ConfigManager:

    def __init__(self):
        self.config_dir = os.path.expanduser("~/.config/riceautomata")
        self.config_file = os.path.join(self.config_dir, "config.json")
        self._ensure_config_dir()
        self.config = self._load_config()

    def _ensure_config_dir(self):
        """Ensure the config directory exists."""
        os.makedirs(self.config_dir, exist_ok=True)

    def _load_config(self):
        """Load the configuration file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                return {'rices': {}}
        return {'rices': {}}

    def _save_config(self):
        """Save the configuration file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving config: {e}")

    def get_rice_config(self, repository_name):
        """Get configuration for a specific rice."""
        return self.config['rices'].get(repository_name)

    def add_rice_config(self, repository_name, config):
        """Add or update configuration for a rice."""
        if 'rices' not in self.config:
            self.config['rices'] = {}
            
        # Convert paths to absolute paths
        if 'local_directory' in config:
            config['local_directory'] = os.path.abspath(config['local_directory'])
            
        # Update existing config or add new one
        if repository_name in self.config['rices']:
            self.config['rices'][repository_name].update(config)
        else:
            self.config['rices'][repository_name] = config
            
        self._save_config()

    def create_profile(self, repository_name: str, profile_name: str) -> None:
        """Creates a new profile for a repository."""
        try:
            if repository_name not in self.config['rices']:
                raise ConfigurationError(f"Repository {repository_name} not found")
            
            rice_config = self.config['rices'][repository_name]
            if 'profiles' not in rice_config:
                rice_config['profiles'] = {}
            
            if profile_name in rice_config['profiles']:
                raise ConfigurationError(f"Profile {profile_name} already exists")
            
            rice_config['profiles'][profile_name] = {
                'name': profile_name,
                'active': False,
                'created_at': datetime.now().isoformat(),
                'configs': []
            }
            
            self._save_config()
        except Exception as e:
            raise ConfigurationError(f"Failed to create profile: {e}")

    def switch_profile(self, repository_name: str, profile_name: str) -> None:
        """Switches to a different profile for a repository."""
        try:
            if repository_name not in self.config['rices']:
                raise ConfigurationError(f"Repository {repository_name} not found")
            
            rice_config = self.config['rices'][repository_name]
            if 'profiles' not in rice_config or profile_name not in rice_config['profiles']:
                raise ConfigurationError(f"Profile {profile_name} not found")
            
            # Deactivate current active profile
            current_active = rice_config.get('active_profile')
            if current_active and current_active in rice_config['profiles']:
                rice_config['profiles'][current_active]['active'] = False
            
            # Activate new profile
            rice_config['profiles'][profile_name]['active'] = True
            rice_config['active_profile'] = profile_name
            
            self._save_config()
        except Exception as e:
            raise ConfigurationError(f"Failed to switch profile: {e}")

    def get_active_profile(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """Gets the active profile configuration for a repository."""
        try:
            rice_config = self.config['rices'].get(repository_name)
            if not rice_config:
                return None
            
            active_profile = rice_config.get('active_profile')
            if not active_profile:
                return None
                
            return rice_config.get('profiles', {}).get(active_profile)
        except Exception as e:
            logger.error(f"Failed to get active profile: {e}")
            return None

    def get_package_manager_config(self):
        """Gets the package manager configuration."""
        if 'package_managers' not in self.config:
            self.config['package_managers'] = {
                'preferred': None,
                'installed': [],
                'auto_install': False
            }
            self._save_config()
        return self.config['package_managers']

    def set_package_manager_config(self, preferred=None, installed=None, auto_install=None):
        """Updates the package manager configuration."""
        if 'package_managers' not in self.config:
             self.config['package_managers'] = {
                'preferred': None,
                'installed': [],
                'auto_install': False
            }
        config = self.config['package_managers']
        if preferred is not None:
            config['preferred'] = preferred
        if installed is not None:
            config['installed'] = installed
        if auto_install is not None:
            config['auto_install'] = auto_install
        self._save_config()
    
    def set_rice_config(self, repository_name, key, value):
        """Sets a value for a specific key for the rice configuration."""
        if 'rices' not in self.config:
            self.config['rices'] = {}
        if repository_name not in self.config['rices']:
            self.config['rices'][repository_name] = {}
        self.config['rices'][repository_name][key] = value
        self._save_config()

    def _validate_config(self, config_data: Dict[str, Any]) -> None:
        """Validates the configuration data against the schema."""
        try:
            jsonschema.validate(instance=config_data, schema=CONFIG_SCHEMA)
        except jsonschema.exceptions.ValidationError as e:
            raise ValidationError(f"Configuration validation failed: {e.message}")