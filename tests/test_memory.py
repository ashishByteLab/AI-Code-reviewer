import pytest
from app.memory.experience_store import get_experience_store

def test_chromadb_initialization_and_seeding():
    store = get_experience_store()
    count = store.collection.count()
    assert count >= 6 # Seeded with seminar experiences

def test_chromadb_add_and_retrieve():
    store = get_experience_store()
    doc_id = store.add_experience(
        title="Test Fast String Concat Pattern",
        category="ITERATION_OPTIMIZATION",
        bug_snippet="s = ''\nfor w in words:\n    s += w",
        fix_snippet="s = ''.join(words)",
        explanation="O(N) contiguous buffer allocation instead of O(N^2) copying",
        tags="test, strings"
    )
    assert doc_id is not None

    # Query similarity
    results = store.query_similar_experiences("s += word", n_results=2)
    assert len(results) > 0
    assert any("String" in r["title"] or "Concat" in r["title"] for r in results)
