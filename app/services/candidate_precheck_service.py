from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any, Dict, Optional


@dataclass
class CandidatePrecheckResult:
    resolved: bool
    candidate_id: str | None
    identity_status: str
    matched_on: str
    confidence: float
    snapshot_id: str | None = None
    raw_text: str | None = None
    # Name/company extracted by OCR during precheck. Surfaced so the UI can greet
    # the visitor immediately — even a brand-new visitor whose name is not yet
    # persisted (the temporary candidate is only written later, in SNAPSHOT).
    name: str | None = None
    company: str | None = None
    debug: dict = field(default_factory=dict)


class CandidatePrecheckService:
    service_name = "candidate_precheck"

    def __init__(self, context):
        self.context = context
        config = context.config.get("identity", {}).get("precheck", {})
        self.enabled = bool(config.get("enabled", True))
        self.max_duration_s = float(config.get("max_duration_s", 1.0))
        self.min_card_confidence = float(config.get("min_card_confidence", 0.35))
        self.require_ocr_for_known_match = bool(config.get("require_ocr_for_known_match", True))
        self.allow_vector_match = bool(config.get("allow_vector_match", False))

    def resolve_from_frame(self, *, frame, card_measurement, budget_s: Optional[float] = None) -> CandidatePrecheckResult:
        if not self.enabled:
            return CandidatePrecheckResult(
                resolved=False,
                candidate_id=None,
                identity_status="PRECHECK_DISABLED",
                matched_on="disabled",
                confidence=0.0,
            )

        if card_measurement is None or float(getattr(card_measurement, "confidence", 0.0) or 0.0) < self.min_card_confidence:
            return CandidatePrecheckResult(
                resolved=False,
                candidate_id=None,
                identity_status="PRECHECK_SKIPPED_LOW_CONFIDENCE",
                matched_on="low_confidence",
                confidence=float(getattr(card_measurement, "confidence", 0.0) or 0.0),
            )

        effective_budget = self.max_duration_s if budget_s is None else min(self.max_duration_s, float(budget_s))
        started_at = time.monotonic()

        snapshot_service = self.context.get_service("snapshot", default=None)
        ocr_service = self.context.get_service("ocr", default=None)
        identity = self.context.get_service("identity", default=None)
        persistence = self.context.get_service("persistence", default=None)
        vector = self.context.get_service("vector", default=None)
        if snapshot_service is None or ocr_service is None or identity is None or persistence is None:
            return CandidatePrecheckResult(
                resolved=False,
                candidate_id=None,
                identity_status="PRECHECK_UNAVAILABLE",
                matched_on="unavailable",
                confidence=0.0,
            )

        preview = snapshot_service.capture_preview(frame=frame, card_measurement=card_measurement)
        if (time.monotonic() - started_at) > effective_budget:
            return CandidatePrecheckResult(
                resolved=False,
                candidate_id=None,
                identity_status="PRECHECK_BUDGET_EXCEEDED",
                matched_on="timeout",
                confidence=0.0,
                snapshot_id=preview.snapshot_id,
            )

        metadata = ocr_service.process_snapshot(preview.image_path, preview.crop_path)
        if self.require_ocr_for_known_match and not (metadata.get("raw_text") or "").strip():
            return CandidatePrecheckResult(
                resolved=False,
                candidate_id=None,
                identity_status="PRECHECK_NO_OCR_MATCH",
                matched_on="ocr_empty",
                confidence=0.0,
                snapshot_id=preview.snapshot_id,
            )

        decision = identity.precheck_candidate(
            metadata,
            persistence_service=persistence,
            vector_service=vector,
            allow_vector_match=self.allow_vector_match,
        )
        return CandidatePrecheckResult(
            resolved=decision.candidate_id is not None,
            candidate_id=decision.candidate_id,
            identity_status=decision.identity_status,
            matched_on=decision.matched_on,
            confidence=float(metadata.get("metadata_confidence", 0.0) or 0.0),
            snapshot_id=preview.snapshot_id,
            raw_text=metadata.get("raw_text"),
            name=(metadata.get("name") or {}).get("value"),
            company=(metadata.get("company") or {}).get("value"),
            debug=decision.debug,
        )

    def get_status(self):
        return {
            "status": "READY" if self.enabled else "DISABLED",
            "max_duration_s": self.max_duration_s,
        }