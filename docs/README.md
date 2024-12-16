# RiceAutomator: Your Dotfile Management Powerhouse

RiceAutomator is a powerful, flexible, and intelligent command-line tool designed to automate the downloading, installation, and management of dotfiles ("rices") on Linux systems. It goes beyond basic symlinking by providing advanced features like cross-distribution compatibility, intelligent dotfile discovery, selective installation, and NixOS integration.

## Features

- **Cross-Distribution Compatibility:** Detects and uses the appropriate package manager (pacman, apt, dnf, zypper) for your distribution.
- **Intelligent Dotfile Discovery:** Automatically detects configuration directories, wallpapers, scripts, and other dotfiles, even in unconventional structures.
- **Selective Installation:** Choose to install dotfiles for specific applications or categories (e.g., "nvim", "waybar", "wallpapers").
- **NixOS Integration:** Seamlessly installs and manages NixOS configurations within your dotfile repository.
- **Dependency Management:** Automatically detects and installs package dependencies.
- **GNU Stow Integration:** Uses GNU Stow for efficient and conflict-free symlinking.
- **Backup & Restore:** Creates backups of your current configurations before applying new dotfiles.
- **Multiple Rice Handling:** Intelligently detects and prompts you to select which rice to install from a repository containing multiple configurations.
- **Verbose Output:** Detailed logging of operations with a verbose mode for enhanced visibility.
- **Custom Rules Engine:** Create custom rules to discover dotfiles, and use a custom dependency map.
- **Custom Stow Options:** Allow the user to define the stow options to be used.
- **Comprehensive Error Handling:** Graceful handling of errors, providing informative messages.

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/riceautomator.git
   cd riceautomator
   ```

2.  **Make `cli.py` executable:**
    ```bash
    chmod +x src/cli.py
    ```

3.  **Run from the project directory using:** `./src/cli.py <command>`

## Usage

RiceAutomator is primarily a command-line tool. The basic structure of the commands is:

```bash
./src/cli.py <command> [options]
```

### Available Commands

-   **`clone` or `-S`:** Clones a dotfiles repository.

    ```bash
    ./src/cli.py clone <repository_url>
    ./src/cli.py -S <repository_url>
    ```

    **Example:**

    ```bash
    ./src/cli.py clone https://github.com/user/my-dotfiles.git
    ```

-   **`apply` or `-A`:** Applies dotfiles from a local repository.

    ```bash
    ./src/cli.py apply <repository_name> [options]
    ./src/cli.py -A <repository_name> [options]
    ```

    **Options:**

    -   `--skip-packages <package1,package2,...>`: Skips the installation of specified packages.
    -   `--stow-options "<stow option> <stow option>..."`: Passes custom options to the GNU Stow command.
     - `--target-packages <package1,package2,...>`: Apply dots only for these packages.

    **Example:**
    ```bash
     ./src/cli.py apply my-dotfiles --skip-packages neovim,waybar --stow-options "--adopt --no-folding"
     ./src/cli.py apply my-dotfiles --target-packages nvim,waybar
     ./src/cli.py apply my-dotfiles --target-packages wallpapers
    ```

-   **`manage` or `-m`:** Manages dotfiles by uninstalling previous ones and applying new ones.

    ```bash
    ./src/cli.py manage <repository_name> [options]
    ./src/cli.py -m <repository_name> [options]
    ```

    **Options:**

    -   `--stow-options "<stow option> <stow option>..."`: Passes custom options to the GNU Stow command.
    -  `--target-packages <package1,package2,...>`: Apply dots only for these packages.

   **Example:**

    ```bash
     ./src/cli.py manage my-dotfiles --stow-options "--adopt"
     ./src/cli.py manage my-dotfiles --target-packages nvim
    ```

-   **`backup` or `-b`:** Creates a backup of the currently applied dotfiles.

    ```bash
    ./src/cli.py backup <backup_name> <repository_name>
    ./src/cli.py -b <backup_name> <repository_name>
    ```

    **Example:**
    ```bash
    ./src/cli.py backup my_backup_1 my-dotfiles
    ```

-   **`-v` or `--verbose`:** Enables verbose output for more detailed logging.

    ```bash
    ./src/cli.py apply my-dotfiles -v
    ./src/cli.py apply -v my-dotfiles --target-packages nvim
    ```
-   **`--distro`:** Specifies the distribution for package management (e.g. `ubuntu`, `fedora`).
    ```bash
    ./src/cli.py apply my-dotfiles --distro ubuntu
    ```

### Examples

1.  **Clone a repository and apply dotfiles:**

    ```bash
    ./src/cli.py clone https://github.com/user/my-dotfiles.git
    ./src/cli.py apply my-dotfiles
    ```

2.  **Manage dotfiles, uninstalling the old ones, and applying the new ones, passing stow options:**

    ```bash
    ./src/cli.py manage my-dotfiles --stow-options "--adopt"
    ```
3. **Install only configs for `nvim` and `waybar` and verbose output:**
   ```bash
    ./src/cli.py apply my-dotfiles --target-packages nvim,waybar -v
    ```
4. **Clone a repository, apply nixos config (if present), and verbose output**
   ```bash
    ./src/cli.py clone https://github.com/user/my-nixos-dots.git
    ./src/cli.py apply my-nixos-dots -v
    ```
5. **Create a backup of the current configuration, and install with target packages**
   ```bash
    ./src/cli.py backup my_backup my-dotfiles
    ./src/cli.py apply my-dotfiles --target-packages nvim,waybar -v
    ```

## Configuration

-   **Configuration File:**
    -   `config.json`: Stores information about each managed rice, backups, and install status. Located in `$HOME/.config/riceautomator/`.
-   **Dependency Map:**
    -   `dependency_map.json`: Maps dotfile directory names to package names. Located in the `configs/` directory.
    -   Customize this file to map your dotfile directories to the corresponding package names for the installation.
-   **Rules File:**
    -   `rules.json`: Defines custom rules to discover dotfile directories. Located in the `configs/` directory.

## Contributing

Contributions are welcome! If you have suggestions, bug reports, or would like to contribute to the code, please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your changes.
3.  Make your changes and commit them with clear and descriptive messages.
4.  Open a pull request.

## Development

-   **Project Structure:**
    -   `src/`: Contains all the source code files.
        -   `cli.py`: Handles command-line interface parsing and main logic.
        -   `config.py`: Manages loading, saving, and handling configuration.
        -   `package.py`: Detects package managers, installs packages, and manages dependencies.
        -   `dotfile.py`: Discovers, links, and backs up dotfiles.
        -   `utils.py`: Provides utility functions (logging, input sanitization, etc.).
    -   `configs/`: Contains default configuration and rules files.
    -   `tests/`: Contains unit tests and integration tests.
    -   `docs/`: Contains documentation (including this README).
-   **Logging:** All operations are logged in `~/.config/riceautomator/riceautomator.log`. Use the verbose mode to output the logs on the terminal.

## Future Enhancements

- Pre/Post install scripts.
- Restore function
- Improve conflict handling with better stow options and user prompts.
- A GUI option for users less inclined to use the CLI.
- Improve documentation.
- Create more tests.

## License

This project is licensed under the Apache License, Version 2.0.
