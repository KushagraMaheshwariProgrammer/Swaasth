"""Background warmup for heavy datasets and guideline indexes."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_warmup_lock = threading.Lock()
_warmup_started = False
_warmup_complete = False
_warmup_error: str | None = None


def warmup_status() -> dict[str, Any]:
    return {
        "started": _warmup_started,
        "complete": _warmup_complete,
        "error": _warmup_error,
    }


def is_warmup_complete() -> bool:
    return _warmup_complete


def wait_for_warmup(*, timeout_seconds: float = 120.0) -> None:
    """Block until warmup finishes, or raise 503.

    Used by sync analysis endpoints so clients (especially older app builds that
    map every 503 to "backend unreachable") succeed across Container App
    restarts instead of failing immediately.
    """
    deadline = time.monotonic() + max(timeout_seconds, 1.0)
    while True:
        if _warmup_complete:
            return
        if _warmup_error:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Backend warmup failed while loading guideline indexes. "
                    "Please retry in a minute."
                ),
            )
        if time.monotonic() >= deadline:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Backend is still warming up guideline indexes. "
                    "Retry in about a minute."
                ),
            )
        time.sleep(0.5)


def _run_warmup() -> None:
    global _warmup_complete, _warmup_error
    try:
        from app.jan_aushadhi_rates import get_jan_aushadhi_store
        from app.pharma_rates import get_pharma_store
        from app.restricted_medicines import get_restricted_medicines_store
        from app.services.primary_guidelines_index import get_primary_guidelines_store
        from app.services.rag_pipeline import _get_reranker
        from app.services.stg_index import get_stg_index_store

        logger.info("Warmup: loading pharma datasets")
        pharma = get_pharma_store()
        az_count = len(pharma.az.rows) if pharma.az else 0
        logger.info(
            "Warmup: loaded %s NPPA prices and %s brand mappings",
            len(pharma.nppa.rows),
            az_count,
        )

        logger.info("Warmup: loading Jan Aushadhi catalog")
        jan_aushadhi = get_jan_aushadhi_store()
        logger.info("Warmup: loaded %s Jan Aushadhi products", len(jan_aushadhi.rows))

        logger.info("Warmup: loading restricted medicines catalog")
        restricted = get_restricted_medicines_store()
        logger.info(
            "Warmup: restricted medicines available=%s count=%s",
            restricted.is_available(),
            len(restricted.rows),
        )

        logger.info("Warmup: loading STG indexes")
        stg = get_stg_index_store()
        if stg.is_ready:
            stg.embed_texts(["warmup"])
            logger.info("Warmup: STG index ready")
        else:
            logger.warning("Warmup: STG index files missing at %s", stg.index_dir)

        primary = get_primary_guidelines_store()
        if primary.is_ready:
            primary.embed_texts(["warmup"])
            logger.info("Warmup: primary guidelines index ready")
        else:
            logger.warning(
                "Warmup: primary guidelines index files missing at %s",
                primary.index_dir,
            )

        logger.info("Warmup: loading reranker")
        _get_reranker()
        logger.info("Warmup complete")
        _warmup_complete = True
    except Exception as exc:
        _warmup_error = str(exc)
        logger.exception("Warmup failed: %s", exc)


def start_background_warmup() -> None:
    global _warmup_started
    with _warmup_lock:
        if _warmup_started:
            return
        _warmup_started = True
        thread = threading.Thread(
            target=_run_warmup,
            name="swaasth-startup-warmup",
            daemon=True,
        )
        thread.start()
