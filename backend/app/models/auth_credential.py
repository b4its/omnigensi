"""Stores an operator-changed password so the env default can be rotated.

``APP_PASSWORD`` remains the source of truth until someone changes it from the
UI. Changing the password from the app writes a salted hash here, which then
takes precedence; removing the row reverts to the environment value.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthCredential(Base):
    """A single row (singleton) holding the current password hash."""

    __tablename__ = "auth_credential"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # PBKDF2-HMAC-SHA256 in the form "pbkdf2_sha256$<iterations>$<salt>$<hash>"
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
