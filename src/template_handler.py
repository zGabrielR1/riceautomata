import os
import re
import json
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader, Template
from src.utils import setup_logger

logger = setup_logger()

class TemplateHandler:
    """Handles the processing and application of dotfile templates."""
    
    def __init__(self, template_dir: str = None, context: Dict = None):
        self.template_dir = template_dir
        self.context = context or {}
        self.logger = logger
        self._init_jinja_env()
        
    def _init_jinja_env(self):
        """Initialize Jinja2 environment with custom filters and globals."""
        if self.template_dir and os.path.exists(self.template_dir):
            self.env = Environment(
                loader=FileSystemLoader(self.template_dir),
                trim_blocks=True,
                lstrip_blocks=True
            )
        else:
            self.env = Environment(
                trim_blocks=True,
                lstrip_blocks=True
            )
            
        # Add custom filters
        self.env.filters.update({
            'to_json': lambda x: json.dumps(x, indent=2),
            'basename': os.path.basename,
            'dirname': os.path.dirname
        })
        
    def discover_templates(self, directory: str) -> List[str]:
        """
        Discover template files in a directory.
        
        Args:
            directory: Directory to search for templates
            
        Returns:
            List of discovered template file paths
        """
        templates = []
        template_patterns = [
            r'\.j2$',
            r'\.template$',
            r'\.tpl$',
            r'\.tmpl$'
        ]
        
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if any(re.search(pattern, file) for pattern in template_patterns):
                        templates.append(os.path.join(root, file))
                        
            if templates:
                self.logger.info(f"Discovered {len(templates)} template files")
            else:
                self.logger.debug("No template files found")
                
        except Exception as e:
            self.logger.error(f"Error discovering templates: {e}")
            
        return templates
        
    def process_template(self, template_path: str, output_path: str, context: Optional[Dict] = None) -> bool:
        """
        Process a template file and write the result.
        
        Args:
            template_path: Path to the template file
            output_path: Path where the processed file should be written
            context: Optional additional context to merge with default context
            
        Returns:
            bool indicating success
        """
        try:
            # Merge contexts
            template_context = {**self.context, **(context or {})}
            
            # Load template
            if self.template_dir and template_path.startswith(self.template_dir):
                template_name = os.path.relpath(template_path, self.template_dir)
                template = self.env.get_template(template_name)
            else:
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = Template(f.read())
                    
            # Render template
            result = template.render(**template_context)
            
            # Create output directory if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Write result
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(result)
                
            self.logger.info(f"Successfully processed template: {template_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing template {template_path}: {e}")
            return False
            
    def process_directory(self, source_dir: str, target_dir: str, context: Optional[Dict] = None) -> bool:
        """
        Process all templates in a directory.
        
        Args:
            source_dir: Directory containing templates
            target_dir: Directory where processed files should be written
            context: Optional additional context to merge with default context
            
        Returns:
            bool indicating overall success
        """
        success = True
        templates = self.discover_templates(source_dir)
        
        for template_path in templates:
            rel_path = os.path.relpath(template_path, source_dir)
            output_path = os.path.join(
                target_dir,
                re.sub(r'\.(j2|template|tpl|tmpl)$', '', rel_path)
            )
            
            if not self.process_template(template_path, output_path, context):
                success = False
                
        return success
        
    def validate_template(self, template_path: str) -> bool:
        """
        Validate a template file.
        
        Args:
            template_path: Path to the template file
            
        Returns:
            bool indicating if template is valid
        """
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                template_content = f.read()
                
            # Try to parse template
            Template(template_content)
            return True
            
        except Exception as e:
            self.logger.error(f"Template validation failed for {template_path}: {e}")
            return False
            
    def update_context(self, new_context: Dict):
        """Update the default context with new values."""
        self.context.update(new_context)
        
    def get_template_variables(self, template_path: str) -> List[str]:
        """
        Extract variables used in a template.
        
        Args:
            template_path: Path to the template file
            
        Returns:
            List of variable names used in the template
        """
        variables = set()
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Find {{ variable }} patterns
            var_pattern = r'{{\s*(\w+)[^}]*}}'
            variables.update(re.findall(var_pattern, content))
            
            # Find {% if variable %} patterns
            if_pattern = r'{%\s*if\s+(\w+)[^%]*%}'
            variables.update(re.findall(if_pattern, content))
            
            # Find {% for x in variable %} patterns
            for_pattern = r'{%\s*for\s+\w+\s+in\s+(\w+)[^%]*%}'
            variables.update(re.findall(for_pattern, content))
            
        except Exception as e:
            self.logger.error(f"Error extracting variables from {template_path}: {e}")
            
        return sorted(list(variables))
