from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional


def _field(value: Optional[str], confidence: float, source: str) -> Dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence if value else 0.0,
        "source": source if value else "missing",
    }


class RapidOcrService:
    """OCR backend using rapidocr-onnxruntime.

    ONNX Runtime inference sessions are thread-safe, but we still guard the
    engine with a lock because RapidOCR wraps three separate sessions (det,
    cls, rec) behind a single Python object — concurrent calls would interleave
    internal state.  A single lock is sufficient because OCR is called at most
    once per card scan (event-driven, not per-frame).
    """

    def __init__(self, context):
        self.context = context
        self.status: Dict[str, Any] = {"status": "NOT_INITIALIZED"}
        self._lock = threading.Lock()
        self._engine = None
        self._load_backend()

    def _load_backend(self) -> None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            self._engine = RapidOCR()
            self.status = {"status": "READY"}
        except Exception as exc:
            self._engine = None
            self.status = {"status": "UNAVAILABLE", "last_error": str(exc)}

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        if self._engine is None:
            return {"status": self.status.get("status", "UNAVAILABLE"), "raw_text": "", "lines": []}

        try:
            with self._lock:
                result, _elapse = self._engine(image_path)
        except Exception as exc:
            return {"status": "ERROR", "raw_text": "", "lines": [], "error": str(exc)}

        lines: List[str] = []
        for detection in result or []:
            if len(detection) >= 2:
                text = str(detection[1]).strip()
                if text:
                    lines.append(text)

        raw_text = "\n".join(lines)
        return {"status": "OK", "raw_text": raw_text, "lines": lines}

    def get_status(self) -> Dict[str, Any]:
        return {"status": self.status.get("status", "UNKNOWN"), "backend": "rapidocr"}


# Keep alias so imports that reference PaddleOcrService still resolve.
PaddleOcrService = RapidOcrService


class RegexFieldExtractor:
    EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.IGNORECASE)
    PHONE_RE = re.compile(r"(?:\+?\d[\d\s()./-]{6,}\d)")
    WEBSITE_RE = re.compile(r"(?:https?://)?(?:www\.)?[A-Z0-9.-]+\.[A-Z]{2,}(?:/[\w./?%&=-]*)?", re.IGNORECASE)

    def extract(self, raw_text: str) -> Dict[str, Any]:
        normalized_text = raw_text or ""
        emails = self.EMAIL_RE.findall(normalized_text)
        phones = self.PHONE_RE.findall(normalized_text)
        website_source = normalized_text
        for email in emails:
            website_source = website_source.replace(email, " ")
        websites = [
            candidate
            for candidate in self.WEBSITE_RE.findall(website_source)
            if not any(candidate in email for email in emails)
        ]
        return {
            "email": _field(emails[0] if emails else None, 0.99, "regex"),
            "phone": _field(phones[0] if phones else None, 0.95, "regex"),
            "website": _field(websites[0] if websites else None, 0.9, "regex"),
        }


class HeuristicFieldExtractor:
    ROLE_KEYWORDS = (
        "engineer", "manager", "lead", "researcher", "professor",
        "ceo", "cto", "director", "consultant",
    )

    def extract(self, lines: List[str], deterministic_fields: Dict[str, Any]) -> Dict[str, Any]:
        filtered_lines = [line.strip() for line in lines if line.strip()]
        deterministic_values = {
            value.get("value")
            for value in deterministic_fields.values()
            if isinstance(value, dict) and value.get("value")
        }
        semantic_lines = [line for line in filtered_lines if line not in deterministic_values]

        role = next(
            (line for line in semantic_lines if any(kw in line.lower() for kw in self.ROLE_KEYWORDS)),
            None,
        )
        company = self._select_company(semantic_lines, role)
        name = None
        for line in semantic_lines:
            words = [w for w in re.split(r"\s+", line) if w]
            if (
                len(words) in {2, 3}
                and not any(c.isdigit() for c in line)
                and not any(kw in line.lower() for kw in self.ROLE_KEYWORDS)
                and not any(t.isupper() and len(t) > 3 for t in words)
            ):
                name = line
                break

        return {
            "name": _field(name, 0.65, "heuristic"),
            "company": _field(company, 0.55 if role is None else 0.62, "heuristic"),
            "role": _field(role, 0.55, "heuristic"),
        }

    def _select_company(self, semantic_lines: List[str], role: Optional[str]) -> Optional[str]:
        if not semantic_lines:
            return None
        if role and role in semantic_lines:
            idx = semantic_lines.index(role)
            neighbors = []
            if idx > 0:
                neighbors.append(semantic_lines[idx - 1])
            if idx + 1 < len(semantic_lines):
                neighbors.append(semantic_lines[idx + 1])
            for n in neighbors:
                if n != role:
                    return n
        ranked = sorted(semantic_lines, key=lambda l: (-len(l), l.lower()))
        for candidate in ranked:
            if candidate != role:
                return candidate
        return None


