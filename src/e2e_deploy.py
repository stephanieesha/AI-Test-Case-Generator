"""
The deploy steps for each end-to-end tool: put the tests on GitHub and have GitHub Actions run them.

Each tool has one workflow file. It runs the tests on every push and pull request to main, and from
the Actions tab on request, then keeps the report as a download. Nothing is run or sent anywhere
here, the page only shows the steps and the file.
"""

WORKFLOW_FOLDER = ".github/workflows"
BRANCH = "add-e2e-workflow"

WORKFLOWS = {
    "cypress": """\
name: Cypress tests

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      CYPRESS_BASE_URL: ${{ vars.BASE_URL }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: lts/*
      - name: Install the packages
        run: npm ci
      - name: Install the Cypress app
        run: npx cypress install
      - name: Run the tests
        run: npx cypress run
      - name: Keep the screenshots and videos
        uses: actions/upload-artifact@v7
        if: ${{ !cancelled() }}
        with:
          name: cypress-results
          path: |
            cypress/screenshots
            cypress/videos
          if-no-files-found: ignore
""",
    "playwright": """\
name: Playwright tests

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      BASE_URL: ${{ vars.BASE_URL }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: lts/*
      - name: Install the packages
        run: npm ci
      - name: Install the browsers
        run: npx playwright install --with-deps
      - name: Run the tests
        run: npx playwright test
      - name: Keep the report
        uses: actions/upload-artifact@v7
        if: ${{ !cancelled() }}
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
""",
    "selenium": """\
name: Selenium tests

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      BASE_URL: ${{ vars.BASE_URL }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-python@v6
        with:
          python-version: "3.12"
      - name: Install the packages
        run: pip install -r requirements.txt
      - name: Run the tests
        run: python -m pytest --junitxml=junit.xml
      - name: Keep the results
        uses: actions/upload-artifact@v7
        if: ${{ !cancelled() }}
        with:
          name: selenium-results
          path: junit.xml
          if-no-files-found: ignore
""",
    "cucumber": """\
name: Cucumber tests

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]
  workflow_dispatch:

jobs:
  test:
    runs-on: ubuntu-latest
    timeout-minutes: 30
    env:
      BASE_URL: ${{ vars.BASE_URL }}
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v6
        with:
          node-version: lts/*
      - name: Install the packages
        run: npm ci
      - name: Install the browsers
        run: npx playwright install --with-deps
      - name: Run the features
        run: npx cucumber-js --format progress --format html:cucumber-report.html
      - name: Keep the report
        uses: actions/upload-artifact@v7
        if: ${{ !cancelled() }}
        with:
          name: cucumber-report
          path: cucumber-report.html
          if-no-files-found: ignore
""",
}

# Lines for .gitignore in a new project, so packages, virtual environments and reports stay out of git.
GITIGNORE = {
    "cypress": "node_modules/\ncypress/screenshots/\ncypress/videos/\n.env\n",
    "playwright": "node_modules/\n/test-results/\n/playwright-report/\n/blob-report/\n/playwright/.cache/\n.env\n",
    "selenium": ".venv/\n__pycache__/\n.pytest_cache/\njunit.xml\n.env\n",
    "cucumber": "node_modules/\ncucumber-report.html\n.env\n",
}

GITIGNORE_STEP = {
    "title": "Keep generated files out of git",
    "detail": "Create a file called .gitignore in the project folder with these lines.",
}
PLAYWRIGHT_GITIGNORE_DETAIL = "Playwright already created a .gitignore. Check that it has these lines and add any that are missing."

VARIABLE = (
    "On GitHub, open the repository's Settings, then Secrets and variables, then Actions, then the Variables tab. "
    "Add a repository variable called BASE_URL with the address of the site the tests should open. "
)

