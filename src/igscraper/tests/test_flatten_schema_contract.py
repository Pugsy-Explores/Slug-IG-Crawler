"""Contract tests for bundled flatten schema (no browser)."""

from __future__ import annotations

import ast
from pathlib import Path

import yaml

from igscraper.models.registry_parser import load_schema

# Must stay aligned with rules.data in flatten_schema.yaml and audit executive_summary.
CRITICAL_RULES_DATA_KEYS = frozenset(
    {
        "xdt_api__v1__feed__user_timeline_graphql_connection",
        "xdt_api__v1__media__media_id__comments__connection",
        "xdt_api__v1__media__media_id__comments__parent_comment_id__child_comments__connection",
    }
)


def test_bundled_schema_has_critical_data_keys() -> None:
    raw = yaml.safe_load(load_schema(None))
    rules = raw["rules"]
    data = rules["data"]
    present = CRITICAL_RULES_DATA_KEYS & set(data.keys())
    missing = CRITICAL_RULES_DATA_KEYS - present
    assert not missing, f"rules.data missing keys: {sorted(missing)}"


def test_selenium_backend_comment_model_keys_subset_of_schema() -> None:
    """COMMENT_MODEL_KEYS must name top-level rules.data xdt keys (see selenium_backend.py)."""
    raw = yaml.safe_load(load_schema(None))
    data_keys = set(raw["rules"]["data"].keys()) - {"__strict__", "__separate__"}
    backend_path = Path(__file__).resolve().parents[1] / "backends" / "selenium_backend.py"
    tree = ast.parse(backend_path.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and target.attr == "COMMENT_MODEL_KEYS"
                and isinstance(node.value, ast.Set)
            ):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        keys.add(elt.value)
    assert keys, "expected COMMENT_MODEL_KEYS set literal with string entries in selenium_backend.py"
    for k in keys:
        assert k in data_keys, f"COMMENT_MODEL_KEYS entry {k!r} not in flatten_schema rules.data"
