import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import app as app_module
from e2e_tools import E2E_TOOLS

VOID_TAGS = {"area", "base", "br", "col", "hr", "img", "input", "link", "meta", "source", "wbr"}


class ClassFinder(HTMLParser):
    """Records, for the first element with a class, the classes of every element it sits inside."""

    def __init__(self, wanted):
        super().__init__()
        self.wanted = wanted
        self.stack = []
        self.found = None

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if self.found is None and self.wanted in classes:
            self.found = [c for _, cs in self.stack for c in cs]
        if tag not in VOID_TAGS:
            self.stack.append((tag, classes))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                return


def inherited_classes(html, wanted):
    finder = ClassFinder(wanted)
    finder.feed(html)
    return finder.found


@pytest.fixture
def page():
    return app_module.app.test_client().get("/").get_data(as_text=True)


def test_tools_come_in_the_order_the_page_shows_them():
    assert list(E2E_TOOLS) == ["cypress", "playwright", "selenium", "cucumber"]


def test_every_tool_has_a_name_a_language_and_a_summary():
    for tool in E2E_TOOLS.values():
        assert set(tool) == {"name", "language", "summary"}
        assert all(isinstance(value, str) and value.strip() for value in tool.values())


def test_each_tool_has_the_language_its_steps_are_written_for():
    languages = {tool_id: tool["language"] for tool_id, tool in E2E_TOOLS.items()}
    assert languages == {
        "cypress": "JavaScript",
        "playwright": "TypeScript",
        "selenium": "Python",
        "cucumber": "JavaScript",
    }


def test_page_has_one_radio_per_tool_in_order(page):
    values = re.findall(r'<input type="radio" name="e2e_tool" value="([^"]*)"', page)
    assert values == list(E2E_TOOLS)


def test_no_tool_is_chosen_before_the_user_picks_one(page):
    radios = re.findall(r'<input[^>]*name="e2e_tool"[^>]*>', page)
    assert len(radios) == len(E2E_TOOLS)
    assert not any("checked" in radio for radio in radios)


def test_page_shows_each_tools_name_language_and_summary(page):
    for tool in E2E_TOOLS.values():
        assert f"<strong>{tool['name']}</strong>" in page
        assert f'<span class="e2e-language">{tool["language"]}</span>' in page
        assert tool["summary"] in page


def test_tool_text_is_escaped_on_the_page(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "E2E_TOOLS",
        {"evil": {"name": "<script>alert(1)</script>", "language": "A & B", "summary": '"quoted" <b>bold</b>'}},
    )
    page = app_module.app.test_client().get("/").get_data(as_text=True)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "A &amp; B" in page
    assert "<b>bold</b>" not in page


def test_the_box_sits_inside_the_generated_output_panel_after_the_output(page):
    assert "panel" in inherited_classes(page, "e2e-box")
    assert page.index('id="output"') < page.index('class="e2e-box"')


def test_the_box_keeps_the_page_shape_the_cypress_suite_counts(page):
    assert page.count('class="panel"') == 2
    assert len(re.findall(r"<h2[ >]", page)) == 2
    assert page.count('class="style-option"') == 2
    assert 'class="jira-row"' in page
    start = page.index('class="e2e-box"')
    box = page[start:page.index("<script", start)]
    assert "<h2" not in box
    assert "<h3" not in box
    assert 'class="panel' not in box
    assert 'class="style-option' not in box
    assert 'class="jira-row' not in box
