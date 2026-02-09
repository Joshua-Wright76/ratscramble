from __future__ import annotations

from src.llm.json_utils import try_extract_json_object


def test_try_extract_json_object_from_plain_json() -> None:
    obj = try_extract_json_object('{"vote": 1, "utterance": "hi"}')
    assert obj == {"vote": 1, "utterance": "hi"}


def test_try_extract_json_object_from_fenced_json() -> None:
    text = """Here you go:\n```json\n{\"vote\": 0, \"scratchpad\": \"x\"}\n```"""
    obj = try_extract_json_object(text)
    assert obj == {"vote": 0, "scratchpad": "x"}


def test_try_extract_json_object_from_python_dict_like_text() -> None:
    text = "Model output: {'attempt_take_token': 3, 'utterance': 'taking token'}"
    obj = try_extract_json_object(text)
    assert obj == {"attempt_take_token": 3, "utterance": "taking token"}


def test_try_extract_json_object_returns_none_for_no_object() -> None:
    assert try_extract_json_object("just plain prose") is None
