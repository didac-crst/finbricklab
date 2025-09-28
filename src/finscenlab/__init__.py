"""
Compatibility shim for finscenlab package.

This package provides backward compatibility for existing code that imports
from 'finscenlab'. New code should use 'finbricklab' instead.
"""

import warnings

warnings.warn(
    "Package 'finscenlab' is deprecated and will be removed in a future version. "
    "Please use 'finbricklab' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Import everything from finbricklab to maintain compatibility
from finbricklab import *
