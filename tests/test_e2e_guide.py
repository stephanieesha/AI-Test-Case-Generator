import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
import github_source
from e2e_guide import NEW_PROJECT_FOLDER, GuideError, build_guide
from e2e_tools import E2E_TOOLS

REPO_URL = "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test"


@pytest.fixture
def client():
    return app_module.app.test_client()


def post(client, **body):
    return client.post("/e2e/guide", json=body)


def test_a_new_project_goes_in_the_default_folder():
    guide = build_guide("playwright", "new")
    assert guide["tool"] == {"id": "playwright", "name": "Playwright", "language": "TypeScript"}
    assert guide["source"] == {"type": "new", "folder": NEW_PROJECT_FOLDER}
    assert NEW_PROJECT_FOLDER == "my-e2e-tests"


def test_a_repository_link_is_ignored_for_a_new_project():
    assert build_guide("cypress", "new", "not even a link")["source"] == {"type": "new", "folder": NEW_PROJECT_FOLDER}


def test_a_cloned_project_goes_in_the_folder_named_after_the_repository():
    guide = build_guide("cypress", "clone", REPO_URL + ".git")
    assert guide["source"] == {
        "type": "clone",
        "owner": "stephanieesha",
        "repo": "AI-Test-Case-Generator-e2e-test",
        "url": REPO_URL + ".git",
        "folder": "AI-Test-Case-Generator-e2e-test",
    }


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_every_tool_gets_its_name_and_language(tool_id):
    tool = build_guide(tool_id, "new")["tool"]
    assert tool == {"id": tool_id, "name": E2E_TOOLS[tool_id]["name"], "language": E2E_TOOLS[tool_id]["language"]}


@pytest.mark.parametrize("tool_id", [None, "", 5, ["cypress"], {"id": "cypress"}])
def test_no_tool_asks_for_one(tool_id):
    with pytest.raises(GuideError) as error:
        build_guide(tool_id, "new")
    assert str(error.value) == "Choose the tool you will write the automated tests in."


@pytest.mark.parametrize("tool_id", ["jest", "Cypress", " cypress", "__class__", "cypress; ls"])
def test_an_unknown_tool_is_turned_back_without_repeating_what_was_sent(tool_id):
    with pytest.raises(GuideError) as error:
        build_guide(tool_id, "new")
    assert str(error.value) == "That tool is not one of the choices."


@pytest.mark.parametrize("source_type", [None, "", "fork", "NEW", "clone ", 5, ["new"]])
def test_an_unknown_source_asks_for_a_choice(source_type):
    with pytest.raises(GuideError) as error:
        build_guide("cypress", source_type)
    assert str(error.value) == "Choose whether to start a new project or use one from GitHub."


def test_a_bad_repository_link_gives_the_message_for_that_link():
    with pytest.raises(GuideError) as error:
        build_guide("cypress", "clone", "https://gitlab.com/owner/repo")
    assert str(error.value) == github_source.NOT_GITHUB


def test_a_clone_without_a_link_asks_for_one():
    with pytest.raises(GuideError) as error:
        build_guide("cypress", "clone", "")
    assert str(error.value) == github_source.EMPTY


def test_the_tool_is_checked_before_the_source():
    with pytest.raises(GuideError) as error:
        build_guide("", "")
    assert str(error.value) == "Choose the tool you will write the automated tests in."


def test_the_guide_has_one_part_for_each_thing_the_page_shows_in_the_order_it_shows_them():
    assert list(build_guide("playwright", "new")) == ["tool", "source", "install_steps", "folder_structure", "deploy_steps"]


def test_the_endpoint_returns_the_guide_for_a_new_project(client):
    response = post(client, tool="selenium", source="new")
    assert response.status_code == 200
    assert response.get_json() == build_guide("selenium", "new")


def test_the_endpoint_returns_the_guide_for_a_cloned_project(client):
    response = post(client, tool="cucumber", source="clone", repo_url=REPO_URL)
    assert response.status_code == 200
    assert response.get_json() == build_guide("cucumber", "clone", REPO_URL)


@pytest.mark.parametrize(
    "body, message",
    [
        ({}, "Choose the tool you will write the automated tests in."),
        ({"tool": "jest", "source": "new"}, "That tool is not one of the choices."),
        ({"tool": "cypress"}, "Choose whether to start a new project or use one from GitHub."),
        ({"tool": "cypress", "source": "clone"}, github_source.EMPTY),
        ({"tool": "cypress", "source": "clone", "repo_url": "https://example.com/a/b"}, github_source.NOT_GITHUB),
        ({"tool": 5, "source": "new"}, "Choose the tool you will write the automated tests in."),
        ({"tool": "cypress", "source": "clone", "repo_url": 5}, github_source.EMPTY),
    ],
)
def test_the_endpoint_turns_back_a_choice_that_cannot_be_used(client, body, message):
    response = post(client, **body)
    assert response.status_code == 400
    assert response.get_json() == {"error": message}


@pytest.mark.parametrize("raw", ["", "not json", "[1, 2]", "null", '"cypress"'])
def test_the_endpoint_turns_back_a_body_that_is_not_a_json_object(client, raw):
    response = client.post("/e2e/guide", data=raw, content_type="application/json")
    assert response.status_code == 400
    assert response.get_json() == {"error": "Choose the tool you will write the automated tests in."}


def test_the_endpoint_turns_back_a_body_that_is_not_json_at_all(client):
    response = client.post("/e2e/guide", data="tool=cypress&source=new")
    assert response.status_code == 400


def test_the_endpoint_only_answers_post(client):
    assert client.get("/e2e/guide").status_code == 405


def test_the_endpoint_does_not_use_the_generator_or_the_limits(client, monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("the guide must not call the generator or the limits")

    monkeypatch.setattr(app_module.generator, "generate", fail)
    monkeypatch.setattr(app_module, "check_generation_allowed", fail)
    assert post(client, tool="cypress", source="new").status_code == 200
