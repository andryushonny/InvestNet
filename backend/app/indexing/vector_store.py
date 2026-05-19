from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Optional

import numpy as np

DIM = 512


class VectorStore:
    """FAISS HNSW index + sqlite map for chunk metadata."""

    def __init__(self, index_path: Path, map_path: Path, dim: int = DIM):
        import faiss

        self.index_path = index_path
        self.map_path = map_path
        self.dim = dim
        self._lock = threading.RLock()
        self._faiss = faiss

        if index_path.exists():
            self.index = faiss.read_index(str(index_path))
        else:
            base = faiss.IndexHNSWFlat(dim, 32)
            base.hnsw.efConstruction = 200
            base.hnsw.efSearch = 64
            self.index = faiss.IndexIDMap2(base)

        map_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(map_path), check_same_thread=False)
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS faiss_map (
              faiss_id INTEGER PRIMARY KEY,
              chunk_text TEXT NOT NULL,
              person_id INTEGER NOT NULL,
              interaction_id INTEGER,
              metadata TEXT
            )
            """
        )
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_faiss_person ON faiss_map(person_id)")
        self.conn.commit()
        cur = self.conn.execute("SELECT COALESCE(MAX(faiss_id), 0) FROM faiss_map")
        self._next_id = int(cur.fetchone()[0]) + 1

    def add(self, vectors: list[list[float]], records: list[dict]) -> list[int]:
        assert len(vectors) == len(records)
        if not vectors:
            return []
        with self._lock:
            ids = list(range(self._next_id, self._next_id + len(vectors)))
            self._next_id += len(vectors)
            arr = np.asarray(vectors, dtype="float32")
            id_arr = np.asarray(ids, dtype="int64")
            self.index.add_with_ids(arr, id_arr)
            with self.conn:
                self.conn.executemany(
                    "INSERT INTO faiss_map (faiss_id, chunk_text, person_id, interaction_id, metadata) VALUES (?,?,?,?,?)",
                    [
                        (
                            fid,
                            r["text"],
                            r["person_id"],
                            r.get("interaction_id"),
                            json.dumps(r.get("metadata") or {}),
                        )
                        for fid, r in zip(ids, records)
                    ],
                )
            return ids

    def search(self, query_vec: list[float], top_k: int = 50) -> list[tuple[int, float, dict]]:
        if self.index.ntotal == 0:
            return []
        with self._lock:
            q = np.asarray([query_vec], dtype="float32")
            D, I = self.index.search(q, min(top_k, self.index.ntotal))
        results: list[tuple[int, float, dict]] = []
        ids = [int(i) for i in I[0] if i >= 0]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        cur = self.conn.execute(
            f"SELECT faiss_id, chunk_text, person_id, interaction_id, metadata FROM faiss_map WHERE faiss_id IN ({placeholders})",
            ids,
        )
        by_id = {row[0]: row for row in cur.fetchall()}
        for fid, dist in zip(I[0], D[0]):
            row = by_id.get(int(fid))
            if not row:
                continue
            md = json.loads(row[4] or "{}")
            md.update({"chunk_text": row[1], "person_id": row[2], "interaction_id": row[3]})
            results.append((int(fid), float(dist), md))
        return results

    def delete_by_person(self, person_id: int) -> None:
        with self._lock:
            cur = self.conn.execute("SELECT faiss_id FROM faiss_map WHERE person_id = ?", (person_id,))
            ids = [r[0] for r in cur.fetchall()]
            if not ids:
                return
            self.index.remove_ids(np.asarray(ids, dtype="int64"))
            with self.conn:
                self.conn.execute(
                    f"DELETE FROM faiss_map WHERE faiss_id IN ({','.join('?' for _ in ids)})",
                    ids,
                )

    def save(self) -> None:
        with self._lock:
            self.index_path.parent.mkdir(parents=True, exist_ok=True)
            self._faiss.write_index(self.index, str(self.index_path))

    @property
    def size(self) -> int:
        return int(self.index.ntotal)


_interactions: Optional[VectorStore] = None
_profiles: Optional[VectorStore] = None


def init_stores(interactions_idx: Path, interactions_map: Path, profiles_idx: Path, profiles_map: Path) -> None:
    global _interactions, _profiles
    _interactions = VectorStore(interactions_idx, interactions_map)
    _profiles = VectorStore(profiles_idx, profiles_map)


def interactions() -> VectorStore:
    assert _interactions is not None
    return _interactions


def profiles() -> VectorStore:
    assert _profiles is not None
    return _profiles


def save_all() -> None:
    if _interactions:
        _interactions.save()
    if _profiles:
        _profiles.save()
