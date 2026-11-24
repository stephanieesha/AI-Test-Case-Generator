"""
Tests for the Jira connection: how settings are checked, how requests are
built, how Jira's answers become readable messages, and how the routes use
only the settings the visitor sends. No test reaches Atlassian.
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
import jira_client
from jira_client import JiraClient, JiraError, normalize_issue_key, normalize_site

VISITOR = {"site": "mysite", "email": "me@example.com", "api_token": "tok-123"}
ISSUE = {"fields": {"summary": "Login", "description": "Users sign in."}}


class FakeResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = {} if body is None else body

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._body


class JiraStub:
    def __init__(self):
        self.calls = []
        self.response = FakeResponse(200, ISSUE)
        self.error = None

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture
def jira(monkeypatch):
    stub = JiraStub()
    monkeypatch.setattr(jira_client.requests, "get", stub.get)
    return stub


@pytest.fixture
def client(monkeypatch):
    monkeypatch.delenv("DISABLE_JIRA", raising=False)
    return app_module.app.test_client()


# --- Checking what the visitor typed -------------------------------------

@pytest.mark.parametrize("raw, expected", [
    ("mysite", "mysite"),
    ("  MySite  ", "mysite"),
    ("mysite.atlassian.net", "mysite"),
    ("https://mysite.atlassian.net/", "mysite"),
    ("https://mysite.atlassian.net/jira/software", "mysite"),
    ("my-site-2", "my-site-2"),
])
def test_site_accepts_the_common_ways_people_write_it(raw, expected):
    assert normalize_site(raw) == expected


@pytest.mark.parametrize("raw", ["", "evil.com", "mysite.example.com", "https://evil.com/x", "-mysite", "my_site", "my site"])
def test_site_rejects_anything_that_is_not_an_atlassian_site_name(raw):
    with pytest.raises(JiraError):
        normalize_site(raw)


def test_issue_key_is_uppercased_and_checked():
    assert normalize_issue_key(" tcg-4 ") == "TCG-4"
    assert normalize_issue_key("AB_1-20") == "AB_1-20"


@pytest.mark.parametrize("raw", ["", "TCG", "4-TCG", "TCG-4/../x", "TCG-4?expand=x", "../secret"])
def test_issue_key_rejects_anything_that_is_not_a_key(raw):
    with pytest.raises(JiraError):
        normalize_issue_key(raw)


def test_a_client_needs_an_email_and_a_token():
    with pytest.raises(JiraError, match="email and API token"):
        JiraClient("mysite", "", "tok")
    with pytest.raises(JiraError, match="email and API token"):
        JiraClient("mysite", "me@example.com", "   ")


# --- Checking the login ---------------------------------------------------

def test_check_login_calls_myself_with_the_visitors_credentials(jira):
    jira.response = FakeResponse(200, {"displayName": "Test User"})
    name = JiraClient("MySite.atlassian.net", "me@example.com", "tok-123").check_login()
    url, kwargs = jira.calls[0]
    assert url == "https://mysite.atlassian.net/rest/api/2/myself"
    assert kwargs["auth"].username == "me@example.com"
    assert kwargs["auth"].password == "tok-123"
    assert kwargs["timeout"] == jira_client.REQUEST_TIMEOUT_SECONDS
    assert name == "Test User"


def test_check_login_without_a_display_name_still_gives_a_name(jira):
    jira.response = FakeResponse(200, {})
    assert JiraClient("mysite", "me@example.com", "tok").check_login() == "your Jira account"


@pytest.mark.parametrize("status, expected", [
    (401, "Jira rejected the email or API token."),
    (403, "Jira refused this account. Check the email and API token."),
    (404, "No Jira site found at mysite.atlassian.net. Check the site name."),
    (500, "Jira returned an error (500). Try again later."),
])
def test_check_login_reports_each_status_plainly(jira, status, expected):
    jira.response = FakeResponse(status, {})
    with pytest.raises(JiraError) as err:
        JiraClient("mysite", "me@example.com", "tok").check_login()
    assert str(err.value) == expected


# --- Talking to Jira ------------------------------------------------------

def test_get_issue_calls_the_visitors_site_with_their_own_credentials(jira):
    issue = JiraClient("MySite.atlassian.net", "me@example.com", "tok-123").get_issue("tcg-4")
    url, kwargs = jira.calls[0]
    assert url == "https://mysite.atlassian.net/rest/api/2/issue/TCG-4"
    assert kwargs["auth"].username == "me@example.com"
    assert kwargs["auth"].password == "tok-123"
    assert kwargs["timeout"] == jira_client.REQUEST_TIMEOUT_SECONDS
    assert issue == {"key": "TCG-4", "summary": "Login", "description": "Users sign in."}


def test_a_missing_description_becomes_empty_text(jira):
    jira.response = FakeResponse(200, {"fields": {"summary": "Only a title", "description": None}})
    issue = JiraClient("mysite", "me@example.com", "tok").get_issue("TCG-4")
    assert issue["description"] == ""


@pytest.mark.parametrize("status, expected", [
    (401, "Jira rejected the email or API token."),
    (403, "This Jira account cannot read TCG-4."),
    (404, "No ticket TCG-4 on mysite.atlassian.net. Check the key and site name."),
    (500, "Jira returned an error (500). Try again later."),
])
def test_jira_error_statuses_get_plain_messages(jira, status, expected):
    jira.response = FakeResponse(status, {})
    with pytest.raises(JiraError) as err:
        JiraClient("mysite", "me@example.com", "tok").get_issue("TCG-4")
    assert str(err.value) == expected


def test_network_failures_say_what_to_check(jira):
    client = JiraClient("mysite", "me@example.com", "tok")
    jira.error = requests.ConnectionError("no route")
    with pytest.raises(JiraError, match="Could not reach mysite.atlassian.net"):
        client.get_issue("TCG-4")
    jira.error = requests.Timeout("slow")
    with pytest.raises(JiraError, match="took too long"):
        client.get_issue("TCG-4")


def test_the_token_never_appears_in_an_error(jira):
    jira.error = requests.ConnectionError("failed for secret-token-xyz")
    with pytest.raises(JiraError) as err:
        JiraClient("mysite", "me@example.com", "secret-token-xyz").get_issue("TCG-4")
    assert "secret-token-xyz" not in str(err.value)


def test_an_unreadable_response_is_reported_not_crashed_on(jira):
    class NotJson(FakeResponse):
        def json(self):
            raise ValueError("not json")

    jira.response = NotJson(200)
    with pytest.raises(JiraError, match="could not read"):
        JiraClient("mysite", "me@example.com", "tok").get_issue("TCG-4")


def test_a_response_that_is_not_an_object_is_reported(jira):
    jira.response = FakeResponse(200, ["not", "an", "object"])
    with pytest.raises(JiraError, match="could not read"):
        JiraClient("mysite", "me@example.com", "tok").check_login()


# --- The routes -----------------------------------------------------------

def test_the_routes_are_post_only_so_settings_never_travel_in_a_url(client):
    assert client.get("/jira/TCG-4").status_code == 405
    assert client.get("/jira/check").status_code == 405


def test_the_routes_ignore_the_owners_environment_variables(client, monkeypatch, jira):
    monkeypatch.setenv("JIRA_API_TOKEN", "owner-secret")
    monkeypatch.setenv("JIRA_EMAIL", "owner@example.com")
    monkeypatch.setenv("JIRA_DOMAIN", "owner")
    assert client.post("/jira/TCG-4", json={}).status_code == 400
    assert client.post("/jira/check", json={}).status_code == 400
    assert jira.calls == []


def test_fetching_needs_the_visitors_email_and_token(client, jira):
    response = client.post("/jira/TCG-4", json={"site": "mysite", "email": "", "api_token": ""})
    assert response.status_code == 400
    assert response.get_json()["error"] == "Enter your Jira email and API token."
    assert jira.calls == []


def test_check_returns_the_name_for_valid_settings(client, jira):
    jira.response = FakeResponse(200, {"displayName": "Test User"})
    response = client.post("/jira/check", json=VISITOR)
    assert response.status_code == 200
    assert response.get_json() == {"name": "Test User"}
    url, _ = jira.calls[0]
    assert url == "https://mysite.atlassian.net/rest/api/2/myself"


def test_check_reports_a_bad_token_without_echoing_it(client, jira):
    jira.response = FakeResponse(401, {})
    response = client.post("/jira/check", json=VISITOR)
    assert response.status_code == 400
    assert response.get_json()["error"] == "Jira rejected the email or API token."
    assert "tok-123" not in response.get_data(as_text=True)


def test_check_rejects_a_bad_site_before_contacting_jira(client, jira):
    response = client.post("/jira/check", json={**VISITOR, "site": "evil.com"})
    assert response.status_code == 400
    assert jira.calls == []


@pytest.mark.parametrize("body", [{}, ["not", "an", "object"], {"site": 123, "email": ["x"], "api_token": None}])
def test_check_treats_missing_or_non_text_settings_as_a_client_error(client, jira, body):
    assert client.post("/jira/check", json=body).status_code == 400
    assert jira.calls == []


def test_check_is_switched_off_by_the_same_setting(client, monkeypatch, jira):
    monkeypatch.setenv("DISABLE_JIRA", "true")
    response = client.post("/jira/check", json=VISITOR)
    assert response.status_code == 403
    assert "turned off" in response.get_json()["error"]
    assert jira.calls == []


def test_fetch_is_switched_off_by_the_same_setting(client, monkeypatch, jira):
    monkeypatch.setenv("DISABLE_JIRA", "true")
    assert client.post("/jira/TCG-4", json=VISITOR).status_code == 403
    assert jira.calls == []


def test_the_fetch_route_uses_the_settings_the_visitor_sent(client, jira):
    response = client.post("/jira/tcg-4", json=VISITOR)
    assert response.status_code == 200
    assert response.get_json() == {"requirement": "Login\n\nUsers sign in.", "key": "TCG-4"}
    url, _ = jira.calls[0]
    assert url == "https://mysite.atlassian.net/rest/api/2/issue/TCG-4"


def test_the_fetch_route_returns_a_readable_error_and_never_the_token(client, jira):
    jira.error = requests.ConnectionError("no route")
    response = client.post("/jira/TCG-4", json=VISITOR)
    assert response.status_code == 400
    assert "Could not reach mysite.atlassian.net" in response.get_json()["error"]
    assert "tok-123" not in response.get_data(as_text=True)


def test_unexpected_failures_return_a_generic_message(client, monkeypatch):
    def broken(url, **kwargs):
        raise RuntimeError("internal detail tok-123")

    monkeypatch.setattr(jira_client.requests, "get", broken)
    for path in ("/jira/check", "/jira/TCG-4"):
        response = client.post(path, json=VISITOR)
        assert response.status_code == 500
        body = response.get_data(as_text=True)
        assert "internal detail" not in body
        assert "tok-123" not in body
