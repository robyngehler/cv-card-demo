from __future__ import annotations

import json
import os
from pathlib import Path
import sqlite3
import threading
import time
import uuid
from typing import Any, Dict, Optional


SCHEMA_STATEMENTS = [
        """
        CREATE TABLE IF NOT EXISTS candidates (
            candidate_id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            name TEXT,
            company TEXT,
            email TEXT,
            email_hash TEXT,
            name_company_hash TEXT,
            phone TEXT,
            website TEXT,
            metadata_confidence REAL,
            identity_status TEXT NOT NULL,
            merged_into_candidate_id TEXT,
            merged_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            candidate_id TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            state TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS answers (
            answer_id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            candidate_id TEXT,
            question_id TEXT NOT NULL,
            score REAL NOT NULL,
            rating REAL NOT NULL,
            source TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            fusion_state TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS snapshots (
            snapshot_id TEXT PRIMARY KEY,
            candidate_id TEXT,
            session_id TEXT,
            image_path TEXT NOT NULL,
            crop_path TEXT,
            ocr_text TEXT,
            extraction_json TEXT,
            created_at TEXT NOT NULL
        )
        """,
]

IDENTITY_STATUS_PRIORITY = {
        "MERGED": 0,
        "TEMPORARY": 1,
        "TEMPORARY_PRECHECK_FAILED": 1,
        "TEMPORARY_PRECHECK_UNRESOLVED": 1,
        "UNRESOLVED": 1,
        "VECTOR_SUGGESTED_REVIEW": 2,
        "DETERMINISTIC_NAME_COMPANY": 3,
        "MATCHED_NAME_COMPANY": 4,
        "DETERMINISTIC_EMAIL": 5,
        "MATCHED_EMAIL": 6,
}


class SQLiteRepositoryBase:
    def __init__(self, service: "SQLitePersistenceService"):
        self.service = service

    def connection(self):
        return self.service.connection()


class SQLiteCandidateRepository(SQLiteRepositoryBase):
    def ensure_candidate(self, *, candidate_id: str, identity_status: str = "TEMPORARY") -> None:
        now = self.service.utcnow()
        with self.connection() as connection:
            existing = self._fetch_one_from_connection(
                connection,
                "SELECT candidate_id, identity_status FROM candidates WHERE candidate_id = ?",
                (candidate_id,),
            )
            if existing is None:
                connection.execute(
                    """
                    INSERT INTO candidates (candidate_id, created_at, last_seen_at, identity_status)
                    VALUES (?, ?, ?, ?)
                    """,
                    (candidate_id, now, now, identity_status),
                )
                return

            connection.execute(
                "UPDATE candidates SET last_seen_at = ?, identity_status = ? WHERE candidate_id = ?",
                (
                    now,
                    self._preferred_identity_status(existing.get("identity_status"), identity_status),
                    candidate_id,
                ),
            )

    def upsert_metadata(self, candidate_id: str, metadata: Dict[str, Any], identity_status: str) -> None:
        now = self.service.utcnow()
        email = self._field_value(metadata, "email")
        name = self._field_value(metadata, "name")
        company = self._field_value(metadata, "company")
        phone = self._field_value(metadata, "phone")
        website = self._field_value(metadata, "website")
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO candidates (
                  candidate_id, created_at, last_seen_at, name, company, email, email_hash,
                  name_company_hash, phone, website, metadata_confidence, identity_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(candidate_id) DO UPDATE SET
                  last_seen_at=excluded.last_seen_at,
                  name=COALESCE(excluded.name, candidates.name),
                  company=COALESCE(excluded.company, candidates.company),
                  email=COALESCE(excluded.email, candidates.email),
                  email_hash=COALESCE(excluded.email_hash, candidates.email_hash),
                  name_company_hash=COALESCE(excluded.name_company_hash, candidates.name_company_hash),
                  phone=COALESCE(excluded.phone, candidates.phone),
                  website=COALESCE(excluded.website, candidates.website),
                  metadata_confidence=COALESCE(excluded.metadata_confidence, candidates.metadata_confidence),
                                    identity_status=CASE
                                        WHEN candidates.identity_status IS NULL THEN excluded.identity_status
                                        WHEN excluded.identity_status IS NULL THEN candidates.identity_status
                                        ELSE candidates.identity_status
                                    END
                """,
                (
                    candidate_id,
                    now,
                    now,
                    name,
                    company,
                    email,
                    metadata.get("email_hash"),
                    metadata.get("name_company_hash"),
                    phone,
                    website,
                    metadata.get("metadata_confidence"),
                    self._preferred_identity_status(
                        self.find_candidate(candidate_id).get("identity_status") if self.find_candidate(candidate_id) else None,
                        identity_status,
                    ),
                ),
            )

    def find_by_email_hash(self, email_hash: str) -> Optional[Dict[str, Any]]:
        if not email_hash:
            return None
        return self._fetch_one(
            "SELECT candidate_id, email_hash FROM candidates WHERE email_hash = ?",
            (email_hash,),
        )

    def find_by_name_company_hash(self, name_company_hash: str) -> Optional[Dict[str, Any]]:
        if not name_company_hash:
            return None
        return self._fetch_one(
            "SELECT candidate_id, name_company_hash FROM candidates WHERE name_company_hash = ?",
            (name_company_hash,),
        )

    def _fetch_one(self, query: str, params: tuple[Any, ...]) -> Optional[Dict[str, Any]]:
        with self.connection() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            return dict(row)

    def _fetch_one_from_connection(self, connection, query: str, params: tuple[Any, ...]) -> Optional[Dict[str, Any]]:
        connection.row_factory = sqlite3.Row
        row = connection.execute(query, params).fetchone()
        if row is None:
            return None
        return dict(row)

    def find_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        return self._fetch_one("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))

    def find_recent_candidates(self, limit: int = 10) -> list[Dict[str, Any]]:
        with self.connection() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                "SELECT * FROM candidates ORDER BY last_seen_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_merged(self, *, old_candidate_id: str, new_candidate_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                UPDATE candidates
                SET identity_status = 'MERGED', merged_into_candidate_id = ?, merged_at = ?
                WHERE candidate_id = ?
                """,
                (new_candidate_id, self.service.utcnow(), old_candidate_id),
            )

    def _field_value(self, metadata: Dict[str, Any], key: str) -> Optional[str]:
        value = metadata.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if value is None:
            return None
        value = str(value).strip()
        return value or None

    def _preferred_identity_status(self, existing_status: Optional[str], new_status: Optional[str]) -> Optional[str]:
        if new_status is None:
            return existing_status
        if existing_status is None:
            return new_status
        existing_priority = IDENTITY_STATUS_PRIORITY.get(existing_status, 1)
        new_priority = IDENTITY_STATUS_PRIORITY.get(new_status, 1)
        return existing_status if existing_priority >= new_priority else new_status


