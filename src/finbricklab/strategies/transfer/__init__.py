"""
Transfer strategies for FinBrickLab.
"""

from .lumpsum import TransferLumpSum
from .recurring import TransferRecurring
from .scheduled import TransferScheduled

__all__ = [
    "TransferLumpSum",
    "TransferRecurring",
    "TransferScheduled",
]
