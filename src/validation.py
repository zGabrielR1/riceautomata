import os
import re
import json
import yaml
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass
from src.utils import setup_logger

logger = setup_logger()

@dataclass
class ValidationError:
    """Represents a configuration validation error."""
    path: str
    message: str
    severity: str = "error"  # error, warning, info

class ConfigValidator:
    """Validates configuration files and settings."""
    
    def __init__(self, schema_dir: Optional[str] = None):
        self.schema_dir = schema_dir
        self._load_schemas()
        
    def _load_schemas(self):
        """Load JSON schemas for validation."""
        self.schemas = {}
        if not self.schema_dir or not os.path.exists(self.schema_dir):
            return
            
        for file in os.listdir(self.schema_dir):
            if file.endswith('.json'):
                try:
                    with open(os.path.join(self.schema_dir, file), 'r') as f:
                        name = os.path.splitext(file)[0]
                        self.schemas[name] = json.load(f)
                except Exception as e:
                    logger.error(f"Error loading schema {file}: {e}")
                    
    def validate_config(self, config: Dict[str, Any], schema_name: str) -> List[ValidationError]:
        """Validate a configuration against a schema."""
        errors = []
        
        if schema_name not in self.schemas:
            errors.append(ValidationError("", f"Schema '{schema_name}' not found"))
            return errors
            
        schema = self.schemas[schema_name]
        return self._validate_against_schema(config, schema, "")
        
    def _validate_against_schema(self, data: Any, schema: Dict[str, Any], path: str) -> List[ValidationError]:
        """Recursively validate data against a schema."""
        errors = []
        
        if "type" in schema:
            type_errors = self._validate_type(data, schema["type"], path)
            errors.extend(type_errors)
            
        if schema.get("required") and isinstance(data, dict):
            for field in schema["required"]:
                if field not in data:
                    errors.append(ValidationError(
                        f"{path}.{field}" if path else field,
                        f"Required field '{field}' is missing"
                    ))
                    
        if isinstance(data, dict) and "properties" in schema:
            for key, value in data.items():
                if key in schema["properties"]:
                    field_path = f"{path}.{key}" if path else key
                    field_errors = self._validate_against_schema(
                        value,
                        schema["properties"][key],
                        field_path
                    )
                    errors.extend(field_errors)
                    
        return errors
        
    def _validate_type(self, value: Any, expected_type: str, path: str) -> List[ValidationError]:
        """Validate a value's type."""
        errors = []
        
        type_map = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        if expected_type in type_map:
            expected_class = type_map[expected_type]
            if not isinstance(value, expected_class):
                errors.append(ValidationError(
                    path,
                    f"Expected type '{expected_type}', got '{type(value).__name__}'"
                ))
                
        return errors
        
    def validate_file_paths(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate file and directory paths in configuration."""
        errors = []
        
        def check_path(path: str, path_type: str, config_path: str):
            if not os.path.exists(path):
                errors.append(ValidationError(
                    config_path,
                    f"{path_type} not found: {path}",
                    "warning"
                ))
            elif path_type == "Directory" and not os.path.isdir(path):
                errors.append(ValidationError(
                    config_path,
                    f"Path is not a directory: {path}",
                    "error"
                ))
            elif path_type == "File" and not os.path.isfile(path):
                errors.append(ValidationError(
                    config_path,
                    f"Path is not a file: {path}",
                    "error"
                ))
                
        paths_to_check = [
            (config.get("dotfiles_dir"), "Directory", "dotfiles_dir"),
            (config.get("backup_dir"), "Directory", "backup_dir"),
            (config.get("config_file"), "File", "config_file")
        ]
        
        for path, path_type, config_path in paths_to_check:
            if path:
                check_path(os.path.expanduser(path), path_type, config_path)
                
        return errors
        
    def validate_dependencies(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate package dependencies."""
        errors = []
        packages = config.get("packages", {})
        
        for package, version in packages.items():
            if not isinstance(version, str):
                errors.append(ValidationError(
                    f"packages.{package}",
                    f"Package version must be a string, got {type(version).__name__}"
                ))
            elif not re.match(r'^[\w\-\.\+~]+$', version):
                errors.append(ValidationError(
                    f"packages.{package}",
                    f"Invalid version format: {version}"
                ))
                
        return errors
        
    def validate_scripts(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate script configurations."""
        errors = []
        scripts = config.get("scripts", {})
        
        valid_phases = {"pre_clone", "post_clone", "pre_apply", "post_apply"}
        
        for phase, script_list in scripts.items():
            if phase not in valid_phases:
                errors.append(ValidationError(
                    f"scripts.{phase}",
                    f"Invalid script phase: {phase}"
                ))
                continue
                
            if not isinstance(script_list, list):
                errors.append(ValidationError(
                    f"scripts.{phase}",
                    "Script list must be an array"
                ))
                continue
                
            for i, script in enumerate(script_list):
                if not isinstance(script, str):
                    errors.append(ValidationError(
                        f"scripts.{phase}[{i}]",
                        "Script must be a string"
                    ))
                    
        return errors
        
    def validate_templates(self, config: Dict[str, Any]) -> List[ValidationError]:
        """Validate template configurations."""
        errors = []
        templates = config.get("templates", {})
        
        for template, settings in templates.items():
            if not isinstance(settings, dict):
                errors.append(ValidationError(
                    f"templates.{template}",
                    "Template settings must be an object"
                ))
                continue
                
            required_fields = ["source", "target"]
            for field in required_fields:
                if field not in settings:
                    errors.append(ValidationError(
                        f"templates.{template}",
                        f"Missing required field: {field}"
                    ))
                    
        return errors
        
    def format_errors(self, errors: List[ValidationError], colored: bool = True) -> str:
        """Format validation errors for display."""
        if not errors:
            return "No validation errors found."
            
        # ANSI color codes
        colors = {
            "error": "\033[91m" if colored else "",  # Red
            "warning": "\033[93m" if colored else "",  # Yellow
            "info": "\033[94m" if colored else "",  # Blue
            "reset": "\033[0m" if colored else ""
        }
        
        result = []
        for error in errors:
            prefix = {
                "error": "❌ Error",
                "warning": "⚠️ Warning",
                "info": "ℹ️ Info"
            }.get(error.severity, "")
            
            result.append(
                f"{colors[error.severity]}{prefix} in {error.path}:\n"
                f"  {error.message}{colors['reset']}"
            )
            
        return "\n".join(result)
