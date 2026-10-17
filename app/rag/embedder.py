import numpy as np


class SentenceTransformerEmbedder:
    MODEL_NAME = 'all-MiniLM-L6-v2'  # 384-dim, fast, good quality

    def __init__(self, model_name: str = None):
        self.model_name = model_name or self.MODEL_NAME
        self._model = None  # Lazy-loaded on first use

    def _get_model(self):
        if self._model is None:
            import gc
            try:
                import torch
                torch.set_num_threads(1)
                torch.set_grad_enabled(False)
            except Exception:
                pass
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device='cpu')
            gc.collect()
        return self._model

    def embed(self, texts: list) -> np.ndarray:
        import gc
        res = self._get_model().encode(
            texts,
            normalize_embeddings=True,
            batch_size=8,
            show_progress_bar=False
        )
        gc.collect()
        return res

    def embed_one(self, text: str) -> np.ndarray:
        return self.embed([text])[0]
