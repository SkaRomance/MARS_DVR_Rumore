"""Template and print settings management service."""

import logging
from pathlib import Path
from typing import Any
from uuid import UUID
import json

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "docx_templates"


class TemplateService:
    """Manages document templates and print settings."""

    def __init__(self, templates_dir: Path | None = None):
        self._templates_dir = templates_dir or TEMPLATES_DIR
        self._templates_cache: dict[str, dict] = {}
        self._print_settings_cache: dict[str, dict] = {}

    async def get_template(self, template_key: str) -> dict | None:
        """Get template by key.

        Args:
            template_key: Template identifier (e.g., "base_dvr", "cover_page")

        Returns:
            Template dict with content and metadata, or None if not found
        """
        if template_key in self._templates_cache:
            return self._templates_cache[template_key]

        template_path = self._templates_dir / f"{template_key}.json"
        if template_path.exists():
            try:
                with open(template_path, "r", encoding="utf-8") as f:
                    template_data = json.load(f)
                    self._templates_cache[template_key] = template_data
                    return template_data
            except Exception as e:
                logger.error("Failed to load template %s: %s", template_key, e)
                return None

        template_file = self._templates_dir / f"{template_key}.docx"
        if template_file.exists():
            template_data = {
                "key": template_key,
                "type": "docx",
                "path": str(template_file),
            }
            self._templates_cache[template_key] = template_data
            return template_data

        return None

    async def save_template_override(self, template_key: str, content: dict) -> None:
        """Save template override.

        Args:
            template_key: Template identifier
            content: Template content dict
        """
        override_path = self._templates_dir / "overrides" / f"{template_key}.json"
        override_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(override_path, "w", encoding="utf-8") as f:
                json.dump(content, f, indent=2, ensure_ascii=False)
            logger.info("Saved template override: %s", template_key)
        except Exception as e:
            logger.error("Failed to save template override %s: %s", template_key, e)
            raise

    async def get_print_settings(self, company_id: UUID) -> dict | None:
        """Get print settings for company.

        Args:
            company_id: Company UUID

        Returns:
            Print settings dict, or None
        """
        cache_key = str(company_id)
        if cache_key in self._print_settings_cache:
            return self._print_settings_cache[cache_key]

        settings_path = self._templates_dir / "print_settings" / f"{cache_key}.json"
        if settings_path.exists():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    self._print_settings_cache[cache_key] = settings
                    return settings
            except Exception as e:
                logger.error("Failed to load print settings for %s: %s", company_id, e)
                return None

        return None

    async def save_print_settings(self, company_id: UUID, settings: dict) -> None:
        """Save print settings for company.

        Args:
            company_id: Company UUID
            settings: Print settings dict
        """
        settings_dir = self._templates_dir / "print_settings"
        settings_dir.mkdir(parents=True, exist_ok=True)

        settings_path = settings_dir / f"{company_id}.json"
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)

            cache_key = str(company_id)
            self._print_settings_cache[cache_key] = settings
            logger.info("Saved print settings for company: %s", company_id)
        except Exception as e:
            logger.error("Failed to save print settings for %s: %s", company_id, e)
            raise

    async def get_document_template(
        self, template_key: str, language: str = "it"
    ) -> dict:
        """Get document template with language fallback.

        Args:
            template_key: Template identifier
            language: Language code (default: "it")

        Returns:
            Template dict with content
        """
        template = await self.get_template(template_key)
        if template:
            return template

        lang_template = await self.get_template(f"{template_key}_{language}")
        if lang_template:
            return lang_template

        default_template = await self.get_template("base_dvr")
        if default_template:
            return default_template

        return {
            "key": template_key,
            "language": language,
            "type": "docx",
            "path": str(self._templates_dir / "base_dvr.docx"),
        }


_default_service: TemplateService | None = None


def get_template_service() -> TemplateService:
    """Get or create global template service instance."""
    global _default_service
    if _default_service is None:
        _default_service = TemplateService()
    return _default_service
