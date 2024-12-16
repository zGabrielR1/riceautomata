import argparse
import sys
from src.utils import setup_logger, sanitize_url, exception_handler
from src.package import PackageManager
from src.dotfile import DotfileManager
import logging
import os

def main():
  sys.excepthook = exception_handler
  parser = argparse.ArgumentParser(description="Automate the management of dotfiles")
  parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

  subparsers = parser.add_subparsers(title="Commands", dest="command", help="Available commands")

  # Clone Repository command
  clone_parser = subparsers.add_parser("clone", aliases=["-S"], help="Clone a dotfiles repository")
  clone_parser.add_argument("repository_url", type=str, help="URL of the repository to clone")

  # Apply dotfiles command
  apply_parser = subparsers.add_parser("apply", aliases=["-A"], help="Apply dotfiles from a local repository")
  apply_parser.add_argument("repository_name", type=str, help="Name of the repository to apply")
  apply_parser.add_argument("--skip-packages", type=str, help="List of packages to be skipped, separated with commas")
  apply_parser.add_argument("--stow-options", type=str, help="Options for GNU Stow command, separated with spaces")
  apply_parser.add_argument("--target-packages", type=str, help="List of packages to install only the configs, separated with commas")

  # Manage dotfiles command
  manage_parser = subparsers.add_parser("manage", aliases=["-m"], help="Manage dotfiles, uninstalling the previous ones, and applying the new ones")
  manage_parser.add_argument("repository_name", type=str, help="Name of the repository to manage")
  manage_parser.add_argument("--stow-options", type=str, help="Options for GNU Stow command, separated with spaces")
  manage_parser.add_argument("--target-packages", type=str, help="List of packages to install only the configs, separated with commas")

  # Create backup command
  backup_parser = subparsers.add_parser("backup", aliases=["-b"], help="Create a backup of the applied configuration")
  backup_parser.add_argument("backup_name", type=str, help="Name of the backup")
  backup_parser.add_argument("repository_name", type=str, help="Name of the repository to back up")

  # Specify distro
  parser.add_argument("--distro", type=str, help="Specify the distribution to use")

  args = parser.parse_args()

  logger = setup_logger(args.verbose, os.path.expanduser("~/.config/riceautomator/riceautomator.log"))

  package_manager = PackageManager(args.verbose)

  if args.distro:
      package_manager.set_package_manager(args.distro)
  dotfile_manager = DotfileManager(args.verbose)

  if args.command == "clone":
     try:
        url = sanitize_url(args.repository_url)
        if not dotfile_manager.clone_repository(url):
           logger.error(f"Failed to clone repository: {url}")
           sys.exit(1)

     except ValueError as e:
        logger.error(f"Invalid URL: {e}")
        sys.exit(1)

  elif args.command == "apply":
    if args.skip_packages:
      skip_packages = args.skip_packages.split(",")
    else:
      skip_packages = []
    if args.target_packages:
        target_packages = args.target_packages.split(",")
    else:
        target_packages = None

    if args.stow_options:
      stow_options = args.stow_options.split(" ")
    else:
      stow_options = []

    rice_config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
    if not rice_config:
       logger.error(f"No configuration found for {args.repository_name}")
       sys.exit(1)
    dependencies = rice_config.get('dependencies', [])
    packages_to_install = [package for package in dependencies if package not in skip_packages]
    if not package_manager.install(packages_to_install):
        sys.exit(1)
    if not dotfile_manager.apply_dotfiles(args.repository_name, stow_options, package_manager, target_packages):
       sys.exit(1)

  elif args.command == "manage":
    if args.stow_options:
       stow_options = args.stow_options.split(" ")
    else:
       stow_options = []
    if args.target_packages:
        target_packages = args.target_packages.split(",")
    else:
        target_packages = None
    if not dotfile_manager.manage_dotfiles(args.repository_name, stow_options, package_manager, target_packages):
        sys.exit(1)

  elif args.command == "backup":
     if not dotfile_manager.create_backup(args.repository_name, args.backup_name):
        sys.exit(1)

if __name__ == "__main__":
    main()