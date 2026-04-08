"""Review Agent - AI-guided assessment validation."""

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.domain.services.ai_orchestrator import AIOrchestrator, AIOrchestratorError

logger = logging.getLogger(__name__)


@dataclass
class ReviewIssue:
    """Issue found during assessment review."""

    severity: str
    category: str
    description: str
    location: str | None = None
    suggestion: str | None = None


@dataclass
class ReviewWarning:
    """Warning from assessment review."""

    description: str
    location: str | None = None
    suggestion: str | None = None


@dataclass
class ReviewResult:
    """Result of assessment review operation."""

    issues: list[ReviewIssue]
    warnings: list[ReviewWarning]
    missing_data: list[str]
    validation_passed: bool
    overall_score: float
    raw_response: dict[str, Any] | None = None


class ReviewAgent:
    """AI agent for validating noise assessment data.

    Responsibilities:
    - Validate completeness (all required fields present)
    - Validate consistency (lex_8h vs risk band alignment)
    - Validate correctness (calculated values match expected formulas)
    - Validate coverage (workers, measurements, noise sources documented)
    """

    TEMPLATE_NAME = "review_prompt.md"

    def __init__(self, orchestrator: AIOrchestrator):
        self._orchestrator = orchestrator

    async def review(
        self,
        assessment_data: dict[str, Any],
        company_name: str,
        ateco_code: str,
        assessment_id: UUID | None = None,
        focus_areas: list[str] | None = None,
    ) -> ReviewResult:
        """Review assessment data for issues.

        Args:
            assessment_data: Complete assessment JSON data
            company_name: Name of the company
            ateco_code: Primary ATECO code
            assessment_id: Optional assessment ID for logging
            focus_areas: Optional specific areas to focus on

        Returns:
            ReviewResult with structured validation results
        """
        context = {
            "assessment_data": str(assessment_data),
            "company_name": company_name,
            "ateco_code": ateco_code,
            "focus_areas": ", ".join(focus_areas) if focus_areas else "Tutti",
        }

        try:
            result = await self._orchestrator.execute(
                template_name=self.TEMPLATE_NAME,
                context=context,
                interaction_type="review",
                assessment_id=assessment_id,
            )

            return self._parse_review_result(result)

        except AIOrchestratorError as e:
            logger.error("Review failed: %s", e)
            return ReviewResult(
                issues=[
                    ReviewIssue(
                        severity="error",
                        category="system",
                        description="AI review service unavailable",
                        location="AI Orchestrator",
                        suggestion="Check AI service configuration",
                    )
                ],
                warnings=[],
                missing_data=["AI review failed"],
                validation_passed=False,
                overall_score=0.0,
                raw_response=None,
            )

    def _parse_review_result(self, result: dict[str, Any]) -> ReviewResult:
        """Parse raw AI response into structured review results."""
        issues = []
        for i in result.get("issues", []):
            issues.append(
                ReviewIssue(
                    severity=i.get("severity", "info"),
                    category=i.get("category", "unknown"),
                    description=i.get("description", ""),
                    location=i.get("location"),
                    suggestion=i.get("suggestion"),
                )
            )

        warnings = []
        for w in result.get("warnings", []):
            warnings.append(
                ReviewWarning(
                    description=w.get("description", ""),
                    location=w.get("location"),
                    suggestion=w.get("suggestion"),
                )
            )

        return ReviewResult(
            issues=issues,
            warnings=warnings,
            missing_data=result.get("missing_data", []),
            validation_passed=result.get("validation_passed", False),
            overall_score=result.get("overall_score", 0.5),
            raw_response=result,
        )
