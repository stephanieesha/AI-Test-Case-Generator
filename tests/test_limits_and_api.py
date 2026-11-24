import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
import limits

CANNED = {
    "style": "bdd",
    "test_cases": [{"title": "T", "steps": ["Given x", "When y", "Then z"]}],
    "ambiguity_notes": [],
    "retrieved_examples": ["corpus-001"],
}


@pytest.fixture
def client(monkeypatch, tmp_path):
    limits.reset()
    calls = []

    def fake_generate(requirement, style="bdd", top_k=2):
        calls.append((requirement, style))
        return dict(CANNED)

    monkeypatch.setattr(app_module.generator, "generate", fake_generate)
    monkeypatch.setattr(app_module, "LOG_PATH", tmp_path / "log.jsonl")
    test_client = app_module.app.test_client()
    test_client.calls = calls
    yield test_client
    limits.reset()


def post(client, **body):
    return client.post("/generate", json={"requirement": "As a user I want x", **body})


def test_generates_and_returns_the_result(client):
    response = post(client)
    assert response.status_code == 200
    assert response.get_json()["test_cases"][0]["title"] == "T"


def test_empty_requirement_is_rejected_without_calling_the_model(client):
    assert client.post("/generate", json={"requirement": "   "}).status_code == 400
    assert client.calls == []


def test_unknown_style_is_a_client_error_not_a_server_error(client):
    response = post(client, style="nope")
    assert response.status_code == 400
    assert "Unknown style 'nope'" in response.get_json()["error"]
    assert client.calls == []


def test_requirement_length_can_be_capped(client, monkeypatch):
    monkeypatch.setenv("MAX_REQUIREMENT_CHARS", "10")
    response = post(client)
    assert response.status_code == 400
    assert "too long" in response.get_json()["error"]
    assert client.calls == []


def test_hourly_limit_per_visitor(client, monkeypatch):
    monkeypatch.setenv("GENERATE_LIMIT_PER_HOUR", "2")
    assert [post(client).status_code for _ in range(3)] == [200, 200, 429]
    assert len(client.calls) == 2
    other_visitor = client.post("/generate", json={"requirement": "As a user I want x"},
                                headers={"X-Forwarded-For": "203.0.113.9"})
    assert other_visitor.status_code == 200


def test_daily_limit_across_all_visitors(client, monkeypatch):
    monkeypatch.setenv("DAILY_GENERATION_LIMIT", "2")
    codes = []
    for ip in ("203.0.113.1", "203.0.113.2", "203.0.113.3"):
        codes.append(client.post("/generate", json={"requirement": "As a user I want x"},
                                 headers={"X-Forwarded-For": ip}).status_code)
    assert codes == [200, 200, 429]
    assert "daily" in post(client).get_json()["error"]


def test_rejected_requests_do_not_use_up_the_allowance(client, monkeypatch):
    monkeypatch.setenv("GENERATE_LIMIT_PER_HOUR", "1")
    client.post("/generate", json={"requirement": ""})
    post(client, style="nope")
    assert post(client).status_code == 200


def test_jira_lookup_can_be_switched_off(client, monkeypatch):
    monkeypatch.setenv("DISABLE_JIRA", "true")
    response = client.post("/jira/KAN-1", json={"site": "mysite", "email": "a@example.com", "api_token": "t"})
    assert response.status_code == 403
    assert "turned off" in response.get_json()["error"]


def test_not_indexed_by_search_engines(client):
    assert "noindex" in client.get("/").headers["X-Robots-Tag"]
    assert "Disallow: /" in client.get("/robots.txt").get_data(as_text=True)
