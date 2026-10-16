# Reranker — pass-through identity function
#
# This module is a placeholder for a future cross-encoder reranker.
# The current implementation returns chunks unchanged (identity function).
#
# TODO: To wire in a real reranker:
#   1. Install: pip install sentence-transformers (cross-encoder)
#   2. Load CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
#   3. Score each (query, chunk.content) pair
#   4. Re-sort chunks by cross-encoder score
#   5. Call rerank() from HybridRetriever.retrieve() after initial FAISS results


def rerank(chunks: list, query: str = None) -> list:
    """Pass-through identity reranker. Returns chunks unchanged.

    Args:
        chunks: List of RetrievedChunk objects
        query: The original query string (unused in pass-through)

    Returns:
        Same list of chunks in the same order
    """
    return chunks
