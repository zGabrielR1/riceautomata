# RiceAutomata

A powerful command-line tool for managing dotfiles and system configurations on Linux/Unix systems, with enhanced automated installation capabilities.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/riceautomata.git
cd riceautomata

# Install dependencies
pip install -r requirements.txt

# Make the command available system-wide
pip install -e .
```

## Usage

RiceAutomata provides a simple command-line interface for managing your dotfiles:

```bash
# Clone a dotfiles repository
riceautomata clone https://github.com/user/dotfiles

# Apply dotfiles with automated installation (recommended)
riceautomata apply my-dotfiles --auto

# Apply dotfiles with specific options
riceautomata apply my-dotfiles --auto --no-backup --force

# Apply dotfiles manually with a specific profile
riceautomata apply my-dotfiles -p minimal

# Manage dotfiles (uninstall previous, apply new)
riceautomata manage my-dotfiles --target-packages i3,polybar

# List available profiles
riceautomata profile list my-dotfiles

# Create a new profile
riceautomata profile create my-dotfiles work

# Switch to a different profile
riceautomata profile switch my-dotfiles work

# Create a backup
riceautomata backup create my-dotfiles backup-name

# Restore from backup
riceautomata backup restore my-dotfiles backup-name

# Preview changes before applying
riceautomata preview my-dotfiles -p minimal

# Show differences between current and new configurations
riceautomata diff my-dotfiles -p minimal

# Search for configurations
riceautomata search "polybar" --content  # Search in file contents
riceautomata search "i3" -r my-dotfiles  # Search in specific repository

# Export configuration
riceautomata export my-dotfiles --include-deps --include-assets

# Import configuration
riceautomata import rice-export.json --name new-rice
```

### Command Options

#### Global Options
- `-v, --verbose`: Enable verbose output

#### Apply/Manage Options
- `-p, --profile`: Specify profile to use
- `-t, --target-packages`: Comma-separated list of packages to configure
- `--auto`: Enable fully automated installation with enhanced detection
- `--no-backup`: Skip creating backup of existing configuration
- `--force`: Force installation even if validation fails
- `--skip-verify`: Skip post-installation verification
- `--stow-options`: Space-separated GNU Stow options
- `--templates`: Process template files
- `--custom-paths`: Comma-separated list of custom paths
- `--ignore-rules`: Ignore discovery rules

#### Preview Options
- `-p, --profile`: Profile to preview
- `--target-packages`: Comma-separated list of packages to preview

#### Diff Options
- `-p, --profile`: Profile to compare
- `--target-packages`: Comma-separated list of packages to compare

#### Search Options
- `-r, --repository`: Limit search to specific repository
- `--content`: Search in file contents

#### Export Options
- `-o, --output`: Output file path
- `--include-deps`: Include dependency information
- `--include-assets`: Include asset information

#### Import Options
- `-n, --name`: Name for the imported configuration
- `--skip-deps`: Skip dependency installation
- `--skip-assets`: Skip asset installation

## Features

### Core Features
- **Command-Line Interface**: Simple and intuitive CLI for all operations
- **Profile Management**: Create and switch between different configuration profiles
- **Package Management**: 
  - Automatic package installation with parallel processing
  - Support for multiple package managers
  - Nix integration
- **Backup System**: Create and restore configuration backups
- **Enhanced Error Handling**: Robust error handling with detailed logging
- **Progress Tracking**: Visual progress indicators for long-running operations
- **Template System**: Advanced template processing with Jinja2
- **Smart Directory Analysis**: Intelligent detection of dotfile directories

### Advanced Features
- **Automated Installation**: 
  - System compatibility detection
  - Intelligent dependency analysis
  - Automatic backup creation
  - Post-installation verification
  - Rollback on failure
- **Enhanced Dependency Detection**:
  - Multiple config file format support (JSON, YAML, TOML, INI)
  - Shell script analysis
  - Desktop environment detection
  - Font dependency detection
  - Service dependency detection
- **System Compatibility Checks**:
  - Display server detection (X11/Wayland)
  - GPU information
  - Desktop environment detection
  - Available memory and disk space
  - Systemd availability
  - Fonts support
- **Parallel Processing**: Concurrent package installation and script execution
- **Profile Management**: Comprehensive profile system with save/load/switch capabilities
- **Directory Analysis**: Smart scoring and categorization of dotfile directories
- **Template Processing**: Support for multiple template formats with variable extraction
- **Error Recovery**: Graceful handling of errors with detailed logging
- **Progress Tracking**: Real-time progress indicators for all operations
- **Import/Export**: Portable configuration sharing with dependency and asset handling

### Development Features
- **Modular Architecture**: Well-organized codebase with clear separation of concerns
- **Type Hints**: Comprehensive type annotations for better code quality
- **Documentation**: Detailed docstrings and comments
- **Error Handling**: Robust error handling with context managers
- **Logging**: Detailed logging system for debugging

## Directory Structure
```
~/.config/rice-automata/
├── config.json         # Main configuration file
├── backups/           # Directory containing configuration backups
└── managed-rices/     # Directory containing managed rice configurations
```

## Configuration Format
```json
{
    "repository_name": {
        "dotfile_dirs": ["config", "local"],
        "package_lists": ["packages.txt"],
        "assets": ["fonts", "icons"],
        "profiles": {
            "default": {
                "packages": [],
                "config": {}
            }
        }
    }
}
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project doesnt contain any license.

## Changelog

### Latest Changes
- Added automated installation with enhanced detection (`--auto`)
- Added comprehensive system compatibility checks
- Enhanced dependency detection for multiple file formats
- Added intelligent backup and rollback system
- Added import/export functionality for sharing configurations
- Added preview command to show changes before applying
- Added diff command to compare configurations
- Added search functionality for finding configurations
- Improved CLI interface with better command organization
- Added profile management commands
- Enhanced backup and restore functionality
- Improved error handling and logging
- Added template support
- Enhanced dependency resolution
