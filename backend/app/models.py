import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, BigInteger, ForeignKey, DateTime, Text, JSON
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=False)
    created_ai = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
