import pytest
from app.core.security import encrypt_api_key, decrypt_api_key, sanitize_workspace_path
from app.core.config import settings


def test_api_key_encryption_decryption():
    raw_key = "sk-or-v1-super-secret-api-key-test"
    encrypted = encrypt_api_key(raw_key)
    assert encrypted != raw_key
    assert len(encrypted) > 20

    decrypted = decrypt_api_key(encrypted)
    assert decrypted == raw_key


def test_empty_key_encryption():
    assert encrypt_api_key("") == ""
    assert decrypt_api_key("") == ""


def test_sanitize_workspace_path_valid():
    filename = "report.md"
    resolved = sanitize_workspace_path(filename)
    assert str(resolved).startswith(str(settings.workspace_path))
    assert resolved.name == "report.md"


def test_sanitize_workspace_path_traversal_detection():
    with pytest.raises(ValueError, match="Path traversal detected"):
        sanitize_workspace_path("../../etc/passwd")

    with pytest.raises(ValueError, match="Path traversal detected"):
        sanitize_workspace_path("../../../../sensitive_data.txt")
