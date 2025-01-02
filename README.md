# RiceAutomata

A powerful and user-friendly dotfile manager that helps you manage multiple system configurations (rice setups) with ease.

## Quick Start

1. **Installation**
```bash
# Clone the repository
git clone https://github.com/yourusername/riceautomata
cd riceautomata

# Install dependencies
pip install -r requirements.txt
```

2. **Basic Usage**

```bash
# Clone a dotfiles repository
riceautomata clone https://github.com/user/dotfiles

# List available profiles
riceautomata list my-dotfiles

# List all available profiles (* indicates active profile)
riceautomata list

# Apply a profile
riceautomata apply my-dotfiles --profile minimal

# Backup current configuration
riceautomata backup
```

## Features

- **Profile Management**: Create and switch between different system configurations
- **Automatic Backups**: Safe configuration changes with automatic backups
- **Package Management**: Handles package installations across different package managers
- **Smart Analysis**: Analyzes dotfiles for dependencies and conflicts
- **Safe Operations**: Rollback capability if something goes wrong
- **Template Support**: Use templates to customize configurations

## Common Commands

```bash
# Create a new profile
riceautomata create my-profile

# Apply a specific profile
riceautomata apply my-profile

# List all available profiles (* indicates active profile)
riceautomata list

# List profiles for a specific repository
riceautomata list my-dotfiles

# You can also use list-profiles (same functionality)
riceautomata list-profiles [repository-name]

# Create a backup of current configuration
riceautomata backup

# Restore from a backup
riceautomata restore <backup-name>

# Manage specific dotfiles
riceautomata manage my-profile --target-files .config/i3,.config/polybar
```

## Directory Structure

```
~/.config/riceautomator/
├── profiles/           # Your rice profiles
├── backups/           # Automatic backups
└── config.json        # Main configuration file
```

## Tips

- Always create a backup before applying a new profile
- Use the `--dry-run` flag to preview changes
- Check the logs at `~/.config/riceautomator/logs` if something goes wrong
- Use templates for configuration files that need system-specific modifications

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
