"""Golden-style parser tests: minimal GraphQL JSON fixtures must flatten to non-empty rows."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from igscraper.models.common import MODEL_REGISTRY
from igscraper.models.registry_parser import GraphQLModelRegistry

_FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _registry() -> GraphQLModelRegistry:
    return GraphQLModelRegistry(MODEL_REGISTRY, None)


def _flatten_full_response(reg: GraphQLModelRegistry, payload: dict) -> list[dict]:
    """Use public :meth:`GraphQLModelRegistry.flatten_response` (rules-shaped wrap)."""
    rows, _diag = reg.flatten_response(payload, debug=False)
    return rows


@pytest.mark.parametrize(
    "fixture_name,expected_substr",
    [
        ("sample_graphql_timeline_min.json", "user_timeline_graphql_connection"),
        ("sample_graphql_comments_min.json", "comments__connection"),
    ],
)
def test_fixture_flattens_non_empty(fixture_name: str, expected_substr: str) -> None:
    path = _FIXTURES / fixture_name
    payload = json.loads(path.read_text(encoding="utf-8"))
    reg = _registry()
    rows = _flatten_full_response(reg, payload)
    assert rows, f"{fixture_name} produced no rows"
    flat_keys = "".join(rows[0].keys())
    assert expected_substr in flat_keys
