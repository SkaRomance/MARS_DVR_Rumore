"""Prompt templates package for AI services."""

from src.domain.services.prompts.template_loader import (
    TemplateLoader,
    get_template_loader,
)

__all__ = ["get_template_loader", "TemplateLoader"]
