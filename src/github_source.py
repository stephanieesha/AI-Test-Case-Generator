"""
Reads a GitHub repository link that someone pastes, so the page can tell them how to clone it.

The link is only checked and tidied up here. Nothing is fetched from GitHub, so the repository can
be private. The owner and repository names are kept to the characters GitHub allows, which also
means they are safe to show inside a shell command.
"""

import re
from urllib.parse import urlsplit

EXAMPLE = "https://github.com/owner/repo"
MAX_LINK_LENGTH = 300

EMPTY = "Paste the link to the GitHub repository you want to use."
NOT_GITHUB = f"That is not a GitHub link. Use one like {EXAMPLE}."
NO_REPO = f"That link does not name a repository. Use one like {EXAMPLE}."
EXTRA_PATH = f"Use the link to the repository's main page, like {EXAMPLE}, without a branch or folder at the end."
CREDENTIALS = f"Take the username or token out of the link and use one like {EXAMPLE}."
BAD_NAME = "That owner or repository name has characters GitHub does not allow."

HOSTS = {"github.com", "www.github.com"}
SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://")
SSH_LINK = re.compile(r"git@github\.com:([^/]+)/([^/]+)", re.IGNORECASE)
OWNER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,38}")
REPO = re.compile(r"[A-Za-z0-9._][A-Za-z0-9._-]{0,99}")


class SourceError(ValueError):
    """The link cannot be used. The message is written for the person who pasted it."""


def parse_github_repo(link):
    """Return the owner, the repository name and the https clone link for a GitHub repository link."""
    text = link.strip() if isinstance(link, str) else ""
    if not text:
        raise SourceError(EMPTY)
    if len(text) > MAX_LINK_LENGTH or not text.isascii() or any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in text):
        raise SourceError(NOT_GITHUB)

    owner, repo = _owner_and_repo(text)
    if repo.lower().endswith(".git"):
        repo = repo[:-4]
    if not repo:
        raise SourceError(NO_REPO)
    if not OWNER.fullmatch(owner) or not REPO.fullmatch(repo) or repo in (".", ".."):
        raise SourceError(BAD_NAME)
    return {"owner": owner, "repo": repo, "url": f"https://github.com/{owner}/{repo}.git"}


def _owner_and_repo(text):
    ssh = SSH_LINK.fullmatch(text)
    if ssh:
        return ssh.group(1), ssh.group(2)

    if not SCHEME.match(text):
        text = "https://" + text
    try:
        parts = urlsplit(text)
        port = parts.port
    except ValueError:
        raise SourceError(NOT_GITHUB) from None
    if parts.scheme.lower() not in ("http", "https"):
        raise SourceError(NOT_GITHUB)
    if parts.username is not None or parts.password is not None:
        raise SourceError(CREDENTIALS)
    if parts.hostname not in HOSTS or port is not None:
        raise SourceError(NOT_GITHUB)

    path = parts.path.strip("/")
    segments = path.split("/") if path else []
    if len(segments) < 2:
        raise SourceError(NO_REPO)
    if len(segments) > 2:
        raise SourceError(EXTRA_PATH)
    return segments[0], segments[1]
