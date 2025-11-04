#!/usr/bin/env python3
"""
Pytest wrapper that runs appropriate tests based on current git branch.

- On feat/postings-model-v2: runs only v2 tests (marked with @pytest.mark.v2)
- On other branches: runs all tests
"""

import subprocess
import sys
from pathlib import Path


def get_current_branch() -> str:
    """Get current git branch name."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: check environment variable or default to "main"
        return "main"


def main() -> int:
    """Run pytest with appropriate markers based on branch."""
    branch = get_current_branch()
    
    # On v2 feature branch, run only v2 tests
    if branch == "feat/postings-model-v2":
        args = ["poetry", "run", "pytest", "-m", "v2", "-q"]
    else:
        # On other branches, run all tests
        args = ["poetry", "run", "pytest", "-q"]
    
    # Pass through any additional arguments
    args.extend(sys.argv[1:])
    
    # Run pytest
    result = subprocess.run(args, cwd=Path(__file__).parent.parent)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())

