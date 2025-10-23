"""
Private equity valuation strategy (planned).
"""

from finbricklab.core.interfaces import IValuationStrategy


class ValuationPrivateEquity(IValuationStrategy):
    """
    Private equity valuation strategy (kind: 'a.private_equity').
    
    This strategy is planned for future implementation.
    """
    
    def simulate(self, brick, ctx, months):
        """Raise NotImplementedError for planned feature."""
        raise NotImplementedError(
            "a.private_equity strategy is planned for future implementation. "
            "See ROADMAP for details."
        )
