"""
Builds a prompt grounded in retrieved style examples and calls the Claude API
to generate test cases in that established style, plus flags ambiguous or
under-specified requirements before development starts.

Two output styles are supported, each with its own corpus and prompt:

- "bdd": Given/When/Then, best for quick validation during testing.
- "step_by_step": numbered steps with an expected result at each stage, plus
  preconditions/test data/postconditions - suited to complex processes where
  precise, repeatable execution matters and someone unfamiliar with the app
  should be able to follow it end to end.
"""

import json
import os
from pathlib import Path

import anthropic

from retriever import StyleRetriever
from validation_summary import build_validation_summary

BDD_SYSTEM_PROMPT = """You are a QA engineer generating test cases in a \
specific team's established style. You will be shown example requirements \
paired with test cases written in that team's conventions (Given/When/Then \
steps, plain language, one behavior per test case). Match that style \
exactly for the new requirement.

Also assess whether the requirement is specific enough to test confidently. \
Flag anything ambiguous: missing edge cases, undefined error states, unclear \
acceptance criteria, or vague terms.

Respond with ONLY valid JSON, no other text, in this exact shape:
{
  "test_cases": [
    {"title": "...", "steps": ["Given ...", "When ...", "Then ..."]}
  ],
  "ambiguity_notes": ["...", "..."]
}
If there are no ambiguities, return an empty list for ambiguity_notes."""

STEP_BY_STEP_SYSTEM_PROMPT = """You are a QA engineer generating detailed, \
step-by-step test cases in a specific team's established style. You will be \
shown example requirements paired with test cases written in that team's \
conventions: numbered steps, each with a specific action and its expected \
result, plus preconditions and test data stated up front. This style is for \
complex processes where precise, repeatable execution matters - someone with \
little familiarity with the app should be able to follow it successfully. \
Match that style exactly for the new requirement.

Also assess whether the requirement is specific enough to test confidently. \
Flag anything ambiguous: missing edge cases, undefined error states, unclear \
acceptance criteria, or vague terms.

Respond with ONLY valid JSON, no other text, in this exact shape:
{
  "test_cases": [
    {
      "title": "...",
      "preconditions": ["...", "..."],
      "test_data": ["...", "..."],
      "steps": [
        {"step_number": 1, "action": "...", "expected_result": "..."}
      ],
      "postconditions": ["...", "..."]
    }
  ],
  "ambiguity_notes": ["...", "..."]
}
Use an empty list for test_data or postconditions if none apply. If there
are no ambiguities, return an empty list for ambiguity_notes."""

STYLES = {
    "bdd": {
        "system_prompt": BDD_SYSTEM_PROMPT,
        "corpus_filename": "style_examples.json",
    },
    "step_by_step": {
        "system_prompt": STEP_BY_STEP_SYSTEM_PROMPT,
        "corpus_filename": "style_examples_step_by_step.json",
    },
}


class TestCaseGenerator:
    def __init__(self, corpus_dir, model: str = None):
        corpus_dir = Path(corpus_dir)
        self.retrievers = {
            style: StyleRetriever(corpus_dir / config["corpus_filename"])
            for style, config in STYLES.items()
        }
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
        self.client = anthropic.Anthropic()

    def _build_prompt(self, requirement: str, examples: list) -> str:
        example_blocks = []
        for ex in examples:
            cases_text = json.dumps(ex["test_cases"], indent=2)
            example_blocks.append(
                f"Requirement: {ex['requirement']}\nTest cases:\n{cases_text}"
            )
        examples_text = "\n\n".join(example_blocks)
        return (
            f"Here are examples of past requirements and their test cases:\n\n"
            f"{examples_text}\n\n"
            f"Now generate test cases for this new requirement, matching the "
            f"same style:\n\nRequirement: {requirement}"
        )

    def generate(self, requirement: str, style: str = "bdd", top_k: int = 2) -> dict:
        if style not in STYLES:
            raise ValueError(f"Unknown style '{style}'. Must be one of: {list(STYLES.keys())}")

        retriever = self.retrievers[style]
        system_prompt = STYLES[style]["system_prompt"]

        examples = retriever.retrieve(requirement, top_k=top_k)
        prompt = self._build_prompt(requirement, examples)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt}],
        )

        raw_text = "".join(
            block.text for block in response.content if block.type == "text"
        )

        # Models sometimes wrap JSON in markdown code fences despite being
        # told not to - strip them before parsing rather than failing.
        cleaned_text = raw_text.strip()
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text.split("\n", 1)[1] if "\n" in cleaned_text else cleaned_text
            cleaned_text = cleaned_text.rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Model did not return valid JSON. Raw response:\n{raw_text}"
            ) from e

        parsed["validation_summary"] = build_validation_summary(parsed.get("test_cases", []), style)
        parsed["retrieved_examples"] = [ex["id"] for ex in examples]
        parsed["style"] = style
        return parsed
