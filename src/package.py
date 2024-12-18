# src/packages.py
import subprocess
import os
import shutil
from src.utils import setup_logger, confirm_action
import sys
import json
from abc import ABC, abstractmethod

logger = setup_logger()

class PackageManagerInterface(ABC):
  """Interface for package managers."""
  @abstractmethod
  def install(self, packages):
      """Installs packages."""
      pass
  
  @abstractmethod
  def is_installed(self, package):
    """Checks if a package is installed."""
    pass

class PacmanPackageManager(PackageManagerInterface):
   """Pacman package manager implementation."""

   def __init__(self, aur_helper, logger, verbose):
        self.logger = logger
        self.verbose = verbose
        self.aur_helper = aur_helper

   def _run_command(self, command, check=True):
      """Runs a command and returns the result."""
      try:
        result = subprocess.run(command, capture_output=True, text=True, check=check)
        if check and result.stderr:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error:\n{result.stderr}")
            return False
        if self.verbose:
             self.logger.debug(f"Command ran successfully: {' '.join(command)}")
             if result.stdout:
              self.logger.debug(f"Output:\n{result.stdout}")
        return result
      except FileNotFoundError as e:
        self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
        return False
      except Exception as e:
        self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
        return False

   def _check_paru(self):
      """Checks if Paru is installed"""
      paru_result = self._run_command(["paru", "--version"], check=False)
      return paru_result and paru_result.returncode == 0

   def _check_yay(self):
        """Checks if yay is installed"""
        yay_result = self._run_command(["yay", "--version"], check=False)
        return yay_result and yay_result.returncode == 0

   def _install_aur_helper(self):
      """Installs an AUR Helper (Paru or Yay)."""
      if self.verbose:
        self.logger.info(f"{self.aur_helper} not found, trying to install it.")
      if self.aur_helper == "paru":
        install_result = self._run_command(["sudo", "pacman", "-S", "--noconfirm", "paru"], check=False)
        if install_result and install_result.returncode == 0:
            self.logger.info("Paru installed successfully.")
            return True
        else:
           self.logger.warning("Failed to install Paru with pacman, trying to install with yay instead.")
           return self._install_yay()
      elif self.aur_helper == "yay":
        return self._install_yay()
      else:
        self.logger.error("Invalid AUR Helper specified.")
        return False

   def _install_yay(self):
        """Tries to install yay."""
        install_yay_result = self._run_command(["sudo", "pacman", "-S", "--noconfirm", "yay"], check=False)
        if install_yay_result and install_yay_result.returncode == 0:
              self.logger.info("Yay installed successfully.")
              if self.aur_helper == "paru":
                  install_paru_yay_result = self._run_command(["yay", "-S", "--noconfirm", "paru"], check=False)
                  if install_paru_yay_result and install_paru_yay_result.returncode == 0:
                      self.logger.info("Paru installed successfully using yay")
                      return True
                  else:
                       self.logger.error("Failed to install paru with yay")
                       return False
              return True
        else:
           self.logger.error("Failed to install yay")
           return False

   def _install_pacman_package(self, package, use_paru = True):
        """Installs a package using pacman."""
        install_command = ["sudo", "pacman", "-S", "--noconfirm"]
        if use_paru and (self._check_paru() or self._check_yay()):
           if self.aur_helper == "paru":
            install_command = ["paru", "-S", "--noconfirm"]
           else:
            install_command = ["yay", "-S", "--noconfirm"]
        install_command.append(package)
        install_result = self._run_command(install_command)
        if install_result and install_result.returncode == 0:
            self.logger.info(f"Packages installed: {package}")
            return True
        else:
            self.logger.error(f"Failed to install package: {package}")
            return False

   def install(self, packages, local_dir):
      """Installs a list of packages using the pacman package manager."""
      if not packages:
          self.logger.debug("No pacman packages to install")
          return True
      if not (self._check_paru() or self._check_yay()):
          if not self._install_aur_helper():
            self.logger.error("Can't use aur helper, and failed to install it. Please install manually.")
            return False
      for package in packages:
        if package.startswith("aur:"):
                package_name = package.split(":",1)[1]
                if not self._install_custom_aur_package(local_dir, package_name):
                    return False
        else:
          if not self._install_pacman_package(package):
            return False
      return True

   def _install_custom_aur_package(self, local_dir, package):
        """Installs a custom AUR package using paru."""
        pkgbuild_path = os.path.join(local_dir, package, "PKGBUILD")
        if not os.path.exists(pkgbuild_path):
            self.logger.error(f"PKGBUILD not found for custom aur package: {package}")
            return False
        if self._check_paru() or self._check_yay():
            if self.aur_helper == "paru":
                return self._run_command(["paru", "-S", "--noconfirm", "-B", os.path.dirname(pkgbuild_path)])
            else:
                return self._run_command(["yay", "-S", "--noconfirm", "-B", os.path.dirname(pkgbuild_path)])
        else:
           self.logger.error(f"AUR helper {self.aur_helper} not found. Please install it to install custom packages.")
           return False
   
   def is_installed(self, package):
    """Checks if a package is installed using pacman."""
    query_command = ["pacman", "-Qq", package]
    result = self._run_command(query_command, check=False)
    return result and result.returncode == 0

