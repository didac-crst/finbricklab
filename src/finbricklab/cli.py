"""
Command-line interface for FinBrickLab.
"""

from __future__ import annotations
import argparse
import json
import sys
from datetime import date
from finbricklab import Scenario, ABrick, LBrick, FBrick


def _load_json(path: str) -> dict:
    """Load JSON from file path."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, data: dict) -> None:
    """Save data as JSON to file path."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def cmd_example(_) -> int:
    """Print a minimal working scenario JSON."""
    example = {
        "id": "demo",
        "name": "CLI Demo",
        "bricks": [
            {
                "id": "cash",
                "name": "Cash Account",
                "kind": "a.cash",
                "spec": {"initial_balance": 1000.0, "interest_pa": 0.02}
            },
            {
                "id": "house",
                "name": "Primary Residence",
                "kind": "a.property_discrete",
                "spec": {
                    "initial_value": 400000.0,
                    "appreciation_pa": 0.03,
                    "sell_on_window_end": False
                }
            }
        ]
    }
    json.dump(example, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_run(args) -> int:
    """Run a scenario JSON and export JSON results."""
    try:
        cfg = _load_json(args.input)
        
        # Convert dict to Scenario object
        bricks = []
        for brick_cfg in cfg.get("bricks", []):
            brick_class = None
            if brick_cfg["kind"].startswith("a."):
                brick_class = ABrick
            elif brick_cfg["kind"].startswith("l."):
                brick_class = LBrick
            elif brick_cfg["kind"].startswith("f."):
                brick_class = FBrick
            else:
                print(f"Error: Unknown brick kind '{brick_cfg['kind']}'", file=sys.stderr)
                return 1
                
            bricks.append(brick_class(**brick_cfg))
        
        scn = Scenario(
            id=cfg.get("id", "scenario"),
            name=cfg.get("name", "Unnamed Scenario"),
            bricks=bricks
        )
        
        # Run simulation
        start_date = date.fromisoformat(args.start)
        res = scn.run(start=start_date, months=args.months)
        
        # Export results
        out = scn.export_run_json(res)
        _save_json(args.output, out)
        
        print(f"Scenario completed successfully. Results saved to {args.output}")
        return 0
        
    except Exception as e:
        print(f"Error running scenario: {e}", file=sys.stderr)
        return 1


def cmd_validate(args) -> int:
    """Validate a scenario JSON."""
    try:
        cfg = _load_json(args.input)
        
        # Convert dict to Scenario object (same logic as cmd_run)
        bricks = []
        for brick_cfg in cfg.get("bricks", []):
            brick_class = None
            if brick_cfg["kind"].startswith("a."):
                brick_class = ABrick
            elif brick_cfg["kind"].startswith("l."):
                brick_class = LBrick
            elif brick_cfg["kind"].startswith("f."):
                brick_class = FBrick
            else:
                print(f"Error: Unknown brick kind '{brick_cfg['kind']}'", file=sys.stderr)
                return 1
                
            bricks.append(brick_class(**brick_cfg))
        
        scn = Scenario(
            id=cfg.get("id", "scenario"),
            name=cfg.get("name", "Unnamed Scenario"),
            bricks=bricks
        )
        
        # Validate configuration
        if args.warn:
            # Just check if we can create the scenario without errors
            print("Scenario configuration appears valid (warn mode)")
        else:
            # Run a minimal validation
            scn.validate_run({}, mode="error")
            print("Scenario configuration is valid")
        
        return 0
        
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
        prog="finbrick",
        description="FinBrickLab - Financial simulation engine"
    )
    
    # Version argument
    parser.add_argument("--version", action="version", version="FinBrickLab 0.1.0")
    
    subparsers = parser.add_subparsers(dest="cmd", required=True, help="Available commands")
    
    # Example command
    example_parser = subparsers.add_parser(
        "example",
        help="Print a minimal working scenario JSON"
    )
    example_parser.set_defaults(func=cmd_example)
    
    # Run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run a scenario JSON and export JSON results"
    )
    run_parser.add_argument("-i", "--input", required=True, help="Input scenario JSON file")
    run_parser.add_argument("-o", "--output", required=True, help="Output results JSON file")
    run_parser.add_argument("--start", default="2026-01-01", help="Start date (YYYY-MM-DD)")
    run_parser.add_argument("--months", type=int, default=12, help="Number of months to simulate")
    run_parser.set_defaults(func=cmd_run)
    
    # Validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a scenario JSON"
    )
    validate_parser.add_argument("-i", "--input", required=True, help="Input scenario JSON file")
    validate_parser.add_argument("--warn", action="store_true", help="Warn instead of error on issues")
    validate_parser.set_defaults(func=cmd_validate)
    
    # Parse arguments and execute
    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
