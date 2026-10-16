"""Admin blueprint tests."""
import io
import pytest
from app.extensions import db
from app.models.user import User, UserRole


def test_student_cannot_access_admin_dashboard(authenticated_client):
    res = authenticated_client.get('/admin/')
    assert res.status_code in (302, 403)


def test_admin_can_access_dashboard(admin_client):
    res = admin_client.get('/admin/')
    assert res.status_code == 200


def test_admin_can_list_college_docs(admin_client):
    res = admin_client.get('/admin/documents')
    assert res.status_code == 200
    data = res.get_json()
    assert 'documents' in data


def test_admin_can_upload_college_wide_doc(admin_client, app):
    txt_bytes = b'College-wide test document content.'
    data = {'file': (io.BytesIO(txt_bytes), 'college.txt', 'text/plain')}
    res = admin_client.post('/admin/documents', data=data,
                            content_type='multipart/form-data')
    assert res.status_code == 202
    doc = res.get_json()['document']
    assert doc['file_type'] == 'txt'


def test_admin_can_delete_college_wide_doc(admin_client, app):
    # Upload first
    txt_bytes = b'College delete test content.'
    data = {'file': (io.BytesIO(txt_bytes), 'todel.txt', 'text/plain')}
    res = admin_client.post('/admin/documents', data=data,
                            content_type='multipart/form-data')
    doc_id = res.get_json()['document']['id']

    # Delete
    res = admin_client.delete(f'/admin/documents/{doc_id}')
    assert res.status_code == 204


def test_admin_can_list_users(admin_client):
    res = admin_client.get('/admin/users')
    assert res.status_code == 200
    data = res.get_json()
    assert 'users' in data
    assert len(data['users']) >= 1


def test_admin_can_toggle_user_active(admin_client, app):
    # Create a student user to toggle
    with app.app_context():
        student = User(email='toggle@test.com', display_name='Toggle')
        student.set_password('Test@1234!')
        db.session.add(student)
        db.session.commit()
        uid = student.id

    res = admin_client.put(f'/admin/users/{uid}/toggle-active', json={})
    assert res.status_code == 200
    data = res.get_json()
    # Original is_active=True, so it should now be False
    assert data['user']['is_active'] == False


def test_student_cannot_upload_college_wide(authenticated_client):
    txt_bytes = b'Student trying to upload college-wide.'
    data = {'file': (io.BytesIO(txt_bytes), 'hack.txt', 'text/plain')}
    res = authenticated_client.post('/admin/documents', data=data,
                                    content_type='multipart/form-data')
    assert res.status_code in (302, 403)
