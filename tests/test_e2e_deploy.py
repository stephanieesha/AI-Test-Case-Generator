import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from e2e_deploy import BRANCH, GITIGNORE, WORKFLOWS, deploy_steps, workflow_path
from e2e_guide import build_guide
from e2e_install import install_steps
from e2e_tools import E2E_TOOLS

NEW = {"type": "new", "folder": "my-e2e-tests"}
CLONE = {"type": "clone", "owner": "o", "repo": "r", "url": "https://github.com/o/r.git", "folder": "r"}

TITLES_FOR_A_NEW_PROJECT = [
    "Create an empty repository on GitHub",
    "Keep generated files out of git",
    "Add the workflow file",
    "Point the tests at your site",
    "Commit and push",
    "Watch the run",
]
TITLES_FOR_A_NEW_SELENIUM_PROJECT = [
    "Create an empty repository on GitHub",
    "Keep generated files out of git",
    "Save the packages the tests need",
    "Add the workflow file",
    "Point the tests at your site",
    "Commit and push",
    "Watch the run",
]
TITLES_FOR_A_CLONED_PROJECT = [
    "Create a branch",
    "Add the workflow file",
    "Point the tests at your site",
    "Commit and push the branch",
    "Open a pull request",
    "Watch the run",
]

PUSH_A_NEW_PROJECT = [
    "git init",
    "git add .",
    'git commit -m "Add the end-to-end tests"',
    "git branch -M main",
    "git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git",
    "git push -u origin main",
]

BASE_URL_LINE = {
    "cypress": "CYPRESS_BASE_URL: ${{ vars.BASE_URL }}",
    "playwright": "BASE_URL: ${{ vars.BASE_URL }}",
    "selenium": "BASE_URL: ${{ vars.BASE_URL }}",
    "cucumber": "BASE_URL: ${{ vars.BASE_URL }}",
}
TEST_COMMAND = {
    "cypress": "npx cypress run",
    "playwright": "npx playwright test",
    "selenium": "python -m pytest --junitxml=junit.xml",
    "cucumber": "npx cucumber-js --format progress --format html:cucumber-report.html",
}


def titles(steps):
    return [step["title"] for step in steps]


def step_named(steps, title):
    return next(step for step in steps if step["title"] == title)


def run_lines(tool_id):
    return re.findall(r"^\s+run: (.+)$", WORKFLOWS[tool_id], re.M)


def test_every_tool_has_a_workflow_and_ignore_lines_and_nothing_else_does():
    assert set(WORKFLOWS) == set(E2E_TOOLS)
    assert set(GITIGNORE) == set(E2E_TOOLS)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_goes_in_a_file_named_after_the_tool(tool_id):
    assert workflow_path(tool_id) == f".github/workflows/{tool_id}.yml"


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_file_is_tidy_text(tool_id):
    text = WORKFLOWS[tool_id]
    assert text.endswith("\n") and not text.endswith("\n\n")
    assert "\t" not in text
    assert not re.search(r"[ \t]+$", text, re.M)
    assert all((len(line) - len(line.lstrip(" "))) % 2 == 0 for line in text.splitlines() if line.strip())


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_runs_on_push_pull_request_and_by_hand(tool_id):
    text = WORKFLOWS[tool_id]
    assert re.search(r"^on:\n  push:\n    branches: \[main, master\]\n  pull_request:\n    branches: \[main, master\]\n  workflow_dispatch:\n", text, re.M)
    assert "runs-on: ubuntu-latest" in text
    assert "timeout-minutes: 30" in text


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_reads_the_site_address_from_the_repository_variable(tool_id):
    assert f"      {BASE_URL_LINE[tool_id]}\n" in WORKFLOWS[tool_id]
    assert "secrets." not in WORKFLOWS[tool_id]


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_runs_the_tests_and_keeps_the_report_even_when_they_fail(tool_id):
    text = WORKFLOWS[tool_id]
    assert TEST_COMMAND[tool_id] in run_lines(tool_id)
    assert "uses: actions/upload-artifact@v7\n        if: ${{ !cancelled() }}\n" in text


REPORT_PATHS = {
    "cypress": ["cypress/screenshots", "cypress/videos"],
    "playwright": ["playwright-report"],
    "selenium": ["junit.xml"],
    "cucumber": ["cucumber-report.html"],
}


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_report_the_workflow_keeps_is_the_one_the_tests_write_and_is_left_out_of_git(tool_id):
    text = WORKFLOWS[tool_id]
    ignored = [line.strip("/") for line in GITIGNORE[tool_id].splitlines()]
    for report in REPORT_PATHS[tool_id]:
        assert re.search(rf"^\s+(?:path: |)(?:\./)?{re.escape(report)}/?$", text, re.M), report
        assert report in ignored


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_every_action_in_the_workflow_is_pinned_to_a_major_version(tool_id):
    uses = re.findall(r"uses: (\S+)", WORKFLOWS[tool_id])
    assert uses[0] == "actions/checkout@v6"
    assert all(re.fullmatch(r"actions/[a-z-]+@v\d+", value) for value in uses)
    assert len(uses) == len(set(uses))


