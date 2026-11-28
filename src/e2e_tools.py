"""
The end-to-end tools the page can set up: the choices in the "Automate these test cases" box.

Each tool has the language its steps are written for and one line on what it is good at. The tools
are listed in the order the page shows them.
"""

E2E_TOOLS = {
    "cypress": {
        "name": "Cypress",
        "language": "JavaScript",
        "summary": "Runs next to your app in the browser, with an interactive runner that shows every step as it happens.",
    },
    "playwright": {
        "name": "Playwright",
        "language": "TypeScript",
        "summary": "Drives Chromium, Firefox and WebKit from one test run, and waits for the page by itself.",
    },
    "selenium": {
        "name": "Selenium",
        "language": "Python",
        "summary": "The long-standing browser driver, used here with pytest. It also has Java, JavaScript and C# versions.",
    },
    "cucumber": {
        "name": "Cucumber",
        "language": "JavaScript",
        "summary": "Runs plain-language Given/When/Then files, the same shape as the BDD test cases. Playwright drives the browser.",
    },
}
