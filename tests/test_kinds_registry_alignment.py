"""
Tests for kind taxonomy and registry alignment.
"""

from finbricklab.core.bricks import FlowRegistry, ScheduleRegistry, ValuationRegistry
from finbricklab.core.kinds import K


def test_registry_keys_are_current():
    """Ensure all registered keys belong to the new taxonomy."""
    ok = set(K.all_kinds())
    for reg in (ValuationRegistry, ScheduleRegistry, FlowRegistry):
        for k in reg.keys():
            assert k in ok, f"Registry key not in K: {k}"


def test_no_legacy_tokens_left():
    """Ensure no legacy kind names remain in registries."""
    bad = {
        "a.etf_unitized",
        "a.property_discrete", 
        "f.income.fixed",
        "f.expense.fixed",
        "l.mortgage.annuity",
    }
    for reg in (ValuationRegistry, ScheduleRegistry, FlowRegistry):
        for k in reg.keys():
            assert k not in bad, f"Legacy kind still registered: {k}"


def test_kind_prefix_semantics():
    """Test behavior-based family detection remains stable."""
    # Assets
    for k in (K.A_CASH, K.A_SECURITY_UNITIZED, K.A_PROPERTY):
        assert k.split(".")[0] == "a"

    # Liabilities
    for k in (K.L_LOAN_ANNUITY,):
        assert k.split(".")[0] == "l"

    # Flows
    for k in (K.F_INCOME_RECURRING, K.F_EXPENSE_RECURRING):
        assert k.split(".")[0] == "f"

    # Transfers
    for k in (K.T_TRANSFER_RECURRING,):
        assert k.split(".")[0] == "t"


def test_all_kinds_completeness():
    """Test that all_kinds() returns expected kinds."""
    expected_kinds = [
        # Assets
        "a.cash",
        "a.security.unitized",
        "a.property",
        "a.private_equity",
        # Liabilities
        "l.loan.annuity",
        "l.loan.balloon",
        "l.credit.line",
        "l.credit.fixed",
        # Flows
        "f.income.recurring",
        "f.income.onetime",
        "f.expense.recurring",
        "f.expense.onetime",
        # Transfers
        "t.transfer.recurring",
        "t.transfer.lumpsum",
        "t.transfer.scheduled",
    ]

    actual_kinds = K.all_kinds()
    assert set(actual_kinds) == set(expected_kinds)
    assert len(actual_kinds) == len(expected_kinds)
