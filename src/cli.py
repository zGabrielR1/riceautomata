# src/cli.py

import argparse
import sys
import logging
import os
import json
from typing import Dict, Any, Callable, List, Tuple
from colorama import init, Fore, Style
import datetime
import shutil

from .utils import sanitize_url, exception_handler
from .logger import setup_logger  # Updated import
from .package_manager import PackageManager
from .dotfile_manager import DotfileManager
from .config import ConfigManager

init()  # Initialize colorama for colored output

def print_profiles(profiles: Dict[str, Any], active_profile: str) -> None:
    """Pretty print the profiles information."""
    if not profiles:
        print(f"{Fore.YELLOW}No profiles found{Style.RESET_ALL}")
        return

    print(f"\n{Fore.CYAN}Available Profiles:{Style.RESET_ALL}")
    for profile in sorted(profiles.keys()):
        if profile == active_profile:
            print(f" * {profile} {Fore.GREEN}(active){Style.RESET_ALL}")
        else:
            print(f"   {profile}")
    print()

def handle_clone(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'clone' command."""
    repository_url = sanitize_url(args.repository_url)
    success = dotfile_manager.clone_repository(repository_url)
    if success:
        print(f"{Fore.GREEN}✓ Successfully cloned repository: {repository_url}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Failed to clone repository: {repository_url}{Style.RESET_ALL}")
        sys.exit(1)

def handle_apply(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'apply' command."""
    try:
        repository_name = args.repository_name
        # Validate repository_name format (should not be a path)
        if '/' in repository_name or '\\' in repository_name:
            logger.error("Repository name should not be a path. Please provide the repository name only.")
            sys.exit(1)
        
        success = dotfile_manager.apply_dotfiles(
            repository_name=repository_name,
            stow_options=args.stow_options.split() if args.stow_options else [],
            package_manager=package_manager,
            target_packages=args.target_packages.split(',') if args.target_packages else None,
            overwrite_symlink=args.overwrite_symlink,
            custom_paths=dict(path.split(':') for path in args.custom_paths.split(',')) if args.custom_paths else None,
            ignore_rules=args.ignore_rules,
            template_context=json.loads(args.template_context),
            discover_templates=args.discover_templates,
            custom_scripts=args.custom_scripts.split(',') if args.custom_scripts else None
        )
        
        if success:
            print(f"{Fore.GREEN}✓ Successfully applied dotfiles for repository '{repository_name}'.{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}✗ Failed to apply dotfiles for repository '{repository_name}'.{Style.RESET_ALL}")
            sys.exit(1)
    
    except json.JSONDecodeError:
        logger.error("Invalid JSON for template_context.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred during application: {e}")
        sys.exit(1)


def handle_manage(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'manage' command."""
    _handle_manage_apply_command(args, dotfile_manager, package_manager, logger, manage=True)

def handle_preview(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'preview' command."""
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

def handle_diff(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'diff' command."""
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

def handle_search(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'search' command."""
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
                        rel_path = os.path.relpath(
                            os.path.join(root, file),
                            local_dir
                        )
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

def handle_profile_list(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'profile list' command."""
    profiles = dotfile_manager.config_manager.get_rice_config(args.repository_name).get("profiles", {})
    active_profile = dotfile_manager.config_manager.get_active_profile(args.repository_name)
    print_profiles(profiles, active_profile)

def handle_profile_create(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'profile create' command."""
    dotfile_manager.config_manager.create_profile(args.repository_name, args.profile_name)
    logger.info(f"Created profile '{args.profile_name}' for repository '{args.repository_name}'")

def handle_profile_switch(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'profile switch' command."""
    dotfile_manager.config_manager.switch_profile(args.repository_name, args.profile_name)
    logger.info(f"Switched to profile '{args.profile_name}' for repository '{args.repository_name}'")

def handle_backup_create(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'backup create' command."""
    backup_id = dotfile_manager.backup_manager.create_backup(args.repository_name, args.backup_name)
    if backup_id:
        print(f"{Fore.GREEN}✓ Created backup: {args.backup_name} (ID: {backup_id}){Style.RESET_ALL}")

def handle_backup_restore(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'backup restore' command."""
    if dotfile_manager.backup_manager.restore_backup(args.repository_name, args.backup_name):
        print(f"{Fore.GREEN}✓ Restored backup: {args.backup_name}{Style.RESET_ALL}")

def handle_export(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'export' command."""
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
        print(f"{Fore.GREEN}✓ Successfully exported configuration to: {output_file}{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Failed to export configuration: {e}")
        sys.exit(1)

def handle_import(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'import' command."""
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

    print(f"{Fore.GREEN}✓ Successfully imported configuration as: {repo_name}{Style.RESET_ALL}")

def handle_snapshot_create(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'snapshot create' command."""
    if dotfile_manager.create_snapshot(args.name, args.description):
        print(f"{Fore.GREEN}✓ Created snapshot: {args.name}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Failed to create snapshot: {args.name}{Style.RESET_ALL}")

def handle_snapshot_list(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'snapshot list' command."""
    if dotfile_manager.list_snapshots():
        print(f"{Fore.GREEN}✓ Listed snapshots{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Failed to list snapshots{Style.RESET_ALL}")

def handle_snapshot_restore(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'snapshot restore' command."""
    if dotfile_manager.restore_snapshot(args.name):
        print(f"{Fore.GREEN}✓ Restored snapshot: {args.name}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Failed to restore snapshot: {args.name}{Style.RESET_ALL}")

def handle_snapshot_delete(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'snapshot delete' command."""
    if dotfile_manager.delete_snapshot(args.name):
        print(f"{Fore.GREEN}✓ Deleted snapshot: {args.name}{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}✗ Failed to delete snapshot: {args.name}{Style.RESET_ALL}")

def handle_list(args: argparse.Namespace, dotfile_manager: DotfileManager, package_manager: PackageManager, logger: logging.Logger) -> None:
    """Handles the 'list' command."""
    try:
        config_manager = ConfigManager()
        if args.repository_name:
            # List profiles for specific repository
            rice_config = config_manager.get_rice_config(args.repository_name)
            if rice_config and 'profiles' in rice_config:
                active_profile = rice_config.get('active_profile', '')
                profiles = rice_config.get('profiles', {})
                print_profiles(profiles, active_profile)
            else:
                print(f"{Fore.YELLOW}No profiles found for repository '{args.repository_name}'{Style.RESET_ALL}")
        else:
            # List all profiles from all repositories
            config_data = config_manager._load_config()
            if config_data and 'rices' in config_data and config_data['rices']:
                found_repos = False
                for repo_name, repo_config in config_data['rices'].items():
                    if repo_config and 'profiles' in repo_config and repo_config['profiles']:
                        found_repos = True
                        print(f"\n{Fore.CYAN}Repository: {repo_name}{Style.RESET_ALL}")
                        active_profile = repo_config.get('active_profile', '')
                        print_profiles(repo_config.get('profiles', {}), active_profile)
                if not found_repos:
                    print(f"{Fore.YELLOW}No profiles found in any repository{Style.RESET_ALL}")
            else:
                print(f"{Fore.YELLOW}No repositories or profiles found{Style.RESET_ALL}")
    except Exception as e:
        logger.error(f"Error listing profiles: {str(e)}")
        sys.exit(1)

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
            if not dotfile_manager.manage_dotfiles(args.profile_name, args.target_files, args.dry_run):
                sys.exit(1)
        else:
            if not dotfile_manager.apply_dotfiles(args.repository_name, stow_options, package_manager, target_packages, args.overwrite_symlink, custom_paths, args.ignore_rules, args.template_context, args.discover_templates, args.custom_scripts):
                sys.exit(1)
    except Exception as e:
        logger.error(f"An error occurred in command: {args.command}. Error: {e}")
        sys.exit(1)

# Command definitions
COMMANDS = {
    "clone": {
        "help": "Clone a dotfiles repository",
        "arguments": [
            ("repository_url", {"help": "URL of the repository to clone"}),
        ],
        "handler": handle_clone,
    },
    "apply": {
        "help": "Apply dotfiles from a repository",
        "aliases": ["A"],
        "arguments": [
            ("repository_name", {"help": "Name of the repository to apply"}),
            (("-p", "--profile"), {"help": "Profile to use"}),
            (("-t", "--target-packages"), {"help": "Comma-separated list of packages to configure"}),
            ("--auto", {"action": "store_true", "help": "Enable fully automated installation with enhanced detection"}),
            ("--no-backup", {"action": "store_true", "help": "Skip creating backup of existing configuration"}),
            ("--force", {"action": "store_true", "help": "Force installation even if validation fails"}),
            ("--skip-verify", {"action": "store_true", "help": "Skip post-installation verification"}),
            ("--stow-options", {"help": "Space-separated GNU Stow options"}),
            ("--templates", {"action": "store_true", "help": "Process template files"}),
            ("--custom-paths", {"help": "Comma-separated list of custom paths"}),
            ("--ignore-rules", {"action": "store_true", "help": "Ignore discovery rules"}),
            (("--overwrite-symlink",), {"help": "Overwrite existing symlinks", "action": "store_true"}),
            ("--template-context", {"help": "JSON string containing template context variables", "default": "{}"}),
            ("--discover-templates", {"action": "store_true", "help": "Automatically discover and process template files", "default": False}),
            ("--custom-scripts", {"help": "Comma-separated list of custom scripts to run"}),
        ],
        "handler": handle_apply,
    },
    "manage": {
        "help": "Manage specific dotfiles",
        "aliases": ["m"],  # ✅ Changed to a non-hyphenated alias
        "arguments": [
            ("repository_name", {"help": "Name of the repository to manage"}),
            ("--target-files", {"help": "Comma-separated list of files to manage"}),
            ("--dry-run", {"action": "store_true", "help": "Preview changes without applying them"}),
            ("--stow-options", {"help": "Space-separated GNU Stow options"}),
        ],
        "handler": handle_manage,
    },
    "preview": {
        "help": "Preview changes before applying",
        "arguments": [
            ("repository_name", {"help": "Name of the repository"}),
            (("-p", "--profile"), {"help": "Profile to preview"}),
            ("--target-packages", {"help": "Comma-separated list of packages to preview"}),
        ],
        "handler": handle_preview,
    },
    "diff": {
        "help": "Show differences between current and new configurations",
        "arguments": [
            ("repository_name", {"help": "Name of the repository"}),
            (("-p", "--profile"), {"help": "Profile to compare"}),
            ("--target-packages", {"help": "Comma-separated list of packages to compare"}),
        ],
        "handler": handle_diff,
    },
    "search": {
        "help": "Search for configurations or settings",
        "arguments": [
            ("query", {"help": "Search query"}),
            (("-r", "--repository"), {"help": "Limit search to specific repository"}),
            ("--content", {"action": "store_true", "help": "Search in file contents"}),
        ],
        "handler": handle_search,
    },
    "profile": {
        "help": "Profile management commands",
        "subcommands": {
            "list": {
                "help": "List available profiles",
                "arguments": [
                    ("repository_name", {"help": "Repository name"}),
                ],
                "handler": handle_profile_list,
            },
            "create": {
                "help": "Create a new profile",
                "arguments": [
                    ("repository_name", {"help": "Repository name"}),
                    ("profile_name", {"help": "Profile name"}),
                    ("--description", {"help": "Optional description of the profile"}),
                ],
                "handler": handle_profile_create,
            },
            "switch": {
                "help": "Switch to a profile",
                "arguments": [
                    ("repository_name", {"help": "Repository name"}),
                    ("profile_name", {"help": "Profile to switch to"}),
                ],
                "handler": handle_profile_switch,
            },
        },
    },
    "backup": {
        "help": "Backup management commands",
        "subcommands": {
            "create": {
                "help": "Create a backup",
                "arguments": [
                    ("repository_name", {"help": "Repository name"}),
                    ("backup_name", {"help": "Backup name"}),
                ],
                "handler": handle_backup_create,
            },
            "restore": {
                "help": "Restore a backup",
                "arguments": [
                    ("repository_name", {"help": "Repository name"}),
                    ("backup_name", {"help": "Backup to restore"}),
                ],
                "handler": handle_backup_restore,
            },
        },
    },
    "export": {
        "help": "Export configuration to a portable format",
        "arguments": [
            ("repository_name", {"help": "Name of the repository to export"}),
            (("-o", "--output"), {"help": "Output file path (default: rice-export.json)"}),
            ("--include-deps", {"action": "store_true", "help": "Include dependency information"}),
            ("--include-assets", {"action": "store_true", "help": "Include asset information"}),
        ],
        "handler": handle_export,
    },
    "import": {
        "help": "Import configuration from a file",
        "arguments": [
            ("file", {"help": "Path to the exported configuration file"}),
            (("-n", "--name"), {"help": "Name for the imported configuration"}),
            ("--skip-deps", {"action": "store_true", "help": "Skip dependency installation"}),
            ("--skip-assets", {"action": "store_true", "help": "Skip asset installation"}),
        ],
        "handler": handle_import,
    },
    "snapshot": {
        "help": "Manage system snapshots",
        "subcommands": {
            "create": {
                "help": "Create a new snapshot",
                "arguments": [
                    ("name", {"help": "Name of the snapshot"}),
                    (("-d", "--description"), {"help": "Description of the snapshot"}),
                ],
                "handler": handle_snapshot_create,
            },
            "list": {
                "help": "List all snapshots",
                "arguments": [],
                "handler": handle_snapshot_list,
            },
            "restore": {
                "help": "Restore a snapshot",
                "arguments": [
                    ("name", {"help": "Name of the snapshot to restore"}),
                ],
                "handler": handle_snapshot_restore,
            },
            "delete": {
                "help": "Delete a snapshot",
                "arguments": [
                    ("name", {"help": "Name of the snapshot to delete"}),
                ],
                "handler": handle_snapshot_delete,
            },
        },
    },
    "list": {
        "help": "List all available profiles",
        "aliases": ["ls", "list-profiles"],  # ✅ Correct: Aliases do not start with hyphen
        "arguments": [
            ("repository_name", {"nargs": '?', "help": "Optional: Name of the repository to list profiles from"}),
        ],
        "handler": handle_list,
    },
}

def setup_subparser(subparsers: argparse._SubParsersAction, command_name: str, command_data: Dict[str, Any]) -> None:
    """Sets up a subparser for a command."""
    subparser = subparsers.add_parser(
        command_name, 
        aliases=command_data.get("aliases", []), 
        help=command_data["help"]
    )
    arguments = command_data.get("arguments", [])
    if arguments:
        for item in arguments:
            if isinstance(item, tuple) and len(item) == 2:
                arg_name, arg_params = item
                # Only validate option strings that are meant to be optional arguments
                if isinstance(arg_name, tuple):
                    for opt in arg_name:
                        if not opt.startswith('-'):
                            raise ValueError(f"Invalid option string '{opt}': optional arguments must start with '-'")
                    subparser.add_argument(*arg_name, **arg_params)
                else:
                    # For single arguments, only validate if it starts with '-'
                    if arg_name.startswith('-'):
                        if not arg_name.startswith('-'):
                            raise ValueError(f"Invalid option string '{arg_name}': optional arguments must start with '-'")
                    subparser.add_argument(arg_name, **arg_params)
            else:
                print(f"Warning: Invalid argument format for command '{command_name}': {item}. Expected a tuple of (name, params).")

    # Recursively set up subparsers for subcommands
    if "subcommands" in command_data:
        subsubparsers = subparser.add_subparsers(dest=f"{command_name}_command")
        for sub_name, sub_data in command_data["subcommands"].items():
            setup_subparser(subsubparsers, sub_name, sub_data)
            
    subparser.set_defaults(handler=lambda args, dotfile_manager, package_manager, logger: command_data["handler"](args, dotfile_manager, package_manager, logger) if "handler" in command_data else None)

def main():
    """Main entry point for the CLI."""
    sys.excepthook = exception_handler
    parser = argparse.ArgumentParser(
        description="RiceAutomata - A powerful dotfile and system configuration manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  riceautomata clone https://github.com/user/dotfiles
  riceautomata apply my-dotfiles
  riceautomata A my-dotfiles --profile minimal
  riceautomata manage my-dotfiles --target-packages i3,polybar
  riceautomata list-profiles my-dotfiles
""")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")
    subparsers = parser.add_subparsers(title="Commands", dest="command", help="Available commands")

    # Set up subparsers for each command
    for command_name, command_data in COMMANDS.items():
        setup_subparser(subparsers, command_name, command_data)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    logger = setup_logger(args.verbose)
    dotfile_manager = DotfileManager(verbose=args.verbose)
    package_manager = PackageManager()  # Removed verbose parameter

    try:
        # Handle top-level commands and subcommands
        if args.command == "profile" and hasattr(args, "profile_command"):
            command_data = COMMANDS[args.command]["subcommands"][args.profile_command]
        elif args.command == "backup" and hasattr(args, "backup_command"):
            command_data = COMMANDS[args.command]["subcommands"][args.backup_command]
        elif args.command == "snapshot" and hasattr(args, "snapshot_command"):
            command_data = COMMANDS[args.command]["subcommands"][args.snapshot_command]
        else:
            command_data = COMMANDS[args.command]

        if "handler" in command_data:
            command_data["handler"](args, dotfile_manager, package_manager, logger)
        else:
            logger.error(f"No handler defined for command: {args.command}")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Add the project root to the Python path when running directly
    import os
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, project_root)
    
    main()
