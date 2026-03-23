from sqlalchemy import Column, String, DateTime, Boolean, BigInteger, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import uuid


class Base(DeclarativeBase):
    pass


def gen_uuid():
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id = Column(String, primary_key=True, default=gen_uuid)
    wallet_address = Column(String(44), unique=True, nullable=False, index=True)
    username = Column(String(50), unique=True, nullable=True)
    avatar_url = Column(String(255), nullable=True)
    arkv_balance = Column(BigInteger, default=0)
    is_admin = Column(Boolean, default=False)
    is_banned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen = Column(DateTime(timezone=True), onupdate=func.now())
    nonces = relationship("WalletNonce", back_populates="user", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="user")
    messages = relationship("ChatMessage", back_populates="user")


class WalletNonce(Base):
    __tablename__ = "wallet_nonces"
    id = Column(String, primary_key=True, default=gen_uuid)
    wallet_address = Column(String(44), ForeignKey("users.wallet_address", ondelete="CASCADE"), nullable=False)
    nonce = Column(String(64), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    used = Column(Boolean, default=False)
    user = relationship("User", back_populates="nonces")


class Announcement(Base):
    __tablename__ = "announcements"
    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(String, ForeignKey("users.id"), nullable=False)
    pinned = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Proposal(Base):
    __tablename__ = "proposals"
    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    author_id = Column(String, ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="active")
    votes_yes = Column(BigInteger, default=0)
    votes_no = Column(BigInteger, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    closes_at = Column(DateTime(timezone=True), nullable=True)
    votes = relationship("Vote", back_populates="proposal")


class Vote(Base):
    __tablename__ = "votes"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    proposal_id = Column(String, ForeignKey("proposals.id"), nullable=False)
    choice = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="votes")
    proposal = relationship("Proposal", back_populates="votes")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id = Column(String, primary_key=True, default=gen_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="messages")


class ExclusiveContent(Base):
    __tablename__ = "exclusive_content"
    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    min_arkv_required = Column(BigInteger, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
