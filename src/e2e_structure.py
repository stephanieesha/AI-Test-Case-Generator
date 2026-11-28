"""
The folder structure for each end-to-end tool, laid out as a page object model: the selectors in one
folder, one page class per page in another, and the tests in their own folder.

Only the folders and a few example file names are shown, as a tree with a short note on what each
folder is for. Nothing is created anywhere.
"""

from e2e_deploy import workflow_path

# Each tool has the folders it expects, plus the page object folders. "under" is the folder that holds
# locators/ and pages/, and "base_page" is the file in pages/ that every page class extends.
STRUCTURES = {
    "cypress": {
        "layout": [
            "cypress.config.js",
            "package.json",
            (
                "cypress",
                [
                    ("e2e", ["login.cy.js"]),
                    ("fixtures", ["users.json"]),
                    ("locators", ["login.locators.js"]),
                    ("pages", ["base.page.js", "login.page.js"]),
                    ("support", ["commands.js", "e2e.js"]),
                ],
            ),
        ],
        "under": "cypress/",
        "base_page": "base.page.js",
        "tests": "cypress/e2e/ holds the specs. They call page methods and never use selectors directly.",
        "setup": (
            "cypress.config.js holds the settings, such as the base URL. cypress/fixtures/ holds test data, "
            "and cypress/support/ holds the custom commands and the setup that every spec loads."
        ),
    },
    "playwright": {
        "layout": [
            "playwright.config.ts",
            "package.json",
            ("locators", ["login.locators.ts"]),
            ("pages", ["base.page.ts", "login.page.ts"]),
            ("tests", ["login.spec.ts"]),
        ],
        "under": "",
        "base_page": "base.page.ts",
        "tests": "tests/ holds the tests. They call page methods and never use selectors directly.",
        "setup": "playwright.config.ts holds the settings, such as the browsers, the base URL and where the tests are.",
    },
    "selenium": {
        "layout": [
            "conftest.py",
            "requirements.txt",
            ("locators", ["login_locators.py"]),
            ("pages", ["base_page.py", "login_page.py"]),
            ("tests", ["test_login.py"]),
        ],
        "under": "",
        "base_page": "base_page.py",
        "tests": (
            "tests/ holds the tests, in files named test_*.py so pytest finds them. "
            "They call page methods and never use selectors directly."
        ),
        "setup": (
            "conftest.py holds the pytest fixtures, such as starting and closing the browser. "
            "Keep it in the project folder, next to locators/ and pages/, so the tests can import them."
        ),
    },
    "cucumber": {
        "layout": [
            "cucumber.js",
            "package.json",
            (
                "features",
                [
                    "login.feature",
                    ("step_definitions", ["login.steps.js"]),
                    ("support", ["hooks.js", "world.js"]),
                ],
            ),
            ("locators", ["login.locators.js"]),
            ("pages", ["base.page.js", "login.page.js"]),
        ],
        "under": "",
        "base_page": "base.page.js",
        "tests": (
            "features/ holds the .feature files with the Given, When and Then lines, and "
            "features/step_definitions/ links each line to page methods. The steps never use selectors directly."
        ),
        "setup": (
            "features/support/ holds the hooks that open and close the browser and the world that gives each "
            "scenario its page objects. cucumber.js holds the settings."
        ),
    },
}

NEW_NOTE = (
    "login is only an example, so name the files after the feature you test. "
    "You do not need every file yet. Create the folders as you write your first test."
)
CLONE_NOTE = (
    "login is only an example, so name the files after the feature you test. "
    "Keep the folders the repository already has and add only the ones that are missing, instead of moving files."
)


def folder_structure(tool_id, source):
    """Return the folder tree as text and the notes that explain it, as {"tree", "notes"}."""
    structure = STRUCTURES[tool_id]
    under = structure["under"]
    layout = [*structure["layout"], _workflow_entry(tool_id)]
    notes = [
        f"{under}locators/ holds the selectors, one file per page, and nothing else.",
        (
            f"{under}pages/ holds one class per page. Each page class extends the base page, uses the locators "
            "of its page and has a method for each thing a person does there, such as logging in."
        ),
        f"{structure['base_page']} holds what every page shares, such as opening an address and waiting for the page to load.",
        structure["tests"],
        structure["setup"],
        CLONE_NOTE if source["type"] == "clone" else NEW_NOTE,
    ]
    return {"tree": "\n".join([f"{source['folder']}/", *_lines(layout, "")]), "notes": notes}


def _workflow_entry(tool_id):
    *folders, name = workflow_path(tool_id).split("/")
    entry = name
    for folder in reversed(folders):
        entry = (folder, [entry])
    return entry


def _lines(entries, prefix):
    lines = []
    for index, entry in enumerate(entries):
        last = index == len(entries) - 1
        name, children = (entry, None) if isinstance(entry, str) else entry
        lines.append(prefix + ("└── " if last else "├── ") + (name if children is None else name + "/"))
        if children is not None:
            lines += _lines(children, prefix + ("    " if last else "│   "))
    return lines
