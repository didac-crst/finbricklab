"""
Tests for mortgage parameter aliasing and precedence behavior.
"""

import warnings
from datetime import date

import numpy as np
import pytest
from finbricklab.core.bricks import LBrick
from finbricklab.core.context import ScenarioContext
from finbricklab.core.kinds import K
from finbricklab.strategies.schedule.loan_annuity import (
    FinBrickDeprecationWarning,
    FinBrickWarning,
    ScheduleLoanAnnuity,
)


class TestMortgageAliasing:
    """Test parameter aliasing and precedence behavior."""

    def test_new_aliases_only(self):
        """Test using only new parameter aliases."""
        mortgage = LBrick(
            id="alias_test",
            name="Alias Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "interest_rate_pa": 0.025,  # New alias
                "amortization_rate_pa": 0.03,  # New alias
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)

        # Check that aliases were applied
        assert mortgage.spec["rate_pa"] == 0.025
        assert mortgage.spec["amortization_pa"] == 0.03
        assert "term_months" in mortgage.spec  # Should be calculated

    def test_old_names_only(self):
        """Test using only old parameter names (backward compatibility)."""
        mortgage = LBrick(
            id="old_names_test",
            name="Old Names Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,  # Old name
                "amortization_pa": 0.03,  # Old name
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)

        # Check that old names work as before
        assert mortgage.spec["rate_pa"] == 0.025
        assert mortgage.spec["amortization_pa"] == 0.03
        assert "term_months" in mortgage.spec  # Should be calculated

    def test_alias_clash_with_warning(self):
        """Test alias clash produces warning and correct precedence."""
        mortgage = LBrick(
            id="clash_test",
            name="Clash Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,  # Old name
                "interest_rate_pa": 0.030,  # New alias (different value)
                "amortization_pa": 0.03,
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            strategy.prepare(mortgage, ctx)

            # Check that warning was issued
            assert len(w) == 1, f"Expected 1 warning, got {len(w)}"
            assert issubclass(w[0].category, FinBrickWarning)
            assert "interest_rate_pa" in str(w[0].message) and "rate_pa" in str(
                w[0].message
            )

        # Check that old name wins (precedence)
        assert mortgage.spec["rate_pa"] == 0.025
        assert mortgage.spec["interest_rate_pa"] == 0.030  # New alias preserved

    def test_credit_window_precedence(self):
        """Test credit window parameter precedence."""
        mortgage = LBrick(
            id="credit_window_test",
            name="Credit Window Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            start_date=date(2026, 1, 1),
            end_date=date(2030, 1, 1),  # Pre-existing end_date
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,
                "amortization_pa": 0.03,
                "credit_end_date": date(2031, 1, 1),  # Should override end_date
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            strategy.prepare(mortgage, ctx)

            # Check that override warning was issued
            assert len(w) == 1, f"Expected 1 warning, got {len(w)}"
            assert issubclass(w[0].category, FinBrickWarning)
            assert "Overriding brick.end_date with credit_end_date" in str(w[0].message)

        # Check that credit_end_date was applied
        assert mortgage.end_date == date(2031, 1, 1)

    def test_credit_window_hierarchy(self):
        """Test credit window parameter hierarchy."""
        # Test credit_end_date > credit_term_months > fix_rate_months

        # Test 1: credit_end_date should win
        mortgage1 = LBrick(
            id="hierarchy_test_1",
            name="Hierarchy Test 1",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,
                "amortization_pa": 0.03,
                "credit_end_date": date(2031, 1, 1),
                "credit_term_months": 120,
                "fix_rate_months": 180,
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage1, ctx)

        # credit_end_date should win
        assert mortgage1.end_date == date(2031, 1, 1)
        assert mortgage1.duration_m is None

        # Test 2: credit_term_months should win if no credit_end_date
        mortgage2 = LBrick(
            id="hierarchy_test_2",
            name="Hierarchy Test 2",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,
                "amortization_pa": 0.03,
                "credit_term_months": 120,
                "fix_rate_months": 180,
            },
        )

        strategy.prepare(mortgage2, ctx)

        # credit_term_months should win
        assert mortgage2.duration_m == 120

        # Test 3: fix_rate_months should win if no others
        mortgage3 = LBrick(
            id="hierarchy_test_3",
            name="Hierarchy Test 3",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,
                "amortization_pa": 0.03,
                "fix_rate_months": 180,
            },
        )

        strategy.prepare(mortgage3, ctx)

        # fix_rate_months should win
        assert mortgage3.duration_m == 180

    def test_deprecated_annual_rate_warning(self):
        """Test that annual_rate produces deprecation warning."""
        mortgage = LBrick(
            id="deprecated_test",
            name="Deprecated Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,  # Required parameter
                "annual_rate": 0.025,  # Deprecated parameter (should warn)
                "amortization_pa": 0.03,
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()

        # Capture warnings
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            strategy.prepare(mortgage, ctx)

            # Check that deprecation warning was issued
            assert len(w) == 1, f"Expected 1 warning, got {len(w)}"
            assert issubclass(w[0].category, FinBrickDeprecationWarning)
            assert "annual_rate" in str(w[0].message)
            assert "interest_rate_pa" in str(w[0].message)

    def test_warnings_are_once_only(self):
        """Test that warnings are issued only once per brick."""
        mortgage = LBrick(
            id="once_only_test",
            name="Once Only Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                "principal": 300_000.0,
                "rate_pa": 0.025,
                "interest_rate_pa": 0.030,  # Should trigger warning
                "amortization_pa": 0.03,
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()

        # First call - should warn
        with warnings.catch_warnings(record=True) as w1:
            warnings.simplefilter("always")
            strategy.prepare(mortgage, ctx)
            assert len(w1) == 1

        # Second call - should NOT warn (already warned)
        with warnings.catch_warnings(record=True) as w2:
            warnings.simplefilter("always")
            strategy.prepare(mortgage, ctx)
            assert len(w2) == 0

    def test_lmortgagespec_integration(self):
        """Test that LMortgageSpec objects work with aliases."""
        from dataclasses import asdict

        from finbricklab.core.specs import LMortgageSpec

        spec = LMortgageSpec(
            rate_pa=0.025,
            amortization_pa=0.03,
        )

        mortgage = LBrick(
            id="lmortgagespec_test",
            name="LMortgageSpec Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec={
                **asdict(spec),
                "principal": 300_000.0,  # Add principal to the spec dict
            },
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()
        strategy.prepare(mortgage, ctx)

        # Check that LMortgageSpec was normalized to dict
        assert isinstance(mortgage.spec, dict)
        assert mortgage.spec["rate_pa"] == 0.025
        assert mortgage.spec["amortization_pa"] == 0.03
        assert mortgage.spec["principal"] == 300_000.0

    def test_invalid_spec_type_error(self):
        """Test that invalid spec types raise TypeError."""
        mortgage = LBrick(
            id="invalid_spec_test",
            name="Invalid Spec Test Mortgage",
            kind=K.L_LOAN_ANNUITY,
            spec="invalid_spec",  # String instead of dict or LMortgageSpec
        )

        t_index = np.arange("2026-01", "2046-01", dtype="datetime64[M]")
        ctx = ScenarioContext(t_index=t_index, currency="EUR", registry={})

        strategy = ScheduleLoanAnnuity()

        with pytest.raises(TypeError, match="spec must be dict or LMortgageSpec"):
            strategy.prepare(mortgage, ctx)
