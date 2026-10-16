"""RAG retriever tests."""
import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from app.extensions import db
from app.models.document import Document, DocumentChunk, DocumentScope, DocumentStatus
from app.models.user import User, UserRole


def make_user(email, role=UserRole.STUDENT):
    u = User(email=email, display_name=email, role=role)
    u.set_password('Test@1234!')
    db.session.add(u)
    db.session.flush()
    return u


def make_doc(user_id, scope, status=DocumentStatus.READY):
    doc = Document(
        user_id=user_id,
        filename_original='test.txt',
        filename_stored=f'{abs(hash(str(user_id) + str(scope)))}.txt',
        scope=scope,
        status=status,
        file_type='txt',
        file_size=100
    )
    db.session.add(doc)
    db.session.flush()
    return doc


def make_chunk(doc_id, content='test content', page=1):
    chunk = DocumentChunk(
        document_id=doc_id, chunk_index=0,
        content=content, embedding_model='all-MiniLM-L6-v2',
        page_number=page
    )
    db.session.add(chunk)
    db.session.flush()
    return chunk


def test_retriever_respects_private_scope(app):
    with app.app_context():
        u_a = make_user('raga@test.com')
        u_b = make_user('ragb@test.com')

        doc_a = make_doc(u_a.id, DocumentScope.PRIVATE)
        doc_b = make_doc(u_b.id, DocumentScope.PRIVATE)
        chunk_a = make_chunk(doc_a.id, 'user a content')
        chunk_b = make_chunk(doc_b.id, 'user b content')
        db.session.commit()

        from app.rag.retriever import HybridRetriever
        retriever = HybridRetriever(app)

        # Mock vector store to return no results (test keyword path)
        with patch.object(retriever.vector_store, 'search', return_value=[]):
            results = retriever.retrieve('user a content', user_id=u_a.id)

        # No results from user B's documents
        for r in results:
            assert r.document_id != doc_b.id


def test_retriever_returns_empty_for_no_docs(app):
    with app.app_context():
        u = make_user('empty@test.com')
        db.session.commit()

        from app.rag.retriever import HybridRetriever
        retriever = HybridRetriever(app)

        with patch.object(retriever.vector_store, 'search', return_value=[]):
            results = retriever.retrieve('test query', user_id=u.id)

        assert results == []


def test_vector_store_add_and_search(app, tmp_path):
    from app.rag.vector_store import FAISSVectorStore
    vs = FAISSVectorStore(tmp_path)
    embeddings = np.random.rand(3, 384).astype('float32')
    meta = [
        {'chunk_db_id': 1, 'document_id': 1, 'scope': 'private', 'user_id': 1},
        {'chunk_db_id': 2, 'document_id': 1, 'scope': 'private', 'user_id': 1},
        {'chunk_db_id': 3, 'document_id': 2, 'scope': 'private', 'user_id': 1},
    ]
    vs.add_chunks('private_1', embeddings, meta)

    query = np.random.rand(384).astype('float32')
    results = vs.search('private_1', query, top_k=2)
    assert len(results) <= 2


def test_embedder_produces_correct_shape(app):
    with app.app_context():
        embedder = app.extensions['embedder']
        vecs = embedder.embed(['hello world', 'test document'])
        assert vecs.shape == (2, 384)


def test_reranker_passthrough(app):
    from app.rag.reranker import rerank
    chunks = [MagicMock(), MagicMock()]
    result = rerank(chunks, query='test')
    assert result is chunks
