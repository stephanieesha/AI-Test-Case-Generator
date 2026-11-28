import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from e2e_guide import build_guide
from e2e_install import INSTALL, install_steps
from e2e_tools import E2E_TOOLS

NEW = {"type": "new", "folder": "my-e2e-tests"}
CLONE = {"type": "clone", "owner": "o", "repo": "r", "url": "https://github.com/o/r.git", "folder": "r"}

MAKE_FOLDER = ["mkdir my-e2e-tests", "cd my-e2e-tests"]
CLONE_IT = ["git clone https://github.com/o/r.git", "cd r"]
VENV = ["python3 -m venv .venv", "source .venv/bin/activate"]

# The commands of every step, in order. A wrong command here means wrong guidance on the page.
COMMANDS_FOR_A_NEW_PROJECT = {
    "cypress": [
        ["node --version"],
        MAKE_FOLDER,
        ["npm init -y"],
        ["npm install cypress --save-dev", "npx cypress install", "npx cypress verify"],
        ["npx cypress open"],
        ["npx cypress run"],
    ],
    "playwright": [
        ["node --version"],
        MAKE_FOLDER,
        ["npm init playwright@latest"],
        ["npx playwright test"],
    ],
    "selenium": [
        ["python3 --version"],
        MAKE_FOLDER,
        VENV,
        ["pip install selenium pytest"],
        ['python3 -c "import selenium; print(selenium.__version__)"', "python3 -m pytest --version"],
    ],
    "cucumber": [
        ["node --version"],
        MAKE_FOLDER,
        ["npm init -y"],
        ["npm install --save-dev @cucumber/cucumber playwright"],
        ["npx playwright install"],
        ["npx cucumber-js --version"],
    ],
}

COMMANDS_FOR_A_CLONED_PROJECT = {
    "cypress": [
        ["node --version"],
        CLONE_IT,
        ["npm ci"],
        ["npx cypress install", "npx cypress verify"],
        ["npx cypress run"],
    ],
    "playwright": [
        ["node --version"],
        CLONE_IT,
        ["npm ci"],
        ["npx playwright install"],
        ["npx playwright test"],
    ],
    "selenium": [
        ["python3 --version"],
        CLONE_IT,
        VENV,
        ["pip install -r requirements.txt"],
        ["python3 -m pytest"],
    ],
    "cucumber": [
        ["node --version"],
        CLONE_IT,
        ["npm ci"],
        ["npx playwright install"],
        ["npx cucumber-js"],
    ],
}


def commands(steps):
    return [step["commands"] for step in steps]


def test_every_tool_has_install_steps_and_nothing_else_does():
    assert set(INSTALL) == set(E2E_TOOLS)
    assert set(COMMANDS_FOR_A_NEW_PROJECT) == set(E2E_TOOLS)
    assert set(COMMANDS_FOR_A_CLONED_PROJECT) == set(E2E_TOOLS)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_a_new_project_gets_the_install_commands_for_the_tool(tool_id):
    assert commands(install_steps(tool_id, NEW)) == COMMANDS_FOR_A_NEW_PROJECT[tool_id]


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_a_cloned_project_gets_the_clone_then_the_install_commands_for_the_tool(tool_id):
    assert commands(install_steps(tool_id, CLONE)) == COMMANDS_FOR_A_CLONED_PROJECT[tool_id]


@pytest.mark.parametrize("source", [NEW, CLONE], ids=["new", "clone"])
@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_every_step_has_a_title_and_commands_and_a_detail_only_when_it_has_something_to_say(tool_id, source):
    steps = install_steps(tool_id, source)
    assert steps
    for step in steps:
        assert set(step) <= {"title", "detail", "commands"}
        assert isinstance(step["title"], str) and step["title"].strip()
        assert isinstance(step["commands"], list) and step["commands"]
        assert all(isinstance(command, str) and command.strip() for command in step["commands"])
        if "detail" in step:
            assert isinstance(step["detail"], str) and step["detail"].strip()
    titles = [step["title"] for step in steps]
    assert len(titles) == len(set(titles))


@pytest.mark.parametrize("tool_id, check", [("cypress", "node"), ("playwright", "node"), ("cucumber", "node"), ("selenium", "python3")])
def test_the_first_step_checks_the_language_the_tool_runs_on(tool_id, check):
    first = install_steps(tool_id, NEW)[0]
    assert first["commands"] == [f"{check} --version"]


def test_the_python_steps_say_what_to_do_on_windows():
    steps = install_steps("selenium", NEW)
    assert "py instead of python3" in steps[0]["detail"]
    assert ".venv\\Scripts\\activate" in steps[2]["detail"]


def test_the_playwright_setup_says_no_to_its_own_workflow_because_the_deploy_steps_bring_one():
    setup = install_steps("playwright", NEW)[2]
    assert setup["commands"] == ["npm init playwright@latest"]
    assert "GitHub Actions" in setup["detail"]
    assert "TypeScript" in setup["detail"]


def test_the_cypress_steps_explain_the_extra_install_and_verify_commands():
    install = install_steps("cypress", NEW)[3]
    assert "skip" in install["detail"]


def test_the_cloned_steps_use_the_link_and_folder_that_were_checked():
    source = {"type": "clone", "owner": "Octo_Cat", "repo": "my.repo-1", "url": "https://github.com/Octo_Cat/my.repo-1.git", "folder": "my.repo-1"}
    steps = install_steps("playwright", source)
    assert steps[1]["commands"] == ["git clone https://github.com/Octo_Cat/my.repo-1.git", "cd my.repo-1"]
    for command in steps[1]["commands"]:
        assert re.fullmatch(r"[A-Za-z0-9 ._:/-]+", command)


def test_changing_what_comes_back_does_not_change_the_next_answer():
    first = install_steps("selenium", NEW)
    first[0]["commands"].append("rm -rf /")
    first[2]["commands"][0] = "changed"
    first.pop()
    assert commands(install_steps("selenium", NEW)) == COMMANDS_FOR_A_NEW_PROJECT["selenium"]
    assert install_steps("selenium", NEW) == install_steps("selenium", NEW)


def test_the_guide_carries_the_install_steps_for_its_tool_and_source():
    guide = build_guide("cypress", "clone", "https://github.com/o/r")
    assert guide["install_steps"] == install_steps("cypress", guide["source"])
    assert commands(guide["install_steps"]) == COMMANDS_FOR_A_CLONED_PROJECT["cypress"]


def test_the_endpoint_returns_the_install_steps():
    client = app_module.app.test_client()
    response = client.post("/e2e/guide", json={"tool": "cucumber", "source": "new"})
    assert response.status_code == 200
    assert commands(response.get_json()["install_steps"]) == COMMANDS_FOR_A_NEW_PROJECT["cucumber"]
