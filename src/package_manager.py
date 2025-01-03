# src/package_manager.py
import subprocess
from typing import List, Optional, Dict
import logging
import shutil
import os
from abc import ABC, abstractmethod

from .exceptions import PackageManagerError

class PackageManagerInterface(ABC):
    """
    Interface for package managers.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger('DotfileManager')

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if the package manager is available on the system."""
        pass

    @abstractmethod
    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed."""
        pass

    @abstractmethod
    def install_packages(self, packages: List[str]) -> bool:
        """Installs a list of packages."""
        pass

    def update_db(self) -> bool:
        """Updates the package manager's database (if applicable)."""
        return True  # Default behavior is to do nothing

    def _run_command(self, command: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
        """
        Runs a command and handles errors.

        Args:
            command (List[str]): The command to execute.
            check (bool): Whether to raise an exception on non-zero exit codes.
            capture_output (bool): Whether to capture the command's output.

        Returns:
            subprocess.CompletedProcess: The result of the executed command.
        """
        try:
            result = subprocess.run(command, capture_output=capture_output, text=True, check=check)
            if result.returncode != 0:
                self.logger.error(f"Error executing command: {' '.join(command)}")
                if result.stderr:
                    self.logger.error(f"Error output: {result.stderr}")
                if check:
                    raise PackageManagerError(f"Command '{' '.join(command)}' failed with error code {result.returncode}")
            return result
        except FileNotFoundError:
            self.logger.error(f"Command not found: {command[0]}")
            raise PackageManagerError(f"Command not found: {command[0]}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Command '{' '.join(command)}' failed with exit code {e.returncode}")
            raise PackageManagerError(f"Command '{' '.join(command)}' failed with exit code {e.returncode}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred: {e}")
            raise PackageManagerError(f"An unexpected error occurred: {e}")

class PacmanPackageManager(PackageManagerInterface):
    """
    Implementation of PackageManagerInterface for Pacman.
    """

    def __init__(self, logger: Optional[logging.Logger] = None, aur_helper: Optional[str] = "yay"):
        super().__init__(logger)
        self.aur_helper = aur_helper

    def is_available(self) -> bool:
        """Checks if Pacman is available."""
        available = shutil.which("pacman") is not None
        self.logger.debug(f"Pacman availability: {available}")
        return available

    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed via Pacman."""
        try:
            result = self._run_command(["pacman", "-Qq", package], check=False)
            installed = result.returncode == 0
            self.logger.debug(f"Package '{package}' installed via Pacman: {installed}")
            return installed
        except PackageManagerError:
            self.logger.debug(f"Package '{package}' not installed via Pacman.")
            return False

    def install_packages(self, packages: List[str]) -> bool:
        """Installs packages using Pacman."""
        if not self.is_available():
            self.logger.error("Pacman package manager not found.")
            return False

        if not self.update_db():
            self.logger.error("Failed to update Pacman package database.")
            return False

        try:
            self._run_command(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + packages)
            self.logger.info(f"Successfully installed Pacman packages: {', '.join(packages)}")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to install Pacman packages: {e}")
            return False

    def update_db(self) -> bool:
        """Updates the Pacman package database."""
        try:
            self._run_command(["sudo", "pacman", "-Sy"])
            self.logger.debug("Pacman package database updated successfully.")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to update Pacman package database: {e}")
            return False

class AptPackageManager(PackageManagerInterface):
    """
    Implementation of PackageManagerInterface for APT.
    """

    def is_available(self) -> bool:
        """Checks if APT is available."""
        available = shutil.which("apt-get") is not None
        self.logger.debug(f"APT availability: {available}")
        return available

    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed via APT."""
        try:
            result = self._run_command(["dpkg", "-s", package], check=False)
            installed = result.returncode == 0
            self.logger.debug(f"Package '{package}' installed via APT: {installed}")
            return installed
        except PackageManagerError:
            self.logger.debug(f"Package '{package}' not installed via APT.")
            return False

    def install_packages(self, packages: List[str]) -> bool:
        """Installs packages using APT."""
        if not self.is_available():
            self.logger.error("APT package manager not found.")
            return False

        if not self.update_db():
            self.logger.error("Failed to update APT package database.")
            return False

        try:
            self._run_command(["sudo", "apt-get", "install", "-y"] + packages)
            self.logger.info(f"Successfully installed APT packages: {', '.join(packages)}")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to install APT packages: {e}")
            return False

    def update_db(self) -> bool:
        """Updates the APT package database."""
        try:
            self._run_command(["sudo", "apt-get", "update"])
            self.logger.debug("APT package database updated successfully.")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to update APT package database: {e}")
            return False

class AURHelperManager(PackageManagerInterface):
    """
    Manager for AUR (Arch User Repository) helpers like 'yay'.
    """

    def __init__(self, helper_name: str = "yay", logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.helper_name = helper_name

    def is_available(self) -> bool:
        """Checks if the AUR helper is available."""
        available = shutil.which(self.helper_name) is not None
        self.logger.debug(f"AUR helper '{self.helper_name}' availability: {available}")
        return available

    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed via the AUR helper."""
        try:
            result = self._run_command([self.helper_name, "-Qi", package], check=False)
            installed = result.returncode == 0
            self.logger.debug(f"Package '{package}' installed via AUR helper '{self.helper_name}': {installed}")
            return installed
        except PackageManagerError:
            self.logger.debug(f"Package '{package}' not installed via AUR helper '{self.helper_name}'.")
            return False

    def install_packages(self, packages: List[str]) -> bool:
        """Installs AUR packages using the AUR helper."""
        if not self.is_available():
            self.logger.error(f"AUR helper '{self.helper_name}' not found.")
            return False

        try:
            self._run_command([self.helper_name, "-S", "--noconfirm"] + packages)
            self.logger.info(f"Successfully installed AUR packages using '{self.helper_name}': {', '.join(packages)}")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to install AUR packages using '{self.helper_name}': {e}")
            return False

    def install_aur_helper(self) -> bool:
        """
        Installs the AUR helper (e.g., 'yay').

        Returns:
            bool: True if successful, False otherwise.
        """
        self.logger.info(f"Attempting to install AUR helper '{self.helper_name}'...")
        try:
            temp_dir = "/tmp"  # Temporary directory for installation
            clone_dir = os.path.join(temp_dir, f"{self.helper_name}-git")

            # Clean up any previous failed installation attempts
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
                self.logger.debug(f"Removed existing directory '{clone_dir}' for AUR helper installation.")

            # Clone the AUR helper repository
            self._run_command(["git", "clone", f"https://aur.archlinux.org/{self.helper_name}.git", clone_dir])

            # Build and install the AUR helper
            self._run_command(["makepkg", "-si", "--noconfirm"], cwd=clone_dir)
            self.logger.info(f"Successfully installed AUR helper '{self.helper_name}'.")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to install AUR helper '{self.helper_name}': {e}")
            return False
        finally:
            # Clean up the cloned directory
            if os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
                self.logger.debug(f"Cleaned up cloned directory '{clone_dir}' after AUR helper installation.")

    def update_db(self) -> bool:
        """
        AUR helpers typically handle their own updates, so this can be a no-op or
        delegate to the helper's update command if supported.

        Returns:
            bool: True if successful, False otherwise.
        """
        # Example: Some AUR helpers might have an update command
        # Adjust based on the specific helper's capabilities
        self.logger.debug(f"No database update required for AUR helper '{self.helper_name}'.")
        return True
