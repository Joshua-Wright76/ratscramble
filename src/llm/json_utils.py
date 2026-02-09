from __future__ import annotations

import ast
import json
import re
from typing import Any


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL | re.IGNORECASE)


def extract_json_object(text: str) -> dict[str, Any]:
    value = try_extract_json_object(text)
    if value is not None:
        return value
    raise ValueError("No JSON object found in model response")


def try_extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        value = json.loads(text)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    fenced_match = _FENCED_JSON_RE.search(text)
    if fenced_match:
        candidate = fenced_match.group(1)
        parsed = _parse_dict_like(candidate)
        if parsed is not None:
            return parsed

    match = _JSON_OBJECT_RE.search(text)
    if match:
        parsed = _parse_dict_like(match.group(0))
        if parsed is not None:
            return parsed

    return None


def _parse_dict_like(candidate: str) -> dict[str, Any] | None:
    try:
        value = json.loads(candidate)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    try:
        value = ast.literal_eval(candidate)
        if isinstance(value, dict):
            return {str(k): v for k, v in value.items()}
    except (ValueError, SyntaxError):
        pass

    return None