@pytest.mark.parametrize("tool_id", ["cypress", "playwright", "cucumber"])
def test_the_node_workflows_use_node_lts_and_a_locked_install(tool_id):
    text = WORKFLOWS[tool_id]
    assert "uses: actions/setup-node@v6\n        with:\n          node-version: lts/*\n" in text
    assert "npm ci" in run_lines(tool_id)


def test_the_selenium_workflow_uses_python_and_installs_from_requirements():
    text = WORKFLOWS["selenium"]
    assert 'uses: actions/setup-python@v6\n        with:\n          python-version: "3.12"\n' in text
    assert "run: pip install -r requirements.txt" in text


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_installs_the_same_way_the_install_steps_do(tool_id):
    steps = [command for step in install_steps(tool_id, CLONE) for command in step["commands"]]
    installs = [command for command in steps if command.startswith(("npm ci", "pip install -r", "npx playwright install", "npx cypress install"))]
    assert installs
    for command in installs:
        assert any(line.startswith(command) for line in run_lines(tool_id)), command


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_file_is_valid_yaml_with_the_expected_shape(tool_id):
    yaml = pytest.importorskip("yaml")
    data = yaml.safe_load(WORKFLOWS[tool_id])
    triggers = data.get("on", data.get(True))
    assert set(triggers) == {"push", "pull_request", "workflow_dispatch"}
    assert triggers["push"] == {"branches": ["main", "master"]}
    assert triggers["pull_request"] == {"branches": ["main", "master"]}
    job = data["jobs"]["test"]
    assert job["runs-on"] == "ubuntu-latest"
    assert all(("uses" in step) != ("run" in step) for step in job["steps"])
    assert job["steps"][-1]["if"] == "${{ !cancelled() }}"
    assert job["steps"][-1]["uses"] == "actions/upload-artifact@v7"
    assert list(job["env"].values()) == ["${{ vars.BASE_URL }}"]


@pytest.mark.parametrize("tool_id", [tool_id for tool_id in E2E_TOOLS if tool_id != "selenium"])
def test_a_new_node_project_gets_the_steps_in_order(tool_id):
    assert titles(deploy_steps(tool_id, NEW)) == TITLES_FOR_A_NEW_PROJECT


def test_a_new_selenium_project_also_saves_its_packages_before_the_workflow_file():
    steps = deploy_steps("selenium", NEW)
    assert titles(steps) == TITLES_FOR_A_NEW_SELENIUM_PROJECT
    assert step_named(steps, "Save the packages the tests need")["commands"] == ["pip freeze > requirements.txt"]


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_a_cloned_project_gets_a_branch_a_pull_request_and_no_new_repository(tool_id):
    steps = deploy_steps(tool_id, CLONE)
    assert titles(steps) == TITLES_FOR_A_CLONED_PROJECT
    assert step_named(steps, "Create a branch")["commands"] == [f"git switch -c {BRANCH}"]
    assert BRANCH == "add-e2e-workflow"


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_a_new_project_is_pushed_to_the_empty_repository(tool_id):
    steps = deploy_steps(tool_id, NEW)
    push = step_named(steps, "Commit and push")
    assert push["commands"] == PUSH_A_NEW_PROJECT
    assert "YOUR-USERNAME" in push["detail"] and "YOUR-REPOSITORY" in push["detail"]
    assert "Leave it empty" in step_named(steps, "Create an empty repository on GitHub")["detail"]


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_a_cloned_project_commits_only_the_workflow_file_and_pushes_the_branch(tool_id):
    commit = step_named(deploy_steps(tool_id, CLONE), "Commit and push the branch")
    assert commit["commands"] == [
        f"git add .github/workflows/{tool_id}.yml",
        'git commit -m "Run the end-to-end tests on GitHub Actions"',
        f"git push -u origin {BRANCH}",
    ]
    assert "git add ." not in commit["commands"]
    pull_request = step_named(deploy_steps(tool_id, CLONE), "Open a pull request")
    assert f"from {BRANCH} into main" in pull_request["detail"]
    assert "fork" in pull_request["detail"]


