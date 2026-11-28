"""
Checks the "Automate these test cases" box on the page: the choices, and what the page does with
them when "Show the steps" is pressed. The page script runs for real with Node.js and a small
browser stub, so this file is skipped for the script checks when Node.js is not installed.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = Path(__file__).parent.parent / "templates" / "index.html"
PAGE_HTML = PAGE.read_text(encoding="utf-8")

# Class names the Cypress suite for this page looks for. Nothing the box draws may reuse them.
CLASSES_USED_BY_THE_CYPRESS_SUITE = {
    "panel", "style-option", "jira-row", "error-box", "empty-state", "test-case", "step-case",
    "step-row", "step-num", "section-label", "ambiguity-box", "meta", "copy-btn", "action", "expected",
}

PLAYWRIGHT_NEW = {
    "tool": {"id": "playwright", "name": "Playwright", "language": "TypeScript"},
    "source": {"type": "new", "folder": "my-e2e-tests"},
    "install_steps": [
        {"title": "Check Node.js", "detail": "Use a current LTS version.", "commands": ["node --version"]},
        {"title": "Create the project folder", "commands": ["mkdir my-e2e-tests", "cd my-e2e-tests"]},
    ],
}
CYPRESS_CLONE = {
    "tool": {"id": "cypress", "name": "Cypress", "language": "JavaScript"},
    "source": {
        "type": "clone",
        "owner": "stephanieesha",
        "repo": "AI-Test-Case-Generator-e2e-test",
        "url": "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test.git",
        "folder": "AI-Test-Case-Generator-e2e-test",
    },
    "install_steps": [
        {
            "title": "Clone the repository",
            "commands": [
                "git clone https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test.git",
                "cd AI-Test-Case-Generator-e2e-test",
            ],
        },
    ],
}

HOSTILE_CLONE = {
    "tool": {"id": "x", "name": "<b>Tool</b>", "language": "<i>Language</i>"},
    "source": {"type": "clone", "owner": "<u>owner</u>", "repo": "<s>repo</s>", "url": "u", "folder": "<s>repo</s>"},
    "install_steps": [
        {"title": "<b>Step</b>", "detail": "<i>Detail</i> & more", "commands": ["echo <u>one</u>", "a && b"]},
    ],
}
HOSTILE_NEW = {
    "tool": {"id": "x", "name": "Tool", "language": "Language"},
    "source": {"type": "new", "folder": "<em>folder</em>"},
}

# What the server answers to each request the script makes below, in order.
REPLIES = [
    {"status": 400, "body": {"error": "Choose the tool you will write the automated tests in."}},
    {"status": 200, "body": PLAYWRIGHT_NEW},
    {"status": 200, "body": CYPRESS_CLONE},
    {"status": 200, "body": PLAYWRIGHT_NEW},
    {"status": 400, "body": {"error": "<img src=x onerror=alert(1)>"}},
    {"status": 200, "body": PLAYWRIGHT_NEW, "hold": True},
    {"status": 400, "body": {"error": "Choose the tool you will write the automated tests in."}, "hold": True},
    {"reject": "Failed to fetch"},
    {"status": 500, "body": {}},
    {"status": 200, "body": HOSTILE_CLONE},
    {"status": 200, "body": HOSTILE_NEW},
]

NODE_RUNNER = r"""
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(__PAGE__, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const replies = __REPLIES__;

const elements = {};
function element(id) {
  if (!elements[id]) {
    elements[id] = { value: '', textContent: '', className: '', disabled: false, hidden: false, innerHTML: '', addEventListener() {} };
  }
  return elements[id];
}
function textNode() {
  let text = '';
  return {
    set textContent(value) { text = String(value); },
    get innerHTML() { return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); },
  };
}

const picked = { e2e_tool: null, e2e_source: 'new' };
function querySelector(selector) {
  const match = selector.match(/^input\[name="([a-z0-9_]+)"\]:checked$/);
  if (!match || !(match[1] in picked)) throw new Error('unexpected selector: ' + selector);
  return picked[match[1]] === null ? null : { value: picked[match[1]] };
}

const sent = [];
let release = null;
const sandbox = {
  document: { getElementById: element, createElement: textNode, querySelector },
  sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  window: {},
  navigator: { clipboard: { writeText() {} } },
  fetch: async (url, options) => {
    sent.push({ url, method: options.method, body: JSON.parse(options.body) });
    const reply = replies.shift();
    if (reply.reject) throw new Error(reply.reject);
    if (reply.hold) await new Promise((resolve) => { release = resolve; });
    return { ok: reply.status < 400, status: reply.status, json: async () => reply.body };
  },
};
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const guide = () => element('e2eGuide').innerHTML;
const out = {};

