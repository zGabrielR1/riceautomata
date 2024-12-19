# src/cli.py
import argparse
import sys
from src.utils import setup_logger, sanitize_url, exception_handler
from src.package import PackageManager
from src.dotfile import DotfileManager
import logging
import os
import json
from typing import Dict, Any
from colorama import init, Fore, Style

init()  # Initialize colorama for colored output

def print_profiles(profiles: Dict[str, Any], active_profile: str) -> None:
    """Pretty print the profiles information."""
    print(f"{Fore.GREEN}Active Profile:{Style.RESET_ALL} {active_profile}")
    print(f"\n{Fore.CYAN}Available Profiles:{Style.RESET_ALL}")
    for profile in sorted(profiles.keys()):
        prefix = "* " if profile == active_profile else "  "
        print(f"{prefix}{profile}")

def main():
    sys.excepthook = exception_handler
    parser = argparse.ArgumentParser(description="Automate the management of dotfiles")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    subparsers = parser.add_subparsers(title="Commands", dest="command", help="Available commands")

    # Profile management commands
    list_profiles_parser = subparsers.add_parser("list-profiles", help="List available profiles for a repository")
    list_profiles_parser.add_argument("repository_name", type=str, help="Name of the repository")

    create_profile_parser = subparsers.add_parser("create-profile", help="Create a new profile for a repository")
    create_profile_parser.add_argument("repository_name", type=str, help="Name of the repository")
    create_profile_parser.add_argument("profile_name", type=str, help="Name of the new profile")

    switch_profile_parser = subparsers.add_parser("switch-profile", help="Switch to a different profile")
    switch_profile_parser.add_argument("repository_name", type=str, help="Name of the repository")
    switch_profile_parser.add_argument("profile_name", type=str, help="Name of the profile to switch to")

    # Clone Repository command
    clone_parser = subparsers.add_parser("clone", aliases=["-S"], help="Clone a dotfiles repository")
    clone_parser.add_argument("repository_url", type=str, help="URL of the repository to clone")

    # Apply dotfiles command
    apply_parser = subparsers.add_parser("apply", aliases=["-A"], help="Apply dotfiles from a local repository")
    
    apply_parser.add_argument(
    "repository_name", type=lambda s: s.split(","), default=[], 
    help="Name of the repository to apply")
    apply_parser.add_argument(
        "--discover-templates", action="store_true",
        help="Discover all templates recursively in all directories."
    )
    apply_parser.add_argument(
    "--custom-scripts", type=lambda s: s.split(","), default=[],
    help="List of custom scripts to be discovered, separated by commas"
    )
    apply_parser.add_argument(
    "--custom-rules", type=lambda s: s.split(","), default=[],
    help="List of custom rules to be discovered, separated by commas"
    )
    apply_parser.add_argument(
    "--stow-options", type=lambda s: s.split(" "), default=[],
    help="Options for GNU Stow command, separated by spaces"
    )
    apply_parser.add_argument(
    "--target-packages", type=lambda s: s.split(","), default=[],
    help="List of packages to install only the configs, separated by commas"
    )
    apply_parser.add_argument(
    "--custom-paths", type=lambda s: s.split(","), default=[],
    help="List of custom paths to be discovered as dotfiles, separated by commas"
    )
    apply_parser.add_argument(
    "--ignore-rules", action="store_true", 
    help="Ignores the custom rules for discovering dotfiles."
    )
    apply_parser.add_argument(
    "--template-context", type=lambda s: s.split(","),default=[], 
    help="Path to the json with template variables"
    )
    apply_parser.add_argument(
    "--custom-extras-paths", type=lambda s: s.split(","), default=[],
    help="List of custom paths to be discovered as extras, separated by commas"
    )
    apply_parser.add_argument(
    "--profile", type=lambda s: s.split(","), default=[], 
    help="Profile to use for this operation"
    )

    # Manage dotfiles command
    manage_parser = subparsers.add_parser("manage", aliases=["-m"], help="Manage dotfiles, uninstalling the previous ones, and applying the new ones")
    manage_parser.add_argument("repository_name", type=str, help="Name of the repository to manage")
    manage_parser.add_argument("--discover-templates", action="store_true", help="Discover all templates recursively in all directories.")
    manage_parser.add_argument("--custom-scripts", type=str, help="List of custom scripts to be discovered, separated with commas")
    manage_parser.add_argument("--stow-options", type=str, help="Options for GNU Stow command, separated with spaces")
    manage_parser.add_argument("--target-packages", type=str, help="List of packages to install only the configs, separated with commas")
    manage_parser.add_argument("--custom-paths", type=str, help="List of custom paths to be discovered as dotfiles, separated with commas")
    manage_parser.add_argument("--ignore-rules", action="store_true", help="Ignores the custom rules for discovering dotfiles.")
    manage_parser.add_argument("--template-context", type=str, help="Path to the json with template variables")
    manage_parser.add_argument("--custom-extras-paths", type=str, help="Path to the JSON with custom extras paths")
    manage_parser.add_argument("--profile", type=str, help="Profile to use for this operation")

    # Create backup command
    backup_parser = subparsers.add_parser("backup", aliases=["-b"], help="Create a backup of the applied configuration")
    backup_parser.add_argument("backup_name", type=str, help="Name of the backup")
    backup_parser.add_argument("repository_name", type=str, help="Name of the repository to back up")

    # Global options
    parser.add_argument("--distro", type=str, help="Specify the distribution to use")
    parser.add_argument("--aur-helper", type=str, default="paru", choices=["paru", "yay"], help="Specify the AUR helper to use")
    parser.add_argument("--shell", type=str, default="bash", choices=["bash", "zsh", "fish"], help="Specify the shell to use for the scripts")

    args = parser.parse_args()

    # Initialize logger immediately after parsing arguments
    logger = setup_logger(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    package_manager = PackageManager(args.verbose, args.aur_helper)
    dotfile_manager = DotfileManager(args.verbose)

    if args.distro:
        package_manager.set_package_manager(args.distro)

    try:
        if args.command == "list-profiles":
            rice_config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
            if not rice_config:
                logger.error(f"Repository {args.repository_name} not found")
                sys.exit(1)
            profiles = rice_config.get('profiles', {})
            active_profile = rice_config.get('active_profile', 'default')
            print_profiles(profiles, active_profile)

        elif args.command == "create-profile":
            dotfile_manager.config_manager.create_profile(args.repository_name, args.profile_name)
            logger.info(f"Created new profile: {args.profile_name}")

        elif args.command == "switch-profile":
            dotfile_manager.config_manager.switch_profile(args.repository_name, args.profile_name)
            logger.info(f"Switched to profile: {args.profile_name}")

        elif args.command == "clone":
            if not dotfile_manager.clone_repository(sanitize_url(args.repository_url)):
                sys.exit(1)

        elif args.command == "manage":
            if args.shell:
                dotfile_manager.config_manager.set_rice_config(args.repository_name, 'script_config', {'shell': args.shell})
            if args.custom_extras_paths:
                try:
                    with open(args.custom_extras_paths, 'r') as f:
                        custom_extras_paths = json.load(f)
                        dotfile_manager.config_manager.set_rice_config(args.repository_name, 'custom_extras_paths', custom_extras_paths)
                except Exception as e:
                    logger.error(f"Error loading custom extras paths: {e}")
                    sys.exit(1)
            if args.profile:
                dotfile_manager.config_manager.switch_profile(args.repository_name, args.profile)
            if not _handle_nix_rice_installation(args, dotfile_manager, package_manager, logger):
                sys.exit(1)
            _handle_manage_apply_command(args, dotfile_manager, package_manager, logger, manage=True)

        elif args.command == "backup":
            if not dotfile_manager.create_backup(args.repository_name, args.backup_name):
                sys.exit(1)

        elif args.command == "apply":
            if args.profile:
                dotfile_manager.config_manager.switch_profile(args.repository_name, args.profile)
            if not _handle_nix_rice_installation(args, dotfile_manager, package_manager, logger):
                sys.exit(1)
            _handle_manage_apply_command(args, dotfile_manager, package_manager, logger, manage=False)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)

