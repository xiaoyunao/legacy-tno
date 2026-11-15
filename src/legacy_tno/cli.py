"""Command line for profiling, pilot selection, and per-field processing."""
import argparse
from pathlib import Path
import json


def main():
    parser = argparse.ArgumentParser(prog="legacy-tno")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("inventory", "select-pilot", "run", "plot"):
        cmd = commands.add_parser(name)
        cmd.add_argument("--work", type=Path, required=True)
        if name == "inventory":
            cmd.add_argument("--quick", action="store_true")
        if name in ("select-pilot", "run"):
            cmd.add_argument("--config", type=Path, required=True)
        if name == "run":
            cmd.add_argument("--fields", type=Path, required=True)
            cmd.add_argument("--field", choices=("validation","exploration"), required=True)
            cmd.add_argument("--commit", required=True)
            cmd.add_argument("--resume", action="store_true")
            cmd.add_argument("--stop-after", choices=("catalog",))
    args = parser.parse_args()
    if args.command == "inventory":
        from .profile import main as profile
        profile(args.work, args.quick)
    if args.command == "select-pilot":
        from .select import choose
        from .pipeline import write_json
        selected = choose(args.work, json.loads(args.config.read_text()))
        write_json(args.work / "inputs" / "selected-fields.json", selected)
        print(json.dumps(selected["fields"], indent=2))
    if args.command == "run":
        from .pipeline import run
        run(args.config, args.work, args.fields, args.field, args.commit, args.resume, args.stop_after)
    if args.command == "plot":
        from .plot import plot
        plot(args.work)


if __name__ == "__main__":
    main()
