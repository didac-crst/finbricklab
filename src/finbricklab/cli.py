"""
Command-line interface for FinBrickLab.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from finbricklab import Scenario


def _load_json(path: str) -> dict:
    """Load JSON from file path."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class NumpyEncoder(json.JSONEncoder):
    """JSON encoder that handles numpy arrays, datetime64, pandas DataFrames, and ScenarioResults."""

    def default(self, obj):
        import numpy as np
        import pandas as pd

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, np.datetime64):
            return str(obj)
        elif isinstance(obj, pd.DataFrame):
            return obj.to_dict("records")
        elif isinstance(obj, pd.Series):
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):
            # Handle custom objects by converting to dict
            return obj.__dict__
        return super().default(obj)


def _save_json(path: str, data: dict) -> None:
    """Save data as JSON to file path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, cls=NumpyEncoder)


def _print_execution_summary(res: dict, selection: list[str] = None) -> None:
    """Print execution summary to stdout."""
    meta = res.get("meta", {})
    execution_order = meta.get("execution_order", [])
    overlaps = meta.get("overlaps", {})

    # Count bricks and MacroBricks in selection
    brick_count = len(execution_order)
    macrobrick_count = 0
    if selection:
        macrobrick_count = sum(
            1 for sel_id in selection if sel_id in res.get("by_struct", {})
        )

    # Build summary message
    summary_parts = [f"Executing {brick_count} bricks"]
    if macrobrick_count > 0:
        summary_parts.append(f"(deduped) from {macrobrick_count} MacroBricks")

    if selection:
        summary_parts.append(f"[{','.join(selection)}]")

    if overlaps:
        overlap_bricks = list(overlaps.keys())
        summary_parts.append(f"; overlaps: {','.join(overlap_bricks)}")

    print(" ".join(summary_parts))


def cmd_list_macrobricks(args) -> int:
    """List MacroBricks with their flat member lists and overlaps."""
    try:
        cfg = _load_json(args.input)
        scn = Scenario.from_dict(cfg)

        if args.json:
            # JSON output
            output = {}
            for struct_id, _macrobrick in scn._registry.iter_macrobricks():
                members = list(scn._registry.get_struct_flat_members(struct_id))
                output[struct_id] = {
                    "name": _macrobrick.name,
                    "members": members,
                    "tags": _macrobrick.tags,
                }

            # Add overlaps info
            overlaps = {}
            for struct_id, _macrobrick in scn._registry.iter_macrobricks():
                members = scn._registry.get_struct_flat_members(struct_id)
                for brick_id in members:
                    # Find which other MacroBricks contain this brick
                    other_owners = []
                    for other_id, _other_mb in scn._registry.iter_macrobricks():
                        if (
                            other_id != struct_id
                            and brick_id
                            in scn._registry.get_struct_flat_members(other_id)
                        ):
                            other_owners.append(other_id)
                    if other_owners:
                        overlaps[brick_id] = sorted(other_owners)

            if overlaps:
                output["_overlaps"] = overlaps

            json.dump(output, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            # Human-readable output
            for struct_id, _macrobrick in scn._registry.iter_macrobricks():
                members = list(scn._registry.get_struct_flat_members(struct_id))
                print(f"{struct_id}: {_macrobrick.name}")
                print(f"  Members: {', '.join(members)}")
                if _macrobrick.tags:
                    print(f"  Tags: {', '.join(_macrobrick.tags)}")
                print()

            # Show overlaps
            overlaps = {}
            for struct_id, _macrobrick in scn._registry.iter_macrobricks():
                members = scn._registry.get_struct_flat_members(struct_id)
                for brick_id in members:
                    other_owners = []
                    for other_id, _other_mb in scn._registry.iter_macrobricks():
                        if (
                            other_id != struct_id
                            and brick_id
                            in scn._registry.get_struct_flat_members(other_id)
                        ):
                            other_owners.append(other_id)
                    if other_owners:
                        overlaps[brick_id] = sorted(other_owners)

            if overlaps:
                print("Overlaps:")
                for brick_id, owners in overlaps.items():
                    print(f"  {brick_id}*: {', '.join(owners)}")

        return 0

    except Exception as e:
        print(f"Error listing MacroBricks: {e}", file=sys.stderr)
        return 1


def cmd_example(_) -> int:
    """Print a minimal working scenario JSON with MacroBricks."""
    example = {
        "id": "demo",
        "name": "CLI Demo with MacroBricks",
        "bricks": [
            {
                "id": "cash",
                "name": "Main Cash Account",
                "kind": "a.cash",
                "spec": {"initial_balance": 10000.0, "interest_pa": 0.02},
            },
            {
                "id": "house",
                "name": "Primary Residence",
                "kind": "a.property_discrete",
                "spec": {
                    "initial_value": 400000.0,
                    "fees_pct": 0.05,
                    "appreciation_pa": 0.03,
                    "sell_on_window_end": False,
                },
            },
            {
                "id": "mortgage",
                "name": "Home Loan",
                "kind": "l.mortgage.annuity",
                "links": {"principal": {"from_house": "house"}},
                "spec": {"rate_pa": 0.034, "term_months": 300},
            },
            {
                "id": "rental_prop",
                "name": "Rental Property",
                "kind": "a.property_discrete",
                "spec": {
                    "initial_value": 250000.0,
                    "fees_pct": 0.05,
                    "appreciation_pa": 0.025,
                    "sell_on_window_end": False,
                },
            },
            {
                "id": "rental_mortgage",
                "name": "Rental Property Loan",
                "kind": "l.mortgage.annuity",
                "links": {"principal": {"from_house": "rental_prop"}},
                "spec": {"rate_pa": 0.038, "term_months": 240},
            },
        ],
        "structs": [
            {
                "id": "primary_residence",
                "name": "Primary Residence Package",
                "members": ["house", "mortgage"],
                "tags": ["primary", "residence"],
            },
            {
                "id": "rental_investment",
                "name": "Rental Investment",
                "members": ["rental_prop", "rental_mortgage"],
                "tags": ["rental", "investment"],
            },
        ],
    }
    json.dump(example, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_run(args) -> int:
    """Run a scenario JSON and export JSON results."""
    try:
        cfg = _load_json(args.input)

        # Create scenario using from_dict method
        scn = Scenario.from_dict(cfg)

        # Run simulation
        start_date = date.fromisoformat(args.start)
        selection = args.select if args.select else None
        res = scn.run(start=start_date, months=args.months, selection=selection)

        # Print execution summary
        _print_execution_summary(res, selection)

        # Export results
        _save_json(args.output, res)

        print(f"Results saved to {args.output}")
        return 0

    except Exception as e:
        print(f"Error running scenario: {e}", file=sys.stderr)
        return 1


def cmd_validate(args) -> int:
    """Validate a scenario JSON."""
    try:
        cfg = _load_json(args.input)

        # Create scenario using from_dict method
        scn = Scenario.from_dict(cfg)

        # Validate configuration
        try:
            # Get validation report from registry
            report = scn._registry.validate()

            if args.format == "json":
                # JSON output
                json.dump(report.to_dict(), sys.stdout, indent=2)
                sys.stdout.write("\n")
            else:
                # Human-readable output
                print(str(report))

            return report.get_exit_code()

        except Exception as e:
            if args.format == "json":
                error_report = {
                    "has_errors": True,
                    "has_warnings": False,
                    "is_valid": False,
                    "exit_code": 1,
                    "error": str(e),
                }
                json.dump(error_report, sys.stdout, indent=2)
                sys.stdout.write("\n")
            else:
                print(f"❌ Validation failed: {e}")
            return 1

    except Exception as e:
        if args.warn:
            print(f"Warning: {e}")
            return 0
        else:
            print(f"Validation failed: {e}", file=sys.stderr)
            return 1


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="finbrick", description="FinBrickLab - Financial simulation engine"
    )

    # Version argument
    parser.add_argument("--version", action="version", version="FinBrickLab 0.1.0")

    subparsers = parser.add_subparsers(
        dest="cmd", required=True, help="Available commands"
    )

    # Example command
    example_parser = subparsers.add_parser(
        "example", help="Print a minimal working scenario JSON"
    )
    example_parser.set_defaults(func=cmd_example)

    # Run command
    run_parser = subparsers.add_parser(
        "run", help="Run a scenario JSON and export JSON results"
    )
    run_parser.add_argument(
        "-i", "--input", required=True, help="Input scenario JSON file"
    )
    run_parser.add_argument(
        "-o", "--output", required=True, help="Output results JSON file"
    )
    run_parser.add_argument(
        "--start", default="2026-01-01", help="Start date (YYYY-MM-DD)"
    )
    run_parser.add_argument(
        "--months", type=int, default=12, help="Number of months to simulate"
    )
    run_parser.add_argument(
        "--select",
        nargs="*",
        help="Select specific bricks and/or MacroBricks to execute",
    )
    run_parser.epilog = """
Aggregation Semantics:
  • Per-MacroBrick view: sums all executed member bricks of that MacroBrick
  • Portfolio totals: sum unique bricks from selection (union)
  • Summing multiple MacroBrick rows can overstate due to overlap → use portfolio total
  • Execution order: topological sort by dependencies, fallback to stable ID sort
  • Overlaps: reported in results.meta["overlaps"] for current selection
    """
    run_parser.set_defaults(func=cmd_run)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a scenario JSON")
    validate_parser.add_argument(
        "-i", "--input", required=True, help="Input scenario JSON file"
    )
    validate_parser.add_argument(
        "--warn", action="store_true", help="Warn instead of error on issues"
    )
    validate_parser.add_argument(
        "--format", choices=["human", "json"], default="human", help="Output format"
    )
    validate_parser.set_defaults(func=cmd_validate)

    # List MacroBricks command
    list_parser = subparsers.add_parser(
        "list-macrobricks", help="List MacroBricks with their members and overlaps"
    )
    list_parser.add_argument(
        "-i", "--input", required=True, help="Input scenario JSON file"
    )
    list_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    list_parser.set_defaults(func=cmd_list_macrobricks)

    # Parse arguments and execute
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
