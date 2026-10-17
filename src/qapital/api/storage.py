"""Finished results, kept so a link to a result keeps working and an identical request is answered instantly.

SQLAlchemy Core on one table; SQLite by default, any database SQLAlchemy supports (e.g. Postgres) through the
DATABASE_URL setting. Results are stored as the JSON the website receives."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, select
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

metadata = MetaData()
results = Table(
    "results",
    metadata,
    Column("id", String(32), primary_key=True),
    Column("kind", String(16), nullable=False),
    Column("request_key", String(64), nullable=False, index=True),  # sha256 of the request and the snapshot
    Column("snapshot", String(32), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("payload", Text, nullable=False),
)


class Storage:
    def __init__(self, url: str):
        self.engine: Engine = _engine(url)
        metadata.create_all(self.engine)

    def save(self, kind: str, request_key: str, snapshot: str, payload: str, result_id: str | None = None) -> str:
        result_id = result_id or uuid.uuid4().hex
        with self.engine.begin() as connection:
            connection.execute(
                results.insert().values(
                    id=result_id,
                    kind=kind,
                    request_key=request_key,
                    snapshot=snapshot,
                    created_at=datetime.now(UTC),
                    payload=payload,
                )
            )
        return result_id

    def get(self, result_id: str) -> tuple[str, str] | None:
        """(kind, payload) of a stored result."""
        with self.engine.connect() as connection:
            row = connection.execute(select(results.c.kind, results.c.payload).where(results.c.id == result_id)).first()
        return (row.kind, row.payload) if row else None

    def find(self, request_key: str) -> tuple[str, str, str] | None:
        """(id, kind, payload) of the newest result for an identical request, if any."""
        query = (
            select(results.c.id, results.c.kind, results.c.payload)
            .where(results.c.request_key == request_key)
            .order_by(results.c.created_at.desc())
            .limit(1)
        )
        with self.engine.connect() as connection:
            row = connection.execute(query).first()
        return (row.id, row.kind, row.payload) if row else None


def _engine(url: str) -> Engine:
    # Hosted Postgres services hand out postgres:// or postgresql:// URLs; SQLAlchemy needs the driver named.
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url.removeprefix(prefix)
    if url.startswith("sqlite"):
        options: dict = {"connect_args": {"check_same_thread": False}}
        if url in ("sqlite://", "sqlite:///:memory:"):
            options["poolclass"] = StaticPool  # one shared in-memory database, for tests
        return create_engine(url, **options)
    return create_engine(url, pool_pre_ping=True)
