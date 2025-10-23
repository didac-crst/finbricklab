"""
Credit line schedule strategy (planned).
"""

from finbricklab.core.interfaces import IScheduleStrategy


class ScheduleCreditLine(IScheduleStrategy):
    """
    Credit line schedule strategy (kind: 'l.credit.line').
    
    This strategy is planned for future implementation.
    """
    
    def simulate(self, brick, ctx, months):
        """Raise NotImplementedError for planned feature."""
        raise NotImplementedError(
            "l.credit.line strategy is planned for future implementation. "
            "See ROADMAP for details."
        )
