"""
Command-line entry point. Takes a requirement, generates style-matched test
cases, prints them, and logs the run for traceability - the log is what lets
you later report a real metric like "X% of tickets flagged as ambiguous
before development started," instead of that being a one-off demo claim.

Usage:
    python src/cli.py --requirement "As a user, I want to filter items by price range"
    python src/cli.py --file path/to/ticket.txt --style step_by_step
"""

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from generator import TestCaseGenerator

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
LOG_PATH = Path(__file__).parent.parent / "logs" / "generation_log.jsonl"


def log_run(requirement: str, result: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "requirement": requirement,
        "style": result.get("style"),
        "num_test_cases": len(result.get("test_cases", [])),
        "num_ambiguities": len(result.get("ambiguity_notes", [])),
        "retrieved_examples": result.get("retrieved_examples", []),
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def print_result(result: dict) -> None:
    print("\n=== Generated test cases ===\n")
    for case in result.get("test_cases", []):
        print(f"- {case['title']}")

        if result.get("style") == "step_by_step":
            if case.get("preconditions"):
                print("    Preconditions:")
                for p in case["preconditions"]:
                    print(f"      - {p}")
            if case.get("test_data"):
                print("    Test data:")
                for d in case["test_data"]:
                    print(f"      - {d}")
            for step in case["steps"]:
                print(f"    {step['step_number']}. {step['action']}")
                print(f"       Expected: {step['expected_result']}")
            if case.get("postconditions"):
                print("    Postconditions:")
                for p in case["postconditions"]:
                    print(f"      - {p}")
        else:
            for step in case["steps"]:
                print(f"    {step}")
        print()

    ambiguities = result.get("ambiguity_notes", [])
    if ambiguities:
        print("=== Ambiguity flags ===\n")
        for note in ambiguities:
            print(f"- {note}")
    else:
        print("No ambiguities flagged.")

    print(f"\n(Grounded in style examples: {', '.join(result.get('retrieved_examples', []))})")


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--requirement", type=str, help="Requirement text directly")
    group.add_argument("--file", type=Path, help="Path to a file containing the requirement")
    parser.add_argument("--top-k", type=int, default=2, help="Number of style examples to retrieve")
    parser.add_argument(
        "--style",
        type=str,
        choices=["bdd", "step_by_step"],
        default="bdd",
        help="Test case format: 'bdd' (Given/When/Then) or 'step_by_step' (numbered steps with expected results)",
    )
    args = parser.parse_args()

    requirement = args.requirement or args.file.read_text(encoding="utf-8").strip()

    generator = TestCaseGenerator(CORPUS_DIR)
    result = generator.generate(requirement, style=args.style, top_k=args.top_k)

    print_result(result)
    log_run(requirement, result)


if __name__ == "__main__":
    main()
