"""ChromaDB-backed primary guidelines index (ICMR + Clinical Establishments Act STG)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.services.rag_pipeline import Bm25Index, DEFAULT_EMBED_MODEL, DEFAULT_RETRIEVAL_POOL_K
from app.services.stg_index import EMBED_MODEL
from app.services.stg_parser import StgChunk

_BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_INDEX_DIR = _BACKEND_ROOT / "data" / "primary_guidelines_index"
COLLECTION_NAME = "primary_guidelines"

_store: "PrimaryGuidelinesIndexStore | None" = None


class PrimaryGuidelinesIndexStore:
    def __init__(self, index_dir: Path) -> None:
        self.index_dir = index_dir
        self.toc_path = index_dir / "toc.json"
        self.documents_path = index_dir / "documents.json"
        self.chroma_path = index_dir / "chroma"
        self.manifest_path = index_dir / "chunks_manifest.json"
        self._toc: list[dict[str, Any]] = []
        self._documents: list[str] = []
        self._client: Any = None
        self._collection: Any = None
        self._embedder: Any = None
        self._bm25: Bm25Index | None = None
        self._load_metadata()

    def _load_metadata(self) -> None:
        if self.toc_path.exists():
            payload = json.loads(self.toc_path.read_text(encoding="utf-8"))
            self._toc = [item for item in payload if isinstance(item, dict)]
        else:
            self._toc = []

        if self.documents_path.exists():
            payload = json.loads(self.documents_path.read_text(encoding="utf-8"))
            self._documents = [str(item) for item in payload if str(item).strip()]
        else:
            self._documents = sorted(
                {
                    str(item.get("condition") or "").strip()
                    for item in self._toc
                    if str(item.get("condition") or "").strip()
                }
            )

    @property
    def is_ready(self) -> bool:
        return self.toc_path.exists() and self.chroma_path.exists()

    @property
    def toc(self) -> list[dict[str, Any]]:
        return list(self._toc)

    def condition_names(self) -> list[str]:
        if self._documents:
            return list(self._documents)
        return sorted(
            {
                str(item.get("condition") or "").strip()
                for item in self._toc
                if str(item.get("condition") or "").strip()
            }
        )

    def corpus_labels(self) -> list[str]:
        return sorted(
            {
                str(item.get("corpus") or "").strip()
                for item in self._toc
                if str(item.get("corpus") or "").strip()
            }
        )

    def _ensure_client(self) -> None:
        if self._collection is not None:
            return
        if not self.is_ready:
            raise FileNotFoundError(
                f"Primary guidelines index is not built at {self.index_dir}. "
                "Run: python backend/scripts/build_primary_guidelines_index.py"
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

    def build_index(
        self,
        chunks: list[StgChunk],
        extra_metadata: list[dict[str, Any]] | None = None,
        *,
        batch_size: int = 128,
        progress: bool = True,
    ) -> None:
        import chromadb
        import shutil
        import sys
        from chromadb.config import Settings
        from fastembed import TextEmbedding

        self.index_dir.mkdir(parents=True, exist_ok=True)
        if self.chroma_path.exists():
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

        total = len(chunks)
        for start in range(0, total, batch_size):
            batch = chunks[start : start + batch_size]
            batch_meta = (extra_metadata or [])[start : start + batch_size]
            ids = [chunk.chunk_id for chunk in batch]
            documents = [chunk.text for chunk in batch]
            metadatas = []
            for index, chunk in enumerate(batch):
                extra = batch_meta[index] if index < len(batch_meta) else {}
                metadatas.append(
                    {
                        "condition": chunk.condition,
                        "chapter": chunk.chapter,
                        "section_type": chunk.section_type,
                        "page_start": chunk.page_start,
                        "page_end": chunk.page_end,
                        "corpus": str(extra.get("corpus") or ""),
                        "source_file": str(extra.get("source_file") or ""),
                        "document": str(extra.get("document") or chunk.condition),
                    }
                )
            embeddings = [
                [float(value) for value in vector]
                for vector in embedder.embed(documents, batch_size=batch_size)
            ]
            collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings,
            )
            done = min(start + batch_size, total)
            if progress:
                pct = round((done / total) * 100)
                print(
                    f"Embedded {done}/{total} chunks ({pct}%)",
                    file=sys.stderr,
                    flush=True,
                )

        self._client = client
        self._collection = collection
        self._embedder = embedder

    def build_index_from_manifest(
        self,
        *,
        batch_size: int = 128,
        progress: bool = True,
    ) -> int:
        manifest_path = self.index_dir / "chunks_manifest.json"
        if not manifest_path.exists():
            raise FileNotFoundError(f"Missing manifest at {manifest_path}")

        import json

        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        chunks: list[StgChunk] = []
        metadata: list[dict[str, Any]] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").strip()
            if len(text) < 40:
                continue
            chunks.append(
                StgChunk(
                    chunk_id=str(item.get("chunk_id") or ""),
                    condition=str(item.get("document") or item.get("condition") or ""),
                    chapter=str(item.get("chapter") or ""),
                    section_type=str(item.get("section_type") or "general"),
                    page_start=int(item.get("page_start") or 0),
                    page_end=int(item.get("page_end") or 0),
                    text=text[:8000],
                )
            )
            metadata.append(
                {
                    "corpus": str(item.get("corpus") or ""),
                    "source_file": str(item.get("source_file") or ""),
                    "document": str(item.get("document") or item.get("condition") or ""),
                }
            )

        self.build_index(chunks, extra_metadata=metadata, batch_size=batch_size, progress=progress)
        return len(chunks)

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
                results.append(self._chunk_payload(chunk_id, metadata, document, source="toc"))
        return results

    def _ensure_bm25(self) -> Bm25Index:
        if self._bm25 is None:
            self._bm25 = Bm25Index(self.manifest_path)
        return self._bm25

    def keyword_search(self, query: str, top_k: int = DEFAULT_RETRIEVAL_POOL_K) -> list[dict[str, Any]]:
        results = self._ensure_bm25().search(query, top_k=top_k)
        enriched: list[dict[str, Any]] = []
        for item in results:
            payload = self._chunk_payload(
                str(item.get("chunk_id") or ""),
                {
                    "condition": item.get("condition", ""),
                    "chapter": item.get("chapter", ""),
                    "section_type": item.get("section_type", "general"),
                    "page_start": item.get("page_start"),
                    "page_end": item.get("page_end"),
                    "corpus": item.get("corpus", ""),
                    "source_file": item.get("source_file", ""),
                    "document": item.get("document", item.get("condition", "")),
                },
                str(item.get("text") or ""),
                source="bm25",
            )
            payload["bm25_score"] = item.get("bm25_score")
            enriched.append(payload)
        return enriched

    def semantic_search(
        self,
        query: str,
        top_k: int = DEFAULT_RETRIEVAL_POOL_K,
        condition_filter: list[str] | None = None,
        corpus_filter: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        self._ensure_client()
        query_embedding = self.embed_texts([query])[0]
        where: dict[str, Any] | None = None
        filters: list[dict[str, Any]] = []
        if condition_filter:
            if len(condition_filter) == 1:
                filters.append({"condition": condition_filter[0]})
            else:
                filters.append({"condition": {"$in": condition_filter}})
        if corpus_filter:
            if len(corpus_filter) == 1:
                filters.append({"corpus": corpus_filter[0]})
            else:
                filters.append({"corpus": {"$in": corpus_filter}})

        if len(filters) == 1:
            where = filters[0]
        elif len(filters) > 1:
            where = {"$and": filters}

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
            document = documents[index] if index < len(documents) else ""
            item = self._chunk_payload(chunk_id, metadata, document, source="semantic")
            item["distance"] = distances[index] if index < len(distances) else None
            payload.append(item)
        return payload

    def _chunk_payload(
        self,
        chunk_id: str,
        metadata: dict[str, Any],
        document: str,
        *,
        source: str,
    ) -> dict[str, Any]:
        corpus = str(metadata.get("corpus") or "")
        corpus_label = {
            "icmr": "ICMR",
            "clinical_establishments": "Clinical Establishments Act STG",
        }.get(corpus, corpus or "Primary guidelines")
        return {
            "chunk_id": chunk_id,
            "condition": metadata.get("condition", ""),
            "chapter": metadata.get("chapter", ""),
            "section_type": metadata.get("section_type", "general"),
            "page_start": metadata.get("page_start"),
            "page_end": metadata.get("page_end"),
            "text": document,
            "source": source,
            "corpus": corpus,
            "corpus_label": corpus_label,
            "source_file": metadata.get("source_file", ""),
            "document": metadata.get("document", metadata.get("condition", "")),
            "guideline_tier": "primary",
        }


def get_primary_guidelines_store(index_dir: Path | None = None) -> PrimaryGuidelinesIndexStore:
    global _store
    resolved = index_dir or Path(
        os.getenv("PRIMARY_GUIDELINES_INDEX_DIR", str(DEFAULT_INDEX_DIR))
    )
    if _store is None or _store.index_dir != resolved:
        _store = PrimaryGuidelinesIndexStore(resolved)
    return _store
