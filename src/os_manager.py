# dotfilemanager/os_manager.py

import platform
import subprocess
from pathlib import Path
from typing import Optional
import logging
import shutil

from .exceptions import OSManagerError

class OSManager:
    """
    Manages OS-specific operations.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initializes the OSManager.

        Args:
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')
        self.os_type = platform.system().lower()
        self.distribution = self._get_linux_distribution()

    def _get_linux_distribution(self) -> Optional[str]:
        """
        Retrieves the Linux distribution name.

        Returns:
            Optional[str]: Distribution name if on Linux, else None.
        """
        try:
            if self.os_type == 'linux':
                return platform.linux_distribution()[0].lower()
            return None
        except AttributeError:
            # platform.linux_distribution() is deprecated in Python 3.8+
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("ID="):
                            return line.strip().split("=")[1].strip('"').lower()
            except Exception:
                return None

    def is_arch_based(self) -> bool:
        """
        Checks if the system is Arch-based.

        Returns:
            bool: True if Arch-based, False otherwise.
        """
        if self.os_type == 'linux' and 'arch' in self.distribution:
            return True
        return False

    def get_package_manager(self) -> Optional[str]:
        """
        Retrieves the package manager for the current OS.

        Returns:
            Optional[str]: Package manager command if found, else None.
        """
        if self.is_arch_based():
            return 'pacman'
        elif self.os_type == 'darwin':
            return 'brew'
        elif self.os_type == 'linux':
            # Check for apt
            if shutil.which('apt'):
                return 'apt'
        return None

    def install_system_packages(self, packages: List[str], package_manager: str) -> bool:
        """
        Installs system packages using the specified package manager.

        Args:
            packages (List[str]): List of package names.
            package_manager (str): Package manager command.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            if package_manager == 'pacman':
                cmd = ['sudo', 'pacman', '-S', '--needed', '--noconfirm'] + packages
            elif package_manager == 'apt':
                cmd = ['sudo', 'apt', 'update']
                subprocess.run(cmd, check=True)
                cmd = ['sudo', 'apt', 'install', '-y'] + packages
            elif package_manager == 'brew':
                cmd = ['brew', 'install'] + packages
            else:
                self.logger.error(f"Unsupported package manager: {package_manager}")
                return False
            self.logger.info(f"Installing packages with {package_manager}: {', '.join(packages)}")
            subprocess.run(cmd, check=True)
            self.logger.debug(f"Successfully installed packages: {', '.join(packages)}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install packages with {package_manager}: {e}")
            return False