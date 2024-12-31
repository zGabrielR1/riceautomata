# RiceAutomator: Your Dotfile Management Powerhouse

RiceAutomator is a powerful, flexible, and intelligent command-line tool designed to automate the downloading, installation, and management of dotfiles ("rices") on Linux systems. It goes beyond basic symlinking by providing advanced features like cross-distribution compatibility, intelligent dotfile discovery, selective installation, and robust error handling with automatic rollback capabilities.

## Features

- **Fully Automated Installation:**
  - One-command installation of any rice directory
  - Automatic dependency detection and parallel installation
  - Smart system compatibility checking
  - Intelligent installation strategy selection
  - Automatic rollback on failure

- **Robust Error Handling & Recovery:**
  - Automatic backup creation before any file operation
  - Rollback support for failed operations
  - Retry logic with exponential backoff for network operations
  - Comprehensive error messages and logging

- **Advanced Configuration Management:**
  - Multiple configuration profiles support
  - JSON schema validation for configurations
  - Template processing with Jinja2
  - Custom configuration inheritance

- **Cross-Distribution Compatibility:** 
  - Detects and uses the appropriate package manager (pacman, apt, dnf, zypper)
  - Handles distribution-specific package names and dependencies
  - Supports NixOS configurations

- **Intelligent Dotfile Discovery:** 
  - Automatically detects configuration directories and files
  - Smart categorization of dotfiles (configs, wallpapers, scripts)
  - Custom rules engine for specialized detection
  - Supports unconventional directory structures
  - Automatic dependency detection from config files

- **File Operations:**
  - Automatic backup before modifications
  - Safe file operations with rollback support
  - Template processing with variable substitution
  - GNU Stow integration for symlinking
  - Parallel processing for faster deployment

- **Snapshot System:**
  - Create checkpoints of your entire rice configuration
  - Safe experimentation with new themes and configs
  - Easy rollback to previous working states
  - Package tracking and restoration
  - Automatic backup and recovery

- **Additional Features:**
  - Selective package installation
  - Dependency management
  - Multiple rice handling
  - Verbose logging
  - Custom stow options
  - Profile-based configurations

## Quick Start

### Automated Installation

The fastest way to install a rice is using the auto-install command:

```bash
python -m src.cli auto-install /path/to/rice
```

This will:
1. Automatically detect your system configuration
2. Find and install all required dependencies
3. Choose the best installation method (Nix, Stow, or direct symlinks)
4. Apply the rice configurations
5. Handle any errors and rollback if needed

Options:
- `--force`: Force installation even if conflicts exist
- `--no-deps`: Skip dependency installation
- `-v` or `--verbose`: Enable verbose output

### Manual Installation

If you prefer more control over the installation process, you can still use the traditional commands:

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/riceautomator.git
   cd riceautomator
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Make `cli.py` executable:**
   ```bash
   chmod +x src/cli.py
   ```

## Usage

RiceAutomator provides a powerful CLI interface with various commands and options:

```bash
./src/cli.py <command> [options]
```

### Global Options

- `-v, --verbose`: Enable verbose output
- `--shell`: Specify shell for scripts (bash, zsh, fish)
- `--distro`: Specify distribution for package management
- `--aur-helper`: Select AUR helper (paru, yay) for Arch Linux

### Commands

#### Clone Repository
```bash
./src/cli.py clone <repository_url>
# or
./src/cli.py -S <repository_url>
```

Clones a dotfiles repository with automatic error recovery and retry logic.

#### Apply Dotfiles
```bash
./src/cli.py apply <repository_name> [options]
# or
./src/cli.py -A <repository_name> [options]
```

**Options:**
- `--skip-packages <pkg1,pkg2>`: Skip specific packages
- `--stow-options "<options>"`: Custom GNU Stow options
- `--target-packages <pkg1,pkg2>`: Apply only specific packages
- `--template-context <file.json>`: Provide variables for template processing
- `--ignore-rules`: Ignore custom discovery rules
- `--custom-paths <paths>`: Additional paths to process
- `--custom-extras-paths <file.json>`: JSON file with extra paths mapping
- `--profile <name>`: Use specific configuration profile

