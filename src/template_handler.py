import os
from jinja2 import Environment, FileSystemLoader
from src.utils import setup_logger

class TemplateHandler:
    """Handles template processing and application."""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.logger = setup_logger(verbose)
        self.template_env = Environment(loader=FileSystemLoader('/'))

    def apply_templates(self, source_dir: str, template_context: dict = None):
        """Apply templates to files in the source directory."""
        if not template_context:
            template_context = {}

        template_files = []
        for root, _, files in os.walk(source_dir):
            for file in files:
                if file.endswith('.template'):
                    template_files.append(os.path.join(root, file))

        for template_file in template_files:
            try:
                # Load and render template
                template = self.template_env.get_template(template_file)
                rendered = template.render(**template_context)

                # Write rendered content to target file
                target_file = template_file[:-9]  # Remove .template extension
                with open(target_file, 'w') as f:
                    f.write(rendered)

                if self.verbose:
                    self.logger.debug(f"Applied template: {template_file} -> {target_file}")

            except Exception as e:
                self.logger.error(f"Failed to process template {template_file}: {e}")
                continue

    def validate_template(self, template_file: str, context: dict = None):
        """Validate a template file with optional context."""
        try:
            template = self.template_env.get_template(template_file)
            if context:
                template.render(**context)
            return True
        except Exception as e:
            self.logger.error(f"Template validation failed for {template_file}: {e}")
            return False
