  import subprocess
  import os
  from src.utils import setup_logger, confirm_action
  import sys

  logger = setup_logger()

  class PackageManager:

      def __init__(self, verbose=False, aur_helper = "paru"):
          self.verbose = verbose
          self.system_package_manager = self._detect_package_manager()
          self.logger = setup_logger(verbose)
          self.nix_installed = self._check_nix()
          self.aur_helper = aur_helper
          self.installed_packages = []
          self.package_managers = {
              'system': self.system_package_manager,
              'pip': self._check_pip(),
              'npm': self._check_npm(),
              'cargo': self._check_cargo()
          }

      def _detect_package_manager(self):
          """Detects the system package manager based on the OS."""
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
          self.logger.warning("Could not detect package manager, defaulting to pacman")
          return "pacman"

      def _check_pip(self):
          """Checks if pip is installed."""
          pip_result = self._run_command(["pip", "--version"], check=False)
          return pip_result and pip_result.returncode == 0

      def _check_npm(self):
          """Checks if npm is installed."""
          npm_result = self._run_command(["npm", "--version"], check=False)
          return npm_result and npm_result.returncode == 0

      def _check_cargo(self):
          """Checks if cargo is installed."""
          cargo_result = self._run_command(["cargo", "--version"], check=False)
          return cargo_result and cargo_result.returncode == 0

      def install_package(self, package_spec):
          """Installs a package using the appropriate package manager."""
          if ':' not in package_spec:
              # Default to system package manager if no prefix
              return self._install_system_package(package_spec)
          
          pm, package = package_spec.split(':', 1)
          if pm == 'pacman' or pm == 'apt' or pm == 'dnf' or pm == 'zypper':
              return self._install_system_package(package)
          elif pm == 'pip':
              return self._install_pip_package(package)
          elif pm == 'npm':
              return self._install_npm_package(package)
          elif pm == 'cargo':
              return self._install_cargo_package(package)
          elif pm == 'aur':
                return self._install_aur_package(package)
          elif pm == 'auto':
              # Try to install using system package manager first
              if self._install_system_package(package):
                  return True
              # Try other package managers
              for pm_func in [self._install_pip_package, self._install_npm_package, self._install_cargo_package]:
                  if pm_func(package):
                      return True
              return False
          else:
              self.logger.error(f"Unsupported package manager: {pm}")
              return False

      def _install_system_package(self, package):
          """Installs a package using the system package manager."""
          if self.system_package_manager == "pacman":
              if self._check_paru():
                if self.aur_helper == "paru":
                  return self._run_command(["paru", "-S", "--noconfirm", package])
                else:
                  return self._run_command(["yay", "-S", "--noconfirm", package])
              return self._run_command(["sudo", "pacman", "-S", "--noconfirm", package])
          elif self.system_package_manager == "apt":
              return self._run_command(["sudo", "apt", "install", "-y", package])
          elif self.system_package_manager == "dnf":
              return self._run_command(["sudo", "dnf", "install", "-y", package])
          elif self.system_package_manager == "zypper":
              return self._run_command(["sudo", "zypper", "install", "-y", package])
          return False

      def _install_pip_package(self, package):
          """Installs a Python package using pip."""
          if not self._check_pip():
              self.logger.error("pip is not installed")
              return False
          return self._run_command(["pip", "install", "--user", package])

      def _install_npm_package(self, package):
          """Installs a Node.js package using npm."""
          if not self._check_npm():
              self.logger.error("npm is not installed")
              return False
          return self._run_command(["npm", "install", "-g", package])

      def _install_cargo_package(self, package):
          """Installs a Rust package using cargo."""
          if not self._check_cargo():
              self.logger.error("cargo is not installed")
              return False
          return self._run_command(["cargo", "install", package])
      
      def _install_aur_package(self, package):
          """Installs an AUR package using paru."""
          if not self._check_paru():
            if not self._install_paru():
              self.logger.error(f"AUR Helper not installed, and failed to install it, can't install package: {package}")
              return False
          if self.aur_helper == "paru":
              return self._run_command(["paru", "-S", "--noconfirm", package])
          else:
              return self._run_command(["yay", "-S", "--noconfirm", package])

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
              
      def _install_font_manually(self, font_path):
          """Tries to install the font manually."""
          try:
            font_target_path = os.path.join(os.path.expanduser("~/.local/share/fonts"), os.path.basename(font_path))
            if not os.path.exists(os.path.dirname(font_target_path)):
              os.makedirs(os.path.dirname(font_target_path), exist_ok = True)
            shutil.copy2(font_path, font_target_path)
            self._run_command(["fc-cache", "-f", "-v"])
            self.logger.info(f"Successfully installed font manually at: {font_target_path}")
            return True
          except Exception as e:
            self.logger.error(f"Error installing font manually: {e}")
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

      def _install_packages(self, packages, use_paru = True):
          """Installs a list of packages using the package manager."""
          if not packages:
            self.logger.debug("No packages to install")
            return True
          if use_paru and self.system_package_manager == "pacman" and not self._check_paru():
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
            if self.system_package_manager == "pacman":
              install_command.extend(["sudo", "pacman", "-S", "--noconfirm"])
              if use_paru and self._check_paru():
                if self.aur_helper == "paru":
                  install_command = ["paru", "-S", "--noconfirm"]
                else:
                  install_command = ["yay", "-S", "--noconfirm"]
            elif self.system_package_manager == "apt":
                install_command.extend(["sudo", "apt", "install", "-y"])
            elif self.system_package_manager == "dnf":
                install_command.extend(["sudo", "dnf", "install", "-y"])
            elif self.system_package_manager == "zypper":
              install_command.extend(["sudo", "zypper", "install", "-y"])
            install_command.extend(packages)

            install_result = self._run_command(install_command)
            if install_result and install_result.returncode == 0:
              self.logger.info(f"Packages installed: {', '.join(packages)}")
              return True
            else:
                self.logger.error(f"Failed to install packages: {', '.join(packages)}")
                return False

      def is_installed(self, package):
        """Checks if a package is installed using the package manager."""
        if self.nix_installed:
            nix_result = self._run_command(["nix", "profile", "list"], check=False)
            if nix_result and nix_result.returncode == 0:
              self.installed_packages = nix_result.stdout.split("\n")
              if any(package in installed_package for installed_package in self.installed_packages):
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
          if self.system_package_manager == "pacman":
            query_command.extend(["pacman", "-Qq", package])
          elif self.system_package_manager == "apt":
            query_command.extend(["dpkg", "-s", package])
          elif self.system_package_manager == "dnf":
            query_command.extend(["rpm", "-q", package])
          elif self.system_package_manager == "zypper":
            query_command.extend(["rpm", "-q", package])
          result = self._run_command(query_command, check=False)
          
          if result and result.stdout:
             self.installed_packages = result.stdout.split("\n")

          if result and result.returncode == 0:
              if self.verbose:
                self.logger.debug(f"Package {package} is installed")
              return True
          else:
              if self.verbose:
                self.logger.debug(f"Package {package} is not installed")
              return False