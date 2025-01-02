# RiceAutomata

A powerful and user-friendly dotfile manager that helps you manage multiple system configurations (rice setups) with ease.

## Quick Start

1. **Installation**
```bash
# Clone the repository
git clone https://github.com/zgabrielr1/riceautomata
cd riceautomata

# Install dependencies
pip install -r requirements.txt
```

2. **Basic Usage**

```bash
# Clone a dotfiles repository
riceautomata clone https://github.com/user/dotfiles

# List all available profiles (* indicates active profile)
riceautomata list

# List profiles for a specific repository
riceautomata list my-dotfiles

# Create a new profile
riceautomata create my-profile --description "My awesome rice"

# Apply a profile
riceautomata apply my-dotfiles --profile minimal

# Create a backup
riceautomata backup [backup-name]
```

## Features

- **Profile Management**: Create and switch between different system configurations
- **Automatic Backups**: Safe configuration changes with automatic backups
- **Package Management**: Handles package installations across different package managers
- **Smart Analysis**: Analyzes dotfiles for dependencies and conflicts
- **Safe Operations**: Rollback capability if something goes wrong
- **Template Support**: Use templates to customize configurations

## Command Reference

### Basic Commands
```bash
# Profile Management
riceautomata create <profile-name> [--description "Description"]  # Create a new profile
riceautomata list [repository-name]                              # List all profiles
riceautomata apply <profile-name>                               # Apply a profile

# Backup Operations
riceautomata backup [name]                                      # Create a backup
riceautomata restore <backup-name>                             # Restore from backup
```

### Advanced File Management
```bash
# Manage specific dotfiles
riceautomata manage <profile-name> --target-files .config/i3,.config/polybar [--dry-run]

# Import/Export Configurations
riceautomata export <repository-name> [-o output.json] [--include-deps] [--include-assets]
riceautomata import <file.json> [-n new-name] [--skip-deps] [--skip-assets]
```

### Snapshot Management
```bash
# Create a snapshot
riceautomata snapshot create <name> [-d "description"]

# List all snapshots
riceautomata snapshot list

# Restore from snapshot
riceautomata snapshot restore <name>

# Delete a snapshot
riceautomata snapshot delete <name>
```

## Directory Structure

```
~/.config/riceautomator/
├── profiles/           # Your rice profiles
├── backups/           # Automatic backups
├── snapshots/         # System snapshots
└── config.json        # Main configuration file
```

## Tips

- Always create a backup before applying a new profile
- Use the `--dry-run` flag to preview changes without applying them
- Check the logs at `~/.config/riceautomator/logs` if something goes wrong
- Use templates for configuration files that need system-specific modifications
- Export your configurations to share them with others
- Use snapshots for major system changes

## Advanced Features

### Export/Import
The export feature allows you to share your rice configurations with others:
- Include dependencies with `--include-deps`
- Include assets (wallpapers, themes) with `--include-assets`
- Specify custom output file with `-o filename.json`

### Snapshots
Snapshots are more comprehensive than backups:
- Capture the entire system state
- Include package lists
- Store configuration metadata
- Perfect for major system changes

### Templates
Use templates to handle system-specific configurations:
- Variables for system-dependent values
- Conditional sections based on hardware
- Automatic path adjustments

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
