import uuid
import os
from flask import current_app


ALLOWED_EXTENSIONS = {'pdf', 'docx', 'doc', 'pptx', 'txt', 'png', 'jpg', 'jpeg', 'xlsx', 'xls'}
ALLOWED_MIMES = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword',
    'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'txt': 'text/plain',
    'png': 'image/png',
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'xls': 'application/vnd.ms-excel',
}
MAGIC_BYTES = {
    'pdf': b'%PDF',
    'docx': b'PK\x03\x04',   # ZIP-based
    'pptx': b'PK\x03\x04',
    'xlsx': b'PK\x03\x04',
    'png': b'\x89PNG',
    'jpg': b'\xff\xd8\xff',
    'jpeg': b'\xff\xd8\xff',
}


class ValidationError(Exception):
    pass


def validate_upload(file_storage) -> tuple:
    """Validate an uploaded file. Returns (extension, stored_filename) or raises ValidationError."""
    original_name = file_storage.filename or ''
    ext = original_name.rsplit('.', 1)[-1].lower() if '.' in original_name else ''

    if ext not in ALLOWED_EXTENSIONS:
        raise ValidationError(f'File type .{ext} is not supported.')

    # MIME type check (client-provided — secondary signal only)
    content_type = file_storage.content_type or ''
    if ALLOWED_MIMES.get(ext) and content_type:
        declared_type = content_type.split(';')[0].strip()
        if declared_type and declared_type != ALLOWED_MIMES[ext]:
            # Log warning but do not reject — magic byte check below is authoritative
            current_app.logger.warning(
                "MIME mismatch for '%s': expected %s, got %s",
                original_name, ALLOWED_MIMES[ext], declared_type
            )

    # Read first 8 bytes for magic byte check
    header = file_storage.stream.read(8)
    file_storage.stream.seek(0)
    expected_magic = MAGIC_BYTES.get(ext)
    if expected_magic and not header.startswith(expected_magic):
        raise ValidationError('File content does not match its extension.')

    # File size check
    file_storage.stream.seek(0, 2)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 50 * 1024 * 1024)
    if size > max_size:
        raise ValidationError(f'File exceeds the {max_size // (1024 * 1024)} MB limit.')
    if size == 0:
        raise ValidationError('File is empty.')

    stored_name = f'{uuid.uuid4().hex}.{ext}'
    return ext, stored_name, size
