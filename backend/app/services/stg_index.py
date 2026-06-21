"""ChromaDB-backed STG vector index with local fastembed embeddings."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.services.stg_parser import StgChunk, TocEntry

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INDEX_DIR = _BACKEND_ROOT / "data" / "stg_index"
COLLECTION_NAME = "stg_guidelines"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

_store: "StgIndexStore | None" = None


class StgIndexStore:
    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.toc_path = index_dir / "toc.json"
        self.chroma_path = index_dir / "chroma"
        self._toc: list[TocEntry] = []
        self._client: Any = None
        self._collection: Any = None
        self._embedder: Any = None
        self._load_toc()

    def _load_toc(self) -> None:
        if not self.toc_path.exists():
            self._toc = []
            return
        payload = json.loads(self.toc_path.read_text(encoding="utf-8"))
        self._toc = [
            TocEntry(
                condition=str(item.get("condition", "")),
                book_page=int(item.get("book_page", 0)),
                chapter=str(item.get("chapter", "")),
            )
            for item in payload
        ]

    @property
    def is_ready(self) -> bool:
        return self.toc_path.exists() and self.chroma_path.exists()

    @property
    def toc(self) -> list[TocEntry]:
        return list(self._toc)

    def condition_names(self) -> list[str]:
        return [entry.condition for entry in self._toc]

    def _ensure_client(self) -> None:
        if self._collection is not None:
            return
        if not self.is_ready:
            raise FileNotFoundError(
                f"STG index is not built at {self.index_dir}. "
                "Run: python backend/scripts/build_stg_index.py"
            )
        import chromadb
        from chromadb.config import Settings
        from fastembed import TextEmbedding

        self._embedder = TextEmbedding(model_name=EMBED_MODEL)
        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        self._ensure_client()
        return [[float(value) for value in vector] for vector in self._embedder.embed(texts)]

    def build_index(self, chunks: list[StgChunk]) -> None:
        import chromadb
        from chromadb.config import Settings
        from fastembed import TextEmbedding

        self.index_dir.mkdir(parents=True, exist_ok=True)
        if self.chroma_path.exists():
            import shutil

            shutil.rmtree(self.chroma_path)

        embedder = TextEmbedding(model_name=EMBED_MODEL)
        client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=Settings(anonymized_telemetry=False),
        )
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

        batch_size = 64
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            ids = [chunk.chunk_id for chunk in batch]
            documents = [chunk.text for chunk in batch]
            metadatas = [
                {
                    "condition": chunk.condition,
                    "chapter": chunk.chapter,
                    "section_type": chunk.section_type,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                }
                for chunk in batch
            ]
            embeddings = [
                [float(value) for value in vector]
                for vector in embedder.embed(documents)
            ]
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )

        self._client = client
        self._collection = collection
        self._embedder = embedder

    def get_chunks_for_conditions(
        self,
        conditions: list[str],
        limit_per_condition: int = 12,
    ) -> list[dict[str, Any]]:
        self._ensure_client()
        if not conditions:
            return []
        normalized = {name.strip().lower(): name.strip() for name in conditions if name.strip()}
        results: list[dict[str, Any]] = []
        for condition_lower, condition_label in normalized.items():
            fetched = self._collection.get(
                where={"condition": condition_label},
                include=["documents", "metadatas"],
            )
            ids = fetched.get("ids") or []
            documents = fetched.get("documents") or []
            metadatas = fetched.get("metadatas") or []
            for index, chunk_id in enumerate(ids[:limit_per_condition]):
                metadata = metadatas[index] if index < len(metadatas) else {}
                document = documents[index] if index < len(documents) else ""
                results.append(
                    {
                        "chunk_id": chunk_id,
                        "condition": metadata.get("condition", condition_label),
                        "chapter": metadata.get("chapter", ""),
                        "section_type": metadata.get("section_type", "general"),
                        "page_start": metadata.get("page_start"),
                        "page_end": metadata.get("page_end"),
                        "text": document,
                        "source": "toc",
                    }
                )
        return results

    def semantic_search(
        self,
        query: str,
        top_k: int = 8,
        condition_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_client()
        query_embedding = self.embed_texts([query])[0]
        where: dict[str, Any] | None = None
        if condition_filter:
            if len(condition_filter) == 1:
                where = {"condition": condition_filter[0]}
            else:
                where = {"condition": {"$in": condition_filter}}

        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        ids = (results.get("ids") or [[]])[0]
        documents = (results.get("documents") or [[]])[0]
        metadatas = (results.get("metadatas") or [[]])[0]
        distances = (results.get("distances") or [[]])[0]

        payload: list[dict[str, Any]] = []
        for index, chunk_id in enumerate(ids):
            metadata = metadatas[index] if index < len(metadatas) else {}
            payload.append(
                {
                    "chunk_id": chunk_id,
                    "condition": metadata.get("condition", ""),
                    "chapter": metadata.get("chapter", ""),
                    "section_type": metadata.get("section_type", "general"),
                    "page_start": metadata.get("page_start"),
                    "page_end": metadata.get("page_end"),
                    "text": documents[index] if index < len(documents) else "",
                    "distance": distances[index] if index < len(distances) else None,
                    "source": "semantic",
                }
            )
        return payload


def get_stg_index_store(index_dir: Path | None = None) -> StgIndexStore:
    global _store
    resolved = index_dir or Path(
        os.getenv("STG_INDEX_DIR", str(DEFAULT_INDEX_DIR))
    )
    if _store is None or _store.index_dir != resolved:
        _store = StgIndexStore(resolved)
    return _store
