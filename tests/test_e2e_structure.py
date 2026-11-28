import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from e2e_deploy import workflow_path
from e2e_guide import build_guide
from e2e_structure import CLONE_NOTE, NEW_NOTE, STRUCTURES, folder_structure
from e2e_tools import E2E_TOOLS

NEW = {"type": "new", "folder": "my-e2e-tests"}
CLONE = {"type": "clone", "owner": "o", "repo": "r", "url": "https://github.com/o/r.git", "folder": "r"}

TREES = {
    "cypress": """\
my-e2e-tests/
├── cypress.config.js
├── package.json
├── cypress/
│   ├── e2e/
│   │   └── login.cy.js
│   ├── fixtures/
│   │   └── users.json
│   ├── locators/
│   │   └── login.locators.js
│   ├── pages/
│   │   ├── base.page.js
│   │   └── login.page.js
│   └── support/
│       ├── commands.js
│       └── e2e.js
└── .github/
    └── workflows/
        └── cypress.yml""",
    "playwright": """\
my-e2e-tests/
├── playwright.config.ts
├── package.json
├── locators/
│   └── login.locators.ts
├── pages/
│   ├── base.page.ts
│   └── login.page.ts
├── tests/
│   └── login.spec.ts
└── .github/
    └── workflows/
        └── playwright.yml""",
    "selenium": """\
my-e2e-tests/
├── conftest.py
├── requirements.txt
├── locators/
│   └── login_locators.py
├── pages/
│   ├── base_page.py
│   └── login_page.py
├── tests/
│   └── test_login.py
└── .github/
    └── workflows/
        └── selenium.yml""",
    "cucumber": """\
my-e2e-tests/
├── cucumber.js
├── package.json
├── features/
│   ├── login.feature
│   ├── step_definitions/
│   │   └── login.steps.js
│   └── support/
│       ├── hooks.js
│       └── world.js
├── locators/
│   └── login.locators.js
├── pages/
│   ├── base.page.js
│   └── login.page.js
└── .github/
    └── workflows/
        └── cucumber.yml""",
}

# Where each tool looks for its tests, where the locators and pages go, and what its code files end in.
TESTS_FOLDER = {"cypress": "cypress/e2e/", "playwright": "tests/", "selenium": "tests/", "cucumber": "features/"}
UNDER = {"cypress": "cypress/", "playwright": "", "selenium": "", "cucumber": ""}
CONFIG_FILE = {"cypress": "cypress.config.js", "playwright": "playwright.config.ts", "selenium": "conftest.py", "cucumber": "cucumber.js"}
CODE_EXTENSION = {"JavaScript": ".js", "TypeScript": ".ts", "Python": ".py"}

BASE_PAGE = {"cypress": "base.page.js", "playwright": "base.page.ts", "selenium": "base_page.py", "cucumber": "base.page.js"}
TESTS_NOTE = {
    "cypress": "cypress/e2e/ holds the specs. They call page methods and never use selectors directly.",
    "playwright": "tests/ holds the tests. They call page methods and never use selectors directly.",
    "selenium": (
        "tests/ holds the tests, in files named test_*.py so pytest finds them. "
        "They call page methods and never use selectors directly."
    ),
    "cucumber": (
        "features/ holds the .feature files with the Given, When and Then lines, and "
        "features/step_definitions/ links each line to page methods. The steps never use selectors directly."
    ),
}
SETUP_NOTE = {
    "cypress": (
        "cypress.config.js holds the settings, such as the base URL. cypress/fixtures/ holds test data, "
        "and cypress/support/ holds the custom commands and the setup that every spec loads."
    ),
    "playwright": "playwright.config.ts holds the settings, such as the browsers, the base URL and where the tests are.",
    "selenium": (
        "conftest.py holds the pytest fixtures, such as starting and closing the browser. "
        "Keep it in the project folder, next to locators/ and pages/, so the tests can import them."
    ),
    "cucumber": (
        "features/support/ holds the hooks that open and close the browser and the world that gives each "
        "scenario its page objects. cucumber.js holds the settings."
    ),
}
NEW_NOTE_TEXT = (
    "login is only an example, so name the files after the feature you test. "
    "You do not need every file yet. Create the folders as you write your first test."
)
CLONE_NOTE_TEXT = (
    "login is only an example, so name the files after the feature you test. "
    "Keep the folders the repository already has and add only the ones that are missing, instead of moving files."
)


