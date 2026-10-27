"""수집기 밖 파이프라인(온톨로지 동기화·이슈·지표·해자 카드)도 ops.collector_runs 에 남긴다. ADR-0015 원칙 6."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

log = logging.getLogger("wsj.runlog")


@contextmanager
def logged_run(store, name: str, params: dict[str, Any] | None = None) -> Iterator[dict[str, Any]]:
    """with logged_run(store, "issues", {...}) as run: ... run["rows"] = n; run["notes"] = "..." """
    run: dict[str, Any] = {"rows": 0, "notes": None, "watermark": None}
    run_id = None
    if store is not None and hasattr(store, "run_started"):
        try:
            run_id = store.run_started(name, params or {})
        except Exception as exc:  # noqa: BLE001 - 기록 실패가 본 작업을 막지 않게
            log.warning("run log start failed: %s", exc)
    try:
        yield run
    except BaseException as exc:
        if run_id is not None:
            try:
                store.run_finished(run_id, "failed", int(run["rows"] or 0), None, f"{type(exc).__name__}: {exc}")
            except Exception:  # noqa: BLE001
                log.warning("run log finish failed")
        raise
    if run_id is not None:
        try:
            store.run_finished(run_id, "succeeded", int(run["rows"] or 0), run.get("watermark"), run.get("notes"))
        except Exception as exc:  # noqa: BLE001
            log.warning("run log finish failed: %s", exc)
