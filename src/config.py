# dotfilemanager/config.py
import json
from pathlib import Path
from typing import Any, Dict, Optional, List
import logging

from .exceptions import ConfigurationError
from .utils import create_timestamp

class RepositoryConfig:
    """
    Represents the configuration for a specific rice repository (e.g., from rice.json).
    """

    def __init__(self, repo_config_path: Path, logger: logging.Logger):
        self.logger = logger
        self.path = repo_config_path
        self.config: Dict[str, Any] = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Loads the repository configuration from the JSON file."""
        try:
            if self.path.exists():
                with self.path.open("r", encoding="utf-8") as f:
                    config = json.load(f)
                    self.logger.debug(f"Loaded repository configuration from {self.path}")
                    return config
            else:
                self.logger.warning(f"Repository configuration file not found at {self.path}.")
                return {}  # Default to an empty config if not found
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in repository configuration file: {e}")
            raise ConfigurationError(f"Invalid JSON in repository configuration file: {e}")
        except Exception as e:
            self.logger.error(f"Failed to load repository configuration: {e}")
            raise ConfigurationError(f"Failed to load repository configuration: {e}")

    def get_dotfile_directories(self) -> List[str]:
        """Returns a list of dotfile directories specified in the config."""
        return self.config.get("dotfiles", {}).get("directories", [])
    
    def get_dotfile_categories(self) -> Dict[str, str]:
        """
        Returns a dictionary mapping dotfile directories to their categories.
        """
        return self.config.get("dotfiles", {}).get("categories", {})

    def get_dependencies(self) -> Dict[str, List[str]]:
        """Returns a dictionary of dependencies specified in the config."""
        return self.config.get("dependencies", {})

    def get_scripts(self) -> Dict[str, List[str]]:
        """Returns a dictionary of scripts specified in the config."""
        return self.config.get("scripts", {})

    def get_template_config(self) -> Dict[str, Any]:
        """Returns the template configuration specified in the config."""
        return self.config.get("templates", {})

    def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Returns the configuration for a specific profile.
        """
        return self.config.get("profiles", {}).get(profile_name)

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a configuration value by key.

        Args:
            key: The key of the configuration value.
            default: The default value to return if the key is not found.

        Returns:
            The configuration value if found, otherwise the default value.
        """
        return self.config.get(key, default)

class ConfigManager:
    """
    Manages loading, saving, and updating configurations.
    """

    def __init__(self, config_path: Optional[Path] = None, logger: Optional[logging.Logger] = None):
        """
        Initializes the ConfigManager.

        Args:
            config_path (Optional[Path]): Path to the configuration file.
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger("DotfileManager")
        self.config_path = config_path or Path.home() / ".dotfilemanager" / "config.json"
        self.config_data: Dict[str, Any] = {}
        self._load_config()  # Load config on initialization
    def _load_config(self) -> Dict[str, Any]:
        if self.config_path.exists():
            try:
                with self.config_path.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.logger.debug(f"Loaded configuration from {self.config_path}")
                    return data
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid JSON in config file: {e}")
                raise ConfigurationError(f"Invalid JSON in config file: {e}")
            except Exception as e:
                self.logger.error(f"Failed to load config file: {e}")
                raise ConfigurationError(f"Failed to load config file: {e}")
        else:
            self.logger.debug(f"Config file not found at {self.config_path}. Creating a new one.")
            return {'rices': {}}


    def _save_config(self) -> None:
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with self.config_path.open('w', encoding='utf-8') as f:
                json.dump(self.config_data, f, indent=4)
                self.logger.debug(f"Saved configuration to {self.config_path}")
        except Exception as e:
            self.logger.error(f"Failed to save config file: {e}")
            raise ConfigurationError(f"Failed to save config file: {e}")
            
    def add_rice_config(self, repository_name: str, config: Dict[str, Any]) -> None:
        """
        Adds or updates a rice configuration.

        Args:
            repository_name (str): Name of the repository.
            config (Dict[str, Any]): Configuration data.

        Raises:
            ConfigurationError: If the config is missing required fields.
        """
        # Validate essential fields in the rice config
        required_fields = ['repository_url', 'local_directory']
        missing_fields = [field for field in required_fields if field not in config]
        if missing_fields:
            raise ConfigurationError(f"Rice configuration is missing required fields: {', '.join(missing_fields)}")

        # Validate that profiles, if present, have the correct structure
        if 'profiles' in config:
            if not isinstance(config['profiles'], dict):
                raise ConfigurationError("The 'profiles' field must be a dictionary.")
            for profile_name, profile_config in config['profiles'].items():
                if not isinstance(profile_config, dict):
                    raise ConfigurationError(f"Profile '{profile_name}' must be a dictionary.")
                if 'dotfile_directories' not in profile_config:
                    raise ConfigurationError(f"Profile '{profile_name}' is missing 'dotfile_directories'.")

        self.config_data.setdefault('rices', {})[repository_name] = config
        self._save_config()

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

        Raises:
            ConfigurationError: If the rice configuration is not found or the profile already exists.
        """
        rice_config = self.get_rice_config(repository_name)
        if not rice_config:
            raise ConfigurationError(f"Rice configuration for '{repository_name}' not found.")
        
        profiles = rice_config.setdefault('profiles', {})
        if profile_name in profiles:
            self.logger.warning(f"Profile '{profile_name}' already exists for repository '{repository_name}'.")
            return

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
        self._save_config()
        self.logger.debug(f"Created profile '{profile_name}' for repository '{repository_name}'.")
        

    def get_profile(self, repository_name: str, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a specific profile for a given rice.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile.

        Returns:
            Optional[Dict[str, Any]]: Profile data if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        if rice_config:
            return rice_config.get('profiles', {}).get(profile_name)
        return None

    def get_profiles(self, repository_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves all profiles for a specific repository.

        Args:
            repository_name (str): Name of the repository.

        Returns:
            Optional[Dict[str, Any]]: Profiles data if exists, else None.
        """
        rice_config = self.get_rice_config(repository_name)
        return rice_config.get('profiles', {}) if rice_config else None

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
        return rice_config.get('active_profile') if rice_config else None

    def set_active_profile(self, repository_name: str, profile_name: str) -> bool:
        """
        Sets the active profile for a specific repository.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile to set as active.

        Returns:
            bool: True if successful, False otherwise.

        Raises:
            ConfigurationError: If the rice configuration or the profile is not found.
        """
        rice_config = self.get_rice_config(repository_name)
        if not rice_config:
            raise ConfigurationError(f"Rice configuration for '{repository_name}' not found.")

        if 'profiles' in rice_config and profile_name in rice_config['profiles']:
            rice_config['active_profile'] = profile_name
            self._save_config()
            self.logger.debug(f"Set active profile to '{profile_name}' for repository '{repository_name}'.")
            return True
        else:
            raise ConfigurationError(f"Profile '{profile_name}' not found for repository '{repository_name}'.")

    def update_profile(self, repository_name: str, profile_name: str, profile_data: Dict[str, Any]) -> None:
        """
        Updates an existing profile with new data.

        Args:
            repository_name (str): Name of the repository.
            profile_name (str): Name of the profile to update.
            profile_data (Dict[str, Any]): New data for the profile.

        Raises:
            ConfigurationError: If the rice configuration or the profile is not found.
        """
        rice_config = self.get_rice_config(repository_name)
        if not rice_config:
            raise ConfigurationError(f"Rice configuration for '{repository_name}' not found.")

        profiles = rice_config.setdefault('profiles', {})
        if profile_name in profiles:
            profiles[profile_name].update(profile_data)
            self._save_config()
            self.logger.debug(f"Updated profile '{profile_name}' for repository '{repository_name}'.")
        else:
            raise ConfigurationError(f"Profile '{profile_name}' not found for repository '{repository_name}'.")

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
            self._save_config()
            self.logger.debug(f"Removed rice configuration for '{repository_name}'")
        else:
            self.logger.warning(f"No rice configuration found for '{repository_name}' to remove.")

    def update_config(self, new_config: Dict[str, Any]) -> None:
        """
        Updates the entire config with new data. Use with caution.
        """
        self.config_data = new_config
        self._save_config()


    def get_repository_config(self, repository_path: Path) -> Optional[RepositoryConfig]:
        """
        Loads and returns the configuration for a specific repository.

        Args:
            repository_path (Path): The path to the repository.

        Returns:
            Optional[RepositoryConfig]: The RepositoryConfig instance, or None if not found.
        """
        repo_config_path = repository_path / "rice.json"  # Or your preferred config file name
        if repo_config_path.exists():
            try:
                return RepositoryConfig(repo_config_path, self.logger)
            except ConfigurationError as e:
                self.logger.error(f"Failed to load repository config from {repo_config_path}: {e}")
                return None
        else:
            self.logger.info(f"No repository config found at {repo_config_path}")
            return None
