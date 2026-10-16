import threading
import faiss
import json
import numpy as np
from pathlib import Path


class FAISSVectorStore:
    """
    Maintains one FAISS index per scope (college_wide) or per user (private).
    Index files: {base_path}/{key}.index
    Meta files:  {base_path}/{key}.meta.json
                 → list of {chunk_db_id, document_id, scope, user_id}

    Thread safety: each key has its own threading.Lock acquired around
    load → mutate → save operations to prevent concurrent writes corrupting
    the index file. FAISS computation is performed after releasing the lock
    to avoid blocking concurrent operations on other keys.

    Key scheme:
      - Private scope:   key = f"private_{user_id}"
      - College-wide:    key = "college_wide"
    """
    DIM = 384  # matches all-MiniLM-L6-v2

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._locks: dict = {}
        self._meta_lock = threading.Lock()  # protects self._locks dict itself

    def _get_lock(self, key: str) -> threading.Lock:
        with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
            return self._locks[key]

    def _paths(self, key: str):
        return (
            self.base_path / f'{key}.index',
            self.base_path / f'{key}.meta.json',
        )

    def load(self, key: str):
        idx_path, meta_path = self._paths(key)
        if not idx_path.exists():
            return faiss.IndexFlatIP(self.DIM), []
        index = faiss.read_index(str(idx_path))
        with open(meta_path) as f:
            meta = json.load(f)
        return index, meta

    def save(self, key: str, index, meta: list):
        idx_path, meta_path = self._paths(key)
        faiss.write_index(index, str(idx_path))
        with open(meta_path, 'w') as f:
            json.dump(meta, f)

    def add_chunks(self, key: str, embeddings: np.ndarray, meta_entries: list):
        """Thread-safe: acquires per-key lock before load→add→save."""
        with self._get_lock(key):
            index, meta = self.load(key)
            index.add(embeddings.astype('float32'))
            meta.extend(meta_entries)
            self.save(key, index, meta)

    def search(self, key: str, query_vec: np.ndarray, top_k: int = 10,
               allowed_chunk_ids: set = None) -> list:
        """Thread-safe search. Acquires lock to load index, then releases before FAISS compute."""
        with self._get_lock(key):
            # Load index inside lock — safe against concurrent writes
            index, meta = self.load(key)
        # FAISS search is CPU-bound; performed outside the lock so it does not
        # block concurrent add_chunks calls for other keys, or reads for this key
        # once we have a local copy of the index object.
        if index.ntotal == 0:
            return []
        search_k = min(top_k * 3, index.ntotal)
        scores, indices = index.search(
            query_vec.reshape(1, -1).astype('float32'), search_k
        )
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0 or idx >= len(meta):
                continue
            entry = meta[idx]
            if allowed_chunk_ids is not None and entry['chunk_db_id'] not in allowed_chunk_ids:
                continue
            results.append({**entry, 'score': float(score)})
            if len(results) >= top_k:
                break
        return results
