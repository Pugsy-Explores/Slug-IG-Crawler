"""Standard key=value fragments for grep-friendly logs (Phase 4; mirror Thor / PUGSY)."""

from __future__ import annotations

from typing import Any, Mapping

_KNOWN = ("trace_id", "job_id", "worker_id", "status", "error_code", "run_id")


def format_trace_kv(parts: Mapping[str, Any] | None = None, **kwargs: Any) -> str:
    """Space-separated ``key=value`` tokens; skips None and empty string."""
    merged: dict[str, Any] = {}
    if parts:
        merged.update({k: v for k, v in parts.items() if v is not None and v != ""})
    merged.update({k: v for k, v in kwargs.items() if v is not None and v != ""})
    ordered: list[str] = []
    for key in _KNOWN:
        if key in merged:
            ordered.append(f"{key}={merged[key]}")
    for key in sorted(k for k in merged if k not in _KNOWN):
        ordered.append(f"{key}={merged[key]}")
    return " ".join(ordered)
