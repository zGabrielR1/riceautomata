# src/scripts.py
import subprocess
import os
from src.utils import setup_logger
import shlex

logger = setup_logger()

class ScriptRunner:

    def __init__(self, verbose=False):
        self.logger = setup_logger(verbose)
        self.verbose = verbose

    def _run_command(self, command, cwd=None, check=True, env = None):
      """Runs a command and returns the result."""
      try:
          if self.verbose:
             self.logger.debug(f"Running command: {' '.join(command)}")
          result = subprocess.run(command, capture_output=True, text=True, check=check, cwd=cwd, env=env)
          if check and result.stderr:
              self.logger.error(f"Command failed: {' '.join(command)}")
              self.logger.error(f"Error:\n{result.stderr}")
              return False
          if self.verbose and result.stdout:
              self.logger.debug(f"Output:\n{result.stdout.strip()}")
          return result
      except FileNotFoundError as e:
          self.logger.error(f"Command not found: {command[0]}: {e}")
          return False
      except Exception as e:
         self.logger.error(f"Error executing command: {' '.join(command)}. Error: {e}")
         return False

    def run_script(self, script_path, cwd=None, shell="bash", check=True, env = None):
        """Runs a script using the specified shell."""
        if not os.path.exists(script_path):
            self.logger.error(f"Script not found: {script_path}")
            return False
        
        command = [shell, script_path]
        return self._run_command(command, cwd, check, env)
    
    def run_scripts_by_phase(self, local_dir, phase, script_config, env = None):
        """Runs scripts based on the specified phase."""
        if not script_config or not script_config.get(phase):
           return True  # No scripts to run for this phase

        scripts = script_config.get(phase)
        if not isinstance(scripts, list):
            scripts = [scripts]  # Ensure it's a list
        for script_path in scripts:
          full_script_path = os.path.join(local_dir, script_path)
          shell = script_config.get('shell', 'bash')
          if os.path.exists(full_script_path):
              self.logger.info(f"Executing {phase} script: {full_script_path}")
              if not self.run_script(full_script_path, local_dir, shell, env = env):
                  self.logger.error(f"Failed to execute {phase} script: {full_script_path}")
                  return False
          else:
               self.logger.warning(f"{phase} script not found: {full_script_path}")
        return True