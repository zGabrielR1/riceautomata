# dotfilemanager/config.py

import json
from pathlib import Path
from typing import Any, Dict, Optional
import logging

from .exceptions import ConfigurationError
from .utils import create_timestamp

class ConfigManager:
    """
    Manages loading and saving configurations.
    """
    def __init__(self, config_path: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        """
        Initializes the ConfigManager.

        Args:
            config_path (Optional[Path]): Path to the configuration file.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')
        self.config_path = config_path or Path.home() / '.dotfilemanager' / 'config.json'
        self.config_data: Dict[str, Any] = {}
        self.load_config()

    def load_config(self) -> None:
        """
        Loads the configuration from the config file.
        """
        try:
            if self.config_path.exists():
                with self.config_path.open('r', encoding='utf-8') as f:
                    self.config_data = json.load(f)
                    self.logger.debug(f"Loaded configuration from {self.config_path}")
            else:
                self.config_data = {'rices': {}}
                self.logger.info(f"No configuration file found at {self.config_path}. Initialized with empty config.")
                self.save_config()
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in configuration file: {e}")
            raise ConfigurationError(f"Invalid JSON in configuration file: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def save_config(self) -> None:
        """
        Saves the current configuration to the config file.
        """
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open('w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
                self.logger.debug(f"Saved configuration to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Failed to save configuration: {e}")

    def add_rice_config(self, repository_name: str, config: Dict[str, Any]) -> None:
        """
        Adds or updates a rice configuration.

        Args:
            repository_name (str): Name of the repository.
            config (Dict[str, Any]): Configuration data.
        """
        self.config_data.setdefault('rices', {})[repository_name] = config
        self.save_config()

    def get_rice_config(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the configuration for a specific rice.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[Dict[str, Any]]: Configuration data if exists, else None.
        """
        return self.config_data.get('rices', {}).get(repository_name)

    def create_profile(self, repository_name: str, profile_name: str, description: str = "") -> None:
        """
        Creates a new profile for a given rice.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile.
            description (str): Description of the profile.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            profiles = rice_config.setdefault('profiles', {})
            if profile_name in profiles:
                self.logger.warning(f"Profile '{profile_name}' already exists for repository '{repository_name}'.")
            else:
                profiles[profile_name] = {
                    'description': description,
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
                        'custom_scripts': [],
                        'shell': "bash"
                    },
                    'custom_extras_paths': {}
                }
                self.save_config()
                self.logger.debug(f"Created profile '{profile_name}' for repository '{repository_name}'.")
        else:
            self.logger.error(f"Rice configuration for '{repository_name}' not found.")

    def get_profiles(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves all profiles for a specific repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[Dict[str, Any]]: Profiles data if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            return rice_config.get('profiles', {})
        return None

    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Retrieves all profiles across all repositories.

        Returns:
            Dict[str, Dict[str, Any]]: All profiles categorized by repository.
        """
        return {repo: config.get('profiles', {}) for repo, config in self.config_data.get('rices', {}).items()}

    def get_active_profile(self, repository_name: str) -> Optional[str]:
        """
        Retrieves the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[str]: Name of the active profile if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            return rice_config.get('active_profile')
        return None

    def set_active_profile(self, repository_name: str, profile_name: str) -> bool:
        """
        Sets the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile to set as active.

        Returns:
            bool: True if successful, False otherwise.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config and 'profiles' in rice_config and profile_name in rice_config['profiles']:
            rice_config['active_profile'] = profile_name
            self.save_config()
            self.logger.debug(f"Set active profile to '{profile_name}' for repository '{repository_name}'.")
            return True
        self.logger.error(f"Profile '{profile_name}' not found for repository '{repository_name}'.")
        return False

    def get_all_profiles_dict(self) -> Dict[str, Any]:
        """
        Retrieves all profiles in a structured dictionary.

        Returns:
            Dict[str, Any]: All profiles categorized by repository.
        """
        return self.config_data.get('rices', {})

    def remove_rice_config(self, repository_name: str) -> None:
        """
        Removes a rice configuration.

        Args:
            repository_name (str): Name of the repository.  
        """
        if 'rices' in self.config_data and repository_name in self.config_data['rices']:
            del self.config_data['rices'][repository_name]
            self.save_config()
            self.logger.debug(f"Removed rice configuration for '{repository_name}'")
        else:
            self.logger.warning(f"No rice configuration found for '{repository_name}' to remove.")