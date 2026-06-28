"""Command-line wrapper for the single-patient eligibility engine."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .engine import evaluate_patient


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate one patient's wound billing eligibility.")
    parser.add_argument("input_json", help="Path to a single-patient JSON payload.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    args = parser.parse_args()

    payload = json.loads(Path(args.input_json).read_text(encoding="utf-8"))
    result = evaluate_patient(payload)
    indent = 2 if args.pretty else None
    print(json.dumps(result, indent=indent, sort_keys=True))


if __name__ == "__main__":
    main()
