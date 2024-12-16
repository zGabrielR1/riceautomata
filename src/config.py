import json
import os
from src.utils import sanitize_path, setup_logger

logger = setup_logger()
DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/riceautomator")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, "config.json")

class ConfigManager:

    def __init__(self, config_dir=DEFAULT_CONFIG_DIR, config_file=DEFAULT_CONFIG_FILE):
        self.config_dir = sanitize_path(config_dir)
        self.config_file = sanitize_path(config_file)
        self.config_data = {}
        self._ensure_config_dir()
        self._load_config()

    def _ensure_config_dir(self):
        """Creates the config directory if it doesn't exist."""
        if not os.path.exists(self.config_dir):
            os.makedirs(self.config_dir, exist_ok=True)

    def _load_config(self):
        """Loads the configuration data from the JSON file."""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config_data = json.load(f)
            else:
                self.config_data = {
                    'package_managers': {
                        'preferred': None,  # User's preferred package manager
                        'installed': [],    # List of installed package managers
                        'auto_install': False  # Whether to auto-install package managers
                    },
                    'rices': {}  # Rice configurations
                }
                self._save_config()
            logger.debug(f"Configuration loaded from: {self.config_file}")

        except FileNotFoundError:
            logger.debug(f"Config file not found: {self.config_file}. Creating a new one.")
            self.config_data = {}
            self._save_config()
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from {self.config_file}. Check if it's valid JSON")
            self.config_data = {}
            self._save_config()
        except Exception as e:
            logger.error(f"Error loading configuration file: {e}")

    def _save_config(self):
        """Saves the configuration data to the JSON file."""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config_data, f, indent=4)
                logger.debug(f"Config saved to {self.config_file}")
        except Exception as e:
            logger.error(f"Error saving configuration file: {e}")

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
            self.config_data['package_managers'] = {}
        
        if preferred is not None:
            self.config_data['package_managers']['preferred'] = preferred
        if installed is not None:
            self.config_data['package_managers']['installed'] = installed
        if auto_install is not None:
            self.config_data['package_managers']['auto_install'] = auto_install
        
        self._save_config()