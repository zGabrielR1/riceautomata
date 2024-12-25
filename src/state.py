import os
import json
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict
from threading import Lock
from src.utils import setup_logger

logger = setup_logger()

@dataclass
class ApplicationState:
    """Represents the current state of the application."""
    current_rice: Optional[str] = None
    active_profile: Optional[str] = None
    installed_packages: Dict[str, str] = None  # package: version
    applied_templates: Dict[str, float] = None  # template: timestamp
    backup_history: Dict[str, Dict] = None  # backup_name: metadata
    last_operation: Dict[str, Any] = None
    
    def __post_init__(self):
        self.installed_packages = self.installed_packages or {}
        self.applied_templates = self.applied_templates or {}
        self.backup_history = self.backup_history or {}
        self.last_operation = self.last_operation or {}

class StateManager:
    """Manages application state persistence and recovery."""
    
    def __init__(self, state_file: str):
        self.state_file = state_file
        self.state = self._load_state()
        self._lock = Lock()
        
    def _load_state(self) -> ApplicationState:
        """Load state from file or create new if not exists."""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    data = json.load(f)
                return ApplicationState(**data)
        except Exception as e:
            logger.error(f"Error loading state: {e}")
        return ApplicationState()
        
    def _save_state(self):
        """Save current state to file."""
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, 'w') as f:
                json.dump(asdict(self.state), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving state: {e}")
            
    def update_state(self, **kwargs):
        """Update state with new values."""
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self.state, key):
                    setattr(self.state, key, value)
            self._save_state()
            
    def get_state(self) -> ApplicationState:
        """Get current application state."""
        with self._lock:
            return self.state
            
    def record_operation(self, operation: str, details: Dict[str, Any]):
        """Record an operation in the state history."""
        with self._lock:
            self.state.last_operation = {
                "operation": operation,
                "timestamp": time.time(),
                "details": details
            }
            self._save_state()
            
    def clear_state(self):
        """Clear the current state."""
        with self._lock:
            self.state = ApplicationState()
            self._save_state()
            
    def add_installed_package(self, package: str, version: str):
        """Record an installed package."""
        with self._lock:
            self.state.installed_packages[package] = version
            self._save_state()
            
    def remove_installed_package(self, package: str):
        """Remove a package from installed packages."""
        with self._lock:
            self.state.installed_packages.pop(package, None)
            self._save_state()
            
    def record_template_application(self, template: str):
        """Record a template application."""
        with self._lock:
            self.state.applied_templates[template] = time.time()
            self._save_state()
            
    def add_backup(self, name: str, metadata: Dict[str, Any]):
        """Record a backup operation."""
        with self._lock:
            self.state.backup_history[name] = {
                **metadata,
                "timestamp": time.time()
            }
            self._save_state()
            
    def remove_backup(self, name: str):
        """Remove a backup from history."""
        with self._lock:
            self.state.backup_history.pop(name, None)
            self._save_state()
            
    def set_current_rice(self, rice_name: str):
        """Set the current rice configuration."""
        with self._lock:
            self.state.current_rice = rice_name
            self._save_state()
            
    def set_active_profile(self, profile_name: str):
        """Set the active profile."""
        with self._lock:
            self.state.active_profile = profile_name
            self._save_state()
            
    def get_operation_history(self) -> Dict[str, Any]:
        """Get the last operation details."""
        with self._lock:
            return self.state.last_operation
            
    def get_installed_packages(self) -> Dict[str, str]:
        """Get all installed packages and their versions."""
        with self._lock:
            return dict(self.state.installed_packages)
            
    def get_applied_templates(self) -> Dict[str, float]:
        """Get all applied templates and their timestamps."""
        with self._lock:
            return dict(self.state.applied_templates)
            
    def get_backup_history(self) -> Dict[str, Dict]:
        """Get backup history."""
        with self._lock:
            return dict(self.state.backup_history)
