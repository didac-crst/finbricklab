"""
Custom exceptions for FinBrickLab.

This module provides specialized exception classes for better error handling
and user experience throughout the FinBrickLab system.
"""

from __future__ import annotations


class ScenarioValidationError(Exception):
    """
    Raised when scenario validation fails during creation.

    This exception provides detailed information about validation failures,
    including the scenario ID, validation report, and problematic brick IDs.

    Attributes:
        scenario_id: The ID of the scenario that failed validation
        report: The validation report object (if available)
        problem_ids: List of brick/MacroBrick IDs that caused issues
    """

    def __init__(
        self,
        scenario_id: str,
        message: str,
        report=None,
        problem_ids: list[str] | None = None,
    ):
        self.scenario_id = scenario_id
        self.report = report
        self.problem_ids = problem_ids or []
        super().__init__(self._fmt(message))

    def _fmt(self, msg: str) -> str:
        """Format the error message with additional context."""
        suffix = ""
        if self.problem_ids:
            preview = ", ".join(self.problem_ids[:10])
            more = (
                f" (+{len(self.problem_ids)-10} more)"
                if len(self.problem_ids) > 10
                else ""
            )
            suffix = f" | problem_ids: [{preview}]{more}"
        return f"[Scenario {self.scenario_id}] {msg}{suffix}"
