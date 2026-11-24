"""
Renders the results panel with Node.js, using the real page script and a
small browser stub, to check the what-to-validate section and that its text
is escaped. Skipped when Node.js is not installed.
"""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

PAGE = Path(__file__).parent.parent / "templates" / "index.html"

NODE_RUNNER = r"""
const fs = require('fs');
const vm = require('vm');

const html = fs.readFileSync(__PAGE__, 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];

const elements = {};
function element(id) {
  if (!elements[id]) {
    elements[id] = { value: '', innerHTML: '', addEventListener() {} };
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

const sandbox = {
  document: { getElementById: element, createElement: textNode },
  sessionStorage: { getItem() { return null; }, setItem() {} },
  window: {},
  navigator: { clipboard: { writeText() {} } },
  data: __DATA__,
};
vm.createContext(sandbox);
vm.runInContext(script, sandbox);
vm.runInContext('renderResult(data);', sandbox);
console.log(JSON.stringify({ output: elements['output'].innerHTML }));
"""

SAMPLE = {
    "style": "bdd",
    "test_cases": [{"title": "Login", "steps": ["Given a user", "Then they see the dashboard"]}],
    "ambiguity_notes": [],
    "retrieved_examples": ["corpus-001"],
    "validation_summary": [{"title": "Login", "checks": ["they see the dashboard"]}],
}

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="renders the page script with Node.js")


def render(data):
    code = NODE_RUNNER.replace("__PAGE__", json.dumps(str(PAGE))).replace("__DATA__", json.dumps(data))
    result = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return json.loads(result.stdout)["output"]


@needs_node
def test_what_to_validate_shows_above_the_test_cases():
    output = render(SAMPLE)
    assert "What to validate" in output
    assert "they see the dashboard" in output
    assert output.index("What to validate") < output.index('class="test-case"')


@needs_node
def test_the_section_is_left_out_when_there_is_no_summary():
    data = {key: value for key, value in SAMPLE.items() if key != "validation_summary"}
    assert "What to validate" not in render(data)


@needs_node
def test_checks_are_escaped_not_run_as_html():
    data = dict(SAMPLE, validation_summary=[{"title": "T", "checks": ["<img src=x onerror=alert(1)>"]}])
    output = render(data)
    assert "<img" not in output
    assert "&lt;img" in output
