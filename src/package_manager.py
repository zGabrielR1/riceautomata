# dotfilemanager/package_manager.py

import subprocess
from typing import List, Optional
import logging
import shutil

from .exceptions import PackageManagerError

class PackageManagerInterface:
    """
    Interface for package managers.
    """
    def is_installed(self, package: str) -> bool:
        raise NotImplementedError

    def install_packages(self, packages: List[str]) -> bool:
        raise NotImplementedError

class PacmanManager(PackageManagerInterface):
    """
    Manages packages using Pacman.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger('DotfileManager')

    def is_installed(self, package: str) -> bool:
        try:
            result = subprocess.run(['pacman', '-Qi', package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error checking if package {package} is installed: {e}")
            return False

    def install_packages(self, packages: List[str]) -> bool:
        try:
            self.logger.info(f"Installing pacman packages: {', '.join(packages)}")
            subprocess.run(['sudo', 'pacman', '-S', '--needed', '--noconfirm'] + packages, check=True)
            self.logger.debug(f"Successfully installed pacman packages: {', '.join(packages)}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install pacman packages: {e}")
            return False

class AURHelperManager(PackageManagerInterface):
    """
    Manages AUR packages using an AUR helper like yay or paru.
    """
    def __init__(self, helper: str = 'yay', logger: Optional[logging.Logger] = None):
        self.helper = helper
        self.logger = logger or logging.getLogger('DotfileManager')

    def is_installed(self, package: str) -> bool:
        try:
            result = subprocess.run([self.helper, '-Qi', package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return result.returncode == 0
        except Exception as e:
            self.logger.error(f"Error checking if AUR package {package} is installed: {e}")
            return False

    def install_packages(self, packages: List[str]) -> bool:
        try:
            self.logger.info(f"Installing AUR packages with {self.helper}: {', '.join(packages)}")
            subprocess.run([self.helper, '-S', '--needed', '--noconfirm'] + packages, check=True)
            self.logger.debug(f"Successfully installed AUR packages: {', '.join(packages)}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install AUR packages: {e}")
            return False

    def install_helper(self) -> bool:
        """
        Installs the AUR helper if it's not already installed.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            self.logger.info(f"Installing AUR helper: {self.helper}")
            clone_dir = Path("/tmp") / f"{self.helper}-git"
            if clone_dir.exists():
                shutil.rmtree(clone_dir)

            # Clone the AUR helper repository
            subprocess.run(['git', 'clone', f'https://aur.archlinux.org/{self.helper}-git.git', str(clone_dir)], check=True)

            # Build and install the helper
            subprocess.run(['makepkg', '-si', '--noconfirm'], cwd=str(clone_dir), check=True)

            # Cleanup
            shutil.rmtree(clone_dir)
            self.logger.debug(f"Successfully installed AUR helper: {self.helper}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Failed to install AUR helper {self.helper}: {e}")
            return False