"""
Brick cloning utilities for FinBrickLab.

This module provides utilities for creating deep, scenario-local clones of bricks
to ensure immutability and prevent cross-scenario state bleed.
"""

from __future__ import annotations

from copy import deepcopy


def clone_brick(brick):
    """
    Return a deep, scenario-local clone of a brick.

    This function creates a complete deep copy of a brick object, including:
    - Deep-copies spec and links dicts (including numpy arrays)
    - Leaves global, immutable metadata as-is (id, name, kind)
    - Does NOT carry any runtime buffers/state

    Args:
        brick: The brick object to clone

    Returns:
        A deep copy of the brick with scenario-local state

    Note:
        If bricks ever attach transient runtime caches, they should be cleared here:
        # b._runtime_cache = {}
    """
    b = deepcopy(brick)  # simplest & safest; ensure bricks don't hold global singletons

    # If you ever attach transient runtime caches on bricks, clear them here:
    # b._runtime_cache = {}

    return b
