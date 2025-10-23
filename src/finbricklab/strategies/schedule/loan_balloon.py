"""
Balloon loan schedule strategy (planned).
"""

from finbricklab.core.interfaces import IScheduleStrategy


class ScheduleLoanBalloon(IScheduleStrategy):
    """
    Balloon loan schedule strategy (kind: 'l.loan.balloon').
    
    This strategy is planned for future implementation.
    """
    
    def simulate(self, brick, ctx, months):
        """Raise NotImplementedError for planned feature."""
        raise NotImplementedError(
            "l.loan.balloon strategy is planned for future implementation. "
            "See ROADMAP for details."
        )
