import os
import platform
import subprocess
import asyncio
from typing import Optional, Dict, List, Tuple
from src.utils import setup_logger
from src.progress import ProgressTracker, ProgressContext

logger = setup_logger()

class NixManager:
    """Manages Nix installation and configuration."""
    
    def __init__(self, progress_tracker: Optional[ProgressTracker] = None):
        self.progress_tracker = progress_tracker or ProgressTracker()
        self._init_platform_info()
        
    def _init_platform_info(self):
        """Initialize platform-specific information."""
        self.platform = platform.system().lower()
        self.is_linux = self.platform == "linux"
        self.is_macos = self.platform == "darwin"
        
        # Detect Linux distribution
        if self.is_linux:
            try:
                with open("/etc/os-release") as f:
                    lines = f.readlines()
                    self.distro_info = dict(
                        line.strip().split("=", 1) for line in lines if "=" in line
                    )
            except Exception as e:
                logger.error(f"Failed to detect Linux distribution: {e}")
                self.distro_info = {}
                
    async def install_nix(self, multi_user: bool = True) -> bool:
        """
        Install Nix package manager.
        
        Args:
            multi_user: Whether to install Nix in multi-user mode
            
        Returns:
            bool indicating success
        """
        with ProgressContext(self.progress_tracker, "Installing Nix", 100) as progress:
            try:
                # Check if Nix is already installed
                if self.is_nix_installed():
                    logger.info("Nix is already installed")
                    return True
                    
                progress.update(10, "Checking system requirements")
                if not await self._check_requirements():
                    return False
                    
                progress.update(20, "Preparing installation")
                if not await self._prepare_installation(multi_user):
                    return False
                    
                progress.update(30, "Downloading Nix installer")
                if not await self._download_installer():
                    return False
                    
                progress.update(50, "Running Nix installer")
                if not await self._run_installer(multi_user):
                    return False
                    
                progress.update(80, "Configuring Nix")
                if not await self._configure_nix():
                    return False
                    
                progress.update(90, "Verifying installation")
                if not self.verify_installation():
                    return False
                    
                progress.update(100, "Nix installation completed")
                return True
                
            except Exception as e:
                logger.error(f"Failed to install Nix: {e}")
                return False
                
    def is_nix_installed(self) -> bool:
        """Check if Nix is installed."""
        try:
            result = subprocess.run(
                ["nix", "--version"],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except:
            return False
            
    async def _check_requirements(self) -> bool:
        """Check system requirements for Nix installation."""
        try:
            # Check for required commands
            required_commands = ["curl", "sudo", "systemctl" if self.is_linux else ""]
            for cmd in required_commands:
                if cmd and not await self._check_command(cmd):
                    logger.error(f"Required command not found: {cmd}")
                    return False
                    
            # Check system-specific requirements
            if self.is_linux:
                if not os.path.exists("/proc"):
                    logger.error("procfs is required for Nix")
                    return False
                    
            return True
            
        except Exception as e:
            logger.error(f"Failed to check requirements: {e}")
            return False
            
    async def _prepare_installation(self, multi_user: bool) -> bool:
        """Prepare the system for Nix installation."""
        try:
            if self.is_linux and multi_user:
                # Create nix group
                if not await self._run_command(["sudo", "groupadd", "-r", "nix-users"]):
                    return False
                    
                # Create directories
                dirs = ["/nix", "/etc/nix"]
                for dir_path in dirs:
                    if not await self._run_command(["sudo", "mkdir", "-p", dir_path]):
                        return False
                        
            return True
            
        except Exception as e:
            logger.error(f"Failed to prepare for installation: {e}")
            return False
            
    async def _download_installer(self) -> bool:
        """Download the Nix installer."""
        try:
            installer_url = "https://nixos.org/nix/install"
            result = await self._run_command([
                "curl", "-L", installer_url,
                "-o", "/tmp/nix-install.sh"
            ])
            
            if result:
                await self._run_command(["chmod", "+x", "/tmp/nix-install.sh"])
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Failed to download installer: {e}")
            return False
            
    async def _run_installer(self, multi_user: bool) -> bool:
        """Run the Nix installer."""
        try:
            env = os.environ.copy()
            if not multi_user:
                env["NIX_INSTALLER_NO_MODIFY_PROFILE"] = "1"
                
            cmd = ["sudo" if multi_user else "sh", "/tmp/nix-install.sh"]
            if multi_user:
                cmd.append("--daemon")
                
            result = await self._run_command(cmd, env=env)
            return result
            
        except Exception as e:
            logger.error(f"Failed to run installer: {e}")
            return False
            
    async def _configure_nix(self) -> bool:
        """Configure Nix after installation."""
        try:
            # Enable flakes if not already enabled
            nix_conf = "/etc/nix/nix.conf"
            if os.path.exists(nix_conf):
                with open(nix_conf, "r") as f:
                    content = f.read()
                    
                if "experimental-features" not in content:
                    with open(nix_conf, "a") as f:
                        f.write("\nexperimental-features = nix-command flakes\n")
                        
            # Initialize nix profile
            if not await self._run_command(["nix-channel", "--update"]):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to configure Nix: {e}")
            return False
            
    def verify_installation(self) -> bool:
        """Verify Nix installation."""
        try:
            # Check nix command
            if not self.is_nix_installed():
                return False
                
            # Check nix-env
            result = subprocess.run(
                ["nix-env", "--version"],
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return False
                
            # Check store directory
            if not os.path.exists("/nix/store"):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to verify installation: {e}")
            return False
            
    async def _check_command(self, command: str) -> bool:
        """Check if a command is available."""
        try:
            result = await asyncio.create_subprocess_exec(
                "which",
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            return result.returncode == 0
        except:
            return False
            
    async def _run_command(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None
    ) -> bool:
        """Run a command asynchronously."""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                env=env or os.environ,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Command failed: {' '.join(command)}")
                logger.error(f"Error: {stderr.decode().strip()}")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to run command {' '.join(command)}: {e}")
            return False
            
    async def setup_nix_flake(self, directory: str) -> bool:
        """Set up a Nix flake in the specified directory."""
        try:
            flake_content = """
{
  description = "RiceAutomata managed system configuration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs = { self, nixpkgs, home-manager }: {
    # Add your configurations here
  };
}
"""
            flake_path = os.path.join(directory, "flake.nix")
            with open(flake_path, "w") as f:
                f.write(flake_content.strip())
                
            # Initialize git repository if needed
            if not os.path.exists(os.path.join(directory, ".git")):
                await self._run_command(["git", "init"], {"GIT_DIR": directory})
                
            # Initialize flake
            if not await self._run_command(["nix", "flake", "update"], {"PWD": directory}):
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Failed to set up Nix flake: {e}")
            return False
