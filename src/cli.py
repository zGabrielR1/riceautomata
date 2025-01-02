# src/cli.py
import argparse
import sys
from .utils import setup_logger, sanitize_url, exception_handler
from .package import PackageManager
from .dotfile import DotfileManager
import logging
import os
import json
from typing import Dict, Any
from colorama import init, Fore, Style
import datetime
import shutil

init()  # Initialize colorama for colored output

def print_profiles(profiles: Dict[str, Any], active_profile: str) -> None:
    """Pretty print the profiles information."""
    print(f"\n{Fore.CYAN}Available Profiles:{Style.RESET_ALL}")
    for profile in sorted(profiles.keys()):
        if profile == active_profile:
            print(f" * {profile} {Fore.GREEN}(active){Style.RESET_ALL}")
        else:
            print(f"   {profile}")
    print()

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
    apply_parser.add_argument("--auto", action="store_true", help="Enable fully automated installation with enhanced detection")
    apply_parser.add_argument("--no-backup", action="store_true", help="Skip creating backup of existing configuration")
    apply_parser.add_argument("--force", action="store_true", help="Force installation even if validation fails")
    apply_parser.add_argument("--skip-verify", action="store_true", help="Skip post-installation verification")
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

    # Preview command
    preview_parser = subparsers.add_parser("preview", help="Preview changes before applying")
    preview_parser.add_argument("repository_name", help="Name of the repository")
    preview_parser.add_argument("-p", "--profile", help="Profile to preview")
    preview_parser.add_argument("--target-packages", help="Comma-separated list of packages to preview")

    # Diff command
    diff_parser = subparsers.add_parser("diff", help="Show differences between current and new configurations")
    diff_parser.add_argument("repository_name", help="Name of the repository")
    diff_parser.add_argument("-p", "--profile", help="Profile to compare")
    diff_parser.add_argument("--target-packages", help="Comma-separated list of packages to compare")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for configurations or settings")
    search_parser.add_argument("query", help="Search query")
    search_parser.add_argument("-r", "--repository", help="Limit search to specific repository")
    search_parser.add_argument("--content", action="store_true", help="Search in file contents")

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

    # Export command
    export_parser = subparsers.add_parser("export", help="Export configuration to a portable format")
    export_parser.add_argument("repository_name", help="Name of the repository to export")
    export_parser.add_argument("-o", "--output", help="Output file path (default: rice-export.json)")
    export_parser.add_argument("--include-deps", action="store_true", help="Include dependency information")
    export_parser.add_argument("--include-assets", action="store_true", help="Include asset information")

    # Import command
    import_parser = subparsers.add_parser("import", help="Import configuration from a file")
    import_parser.add_argument("file", help="Path to the exported configuration file")
    import_parser.add_argument("-n", "--name", help="Name for the imported configuration")
    import_parser.add_argument("--skip-deps", action="store_true", help="Skip dependency installation")
    import_parser.add_argument("--skip-assets", action="store_true", help="Skip asset installation")

    # Snapshot commands
    snapshot_parser = subparsers.add_parser('snapshot', help='Manage system snapshots')
    snapshot_subparsers = snapshot_parser.add_subparsers(dest='snapshot_command', help='Snapshot commands')

    # Create snapshot
    create_parser = snapshot_subparsers.add_parser('create', help='Create a new snapshot')
    create_parser.add_argument('name', help='Name of the snapshot')
    create_parser.add_argument('-d', '--description', help='Description of the snapshot')

    # Restore snapshot
    restore_parser = snapshot_subparsers.add_parser('restore', help='Restore a snapshot')
    restore_parser.add_argument('name', help='Name of the snapshot to restore')

    # List snapshots
    snapshot_subparsers.add_parser('list', help='List all snapshots')

    # Delete snapshot
    delete_parser = snapshot_subparsers.add_parser('delete', help='Delete a snapshot')
    delete_parser.add_argument('name', help='Name of the snapshot to delete')

    # List command
    list_parser = subparsers.add_parser("list", aliases=["ls"],
        help="List all available profiles")
    list_parser.add_argument("repository_name", nargs='?', help="Optional: Name of the repository to list profiles from")

    # List-profiles command (alias for list)
    list_profiles_parser = subparsers.add_parser("list-profiles", 
        help="List all available profiles")
    list_profiles_parser.add_argument("repository_name", nargs='?', help="Optional: Name of the repository to list profiles from")

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

        elif args.command in ["apply", "-A"]:
            try:
                if args.auto:
                    logger.info(f"Starting automated installation for repository: {args.repository_name}")
                    config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
                    if not config:
                        logger.error(f"No configuration found for repository: {args.repository_name}")
                        sys.exit(1)
                    
                    local_dir = config.get('local_directory')
                    if not local_dir:
                        logger.error("Local directory not found in configuration")
                        sys.exit(1)
                    
                    # Apply automated installation with options
                    success = dotfile_manager.apply_rice_automated(
                        local_dir,
                        skip_backup=args.no_backup,
                        force=args.force,
                        skip_verify=args.skip_verify
                    )
                    
                    if not success:
                        logger.error("Automated installation failed")
                        sys.exit(1)
                        
                    logger.info("Automated installation completed successfully")
                    
                else:
                    # Original manual installation logic
                    _handle_manage_apply_command(args, dotfile_manager, package_manager, logger, manage=False)
                    
            except Exception as e:
                logger.error(f"An error occurred during installation: {e}")
                sys.exit(1)

        elif args.command == "manage":
            is_manage = args.command == "manage"
            _handle_manage_apply_command(args, dotfile_manager, package_manager, logger, is_manage)

        elif args.command == "preview":
            logger.info(f"Previewing changes for repository: {args.repository_name}")
            
            # Get target packages
            target_packages = args.target_packages.split(',') if args.target_packages else None
            
            # Get profile configuration
            profile = args.profile or 'default'
            config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
            if not config:
                logger.error(f"No configuration found for repository: {args.repository_name}")
                sys.exit(1)
                
            profile_config = config.get('profiles', {}).get(profile, {})
            
            # Preview packages
            if 'packages' in profile_config:
                packages = profile_config['packages']
                installed = [pkg for pkg in packages if dotfile_manager._check_installed_packages([pkg])]
                to_install = [pkg for pkg in packages if pkg not in installed]
                
                print(f"\n{Fore.CYAN}Package Changes:{Style.RESET_ALL}")
                if to_install:
                    print(f"{Fore.GREEN}Packages to be installed:{Style.RESET_ALL}")
                    for pkg in to_install:
                        print(f"  + {pkg}")
                if installed:
                    print(f"{Fore.BLUE}Already installed packages:{Style.RESET_ALL}")
                    for pkg in installed:
                        print(f"  = {pkg}")
            
            # Preview dotfile changes
            print(f"\n{Fore.CYAN}Dotfile Changes:{Style.RESET_ALL}")
            dotfile_dirs = dotfile_manager._discover_dotfile_directories(
                config.get('local_directory', ''),
                target_packages=target_packages
            )
            
            for directory in dotfile_dirs:
                print(f"\n{Fore.YELLOW}Directory: {directory}{Style.RESET_ALL}")
                target_dir = os.path.expanduser('~')
                for root, _, files in os.walk(directory):
                    for file in files:
                        src_path = os.path.join(root, file)
                        rel_path = os.path.relpath(src_path, directory)
                        dst_path = os.path.join(target_dir, rel_path)
                        
                        if os.path.exists(dst_path):
                            if os.path.islink(dst_path):
                                print(f"  ~ {rel_path} (will update symlink)")
                            else:
                                print(f"  ! {rel_path} (will backup and replace)")
                        else:
                            print(f"  + {rel_path} (will create)")

        elif args.command == "diff":
            from difflib import unified_diff
            import tempfile
            
            logger.info(f"Showing differences for repository: {args.repository_name}")
            
            # Get target packages
            target_packages = args.target_packages.split(',') if args.target_packages else None
            
            # Get profile configuration
            profile = args.profile or 'default'
            config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
            if not config:
                logger.error(f"No configuration found for repository: {args.repository_name}")
                sys.exit(1)
            
            dotfile_dirs = dotfile_manager._discover_dotfile_directories(
                config.get('local_directory', ''),
                target_packages=target_packages
            )
            
            print(f"\n{Fore.CYAN}Configuration Differences:{Style.RESET_ALL}")
            
            for directory in dotfile_dirs:
                for root, _, files in os.walk(directory):
                    for file in files:
                        src_path = os.path.join(root, file)
                        rel_path = os.path.relpath(src_path, directory)
                        dst_path = os.path.join(os.path.expanduser('~'), rel_path)
                        
                        if os.path.exists(dst_path) and os.path.isfile(dst_path):
                            try:
                                with open(src_path, 'r') as f1, open(dst_path, 'r') as f2:
                                    src_lines = f1.readlines()
                                    dst_lines = f2.readlines()
                                    
                                    diff = list(unified_diff(
                                        dst_lines, src_lines,
                                        fromfile=f"current/{rel_path}",
                                        tofile=f"new/{rel_path}"
                                    ))
                                    
                                    if diff:
                                        print(f"\n{Fore.YELLOW}File: {rel_path}{Style.RESET_ALL}")
                                        for line in diff:
                                            if line.startswith('+'):
                                                print(f"{Fore.GREEN}{line.rstrip()}{Style.RESET_ALL}")
                                            elif line.startswith('-'):
                                                print(f"{Fore.RED}{line.rstrip()}{Style.RESET_ALL}")
                                            else:
                                                print(line.rstrip())
                            except UnicodeDecodeError:
                                print(f"\n{Fore.YELLOW}File: {rel_path} (binary file){Style.RESET_ALL}")
                        elif not os.path.exists(dst_path):
                            print(f"\n{Fore.GREEN}New file: {rel_path}{Style.RESET_ALL}")

        elif args.command == "search":
            import fnmatch
            
            def search_content(file_path, query):
                try:
                    with open(file_path, 'r') as f:
                        for i, line in enumerate(f, 1):
                            if query.lower() in line.lower():
                                return i, line.strip()
                    return None
                except UnicodeDecodeError:
                    return None
            
            logger.info(f"Searching for: {args.query}")
            
            # Get repositories to search
            if args.repository:
                repositories = [args.repository]
            else:
                repositories = dotfile_manager.config_manager.list_rices()
            
            found_something = False
            for repo in repositories:
                config = dotfile_manager.config_manager.get_rice_config(repo)
                if not config:
                    continue
                
                local_dir = config.get('local_directory', '')
                if not local_dir or not os.path.exists(local_dir):
                    continue
                
                print(f"\n{Fore.CYAN}Searching in repository: {repo}{Style.RESET_ALL}")
                
                # Search in dotfile directories
                dotfile_dirs = dotfile_manager._discover_dotfile_directories(local_dir)
                
                for directory in dotfile_dirs:
                    for root, _, files in os.walk(directory):
                        for file in files:
                            if fnmatch.fnmatch(file.lower(), f"*{args.query.lower()}*"):
                                rel_path = os.path.relpath(os.path.join(root, file), local_dir)
                                print(f"{Fore.GREEN}Found in filename:{Style.RESET_ALL} {rel_path}")
                                found_something = True
                            
                            if args.content:
                                file_path = os.path.join(root, file)
                                result = search_content(file_path, args.query)
                                if result:
                                    line_num, line = result
                                    rel_path = os.path.relpath(file_path, local_dir)
                                    print(f"{Fore.YELLOW}Found in content:{Style.RESET_ALL} {rel_path}:{line_num}")
                                    print(f"  {line}")
                                    found_something = True
            
            if not found_something:
                print(f"\n{Fore.YELLOW}No matches found for: {args.query}{Style.RESET_ALL}")

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

        elif args.command == "export":
            logger.info(f"Exporting configuration for repository: {args.repository_name}")
            
            config = dotfile_manager.config_manager.get_rice_config(args.repository_name)
            if not config:
                logger.error(f"No configuration found for repository: {args.repository_name}")
                sys.exit(1)
            
            # Create export data structure
            export_data = {
                "name": args.repository_name,
                "timestamp": datetime.datetime.now().isoformat(),
                "config": config,
                "profiles": {},
                "dependencies": {},
                "assets": {}
            }
            
            # Export profiles
            profiles = config.get("profiles", {})
            for profile_name, profile_data in profiles.items():
                export_data["profiles"][profile_name] = profile_data
            
            # Export dependencies if requested
            if args.include_deps:
                dotfile_dirs = dotfile_manager._discover_dotfile_directories(
                    config.get("local_directory", "")
                )
                dependencies = dotfile_manager._discover_dependencies(
                    config.get("local_directory", ""),
                    dotfile_dirs
                )
                export_data["dependencies"] = dependencies
            
            # Export assets if requested
            if args.include_assets:
                assets = {}
                asset_dirs = ["wallpapers", "icons", "fonts", "themes"]
                for asset_dir in asset_dirs:
                    dir_path = os.path.join(config.get("local_directory", ""), asset_dir)
                    if os.path.exists(dir_path):
                        assets[asset_dir] = []
                        for root, _, files in os.walk(dir_path):
                            for file in files:
                                rel_path = os.path.relpath(
                                    os.path.join(root, file),
                                    dir_path
                                )
                                assets[asset_dir].append(rel_path)
                export_data["assets"] = assets
            
            # Save export data
            output_file = args.output or "rice-export.json"
            try:
                with open(output_file, "w") as f:
                    json.dump(export_data, f, indent=2)
                logger.info(f"Successfully exported configuration to: {output_file}")
            except Exception as e:
                logger.error(f"Failed to export configuration: {e}")
                sys.exit(1)

        elif args.command == "import":
            logger.info(f"Importing configuration from: {args.file}")
            
            try:
                with open(args.file, "r") as f:
                    import_data = json.load(f)
            except Exception as e:
                logger.error(f"Failed to read import file: {e}")
                sys.exit(1)
            
            # Validate import data
            required_keys = ["name", "config"]
            if not all(key in import_data for key in required_keys):
                logger.error("Invalid import file format")
                sys.exit(1)
            
            # Use provided name or original name
            repo_name = args.name or import_data["name"]
            
            # Create configuration
            config = import_data["config"]
            dotfile_manager.config_manager.add_rice_config(repo_name, config)
            
            # Import profiles
            if "profiles" in import_data:
                for profile_name, profile_data in import_data["profiles"].items():
                    dotfile_manager.config_manager.create_profile(repo_name, profile_name)
                    dotfile_manager.config_manager.update_profile(repo_name, profile_name, profile_data)
            
            # Install dependencies if included and not skipped
            if "dependencies" in import_data and not args.skip_deps:
                dependencies = import_data["dependencies"]
                if dependencies:
                    logger.info("Installing dependencies...")
                    dotfile_manager._install_packages(dependencies)
            
            # Process assets if included and not skipped
            if "assets" in import_data and not args.skip_assets:
                assets = import_data["assets"]
                if assets:
                    logger.info("Processing assets...")
                    for asset_type, asset_files in assets.items():
                        target_dir = os.path.expanduser(f"~/.local/share/{asset_type}")
                        os.makedirs(target_dir, exist_ok=True)
                        for asset_file in asset_files:
                            src = os.path.join(config.get("local_directory", ""), asset_type, asset_file)
                            dst = os.path.join(target_dir, os.path.basename(asset_file))
                            if os.path.exists(src):
                                shutil.copy2(src, dst)
            
            logger.info(f"Successfully imported configuration as: {repo_name}")

        elif args.command == "snapshot":
            backup_manager = BackupManager()
            
            if args.snapshot_command == 'create':
                if backup_manager.create_snapshot(args.name, args.description):
                    print(f"{Fore.GREEN}✓ Snapshot '{args.name}' created successfully!{Style.RESET_ALL}")
                else:
                    print(f"{Fore.RED}✗ Failed to create snapshot '{args.name}'{Style.RESET_ALL}")
        
            elif args.snapshot_command == 'restore':
                if input(f"{Fore.YELLOW}⚠ Are you sure you want to restore snapshot '{args.name}'? This will overwrite your current configuration. (y/N): {Style.RESET_ALL}").lower() == 'y':
                    if backup_manager.restore_snapshot(args.name):
                        print(f"{Fore.GREEN}✓ Successfully restored snapshot '{args.name}'!{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ Failed to restore snapshot '{args.name}'{Style.RESET_ALL}")
        
            elif args.snapshot_command == 'list':
                snapshots = backup_manager.list_snapshots()
                if not snapshots:
                    print(f"{Fore.YELLOW}No snapshots found.{Style.RESET_ALL}")
                else:
                    print(f"\n{Fore.CYAN}📸 Available Snapshots:{Style.RESET_ALL}\n")
                    for name, info in snapshots.items():
                        print(f"{Fore.GREEN}• {name}{Style.RESET_ALL}")
                        print(f"  Created: {info['created_at']}")
                        if info.get('description'):
                            print(f"  Description: {info['description']}")
                        print(f"  Packages: {len(info['packages'])}")
                        print()
        
            elif args.snapshot_command == 'delete':
                if input(f"{Fore.YELLOW}⚠ Are you sure you want to delete snapshot '{args.name}'? (y/N): {Style.RESET_ALL}").lower() == 'y':
                    if backup_manager.delete_snapshot(args.name):
                        print(f"{Fore.GREEN}✓ Successfully deleted snapshot '{args.name}'!{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}✗ Failed to delete snapshot '{args.name}'{Style.RESET_ALL}")

        elif args.command in ["list", "list-profiles", "ls"]:
            try:
                config_manager = ConfigManager()
                if args.repository_name:
                    # List profiles for specific repository
                    rice_config = config_manager.get_rice_config(args.repository_name)
                    if rice_config and 'profiles' in rice_config:
                        active_profile = rice_config.get('active_profile', '')
                        print_profiles(rice_config['profiles'], active_profile)
                    else:
                        print(f"No profiles found for repository '{args.repository_name}'")
                else:
                    # List all profiles from all repositories
                    config_data = config_manager._load_config()
                    if 'rices' in config_data:
                        for repo_name, repo_config in config_data['rices'].items():
                            if 'profiles' in repo_config:
                                print(f"\n{Fore.CYAN}Repository: {repo_name}{Style.RESET_ALL}")
                                active_profile = repo_config.get('active_profile', '')
                                print_profiles(repo_config['profiles'], active_profile)
                    else:
                        print("No profiles found")
            except Exception as e:
                logger.error(f"Error listing profiles: {str(e)}")
                sys.exit(1)

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