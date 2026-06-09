"""VectorStore — 本地向量检索（ChromaDB 后端）。

为章节、角色档案、世界书提供语义检索能力。
ChromaDB 为可选依赖，不安装时优雅降级。

向量库位置: projects/<name>/state/vector_db/
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_chromadb = None
_AVAILABLE: bool | None = None


def _check_available() -> bool:
    global _chromadb, _AVAILABLE
    if _AVAILABLE is not None:
        return _AVAILABLE
    try:
        import chromadb
        _chromadb = chromadb
        _AVAILABLE = True
    except ImportError:
        _AVAILABLE = False
    return _AVAILABLE


@dataclass
class VectorChunk:
    content: str
    source_type: str
    source_id: str
    chapter_id: float | None = None
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class VectorStore:
    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self._db_path = project_dir / "state" / "vector_db"
        self._client = None
        self._collections: dict[str, Any] = {}

    @property
    def available(self) -> bool:
        return _check_available()

    def _ensure_client(self):
        if not self.available:
            raise RuntimeError("chromadb 未安装。pip install novel-engine[vector]")
        if self._client is None:
            self._db_path.mkdir(parents=True, exist_ok=True)
            self._client = _chromadb.PersistentClient(
                path=str(self._db_path)
            )

    def _get_collection(self, name: str):
        if name not in self._collections:
            self._ensure_client()
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

    def index_chapter(
        self,
        chapter_id: float,
        text: str,
        summary: str = "",
        metadata: dict[str, Any] | None = None,
        chunk_size: int = 800,
        overlap: int = 100,
    ) -> int:
        """将章节正文分块索引。返回索引的 chunk 数。"""
        col = self._get_collection("chapters")
        chunks = self._split_text(text, chunk_size, overlap)
        if summary:
            chunks.insert(0, summary)

        ids = []
        documents = []
        metadatas = []

        for i, chunk in enumerate(chunks):
            doc_id = f"ch{chapter_id:g}_chunk{i}"
            ids.append(doc_id)
            documents.append(chunk)
            meta = {"chapter_id": chapter_id, "chunk_index": i, "source_type": "chapter"}
            if metadata:
                meta.update(metadata)
            metadatas.append(meta)

        if ids:
            col.upsert(ids=ids, documents=documents, metadatas=metadatas)
        return len(ids)

    def index_profile(self, character_name: str, state_text: str) -> None:
        """索引角色档案。"""
        col = self._get_collection("profiles")
        doc_id = f"profile_{hashlib.md5(character_name.encode()).hexdigest()[:8]}"
        col.upsert(
            ids=[doc_id],
            documents=[state_text],
            metadatas=[{"character": character_name, "source_type": "profile"}],
        )

    def index_lorebook_entry(self, entry_id: str, content: str, title: str = "") -> None:
        """索引世界书条目。"""
        col = self._get_collection("lorebook")
        doc_id = f"lore_{entry_id}"
        col.upsert(
            ids=[doc_id],
            documents=[content],
            metadatas=[{"entry_id": entry_id, "title": title, "source_type": "lorebook"}],
        )

    def query(
        self,
        text: str,
        collections: list[str] | None = None,
        n_results: int = 8,
    ) -> list[VectorChunk]:
        """跨 collection 语义检索。"""
        if collections is None:
            collections = ["chapters", "profiles", "lorebook"]

        results: list[VectorChunk] = []

        for col_name in collections:
            try:
                col = self._get_collection(col_name)
                if col.count() == 0:
                    continue
                res = col.query(
                    query_texts=[text],
                    n_results=min(n_results, col.count()),
                )
            except Exception:
                continue

            docs = res.get("documents", [[]])[0]
            metas = res.get("metadatas", [[]])[0]
            distances = res.get("distances", [[]])[0]

            for doc, meta, dist in zip(docs, metas, distances):
                score = max(0.0, 1.0 - dist)
                results.append(VectorChunk(
                    content=doc,
                    source_type=meta.get("source_type", col_name),
                    source_id=meta.get("entry_id", meta.get("character", f"ch{meta.get('chapter_id', '?')}")),
                    chapter_id=meta.get("chapter_id"),
                    score=score,
                    metadata=meta,
                ))

        results.sort(key=lambda c: c.score, reverse=True)
        return results[:n_results]

    def rebuild(self, project_dir: Path, outline: dict[str, Any]) -> dict[str, int]:
        """重建所有 collection。返回各 collection 的 chunk 数。"""
        stats = {"chapters": 0, "profiles": 0, "lorebook": 0}

        # 索引已生成的章节
        from . import state as state_mod
        st = state_mod.load(project_dir)
        chapters_dir = project_dir / "chapters"

        if chapters_dir.exists():
            for md_file in sorted(chapters_dir.glob("ch*.md")):
                text = md_file.read_text(encoding="utf-8")
                # 从文件名提取 chapter_id
                stem = md_file.stem
                try:
                    id_part = stem.split("_", 1)[0].replace("ch", "")
                    if "_" in id_part:
                        id_part = id_part.replace("_", ".")
                    cid = float(id_part)
                except ValueError:
                    continue

                summary = st.get("summaries", {}).get(str(int(cid) if cid == int(cid) else cid), "")
                n = self.index_chapter(cid, text, summary)
                stats["chapters"] += n

        # 索引角色档案
        from . import profiles as prof_mod
        prof_data = prof_mod.load(project_dir)
        for name in prof_data.get("characters", {}):
            state_at = prof_mod.effective_state_at(project_dir, name, 9999)
            if state_at:
                text = json.dumps(state_at, ensure_ascii=False)
                self.index_profile(name, f"{name}: {text}")
                stats["profiles"] += 1

        # 索引世界书
        try:
            from .lorebook import Lorebook
            lb = Lorebook(project_dir)
            for entry in lb.entries:
                self.index_lorebook_entry(entry.id, entry.content, entry.title)
                stats["lorebook"] += 1
        except Exception:
            pass

        return stats

    def status(self) -> dict[str, int]:
        """返回各 collection 的文档数。"""
        if not self.available:
            return {"available": False}
        try:
            self._ensure_client()
        except Exception:
            return {"available": False}

        result = {"available": True}
        for name in ["chapters", "profiles", "lorebook"]:
            try:
                col = self._get_collection(name)
                result[name] = col.count()
            except Exception:
                result[name] = 0
        return result

    @staticmethod
    def _split_text(text: str, chunk_size: int = 800, overlap: int = 100) -> list[str]:
        """按字符数分块，带重叠。"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start = end - overlap

        return chunks