@pytest.mark.parametrize("source", [NEW, CLONE], ids=["new", "clone"])
@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_file_step_carries_the_workflow_text_and_path(tool_id, source):
    step = step_named(deploy_steps(tool_id, source), "Add the workflow file")
    assert step["file"] == {"path": f".github/workflows/{tool_id}.yml", "content": WORKFLOWS[tool_id]}
    assert "commands" not in step


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_a_new_project_gets_ignore_lines_for_its_tool(tool_id):
    step = step_named(deploy_steps(tool_id, NEW), "Keep generated files out of git")
    assert step["file"] == {"path": ".gitignore", "content": GITIGNORE[tool_id]}
    lines = GITIGNORE[tool_id].splitlines()
    assert ".env" in lines
    assert ("node_modules/" in lines) == (tool_id != "selenium")
    assert (".venv/" in lines) == (tool_id == "selenium")


def test_a_cloned_project_keeps_the_ignore_lines_it_already_has():
    for tool_id in E2E_TOOLS:
        assert "Keep generated files out of git" not in titles(deploy_steps(tool_id, CLONE))


def test_playwright_is_told_it_already_made_a_gitignore_and_the_others_are_told_to_create_one():
    assert "already created" in step_named(deploy_steps("playwright", NEW), "Keep generated files out of git")["detail"]
    for tool_id in ("cypress", "selenium", "cucumber"):
        assert "Create a file called .gitignore" in step_named(deploy_steps(tool_id, NEW), "Keep generated files out of git")["detail"]


@pytest.mark.parametrize(
    "tool_id, hints",
    [
        ("cypress", ["CYPRESS_BASE_URL", "baseUrl"]),
        ("playwright", ["process.env.BASE_URL", "playwright.config.ts"]),
        ("selenium", ['os.environ["BASE_URL"]', "--headless=new"]),
        ("cucumber", ["process.env.BASE_URL"]),
    ],
)
def test_each_tool_is_told_how_to_read_the_site_address(tool_id, hints):
    detail = step_named(deploy_steps(tool_id, NEW), "Point the tests at your site")["detail"]
    assert "Settings" in detail and "Variables" in detail and "BASE_URL" in detail
    for hint in hints:
        assert hint in detail


@pytest.mark.parametrize("source", [NEW, CLONE], ids=["new", "clone"])
@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_every_step_has_a_title_and_only_the_parts_it_needs(tool_id, source):
    steps = deploy_steps(tool_id, source)
    for step in steps:
        assert set(step) <= {"title", "detail", "commands", "file"}
        assert isinstance(step["title"], str) and step["title"].strip()
        if "detail" in step:
            assert isinstance(step["detail"], str) and step["detail"].strip()
        if "commands" in step:
            assert step["commands"] and all(isinstance(c, str) and c.strip() for c in step["commands"])
        if "file" in step:
            assert set(step["file"]) == {"path", "content"}
            assert all(isinstance(v, str) and v for v in step["file"].values())
    assert len(set(titles(steps))) == len(steps)


def test_nothing_in_the_deploy_steps_depends_on_the_repository_that_was_checked():
    one = {"type": "clone", "owner": "a", "repo": "b", "url": "https://github.com/a/b.git", "folder": "b"}
    other = {"type": "clone", "owner": "Octo_Cat", "repo": "my.repo-1", "url": "https://github.com/Octo_Cat/my.repo-1.git", "folder": "my.repo-1"}
    assert deploy_steps("playwright", one) == deploy_steps("playwright", other)


def test_changing_what_comes_back_does_not_change_the_next_answer():
    first = deploy_steps("selenium", NEW)
    first[1]["file"]["content"] = "changed"
    first[1]["file"]["path"] = "changed"
    first[-2]["commands"].append("rm -rf /")
    first[-1]["title"] = "changed"
    first[-1]["detail"] = "changed"
    first.pop()
    assert titles(deploy_steps("selenium", NEW)) == TITLES_FOR_A_NEW_SELENIUM_PROJECT
    assert step_named(deploy_steps("selenium", NEW), "Watch the run")["detail"].startswith("Open the Actions tab")
    assert step_named(deploy_steps("selenium", NEW), "Commit and push")["commands"] == PUSH_A_NEW_PROJECT
    assert step_named(deploy_steps("selenium", NEW), "Keep generated files out of git")["file"]["content"] == GITIGNORE["selenium"]


def test_the_guide_carries_the_deploy_steps_for_its_tool_and_source():
    guide = build_guide("cypress", "clone", "https://github.com/o/r")
    assert guide["deploy_steps"] == deploy_steps("cypress", guide["source"])
    assert titles(guide["deploy_steps"]) == TITLES_FOR_A_CLONED_PROJECT


def test_the_endpoint_returns_the_deploy_steps():
    response = app_module.app.test_client().post("/e2e/guide", json={"tool": "selenium", "source": "new"})
    assert response.status_code == 200
    assert titles(response.get_json()["deploy_steps"]) == TITLES_FOR_A_NEW_SELENIUM_PROJECT
