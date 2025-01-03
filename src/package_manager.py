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
    def install(self, packages: List[str]) -> bool:
        """Installs a list of packages."""
        pass

    def update_db(self) -> bool:
        """Updates the package manager's database (if applicable)."""
        return True # Default behavior is to do nothing
    
    def _run_command(self, command: List[str], check: bool = True, capture_output: bool = True) -> subprocess.CompletedProcess:
        """Runs a command and handles errors."""
        try:
            result = subprocess.run(command, capture_output=capture_output, text=True, check=check)
            if result.returncode != 0:
                self.logger.error(f"Error executing command: {command}")
                if result.stderr:
                    self.logger.error(f"Error output: {result.stderr}")
                if check:
                    raise PackageManagerError(f"Command '{' '.join(command)}' failed with error code {result.returncode}")
                else:
                    return result
            return result
        except FileNotFoundError:
            self.logger.error(f"Command not found: {command[0]}")
            raise PackageManagerError(f"Command not found: {command[0]}")
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
        return shutil.which("pacman") is not None

    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed via Pacman."""
        try:
            result = self._run_command(["pacman", "-Qq", package], check=False)
            return result.returncode == 0
        except PackageManagerError:
            return False

    def install(self, packages: List[str]) -> bool:
        """Installs packages using Pacman."""
        if not self.is_available():
            self.logger.error("Pacman package manager not found.")
            return False
        
        if not self.update_db():
            self.logger.error("Failed to update package database.")
            return False
        
        try:
            self._run_command(["sudo", "pacman", "-S", "--needed", "--noconfirm"] + packages)
            self.logger.info(f"Successfully installed packages with Pacman: {', '.join(packages)}")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to install packages with Pacman: {e}")
            return False

    def update_db(self) -> bool:
        """Updates the Pacman package database."""
        try:
            self._run_command(["sudo", "pacman", "-Sy"])
            self.logger.debug("Pacman package database updated.")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to update Pacman package database: {e}")
            return False

    def install_aur_helper(self) -> bool:
        """Installs the configured AUR helper (default: yay)."""
        if not self.is_available():
            self.logger.error("Pacman is required to install an AUR helper.")
            return False

        if self.aur_helper == "yay":
            # Check if yay is already installed
            if shutil.which("yay") is not None:
                self.logger.info("AUR helper 'yay' is already installed.")
                return True

            self.logger.info(f"Installing AUR helper: {self.aur_helper}")
            try:
                temp_dir = "/tmp"  # Use /tmp as a temporary directory
                clone_dir = os.path.join(temp_dir, "yay")

                # Clean up any previous failed installation attempts
                if os.path.exists(clone_dir):
                    shutil.rmtree(clone_dir)

                # Clone yay from AUR
                self._run_command(["git", "clone", f"https://aur.archlinux.org/yay.git", clone_dir])

                # Build and install yay
                self._run_command(["makepkg", "-si", "--noconfirm"], cwd=clone_dir)

                self.logger.info(f"Successfully installed AUR helper: {self.aur_helper}")
                return True
            except PackageManagerError as e:
                self.logger.error(f"Failed to install AUR helper {self.aur_helper}: {e}")
                return False
            finally:
                # Clean up the cloned directory
                if os.path.exists(clone_dir):
                    shutil.rmtree(clone_dir)

        else:
            self.logger.error(f"Unsupported AUR helper: {self.aur_helper}. Only 'yay' is currently supported.")
            return False

class AptPackageManager(PackageManagerInterface):
    """
    Implementation of PackageManagerInterface for APT.
    """

    def is_available(self) -> bool:
        """Checks if APT is available."""
        return shutil.which("apt-get") is not None

    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed via APT."""
        try:
            result = self._run_command(["dpkg", "-s", package], check=False)
            return result.returncode == 0
        except PackageManagerError:
            return False

    def install(self, packages: List[str]) -> bool:
        """Installs packages using APT."""
        if not self.is_available():
            self.logger.error("APT package manager not found.")
            return False
        
        if not self.update_db():
            self.logger.error("Failed to update package database.")
            return False

        try:
            self._run_command(["sudo", "apt-get", "install", "-y"] + packages)
            self.logger.info(f"Successfully installed packages with APT: {', '.join(packages)}")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to install packages with APT: {e}")
            return False

    def update_db(self) -> bool:
        """Updates the APT package database."""
        try:
            self._run_command(["sudo", "apt-get", "update"])
            self.logger.debug("APT package database updated.")
            return True
        except PackageManagerError as e:
            self.logger.error(f"Failed to update APT package database: {e}")
            return False