from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

from .models import Project


DATA_DIR = Path(os.getenv("FOLDSPEC_DATA_DIR", "./data")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "foldspec.sqlite3"


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with connect() as db:
        db.execute("CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, updated_at TEXT NOT NULL, document TEXT NOT NULL)")
        db.execute("CREATE TABLE IF NOT EXISTS revisions (project_id TEXT NOT NULL, revision INTEGER NOT NULL, document TEXT NOT NULL, PRIMARY KEY(project_id, revision))")
        db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL, revision INTEGER NOT NULL, status TEXT NOT NULL, spec_json TEXT NOT NULL, result TEXT)")


def save(project: Project, *, new_revision: bool = False) -> Project:
    from datetime import UTC, datetime

    project.updated_at = datetime.now(UTC)
    if new_revision:
        project.revision += 1
        project.spec.revision = project.revision
    payload = project.model_dump_json()
    spec_payload = project.spec.model_dump_json()
    with connect() as db:
        db.execute("INSERT INTO projects(id, updated_at, document) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at, document=excluded.document", (project.id, project.updated_at.isoformat(), payload))
        # Revision rows are immutable specification snapshots. Conversation,
        # display preferences, and build state live on the mutable project row.
        db.execute("INSERT OR IGNORE INTO revisions(project_id, revision, document) VALUES (?, ?, ?)", (project.id, project.revision, spec_payload))
    return project


def get(project_id: str) -> Project | None:
    with connect() as db:
        row = db.execute("SELECT document FROM projects WHERE id=?", (project_id,)).fetchone()
    return Project.model_validate_json(row["document"]) if row else None


def list_projects() -> list[Project]:
    with connect() as db:
        rows = db.execute("SELECT document FROM projects ORDER BY updated_at DESC").fetchall()
    return [Project.model_validate_json(row["document"]) for row in rows]


def get_revision(project_id: str, revision: int) -> Project | None:
    with connect() as db:
        row = db.execute("SELECT document FROM revisions WHERE project_id=? AND revision=?", (project_id, revision)).fetchone()
    if not row:
        return None
    document = json.loads(row["document"])
    current = get(project_id)
    if not current:
        return None
    snapshot = current.model_copy(deep=True)
    # Accept full project documents written by the earlier prototype format.
    snapshot.spec = Project.model_validate(document).spec if "spec" in document else Project.model_validate({**current.model_dump(), "spec": document}).spec
    snapshot.revision = revision
    snapshot.spec.revision = revision
    snapshot.build = current.build if revision == current.revision else None
    return snapshot


def list_revisions(project_id: str) -> list[Project]:
    with connect() as db:
        numbers = [row["revision"] for row in db.execute("SELECT revision FROM revisions WHERE project_id=? ORDER BY revision DESC", (project_id,)).fetchall()]
    return [snapshot for number in numbers if (snapshot := get_revision(project_id, number)) is not None]
