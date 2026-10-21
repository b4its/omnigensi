import base64
import hashlib
from pathlib import Path
from cryptography.fernet import Fernet
from app.core.config import settings


def _get_fernet_key() -> bytes:
    raw_key = settings.ENCRYPTION_KEY.encode()
    try:
        # Check if it's already a valid Fernet key (32 url-safe base64-encoded bytes)
        decoded = base64.urlsafe_b64decode(raw_key)
        if len(decoded) == 32:
            return raw_key
    except Exception:
        pass
    # If not a standard 32-byte fernet key, derive a valid 32-byte urlsafe base64 key
    digest = hashlib.sha256(raw_key).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_key(plain_key: str) -> str:
    if not plain_key:
        return ""
    fernet = Fernet(_get_fernet_key())
    return fernet.encrypt(plain_key.encode()).decode()


def decrypt_api_key(enc_key: str) -> str:
    if not enc_key:
        return ""
    try:
        fernet = Fernet(_get_fernet_key())
        return fernet.decrypt(enc_key.encode()).decode()
    except Exception:
        # Fallback if plain key was passed directly
        return enc_key


def sanitize_workspace_path(relative_path: str) -> Path:
    """
    Sanitizes and resolves relative_path within the configured workspace root.
    Raises ValueError on directory traversal attempts.
    """
    workspace_root = settings.workspace_path
    clean_rel = Path(relative_path.lstrip("/\\"))
    resolved = (workspace_root / clean_rel).resolve()
    
    # Path traversal check
    if not str(resolved).startswith(str(workspace_root)):
        raise ValueError(f"Path traversal detected: {relative_path} escapes workspace root")
        
    return resolved
