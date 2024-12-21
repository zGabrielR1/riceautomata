# RiceAutomata

A powerful dotfile and system configuration manager designed to automate the process of setting up and managing your Linux/Unix system configurations.

## Features

### Core Features
- **Automated Dotfile Management**: Seamlessly manage and deploy your dotfiles across different systems
- **Multi-Profile Support**: Create and manage different configuration profiles for various environments
- **Package Management**: 
  - Automatic package installation and management
  - Support for multiple package managers (pacman, apt, dnf, zypper, pip, npm, cargo)
  - Nix package manager integration
  - Parallel package installation for improved performance

### Asset Management
- **Asset Processing**: Automated handling of fonts, icons, and other assets
- **Permission Management**: Proper file permission handling during deployment
- **Directory Structure**: Maintains correct directory hierarchies

### Configuration Features
- **Format Support**: Handle multiple configuration file formats:
  - JSON
  - YAML
  - TOML
  - Plain text
- **Template Support**: Use Jinja2 templates for dynamic configuration files
- **Backup System**: Create and manage backups of your configurations

### Advanced Features
- **Profile Management**: 
  - Environment-specific configurations
  - Profile-specific package sets
  - Custom asset management per profile
- **Dependency Resolution**: Automatic detection and installation of dependencies
- **Error Handling**: Robust error handling with detailed logging
- **Rollback Support**: Safely rollback changes if something goes wrong

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/riceautomata.git
cd riceautomata

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from src.dotfile import DotfileManager

# Initialize the manager
manager = DotfileManager(verbose=True)

# Apply dotfiles from a repository
manager.apply_dotfiles(
    repository_name="my-dotfiles",
    stow_options=[],
    package_manager="pacman"
)
```

### Profile Management

```python
# Create and manage profiles
profiles = {
    "work": {
        "packages": ["vim", "tmux", "git"],
        "config": {
            "target_dir": "~/.config",
            "files": {
                "vim/vimrc": {"settings": "work-specific-settings"}
            }
        }
    },
    "home": {
        "packages": ["neovim", "alacritty"],
        "assets": "~/dotfiles/assets"
    }
}

manager._manage_profiles(profiles)
```

### Package Management

```python
# Install packages from a list
packages = ["neovim", "tmux", "zsh"]
manager._install_packages(packages)

# Read and install packages from a file
manager._read_package_list("packages.yaml")
```

## Configuration

### Directory Structure
```
~/.config/rice-automata/
├── config.json         # Main configuration file
└── managed-rices/     # Directory containing managed rice configurations
```

### Configuration File Format
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

## Acknowledgments

- GNU Stow for symlink management
- All the package managers that make this possible
- The dotfile community for inspiration

## Changelog

### Latest Changes
- Added profile management system
- Implemented parallel package installation
- Added support for multiple package managers
- Improved asset management
- Enhanced error handling and logging
- Added backup and rollback functionality
- Added template support for configuration files
- Improved dependency resolution
