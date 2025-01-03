# dotfilemanager/main.py

import argparse
import sys
from pathlib import Path
from typing import Optional, Dict, Any
import json

from .dotfile_manager import DotfileManager

def main():
    parser = argparse.ArgumentParser(description="DotfileManager: Manage and apply your dotfiles configurations.")
    parser.add_argument('--verbose', '-v', action='store_true', help="Enable verbose logging (DEBUG level).")
    parser.add_argument('--log-file', type=str, help="Path to the log file.")

    subparsers = parser.add_subparsers(dest='command', required=True)

    # Clone command
    clone_parser = subparsers.add_parser('clone', help='Clone a dotfile repository.')
    clone_parser.add_argument('repository_url', type=str, help='URL of the git repository to clone.')

    # Apply command
    apply_parser = subparsers.add_parser('apply', help='Apply dotfiles from a repository.')
    apply_parser.add_argument('repository_name', type=str, help='Name of the repository to apply.')
    apply_parser.add_argument('--profile', type=str, help='Name of the profile to apply.')
    apply_parser.add_argument('--stow-options', nargs='*', default=[], help='Additional options for GNU Stow.')
    apply_parser.add_argument('--overwrite-symlink', type=str, help='Path to overwrite existing symlinks.')
    apply_parser.add_argument('--custom-paths', nargs='*', help='Custom paths in the format key=value.')
    apply_parser.add_argument('--ignore-rules', action='store_true', help='Ignore rules during application.')
    apply_parser.add_argument('--template-context', type=str, help='Path to JSON file with template context.')
    apply_parser.add_argument('--discover-templates', action='store_true', help='Discover and process templates.')
    apply_parser.add_argument('--custom-scripts', nargs='*', help='Additional scripts to run.')

    # List command
    list_parser = subparsers.add_parser('list', help='List all profiles or profiles for a specific repository.')
    list_parser.add_argument('repository_name', nargs='?', type=str, help='Name of the repository to list profiles for.')

    # Create profile command
    create_parser = subparsers.add_parser('create', help='Create a new profile.')
    create_parser.add_argument('profile_name', type=str, help='Name of the new profile.')
    create_parser.add_argument('--description', type=str, help='Description of the profile.', default='')

    # Backup command
    backup_parser = subparsers.add_parser('backup', help='Create a backup of the applied configuration.')
    backup_parser.add_argument('repository_name', type=str, help='Name of the repository to backup.')
    backup_parser.add_argument('backup_name', type=str, help='Name for the backup.')

    # Restore backup command
    restore_parser = subparsers.add_parser('restore', help='Restore a backup of the configuration.')
    restore_parser.add_argument('repository_name', type=str, help='Name of the repository to restore.')
    restore_parser.add_argument('backup_name', type=str, help='Name of the backup to restore.')

    # Manage command
    manage_parser = subparsers.add_parser('manage', help='Manage specific dotfiles.')
    manage_parser.add_argument('profile_name', type=str, help='Name of the profile to manage.')
    manage_parser.add_argument('--target-files', type=str, help='Comma-separated list of dotfiles to manage.')
    manage_parser.add_argument('--dry-run', action='store_true', help='Preview changes without applying them.')

    # Export command
    export_parser = subparsers.add_parser('export', help='Export a repository configuration.')
    export_parser.add_argument('repository_name', type=str, help='Name of the repository to export.')
    export_parser.add_argument('-o', '--output', type=str, default='export.json', help='Output JSON file.')
    export_parser.add_argument('--include-deps', action='store_true', help='Include dependencies in the export.')
    export_parser.add_argument('--include-assets', action='store_true', help='Include assets in the export.')

    # Import command
    import_parser = subparsers.add_parser('import', help='Import a repository configuration.')
    import_parser.add_argument('file', type=str, help='Path to the JSON file to import.')
    import_parser.add_argument('-n', '--new-name', type=str, help='New name for the imported repository.')
    import_parser.add_argument('--skip-deps', action='store_true', help='Skip installing dependencies.')
    import_parser.add_argument('--skip-assets', action='store_true', help='Skip importing assets.')

    # Snapshot commands
    snapshot_parser = subparsers.add_parser('snapshot', help='Manage system snapshots.')
    snapshot_subparsers = snapshot_parser.add_subparsers(dest='snapshot_command', required=True)

    # Snapshot create
    snapshot_create_parser = snapshot_subparsers.add_parser('create', help='Create a snapshot.')
    snapshot_create_parser.add_argument('name', type=str, help='Name of the snapshot.')
    snapshot_create_parser.add_argument('-d', '--description', type=str, help='Description of the snapshot.', default='')

    # Snapshot list
    snapshot_list_parser = snapshot_subparsers.add_parser('list', help='List all snapshots.')

    # Snapshot restore
    snapshot_restore_parser = snapshot_subparsers.add_parser('restore', help='Restore from a snapshot.')
    snapshot_restore_parser.add_argument('name', type=str, help='Name of the snapshot to restore.')

    # Snapshot delete
    snapshot_delete_parser = snapshot_subparsers.add_parser('delete', help='Delete a snapshot.')
    snapshot_delete_parser.add_argument('name', type=str, help='Name of the snapshot to delete.')

    args = parser.parse_args()

    # Initialize DotfileManager
    manager = DotfileManager(verbose=args.verbose, log_file=args.log_file)

    if args.command == 'clone':
        success = manager.clone_repository(args.repository_url)

    elif args.command == 'apply':
        custom_paths = {}
        if args.custom_paths:
            for cp in args.custom_paths:
                if '=' in cp:
                    key, value = cp.split('=', 1)
                    custom_paths[key] = value
        template_context = {}
        if args.template_context:
            try:
                with open(args.template_context, 'r', encoding='utf-8') as f:
                    template_context = json.load(f)
            except Exception as e:
                manager.logger.error(f"Failed to load template context: {e}")
        custom_scripts = args.custom_scripts if args.custom_scripts else []
        profile = args.profile if args.profile else 'default'
        success = manager.apply_dotfiles(
            repository_name=args.repository_name,
            profile_name=profile,
            stow_options=args.stow_options,
            overwrite_symlink=args.overwrite_symlink,
            custom_paths=custom_paths,
            ignore_rules=args.ignore_rules,
            template_context=template_context,
            discover_templates=args.discover_templates,
            custom_scripts=custom_scripts
        )

    elif args.command == 'list':
        repository = args.repository_name if args.repository_name else None
        success = manager.list_profiles(repository)

    elif args.command == 'create':
        success = manager.create_profile(args.profile_name, args.description)

    elif args.command == 'backup':
        success = manager.create_backup(args.repository_name, args.backup_name)

    elif args.command == 'restore':
        success = manager.restore_backup(args.repository_name, args.backup_name)

    elif args.command == 'manage':
        target_files = args.target_files.split(',') if args.target_files else []
        success = manager.manage_dotfiles(
            profile_name=args.profile_name,
            target_files=target_files,
            dry_run=args.dry_run
        )

    elif args.command == 'export':
        success = manager.export_configuration(
            repository_name=args.repository_name,
            output_file=args.output,
            include_deps=args.include_deps,
            include_assets=args.include_assets
        )

    elif args.command == 'import':
        success = manager.import_configuration(
            file_path=args.file,
            new_name=args.new_name,
            skip_deps=args.skip_deps,
            skip_assets=args.skip_assets
        )

    elif args.command == 'snapshot':
        if args.snapshot_command == 'create':
            success = manager.create_snapshot(args.name, args.description)
        elif args.snapshot_command == 'list':
            success = manager.list_snapshots()
        elif args.snapshot_command == 'restore':
            success = manager.restore_snapshot(args.name)
        elif args.snapshot_command == 'delete':
            success = manager.delete_snapshot(args.name)
        else:
            manager.logger.error(f"Unknown snapshot command: {args.snapshot_command}")
            success = False

    else:
        manager.logger.error(f"Unknown command: {args.command}")
        success = False

    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()