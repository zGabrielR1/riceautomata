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
  apply_parser.add_argument("--overwrite-sym", type=str, help="Overwrite specific symlinks, separated with commas")

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

  # AUR Helper Selection
  parser.add_argument("--aur-helper", type=str, default="paru", choices=["paru", "yay"], help="Specify the AUR helper to use")

  args = parser.parse_args()

  logger = setup_logger(args.verbose)

  package_manager = PackageManager(args.verbose, args.aur_helper)

  if args.distro: 
      package_manager.set_package_manager(args.distro)
  dotfile_manager = DotfileManager(args.verbose)

  if args.command == "clone":
      if not dotfile_manager.clone_repository(sanitize_url(args.repository_url)):
          sys.exit(1)
  elif args.command == "manage":
    if args.target_packages:
        target_packages = args.target_packages.split(",")
    else:
        target_packages = None

    if args.stow_options:
      stow_options = args.stow_options.split(" ")
    else:
      stow_options = []
    if not dotfile_manager.manage_dotfiles(args.repository_name, stow_options, package_manager, target_packages):
        sys.exit(1)
  elif args.command == "backup":
      if not dotfile_manager.create_backup(args.repository_name, args.backup_name):
          sys.exit(1)
  elif args.command == "apply":
    if args.target_packages:
        target_packages = args.target_packages.split(",")
    else:
        target_packages = None
    if args.skip_packages:
        skip_packages = args.skip_packages.split(",")
    else:
        skip_packages = []

    rice_config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
    if not rice_config:
        logger.error(f"No configuration found for repository: {args.repository_name}")
        sys.exit(1)
    dependencies = rice_config.get('dependencies', [])
    packages_to_install = [package for package in dependencies if package not in skip_packages]
    if not package_manager.install(packages_to_install):
       sys.exit(1)
    if args.overwrite_sym:
      overwrite_sym = args.overwrite_sym
    else: overwrite_sym = None

    if args.stow_options:
      stow_options = args.stow_options.split(" ")
    else:
      stow_options = []
    if not dotfile_manager.apply_dotfiles(args.repository_name, stow_options, package_manager, target_packages, overwrite_sym):
       sys.exit(1)


if __name__ == "__main__":
    main()