"""
The install steps for each end-to-end tool, for a new project and for one cloned from GitHub.

The commands follow each tool's own install guide. Nothing is run here, the page only shows them.
The folder and clone link put into the commands come from build_guide, which has already checked
them, so they only hold characters that are safe in a shell command.
"""

CHECK_NODE = {
    "title": "Check Node.js",
    "detail": "Use a current LTS version of Node.js. If this prints nothing or an old version, install the LTS version from nodejs.org.",
    "commands": ["node --version"],
}

CHECK_PYTHON = {
    "title": "Check Python",
    "detail": "Selenium needs Python 3.10 or newer. If this prints nothing or an older version, install Python from python.org. On Windows, use py instead of python3.",
    "commands": ["python3 --version"],
}

PACKAGES_LOCKED = "Use npm install instead if the repository has no package-lock.json."
README_HINT = "Check the repository's README for anything the tests expect first, such as the address of the site they test."

VIRTUAL_ENVIRONMENT = {
    "title": "Create a virtual environment",
    "detail": "On Windows, activate it with .venv\\Scripts\\activate instead.",
    "commands": ["python3 -m venv .venv", "source .venv/bin/activate"],
}

INSTALL = {
    "cypress": {
        "check": CHECK_NODE,
        "new": [
            {"title": "Create package.json", "commands": ["npm init -y"]},
            {
                "title": "Install Cypress",
                "detail": "Newer versions of npm can skip the download Cypress does when it installs, so the last two commands make sure the Cypress app is there and starts.",
                "commands": ["npm install cypress --save-dev", "npx cypress install", "npx cypress verify"],
            },
            {
                "title": "Open Cypress once",
                "detail": "Choose E2E Testing and keep the configuration files it suggests. Pick a browser, then choose Scaffold example specs so there is something to run.",
                "commands": ["npx cypress open"],
            },
            {
                "title": "Run the tests from the terminal",
                "detail": "The example specs should pass.",
                "commands": ["npx cypress run"],
            },
        ],
        "clone": [
            {"title": "Install the packages", "detail": PACKAGES_LOCKED, "commands": ["npm ci"]},
            {
                "title": "Download the Cypress app",
                "detail": "Newer versions of npm can skip the download Cypress does when it installs, so run these to make sure the Cypress app is there and starts.",
                "commands": ["npx cypress install", "npx cypress verify"],
            },
            {"title": "Run the tests", "detail": README_HINT, "commands": ["npx cypress run"]},
        ],
    },
    "playwright": {
        "check": CHECK_NODE,
        "new": [
            {
                "title": "Set up Playwright",
                "detail": "Pick TypeScript when it asks. Keep the tests folder name it suggests, answer no to adding a GitHub Actions workflow because the deploy steps give you one, and answer yes to installing the browsers.",
                "commands": ["npm init playwright@latest"],
            },
            {
                "title": "Run the example tests",
                "detail": "The project comes with example tests, so these should pass. Open the report with npx playwright show-report.",
                "commands": ["npx playwright test"],
            },
        ],
        "clone": [
            {"title": "Install the packages", "detail": PACKAGES_LOCKED, "commands": ["npm ci"]},
            {"title": "Download the browsers", "commands": ["npx playwright install"]},
            {
                "title": "Run the tests",
                "detail": README_HINT + " Open the report with npx playwright show-report.",
                "commands": ["npx playwright test"],
            },
        ],
    },
    "selenium": {
        "check": CHECK_PYTHON,
        "new": [
            VIRTUAL_ENVIRONMENT,
            {
                "title": "Install Selenium and pytest",
                "detail": "Selenium Manager downloads the browser driver for you when the first test starts, so you only need Chrome or Firefox installed.",
                "commands": ["pip install selenium pytest"],
            },
            {
                "title": "Check the install",
                "detail": "Both commands should print a version number. Run your tests with python3 -m pytest once you have written some.",
                "commands": ['python3 -c "import selenium; print(selenium.__version__)"', "python3 -m pytest --version"],
            },
        ],
        "clone": [
            VIRTUAL_ENVIRONMENT,
            {
                "title": "Install the packages",
                "detail": "If the repository lists its packages somewhere else, such as pyproject.toml, install them from there.",
                "commands": ["pip install -r requirements.txt"],
            },
            {"title": "Run the tests", "detail": README_HINT, "commands": ["python3 -m pytest"]},
        ],
    },
    "cucumber": {
        "check": CHECK_NODE,
        "new": [
            {"title": "Create package.json", "commands": ["npm init -y"]},
            {
                "title": "Install Cucumber and Playwright",
                "detail": "Cucumber runs the Given/When/Then files and Playwright drives the browser.",
                "commands": ["npm install --save-dev @cucumber/cucumber playwright"],
            },
            {"title": "Download the browsers", "commands": ["npx playwright install"]},
            {
                "title": "Check the install",
                "detail": "It should print a version number. Run your features with npx cucumber-js once you have written some.",
                "commands": ["npx cucumber-js --version"],
            },
        ],
        "clone": [
            {"title": "Install the packages", "detail": PACKAGES_LOCKED, "commands": ["npm ci"]},
            {"title": "Download the browsers", "commands": ["npx playwright install"]},
            {"title": "Run the features", "detail": README_HINT, "commands": ["npx cucumber-js"]},
        ],
    },
}


def install_steps(tool_id, source):
    """Return the install steps as a list of {"title", "detail" (optional), "commands"} dictionaries."""
    tool = INSTALL[tool_id]
    if source["type"] == "clone":
        first = {
            "title": "Clone the repository",
            "commands": [f"git clone {source['url']}", f"cd {source['folder']}"],
        }
        rest = tool["clone"]
    else:
        first = {
            "title": "Create the project folder",
            "commands": [f"mkdir {source['folder']}", f"cd {source['folder']}"],
        }
        rest = tool["new"]
    return [_copy(step) for step in [tool["check"], first, *rest]]


def _copy(step):
    return {**step, "commands": list(step["commands"])}