class AptPackageManager(PackageManagerInterface):
  """Apt package manager implementation."""
  def __init__(self, logger, verbose):
        self.logger = logger
        self.verbose = verbose
  
  def _run_command(self, command, check=True):
      """Runs a command and returns the result."""
      try:
        result = subprocess.run(command, capture_output=True, text=True, check=check)
        if check and result.stderr:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error:\n{result.stderr}")
            return False
        if self.verbose:
             self.logger.debug(f"Command ran successfully: {' '.join(command)}")
             if result.stdout:
              self.logger.debug(f"Output:\n{result.stdout}")
        return result
      except FileNotFoundError as e:
        self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
        return False
      except Exception as e:
        self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
        return False

  def _install_apt_package(self, package):
    """Installs a package using apt."""
    return self._run_command(["sudo", "apt", "install", "-y", package])

  def install(self, packages, local_dir):
    """Installs a list of packages using the apt package manager."""
    if not packages:
        self.logger.debug("No apt packages to install")
        return True
    for package in packages:
      if not self._install_apt_package(package):
         return False
    return True

  def is_installed(self, package):
    """Checks if a package is installed using apt."""
    query_command = ["dpkg", "-s", package]
    result = self._run_command(query_command, check=False)
    return result and result.returncode == 0
  
class DnfPackageManager(PackageManagerInterface):
   """Dnf package manager implementation."""
   def __init__(self, logger, verbose):
        self.logger = logger
        self.verbose = verbose

   def _run_command(self, command, check=True):
        """Runs a command and returns the result."""
        try:
          result = subprocess.run(command, capture_output=True, text=True, check=check)
          if check and result.stderr:
              self.logger.error(f"Command failed: {' '.join(command)}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False
          if self.verbose:
              self.logger.debug(f"Command ran successfully: {' '.join(command)}")
              if result.stdout:
                self.logger.debug(f"Output:\n{result.stdout}")
          return result
        except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
        except Exception as e:
          self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
          return False
   
   def _install_dnf_package(self, package):
        """Installs a package using dnf."""
        return self._run_command(["sudo", "dnf", "install", "-y", package])
    
   def install(self, packages, local_dir):
    """Installs a list of packages using the dnf package manager."""
    if not packages:
        self.logger.debug("No dnf packages to install")
        return True
    for package in packages:
       if not self._install_dnf_package(package):
          return False
    return True

   def is_installed(self, package):
        """Checks if a package is installed using dnf."""
        query_command = ["rpm", "-q", package]
        result = self._run_command(query_command, check=False)
        return result and result.returncode == 0

class ZypperPackageManager(PackageManagerInterface):
  """Zypper package manager implementation."""
  def __init__(self, logger, verbose):
        self.logger = logger
        self.verbose = verbose
  
  def _run_command(self, command, check=True):
      """Runs a command and returns the result."""
      try:
        result = subprocess.run(command, capture_output=True, text=True, check=check)
        if check and result.stderr:
            self.logger.error(f"Command failed: {' '.join(command)}")
            self.logger.error(f"Error:\n{result.stderr}")
            return False
        if self.verbose:
             self.logger.debug(f"Command ran successfully: {' '.join(command)}")
             if result.stdout:
              self.logger.debug(f"Output:\n{result.stdout}")
        return result
      except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
        except Exception as e:
        self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
        return False
  
  def _install_zypper_package(self, package):
       """Installs a package using zypper."""
       return self._run_command(["sudo", "zypper", "install", "-y", package])
  
  def install(self, packages, local_dir):
    """Installs a list of packages using the zypper package manager."""
    if not packages:
        self.logger.debug("No zypper packages to install")
        return True
    for package in packages:
       if not self._install_zypper_package(package):
           return False
    return True

  def is_installed(self, package):
    """Checks if a package is installed using zypper."""
    query_command = ["rpm", "-q", package]
    result = self._run_command(query_command, check=False)
    return result and result.returncode == 0

class PipPackageManager(PackageManagerInterface):
    """Pip package manager implementation."""
    def __init__(self, logger, verbose):
        self.logger = logger
        self.verbose = verbose

    def _run_command(self, command, check=True):
        """Runs a command and returns the result."""
        try:
          result = subprocess.run(command, capture_output=True, text=True, check=check)
          if check and result.stderr:
              self.logger.error(f"Command failed: {' '.join(command)}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False
          if self.verbose:
              self.logger.debug(f"Command ran successfully: {' '.join(command)}")
              if result.stdout:
                self.logger.debug(f"Output:\n{result.stdout}")
          return result
        except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
        except Exception as e:
            self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
            return False

    def _check_pip(self):
        """Checks if pip is installed."""
        pip_result = self._run_command(["pip", "--version"], check=False)
        return pip_result and pip_result.returncode == 0

    def _install_pip_package(self, package):
      """Installs a Python package using pip."""
      if not self._check_pip():
            self.logger.error("pip is not installed")
            return False
      return self._run_command(["pip", "install", "--user", package])
  
    def install(self, packages, local_dir):
      """Installs a list of packages using pip."""
      if not packages:
        self.logger.debug("No pip packages to install")
        return True
      if not self._check_pip():
            self.logger.error("pip is not installed")
            return False
      for package in packages:
         if not self._install_pip_package(package):
           return False
      return True

    def is_installed(self, package):
        """Checks if a package is installed using pip."""
        result = self._run_command(["pip", "show", package], check = False)
        return result and result.returncode == 0

class NpmPackageManager(PackageManagerInterface):
    """Npm package manager implementation."""
    def __init__(self, logger, verbose):
        self.logger = logger
        self.verbose = verbose

    def _run_command(self, command, check=True):
        """Runs a command and returns the result."""
        try:
          result = subprocess.run(command, capture_output=True, text=True, check=check)
          if check and result.stderr:
              self.logger.error(f"Command failed: {' '.join(command)}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False
          if self.verbose:
              self.logger.debug(f"Command ran successfully: {' '.join(command)}")
              if result.stdout:
                self.logger.debug(f"Output:\n{result.stdout}")
          return result
        except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
        except Exception as e:
          self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
          return False

    def _check_npm(self):
        """Checks if npm is installed."""
        npm_result = self._run_command(["npm", "--version"], check=False)
        return npm_result and npm_result.returncode == 0
    
    def _install_npm_package(self, package):
        """Installs a Node.js package using npm."""
        if not self._check_npm():
            self.logger.error("npm is not installed")
            return False
        return self._run_command(["npm", "install", "-g", package])

    def install(self, packages, local_dir):
      """Installs a list of packages using npm."""
      if not packages:
        self.logger.debug("No npm packages to install")
        return True
      if not self._check_npm():
            self.logger.error("npm is not installed")
            return False
      for package in packages:
          if not self._install_npm_package(package):
             return False
      return True
      
    def is_installed(self, package):
        """Checks if a package is installed using npm."""
        result = self._run_command(["npm", "list", "-g", package], check=False)
        return result and result.returncode == 0

class CargoPackageManager(PackageManagerInterface):
    """Cargo package manager implementation."""
    def __init__(self, logger, verbose):
        self.logger = logger
        self.verbose = verbose

    def _run_command(self, command, check=True):
        """Runs a command and returns the result."""
        try:
          result = subprocess.run(command, capture_output=True, text=True, check=check)
          if check and result.stderr:
              self.logger.error(f"Command failed: {' '.join(command)}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False
          if self.verbose:
              self.logger.debug(f"Command ran successfully: {' '.join(command)}")
              if result.stdout:
                self.logger.debug(f"Output:\n{result.stdout}")
          return result
        except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
        except Exception as e:
          self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
          return False

    def _check_cargo(self):
        """Checks if cargo is installed."""
        cargo_result = self._run_command(["cargo", "--version"], check=False)
        return cargo_result and cargo_result.returncode == 0

    def _install_cargo_package(self, package):
        """Installs a Rust package using cargo."""
        if not self._check_cargo():
            self.logger.error("cargo is not installed")
            return False
        return self._run_command(["cargo", "install", package])
    
    def install(self, packages, local_dir):
      """Installs a list of packages using cargo."""
      if not packages:
        self.logger.debug("No cargo packages to install")
        return True
      if not self._check_cargo():
            self.logger.error("cargo is not installed")
            return False
      for package in packages:
        if not self._install_cargo_package(package):
           return False
      return True
    
    def is_installed(self, package):
        """Checks if a package is installed using cargo."""
        result = self._run_command(["cargo", "install", "--list"], check=False)
        if result and result.returncode == 0:
            installed_packages = result.stdout.split("\n")
            return any(package in installed for installed in installed_packages)
        else:
           return False

class PackageManager:

    def __init__(self, verbose=False, aur_helper = "paru"):
        self.verbose = verbose
        self.system_package_manager = self._detect_package_manager()
        self.logger = setup_logger(verbose)
        self.nix_installed = self._check_nix()
        self.aur_helper = aur_helper
        self.package_managers = {
            'pacman': PacmanPackageManager(self.aur_helper, self.logger, self.verbose),
            'apt': AptPackageManager(self.logger, self.verbose),
            'dnf': DnfPackageManager(self.logger, self.verbose),
            'zypper': ZypperPackageManager(self.logger, self.verbose),
            'pip': PipPackageManager(self.logger, self.verbose),
            'npm': NpmPackageManager(self.logger, self.verbose),
            'cargo': CargoPackageManager(self.logger, self.verbose)
        }
    
    def set_package_manager(self, distro):
      """Sets the package manager for the application."""
      if distro:
           if distro.lower() == "arch":
              self.system_package_manager = "pacman"
           elif distro.lower() == "ubuntu" or distro.lower() == "debian":
              self.system_package_manager = "apt"
           elif distro.lower() == "fedora":
               self.system_package_manager = "dnf"
           elif distro.lower() == "opensuse-tumbleweed":
               self.system_package_manager = "zypper"
           else:
              self.system_package_manager = self._detect_package_manager()
      
      self.package_managers['system'] = self.system_package_manager # Update system manager on dict.

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
            for pm_type in ['pip', 'npm', 'cargo']:
              pm_func = self.package_managers.get(pm_type)
              if pm_func.install([package], None):
                return True
            return False
        else:
            self.logger.error(f"Unsupported package manager: {pm}")
            return False
    
    def _install_system_package(self, package):
        """Installs a package using the system package manager."""
        if self.system_package_manager in self.package_managers:
           return self.package_managers.get(self.system_package_manager).install([package], None)
        else:
            self.logger.error(f"Unsupported package manager: {self.system_package_manager}")
            return False
    
    def _install_pip_package(self, package):
       return self.package_managers.get('pip').install([package], None)
    
    def _install_npm_package(self, package):
       return self.package_managers.get('npm').install([package], None)
    
    def _install_cargo_package(self, package):
       return self.package_managers.get('cargo').install([package], None)
    
    def _install_aur_package(self, package):
       return self.package_managers.get('pacman').install([f"aur:{package}"], None)
    
    def _install_from_list(self, list_path):
      """Installs packages from the specified list file."""
      if not os.path.exists(list_path):
        self.logger.error(f"List file not found {list_path}")
        return False
      try:
         with open(list_path, "r") as file:
              packages = [line.strip() for line in file if line.strip() and not line.startswith("#")]
              if packages:
                   if not self.install(packages):
                     return False
      except Exception as e:
          self.logger.error(f"Error reading the list of packages on file: {list_path}. Error: {e}")
          return False
      return True
    def install(self, packages, use_paru = True, local_dir = None):
        """Installs the list of packages using the package manager, with user confirmation."""
        if packages:
            if self.verbose:
                self.logger.info(f"Attempting to install packages: {', '.join(packages)}")
                if not self._install_packages(packages, local_dir):
                  return False
                return True
            else:
                if confirm_action(f"Do you want to install these packages?: {', '.join(packages)}"):
                  if not self._install_packages(packages, local_dir):
                    return False
                  return True
        if local_dir:
           pkg_list = os.path.join(local_dir, ".install_pkg.lst")
           pkg_base_list = os.path.join(local_dir, ".install_pkg_base.lst")
           flatpack_list = os.path.join(local_dir, ".install_flatpack.lst")
           if os.path.exists(pkg_list):
              if not self._install_from_list(pkg_list):
                return False
           if os.path.exists(pkg_base_list):
              if not self._install_from_list(pkg_base_list):
                return False
           if os.path.exists(flatpack_list):
                if not self._install_from_list(flatpack_list):
                    return False
        return True

    
    def _install_packages(self, packages, local_dir = None):
        """Installs a list of packages using the package manager."""
        if not packages:
          self.logger.debug("No packages to install")
          return True
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
          for package in packages:
             if ':' not in package:
               if not self._install_system_package(package):
                  return False
             else:
               pm, _ = package.split(":",1)
               if pm in self.package_managers:
                 if not self.package_managers[pm].install([package.split(":",1)[1]], local_dir):
                    return False
          return True

    def _run_command(self, command, check=True):
        """Runs a command and returns the result."""
        try:
          result = subprocess.run(command, capture_output=True, text=True, check=check)
          if check and result.stderr:
              self.logger.error(f"Command failed: {' '.join(command)}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False
          if self.verbose:
              self.logger.debug(f"Command ran successfully: {' '.join(command)}")
              if result.stdout:
                self.logger.debug(f"Output:\n{result.stdout}")
          return result
        except FileNotFoundError as e:
          self.logger.error(f"Command not found. Make sure {command[0]} is installed: {e}")
          return False
        except Exception as e:
          self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
          return False

    def _check_nix(self):
        """Checks if Nix is installed."""
        try:
            result = self._run_command(["nix", "--version"])
            if result and result.returncode == 0:
                self.nix_installed = True
                return True
            return False
        except FileNotFoundError:
            self.logger.warning("Nix is not installed. Nix-related operations will be skipped.")
            self.nix_installed = False
            return False
        except Exception as e:
            self.logger.error(f"Error checking Nix installation: {e}")
            self.nix_installed = False
            return False

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

    def is_installed(self, package):
      """Checks if a package is installed using the appropriate package manager."""
      if self.nix_installed:
          nix_result = self._run_command(["nix", "profile", "list"], check=False)
          if nix_result and nix_result.returncode == 0:
            installed_packages = nix_result.stdout.split("\n")
            if any(package in installed_package for installed_package in installed_packages):
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
         if ':' not in package:
           if self.system_package_manager in self.package_managers:
              return self.package_managers[self.system_package_manager].is_installed(package)
           else:
               self.logger.error(f"Unsupported package manager: {self.system_package_manager}")
               return False
         else:
            pm, _ = package.split(":", 1)
            if pm in self.package_managers:
               return self.package_managers[pm].is_installed(package.split(":",1)[1])
            else:
                self.logger.error(f"Unsupported package manager: {pm}")
                return False