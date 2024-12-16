import os
import shutil
import subprocess
from src.utils import setup_logger, sanitize_path, create_timestamp, confirm_action
from src.config import ConfigManager
import sys
import re
import json
logger = setup_logger()

class DotfileManager:

    def __init__(self, verbose=False):
        self.verbose = verbose
        self.config_manager = ConfigManager()
        self.logger = setup_logger(verbose)
        self.managed_rices_dir = sanitize_path("~/.config/managed-rices")
        self._ensure_managed_dir()
        self.rules_config = self._load_rules()
        self.nix_installed = False

    def _ensure_managed_dir(self):
      """Create managed rices directory if it does not exist."""
      if not os.path.exists(self.managed_rices_dir):
          os.makedirs(self.managed_rices_dir, exist_ok = True)

    def _load_rules(self):
      """Loads the rules to discover the dotfile directories"""
      rules_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs", "rules.json")
      try:
        if os.path.exists(rules_path):
            with open(rules_path, 'r') as f:
              return json.load(f)
        else:
          return {}
      except Exception as e:
          self.logger.error(f"Could not load rules config: {e}")
          return {}

    def _run_command(self, command, check = True):
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
              self.logger.debug(f"Output:\n{result.stdout}")
          return result
      except FileNotFoundError as e:
          self.logger.error(f"Command not found: {command[0]}: {e}")
          return False
      except Exception as e:
         self.logger.error(f"Error executing command: {command}. Error: {e}")
         return False

    def clone_repository(self, repository_url):
      """Clones a git repository."""
      try:
        repo_name = repository_url.split('/')[-1].replace(".git", "")
        local_dir = os.path.join(self.managed_rices_dir, repo_name)
        if os.path.exists(local_dir):
          self.logger.error(f"Repository with same name already exists at {local_dir}")
          return False
        self.logger.info(f"Cloning repository into {local_dir}")
        clone_result = self._run_command(["git", "clone", repository_url, local_dir])

        if clone_result:
          self.logger.info(f"Repository cloned successfully to: {local_dir}")
          timestamp = create_timestamp()
          config = {
            'repository_url': repository_url,
            'local_directory': local_dir,
            'dotfile_directories': {},  
            'config_backup_path': None,
            'dependencies': [],
            'applied': False,
            'timestamp': timestamp,
            'nix_config': False
          }
          self.config_manager.add_rice_config(repo_name, config)
          return True
        else:
            self.logger.error(f"Failed to clone repository: {repository_url}")
            return False

      except Exception as e:
         self.logger.error(f"Error cloning the repository: {repository_url}. Error: {e}")
         return False

    def _is_likely_dotfile_dir(self, dir_path):
        """Checks if the directory is likely to contain dotfiles based on its name, content, and rules."""
        score = 0
        dir_name = os.path.basename(dir_path)
        
        # Check against rules from rules.json
        for rule in self.rules_config.get('rules', []):
            if rule.get('regex'):
                try:
                    if re.search(rule['regex'], dir_name):
                        score += 3  # Higher weight for custom rules
                except Exception as e:
                    self.logger.error(f"Error with rule regex: {rule['regex']}. Check your rules.json file. Error: {e}")
            elif dir_name == rule.get('name'):
                score += 3

        # Common desktop environment/window manager configs
        de_wm_names = [
            "nvim", "zsh", "hypr", "waybar", "alacritty", "dunst", "rofi", "sway", 
            "gtk-3.0", "fish", "kitty", "i3", "bspwm", "awesome", "polybar", "picom",
            "qtile", "xmonad", "openbox", "dwm", "eww", "wezterm", "foot"
        ]
        if dir_name in de_wm_names:
            score += 2

        # Check for common dotfile extensions
        dotfile_extensions = [".conf", ".toml", ".yaml", ".yml", ".json", ".config", 
                            ".sh", ".bash", ".zsh", ".fish", ".lua", ".vim", ".el"]
        for item in os.listdir(dir_path):
            if os.path.isfile(os.path.join(dir_path, item)):
                if any(item.endswith(ext) for ext in dotfile_extensions):
                    score += 1

        # Check for specific content and configuration patterns
        config_keywords = [
            "nvim", "hyprland", "waybar", "zsh", "alacritty", "dunst", "rofi", 
            "sway", "gtk", "fish", "kitty", "config", "theme", "colorscheme",
            "keybind", "workspace", "window", "border", "font", "opacity"
        ]
        
        for item in os.listdir(dir_path):
            if os.path.isfile(os.path.join(dir_path, item)):
                try:
                    with open(os.path.join(dir_path, item), 'r', errors='ignore') as file:
                        content = file.read(1024)  # Read first 1KB for performance
                        for keyword in config_keywords:
                            if keyword in content.lower():
                                score += 0.5
                except:
                    pass  # Skip files that can't be read

        # Return true if score meets threshold
        return score >= 2  # Adjust threshold as needed

    def _categorize_dotfile_directory(self, dir_path):
        """Categorizes a dotfile directory as 'config', 'wallpaper', 'script', etc."""
        dir_name = os.path.basename(dir_path)

        if dir_name == "wallpapers" or dir_name == "wallpaper" or dir_name == "backgrounds":
           return "wallpaper"
        elif dir_name == "scripts":
          return "script"
        elif dir_name == "icons" or dir_name == "cursors":
            return "icon"
        elif dir_name == "cache":
           return "cache"
        elif dir_name == ".local":
           return "local"
        else:
           return "config" # If not specified, consider as a config directory

    def _discover_dotfile_directories(self, local_dir, target_packages = None):
        """Detects dotfile directories using the improved heuristics, and categorizes them."""
        dotfile_dirs = {}  
        for item in os.listdir(local_dir):
           item_path = os.path.join(local_dir, item)
           if os.path.isdir(item_path):
              if target_packages: # If target packages are specified.
                if item in target_packages:
                     category = self._categorize_dotfile_directory(item_path)
                     dotfile_dirs[item] = category
                if item == ".config": # First case, a .config folder in the root folder
                  for sub_item in os.listdir(item_path):
                    sub_item_path = os.path.join(item_path, sub_item)
                    if os.path.isdir(sub_item_path) and self._is_likely_dotfile_dir(sub_item_path) and sub_item in target_packages:
                      category = self._categorize_dotfile_directory(sub_item_path)
                      dotfile_dirs[os.path.join(item, sub_item)] = category
                elif os.path.exists(os.path.join(item_path, ".config")): # Second case, a config folder inside another folder
                   for sub_item in os.listdir(os.path.join(item_path, ".config")):
                     sub_item_path = os.path.join(item_path, ".config", sub_item)
                     if os.path.isdir(sub_item_path) and self._is_likely_dotfile_dir(sub_item_path) and sub_item in target_packages:
                        category = self._categorize_dotfile_directory(sub_item_path)
                        dotfile_dirs[os.path.join(item, ".config", sub_item)] = category
              else:
                  if item == ".config":  # First case, a .config folder in the root folder
                      for sub_item in os.listdir(item_path):
                          sub_item_path = os.path.join(item_path, sub_item)
                          if os.path.isdir(sub_item_path) and self._is_likely_dotfile_dir(sub_item_path):
                              category = self._categorize_dotfile_directory(sub_item_path)
                              dotfile_dirs[os.path.join(item, sub_item)] = category
                  elif os.path.exists(os.path.join(item_path, ".config")):  # Second case, a config folder inside another folder.
                      for sub_item in os.listdir(os.path.join(item_path, ".config")):
                          sub_item_path = os.path.join(item_path, ".config", sub_item)
                          if os.path.isdir(sub_item_path) and self._is_likely_dotfile_dir(sub_item_path):
                              category = self._categorize_dotfile_directory(sub_item_path)
                              dotfile_dirs[os.path.join(item, ".config", sub_item)] = category
                  elif self._is_likely_dotfile_dir(item_path):  # Third case, if the folder is the dotfile itself, like hypr, nvim, etc.
                      category = self._categorize_dotfile_directory(item_path)
                      dotfile_dirs[item] = category
        return dotfile_dirs

    def _discover_dependencies(self, local_dir, dotfile_dirs):
        """Detects dependencies based on the dotfile directories, dependency files and package definitions."""
        dependencies = []
        package_managers = {
            'pacman': ['pkglist.txt', 'packages.txt', 'arch-packages.txt'],
            'apt': ['apt-packages.txt', 'debian-packages.txt'],
            'dnf': ['fedora-packages.txt', 'rpm-packages.txt'],
            'brew': ['brewfile', 'Brewfile'],
            'pip': ['requirements.txt', 'python-packages.txt'],
            'cargo': ['Cargo.toml'],
            'npm': ['package.json']
        }

        # Check for package manager specific dependency files
        for pm, files in package_managers.items():
            for file in files:
                dep_file_path = os.path.join(local_dir, file)
                if os.path.exists(dep_file_path) and os.path.isfile(dep_file_path):
                    try:
                        if file == 'package.json':
                            with open(dep_file_path, 'r') as f:
                                data = json.load(f)
                                deps = data.get('dependencies', {})
                                deps.update(data.get('devDependencies', {}))
                                for pkg in deps.keys():
                                    dependencies.append(f"npm:{pkg}")
                        elif file == 'Cargo.toml':
                            # Parse TOML file for Rust dependencies
                            with open(dep_file_path, 'r') as f:
                                for line in f:
                                    if '=' in line and '[dependencies]' in open(dep_file_path).read():
                                        pkg = line.split('=')[0].strip()
                                        dependencies.append(f"cargo:{pkg}")
                        else:
                            with open(dep_file_path, 'r') as f:
                                for line in f:
                                    line = line.strip()
                                    if line and not line.startswith('#'):
                                        dependencies.append(f"{pm}:{line}")
                    except Exception as e:
                        self.logger.warning(f"Error parsing dependency file {file}: {e}")

        # Check common config directories for implicit dependencies
        common_deps = {
            'nvim': ['neovim'],
            'zsh': ['zsh'],
            'hypr': ['hyprland'],
            'waybar': ['waybar'],
            'alacritty': ['alacritty'],
            'dunst': ['dunst'],
            'rofi': ['rofi'],
            'sway': ['sway'],
            'fish': ['fish'],
            'kitty': ['kitty'],
            'i3': ['i3-wm'],
            'bspwm': ['bspwm'],
            'polybar': ['polybar'],
            'picom': ['picom'],
            'qtile': ['qtile'],
            'xmonad': ['xmonad'],
            'eww': ['eww-wayland']
        }

        for dir_name in dotfile_dirs:
            base_name = os.path.basename(dir_name)
            if base_name in common_deps:
                dependencies.extend(f"auto:{dep}" for dep in common_deps[base_name])

        # Check arch-packages directory
        arch_packages_dir = os.path.join(local_dir, "arch-packages")
        if os.path.exists(arch_packages_dir) and os.path.isdir(arch_packages_dir):
            for item in os.listdir(arch_packages_dir):
                item_path = os.path.join(arch_packages_dir, item)
                if os.path.isdir(item_path):
                    dependencies.append(f"pacman:{item}")

        return list(set(dependencies))  # Remove duplicates

    def _check_nix_config(self, local_dir):
      """Checks if the repository contains a NixOS configuration."""
      nix_files = ["flake.nix", "configuration.nix"]
      for file in nix_files:
        if os.path.exists(os.path.join(local_dir, file)):
          return True
      return False

    def _apply_nix_config(self, local_dir, package_manager):
       """Applies a NixOS configuration."""
       if not package_manager.nix_installed:
            if not package_manager._install_nix():
                self.logger.error("Nix is required, and failed to install. Aborting.")
                return False
       self.logger.info("Applying nix configuration.")
       try:
        nix_apply_command = ["nix", "build", ".#system", "--print-out-paths"]
        nix_apply_result = self._run_command(nix_apply_command, cwd = local_dir)
        if not nix_apply_result:
           return False
        profile_path = nix_apply_result.stdout.strip()
        nix_switch_command = ["sudo", "nix-env", "-p", "/nix/var/nix/profiles/system", "-i", profile_path]
        switch_result = self._run_command(nix_switch_command)
        if not switch_result:
            return False
        return True

       except Exception as e:
         self.logger.error(f"Error applying nix configuration: {e}")
         return False


    def _apply_config_directory(self, local_dir, directory, stow_options = []):
      """Applies the dotfiles using GNU Stow."""
      stow_dir = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
      if os.path.basename(directory) != ".config" and not os.path.exists(stow_dir):
          os.makedirs(stow_dir, exist_ok = True)
      stow_command = ["stow", "-v"]
      stow_command.extend(stow_options)
      stow_command.append(os.path.basename(directory))
      stow_result = self._run_command(stow_command, check=False, cwd=local_dir)
      if not stow_result or stow_result.returncode != 0:
          self.logger.error(f"Failed to stow config: {directory}. Check if Stow is installed, and if the options are correct: {stow_options}")
          return False
      return True

    def _apply_cache_directory(self, local_dir, directory, stow_options = []):
        """Applies a cache directory using GNU Stow."""
        stow_command = ["stow", "-v"]
        stow_command.extend(stow_options)
        stow_command.append(os.path.basename(directory))
        stow_result = self._run_command(stow_command, check = False, cwd=local_dir)
        if not stow_result or stow_result.returncode != 0:
            self.logger.error(f"Failed to stow cache: {directory}. Check if Stow is installed, and if the options are correct: {stow_options}")
            return False
        return True
    def _apply_local_directory(self, local_dir, directory, stow_options = []):
      """Applies a local directory using GNU Stow."""
      stow_command = ["stow", "-v"]
      stow_command.extend(stow_options)
      stow_command.append(os.path.basename(directory))
      stow_result = self._run_command(stow_command, check = False, cwd=local_dir)
      if not stow_result or stow_result.returncode != 0:
         self.logger.error(f"Failed to stow local files: {directory}. Check if Stow is installed, and if the options are correct: {stow_options}")
         return False
      return True

    def _apply_other_directory(self, local_dir, directory):
       """Applies files that aren't configs (wallpaper, scripts) into the home directory"""
       dir_path = os.path.join(local_dir, directory)
       target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
       if os.path.exists(target_path): # if a folder already exists, abort.
         self.logger.warning(f"Path {target_path} already exists, skipping...")
         return False
       try:
        shutil.copytree(dir_path, target_path)
        self.logger.info(f"Copied directory {dir_path} to {target_path}")
       except NotADirectoryError:
         try:
           shutil.copy2(dir_path, target_path)
           self.logger.info(f"Copied file {dir_path} to {target_path}")
         except Exception as e:
            self.logger.error(f"Error copying file {dir_path} to {target_path}: {e}")
            return False
       except Exception as e:
          self.logger.error(f"Error copying directory {dir_path} to {target_path}: {e}")
          return False
       return True

    def apply_dotfiles(self, repository_name, stow_options = [], package_manager = None, target_packages = None):
        """Applies dotfiles from a repository using GNU Stow."""
        rice_config = self.config_manager.get_rice_config(repository_name)
        if not rice_config:
            self.logger.error(f"No configuration found for repository: {repository_name}")
            return False

        local_dir = rice_config['local_directory']
        nix_config = self._check_nix_config(local_dir)
        rice_config['nix_config'] = nix_config
        self.config_manager.add_rice_config(repository_name, rice_config)

        if nix_config:
          if not self._apply_nix_config(local_dir, package_manager):
            return False
          rice_config['applied'] = True
          self.config_manager.add_rice_config(repository_name, rice_config)
          self.logger.info("Nix configuration applied sucessfully")
          return True
        if target_packages:
          if not isinstance(target_packages, list):
            target_packages = [target_packages]
          self.logger.info(f"Applying dots for: {', '.join(target_packages)}")
        dotfile_dirs = self._discover_dotfile_directories(local_dir, target_packages)
        if not dotfile_dirs:
           self.logger.warning("No dotfile directories found. Aborting")
           return False
        # Check for multiple rices (top-level directories)
        top_level_dirs = [os.path.basename(dir) for dir in dotfile_dirs if not os.path.dirname(dir)]
        if len(top_level_dirs) > 1 and not target_packages:
           chosen_rice = self._prompt_multiple_rices(top_level_dirs)
           if not chosen_rice:
              self.logger.warning("Installation aborted.")
              return False
           # Filter out all the other directories that aren't this one
           dotfile_dirs = {dir: category for dir, category in dotfile_dirs.items() if os.path.basename(dir).startswith(chosen_rice)}
           if not dotfile_dirs:
            self.logger.error("No dotfiles were found with the specified rice name.")
            return False

        rice_config['dotfile_directories'] = dotfile_dirs
        dependencies = self._discover_dependencies(local_dir, dotfile_dirs)
        rice_config['dependencies'] = dependencies
        self.config_manager.add_rice_config(repository_name, rice_config)

        applied_all = True
        for directory, category in dotfile_dirs.items():
            dir_path = os.path.join(local_dir, directory)
            if not os.path.exists(dir_path):
              self.logger.warning(f"Could not find directory: {dir_path}")
              continue
            if category == "config":
              if not self._apply_config_directory(local_dir, directory, stow_options):
                applied_all = False
            elif category == "cache":
                if not self._apply_cache_directory(local_dir, directory, stow_options):
                  applied_all = False
            elif category == "local":
                if not self._apply_local_directory(local_dir, directory, stow_options):
                    applied_all = False
            else: # wallpaper, scripts, icons, etc.
               if not self._apply_other_directory(local_dir, directory):
                  applied_all = False

        if applied_all:
            self.logger.info(f"Successfully applied dotfiles from {repository_name}")
            rice_config['applied'] = True
            self.config_manager.add_rice_config(repository_name, rice_config)
            return True
        else:
           self.logger.error(f"Failed to apply all dotfiles")
           return False

    def manage_dotfiles(self, repository_name, stow_options = [], package_manager = None, target_packages = None):
         """Manages the dotfiles, uninstalling the previous rice, and applying the new one."""
         current_rice = None
         for key, value in self.config_manager.config_data.items():
            if value.get('applied', False):
              current_rice = key
              break

         if current_rice:
           if not self._uninstall_dotfiles(current_rice):
             return False

         if not self.apply_dotfiles(repository_name, stow_options, package_manager, target_packages):
           return False
         return True

    def _uninstall_dotfiles(self, repository_name):
      """Uninstalls all the dotfiles, from a previous rice."""
      rice_config = self.config_manager.get_rice_config(repository_name)
      if not rice_config:
          self.logger.error(f"No config found for repository: {repository_name}")
          return False
      local_dir = rice_config['local_directory']
      dotfile_dirs = rice_config['dotfile_directories']
      unlinked_all = True
      for directory, category in dotfile_dirs.items():
        if category == "config":
          target_path = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
          if not os.path.exists(target_path):
             self.logger.warning(f"Could not find config directory: {target_path}. Skipping...")
             continue
          stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
          stow_result = self._run_command(stow_command, check = False, cwd = local_dir)
          if not stow_result or stow_result.returncode != 0:
              unlinked_all = False
              self.logger.error(f"Failed to unstow config: {directory} from {target_path}")
        elif category == "cache":
          stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
          stow_result = self._run_command(stow_command, check = False, cwd=local_dir)
          if not stow_result or stow_result.returncode != 0:
             unlinked_all = False
             self.logger.error(f"Failed to unstow cache: {directory}")
        elif category == "local":
           stow_command = ["stow", "-v", "-D", os.path.basename(directory)]
           stow_result = self._run_command(stow_command, check=False, cwd=local_dir)
           if not stow_result or stow_result.returncode != 0:
              unlinked_all = False
              self.logger.error(f"Failed to unstow local files: {directory}")
        else: #Other directories (wallpapers, scripts, etc).
            target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
            if os.path.exists(target_path):
               try:
                 shutil.rmtree(target_path)
                 self.logger.debug(f"Removed directory: {target_path}")
               except NotADirectoryError:
                 try:
                  os.remove(target_path)
                  self.logger.debug(f"Removed file: {target_path}")
                 except Exception as e:
                   self.logger.error(f"Error removing file: {target_path}. Error: {e}")
               except Exception as e:
                   self.logger.error(f"Error removing directory {target_path}: {e}")
            else:
              self.logger.warning(f"Could not find other directory: {target_path}. Skipping...")
      if unlinked_all:
            self.logger.info(f"Successfully uninstalled the dotfiles for: {repository_name}")
            rice_config['applied'] = False
            self.config_manager.add_rice_config(repository_name, rice_config)
            return True
      else:
        self.logger.error("Failed to unlink all the symlinks.")
        return False

    def create_backup(self, repository_name, backup_name):
       """Creates a backup of the applied configuration."""
       rice_config = self.config_manager.get_rice_config(repository_name)
       if not rice_config or not rice_config.get('applied', False):
           self.logger.error(f"No rice applied for {repository_name}. Can't create backup.")
           return False
       backup_dir = os.path.join(rice_config['local_directory'], "backups", backup_name)
       if os.path.exists(backup_dir):
         self.logger.error(f"Backup with the name {backup_name} already exists. Aborting.")
         return False

       os.makedirs(backup_dir, exist_ok=True)

       for directory, category in rice_config['dotfile_directories'].items():
          if category == "config":
            target_path = os.path.join(os.path.expanduser("~/.config"), os.path.basename(directory))
            if not os.path.exists(target_path):
               continue
          elif category == "cache":
            target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory)) #Cache files into home.
            if not os.path.exists(target_path):
               continue
          elif category == "local":
            target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory)) # local files into home.
            if not os.path.exists(target_path):
                continue
          else:
            target_path = os.path.join(os.path.expanduser("~"), os.path.basename(directory))
            if not os.path.exists(target_path):
                continue
          backup_target = os.path.join(backup_dir, os.path.basename(directory))
          try:
            shutil.copytree(target_path, backup_target)
            self.logger.debug(f"Copied {target_path} to {backup_target}")
          except NotADirectoryError:
               try:
                   shutil.copy2(target_path, backup_target)
                   self.logger.debug(f"Copied file {target_path} to {backup_target}")
               except Exception as e:
                   self.logger.error(f"Error copying file {target_path}: {e}")
          except Exception as e:
                self.logger.error(f"Error copying directory {target_path}: {e}")
          rice_config['config_backup_path'] = backup_dir
          self.config_manager.add_rice_config(repository_name, rice_config)

       self.logger.info(f"Backup created successfully at {backup_dir}")
       return True
    def _prompt_multiple_rices(self, rice_names):
        """Prompts the user to choose which rice to install from multiple options."""
        self.logger.warning(f"Multiple rices detected: {', '.join(rice_names)}. Please choose which one you would like to install.")
        while True:
           prompt = f"Which rice do you want to install? ({', '.join(rice_names)}, N to cancel): "
           choice = input(prompt).strip()
           if choice in rice_names:
            return choice
           elif choice.lower() == 'n':
             return None
           else:
            self.logger.warning("Invalid choice, please type the exact name of a rice, or type N to cancel")