from __future__ import annotations

from dataclasses import asdict


class SnapshotProcessingService:
    service_name = "snapshot_processing"

    def __init__(self, context):
        self.context = context

    def process_snapshot(self, snapshot_record) -> None:
        ocr_service = self.context.get_service("ocr", default=None)
        persistence = self.context.get_service("persistence", default=None)
        identity = self.context.get_service("identity", default=None)
        vector = self.context.get_service("vector", default=None)
        if ocr_service is None:
            return

        extraction = ocr_service.process_snapshot(snapshot_record.image_path, snapshot_record.crop_path)
        raw_text = extraction.get("raw_text", "")

        self.context.logger.info(
            "SNAPSHOT_OCR "
            f"snapshot_id={snapshot_record.snapshot_id} "
            f"status={extraction.get('status')} "
            f"raw_text_len={len(raw_text)} "
            f"metadata_confidence={extraction.get('metadata_confidence')}"
)
    
        final_candidate_id = snapshot_record.candidate_id
        if identity is not None and persistence is not None:
            decision = identity.match_candidate(
                extraction,
                persistence_service=persistence,
                vector_service=vector,
            )
            self.context.logger.info(
                "SNAPSHOT_IDENTITY "
                f"snapshot_id={snapshot_record.snapshot_id} "
                f"matched_on={decision.matched_on} "
                f"status={decision.identity_status} "
                f"candidate_id={decision.candidate_id} "
                f"needs_review={decision.needs_review}"
            )
            extraction["identity_decision"] = asdict(decision)
            extraction["email_hash"] = decision.debug.get("email_hash")
            extraction["name_company_hash"] = decision.debug.get("name_company_hash")
            final_candidate_id = decision.candidate_id or final_candidate_id
            if final_candidate_id is not None:
                persistence.upsert_candidate(
                    final_candidate_id,
                    extraction,
                    decision.identity_status,
                )
            if snapshot_record.candidate_id and final_candidate_id and snapshot_record.candidate_id != final_candidate_id:
                persistence.reassign_candidate(
                    old_candidate_id=snapshot_record.candidate_id,
                    new_candidate_id=final_candidate_id,
                )
                session_runtime = self.context.runtime.get("session", {})
                if session_runtime.get("candidate_id") == snapshot_record.candidate_id:
                    session_runtime["candidate_id"] = final_candidate_id
                    session_runtime["identity_status"] = decision.identity_status
                    session_runtime["card_identity_state"] = decision.identity_status

        if persistence is not None:
            persistence.update_snapshot_extraction(
                snapshot_id=snapshot_record.snapshot_id,
                raw_text=raw_text,
                extraction_json=extraction,
            )

        if vector is not None and final_candidate_id:
            vector.index_text(
                final_candidate_id,
                raw_text,
                payload={"snapshot_id": snapshot_record.snapshot_id},
                snapshot_id=snapshot_record.snapshot_id,
            )
            if snapshot_record.crop_path:
                vector.index_image(
                    final_candidate_id,
                    snapshot_record.crop_path,
                    payload={"snapshot_id": snapshot_record.snapshot_id},
                    snapshot_id=snapshot_record.snapshot_id,
                )

    def get_status(self):
        return {"status": "READY"}