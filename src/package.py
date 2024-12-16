import subprocess
import os
from src.utils import setup_logger, confirm_action
import sys

logger = setup_logger()

class PackageManager:

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.package_manager = self._detect_package_manager()
        self.logger = setup_logger(verbose)
        self.nix_installed = self._check_nix()

    def _detect_package_manager(self):
        """Detects the package manager based on the system."""
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as f:
                os_release_content = f.read()
                if "ID=arch" in os_release_content:
                    return "pacman"
                elif "ID=ubuntu" in os_release_content or "ID=debian" in os_release_content:
                    return "apt"
                elif "ID=fedora" in os_release_content:
                    return "dnf"
                elif "ID=opensuse-tumbleweed" in os_release_content:
                    return "zypper"
                else:
                    self.logger.warning("Could not detect package manager, defaulting to pacman. If your system doesn't use pacman, specify it using '--distro <distro_name>'")
                    return "pacman"
        else:
          self.logger.warning("Could not detect package manager, defaulting to pacman. If your system doesn't use pacman, specify it using '--distro <distro_name>'")
          return "pacman"

    def set_package_manager(self, package_manager):
      """Set the package manager, overwriting the detected one"""
      if package_manager in ("pacman", "apt", "dnf", "zypper"):
        self.package_manager = package_manager
      else:
        self.logger.error("Package manager not supported")
        sys.exit(1)

    def _run_command(self, command, check=True):
      """Runs a command and returns the result."""
      try:
          result = subprocess.run(command, capture_output=True, text=True, check=check)
          if check and result.stderr:
              self.logger.error(f"Command failed: {command}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False

          if self.verbose:
              self.logger.debug(f"Command ran successfully: {' '.join(command)}")
              if result.stdout:
                  self.logger.debug(f"Output: \n{result.stdout}")
          return result

      except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
      except Exception as e:
         self.logger.error(f"Error executing command: {command}. Error: {e}")
         return False

    def _check_paru(self):
      """Checks if Paru is installed"""
      paru_result = self._run_command(["paru", "--version"], check=False)
      return paru_result and paru_result.returncode == 0

    def _install_paru(self):
      """Tries to install Paru."""
      if self.verbose:
        self.logger.info("Paru not found, trying to install it.")
      install_paru_result = self._run_command(["sudo", "pacman", "-S", "--noconfirm", "paru"], check=False)
      if install_paru_result and install_paru_result.returncode == 0:
        self.logger.info("Paru installed successfully.")
        return True

      self.logger.warning("Failed to install Paru with pacman, trying to install with yay instead.")
      install_yay_result = self._run_command(["sudo", "pacman", "-S", "--noconfirm", "yay"], check=False)
      if install_yay_result and install_yay_result.returncode == 0:
          self.logger.info("Yay installed successfully.")
          install_paru_yay_result = self._run_command(["yay", "-S", "--noconfirm", "paru"], check=False)
          if install_paru_yay_result and install_paru_yay_result.returncode == 0:
              self.logger.info("Paru installed successfully using yay")
              return True
          else:
            self.logger.error("Failed to install paru with yay")
            return False
      else:
        self.logger.error("Failed to install yay")
        return False

    def _check_nix(self):
      """Checks if Nix is installed."""
      nix_result = self._run_command(["nix", "--version"], check=False)
      return nix_result and nix_result.returncode == 0

    def _install_nix(self):
        """Attempts to install nix using the install script."""
        self.logger.info("Nix not found, attempting to install.")
        try:
            install_nix_command = [
              "sh", "-c",
              'curl -L https://nixos.org/nix/install | sh -s -- --daemon'
            ]
            install_result = self._run_command(install_nix_command, check=False)
            if install_result and install_result.returncode == 0:
               self.logger.info("Nix installed successfully.")
               self.nix_installed = True
               return True
            else:
               self.logger.error("Failed to install Nix.")
               return False
        except Exception as e:
            self.logger.error(f"Error installing nix: {e}")
            return False

    def _install_packages(self, packages, use_paru = True):
        """Installs a list of packages using the package manager."""
        if not packages:
           self.logger.debug("No packages to install")
           return True
        if use_paru and self.package_manager == "pacman" and not self._check_paru():
           if not self._install_paru():
             self.logger.error("Can't use paru, and failed to install it. Please install manually.")
             return False
        if self.nix_installed:
            if self.verbose:
                 self.logger.info(f"Installing packages using nix: {', '.join(packages)}")
            nix_result = self._run_command(["nix", "profile", "install", "--packages"] + packages, check=False)
            if nix_result and nix_result.returncode == 0:
                 self.logger.info(f"Packages installed using nix: {', '.join(packages)}")
                 return True
            else:
                self.logger.error(f"Failed to install using nix: {packages}")
                return False
        else:
          install_command = []
          if self.package_manager == "pacman":
            install_command.extend(["sudo", "pacman", "-S", "--noconfirm"])
            if use_paru and self._check_paru():
              install_command = ["paru", "-S", "--noconfirm"]
          elif self.package_manager == "apt":
              install_command.extend(["sudo", "apt", "install", "-y"])
          elif self.package_manager == "dnf":
              install_command.extend(["sudo", "dnf", "install", "-y"])
          elif self.package_manager == "zypper":
             install_command.extend(["sudo", "zypper", "install", "-y"])
          install_command.extend(packages)

          install_result = self._run_command(install_command)
          if install_result and install_result.returncode == 0:
             self.logger.info(f"Packages installed: {', '.join(packages)}")
             return True
          else:
              self.logger.error(f"Failed to install packages: {', '.join(packages)}")
              return False

    def install(self, packages, use_paru = True):
        """Installs the list of packages using the package manager, with user confirmation."""
        if packages:
            if self.verbose:
                self.logger.info(f"Attempting to install packages: {', '.join(packages)}")
                if not self._install_packages(packages, use_paru):
                   return False
                return True
            else:
                if confirm_action(f"Do you want to install these packages?: {', '.join(packages)}"):
                   if not self._install_packages(packages, use_paru):
                     return False
                   return True
        return True

    def is_installed(self, package):
      """Checks if a package is installed using the package manager."""
      if self.nix_installed:
          nix_result = self._run_command(["nix", "profile", "list"], check=False)
          if nix_result and nix_result.returncode == 0:
            if package in nix_result.stdout:
               if self.verbose:
                    self.logger.debug(f"Nix package {package} is installed")
               return True
            else:
                if self.verbose:
                   self.logger.debug(f"Nix package {package} is not installed")
                return False
          else:
             if self.verbose:
                self.logger.debug(f"Error checking if the nix package is installed")
             return False
      else:
         query_command = []
         if self.package_manager == "pacman":
           query_command.extend(["pacman", "-Qq", package])
         elif self.package_manager == "apt":
           query_command.extend(["dpkg", "-s", package])
         elif self.package_manager == "dnf":
           query_command.extend(["rpm", "-q", package])
         elif self.package_manager == "zypper":
           query_command.extend(["rpm", "-q", package])
         result = self._run_command(query_command, check=False)

         if result and result.returncode == 0:
            if self.verbose:
               self.logger.debug(f"Package {package} is installed")
            return True
         else:
            if self.verbose:
              self.logger.debug(f"Package {package} is not installed")
            return False