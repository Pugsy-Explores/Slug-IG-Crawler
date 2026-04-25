"""Shared vocabulary ``envelope`` inside structured timing logs (Phase 2).

See ``docs/contracts/shared-vocabulary.md``. Legacy ``status`` / ``error_type`` unchanged.
"""

from __future__ import annotations

from typing import Any


def map_timing_error_type_to_code(error_type: str | None) -> str | None:
    if not error_type:
        return None
    if error_type == "SystemExit":
        return "RUNTIME_ABORT"
    if "ValidationError" in error_type or error_type == "ValueError":
        return "INVALID_INPUT"
    return "EXECUTION_ERROR"


def build_timing_log_envelope(
    *,
    thor_worker_id: str,
    workflow_trace_id: str | None = None,
    timing_status: str,
    error_type: str | None,
    version: str = "igscraper-log-v1",
) -> dict[str, Any]:
    """``timing_status`` is legacy ``success`` | ``error`` from pipeline/backend."""
    shared = "success" if timing_status == "success" else "failed"
    code = map_timing_error_type_to_code(error_type) if shared == "failed" else None
    tid = (workflow_trace_id or "").strip() or thor_worker_id
    env: dict[str, Any] = {
        "version": version,
        "status": shared,
        "terminal": True,
        "retryable": False,
        "trace_id": tid,
        "thor_worker_id": thor_worker_id,
    }
    if code:
        env["error_code"] = code
    return env
