"""
Minimal read-only Jira Cloud client. Fetches a ticket's summary and
description so it can be fed directly into the test case generator,
removing the copy/paste step between Jira and this tool.

Read-only by design: this never writes a comment, field, or status back to
Jira. The site, email and API token come from the visitor's own settings in
the page, with each request. Nothing is read from environment variables and
nothing is stored, so the public copy of the app never uses the owner's
Jira account.
"""

import re

import requests
from requests.auth import HTTPBasicAuth

SITE_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
ISSUE_KEY_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*-[0-9]+$")
REQUEST_TIMEOUT_SECONDS = 15
UNREADABLE_RESPONSE = "Jira sent back a response this app could not read."


class JiraError(Exception):
    """A problem the visitor can fix. Its message is safe to show in the page."""


def normalize_site(value: str) -> str:
    """Accept 'mysite', 'mysite.atlassian.net' or a full URL, and return 'mysite'."""
    site = (value or "").strip().lower()
    site = re.sub(r"^https?://", "", site).split("/")[0]
    if site.endswith(".atlassian.net"):
        site = site[: -len(".atlassian.net")]
    if not SITE_PATTERN.match(site):
        raise JiraError("Enter your Jira site name, for example mysite from mysite.atlassian.net.")
    return site


def normalize_issue_key(value: str) -> str:
    key = (value or "").strip().upper()
    if not ISSUE_KEY_PATTERN.match(key):
        raise JiraError("Enter a ticket key such as PROJ-123.")
    return key


class JiraClient:
    def __init__(self, site: str, email: str, api_token: str):
        self.site = normalize_site(site)
        self.email = (email or "").strip()
        self.api_token = (api_token or "").strip()
        if not self.email or not self.api_token:
            raise JiraError("Enter your Jira email and API token.")

    def check_login(self) -> str:
        """Return the display name of the account these credentials belong to."""
        data = self._get_json(
            "/rest/api/2/myself",
            not_found=f"No Jira site found at {self.site}.atlassian.net. Check the site name.",
            forbidden="Jira refused this account. Check the email and API token.",
        )
        name = data.get("displayName")
        if isinstance(name, str) and name.strip():
            return name.strip()
        return "your Jira account"

    def get_issue(self, issue_key: str) -> dict:
        key = normalize_issue_key(issue_key)
        # Using API v2 rather than v3: v2 returns the description as a plain
        # text/wiki-markup string, while v3 returns a structured "Atlassian
        # Document Format" object. Since this text is just being fed into a
        # prompt (not rendered), the simpler v2 string is all that's needed.
        data = self._get_json(
            f"/rest/api/2/issue/{key}",
            not_found=f"No ticket {key} on {self.site}.atlassian.net. Check the key and site name.",
            forbidden=f"This Jira account cannot read {key}.",
        )
        fields = data.get("fields")
        if not isinstance(fields, dict):
            fields = {}
        return {
            "key": key,
            "summary": fields.get("summary") or "",
            "description": fields.get("description") or "",
        }

    def _get_json(self, path: str, *, not_found: str, forbidden: str) -> dict:
        try:
            response = requests.get(
                f"https://{self.site}.atlassian.net{path}",
                auth=HTTPBasicAuth(self.email, self.api_token),
                headers={"Accept": "application/json"},
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
        except requests.Timeout as e:
            raise JiraError("Jira took too long to respond. Try again.") from e
        except requests.ConnectionError as e:
            raise JiraError(f"Could not reach {self.site}.atlassian.net. Check the site name.") from e

        if response.status_code == 401:
            raise JiraError("Jira rejected the email or API token.")
        if response.status_code == 403:
            raise JiraError(forbidden)
        if response.status_code == 404:
            raise JiraError(not_found)
        if not response.ok:
            raise JiraError(f"Jira returned an error ({response.status_code}). Try again later.")

        try:
            data = response.json()
        except ValueError as e:
            raise JiraError(UNREADABLE_RESPONSE) from e
        if not isinstance(data, dict):
            raise JiraError(UNREADABLE_RESPONSE)
        return data
