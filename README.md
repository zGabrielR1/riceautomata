# RiceAutomata

A powerful command-line tool for managing dotfiles and system configurations on Linux/Unix systems.

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

# Apply dotfiles from a repository
riceautomata apply my-dotfiles

# Apply dotfiles with a specific profile
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
```

### Command Options

#### Global Options
- `-v, --verbose`: Enable verbose output

#### Apply/Manage Options
- `-p, --profile`: Specify profile to use
- `-t, --target-packages`: Comma-separated list of packages to configure
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

## Features

### Core Features
- **Command-Line Interface**: Simple and intuitive CLI for all operations
- **Profile Management**: Create and switch between different configuration profiles
- **Package Management**: 
  - Automatic package installation
  - Support for multiple package managers
  - Nix integration
- **Backup System**: Create and restore configuration backups

### Asset Management
- Automated handling of fonts and icons
- Proper permission management
- Directory structure preservation

### Configuration
- Support for multiple formats (JSON, YAML, TOML)
- Template system using Jinja2
- Flexible profile configurations

## Directory Structure
```
~/.config/rice-automata/
├── config.json         # Main configuration file
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

This project is licensed under the MIT License - see the LICENSE file for details.

## Changelog

### Latest Changes
- Added preview command to show changes before applying
- Added diff command to compare configurations
- Added search functionality for finding configurations
- Improved CLI interface with better command organization
- Added profile management commands
- Enhanced backup and restore functionality
- Improved error handling and logging
- Added template support
- Enhanced dependency resolution