(async () => {
  out.emptyOnLoad = guide() === '';

  await sandbox.loadGuide();
  out.noTool = guide();

  picked.e2e_tool = 'playwright';
  await sandbox.loadGuide();
  out.newProject = guide();
  out.buttonAfterSuccess = element('e2eGo').disabled;

  sandbox.clearGuide();
  out.afterClear = guide();

  picked.e2e_tool = 'cypress';
  picked.e2e_source = 'clone';
  element('e2eRepoUrl').value = '  https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test  ';
  await sandbox.loadGuide();
  out.clone = guide();

  picked.e2e_source = 'new';
  await sandbox.loadGuide();
  out.newWithLinkStillTyped = guide();

  picked.e2e_source = 'clone';
  await sandbox.loadGuide();
  out.escapedError = guide();

  picked.e2e_source = 'new';
  const waiting = sandbox.loadGuide();
  out.buttonWhileWaiting = element('e2eGo').disabled;
  out.guideWhileWaiting = guide();
  picked.e2e_source = 'clone';
  sandbox.clearGuide();
  release();
  await waiting;
  out.staleAnswerShown = guide();
  out.buttonAfterStale = element('e2eGo').disabled;

  picked.e2e_source = 'new';
  const waitingForAnError = sandbox.loadGuide();
  picked.e2e_source = 'clone';
  sandbox.clearGuide();
  release();
  await waitingForAnError;
  out.staleErrorShown = guide();

  await sandbox.loadGuide();
  out.offline = guide();
  out.buttonAfterOffline = element('e2eGo').disabled;

  await sandbox.loadGuide();
  out.noMessage = guide();

  await sandbox.loadGuide();
  out.hostileClone = guide();

  picked.e2e_source = 'new';
  await sandbox.loadGuide();
  out.hostileNew = guide();

  console.log(JSON.stringify({ ...out, sent }));
})().catch((err) => { console.error(err); process.exit(1); });
"""


@pytest.fixture(scope="module")
def run():
    if shutil.which("node") is None:
        pytest.skip("runs the page script with Node.js")
    code = NODE_RUNNER.replace("__PAGE__", json.dumps(str(PAGE))).replace("__REPLIES__", json.dumps(REPLIES))
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def markup_of(pattern):
    return re.findall(pattern, PAGE_HTML)


def test_the_page_offers_a_new_project_first_and_it_is_the_one_chosen_at_the_start():
    radios = markup_of(r'<input[^>]*name="e2e_source"[^>]*>')
    assert [re.search(r'value="([^"]*)"', radio).group(1) for radio in radios] == ["new", "clone"]
    assert ["checked" in radio for radio in radios] == [True, False]


def test_the_repository_link_box_is_a_text_box_shown_only_while_clone_is_chosen():
    assert re.search(r'<input type="text" class="e2e-repo" id="e2eRepoUrl"[^>]*placeholder="https://github.com/owner/repo"', PAGE_HTML)
    assert ".e2e-repo { display: none;" in PAGE_HTML
    assert 'input[name="e2e_source"][value="clone"]:checked) .e2e-repo { display: block; }' in PAGE_HTML


def test_changing_any_choice_or_the_link_clears_a_guide_that_is_showing():
    for tag in markup_of(r'<input[^>]*name="e2e_(?:tool|source)"[^>]*>'):
        assert 'onchange="clearGuide()"' in tag
    assert re.search(r'id="e2eRepoUrl"[^>]*oninput="clearGuide\(\)"', PAGE_HTML)


def test_the_button_asks_for_the_guide_and_the_guide_has_a_place_to_show():
    assert re.search(r'<button[^>]*id="e2eGo"[^>]*onclick="loadGuide\(\)"', PAGE_HTML)
    assert PAGE_HTML.index('id="e2eGo"') < PAGE_HTML.index('id="e2eGuide"')


def test_nothing_is_shown_before_the_button_is_pressed(run):
    assert run["emptyOnLoad"] is True


def test_the_request_names_the_choices_and_goes_to_the_guide_endpoint(run):
    first, second = run["sent"][0], run["sent"][1]
    assert first == {"url": "/e2e/guide", "method": "POST", "body": {"tool": "", "source": "new", "repo_url": ""}}
    assert second == {"url": "/e2e/guide", "method": "POST", "body": {"tool": "playwright", "source": "new", "repo_url": ""}}


def test_a_missing_choice_shows_the_servers_message(run):
    assert run["noTool"] == '<div class="e2e-error">Choose the tool you will write the automated tests in.</div>'


def test_a_new_project_shows_the_tool_and_the_folder(run):
    assert "Playwright" in run["newProject"]
    assert "TypeScript" in run["newProject"]
    assert "New project in a folder called my-e2e-tests" in run["newProject"]


def test_a_cloned_project_shows_the_repository_and_sends_the_link_trimmed(run):
    assert "Cypress" in run["clone"]
    assert "Clone stephanieesha/AI-Test-Case-Generator-e2e-test from GitHub" in run["clone"]
    assert run["sent"][2]["body"] == {
        "tool": "cypress",
        "source": "clone",
        "repo_url": "https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test",
    }


def test_the_link_is_not_sent_for_a_new_project_even_if_one_is_still_typed(run):
    assert run["sent"][3]["body"] == {"tool": "cypress", "source": "new", "repo_url": ""}
    assert "New project in a folder called my-e2e-tests" in run["newWithLinkStillTyped"]


def test_the_servers_message_is_escaped_before_it_is_shown(run):
    assert run["escapedError"] == '<div class="e2e-error">&lt;img src=x onerror=alert(1)&gt;</div>'


def test_clearing_removes_the_guide(run):
    assert run["afterClear"] == ""


def test_the_button_is_off_while_waiting_and_back_on_after_every_outcome(run):
    assert run["buttonWhileWaiting"] is True
    assert run["buttonAfterSuccess"] is False
    assert run["buttonAfterStale"] is False
    assert run["buttonAfterOffline"] is False


def test_an_answer_that_arrives_after_the_choice_changed_is_not_shown(run):
    assert run["guideWhileWaiting"] == ""
    assert run["staleAnswerShown"] == ""


def test_an_error_that_arrives_after_the_choice_changed_is_not_shown_either(run):
    assert run["staleErrorShown"] == ""


def test_the_tool_and_the_repository_are_escaped_before_they_are_shown(run):
    for html in (run["hostileClone"], run["hostileNew"]):
        assert not re.search(r"<(?:b|i|u|s|em)>", html)
    assert "&lt;b&gt;Tool&lt;/b&gt;" in run["hostileClone"]
    assert "&lt;i&gt;Language&lt;/i&gt;" in run["hostileClone"]
    assert "&lt;u&gt;owner&lt;/u&gt;/&lt;s&gt;repo&lt;/s&gt;" in run["hostileClone"]
    assert "&lt;em&gt;folder&lt;/em&gt;" in run["hostileNew"]


def test_a_failed_request_shows_why_and_a_reply_with_no_message_gets_a_plain_one(run):
    assert run["offline"] == '<div class="e2e-error">Failed to fetch</div>'
    assert run["noMessage"] == '<div class="e2e-error">Could not build the steps</div>'


def test_what_the_box_draws_never_reuses_a_class_the_cypress_suite_looks_for(run):
    drawn = [run[key] for key in ("noTool", "newProject", "clone", "escapedError", "offline", "noMessage", "hostileClone")]
    classes = {name for html in drawn for value in re.findall(r'class="([^"]*)"', html) for name in value.split()}
    assert classes
    assert not classes & CLASSES_USED_BY_THE_CYPRESS_SUITE
    assert not any("<h2" in html or "<h3" in html for html in drawn)


def test_the_install_steps_show_as_a_numbered_list_with_each_set_of_commands_in_a_box(run):
    shown = run["newProject"]
    assert '<div class="e2e-heading">Install</div><ol class="e2e-steps">' in shown
    assert shown.count("<li>") == 2
    assert (
        '<li><div class="e2e-step-title">Check Node.js</div>'
        '<div class="e2e-step-detail">Use a current LTS version.</div>'
        '<pre class="e2e-commands">node --version</pre></li>'
    ) in shown
    assert shown.endswith("</ol>")


def test_a_step_with_no_detail_has_no_empty_detail_line_and_keeps_one_command_per_line(run):
    assert (
        '<li><div class="e2e-step-title">Create the project folder</div>'
        '<pre class="e2e-commands">mkdir my-e2e-tests\ncd my-e2e-tests</pre></li>'
    ) in run["newProject"]


def test_a_cloned_project_starts_with_the_clone_command(run):
    assert (
        '<pre class="e2e-commands">git clone https://github.com/stephanieesha/AI-Test-Case-Generator-e2e-test.git'
        "\ncd AI-Test-Case-Generator-e2e-test</pre>"
    ) in run["clone"]


def test_the_steps_are_escaped_before_they_are_shown(run):
    shown = run["hostileClone"]
    assert "&lt;b&gt;Step&lt;/b&gt;" in shown
    assert "&lt;i&gt;Detail&lt;/i&gt; &amp; more" in shown
    assert "echo &lt;u&gt;one&lt;/u&gt;\na &amp;&amp; b" in shown
    assert not re.search(r"<(?:b|i|u|s)>", shown)


def test_there_is_no_install_heading_when_the_answer_has_no_steps(run):
    assert "e2e-heading" not in run["hostileNew"]
    assert "<ol" not in run["hostileNew"]


def test_the_markup_of_the_box_never_reuses_a_class_the_cypress_suite_looks_for():
    start = PAGE_HTML.index('class="e2e-box"')
    box = PAGE_HTML[start:PAGE_HTML.index("<script", start)]
    classes = {name for value in re.findall(r'class="([^"]*)"', box) for name in value.split()}
    assert not classes & CLASSES_USED_BY_THE_CYPRESS_SUITE
