"""
Puts the two choices from the page together: the end-to-end tool, and whether the tests go in a new
project or in a repository cloned from GitHub.

The steps for the chosen tool are added to the guide one part at a time. Nothing here calls an AI
model or reaches out to GitHub.
"""

from e2e_tools import E2E_TOOLS
from github_source import SourceError, parse_github_repo

NEW_PROJECT_FOLDER = "my-e2e-tests"


class GuideError(ValueError):
    """A choice that cannot be turned into a guide. The message is written for the person using the page."""


def build_guide(tool_id, source_type, repo_url=""):
    return {"tool": _tool(tool_id), "source": _source(source_type, repo_url)}


def _tool(tool_id):
    if not isinstance(tool_id, str) or not tool_id:
        raise GuideError("Choose the tool you will write the automated tests in.")
    tool = E2E_TOOLS.get(tool_id)
    if tool is None:
        raise GuideError("That tool is not one of the choices.")
    return {"id": tool_id, "name": tool["name"], "language": tool["language"]}


def _source(source_type, repo_url):
    if source_type == "new":
        return {"type": "new", "folder": NEW_PROJECT_FOLDER}
    if source_type == "clone":
        try:
            repo = parse_github_repo(repo_url)
        except SourceError as error:
            raise GuideError(str(error)) from None
        return {"type": "clone", "owner": repo["owner"], "repo": repo["repo"], "url": repo["url"], "folder": repo["repo"]}
    raise GuideError("Choose whether to start a new project or use one from GitHub.")
