import pytest

from src.chunking import build_chunks, split_text_by_sentences, split_text_with_overlap
from src.corpus import load_corpus


def test_split_text_with_overlap_returns_multiple_chunks() -> None:
    text = "abcdefghijklmnopqrstuvwxyz" * 4
    chunks = split_text_with_overlap(text, chunk_size=30, overlap=10)
    assert len(chunks) >= 3


def test_split_text_with_overlap_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError):
        split_text_with_overlap("abc", chunk_size=10, overlap=10)


def test_split_text_by_sentences_keeps_whole_sentences() -> None:
    text = "One two. Three four five. Six."
    chunks = split_text_by_sentences(text, chunk_size=20)
    assert chunks == ["One two.", "Three four five.", "Six."]


def test_split_text_by_sentences_packs_short_sentences_together() -> None:
    chunks = split_text_by_sentences("A b. C d. E f.", chunk_size=100)
    assert chunks == ["A b. C d. E f."]


def test_split_text_by_sentences_keeps_long_sentence_as_own_chunk() -> None:
    long_sentence = "This sentence is clearly longer than the tiny limit."
    chunks = split_text_by_sentences(f"Short. {long_sentence} End.", chunk_size=20)
    assert chunks == ["Short.", long_sentence, "End."]


def test_build_chunks_uses_stable_ids_and_keeps_metadata() -> None:
    chunks = build_chunks(load_corpus())
    ids = [chunk.chunk_id for chunk in chunks]
    assert len(ids) == len(set(ids))
    first = chunks[0]
    assert first.chunk_id == f"{first.doc_id}-chunk-0"
    assert first.version and first.status in {"current", "superseded"}
