"""
Local web UI for the test case generator. Paste a requirement directly, or
pull one straight from a Jira ticket by its key - removing the copy/paste
step between Jira and this tool. Read-only: nothing is ever written back
to Jira.

Run with: python src/app.py
Then open: http://localhost:5001
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, jsonify, render_template, request

from e2e_tools import E2E_TOOLS
from generator import STYLES, TestCaseGenerator
from limits import check_generation_allowed, client_ip, max_requirement_chars
from jira_client import JiraClient, JiraError

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


@app.after_request
def keep_out_of_search_engines(response):
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@app.route("/robots.txt")
def robots():
    return "User-agent: *\nDisallow: /\n", 200, {"Content-Type": "text/plain"}


@app.route("/")
def index():
    return render_template("index.html", e2e_tools=E2E_TOOLS)


JIRA_SWITCHED_OFF_MESSAGE = "Jira lookup is turned off on this public copy of the app - paste the requirement instead"


def _jira_switched_off() -> bool:
    # Kill switch for the whole Jira lookup. Off unless DISABLE_JIRA=true is set.
    return os.environ.get("DISABLE_JIRA", "").lower() == "true"


def _text_field(data: dict, name: str) -> str:
    value = data.get(name)
    return value if isinstance(value, str) else ""


def _jira_client_from_request() -> JiraClient:
    # The site, email and API token come from the visitor's own settings in
    # the page. Nothing is read from environment variables, so the owner's
    # Jira account is never used for someone else's request.
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    return JiraClient(
        site=_text_field(data, "site"),
        email=_text_field(data, "email"),
        api_token=_text_field(data, "api_token"),
    )


@app.route("/jira/check", methods=["POST"])
def check_jira_login():
    if _jira_switched_off():
        return jsonify({"error": JIRA_SWITCHED_OFF_MESSAGE}), 403
    try:
        name = _jira_client_from_request().check_login()
    except JiraError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        # Keep internal details, and anything secret, out of the response.
        app.logger.exception("Jira login check failed")
        return jsonify({"error": "Something went wrong while contacting Jira. Try again."}), 500
    return jsonify({"name": name})


@app.route("/jira/<issue_key>", methods=["POST"])
def fetch_jira_issue(issue_key):
    if _jira_switched_off():
        return jsonify({"error": JIRA_SWITCHED_OFF_MESSAGE}), 403
    try:
        issue = _jira_client_from_request().get_issue(issue_key)
    except JiraError as e:
        return jsonify({"error": str(e)}), 400
    except Exception:
        # Keep internal details, and anything secret, out of the response.
        app.logger.exception("Jira lookup failed")
        return jsonify({"error": "Something went wrong while contacting Jira. Try again."}), 500

    requirement_text = f"{issue['summary']}\n\n{issue['description']}".strip()
    return jsonify({"requirement": requirement_text, "key": issue["key"]})


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json() or {}
    requirement = data.get("requirement", "").strip()
    style = data.get("style", "bdd")

    if not requirement:
        return jsonify({"error": "Requirement text is empty"}), 400
    if style not in STYLES:
        return jsonify({"error": f"Unknown style '{style}'. Must be one of: {list(STYLES.keys())}"}), 400
    if max_requirement_chars() and len(requirement) > max_requirement_chars():
        return jsonify({"error": f"The requirement is too long (the limit is {max_requirement_chars()} characters)"}), 400

    blocked = check_generation_allowed(client_ip(request))
    if blocked:
        return jsonify({"error": blocked}), 429

    try:
        result = generator.generate(requirement, style=style)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    log_run(requirement, result)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=int(os.environ.get("PORT", "5001")))
