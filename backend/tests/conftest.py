"""Pytest configuration: ensure backend package imports work in CI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


@pytest.fixture(autouse=True)
def _override_firebase_auth():
    """Bypass Firebase Bearer verification for HTTP TestClient calls."""
    from app.main import app
    from app.services.firebase_auth import get_current_user

    async def _fake_current_user():
        return {
            "uid": "test-uid",
            "email": "test@example.com",
            "name": "Test User",
            "picture": None,
        }

    app.dependency_overrides[get_current_user] = _fake_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture(autouse=True)
def _mark_warmup_complete(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip startup guideline-index warmup gate during tests."""
    monkeypatch.setattr("app.prescription_routes.is_warmup_complete", lambda: True)
    monkeypatch.setattr("app.startup_warmup.is_warmup_complete", lambda: True)


@pytest.fixture(autouse=True)
def _stub_heavy_ml_on_ci(monkeypatch: pytest.MonkeyPatch) -> None:
    """Avoid onnx/fastembed model loads on GitHub Actions Linux runners."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return

    def _identity_rerank(
        query: str,
        chunks: list[dict],
        *,
        top_k: int = 12,
    ) -> list[dict]:
        return [dict(chunk) for chunk in chunks[:top_k]]

    def _prefix_prefilter(
        query: str,
        titles: list[str],
        *,
        top_k: int = 50,
        embed_fn=None,
    ) -> list[str]:
        return list(titles[:top_k])

    for target in (
        "app.services.rag_pipeline.rerank_chunks",
        "app.services.stg_retrieval.rerank_chunks",
        "app.services.rag_pipeline.prefilter_titles_by_embedding",
        "app.services.stg_retrieval.prefilter_titles_by_embedding",
    ):
        monkeypatch.setattr(
            target,
            _identity_rerank if "rerank" in target else _prefix_prefilter,
            raising=False,
        )
    monkeypatch.setattr(
        "app.services.rag_pipeline._get_reranker",
        lambda: (_ for _ in ()).throw(RuntimeError("reranker disabled in CI")),
        raising=False,
    )