class SQLiteSessionRepository(SQLiteRepositoryBase):
    def create_session(self, *, session_id: str, candidate_id: Optional[str], state: str) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO sessions (session_id, candidate_id, started_at, completed_at, state)
                VALUES (?, ?, ?, NULL, ?)
                """,
                (session_id, candidate_id, self.service.utcnow(), state),
            )

    def complete_session(self, *, session_id: str, state: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE sessions SET completed_at = ?, state = ? WHERE session_id = ?",
                (self.service.utcnow(), state, session_id),
            )

    def reassign_candidate(self, *, old_candidate_id: str, new_candidate_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE sessions SET candidate_id = ? WHERE candidate_id = ?",
                (new_candidate_id, old_candidate_id),
            )

    def get_candidate_session_progress(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        with self.connection() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT sessions.session_id, sessions.candidate_id, sessions.state,
                       COUNT(answers.answer_id) AS answers_count
                FROM sessions
                LEFT JOIN answers ON answers.session_id = sessions.session_id
                WHERE sessions.candidate_id = ? AND sessions.completed_at IS NULL
                GROUP BY sessions.session_id, sessions.candidate_id, sessions.state
                ORDER BY sessions.started_at DESC
                LIMIT 1
                """,
                (candidate_id,),
            ).fetchone()
            return dict(row) if row is not None else None


class SQLiteAnswerRepository(SQLiteRepositoryBase):
    def save_answer(self, payload: Dict[str, Any]) -> str:
        answer_id = f"answer_{int(time.time() * 1000)}_{uuid.uuid4().hex[:8]}"
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO answers (answer_id, session_id, candidate_id, question_id, score, rating, source, timestamp, fusion_state)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    answer_id,
                    payload.get("session_id"),
                    payload.get("candidate_id"),
                    payload.get("question_id"),
                    float(payload.get("score") or 0.0),
                    float(payload.get("rating") or 0.0),
                    payload.get("source") or "unknown",
                    self.service.utcnow(),
                    payload.get("fusion_state"),
                ),
            )
        return answer_id

    def reassign_candidate(self, *, old_candidate_id: str, new_candidate_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE answers SET candidate_id = ? WHERE candidate_id = ?",
                (new_candidate_id, old_candidate_id),
            )


