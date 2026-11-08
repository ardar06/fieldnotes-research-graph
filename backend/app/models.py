from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Case(Base):
    __tablename__ = "cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    purpose: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    people: Mapped[list["Person"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    sources: Mapped[list["Source"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    findings: Mapped[list["Finding"]] = relationship(back_populates="case", cascade="all, delete-orphan")
    relationships: Mapped[list["Link"]] = relationship(back_populates="case", cascade="all, delete-orphan")


class PersonIdentity(Base):
    __tablename__ = "person_identities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    canonical_name: Mapped[str] = mapped_column(String(140), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    memberships: Mapped[list["Person"]] = relationship(back_populates="identity")


class Person(Base):
    __tablename__ = "people"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    identity_id: Mapped[str | None] = mapped_column(
        ForeignKey("person_identities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    aliases: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    case: Mapped[Case] = relationship(back_populates="people")
    identity: Mapped[PersonIdentity | None] = relationship(back_populates="memberships")


class UsernameHandle(Base):
    __tablename__ = "username_handles"
    __table_args__ = (UniqueConstraint("case_id", "person_id", "username", name="uq_username_handle_case_person_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class UsernameScan(Base):
    __tablename__ = "username_scans"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    handle_id: Mapped[str] = mapped_column(ForeignKey("username_handles.id", ondelete="CASCADE"), index=True)
    site_names: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    authorization_acknowledged: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    results: Mapped[list["UsernameScanResult"]] = relationship(back_populates="scan", cascade="all, delete-orphan")


class UsernameScanResult(Base):
    __tablename__ = "username_scan_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scan_id: Mapped[str] = mapped_column(ForeignKey("username_scans.id", ondelete="CASCADE"), index=True)
    site_name: Mapped[str] = mapped_column(String(120), nullable=False)
    profile_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    http_status: Mapped[int | None] = mapped_column(nullable=True)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    scan: Mapped[UsernameScan] = relationship(back_populates="results")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    publisher: Mapped[str] = mapped_column(String(180), nullable=False, default="")
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieved_on: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    case: Mapped[Case] = relationship(back_populates="sources")


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), index=True)
    claim: Mapped[str] = mapped_column(String(2000), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    case: Mapped[Case] = relationship(back_populates="findings")
    person: Mapped[Person] = relationship()
    source: Mapped[Source] = relationship()


class Link(Base):
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    case_id: Mapped[str] = mapped_column(ForeignKey("cases.id", ondelete="CASCADE"), index=True)
    source_person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    target_person_id: Mapped[str] = mapped_column(ForeignKey("people.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="RESTRICT"), index=True)
    label: Mapped[str] = mapped_column(String(240), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    case: Mapped[Case] = relationship(back_populates="relationships")
    source_person: Mapped[Person] = relationship(foreign_keys=[source_person_id])
    target_person: Mapped[Person] = relationship(foreign_keys=[target_person_id])
    source: Mapped[Source] = relationship()
