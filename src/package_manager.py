# src/package_manager.py

import platform
from typing import List, Optional
import logging
import shutil

from .exceptions import PackageManagerError


class PackageManagerInterface:
    """
    Interface for package managers.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger('PackageManager')

    def is_available(self) -> bool:
        """Checks if the package manager is available on the system."""
        raise NotImplementedError

    def is_installed(self, package: str) -> bool:
        """Checks if a package is installed."""
        raise NotImplementedError

    def install_packages(self, packages: List[str]) -> bool:
        """Installs a list of packages."""
        raise NotImplementedError

    def update_db(self) -> bool:
        """Updates the package manager's database."""
        raise NotImplementedError


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
        import subprocess
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
        import subprocess
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
            import subprocess
            import tempfile

            temp_dir = tempfile.gettempdir()
            clone_dir = shutil.os.path.join(temp_dir, f"{self.helper_name}-git")

            # Clean up any previous failed installation attempts
            if shutil.os.path.exists(clone_dir):
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
            if shutil.os.path.exists(clone_dir):
                shutil.rmtree(clone_dir)
                self.logger.debug(f"Cleaned up cloned directory '{clone_dir}' after AUR helper installation.")

    def update_db(self) -> bool:
        """
        AUR helpers typically handle their own updates, so this can be a no-op or
        delegate to the helper's update command if supported.

        Returns:
            bool: True if successful, False otherwise.
        """
        self.logger.debug(f"No database update required for AUR helper '{self.helper_name}'.")
        return True

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
        import subprocess
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


class PackageManager(PackageManagerInterface):
    """
    Facade for managing different package managers based on the operating system.
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        super().__init__(logger)
        self.manager: Optional[PackageManagerInterface] = None
        self.aur_helper_manager: Optional[AURHelperManager] = None
        self._initialize_manager()

    def _initialize_manager(self):
        """
        Initializes the appropriate package manager based on the OS.
        """
        os_type = self.detect_os_type()
        self.logger.debug(f"Detected OS type: {os_type}")

        if os_type == "arch":
            self.manager = PacmanPackageManager(logger=self.logger)
            # Initialize AUR Helper Manager if necessary
            self.aur_helper_manager = AURHelperManager(logger=self.logger)
            if not self.aur_helper_manager.is_available():
                self.logger.info("AUR helper not found. Attempting to install...")
                if not self.aur_helper_manager.install_aur_helper():
                    self.logger.error("Failed to install AUR helper.")
        elif os_type in ["debian", "ubuntu"]:
            self.manager = AptPackageManager(logger=self.logger)
        else:
            self.logger.error(f"Unsupported operating system: {os_type}")
            raise PackageManagerError(f"Unsupported operating system: {os_type}")

    def detect_os_type(self) -> str:
        """
        Detects the operating system type.

        Returns:
            str: The OS type (e.g., 'arch', 'debian', 'ubuntu', etc.).
        """
        system = platform.system().lower()
        if system == "linux":
            try:
                import distro
                distro_name = distro.id().lower()
                if "arch" in distro_name:
                    return "arch"
                elif "debian" in distro_name or "ubuntu" in distro_name:
                    return "debian"
                # Add more distributions as needed
            except ImportError:
                self.logger.warning("The 'distro' package is not installed. Defaulting to 'unknown'.")
                return "unknown"
        elif system == "darwin":
            return "macos"
        elif system == "windows":
            return "windows"
        return "unknown"

    def is_available(self) -> bool:
        """
        Checks if the selected package manager is available.

        Returns:
            bool: True if available, False otherwise.
        """
        if self.manager:
            return self.manager.is_available()
        return False

    def is_installed(self, package: str) -> bool:
        """
        Checks if a package is installed using the selected package manager.

        Args:
            package (str): The package name.

        Returns:
            bool: True if installed, False otherwise.
        """
        if self.manager:
            return self.manager.is_installed(package)
        return False

    def install_packages(self, packages: List[str]) -> bool:
        """
        Installs packages using the selected package manager.

        Args:
            packages (List[str]): List of package names to install.

        Returns:
            bool: True if installation was successful, False otherwise.
        """
        if self.manager:
            return self.manager.install_packages(packages)
        return False

    def update_db(self) -> bool:
        """
        Updates the package manager's database.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        if self.manager:
            return self.manager.update_db()
        return False