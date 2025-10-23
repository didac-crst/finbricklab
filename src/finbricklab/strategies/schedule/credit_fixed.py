"""
Fixed-term credit schedule strategy (planned).
"""

from finbricklab.core.interfaces import IScheduleStrategy


class ScheduleCreditFixed(IScheduleStrategy):
    """
    Fixed-term credit schedule strategy (kind: 'l.credit.fixed').
    
    This strategy is planned for future implementation.
    """
    
    def simulate(self, brick, ctx, months):
        """Raise NotImplementedError for planned feature."""
        raise NotImplementedError(
            "l.credit.fixed strategy is planned for future implementation. "
            "See ROADMAP for details."
        )
