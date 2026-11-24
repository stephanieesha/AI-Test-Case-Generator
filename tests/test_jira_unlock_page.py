"""
Checks the Jira unlock on the page. Fetch from Jira starts locked, unlocks
only after Check Jira succeeds, survives a reload in the same tab, and locks
again when a setting changes. Runs the real page script with Node.js and a
small browser stub. Skipped when Node.js is not installed.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = Path(__file__).parent.parent / "templates" / "index.html"
PAGE_HTML = PAGE.read_text(encoding="utf-8")
SETTINGS = {"site": "mysite", "email": "me@example.com", "api_token": "tok-123"}

# Answers to the page's requests, in order: check, fetch, then a check that fails.
REPLIES = [
    {"status": 200, "body": {"name": "Test User"}},
    {"status": 200, "body": {"requirement": "Login\n\nUsers sign in.", "key": "TCG-4"}},
    {"status": 400, "body": {"error": "Jira rejected the email or API token."}},
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

const stored = new Map();
const sessionStorage = {
  getItem: (key) => (stored.has(key) ? stored.get(key) : null),
  setItem: (key, value) => { stored.set(key, String(value)); },
  removeItem: (key) => { stored.delete(key); },
};

const sent = [];
const sandbox = {
  document: {
    getElementById: element,
    createElement: () => ({ set textContent(value) {}, get innerHTML() { return ''; } }),
  },
  sessionStorage,
  window: {},
  navigator: { clipboard: { writeText() {} } },
  fetch: async (url, options) => {
    sent.push({ url, body: JSON.parse(options.body) });
    const reply = replies.shift();
    return { ok: reply.status < 400, status: reply.status, json: async () => reply.body };
  },
};
vm.createContext(sandbox);
vm.runInContext(script, sandbox);

const out = {};
(async () => {
  out.lockedOnLoad = element('fetchJiraBtn').disabled;

  element('jiraSite').value = 'mysite';
  element('jiraEmail').value = 'me@example.com';
  element('jiraToken').value = 'tok-123';
  sandbox.saveJiraSettings();
  await sandbox.checkJira();
  out.unlockedAfterCheck = element('fetchJiraBtn').disabled === false;
  out.statusAfterCheck = element('jiraStatus').textContent;

  sandbox.loadJiraSettings();
  out.unlockedAfterReload = element('fetchJiraBtn').disabled === false;

  element('jiraKey').value = 'tcg-4';
  await sandbox.fetchJira();
  out.requirement = element('requirement').value;

  element('jiraSite').value = 'othersite';
  sandbox.saveJiraSettings();
  out.lockedAfterEdit = element('fetchJiraBtn').disabled;

  await sandbox.checkJira();
  out.lockedAfterFailedCheck = element('fetchJiraBtn').disabled;
  out.errorAfterFailedCheck = element('jiraStatus').textContent;

  console.log(JSON.stringify({ ...out, sent }));
})().catch((err) => { console.error(err); process.exit(1); });
"""


@pytest.fixture(scope="module")
def run():
    if shutil.which("node") is None:
        pytest.skip("runs the page script with Node.js")
    code = (NODE_RUNNER.replace("__PAGE__", json.dumps(str(PAGE)))
                       .replace("__REPLIES__", json.dumps(REPLIES)))
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)


def test_the_markup_starts_with_fetch_locked():
    assert re.search(r'<input type="text" id="jiraKey"[^>]*\bdisabled\b', PAGE_HTML)
    assert re.search(r'<button[^>]*id="fetchJiraBtn"[^>]*\bdisabled\b', PAGE_HTML)
    assert 'type="password" id="jiraToken"' in PAGE_HTML


def test_fetch_is_locked_when_the_page_loads(run):
    assert run["lockedOnLoad"] is True


def test_a_successful_check_unlocks_fetch(run):
    assert run["unlockedAfterCheck"] is True
    assert run["statusAfterCheck"] == "Connected as Test User"


def test_the_connection_survives_a_reload_in_the_same_tab(run):
    assert run["unlockedAfterReload"] is True


def test_the_settings_go_in_the_body_never_in_the_url(run):
    assert run["sent"][0] == {"url": "/jira/check", "body": SETTINGS}
    assert run["sent"][1] == {"url": "/jira/tcg-4", "body": SETTINGS}


def test_fetch_puts_the_ticket_into_the_requirement_box(run):
    assert run["requirement"] == "Login\n\nUsers sign in."


def test_editing_a_setting_locks_fetch_again(run):
    assert run["lockedAfterEdit"] is True


def test_a_failed_check_keeps_fetch_locked_and_says_why(run):
    assert run["lockedAfterFailedCheck"] is True
    assert "rejected" in run["errorAfterFailedCheck"]
