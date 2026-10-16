"""Document upload, status, and delete tests."""
import io
import pytest
from app.extensions import db
from app.models.document import Document, DocumentScope


def _pdf_bytes():
    """Minimal valid PDF bytes."""
    return b'%PDF-1.4\n%%EOF'


def _txt_bytes():
    return b'Hello world, this is test content.'


def test_upload_valid_txt(authenticated_client, app):
    data = {'file': (io.BytesIO(_txt_bytes()), 'test.txt', 'text/plain')}
    res = authenticated_client.post('/api/documents', data=data,
                                    content_type='multipart/form-data')
    assert res.status_code == 202
    doc = res.get_json()['document']
    assert doc['file_type'] == 'txt'


def test_upload_invalid_extension_rejected(authenticated_client):
    data = {'file': (io.BytesIO(b'content'), 'file.exe', 'application/octet-stream')}
    res = authenticated_client.post('/api/documents', data=data,
                                    content_type='multipart/form-data')
    assert res.status_code == 400


def test_upload_magic_byte_mismatch_rejected(authenticated_client):
    """Claim to be PDF but send bad magic bytes."""
    data = {'file': (io.BytesIO(b'NOT_A_PDF_content'), 'fake.pdf', 'application/pdf')}
    res = authenticated_client.post('/api/documents', data=data,
                                    content_type='multipart/form-data')
    assert res.status_code == 400


def test_upload_no_file_rejected(authenticated_client):
    res = authenticated_client.post('/api/documents', data={},
                                    content_type='multipart/form-data')
    assert res.status_code == 400


def test_delete_own_document(authenticated_client, app):
    # Upload
    data = {'file': (io.BytesIO(_txt_bytes()), 'del.txt', 'text/plain')}
    res = authenticated_client.post('/api/documents', data=data,
                                    content_type='multipart/form-data')
    doc_id = res.get_json()['document']['id']

    # Delete
    res = authenticated_client.delete(f'/api/documents/{doc_id}')
    assert res.status_code == 204


def test_get_document_status_own(authenticated_client, app):
    data = {'file': (io.BytesIO(_txt_bytes()), 'status.txt', 'text/plain')}
    res = authenticated_client.post('/api/documents', data=data,
                                    content_type='multipart/form-data')
    doc_id = res.get_json()['document']['id']

    res = authenticated_client.get(f'/api/documents/{doc_id}/status')
    assert res.status_code == 200
    data = res.get_json()
    assert 'status' in data


def test_list_documents_only_own_private(authenticated_client, app):
    res = authenticated_client.get('/api/documents?scope=private')
    assert res.status_code == 200
    data = res.get_json()
    # All returned docs should be private scope
    for doc in data.get('documents', []):
        assert doc['scope'] == 'private'


def test_cannot_delete_other_users_document(app, client):
    """User B should not be able to delete User A's document."""
    from hashlib import sha512
    from app.models.user import User, UserRole
    from app.models.document import Document, DocumentScope, DocumentStatus

    def _sid():
        base = 'None|None'
        h = sha512()
        h.update(base.encode('utf8'))
        return h.hexdigest()

    with app.app_context():
        u_a = User(email='owner@test.com', display_name='Owner')
        u_a.set_password('Test@1234!')
        db.session.add(u_a)
        db.session.flush()

        doc = Document(
            user_id=u_a.id, filename_original='private.txt',
            filename_stored='00000000.txt', scope=DocumentScope.PRIVATE,
            status=DocumentStatus.READY, file_type='txt', file_size=100
        )
        db.session.add(doc)
        db.session.commit()
        doc_id = doc.id

        u_b = User(email='attacker@test.com', display_name='Attacker')
        u_b.set_password('Test@1234!')
        db.session.add(u_b)
        db.session.commit()
        uid_b, pv_b = u_b.id, u_b.password_version

    with client.session_transaction() as sess:
        sess['_user_id'] = str(uid_b)
        sess['_fresh'] = True
        sess['password_version'] = pv_b
        sess['_id'] = _sid()

    res = client.delete(f'/api/documents/{doc_id}')
    assert res.status_code in (403, 404)
