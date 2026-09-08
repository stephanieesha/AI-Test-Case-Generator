"""
Minimal read-only Jira Cloud client. Fetches a ticket's summary and
description so it can be fed directly into the test case generator,
removing the copy/paste step between Jira and this tool.

Read-only by design: this never writes a comment, field, or status back to
Jira. Uses your own Atlassian account's API token, not a workspace app or
Marketplace listing - see README for how to generate one.
"""

import os

import requests
from requests.auth import HTTPBasicAuth


class JiraClient:
    def __init__(self, domain: str = None, email: str = None, api_token: str = None):
        self.domain = domain or os.environ.get("JIRA_DOMAIN")
        self.email = email or os.environ.get("JIRA_EMAIL")
        self.api_token = api_token or os.environ.get("JIRA_API_TOKEN")

        if not all([self.domain, self.email, self.api_token]):
            raise ValueError(
                "Jira credentials missing - set JIRA_DOMAIN, JIRA_EMAIL, "
                "and JIRA_API_TOKEN in .env"
            )

    def get_issue(self, issue_key: str) -> dict:
        # Using API v2 rather than v3: v2 returns the description as a plain
        # text/wiki-markup string, while v3 returns a structured "Atlassian
        # Document Format" object. Since this text is just being fed into a
        # prompt (not rendered), the simpler v2 string is all that's needed.
        url = f"https://{self.domain}.atlassian.net/rest/api/2/issue/{issue_key}"
        response = requests.get(
            url,
            auth=HTTPBasicAuth(self.email, self.api_token),
            headers={"Accept": "application/json"},
            timeout=15,
        )
        response.raise_for_status()

        fields = response.json().get("fields", {})
        return {
            "key": issue_key,
            "summary": fields.get("summary", ""),
            "description": fields.get("description") or "",
        }
