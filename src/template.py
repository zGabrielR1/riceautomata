# dotfilemanager/template.py

from pathlib import Path
from typing import Dict, Any, Optional
import logging

from jinja2 import Environment, FileSystemLoader, TemplateError

from .exceptions import TemplateRenderingError

class TemplateHandler:
    """
    Handles rendering of template files.
    """
    def __init__(self, logger: Optional[logging.Logger] = None):
        """
        Initializes the TemplateHandler.

        Args:
            logger (Optional[logging.Logger]): Logger instance.
        """
        self.logger = logger or logging.getLogger('DotfileManager')

    def render_templates(self, source_dir: Path, target_dir: Path, context: Dict[str, Any]) -> bool:
        """
        Renders all template files in the source directory and saves them to the target directory.

        Args:
            source_dir (Path): Directory containing template files.
            target_dir (Path): Directory to save rendered files.
            context (Dict[str, Any]): Context for rendering templates.

        Returns:
            bool: True if successful, False otherwise.
        """
        try:
            env = Environment(loader=FileSystemLoader(str(source_dir)))
            for template_file in source_dir.glob('**/*.tpl'):
                relative_path = template_file.relative_to(source_dir).with_suffix('')
                target_file = target_dir / relative_path

                self.logger.debug(f"Rendering template: {template_file} to {target_file}")
                template = env.get_template(str(template_file.relative_to(source_dir)))
                rendered_content = template.render(context)

                target_file.parent.mkdir(parents=True, exist_ok=True)
                with target_file.open('w', encoding='utf-8') as f:
                    f.write(rendered_content)
                self.logger.info(f"Rendered template {template_file} to {target_file}")
            return True
        except TemplateError as e:
            self.logger.error(f"Template rendering failed: {e}")
            raise TemplateRenderingError(f"Template rendering failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error during template rendering: {e}")
            raise TemplateRenderingError(f"Template rendering failed due to unexpected error: {e}")