import re
from dataclasses import dataclass
from flask import current_app
from app.models.document import Document, DocumentChunk, DocumentScope, DocumentStatus
from app.extensions import db
from app.rag.reranker import rerank


@dataclass
class RetrievedChunk:
    chunk_db_id: int
    document_id: int
    doc_title: str
    page_number: int
    content: str
    score: float
    scope: str


class HybridRetriever:
    """Retrieves relevant chunks using FAISS semantic search + SQL keyword search.

    Scope enforcement:
    - Private chunks: filtered to current user's documents at SQL level
    - College-wide chunks: accessible to all authenticated users
    - document_ids filter: validated at API route level before calling retrieve()
    """

    def __init__(self, app=None):
        if app is None:
            app = current_app._get_current_object()
        self.vector_store = app.extensions['vector_store']
        self.embedder = app.extensions['embedder']
        self.threshold = app.config.get('RELEVANCE_THRESHOLD', 0.3)
        self.top_k = app.config.get('TOP_K_RETRIEVAL', 5)

    def retrieve(self, query: str, user_id: int,
                 document_ids: list = None) -> list:
        """Retrieve relevant chunks for the query, respecting scope boundaries."""
        results = []

        # --- College-wide scope ---
        cw_allowed = self._get_scope_chunk_ids(
            DocumentScope.COLLEGE_WIDE, user_id=None, document_ids=document_ids
        )
        # --- Private scope (current user only) ---
        priv_allowed = self._get_scope_chunk_ids(
            DocumentScope.PRIVATE, user_id=user_id, document_ids=document_ids
        )

        # Keyword augmentation (hybrid)
        keyword_chunk_ids = self._keyword_search(query, user_id, document_ids)

        # Fast path: If there are NO available document chunks in scope for this query,
        # return immediately without loading heavy embedding models into memory.
        if not cw_allowed and not priv_allowed and not keyword_chunk_ids:
            return []

        # Vector search (only when documents exist in scope)
        if cw_allowed or priv_allowed:
            try:
                query_vec = self.embedder.embed_one(query)
                if cw_allowed:
                    cw_results = self.vector_store.search(
                        'college_wide', query_vec, top_k=self.top_k, allowed_chunk_ids=cw_allowed
                    )
                    results.extend(cw_results)
                if priv_allowed:
                    priv_results = self.vector_store.search(
                        f'private_{user_id}', query_vec, top_k=self.top_k, allowed_chunk_ids=priv_allowed
                    )
                    results.extend(priv_results)
            except Exception as e:
                current_app.logger.warning('RAG vector search embedding failed: %s', e)

        # Add keyword results
        if keyword_chunk_ids:
            keyword_results = self._load_chunks_by_ids(
                keyword_chunk_ids,
                already_seen={r['chunk_db_id'] for r in results}
            )
            results.extend(keyword_results)

        # Filter by threshold, sort by score, deduplicate, take top_k
        raw_candidates = sorted(results, key=lambda r: r.get('score', 0), reverse=True)
        results = [
            r for r in raw_candidates
            if r.get('score', 0) >= self.threshold or r.get('keyword_match')
        ]

        # If user explicitly asked about specific document(s) (e.g. general overview/summarize prompt),
        # do not drop all chunks if the semantic similarity to generic query words like "overview" is below 0.35
        if not results and document_ids and raw_candidates:
            results = raw_candidates[:self.top_k]
        elif not results and document_ids:
            # Fallback: load the first top_k chunks directly for the specified document(s)
            fallback_chunks = db.session.query(DocumentChunk).filter(
                DocumentChunk.document_id.in_(document_ids)
            ).order_by(DocumentChunk.chunk_index.asc()).limit(self.top_k).all()
            results = [
                {
                    'chunk_db_id': c.id,
                    'document_id': c.document_id,
                    'score': 1.0,
                    'keyword_match': True
                }
                for c in fallback_chunks
            ]

        results = list({r['chunk_db_id']: r for r in results}.values())[:self.top_k]

        # Apply pass-through reranker (identity function — no-op in current version)
        hydrated = self._hydrate(results)
        return rerank(hydrated, query=query)

    def _get_scope_chunk_ids(self, scope, user_id, document_ids) -> set:
        q = db.session.query(DocumentChunk.id).join(Document).filter(
            Document.scope == scope,
            Document.status == DocumentStatus.READY,
        )
        if scope == DocumentScope.PRIVATE:
            q = q.filter(Document.user_id == user_id)
        if document_ids:
            q = q.filter(Document.id.in_(document_ids))
        return {row[0] for row in q.all()}

    def _keyword_search(self, query: str, user_id: int, document_ids) -> list:
        """SQL LIKE keyword search. Strips LIKE metacharacters to prevent wildcard table scans."""
        raw_terms = query.split()
        terms = []
        for t in raw_terms:
            clean = re.sub(r'[%_\\]', '', t)
            if len(clean) > 3:
                terms.append(clean)
        terms = terms[:5]
        if not terms:
            return []
        q = db.session.query(DocumentChunk.id).join(Document).filter(
            Document.status == DocumentStatus.READY,
            db.or_(
                db.and_(Document.scope == DocumentScope.COLLEGE_WIDE),
                db.and_(
                    Document.scope == DocumentScope.PRIVATE,
                    Document.user_id == user_id
                )
            )
        )
        if document_ids:
            q = q.filter(Document.id.in_(document_ids))
        filters = [DocumentChunk.content.ilike(f'%{term}%') for term in terms]
        q = q.filter(db.or_(*filters)).limit(20)
        return [row[0] for row in q.all()]

    def _load_chunks_by_ids(self, ids: list, already_seen: set) -> list:
        if not ids:
            return []
        new_ids = [i for i in ids if i not in already_seen]
        if not new_ids:
            return []
        chunks = db.session.query(DocumentChunk).filter(
            DocumentChunk.id.in_(new_ids)
        ).all()
        return [
            {
                'chunk_db_id': c.id,
                'document_id': c.document_id,
                'score': 0.0,
                'keyword_match': True
            }
            for c in chunks
        ]

    def _hydrate(self, raw: list) -> list:
        """Load full chunk content and document titles from the DB."""
        if not raw:
            return []
        chunk_ids = [r['chunk_db_id'] for r in raw]

        # Query 1: load DocumentChunk objects
        chunks_q = db.session.query(DocumentChunk).filter(
            DocumentChunk.id.in_(chunk_ids)
        ).all()
        chunks_by_id = {c.id: c for c in chunks_q}

        # Query 2: load Document titles and scopes for the chunks we have
        doc_ids = {c.document_id for c in chunks_q}
        docs_q = db.session.query(
            Document.id, Document.filename_original, Document.scope
        ).filter(Document.id.in_(doc_ids)).all()
        docs_by_id = {row.id: row for row in docs_q}

        result = []
        for r in raw:
            chunk = chunks_by_id.get(r['chunk_db_id'])
            if not chunk:
                continue  # chunk was deleted between retrieval and hydration — skip
            doc_row = docs_by_id.get(chunk.document_id)
            doc_title = doc_row.filename_original if doc_row else 'Unknown'
            scope_val = doc_row.scope.value if doc_row else r.get('scope', 'unknown')
            result.append(RetrievedChunk(
                chunk_db_id=chunk.id,
                document_id=chunk.document_id,
                doc_title=doc_title,
                page_number=chunk.page_number or 0,
                content=chunk.content,
                score=r.get('score', 0.0),
                scope=scope_val,
            ))
        return result
