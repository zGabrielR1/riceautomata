import os
import pytest
import tempfile
import shutil
from typing import Generator
from src.config import ConfigManager
from src.state import StateManager
from src.dotfile import DotfileManager
from src.progress import ProgressTracker
from src.validation import ConfigValidator

@pytest.fixture
def temp_dir() -> Generator[str, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir

@pytest.fixture
def config_file(temp_dir: str) -> str:
    """Create a temporary config file."""
    config_path = os.path.join(temp_dir, "config.json")
    with open(config_path, "w") as f:
        f.write("{}")
    return config_path

@pytest.fixture
def state_file(temp_dir: str) -> str:
    """Create a temporary state file."""
    return os.path.join(temp_dir, "state.json")

@pytest.fixture
def config_manager(config_file: str) -> ConfigManager:
    """Create a ConfigManager instance."""
    return ConfigManager(config_file)

@pytest.fixture
def state_manager(state_file: str) -> StateManager:
    """Create a StateManager instance."""
    return StateManager(state_file)

@pytest.fixture
def progress_tracker() -> ProgressTracker:
    """Create a ProgressTracker instance."""
    return ProgressTracker(show_spinner=False)

@pytest.fixture
def config_validator(temp_dir: str) -> ConfigValidator:
    """Create a ConfigValidator instance."""
    schema_dir = os.path.join(temp_dir, "schemas")
    os.makedirs(schema_dir)
    return ConfigValidator(schema_dir)

@pytest.fixture
def dotfile_manager(config_manager: ConfigManager, state_manager: StateManager) -> DotfileManager:
    """Create a DotfileManager instance."""
    return DotfileManager(config_manager, state_manager)

@pytest.fixture
def sample_dotfiles(temp_dir: str) -> str:
    """Create sample dotfiles for testing."""
    dotfiles_dir = os.path.join(temp_dir, "dotfiles")
    os.makedirs(dotfiles_dir)
    
    # Create some sample dotfiles
    configs = {
        ".bashrc": "export PATH=$PATH:~/bin",
        ".vimrc": "set number\nset syntax on",
        ".config/i3/config": "# i3 config file",
        ".config/polybar/config": "# polybar config"
    }
    
    for path, content in configs.items():
        full_path = os.path.join(dotfiles_dir, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
            
    return dotfiles_dir

@pytest.fixture
def sample_templates(temp_dir: str) -> str:
    """Create sample templates for testing."""
    template_dir = os.path.join(temp_dir, "templates")
    os.makedirs(template_dir)
    
    templates = {
        "bashrc.template": "export NAME={{ user_name }}\nexport EMAIL={{ user_email }}",
        "i3.j2": "# i3 config for {{ hostname }}"
    }
    
    for name, content in templates.items():
        with open(os.path.join(template_dir, name), "w") as f:
            f.write(content)
            
    return template_dir

@pytest.fixture
def mock_package_manager(monkeypatch):
    """Mock package manager operations."""
    class MockPackageManager:
        def __init__(self):
            self.installed_packages = set()
            
        def install(self, package):
            self.installed_packages.add(package)
            return True
            
        def is_installed(self, package):
            return package in self.installed_packages
            
        def detect_package_manager(self):
            return "mock"
            
    mock_pm = MockPackageManager()
    # Monkeypatch the package manager in relevant classes
    return mock_pm
