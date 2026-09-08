import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from retriever import StyleRetriever

CORPUS_PATH = Path(__file__).parent.parent / "corpus" / "style_examples.json"


def test_retrieve_returns_requested_count():
    retriever = StyleRetriever(CORPUS_PATH)
    results = retriever.retrieve("delete an item from my list", top_k=3)
    assert len(results) == 3


def test_retrieve_ranks_semantically_closest_requirement_first():
    retriever = StyleRetriever(CORPUS_PATH)
    results = retriever.retrieve(
        "As a user, I want to remove an item from my cart so I am not charged for it",
        top_k=1,
    )
    assert results[0]["id"] == "corpus-003"  # the delete-item example


def test_retrieve_similarity_scores_are_descending():
    retriever = StyleRetriever(CORPUS_PATH)
    results = retriever.retrieve("edit the price of an item", top_k=3)
    similarities = [r["similarity"] for r in results]
    assert similarities == sorted(similarities, reverse=True)


def test_retrieve_includes_similarity_score_in_each_result():
    retriever = StyleRetriever(CORPUS_PATH)
    results = retriever.retrieve("log in with email and password", top_k=1)
    assert "similarity" in results[0]
    assert 0.0 <= results[0]["similarity"] <= 1.0


STEP_BY_STEP_CORPUS_PATH = Path(__file__).parent.parent / "corpus" / "style_examples_step_by_step.json"


def test_step_by_step_corpus_retrieves_correctly():
    retriever = StyleRetriever(STEP_BY_STEP_CORPUS_PATH)
    results = retriever.retrieve(
        "As a user, I want to remove an item from my cart so I am not charged for it",
        top_k=1,
    )
    assert results[0]["id"] == "step-003"  # the delete-item example, step-by-step corpus


def test_step_by_step_corpus_has_expected_shape():
    retriever = StyleRetriever(STEP_BY_STEP_CORPUS_PATH)
    results = retriever.retrieve("add a new item", top_k=1)
    test_case = results[0]["test_cases"][0]
    assert "preconditions" in test_case
    assert "steps" in test_case
    assert "step_number" in test_case["steps"][0]
    assert "expected_result" in test_case["steps"][0]
