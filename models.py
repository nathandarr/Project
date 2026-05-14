"""SQLAlchemy ORM models.

Imports `db` from app.py — Python resolves the partial-import cleanly because
app.py defines `db` before doing `from models import ...` at the bottom.
"""
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from werkzeug.security import check_password_hash, generate_password_hash

from app import db


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)

    first_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(30), nullable=True)

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    is_banned: Mapped[bool] = mapped_column(default=False)
    avatar_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    game_accounts: Mapped[list["GameAccount"]] = relationship(
        "GameAccount",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="GameAccount.id.desc()",
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def full_name(self) -> str:
        first = (self.first_name or "").strip()
        last = (self.last_name or "").strip()
        return f"{first} {last}".strip()


class GameAccount(db.Model):
    __tablename__ = "game_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_name: Mapped[str] = mapped_column(String(100), nullable=False)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False, default="OCE")
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    rank: Mapped[str] = mapped_column(String(50), nullable=False, default="Unranked")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="Active")
    notes: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    tags: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user: Mapped["User"] = relationship("User", back_populates="game_accounts")

    @property
    def tag_list(self) -> list[str]:
        if not self.tags:
            return []
        return [t.strip() for t in self.tags.split(",") if t.strip()]


class ProfileComment(db.Model):
    __tablename__ = "profile_comments"

    id: Mapped[int] = mapped_column(primary_key=True)
    body: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    profile_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    author: Mapped["User"] = relationship("User", foreign_keys=[author_id])
    profile_user: Mapped["User"] = relationship("User", foreign_keys=[profile_user_id])


class Message(db.Model):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    receiver_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    receiver: Mapped["User"] = relationship("User", foreign_keys=[receiver_id])

class CommentLike(db.Model):
    __tablename__ = "comment_likes"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    comment_id: Mapped[int] = mapped_column(ForeignKey("profile_comments.id"), nullable=False)
    vote_type: Mapped[str] = mapped_column(String(10), nullable=False, default="up")

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    comment: Mapped["ProfileComment"] = relationship("ProfileComment", foreign_keys=[comment_id])