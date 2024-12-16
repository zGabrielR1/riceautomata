import json
import os
from src.utils import sanitize_path, setup_logger

logger = setup_logger()
DEFAULT_CONFIG_DIR = os.path.expanduser("~/.config/riceautomator")
DEFAULT_CONFIG_FILE = os.path.join(DEFAULT_CONFIG_DIR, "config.json")
DEFAULT_DEPENDENCY_MAP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "dependency_map.json")

class ConfigManager:

    def __init__(self, config_dir=DEFAULT_CONFIG_DIR, config_file=DEFAULT_CONFIG_FILE, dependency_map=DEFAULT_DEPENDENCY_MAP):
        self.config_dir = sanitize_path(config_dir)
        self.config_file = sanitize_path(config_file)
        self.dependency_map = sanitize_path(dependency_map)
        self.config_data = {}
        self.dependency_data = {}
        self._ensure_config_dir()
        self._load_config()
        self._load_dependencies()

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
              self.config_data = {}
              self._save_config() # Creates the config file if it doesn't exist
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

    def _load_dependencies(self):
      """Loads the dependency map from the JSON file."""
      try:
        if os.path.exists(self.dependency_map):
            with open(self.dependency_map, 'r') as f:
              self.dependency_data = json.load(f)
            logger.debug(f"Dependencies loaded from: {self.dependency_map}")
        else:
          logger.error(f"Dependency map not found at {self.dependency_map}")
          self.dependency_data = {} # Assign an empty dict to avoid errors if the file doesn't exists

      except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from {self.dependency_map}. Check if it's valid JSON")
      except Exception as e:
        logger.error(f"Error loading dependency file: {e}")
        self.dependency_data = {}


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
        return self.config_data.get(repository_name)

    def add_rice_config(self, repository_name, config):
        """Adds or updates configuration data for a repository."""
        self.config_data[repository_name] = config
        self._save_config()

    def get_dependency_map(self):
        """Gets the dependency map"""
        return self.dependency_data