class StructuredFieldParser:
    def __init__(self, context):
        self.context = context
        self.enabled = bool(context.config.get("ocr", {}).get("llm", {}).get("enabled", False))

    def parse(
        self,
        *,
        raw_text: str,
        deterministic_fields: Dict[str, Any],
        heuristic_fields: Dict[str, Any],
    ) -> Dict[str, Any]:
        combined = {
            "name": heuristic_fields.get("name", _field(None, 0.0, "missing")),
            "company": heuristic_fields.get("company", _field(None, 0.0, "missing")),
            "role": heuristic_fields.get("role", _field(None, 0.0, "missing")),
            "email": deterministic_fields.get("email", _field(None, 0.0, "missing")),
            "phone": deterministic_fields.get("phone", _field(None, 0.0, "missing")),
            "website": deterministic_fields.get("website", _field(None, 0.0, "missing")),
        }
        combined["needs_review"] = self._needs_review(combined)
        combined["raw_text"] = raw_text
        combined["parser"] = {
            "enabled": self.enabled,
            "mode": "SCHEMA_ONLY" if not self.enabled else "HEURISTIC_STRUCTURING",
        }
        return combined

    def _needs_review(self, combined: Dict[str, Any]) -> bool:
        high_confidence_email = combined.get("email", {}).get("confidence", 0.0) >= 0.99
        has_name = bool(combined.get("name", {}).get("value"))
        has_company = bool(combined.get("company", {}).get("value"))
        return not (high_confidence_email or (has_name and has_company))


class BusinessCardMetadataPipeline:
    service_name = "ocr"

    def __init__(self, context):
        self.context = context
        self.ocr = RapidOcrService(context)
        self.regex = RegexFieldExtractor()
        self.heuristics = HeuristicFieldExtractor()
        self.parser = StructuredFieldParser(context)

    def process_snapshot(self, image_path: str, crop_path: Optional[str] = None) -> Dict[str, Any]:
        source_path = crop_path or image_path
        ocr_result = self.ocr.extract_text(source_path)
        raw_text = ocr_result.get("raw_text", "")
        lines = ocr_result.get("lines", [])
        deterministic_fields = self.regex.extract(raw_text)
        heuristic_fields = self.heuristics.extract(lines, deterministic_fields)
        parsed = self.parser.parse(
            raw_text=raw_text,
            deterministic_fields=deterministic_fields,
            heuristic_fields=heuristic_fields,
        )
        metadata_confidence = max(
            parsed.get("email", {}).get("confidence", 0.0),
            parsed.get("name", {}).get("confidence", 0.0),
            parsed.get("company", {}).get("confidence", 0.0),
        )
        parsed["metadata_confidence"] = metadata_confidence
        return {
            "status": ocr_result.get("status", "UNKNOWN"),
            "raw_text": raw_text,
            "lines": lines,
            **parsed,
        }

    def get_status(self) -> Dict[str, Any]:
        return self.ocr.get_status()

    def shutdown(self) -> None:
        pass  # no subprocess to clean up


LlmBusinessCardParser = StructuredFieldParser
