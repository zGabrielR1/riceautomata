# dotfilemanager/script.py

import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from .exceptions import ScriptExecutionError

class ScriptRunner:
    """
    Manages execution of scripts.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initializes the ScriptRunner.

        Args:
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')

    def run_scripts_by_phase(self, base_dir: Path, phase: str, script_config: Dict[str, Any], env: Optional[dict] = None) -> bool:
        """
        Runs scripts associated with a specific phase.

        Args:
            base_dir (Path): Base directory containing scripts.
            phase (str): Phase name (e.g., 'pre_clone', 'post_install').
            script_config (Dict[str, Any]): Configuration containing scripts for phases.
            env (Optional[dict]): Environment variables for the scripts.

        Returns:
            bool: True if all scripts run successfully, False otherwise.
        """
        scripts = script_config.get(phase, [])
        for script in scripts:
            script_path = base_dir / script
            if not script_path.exists():
                self.logger.error(f"Script not found: {script_path}")
                return False
            if not self.run_script(script_path, env=env):
                self.logger.error(f"Failed to execute script: {script_path}")
                return False
        return True

    def run_script(self, script_path: Path, env: Optional[dict] = None) -> bool:
        """
        Executes a single script.

        Args:
            script_path (Path): Path to the script.
            env (Optional[dict]): Environment variables for the script.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            self.logger.info(f"Executing script: {script_path}")
            result = subprocess.run([str(script_path)], check=True, shell=True, capture_output=True, text=True, env=env)
            self.logger.debug(f"Script output: {result.stdout}")
            return True
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Script {script_path} failed with error: {e.stderr}")
            raise ScriptExecutionError(f"Script {script_path} failed.")
        except Exception as e:
            self.logger.error(f"Unexpected error while executing script {script_path}: {e}")
            raise ScriptExecutionError(f"Script {script_path} failed due to unexpected error.")