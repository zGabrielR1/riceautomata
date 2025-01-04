# RiceAutomata: Intelligent Dotfile and System Configuration Manager

[![Test Status](https://github.com/zgabrielr1/riceautomata/actions/workflows/test.yml/badge.svg)](https://github.com/zgabrielr1/riceautomata/actions/workflows/test.yml)

RiceAutomata is a powerful and flexible command-line tool designed to automate the management and deployment of your dotfiles and system configurations (also known as "rices"). It simplifies the process of setting up and maintaining a consistent development environment across multiple machines.

## Features

*   **Automated Dotfile Management:**
    *   **Intelligent Discovery:** Automatically discovers dotfiles in your rice repository based on configurable rules, target package dependencies, and custom paths.
    *   **Flexible Application:** Applies dotfiles using GNU Stow for symbolic linking, with options for direct copying or custom handling.
    *   **Template Processing:** Supports Jinja2 templating to dynamically generate configuration files based on user-specific contexts.
    *   **Profile Management:**  Create and manage multiple profiles to easily switch between different configurations (e.g., work, personal, minimal).
    *   **Phased Script Execution:** Run custom scripts at various phases of the dotfile application process (pre-clone, post-clone, pre-apply, post-apply, pre-uninstall, post-uninstall, custom).

*   **Dependency Management:**
    *   **Automated Package Installation:**  Detects and installs required packages using the appropriate package manager for your system (currently supports Pacman, AUR (via yay or paru), APT, DNF, Zypper, Pip, Npm, and Cargo with plans to add more).
    *   **Dependency Map:** Uses a configurable `dependency_map.json` to map common dotfile configurations to their corresponding packages (e.g., `vim` -> `vim`, `config/i3` -> `i3wm`).
    *   **Repository-Specific Dependencies:** Parses `rice.json` within rice repositories to handle project-specific dependencies (see [Repository Configuration](#repository-configuration-ricejson)).
    *   **Font Installation:** Automatically detects and installs fonts from a "fonts" directory if present in your rice.

*   **System Snapshots:**
    *   Create snapshots of your current system configuration.
    *   Restore from snapshots to quickly revert to a previous state.

*   **Backup and Restore:**
    *   Creates backups of existing configuration files before applying dotfiles.
    *   Allows restoring from backups in case of errors or unwanted changes.

*   **Portability:**
    *   **Export:** Export your rice configuration to a portable JSON format, including dependencies and asset information.
    *   **Import:** Import a rice configuration from a previously exported JSON file, optionally skipping dependency or asset installation.

*   **Extensible Design:**
    *   Easily add support for new package managers.
    *   Modular structure allows for customization and extension.

*   **Command-line Interface:**
    *   User-friendly CLI with commands for cloning, applying, managing, backing up, restoring, and more.
    *   Verbose output option for debugging.

## Installation

```bash
pip install riceautomata
```

## Usage

```
riceautomata [OPTIONS] COMMAND [ARGS]...
```

**Available Commands:**

*   **`clone <repository_url>`:** Clone a dotfiles repository.
*   **`apply <repository_name>`:** Apply a cloned repository.
    *   `-p, --profile <profile_name>`: Specify the profile to apply.
    *   `--auto`: Enable fully automated installation (use with caution).
    *   `--no-backup`: Skip creating a backup of existing configuration.
    *   `--force`: Force installation even if validation fails.
    *   `--skip-verify`: Skip post-installation verification.
    *   `--stow-options`: Space-separated GNU Stow options.
    *   `--templates`: Process template files (e.g., Jinja2 templates).
    *   `--custom-paths`: Comma-separated list of custom paths in the format `key=value`.
    *   `--ignore-rules`: Ignore default dotfile discovery rules.
*   **`manage <repository_name>`:** Manage specific dotfiles in a repository.
    *   `--target-files`: Comma-separated list of files to manage.
    *   `--dry-run`: Preview changes without applying them.
    *   `--stow-options`: Space-separated GNU Stow options.
*   **`list [repository_name]`:** List available profiles (all or for a specific repository).
*   **`profile <subcommand>`:** Manage profiles.
    *   `list <repository_name>`: List profiles for a repository.
    *   `create <repository_name> <profile_name>`: Create a new profile.
    *   `switch <repository_name> <profile_name>`: Switch to a different profile.
*   **`backup <repository_name> <backup_name>`:** Create a backup of the applied configuration.
*   **`restore <repository_name> <backup_name>`:** Restore a previously created backup.
*   **`export <repository_name>`:** Export a repository configuration to a JSON file.
    *   `-o, --output <output_file>`: Output file path (default: `rice-export.json`).
    *   `--include-deps`: Include dependency information in the export.
    *   `--include-assets`: Include asset information in the export.
*   **`import <file>`:** Import a repository configuration from a JSON file.
    *   `-n, --name <new_name>`: New name for the imported repository.
    *   `--skip-deps`: Skip dependency installation during import.
    *   `--skip-assets`: Skip asset installation during import.
*   **`snapshot <subcommand>`:** Manage system snapshots.
    *   `create <name>`: Create a new snapshot.
    *   `list`: List all snapshots.
    *   `restore <name>`: Restore from a snapshot.
    *   `delete <name>`: Delete a snapshot.
*   **`preview <repository_name>`:** Preview the changes that will be made before applying a rice.
*   **`diff <repository_name>`:** Show the differences between the current configuration and the one that would be applied.
*   **`search <query>`:** Search for configurations or settings.
    *   `-r, --repository`: Limit search to a specific repository.
    *   `--content`: Search within file contents.

**Options:**

*   `-v, --verbose`: Enable verbose output (for debugging).
*   `-h, --help`: Show the help message and exit.

## Repository Configuration (`rice.json`)

You can include a `rice.json` file in your dotfiles repository to provide more specific instructions to RiceAutomata. Here's an example:

```json
{
  "name": "MyAwesomeRice",
  "description": "My personalized rice configuration",
  "author": "Your Name",
  "version": "1.0",
  "dotfiles": {
    "directories": [
      "dotfiles/config",
      "dotfiles/scripts",
      "dotfiles/.zshrc"
    ],
    "categories": {
        "dotfiles/config": "config",
        "dotfiles/.zshrc": "config",
        "dotfiles/scripts": "script"
    }
  },
  "dependencies": {
    "pacman": ["i3-wm", "polybar", "neovim", "firefox"],
    "aur": ["yay", "nerd-fonts-complete"],
    "pip": ["some-python-package"]
  },
  "scripts": {
    "pre_apply": ["scripts/pre_apply.sh"],
    "post_apply": ["scripts/post_apply.sh"]
  },
  "templates": {
    "directory": "templates",
    "context": {
      "username": "$USER",
      "hostname": "$HOSTNAME"
    }
  },
  "profiles": {
    "default": {
      "description": "Full featured desktop setup."
    },
    "minimal": {
      "description": "Lightweight setup for minimal resource usage.",
      "dotfiles": {
          "exclude": [
              "dotfiles/config/neovim",
              "dotfiles/.config/polybar"
          ]
      },
      "packages": {
          "pacman": {
            "exclude": ["polybar"]
          }
      }
    }
  }
}
```

**Explanation of `rice.json` fields:**

*   **`name`:**  Name of your rice.
*   **`description`:** A brief description of your rice.
*   **`author`:** Your name.
*   **`version`:** Version of your rice.
*   **`dotfiles`:**
    *   **`directories`:** A list of directories or files to be treated as dotfiles. These paths can be relative to the repository root or absolute.
    *   **`categories`:** A mapping of dotfile paths to categories (e.g., "config", "script", "wallpaper"). This helps RiceAutomata organize and apply them correctly.
*   **`dependencies`:**
    *   **`pacman`:**  List of packages to install using `pacman`.
    *   **`aur`:** List of packages to install using an AUR helper (default: `yay`).
    *   **`pip`, `npm`, `cargo`:** List of packages to install using `pip`, `npm` and `cargo` respectively.
    *   **... (Other package managers):** You can add sections for other package managers as they are implemented.
*   **`scripts`:**
    *   **`pre_clone`:** Scripts to run before cloning a repository.
    *   **`post_clone`:** Scripts to run after cloning.
    *   **`pre_install_dependencies`:** Scripts to run before installing dependencies.
    *   **`post_install_dependencies`:** Scripts to run after installing dependencies.
    *   **`pre_apply`:** Scripts to run before applying dotfiles.
    *   **`post_apply`:** Scripts to run after applying dotfiles.
    *   **`pre_uninstall`:** Scripts to run before uninstalling dotfiles.
    *   **`post_uninstall`:** Scripts to run after uninstalling dotfiles.
    *   **`custom_scripts`:** Custom scripts to run when invoked with apply --custom-scripts.
*   **`templates`:**
    *   **`directory`:** The directory containing template files (default: "templates").
    *   **`context`:** A dictionary of key-value pairs to be used as context when rendering templates. You can use environment variables (e.g., `$USER`, `$HOSTNAME`).
*   **`profiles`:**
    *   **`[profile_name]`:**  Each profile is defined as a separate section.
        *   **`description`:** A description of the profile.
        *   **`dotfiles`:**
            *   **`exclude`:** List of dotfiles or directories to exclude when applying this profile.
        *   **`packages`:**
            *   **`[package_manager]`:**  e.g., `pacman`, `apt`, `aur`, etc.
                *   **`exclude`:** List of packages to exclude when applying this profile.
