"""
Tests for the what-to-validate summary. It is read from the test cases the
generator returns, so these tests make no API calls.
"""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import generator as generator_module
from validation_summary import build_validation_summary

CORPUS_DIR = Path(__file__).parent.parent / "corpus"


def test_bdd_collects_each_then_and_the_ands_and_buts_that_follow_it():
    cases = [{"title": "Login", "steps": [
        "Given a registered user",
        "When they sign in",
        "Then they see the dashboard",
        "And the greeting shows their name",
        "But no admin menu",
        "Given a second user",
        "Then they are logged out",
    ]}]
    assert build_validation_summary(cases, "bdd") == [{"title": "Login", "checks": [
        "they see the dashboard",
        "the greeting shows their name",
        "no admin menu",
        "they are logged out",
    ]}]


def test_bdd_skips_empty_outcomes():
    cases = [{"title": "Empty", "steps": ["Given x", "Then ", "When y"]}]
    assert build_validation_summary(cases, "bdd") == [{"title": "Empty", "checks": []}]


def test_step_by_step_collects_expected_results_in_order():
    cases = [{"title": "Checkout", "steps": [
        {"step_number": 1, "action": "Add an item", "expected_result": "Cart shows 1 item"},
        {"step_number": 2, "action": "Pay", "expected_result": "Receipt is emailed"},
        {"step_number": 3, "action": "Wait", "expected_result": ""},
    ]}]
    assert build_validation_summary(cases, "step_by_step") == [
        {"title": "Checkout", "checks": ["Cart shows 1 item", "Receipt is emailed"]},
    ]


def test_odd_input_gives_an_empty_summary_not_an_error():
    assert build_validation_summary(None, "bdd") == []
    assert build_validation_summary([], "step_by_step") == []
    assert build_validation_summary(["not a case", None], "bdd") == []
    assert build_validation_summary([{"title": "No steps"}], "bdd") == [{"title": "No steps", "checks": []}]


def test_generate_adds_the_summary_to_the_result():
    gen = generator_module.TestCaseGenerator(CORPUS_DIR)
    reply = {
        "test_cases": [{"title": "Login", "steps": ["Given a user", "Then they see the dashboard"]}],
        "ambiguity_notes": [],
    }

    def fake_create(**kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=json.dumps(reply))])

    gen.client = SimpleNamespace(messages=SimpleNamespace(create=fake_create))
    result = gen.generate("As a user I want to log in", style="bdd")
    assert result["validation_summary"] == [{"title": "Login", "checks": ["they see the dashboard"]}]
