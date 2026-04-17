ALLOWED_MIME_TYPES = {"image/png", "image/svg+xml", "image/jpeg"}
MAX_LOGO_SIZE = 512000


def validate_logo(content: bytes, content_type: str) -> tuple[bytes, str]:
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"Invalid content type: {content_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}")
    if len(content) > MAX_LOGO_SIZE:
        raise ValueError(f"Logo file too large: {len(content)} bytes. Maximum: {MAX_LOGO_SIZE} bytes")
    return content, content_type
