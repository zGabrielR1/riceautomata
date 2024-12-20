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
    parser = argparse.ArgumentParser(
        description="RiceAutomata - A powerful dotfile and system configuration manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  riceautomata clone https://github.com/user/dotfiles
  riceautomata apply my-dotfiles
  riceautomata -A my-dotfiles --profile minimal
  riceautomata manage my-dotfiles --target-packages i3,polybar
  riceautomata list-profiles my-dotfiles
""")
    
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    subparsers = parser.add_subparsers(title="Commands", dest="command", help="Available commands")

    # Clone command
    clone_parser = subparsers.add_parser("clone", aliases=["-S"], 
        help="Clone a dotfiles repository")
    clone_parser.add_argument("repository_url", help="URL of the repository to clone")

    # Apply command
    apply_parser = subparsers.add_parser("apply", aliases=["-A"], 
        help="Apply dotfiles from a repository")
    apply_parser.add_argument("repository_name", help="Name of the repository to apply")
    apply_parser.add_argument("-p", "--profile", help="Profile to use")
    apply_parser.add_argument("-t", "--target-packages", help="Comma-separated list of packages to configure")
    apply_parser.add_argument("--stow-options", help="Space-separated GNU Stow options")
    apply_parser.add_argument("--templates", action="store_true", help="Process template files")
    apply_parser.add_argument("--custom-paths", help="Comma-separated list of custom paths")
    apply_parser.add_argument("--ignore-rules", action="store_true", help="Ignore discovery rules")

    # Manage command
    manage_parser = subparsers.add_parser("manage", aliases=["-m"], 
        help="Manage dotfiles (uninstall previous, apply new)")
    manage_parser.add_argument("repository_name", help="Name of the repository to manage")
    manage_parser.add_argument("-p", "--profile", help="Profile to use")
    manage_parser.add_argument("-t", "--target-packages", help="Comma-separated list of packages to configure")
    manage_parser.add_argument("--stow-options", help="Space-separated GNU Stow options")

    # Profile commands
    profile_parser = subparsers.add_parser("profile", help="Profile management commands")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    
    list_profile = profile_subparsers.add_parser("list", help="List available profiles")
    list_profile.add_argument("repository_name", help="Repository name")
    
    create_profile = profile_subparsers.add_parser("create", help="Create a new profile")
    create_profile.add_argument("repository_name", help="Repository name")
    create_profile.add_argument("profile_name", help="Profile name")
    
    switch_profile = profile_subparsers.add_parser("switch", help="Switch to a profile")
    switch_profile.add_argument("repository_name", help="Repository name")
    switch_profile.add_argument("profile_name", help="Profile to switch to")

    # Backup commands
    backup_parser = subparsers.add_parser("backup", help="Backup management commands")
    backup_subparsers = backup_parser.add_subparsers(dest="backup_command")
    
    create_backup = backup_subparsers.add_parser("create", help="Create a backup")
    create_backup.add_argument("repository_name", help="Repository name")
    create_backup.add_argument("backup_name", help="Backup name")
    
    restore_backup = backup_subparsers.add_parser("restore", help="Restore a backup")
    restore_backup.add_argument("repository_name", help="Repository name")
    restore_backup.add_argument("backup_name", help="Backup to restore")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)

    logger = setup_logger(args.verbose)
    dotfile_manager = DotfileManager(verbose=args.verbose)
    package_manager = PackageManager(verbose=args.verbose)

    try:
        if args.command == "clone":
            repository_url = sanitize_url(args.repository_url)
            if dotfile_manager.clone_repository(repository_url):
                logger.info(f"Successfully cloned repository: {repository_url}")
            else:
                logger.error(f"Failed to clone repository: {repository_url}")
                sys.exit(1)

        elif args.command in ["apply", "manage"]:
            is_manage = args.command == "manage"
            _handle_manage_apply_command(args, dotfile_manager, package_manager, logger, is_manage)

        elif args.command == "profile":
            if args.profile_command == "list":
                profiles = dotfile_manager.config_manager.get_rice_config(args.repository_name).get("profiles", {})
                active_profile = dotfile_manager.config_manager.get_active_profile(args.repository_name)
                print_profiles(profiles, active_profile)
            
            elif args.profile_command == "create":
                dotfile_manager.config_manager.create_profile(args.repository_name, args.profile_name)
                logger.info(f"Created profile '{args.profile_name}' for repository '{args.repository_name}'")
            
            elif args.profile_command == "switch":
                dotfile_manager.config_manager.switch_profile(args.repository_name, args.profile_name)
                logger.info(f"Switched to profile '{args.profile_name}' for repository '{args.repository_name}'")

        elif args.command == "backup":
            if args.backup_command == "create":
                dotfile_manager.create_backup(args.repository_name, args.backup_name)
                logger.info(f"Created backup '{args.backup_name}' for repository '{args.repository_name}'")
            
            elif args.backup_command == "restore":
                dotfile_manager.restore_backup(args.repository_name, args.backup_name)
                logger.info(f"Restored backup '{args.backup_name}' for repository '{args.repository_name}'")

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

def _handle_nix_rice_installation(args, dotfile_manager, package_manager, logger):
    """Handles the installation of Nix rices."""
    try:
        rice_config = dotfile_manager.analyze_rice_directory(args.repository_name)
        
        # Only proceed with Nix installation if we detect Nix files
        if rice_config.get('is_nix_config', False):
            if not package_manager._check_nix():
                logger.info("Nix configuration detected but Nix is not installed. Skipping Nix-specific setup.")
                return True
            
            logger.info("Installing Nix rice...")
            # Implement logic to install Nix rice here
            # Example: package_manager.install_nix_rice(rice_config)
            return True
        
        return True  # Not a Nix rice, continue normally

    except Exception as e:
        logger.error(f"An error occurred during rice analysis: {e}")
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
        if manage:
            if not dotfile_manager.manage_dotfiles(args.repository_name, stow_options, package_manager, target_packages, custom_paths, args.ignore_rules):
                sys.exit(1)
        else:
            if not dotfile_manager.apply_dotfiles(args.repository_name, stow_options, package_manager, target_packages, custom_paths, args.ignore_rules):
                sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred in command: {args.command}. Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Add the project root to the Python path when running directly
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, project_root)
    
    main()