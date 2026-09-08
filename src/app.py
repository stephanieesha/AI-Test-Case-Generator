"""
Local web UI for the test case generator. Paste a requirement directly, or
pull one straight from a Jira ticket by its key - removing the copy/paste
step between Jira and this tool. Read-only: nothing is ever written back
to Jira.

Run with: python src/app.py
Then open: http://localhost:5001
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, render_template, request

from generator import TestCaseGenerator
from jira_client import JiraClient

CORPUS_DIR = Path(__file__).parent.parent / "corpus"
LOG_PATH = Path(__file__).parent.parent / "logs" / "generation_log.jsonl"

app = Flask(__name__, template_folder=str(Path(__file__).parent.parent / "templates"))
generator = TestCaseGenerator(CORPUS_DIR)


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/jira/<issue_key>")
def fetch_jira_issue(issue_key):
    try:
        client = JiraClient()
        issue = client.get_issue(issue_key)
        requirement_text = f"{issue['summary']}\n\n{issue['description']}".strip()
        return jsonify({"requirement": requirement_text, "key": issue["key"]})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json() or {}
    requirement = data.get("requirement", "").strip()
    style = data.get("style", "bdd")

    if not requirement:
        return jsonify({"error": "Requirement text is empty"}), 400

    try:
        result = generator.generate(requirement, style=style)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    log_run(requirement, result)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True, port=5001)