#### Manage Dotfiles
```bash
./src/cli.py manage <repository_name> [options]
# or
./src/cli.py -m <repository_name> [options]
```

Manages dotfiles with automatic backup and rollback support. Accepts the same options as `apply`.

#### Create Backup
```bash
./src/cli.py backup <backup_name> <repository_name>
# or
./src/cli.py -b <backup_name> <repository_name>
```

Creates a backup with automatic cleanup of old backups.

#### Snapshot Management

Create a snapshot of your current configuration:
```bash
riceautomata snapshot create <name> [-d "description"]
```

List available snapshots:
```bash
riceautomata snapshot list
```

Restore a previous snapshot:
```bash
riceautomata snapshot restore <name>
```

Delete a snapshot:
```bash
riceautomata snapshot delete <name>
```

For detailed information about the snapshot system, see [Snapshot Documentation](snapshots.md).

### Profile Management

RiceAutomator supports multiple configuration profiles per repository. Each profile can have its own settings, paths, and configurations:

#### List Profiles
```bash
./src/cli.py list-profiles <repository_name>
```
Shows all available profiles and indicates the currently active one.

#### Create Profile
```bash
./src/cli.py create-profile <repository_name> <profile_name>
```
Creates a new configuration profile.

#### Switch Profile
```bash
./src/cli.py switch-profile <repository_name> <profile_name>
```
Switches to a different configuration profile.

You can also specify a profile when applying or managing dotfiles:
```bash
./src/cli.py apply my-dotfiles --profile work
./src/cli.py manage my-dotfiles --profile home
```

Each profile can have its own:
- Dotfile directories
- Dependencies
- Script configurations
- Custom paths
- Template variables

### Template Processing

Support for Jinja2 templates in configuration files:

```bash
# Apply with template variables
./src/cli.py apply my-dotfiles --template-context vars.json
```

Example `vars.json`:
```json
{
  "username": "john",
  "email": "john@example.com",
  "theme": "dark"
}
```

### Examples

1. **Basic dotfile application:**
   ```bash
   ./src/cli.py apply my-dotfiles
   ```

2. **Apply with custom options and profile:**
   ```bash
   ./src/cli.py apply my-dotfiles --profile work --target-packages nvim,waybar --template-context vars.json
   ```

3. **Manage dotfiles with rollback support:**
   ```bash
   ./src/cli.py manage my-dotfiles --stow-options "--adopt" --custom-extras-paths extras.json
   ```

4. **Profile management workflow:**
   ```bash
   # List available profiles
   ./src/cli.py list-profiles my-dotfiles
   
   # Create a new work profile
   ./src/cli.py create-profile my-dotfiles work
   
   # Switch to work profile and apply
   ./src/cli.py switch-profile my-dotfiles work
   ./src/cli.py apply my-dotfiles
   ```

## Nix Rice Installation

RiceAutomator supports the installation of Nix rices with automatic detection:

- **Automatic Detection**: The system automatically detects if a rice contains Nix configurations
- **Non-NixOS Systems**: If Nix is not installed, the system will automatically fall back to using GNU Stow or direct symlinks
- **NixOS Systems**: Automatic detection and installation of Nix rices if Nix is available

To install a Nix rice, simply include it in your repository's configuration. The application will handle the rest, ensuring compatibility and proper installation based on your system's capabilities.

## Error Handling

RiceAutomator now provides comprehensive error handling:

- Automatic backup creation before operations
- Rollback support for failed operations
- Detailed error messages
- Operation retry with exponential backoff
- Safe file operations with validation

If an operation fails:
1. The error is logged with details
2. Any changes are automatically rolled back
3. A backup is preserved for manual recovery

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to our repository.

## License

No license. yet.