class SQLiteSnapshotRepository(SQLiteRepositoryBase):
    def save_snapshot(self, payload: Dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                """
                INSERT INTO snapshots (snapshot_id, candidate_id, session_id, image_path, crop_path, ocr_text, extraction_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.get("snapshot_id"),
                    payload.get("candidate_id"),
                    payload.get("session_id"),
                    payload.get("image_path"),
                    payload.get("crop_path"),
                    payload.get("ocr_text"),
                    payload.get("extraction_json"),
                    payload.get("created_at") or self.service.utcnow(),
                ),
            )

    def update_extraction(self, *, snapshot_id: str, raw_text: str, extraction_json: Dict[str, Any]) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE snapshots SET ocr_text = ?, extraction_json = ? WHERE snapshot_id = ?",
                (raw_text, json.dumps(extraction_json, ensure_ascii=True), snapshot_id),
            )

    def reassign_candidate(self, *, old_candidate_id: str, new_candidate_id: str) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE snapshots SET candidate_id = ? WHERE candidate_id = ?",
                (new_candidate_id, old_candidate_id),
            )


class SQLitePersistenceService:
    service_name = "persistence"

    def __init__(self, context):
        self.context = context
        persistence_config = context.config.get("persistence", {})
        self.enabled = bool(persistence_config.get("enabled", True))
        self.sqlite_path = str(persistence_config.get("sqlite_path", "./data/cv_card_demo.sqlite3"))
        self._lock = threading.Lock()
        if self.enabled:
            Path(self.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
            self.ensure_schema()

        self.candidates = SQLiteCandidateRepository(self)
        self.sessions = SQLiteSessionRepository(self)
        self.answers = SQLiteAnswerRepository(self)
        self.snapshots = SQLiteSnapshotRepository(self)

    def connection(self):
        if not self.enabled:
            raise RuntimeError("Persistence service disabled")
        connection = sqlite3.connect(self.sqlite_path, timeout=5.0, check_same_thread=False)
        return connection

    def ensure_schema(self) -> None:
        with self._lock:
            with self.connection() as connection:
                for statement in SCHEMA_STATEMENTS:
                    connection.execute(statement)
                self._ensure_column(connection, "candidates", "merged_into_candidate_id", "TEXT")
                self._ensure_column(connection, "candidates", "merged_at", "TEXT")
                self._ensure_column(connection, "answers", "candidate_id", "TEXT")

    def ensure_candidate(self, *, candidate_id: str, identity_status: str = "TEMPORARY") -> None:
        if not self.enabled:
            return
        self.candidates.ensure_candidate(candidate_id=candidate_id, identity_status=identity_status)

    def upsert_candidate(self, candidate_id: str, metadata: Dict[str, Any], identity_status: str) -> None:
        if not self.enabled:
            return
        self.candidates.upsert_metadata(candidate_id, metadata, identity_status)

    def create_session(self, *, session_id: str, candidate_id: Optional[str], state: str) -> None:
        if not self.enabled:
            return
        self.sessions.create_session(session_id=session_id, candidate_id=candidate_id, state=state)

    def complete_session(self, *, session_id: str, state: str) -> None:
        if not self.enabled:
            return
        self.sessions.complete_session(session_id=session_id, state=state)

    def save_answer(self, payload: Dict[str, Any]) -> Optional[str]:
        if not self.enabled:
            return None
        return self.answers.save_answer(payload)

    def save_snapshot(self, payload: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.snapshots.save_snapshot(payload)

    def update_snapshot_extraction(self, *, snapshot_id: str, raw_text: str, extraction_json: Dict[str, Any]) -> None:
        if not self.enabled:
            return
        self.snapshots.update_extraction(snapshot_id=snapshot_id, raw_text=raw_text, extraction_json=extraction_json)

    def reassign_candidate(self, *, old_candidate_id: str, new_candidate_id: str) -> None:
        if not self.enabled or old_candidate_id == new_candidate_id:
            return
        self.sessions.reassign_candidate(old_candidate_id=old_candidate_id, new_candidate_id=new_candidate_id)
        self.snapshots.reassign_candidate(old_candidate_id=old_candidate_id, new_candidate_id=new_candidate_id)
        self.answers.reassign_candidate(old_candidate_id=old_candidate_id, new_candidate_id=new_candidate_id)
        self.candidates.mark_merged(old_candidate_id=old_candidate_id, new_candidate_id=new_candidate_id)

    def find_candidate_by_email_hash(self, email_hash: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        return self.candidates.find_by_email_hash(email_hash)

    def find_candidate_by_name_company_hash(self, name_company_hash: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        return self.candidates.find_by_name_company_hash(name_company_hash)

    def find_candidate(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        return self.candidates.find_candidate(candidate_id)

    def find_recent_candidates(self, limit: int = 10) -> list[Dict[str, Any]]:
        if not self.enabled:
            return []
        return self.candidates.find_recent_candidates(limit=limit)

    def get_candidate_session_progress(self, candidate_id: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        return self.sessions.get_candidate_session_progress(candidate_id)

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "READY" if self.enabled else "DISABLED",
            "sqlite_path": self.sqlite_path,
            "exists": os.path.exists(self.sqlite_path),
        }

    @staticmethod
    def utcnow() -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    def _ensure_column(self, connection, table_name: str, column_name: str, definition: str) -> None:
        columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()]
        if column_name in columns:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")