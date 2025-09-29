#!/usr/bin/env python3
"""
Check for forbidden tokens in the codebase.

This script scans the repository for forbidden tokens like "tenant" and "household"
to ensure clean Entity-only naming throughout the codebase.
"""

import argparse
import os
import re
import sys


def find_forbidden_tokens(
    directory: str, tokens: list[str], exclude_patterns: list[str] | None = None
) -> dict[str, list[tuple[int, str]]]:
    """
    Find forbidden tokens in the codebase.

    Args:
        directory: Directory to search
        tokens: List of forbidden tokens to search for
        exclude_patterns: List of regex patterns to exclude from search

    Returns:
        Dictionary mapping file paths to list of (line_number, line_content) tuples
    """
    if exclude_patterns is None:
        exclude_patterns = [
            r"__pycache__",
            r"\.git",
            r"\.pytest_cache",
            r"\.venv",
            r"node_modules",
            r"\.pyc$",
            r"\.pyo$",
            r"\.pyd$",
            r"\.so$",
            r"\.egg$",
            r"\.egg-info$",
            r"dist$",
            r"build$",
        ]

    results = {}

    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [
            d
            for d in dirs
            if not any(re.search(pattern, d) for pattern in exclude_patterns)
        ]

        for file in files:
            file_path = os.path.join(root, file)

            # Skip excluded files
            if any(re.search(pattern, file_path) for pattern in exclude_patterns):
                continue

            # Only check text files
            if not file.endswith(
                (".py", ".md", ".txt", ".yml", ".yaml", ".json", ".toml")
            ):
                continue

            try:
                with open(file_path, encoding="utf-8") as f:
                    lines = f.readlines()

                file_matches = []
                for line_num, line in enumerate(lines, 1):
                    for token in tokens:
                        # Case-insensitive search
                        if re.search(re.escape(token), line, re.IGNORECASE):
                            file_matches.append((line_num, line.rstrip()))

                if file_matches:
                    results[file_path] = file_matches

            except (UnicodeDecodeError, PermissionError):
                # Skip binary files or files we can't read
                continue

    return results


def main():
    """Main function."""
    parser = argparse.ArgumentParser(
        description="Check for forbidden tokens in codebase"
    )
    parser.add_argument(
        "--directory",
        "-d",
        default=".",
        help="Directory to search (default: current directory)",
    )
    parser.add_argument(
        "--tokens",
        "-t",
        nargs="+",
        default=["tenant", "household"],
        help="Forbidden tokens to search for (default: tenant household)",
    )
    parser.add_argument(
        "--exclude", "-e", nargs="*", help="Additional exclude patterns"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    exclude_patterns = [
        r"__pycache__",
        r"\.git",
        r"\.pytest_cache",
        r"\.venv",
        r"node_modules",
        r"\.pyc$",
        r"\.pyo$",
        r"\.pyd$",
        r"\.so$",
        r"\.egg$",
        r"\.egg-info$",
        r"dist$",
        r"build$",
        # Exclude this script itself
        r"scripts/check_forbidden_tokens\.py$",
        # Exclude pre-commit config that mentions the tokens it's checking
        r"\.pre-commit-config\.yaml$",
        # Exclude test files that might legitimately test for these tokens
        r"test.*forbidden.*token",
    ]

    if args.exclude:
        exclude_patterns.extend(args.exclude)

    if args.verbose:
        print(f"Searching directory: {args.directory}")
        print(f"Forbidden tokens: {args.tokens}")
        print(f"Exclude patterns: {exclude_patterns}")
        print()

    results = find_forbidden_tokens(args.directory, args.tokens, exclude_patterns)

    if results:
        print("❌ Forbidden tokens found:")
        print()

        for file_path, matches in results.items():
            print(f"📁 {file_path}")
            for line_num, line_content in matches:
                print(f"   Line {line_num}: {line_content}")
            print()

        print(f"Found forbidden tokens in {len(results)} files.")
        print("Please remove or replace these tokens with 'Entity' terminology.")
        sys.exit(1)
    else:
        print("✅ No forbidden tokens found.")
        sys.exit(0)


if __name__ == "__main__":
    main()
