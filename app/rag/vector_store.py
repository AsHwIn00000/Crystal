import threading
import json
import os
import numpy as np
from pathlib import Path


class FAISSVectorStore:
    """
    High-performance, pure-NumPy vector store.
    Stores embeddings as .npy files and metadata as .meta.json files.
    Eliminates native C++ FAISS crashes, OpenMP thread contention, and memory overhead.

    Index files: {base_path}/{key}.npy
    Meta files:  {base_path}/{key}.meta.json
                 -> list of {chunk_db_id, document_id, scope, user_id}
    """
    DIM = 384  # matches all-MiniLM-L6-v2

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._locks: dict = {}
        self._meta_lock = threading.Lock()

    def _get_lock(self, key: str) -> threading.Lock:
        with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def _paths(self, key: str):
        return (
            self.base_path / f'{key}.npy',
            self.base_path / f'{key}.meta.json',
        )

    def load(self, key: str):
        emb_path, meta_path = self._paths(key)
        if not emb_path.exists() or not meta_path.exists():
            return np.empty((0, self.DIM), dtype=np.float32), []
        try:
            embeddings = np.load(str(emb_path))
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            return embeddings, meta
        except Exception:
            return np.empty((0, self.DIM), dtype=np.float32), []

    def save(self, key: str, embeddings: np.ndarray, meta: list):
        emb_path, meta_path = self._paths(key)
        # Atomic write to avoid corruptions or partial reads across threads
        tmp_emb = emb_path.with_suffix('.tmp.npy')
        tmp_meta = meta_path.with_suffix('.tmp.json')
        np.save(str(tmp_emb), embeddings)
        with open(tmp_meta, 'w', encoding='utf-8') as f:
            json.dump(meta, f)
        os.replace(str(tmp_emb), str(emb_path))
        os.replace(str(tmp_meta), str(meta_path))

    def add_chunks(self, key: str, embeddings: np.ndarray, meta_entries: list):
        """Thread-safe: acquires per-key lock before load -> add -> atomic save."""
        with self._get_lock(key):
            curr_emb, curr_meta = self.load(key)
            if curr_emb.size == 0:
                new_emb = embeddings.astype(np.float32)
            else:
                new_emb = np.vstack([curr_emb, embeddings.astype(np.float32)])
            curr_meta.extend(meta_entries)
            self.save(key, new_emb, curr_meta)

    def search(self, key: str, query_vec: np.ndarray, top_k: int = 10,
               allowed_chunk_ids: set = None) -> list:
        """Thread-safe search computing cosine similarity via dot product."""
        with self._get_lock(key):
            embeddings, meta = self.load(key)

        if embeddings.shape[0] == 0 or len(meta) == 0:
            return []

        # Normalize query vector
        q = query_vec.astype(np.float32).flatten()
        norm_q = np.linalg.norm(q)
        if norm_q > 0:
            q = q / norm_q

        # Normalize chunk embeddings
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        normalized_emb = embeddings / norms

        scores = np.dot(normalized_emb, q)
        ranked_indices = np.argsort(scores)[::-1]

        results = []
        for idx in ranked_indices:
            if idx >= len(meta):
                continue
            entry = meta[idx]
            if allowed_chunk_ids is not None and entry['chunk_db_id'] not in allowed_chunk_ids:
                continue
            results.append({**entry, 'score': float(scores[idx])})
            if len(results) >= top_k:
                break
        return results
