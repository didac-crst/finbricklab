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
                "kind": "a.property",
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
                "kind": "l.loan.annuity",
                "links": {"principal": {"from_house": "house"}},
                "spec": {"rate_pa": 0.034, "term_months": 300},
            },
            {
                "id": "rental_prop",
                "name": "Rental Property",
                "kind": "a.property",
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
                "kind": "l.loan.annuity",
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


def cmd_journal_diagnostics(args) -> int:
    """Show journal diagnostics for a scenario."""
    try:
        cfg = _load_json(args.input)

        # Create scenario using from_dict method
        scn = Scenario.from_dict(cfg)

        # Run simulation
        start_date = date.fromisoformat(args.start)
        selection = args.select if args.select else None
        res = scn.run(start=start_date, months=args.months, selection=selection)

        journal = res.get("journal")
        if journal is None:
            print("Error: Journal not available in results", file=sys.stderr)
            return 1

        # Get scenario results
        views = res.get("views")
        if views is None:
            print("Error: ScenarioResults not available", file=sys.stderr)
            return 1

        # Get registry and account registry
        registry = scn._registry
        account_registry = journal.account_registry
        if account_registry is None:
            print("Error: AccountRegistry not available in journal", file=sys.stderr)
            return 1

        # Parse transfer visibility
        from finbricklab.core.transfer_visibility import TransferVisibility

        transfer_visibility = TransferVisibility[args.transfer_visibility.upper()]

        # Expand selection if needed (for MacroGroups) - same logic as aggregation
        selection_set: set[str] = set()
        if selection:
            for node_id in selection:
                # Check if it's a MacroGroup
                if registry and registry.is_macrobrick(node_id):
                    # Expand MacroGroup to A/L nodes
                    macrobrick = registry.get_macrobrick(node_id)
                    members = macrobrick.expand_member_bricks(registry)
                    # Convert brick IDs to node IDs
                    for brick_id in members:
                        brick = registry.get_brick(brick_id)
                        if hasattr(brick, "family"):
                            if brick.family == "a":
                                selection_set.add(f"a:{brick_id}")
                            elif brick.family == "l":
                                selection_set.add(f"l:{brick_id}")
                else:
                    # Direct node ID or brick ID
                    # Try to convert brick ID to node ID
                    brick = registry.get_brick(node_id) if registry else None
                    if brick and hasattr(brick, "family"):
                        selection_set.add(f"{brick.family}:{brick_id}")
                    else:
                        # Assume it's already a node ID
                        selection_set.add(node_id)

        # Filter entries by month if specified
        from datetime import datetime

        entries_to_analyze = journal.entries
        if args.month:
            month_str = args.month  # Expected format: YYYY-MM
            entries_to_analyze = []
            for entry in journal.entries:
                # Normalize timestamp to month
                if isinstance(entry.timestamp, datetime):
                    entry_month = entry.timestamp.strftime("%Y-%m")
                else:
                    # Handle numpy datetime64
                    entry_month = str(entry.timestamp)[:7]  # YYYY-MM
                if entry_month == month_str:
                    entries_to_analyze.append(entry)

        # Calculate diagnostics using same logic as aggregation
        from finbricklab.core.accounts import (
            BOUNDARY_NODE_ID,
            AccountScope,
            AccountType,
            get_node_scope,
            get_node_type,
        )
        from finbricklab.core.transfer_visibility import touches_boundary

        total_entries = len(entries_to_analyze)
        boundary_entries = []
        internal_transfer_entries = []
        transfer_entries = []
        cancelled_entries = []
        boundary_by_category: dict[str, float] = {}
        transfer_total = 0.0

        for entry in entries_to_analyze:
            # Check if entry touches boundary
            touches_bound = touches_boundary(entry, account_registry)

            # Check if this is a transfer entry
            is_transfer_entry = entry.metadata.get("transaction_type") in {
                "transfer",
                "tbrick",
                "maturity_transfer",
            }

            # Check if both postings are INTERNAL and in selection (cancellation logic)
            both_internal_in_selection = False
            if not touches_bound and selection_set:
                both_internal = True
                both_in_selection = True
                for posting in entry.postings:
                    node_id = posting.metadata.get("node_id")
                    scope = get_node_scope(node_id, account_registry)
                    if scope != AccountScope.INTERNAL:
                        both_internal = False
                        break
                    if node_id not in selection_set:
                        both_in_selection = False
                if both_internal and both_in_selection:
                    both_internal_in_selection = True
                    cancelled_entries.append(entry)

            # Apply TransferVisibility filtering (same logic as aggregation)
            should_include = True
            if transfer_visibility != TransferVisibility.ALL:
                if transfer_visibility == TransferVisibility.OFF:
                    # Hide internal transfers only
                    if is_transfer_entry and both_internal_in_selection:
                        should_include = False
                elif transfer_visibility == TransferVisibility.ONLY:
                    # Show only transfer entries
                    if not is_transfer_entry:
                        should_include = False
                elif transfer_visibility == TransferVisibility.BOUNDARY_ONLY:
                    # Show only boundary-crossing transfers (not internal transfers)
                    if is_transfer_entry and not touches_bound:
                        should_include = False
                    if not is_transfer_entry and not touches_bound:
                        should_include = False

            if not should_include:
                continue

            # Categorize entry
            if touches_bound:
                boundary_entries.append(entry)
                # Sum boundary amounts by category
                for posting in entry.postings:
                    node_id = posting.metadata.get("node_id")
                    if node_id == BOUNDARY_NODE_ID:
                        category = posting.metadata.get("category", "unknown")
                        amount = abs(float(posting.amount.value))
                        boundary_by_category[category] = (
                            boundary_by_category.get(category, 0.0) + amount
                        )
            elif is_transfer_entry:
                transfer_entries.append(entry)
                # Sum transfer amounts
                for posting in entry.postings:
                    transfer_total += abs(float(posting.amount.value))
                if not touches_bound and selection_set:
                    # Check if it's an internal transfer
                    all_internal = True
                    for posting in entry.postings:
                        node_id = posting.metadata.get("node_id")
                        scope = get_node_scope(node_id, account_registry)
                        if scope != AccountScope.INTERNAL:
                            all_internal = False
                            break
                    if all_internal:
                        internal_transfer_entries.append(entry)

        # Calculate totals
        boundary_total = sum(boundary_by_category.values())
        cancelled_count = len(cancelled_entries)

        # Get sample entries (top N by timestamp)
        sample_entries = []
        if args.sample > 0:
            # Sort entries by timestamp and take top N
            sorted_entries = sorted(
                entries_to_analyze, key=lambda e: e.timestamp, reverse=True
            )[: args.sample]
            sample_entries = [
                {
                    "id": e.id,
                    "timestamp": str(e.timestamp),
                    "transaction_type": e.metadata.get("transaction_type", "unknown"),
                    "postings": [
                        {
                            "account_id": p.account_id,
                            "node_id": p.metadata.get("node_id", ""),
                            "category": p.metadata.get("category", ""),
                            "amount": float(p.amount.value),
                            "currency": p.amount.currency.code,
                        }
                        for p in e.postings
                    ],
                }
                for e in sorted_entries
            ]

        if args.json:
            # JSON output
            output = {
                "total_entries": total_entries,
                "boundary_entries": len(boundary_entries),
                "internal_transfer_entries": len(internal_transfer_entries),
                "transfer_entries": len(transfer_entries),
                "boundary_total": boundary_total,
                "transfer_total": transfer_total,
                "cancelled_entries": cancelled_count,
                "boundary_by_category": boundary_by_category,
                "sample_entries": sample_entries,
            }
            if args.month:
                output["month"] = args.month
            if selection:
                output["selection"] = list(selection_set) if selection_set else selection
            output["transfer_visibility"] = transfer_visibility.value
            json.dump(output, sys.stdout, indent=2)
            sys.stdout.write("\n")
        else:
            # Human-readable output
            print("Journal Diagnostics")
            print("=" * 50)
            if args.month:
                print(f"Month filter: {args.month}")
            if selection:
                print(f"Selection: {', '.join(selection)}")
                if selection_set:
                    print(f"  Expanded to: {', '.join(sorted(selection_set))}")
            print(f"Transfer visibility: {transfer_visibility.value}")
            print()
            print(f"Total entries: {total_entries}")
            print(f"  Boundary entries: {len(boundary_entries)} (Σ={boundary_total:,.2f})")
            print(f"  Transfer entries: {len(transfer_entries)} (Σ={transfer_total:,.2f})")
            print(f"    Internal transfers: {len(internal_transfer_entries)}")
            if cancelled_count > 0:
                print(f"  Cancelled entries: {cancelled_count} (internal transfers in selection)")
            print()

            # Show boundary totals by category
            if boundary_by_category:
                print("Boundary totals by category:")
                for category, total in sorted(boundary_by_category.items()):
                    print(f"  {category}: {total:,.2f}")
                print()

            # Show sample entries
            if sample_entries:
                print(f"Sample entries (top {args.sample}):")
                for entry in sample_entries:
                    print(f"  {entry['id']} @ {entry['timestamp']}")
                    print(f"    Type: {entry['transaction_type']}")
                    for posting in entry["postings"]:
                        node_id = posting["node_id"] or posting["account_id"]
                        category_str = f" [{posting['category']}]" if posting["category"] else ""
                        print(
                            f"    {posting['account_id']} ({node_id}){category_str}: "
                            f"{posting['amount']:,.2f} {posting['currency']}"
                        )
                    print()

        return 0

    except Exception as e:
        print(f"Error running journal diagnostics: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
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
    run_parser.add_argument(
        "--transfer-visibility",
        choices=["OFF", "ONLY", "BOUNDARY_ONLY", "ALL"],
        default="BOUNDARY_ONLY",
        help="Transfer visibility setting (default: BOUNDARY_ONLY)",
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

    # Journal diagnostics command
    journal_parser = subparsers.add_parser(
        "journal-diagnostics", help="Show journal diagnostics for a scenario"
    )
    journal_parser.add_argument(
        "-i", "--input", required=True, help="Input scenario JSON file"
    )
    journal_parser.add_argument(
        "--start", default="2026-01-01", help="Start date (YYYY-MM-DD)"
    )
    journal_parser.add_argument(
        "--months", type=int, default=12, help="Number of months to simulate"
    )
    journal_parser.add_argument(
        "--select",
        nargs="*",
        help="Select specific bricks and/or MacroBricks to analyze",
    )
    journal_parser.add_argument(
        "--transfer-visibility",
        choices=["OFF", "ONLY", "BOUNDARY_ONLY", "ALL"],
        default="BOUNDARY_ONLY",
        help="Transfer visibility setting (default: BOUNDARY_ONLY)",
    )
    journal_parser.add_argument(
        "--month", help="Filter entries by month (format: YYYY-MM, e.g., 2026-01)"
    )
    journal_parser.add_argument(
        "--sample", type=int, default=5, help="Number of sample entries to show (default: 5, 0 to disable)"
    )
    journal_parser.add_argument(
        "--json", action="store_true", help="Output in JSON format"
    )
    journal_parser.set_defaults(func=cmd_journal_diagnostics)

    # Parse arguments and execute
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
