"""Tests for registry_parser.load_schema (pip vs dev path resolution)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml

from igscraper.models.registry_parser import load_schema


def test_load_schema_none_uses_bundled():
    text = load_schema(None)
    data = yaml.safe_load(text)
    assert isinstance(data, dict)
    assert "rules" in data


def test_load_schema_missing_path_falls_back_to_bundled():
    text = load_schema("src/igscraper/this_file_should_not_exist_ever.yaml")
    data = yaml.safe_load(text)
    assert "rules" in data


def test_load_schema_uses_existing_file():
    bundled = load_schema(None)
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        encoding="utf-8",
    ) as f:
        f.write(bundled)
        path = f.name
    try:
        assert load_schema(path) == bundled
    finally:
        Path(path).unlink(missing_ok=True)