POINT_AT_THE_SITE = {
    "cypress": VARIABLE + "The workflow gives it to Cypress as CYPRESS_BASE_URL, which Cypress uses as its baseUrl, so the config file does not need to change.",
    "playwright": VARIABLE + "The workflow gives it to the tests as an environment variable. Make the tests read it, for example by setting baseURL: process.env.BASE_URL under use in playwright.config.ts.",
    "selenium": VARIABLE + 'The workflow gives it to the tests as an environment variable. Make the tests read it, for example os.environ["BASE_URL"]. On GitHub there is no screen, so start the browser headless, for example options.add_argument("--headless=new") for Chrome.',
    "cucumber": VARIABLE + "The workflow gives it to the tests as an environment variable. Make the tests read it, for example process.env.BASE_URL in the hooks that open the page.",
}

WATCH_THE_RUN = {
    "title": "Watch the run",
    "detail": "Open the Actions tab of the repository. You can also start the workflow yourself with Run workflow. When it finishes, the test report is attached to the run under Artifacts.",
}


def workflow_path(tool_id):
    return f"{WORKFLOW_FOLDER}/{tool_id}.yml"


def deploy_steps(tool_id, source):
    """Return the deploy steps as a list of {"title", "detail" (optional), "commands" (optional), "file" (optional)} dictionaries."""
    path = workflow_path(tool_id)
    workflow = {"path": path, "content": WORKFLOWS[tool_id]}
    point = {"title": "Point the tests at your site", "detail": POINT_AT_THE_SITE[tool_id]}

    if source["type"] == "clone":
        steps = [
            {
                "title": "Create a branch",
                "detail": "Work on a branch so the workflow can be reviewed before it reaches main.",
                "commands": [f"git switch -c {BRANCH}"],
            },
            {
                "title": "Add the workflow file",
                "detail": "Create the folders .github and workflows inside it, then the file below. If the repository already has a workflow that runs these tests, edit that one instead.",
                "file": workflow,
            },
            point,
            {
                "title": "Commit and push the branch",
                "detail": "Add any test files you changed to read BASE_URL in the same commit.",
                "commands": [
                    f"git add {path}",
                    'git commit -m "Run the end-to-end tests on GitHub Actions"',
                    f"git push -u origin {BRANCH}",
                ],
            },
            {
                "title": "Open a pull request",
                "detail": f"On GitHub, open a pull request from {BRANCH} into main. The workflow runs on the pull request and its result shows there. If you are not allowed to push to the repository, fork it on GitHub first, clone your fork instead of the original, and follow the same steps.",
            },
            WATCH_THE_RUN,
        ]
    else:
        ignore = {
            **GITIGNORE_STEP,
            "file": {"path": ".gitignore", "content": GITIGNORE[tool_id]},
        }
        if tool_id == "playwright":
            ignore["detail"] = PLAYWRIGHT_GITIGNORE_DETAIL
        steps = [
            {
                "title": "Create an empty repository on GitHub",
                "detail": "On github.com choose New repository and give it a name. Leave it empty: do not add a README, a .gitignore or a license. Keep the page open, because it shows the link you need in the push step.",
            },
            ignore,
        ]
        if tool_id == "selenium":
            steps.append(
                {
                    "title": "Save the packages the tests need",
                    "detail": "The workflow installs them from requirements.txt.",
                    "commands": ["pip freeze > requirements.txt"],
                }
            )
        steps += [
            {
                "title": "Add the workflow file",
                "detail": "Create the folders .github and workflows inside it, then the file below. It runs the tests on every push and pull request to main, and when you press Run workflow in the Actions tab.",
                "file": workflow,
            },
            point,
            {
                "title": "Commit and push",
                "detail": "Replace YOUR-USERNAME and YOUR-REPOSITORY with the ones GitHub showed when you created the repository.",
                "commands": [
                    "git init",
                    "git add .",
                    'git commit -m "Add the end-to-end tests"',
                    "git branch -M main",
                    "git remote add origin https://github.com/YOUR-USERNAME/YOUR-REPOSITORY.git",
                    "git push -u origin main",
                ],
            },
            WATCH_THE_RUN,
        ]
    return [_copy(step) for step in steps]


def _copy(step):
    copy = dict(step)
    if "commands" in copy:
        copy["commands"] = list(copy["commands"])
    if "file" in copy:
        copy["file"] = dict(copy["file"])
    return copy