def expected_notes(tool_id, last):
    under = UNDER[tool_id]
    return [
        f"{under}locators/ holds the selectors, one file per page, and nothing else.",
        (
            f"{under}pages/ holds one class per page. Each page class extends the base page, uses the locators "
            "of its page and has a method for each thing a person does there, such as logging in."
        ),
        f"{BASE_PAGE[tool_id]} holds what every page shares, such as opening an address and waiting for the page to load.",
        TESTS_NOTE[tool_id],
        SETUP_NOTE[tool_id],
        last,
    ]


def paths_in(tree):
    """Read a tree back into the set of paths it shows. A folder ends with a slash."""
    root, *lines = tree.split("\n")
    paths, stack = set(), []
    for line in lines:
        match = re.fullmatch(r"((?:│   |    )*)(?:├── |└── )(.+)", line)
        assert match, f"not a line of the tree: {line!r}"
        del stack[len(match.group(1)) // 4:]
        name = match.group(2)
        paths.add("".join(stack) + name)
        if name.endswith("/"):
            stack.append(name)
    return paths


def files_under(paths, folder):
    return sorted(path[len(folder):] for path in paths if path.startswith(folder) and not path.endswith("/"))


def test_every_tool_has_a_structure_and_nothing_else_does():
    assert set(STRUCTURES) == set(E2E_TOOLS)
    assert set(TREES) == set(E2E_TOOLS)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_tree_for_a_new_project(tool_id):
    assert folder_structure(tool_id, NEW)["tree"] == TREES[tool_id]


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_tree_for_a_cloned_project_starts_with_the_repository_folder_and_is_otherwise_the_same(tool_id):
    tree = folder_structure(tool_id, CLONE)["tree"]
    assert tree.split("\n")[0] == "r/"
    assert tree.split("\n")[1:] == TREES[tool_id].split("\n")[1:]


def test_the_folder_comes_from_the_source_that_was_checked():
    source = {"type": "clone", "owner": "Octo_Cat", "repo": "my.repo-1", "url": "https://github.com/Octo_Cat/my.repo-1.git", "folder": "my.repo-1"}
    assert folder_structure("playwright", source)["tree"].startswith("my.repo-1/\n├── playwright.config.ts\n")


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_selectors_pages_and_tests_each_have_their_own_folder(tool_id):
    paths = paths_in(folder_structure(tool_id, NEW)["tree"])
    under = UNDER[tool_id]
    assert {f"{under}locators/", f"{under}pages/", TESTS_FOLDER[tool_id]} <= paths
    assert len({f"{under}locators/", f"{under}pages/", TESTS_FOLDER[tool_id]}) == 3


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_every_page_has_its_own_selectors_and_its_own_test_and_the_base_page_has_none(tool_id):
    paths = paths_in(folder_structure(tool_id, NEW)["tree"])
    under = UNDER[tool_id]
    pages = files_under(paths, f"{under}pages/")
    base = STRUCTURES[tool_id]["base_page"]
    assert base in pages
    feature_pages = [page for page in pages if page != base]
    assert feature_pages
    for page in feature_pages:
        feature = re.match(r"[a-z]+", page).group(0)
        assert any(name.startswith(feature) for name in files_under(paths, f"{under}locators/"))
        assert any(feature in name for name in files_under(paths, TESTS_FOLDER[tool_id]))
    assert not any("base" in name for name in files_under(paths, f"{under}locators/"))


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_locators_and_pages_hold_only_their_own_kind_of_file_in_the_language_of_the_tool(tool_id):
    paths = paths_in(folder_structure(tool_id, NEW)["tree"])
    under = UNDER[tool_id]
    extension = CODE_EXTENSION[E2E_TOOLS[tool_id]["language"]]
    for name in files_under(paths, f"{under}locators/"):
        assert "locators" in name and name.endswith(extension)
    for name in files_under(paths, f"{under}pages/"):
        assert "page" in name and name.endswith(extension)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_tests_are_where_the_tool_looks_for_them_and_named_so_it_finds_them(tool_id):
    paths = paths_in(folder_structure(tool_id, NEW)["tree"])
    names = files_under(paths, TESTS_FOLDER[tool_id])
    pattern = {
        "cypress": r"[a-z]+\.cy\.js",
        "playwright": r"[a-z]+\.spec\.ts",
        "selenium": r"test_[a-z]+\.py",
        "cucumber": r"[a-z]+\.feature|step_definitions/[a-z]+\.steps\.js|support/[a-z]+\.js",
    }[tool_id]
    assert names and all(re.fullmatch(pattern, name) for name in names)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_tool_has_its_settings_file_in_the_project_folder(tool_id):
    tree = folder_structure(tool_id, NEW)["tree"].split("\n")
    assert tree[1] == f"├── {CONFIG_FILE[tool_id]}"


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_workflow_file_is_where_the_deploy_steps_put_it(tool_id):
    paths = paths_in(folder_structure(tool_id, NEW)["tree"])
    assert {".github/", ".github/workflows/", workflow_path(tool_id)} <= paths
    assert [path for path in paths if path.endswith((".yml", ".yaml"))] == [workflow_path(tool_id)]


@pytest.mark.parametrize("source", [NEW, CLONE], ids=["new", "clone"])
@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_notes_are_six_plain_sentences_and_a_note_is_never_empty_or_repeated(tool_id, source):
    notes = folder_structure(tool_id, source)["notes"]
    assert len(notes) == 6
    assert len(set(notes)) == 6
    for note in notes:
        assert isinstance(note, str) and note == note.strip() and note.endswith(".")
        assert "  " not in note


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_every_folder_and_file_a_note_names_is_in_the_tree(tool_id):
    structure = folder_structure(tool_id, NEW)
    paths = paths_in(structure["tree"])
    names = {path.rsplit("/", 1)[-1] for path in paths if not path.endswith("/")}
    text = " ".join(structure["notes"])
    folders = re.findall(r"(?<![\w./-])((?:[A-Za-z0-9_.-]+/)+)", text)
    files = re.findall(r"(?<![\w*.-])([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*\.(?:js|ts|py))(?![\w*])", text)
    assert folders and files
    assert set(folders) <= paths
    assert set(files) <= names


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_notes_for_a_new_project(tool_id):
    assert folder_structure(tool_id, NEW)["notes"] == expected_notes(tool_id, NEW_NOTE_TEXT)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_notes_for_a_cloned_project(tool_id):
    assert folder_structure(tool_id, CLONE)["notes"] == expected_notes(tool_id, CLONE_NOTE_TEXT)


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_notes_never_name_the_settings_file_of_another_tool(tool_id):
    text = " ".join(folder_structure(tool_id, NEW)["notes"])
    for other in E2E_TOOLS:
        if other != tool_id:
            assert CONFIG_FILE[other] not in text


def test_a_new_project_is_told_to_create_the_folders_as_it_goes_and_a_cloned_one_to_keep_its_own():
    new = folder_structure("cypress", NEW)["notes"]
    clone = folder_structure("cypress", CLONE)["notes"]
    assert new[-1] == NEW_NOTE == NEW_NOTE_TEXT and clone[-1] == CLONE_NOTE == CLONE_NOTE_TEXT
    assert new[:-1] == clone[:-1]


@pytest.mark.parametrize("tool_id", list(E2E_TOOLS))
def test_the_tree_and_the_notes_are_tidy_text_with_no_dashes_in_the_sentences(tool_id):
    structure = folder_structure(tool_id, NEW)
    assert set(structure) == {"tree", "notes"}
    assert "\t" not in structure["tree"] and not structure["tree"].endswith("\n")
    assert not re.search(r"[ \t]+$", structure["tree"], re.M)
    for text in [structure["tree"], *structure["notes"]]:
        assert "—" not in text and "–" not in text


def test_changing_what_comes_back_does_not_change_the_next_answer():
    first = folder_structure("selenium", NEW)
    first["notes"].append("changed")
    first["notes"][0] = "changed"
    first["tree"] = "changed"
    again = folder_structure("selenium", NEW)
    assert again["tree"] == TREES["selenium"]
    assert len(again["notes"]) == 6 and again["notes"][0].startswith("locators/ holds")


def test_the_guide_carries_the_folder_structure_for_its_tool_and_source():
    guide = build_guide("cypress", "clone", "https://github.com/o/r")
    assert guide["folder_structure"] == folder_structure("cypress", guide["source"])
    assert guide["folder_structure"]["tree"].startswith("r/\n")
    assert guide["folder_structure"]["notes"][-1] == CLONE_NOTE


def test_the_endpoint_returns_the_folder_structure_with_the_tree_characters_intact():
    client = app_module.app.test_client()
    for tool_id in E2E_TOOLS:
        response = client.post("/e2e/guide", json={"tool": tool_id, "source": "new"})
        assert response.status_code == 200
        assert response.get_json()["folder_structure"] == folder_structure(tool_id, NEW)
        assert response.get_json()["folder_structure"]["tree"] == TREES[tool_id]
