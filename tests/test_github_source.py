import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import github_source
from github_source import SourceError, parse_github_repo

REPO_URL = "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test"


@pytest.mark.parametrize(
    "link",
    [
        "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test",
        "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test.git",
        "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test/",
        "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test?tab=readme-ov-file#readme",
        "http://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test",
        "github.com/stephanieesha/AI-Test-Case-Generator-e2e-test",
        "www.github.com/stephanieesha/AI-Test-Case-Generator-e2e-test",
        "HTTPS://GitHub.COM/stephanieesha/AI-Test-Case-Generator-e2e-test",
        "git@github.com:stephanieesha/AI-Test-Case-Generator-e2e-test.git",
        "  https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test \n",
    ],
)
def test_the_ways_people_copy_a_repository_link_all_give_the_same_repository(link):
    assert parse_github_repo(link) == {
        "owner": "stephanieesha",
        "repo": "AI-Test-Case-Generator-e2e-test",
        "url": "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test.git",
    }


def test_the_clone_link_is_always_https_whatever_was_pasted():
    assert parse_github_repo("git@github.com:o/r.git")["url"] == "https://github.com/o/r.git"
    assert parse_github_repo("http://github.com/o/r")["url"] == "https://github.com/o/r.git"


@pytest.mark.parametrize(
    "link, owner, repo",
    [
        ("https://github.com/Owner/Repo", "Owner", "Repo"),
        ("https://github.com/octocat_acme/repo", "octocat_acme", "repo"),
        ("https://github.com/owner/my.repo_name-1", "owner", "my.repo_name-1"),
        ("https://github.com/owner/.github", "owner", ".github"),
        ("https://github.com/owner/repo.js", "owner", "repo.js"),
        ("https://github.com/owner/legit", "owner", "legit"),
        ("https://github.com/owner/repo.GIT", "owner", "repo"),
        ("https://github.com/" + "a" * 39 + "/" + "b" * 100, "a" * 39, "b" * 100),
    ],
)
def test_names_keep_their_case_and_only_a_real_dot_git_ending_is_dropped(link, owner, repo):
    result = parse_github_repo(link)
    assert (result["owner"], result["repo"]) == (owner, repo)


@pytest.mark.parametrize("link", [None, 5, ["https://github.com/o/r"], {"url": "x"}, "", "   ", "\n"])
def test_nothing_pasted_asks_for_a_link(link):
    with pytest.raises(SourceError) as error:
        parse_github_repo(link)
    assert str(error.value) == github_source.EMPTY


@pytest.mark.parametrize(
    "link",
    [
        "not a link",
        "https://gitlab.com/owner/repo",
        "https://bitbucket.org/owner/repo",
        "https://github.com.evil.com/owner/repo",
        "https://evil.com/github.com/owner/repo",
        "https://notgithub.com/owner/repo",
        "https://gist.github.com/owner/repo",
        "https://github.com:8080/owner/repo",
        "https://github.com:abc/owner/repo",
        "ftp://github.com/owner/repo",
        "ssh://git@github.com/owner/repo.git",
        "git@gitlab.com:owner/repo.git",
        "//github.com/owner/repo",
        "https://github.com\\owner\\repo",
        "https://github.com/owner/repo\nhttps://evil.com",
        "https://github.com/owner/re po",
        "https://github.com/owner/rеpo",
        "https://github.com/" + "a" * 300,
    ],
)
def test_a_link_that_is_not_github_is_turned_back(link):
    with pytest.raises(SourceError) as error:
        parse_github_repo(link)
    assert str(error.value) == github_source.NOT_GITHUB


@pytest.mark.parametrize(
    "link",
    [
        "https://token@github.com/owner/repo",
        "https://user:pass@github.com/owner/repo",
        "https://ghp_abc123@github.com/owner/repo.git",
        "https://github.com@evil.com/owner/repo",
    ],
)
def test_a_link_with_a_username_or_token_is_turned_back(link):
    with pytest.raises(SourceError) as error:
        parse_github_repo(link)
    assert str(error.value) == github_source.CREDENTIALS
    assert "ghp_abc123" not in str(error.value)


@pytest.mark.parametrize(
    "link",
    [
        "https://github.com",
        "https://github.com/",
        "https://github.com/owner",
        "github.com/owner/",
        "https://github.com/owner/.git",
        "git@github.com:owner/.git",
    ],
)
def test_a_link_with_no_repository_name_is_turned_back(link):
    with pytest.raises(SourceError) as error:
        parse_github_repo(link)
    assert str(error.value) == github_source.NO_REPO


@pytest.mark.parametrize(
    "link",
    [
        "https://github.com/owner/repo/tree/main",
        "https://github.com/owner/repo/blob/main/README.md",
        "https://github.com/owner/repo/issues",
        "https://github.com/owner/repo/.git",
        "https://github.com/owner//repo",
    ],
)
def test_a_link_to_a_page_inside_the_repository_is_turned_back(link):
    with pytest.raises(SourceError) as error:
        parse_github_repo(link)
    assert str(error.value) == github_source.EXTRA_PATH


@pytest.mark.parametrize(
    "link",
    [
        "https://github.com/owner/repo;ls",
        "https://github.com/owner/repo&&ls",
        "https://github.com/owner/repo|ls",
        "https://github.com/owner/$(whoami)",
        "https://github.com/owner/`id`",
        "https://github.com/owner/repo'",
        'https://github.com/owner/repo"',
        "https://github.com/owner/<script>",
        "https://github.com/owner/re%70o",
        "https://github.com/owner/..",
        "https://github.com/owner/.",
        "https://github.com/owner/-repo",
        "https://github.com/-owner/repo",
        "https://github.com/own.er/repo",
        "https://github.com/" + "a" * 40 + "/repo",
        "https://github.com/owner/" + "b" * 101,
        "git@github.com:owner;ls/repo.git",
    ],
)
def test_names_with_characters_github_does_not_allow_are_turned_back(link):
    with pytest.raises(SourceError) as error:
        parse_github_repo(link)
    assert str(error.value) == github_source.BAD_NAME


def test_every_message_shows_the_form_of_link_to_use_or_says_what_is_wrong():
    for message in (github_source.NOT_GITHUB, github_source.NO_REPO, github_source.EXTRA_PATH, github_source.CREDENTIALS):
        assert github_source.EXAMPLE in message
    assert github_source.EMPTY.startswith("Paste")


def test_a_clean_result_is_safe_to_put_in_a_shell_command():
    for link in ("https://github.com/o/r", REPO_URL, "git@github.com:Octo_Cat/my.repo-1.git"):
        result = parse_github_repo(link)
        for value in (result["owner"], result["repo"], result["url"]):
            assert re.fullmatch(r"[A-Za-z0-9._:/-]+", value)
