import os
import sys
import inquirer
from typing import Dict, Any, Optional
from src.utils import setup_logger
from src.config import ConfigManager
from src.package_manager import PackageManager
from src.state import StateManager

logger = setup_logger()

class SetupWizard:
    """Interactive setup wizard for RiceAutomata."""
    
    def __init__(self, config_manager: ConfigManager, state_manager: StateManager):
        self.config_manager = config_manager
        self.state_manager = state_manager
        self.package_manager = PackageManager()
        
    def run_setup(self) -> bool:
        """Run the interactive setup process."""
        try:
            print("\n🌟 Welcome to RiceAutomata Setup Wizard! 🌟\n")
            
            # Basic Configuration
            basic_config = self._get_basic_configuration()
            if not basic_config:
                return False
                
            # Package Manager Configuration
            pkg_config = self._configure_package_manager()
            if not pkg_config:
                return False
                
            # Default Profile Setup
            profile_config = self._setup_default_profile()
            if not profile_config:
                return False
                
            # Save Configuration
            config = {
                **basic_config,
                "package_manager": pkg_config,
                "default_profile": profile_config
            }
            
            self.config_manager.update_config(config)
            self.state_manager.update_state(
                active_profile=profile_config.get("name")
            )
            
            print("\n✨ Setup completed successfully! ✨")
            self._show_next_steps()
            return True
            
        except KeyboardInterrupt:
            print("\n\nSetup cancelled by user.")
            return False
        except Exception as e:
            logger.error(f"Setup failed: {e}")
            return False
            
    def _get_basic_configuration(self) -> Optional[Dict[str, Any]]:
        """Get basic configuration options from user."""
        questions = [
            inquirer.Text(
                "user_name",
                message="What's your name? (for commit messages)",
                validate=lambda _, x: len(x) > 0
            ),
            inquirer.Text(
                "user_email",
                message="What's your email? (for commit messages)",
                validate=lambda _, x: "@" in x
            ),
            inquirer.Path(
                "dotfiles_dir",
                message="Where would you like to store your dotfiles?",
                path_type=inquirer.Path.DIRECTORY,
                default=os.path.expanduser("~/.dotfiles")
            ),
            inquirer.Confirm(
                "backup_enabled",
                message="Enable automatic backups?",
                default=True
            ),
            inquirer.Text(
                "backup_dir",
                message="Where should backups be stored?",
                default=os.path.expanduser("~/.dotfiles/backups"),
                ignore=lambda x: not x["backup_enabled"]
            )
        ]
        
        try:
            answers = inquirer.prompt(questions)
            if not answers:
                return None
                
            # Create necessary directories
            os.makedirs(answers["dotfiles_dir"], exist_ok=True)
            if answers.get("backup_enabled"):
                os.makedirs(answers["backup_dir"], exist_ok=True)
                
            return answers
            
        except Exception as e:
            logger.error(f"Error during basic configuration: {e}")
            return None
            
    def _configure_package_manager(self) -> Optional[Dict[str, Any]]:
        """Configure package manager settings."""
        detected_pm = self.package_manager.detect_package_manager()
        
        questions = [
            inquirer.List(
                "package_manager",
                message="Select your primary package manager:",
                choices=[
                    ("Pacman (Arch)", "pacman"),
                    ("APT (Debian/Ubuntu)", "apt"),
                    ("DNF (Fedora)", "dnf"),
                    ("Zypper (openSUSE)", "zypper"),
                    ("Nix", "nix")
                ],
                default=detected_pm
            ),
            inquirer.Confirm(
                "install_missing",
                message="Automatically install missing packages?",
                default=True
            ),
            inquirer.Confirm(
                "use_nix",
                message="Enable Nix integration for reproducible builds?",
                default=False
            )
        ]
        
        try:
            answers = inquirer.prompt(questions)
            if not answers:
                return None
                
            if answers["use_nix"] and not self.package_manager.is_nix_installed():
                print("\nNix is not installed. Would you like to install it now?")
                if inquirer.confirm("Install Nix?", default=True):
                    if not self.package_manager.install_nix():
                        print("Failed to install Nix. Continuing without Nix integration.")
                        answers["use_nix"] = False
                else:
                    answers["use_nix"] = False
                    
            return answers
            
        except Exception as e:
            logger.error(f"Error during package manager configuration: {e}")
            return None
            
    def _setup_default_profile(self) -> Optional[Dict[str, Any]]:
        """Set up the default profile configuration."""
        questions = [
            inquirer.Text(
                "name",
                message="Name for your default profile:",
                default="default"
            ),
            inquirer.List(
                "theme",
                message="Select a color theme:",
                choices=[
                    "Dark Mode",
                    "Light Mode",
                    "System Default",
                    "Custom"
                ]
            ),
            inquirer.Checkbox(
                "features",
                message="Select features to enable:",
                choices=[
                    "Automatic Updates",
                    "Backup Before Changes",
                    "Template Processing",
                    "Script Execution"
                ]
            )
        ]
        
        try:
            answers = inquirer.prompt(questions)
            if not answers:
                return None
                
            # Convert feature list to dictionary
            features = {
                feature.lower().replace(" ", "_"): True
                for feature in answers["features"]
            }
            
            return {
                "name": answers["name"],
                "theme": answers["theme"].lower().replace(" ", "_"),
                "features": features
            }
            
        except Exception as e:
            logger.error(f"Error during profile setup: {e}")
            return None
            
    def _show_next_steps(self):
        """Show next steps after setup completion."""
        print("\n📝 Next Steps:")
        print("1. Clone your first rice repository:")
        print("   riceautomata clone https://github.com/user/dotfiles")
        print("\n2. Apply the configuration:")
        print("   riceautomata apply my-dotfiles")
        print("\n3. Create additional profiles if needed:")
        print("   riceautomata profile create my-dotfiles work")
        print("\nFor more commands, run: riceautomata --help")
        
    def validate_environment(self) -> bool:
        """Validate the system environment."""
        checks = [
            ("Git installed", self._check_git),
            ("Stow installed", self._check_stow),
            ("Package manager available", self._check_package_manager),
            ("Write permissions", self._check_permissions)
        ]
        
        print("\n🔍 Checking system requirements...")
        all_passed = True
        
        for name, check_func in checks:
            try:
                if check_func():
                    print(f"✅ {name}: OK")
                else:
                    print(f"❌ {name}: Failed")
                    all_passed = False
            except Exception as e:
                print(f"❌ {name}: Error - {e}")
                all_passed = False
                
        return all_passed
        
    def _check_git(self) -> bool:
        """Check if git is installed."""
        return os.system("git --version > /dev/null 2>&1") == 0
        
    def _check_stow(self) -> bool:
        """Check if GNU Stow is installed."""
        return os.system("stow --version > /dev/null 2>&1") == 0
        
    def _check_package_manager(self) -> bool:
        """Check if a supported package manager is available."""
        return self.package_manager.detect_package_manager() is not None
        
    def _check_permissions(self) -> bool:
        """Check if we have necessary permissions."""
        test_dir = os.path.expanduser("~/.config/riceautomata_test")
        try:
            os.makedirs(test_dir, exist_ok=True)
            os.rmdir(test_dir)
            return True
        except:
            return False
