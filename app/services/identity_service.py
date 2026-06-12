from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re
import time
import unicodedata
import uuid
from typing import Any, Dict, Optional


@dataclass
class IdentityDecision:
    candidate_id: Optional[str]
    identity_status: str
    matched_on: str
    needs_review: bool = False
    debug: Dict[str, Any] = field(default_factory=dict)


class CandidateIdentityResolver:
    service_name = "identity"

    def __init__(self, context):
        self.context = context
        self.status: Dict[str, Any] = {
            "status": "READY",
        }

    def create_temporary_candidate_id(self) -> str:
        timestamp = time.strftime("%Y_%m_%d_%H%M%S", time.gmtime())
        return f"tmp_{timestamp}_{uuid.uuid4().hex[:6]}"

    def create_session_id(self) -> str:
        timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return f"session_{timestamp}_{uuid.uuid4().hex[:6]}"

    def resolve_candidate_id(self, metadata: Dict[str, Any]) -> IdentityDecision:
        email = self._normalized_field_value(metadata, "email")
        if email:
            email_hash = self._hash_identifier(email)
            return IdentityDecision(
                candidate_id=self._candidate_id_from_hash("cand_email", email_hash),
                identity_status="DETERMINISTIC_EMAIL",
                matched_on="email",
                needs_review=False,
                debug={"email_hash": email_hash},
            )

        # Key on the NAME alone, not name+company. The heuristic company field is
        # unstable across OCR runs (it picks the longest non-role line, which
        # flips frame to frame), so a name|company hash produced a new candidate
        # id on every scan and the same visitor was never recognized. The name is
        # read reliably; normalizing it (drop diacritics/punctuation, collapse
        # whitespace, lowercase) makes the hash stable across OCR jitter.
        # NOTE: the hash is still stored/queried via the existing
        # ``name_company_hash`` column and the *_NAME_COMPANY status labels to
        # keep the persistence schema and downstream checks unchanged.
        name_key = self._normalize_identity_key(self._normalized_field_value(metadata, "name"))
        if name_key:
            name_company_hash = self._hash_identifier(name_key)
            return IdentityDecision(
                candidate_id=self._candidate_id_from_hash("cand_name_company", name_company_hash),
                identity_status="DETERMINISTIC_NAME_COMPANY",
                matched_on="name_company",
                needs_review=False,
                debug={"name_company_hash": name_company_hash},
            )

        return IdentityDecision(
            candidate_id=self.create_temporary_candidate_id(),
            identity_status="TEMPORARY",
            matched_on="temporary",
            needs_review=True,
        )

    def match_candidate(
        self,
        metadata: Dict[str, Any],
        *,
        persistence_service=None,
        vector_service=None,
    ) -> IdentityDecision:
        decision = self.resolve_candidate_id(metadata)
        if persistence_service is None:
            return decision

        if decision.matched_on == "email":
            email_hash = decision.debug.get("email_hash")
            existing = persistence_service.find_candidate_by_email_hash(email_hash)
            if existing is not None:
                decision.candidate_id = existing["candidate_id"]
                decision.identity_status = "MATCHED_EMAIL"
                return decision

        if decision.matched_on == "name_company":
            name_company_hash = decision.debug.get("name_company_hash")
            existing = persistence_service.find_candidate_by_name_company_hash(name_company_hash)
            if existing is not None:
                decision.candidate_id = existing["candidate_id"]
                decision.identity_status = "MATCHED_NAME_COMPANY"
                return decision

        if vector_service is not None:
            raw_text = metadata.get("raw_text") or ""
            if raw_text.strip():
                candidates = vector_service.search_text(raw_text, limit=3)
                decision.debug["vector_candidates"] = candidates
                threshold = float(self.context.config.get("identity", {}).get("vector", {}).get("review_threshold", 0.85))
                if candidates and float(candidates[0].get("score", 0.0)) >= threshold and metadata.get("needs_review"):
                    decision.identity_status = "VECTOR_SUGGESTED_REVIEW"
                    decision.needs_review = True

        return decision

    def precheck_candidate(
        self,
        metadata: Dict[str, Any],
        persistence_service,
        vector_service=None,
        allow_vector_match: bool = False,
    ) -> IdentityDecision:
        decision = self.resolve_candidate_id(metadata)
        if persistence_service is None:
            return IdentityDecision(
                candidate_id=None,
                identity_status="UNRESOLVED",
                matched_on="unresolved",
                needs_review=True,
            )

        if decision.matched_on == "email":
            existing = persistence_service.find_candidate_by_email_hash(decision.debug.get("email_hash"))
            if existing is not None:
                return IdentityDecision(
                    candidate_id=existing["candidate_id"],
                    identity_status="MATCHED_EMAIL",
                    matched_on="email",
                    needs_review=False,
                    debug={"email_hash": decision.debug.get("email_hash")},
                )

        if decision.matched_on == "name_company":
            existing = persistence_service.find_candidate_by_name_company_hash(decision.debug.get("name_company_hash"))
            if existing is not None:
                return IdentityDecision(
                    candidate_id=existing["candidate_id"],
                    identity_status="MATCHED_NAME_COMPANY",
                    matched_on="name_company",
                    needs_review=False,
                    debug={"name_company_hash": decision.debug.get("name_company_hash")},
                )

        if allow_vector_match and vector_service is not None:
            raw_text = metadata.get("raw_text") or ""
            if raw_text.strip():
                candidates = vector_service.search_text(raw_text, limit=3)
                threshold = float(self.context.config.get("identity", {}).get("vector", {}).get("review_threshold", 0.85))
                if candidates and float(candidates[0].get("score", 0.0)) >= threshold:
                    return IdentityDecision(
                        candidate_id=candidates[0].get("payload", {}).get("candidate_id") or candidates[0].get("id"),
                        identity_status="VECTOR_SUGGESTED_REVIEW",
                        matched_on="vector",
                        needs_review=True,
                        debug={"vector_candidates": candidates},
                    )

        return IdentityDecision(
            candidate_id=None,
            identity_status="UNRESOLVED",
            matched_on="unresolved",
            needs_review=True,
            debug=decision.debug,
        )

    def get_status(self) -> Dict[str, Any]:
        return dict(self.status)

    def _normalized_field_value(self, metadata: Dict[str, Any], field_name: str) -> Optional[str]:
        field_value = metadata.get(field_name)
        if isinstance(field_value, dict):
            field_value = field_value.get("value")
        if field_value is None:
            return None
        normalized = str(field_value).strip().lower()
        return normalized or None

    @staticmethod
    def _normalize_identity_key(value: Optional[str]) -> Optional[str]:
        """Collapse OCR jitter so the same person hashes to the same key.

        Strips diacritics (``BRÜCKNER`` -> ``bruckner``), lowercases, and keeps
        only alphanumeric tokens joined by single spaces. Returns ``None`` if no
        usable characters remain.
        """
        if not value:
            return None
        decomposed = unicodedata.normalize("NFKD", value)
        ascii_value = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
        tokens = re.findall(r"[a-z0-9]+", ascii_value.lower())
        return " ".join(tokens) or None

    def _hash_identifier(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _candidate_id_from_hash(prefix: str, digest: str) -> str:
        return f"{prefix}_{digest[:16]}"