def _handle_nix_rice_installation(args, dotfile_manager, package_manager, logger):
    """Handles the installation of Nix rices."""
    try:
        rice_config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
        if not rice_config:
            logger.error(f"No configuration found for repository: {args.repository_name}")
            return False

        if 'nix' in rice_config.get('dependencies', []):
            if not package_manager._check_nix():
                logger.info("Nix is not installed. Skipping Nix rice installation.")
                return True

            logger.info("Installing Nix rice...")
            # Implement logic to install Nix rice here
            # Example: package_manager.install_nix_rice(rice_config)
            return True

    except Exception as e:
        logger.error(f"An error occurred during Nix rice installation: {e}")
        return False

def _handle_manage_apply_command(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger, manage: bool = False) -> None:
    """Handles both the apply and manage commands, reducing code duplication."""
    try:
        if args.target_packages:
            target_packages = args.target_packages.split(",")
        else:
            target_packages = None
        if args.stow_options:
            stow_options = args.stow_options.split(" ")
        else:
            stow_options = []
        if args.custom_paths:
            custom_paths = args.custom_paths.split(",")
        else:
            custom_paths = None
        if args.template_context:
            try:
                with open(args.template_context, 'r') as f:
                    template_context = json.load(f)
            except Exception as e:
                logger.error(f"Error loading template context: {e}")
                sys.exit(1)
        else:
            template_context = {}
        if args.custom_scripts:
            custom_scripts = args.custom_scripts.split(",")
        else:
            custom_scripts = None
        if manage:
            if not dotfile_manager.manage_dotfiles(args.repository_name, stow_options, package_manager, target_packages, custom_paths, args.ignore_rules, template_context, args.discover_templates, custom_scripts):
                sys.exit(1)
        else:
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
            if not package_manager.install(packages_to_install, local_dir=rice_config.get('local_directory')):
                sys.exit(1)
            if args.overwrite_sym:
                overwrite_sym = args.overwrite_sym.split(",")
            else:
                overwrite_sym = None
            if not dotfile_manager.apply_dotfiles(args.repository_name, stow_options, package_manager, target_packages, overwrite_sym, custom_paths, args.ignore_rules, template_context, args.discover_templates, custom_scripts):
                sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred in command: {args.command}. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()