import os
from pathlib import Path

from sqlalchemy import create_engine, event, inspect, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .models import Base, Person, PersonIdentity

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data/research.db")

if DATABASE_URL.startswith("sqlite:///") and ":memory:" not in DATABASE_URL:
    database_path = DATABASE_URL.removeprefix("sqlite:///").split("?", 1)[0]
    if database_path and not database_path.startswith("/"):
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)

engine_options: dict = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}
    if DATABASE_URL in {"sqlite://", "sqlite:///:memory:"}:
        engine_options["poolclass"] = StaticPool

engine = create_engine(DATABASE_URL, **engine_options)

if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_person_identity_schema() -> None:
    """Add global identity links and backfill legacy case-local people idempotently."""
    columns = {column["name"] for column in inspect(engine).get_columns("people")}
    if "identity_id" not in columns:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE people ADD COLUMN identity_id VARCHAR(36)"))
    with engine.begin() as connection:
        connection.execute(text("CREATE INDEX IF NOT EXISTS ix_people_identity_id ON people (identity_id)"))

    with SessionLocal() as db:
        legacy_people = list(db.scalars(select(Person).where(Person.identity_id.is_(None))))
        for person in legacy_people:
            identity = PersonIdentity(canonical_name=person.name)
            db.add(identity)
            db.flush()
            person.identity_id = identity.id
        if legacy_people:
            db.commit()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
