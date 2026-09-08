"""
Retrieves the most similar past requirements from the style corpus, used as
few-shot examples so generated test cases match established conventions
rather than generic AI phrasing.

TF-IDF + cosine similarity is used instead of a vector database - the corpus
is small (dozens to low hundreds of examples in realistic use), and this
keeps the project dependency-light and fully offline/inspectable. Swapping
in embeddings (e.g. sentence-transformers or an API-based embedding model)
is a drop-in replacement if the corpus grows large enough to need it - see
README roadmap.
"""

import json
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


class StyleRetriever:
    def __init__(self, corpus_path: Path):
        self.corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
        self._requirements = [entry["requirement"] for entry in self.corpus]
        self._vectorizer = TfidfVectorizer(stop_words="english")
        self._matrix = self._vectorizer.fit_transform(self._requirements)

    def retrieve(self, new_requirement: str, top_k: int = 2) -> list:
        """Return the top_k most similar corpus entries to new_requirement."""
        query_vector = self._vectorizer.transform([new_requirement])
        similarities = cosine_similarity(query_vector, self._matrix)[0]
        ranked_indices = similarities.argsort()[::-1][:top_k]
        return [
            {**self.corpus[i], "similarity": round(float(similarities[i]), 3)}
            for i in ranked_indices
        ]
