from flask import request


def log_audit_event(event_type: str, resource_type: str = None, resource_id: int = None,
                    user_id: int = None, details: dict = None):
    """Helper to create an AuditEvent. Caller must commit the session."""
    from app.models.audit import AuditEvent
    ip = request.remote_addr if request else None
    AuditEvent.log(
        event_type=event_type,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=user_id,
        ip_address=ip,
        details=details
    )
