# AI Test Case Generator with Style-Aware Retrieval

Turns a requirement into test cases that match your team's actual
conventions - not generic AI output you'd get from pasting a ticket into a
chatbot.

## Why this isn't just a chatbot wrapper

Pasting a ticket into a chat window gives inconsistent results: the format,
tone, and structure drift depending on how you phrase the prompt that day.
This tool instead retrieves the most similar past requirements from a style
corpus and feeds them to the model as grounding examples every time, so
output consistently matches established conventions rather than generic
AI phrasing. It also flags ambiguous or under-specified requirements before
development starts, and logs every run - building a real, reportable metric
over time (e.g. "X% of tickets flagged as under-specified pre-dev") instead
of a one-off demo claim.

## Architecture

```
Jira ticket (via key)  --or--  pasted requirement text
              |
              v
    (web UI: templates/index.html + src/app.py)
              |
              v
StyleRetriever (TF-IDF + cosine similarity over corpus/style_examples.json)
              |
              v
top-k most similar past requirements + their test cases
              |
              v
TestCaseGenerator builds a grounded prompt -> calls Claude API
              |
              v
JSON response: test cases (matching style) + ambiguity flags
              |
              v
   displayed in UI + appended to logs/generation_log.jsonl
```

TF-IDF similarity is used instead of a vector database - the corpus is
small, and this keeps the project dependency-light and fully inspectable.
Swapping in real embeddings is a drop-in replacement in `retriever.py` if
the corpus grows large enough to need it.

## Setup

## Two test case formats

Selectable in the UI (radio buttons) or via `--style` on the CLI:

- **BDD (Given/When/Then)** - `bdd`, the default. Best for quick validation
  during testing, one behavior per test case.
- **Step-by-Step / Multi-Stage** - `step_by_step`. Numbered steps, each with
  its own expected result, plus preconditions and test data stated up
  front. Suited to complex processes where precise, repeatable execution
  matters and someone with little familiarity with the app should be able
  to follow it successfully end to end - the format commonly seen in tools
  like Zephyr.

Each style has its own corpus (`corpus/style_examples.json` for BDD,
`corpus/style_examples_step_by_step.json` for step-by-step) so retrieval
stays grounded in examples of the *same* format being requested - style
matching would break if a BDD example were used to ground a step-by-step
generation, or vice versa.

```bash
pip install -r requirements.txt
cp .env.example .env
# add your ANTHROPIC_API_KEY to .env
```

## Usage

**Web UI (recommended):**
```bash
python src/app.py
```
Then open `http://localhost:5001`. Paste a requirement directly, or open
**Jira settings** on the page, enter your Jira site name (for example
`mysite` from `mysite.atlassian.net`), your Atlassian account email and an
API token, then click **Check Jira**. Once Jira is connected, enter a ticket
key (e.g. `PROJ-123`) and click "Fetch from Jira" to pull its summary and
description in automatically - removes the copy/paste step between Jira and
this tool. Click "Copy as text" on the results to paste them into a ticket
comment, test plan, or checklist while testing.

Create an API token at https://id.atlassian.com/manage-profile/security/api-tokens.
This is intentionally read-only: it fetches the ticket for you, but never
writes a comment, field, or status back to Jira. Your Jira settings stay in
the browser tab. They are sent to this app only when you check Jira or fetch
a ticket, and are never saved on the server. Direct paste still works
without any Jira setup at all.

**Command line (still available):**
```bash
python src/cli.py --requirement "As a user, I want to filter my items by price range"
```

## Running the tests

```bash
pytest tests/
```

Covers the retrieval logic: correct result count, correct ranking by
similarity, and that scores are properly ordered. This is a testing tool
that is itself tested - worth calling out.

## The style corpus

`corpus/style_examples.json` currently holds synthetic examples (shopping
app domain, matching the conventions used across this portfolio's other
projects) written in Given/When/Then style. Swap in real past test cases
from your own team to have generated output match your actual conventions
instead of these placeholders - the format is a flat JSON list of
`{id, requirement, test_cases}` objects, so adding more is just appending
entries.

## Roadmap

- **Writing back to Jira** - currently read-only by design (fetches a
  ticket's text, never posts a comment or changes a field). Once the
  read-only flow has been used against real tickets for a while, posting
  generated test cases back as a ticket comment automatically is the
  natural next step.
- A full Jira Marketplace app (via Atlassian Forge) is a further-out
  extension if this proves useful beyond personal use.
