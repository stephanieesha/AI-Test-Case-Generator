"""
Builds the "what to validate" summary from the generated test cases.

Each check comes straight from a test case's expected outcomes: the Then
steps in BDD, and the expected results in step-by-step. That needs no extra
API call, and the summary cannot drift from the test cases it summarizes.
"""


def build_validation_summary(test_cases, style: str) -> list:
    """Return one entry per test case: {"title": ..., "checks": [...]}."""
    summary = []
    for test_case in test_cases or []:
        if not isinstance(test_case, dict):
            continue
        if style == "step_by_step":
            checks = _step_by_step_checks(test_case)
        else:
            checks = _bdd_checks(test_case)
        summary.append({"title": str(test_case.get("title", "")).strip(), "checks": checks})
    return summary


def _step_by_step_checks(test_case: dict) -> list:
    checks = []
    for step in test_case.get("steps") or []:
        if isinstance(step, dict):
            expected = str(step.get("expected_result", "")).strip()
            if expected:
                checks.append(expected)
    return checks


def _bdd_checks(test_case: dict) -> list:
    """Collect each Then, plus any And or But that directly follows one."""
    checks = []
    in_outcome = False
    for step in test_case.get("steps") or []:
        text = str(step).strip()
        lowered = text.lower()
        if lowered.startswith("then "):
            in_outcome = True
            checks.append(text[len("then "):].strip())
        elif in_outcome and lowered.startswith(("and ", "but ")):
            checks.append(text[len("and "):].strip())  # "and " and "but " are the same length
        else:
            in_outcome = False
    return [check for check in checks if check]
