"""Template loader using Jinja2 for AI prompts."""

import logging
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, Template, StrictUndefined

logger = logging.getLogger(__name__)

# Module path for templates
TEMPLATES_DIR = Path(__file__).parent / "templates"


class TemplateLoader:
    """Loads and renders Jinja2 templates for AI prompts."""

    def __init__(self, templates_dir: Path | None = None):
        self._templates_dir = templates_dir or TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template_name: str, context: dict[str, Any]) -> str:
        """Render a template with context.

        Args:
            template_name: Name of template file (e.g., "bootstrap_prompt.md")
            context: Variables to inject into template

        Returns:
            Rendered template string
        """
        try:
            template = self._env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error("Failed to render template %s: %s", template_name, e)
            raise TemplateRenderError(f"Failed to render {template_name}: {e}")

    def render_string(self, template_str: str, context: dict[str, Any]) -> str:
        """Render a template string with context.

        Args:
            template_str: Template string (not file)
            context: Variables to inject

        Returns:
            Rendered string
        """
        template = self._env.from_string(template_str)
        return template.render(**context)

    def list_templates(self) -> list[str]:
        """List available template files."""
        return self._env.loader.list_templates()


# Global template loader instance
_loader: TemplateLoader | None = None


def get_template_loader() -> TemplateLoader:
    """Get or create global template loader instance."""
    global _loader
    if _loader is None:
        _loader = TemplateLoader()
    return _loader


class TemplateRenderError(Exception):
    """Error rendering template."""

    pass
