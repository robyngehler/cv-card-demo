from __future__ import annotations

import multiprocessing as mp
import os
import queue as stdlib_queue
import re
import threading
import time
from typing import Any, Dict, List, Optional


def _field(value: Optional[str], confidence: float, source: str) -> Dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence if value else 0.0,
        "source": source if value else "missing",
    }


def _ocr_worker_main(request_q: Any, response_q: Any) -> None:
    """Entry point for the dedicated OCR subprocess.

    Paddle predictors are NOT thread-safe and their C++ runtime can segfault
    when shared with other ML frameworks (MediaPipe/TFLite XNNPACK) in the same
    process. Running OCR in a dedicated subprocess completely isolates Paddle: a
    crash only kills this worker — the parent process survives and restarts it.

    GPU path: change device='cpu' to device='gpu:0' once paddlepaddle-gpu is
    available for aarch64/JetPack. YOLO and Paddle can share the Jetson GPU
    because the CUDA driver serializes device access across processes.
    """
    # Must be set before importing paddle — disables Intel MKL-DNN on ARM
    # (MKL-DNN assumes x86 ISA features and causes null-pointer crashes on ARM64)
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("FLAGS_call_stack_level", "2")

    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            lang="en",
            enable_mkldnn=False,
            cpu_threads=4,
            device="cpu",
            # Doc-orientation and unwarping are not needed for already-cropped
            # card images viewed top-down; skip them to save two model loads.
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
        )
        response_q.put({"type": "ready"})
    except Exception as exc:
        response_q.put({"type": "init_error", "error": str(exc)})
        return

    while True:
        try:
            req = request_q.get(timeout=10.0)
        except stdlib_queue.Empty:
            continue
        if req.get("cmd") == "shutdown":
            break
        req_id = req["id"]
        try:
            results = ocr.ocr(req["image_path"])
            # PaddleOCR 3.x returns OCRResult objects containing weak-method
            # references that cannot be pickled. Extract plain strings here.
            lines: list[str] = []
            for page in results or []:
                if isinstance(page, dict) and "rec_texts" in page:
                    for text, _ in zip(
                        page.get("rec_texts") or [],
                        page.get("rec_scores") or [],
                    ):
                        t = str(text).strip() if text else ""
                        if t:
                            lines.append(t)
                else:
                    for detection in page or []:
                        if len(detection) >= 2:
                            t = str(detection[1][0]).strip()
                            if t:
                                lines.append(t)
            response_q.put({"id": req_id, "lines": lines, "error": None})
        except Exception as exc:
            response_q.put({"id": req_id, "lines": [], "error": str(exc)})


class PaddleOcrService:
    def __init__(self, context):
        self.context = context
        self.status: Dict[str, Any] = {"status": "NOT_INITIALIZED"}
        # Serialize subprocess requests so only one OCR call is in-flight at a
        # time. The subprocess is single-threaded, so no request-ID matching
        # is needed — responses always correspond to the pending request.
        self._lock = threading.Lock()
        self._worker: Optional[mp.Process] = None
        self._request_q: Optional[Any] = None
        self._response_q: Optional[Any] = None
        self._req_counter = 0
        self._start_worker(init_timeout=120.0)

    def _start_worker(self, init_timeout: float = 30.0) -> None:
        if self._worker and self._worker.is_alive():
            try:
                self._worker.terminate()
                self._worker.join(timeout=3)
            except Exception:
                pass

        # spawn = fresh Python interpreter — no inherited CUDA context, no
        # inherited MediaPipe/TFLite state, no NEON-library conflicts.
        ctx = mp.get_context("spawn")
        self._request_q = ctx.Queue()
        self._response_q = ctx.Queue()
        self._worker = ctx.Process(
            target=_ocr_worker_main,
            args=(self._request_q, self._response_q),
            daemon=True,
            name="ocr-worker",
        )
        self._worker.start()
        try:
            msg = self._response_q.get(timeout=init_timeout)
        except stdlib_queue.Empty:
            self.status = {"status": "UNAVAILABLE", "last_error": "worker init timeout"}
            return
        if msg.get("type") == "init_error":
            self.status = {"status": "UNAVAILABLE", "last_error": msg.get("error", "init failed")}
        else:
            self.status = {"status": "READY"}

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        if self.status.get("status") != "READY":
            return {"status": self.status.get("status", "UNAVAILABLE"), "raw_text": "", "lines": []}

        with self._lock:
            if not self._worker.is_alive():
                self._start_worker(init_timeout=30.0)
                if self.status.get("status") != "READY":
                    return {"status": "UNAVAILABLE", "raw_text": "", "lines": []}

            req_id = self._req_counter
            self._req_counter += 1
            self._request_q.put({"id": req_id, "image_path": image_path})

            # Poll with worker-alive check so we don't wait the full 30s if
            # the subprocess segfaults during inference.
            deadline = time.monotonic() + 30.0
            response = None
            while time.monotonic() < deadline:
                if not self._worker.is_alive():
                    break
                try:
                    response = self._response_q.get(timeout=1.0)
                    break
                except stdlib_queue.Empty:
                    continue

        if response is None:
            return {"status": "ERROR", "raw_text": "", "lines": [], "error": "worker crash or timeout"}
        if response.get("error"):
            return {"status": "ERROR", "raw_text": "", "lines": [], "error": response["error"]}
        lines = response.get("lines") or []
        return {"status": "OK", "raw_text": "\n".join(lines), "lines": lines}

    def shutdown(self) -> None:
        if self._worker and self._worker.is_alive():
            try:
                self._request_q.put({"cmd": "shutdown"})
                self._worker.join(timeout=5)
            finally:
                if self._worker.is_alive():
                    self._worker.terminate()


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
        "engineer",
        "manager",
        "lead",
        "researcher",
        "professor",
        "ceo",
        "cto",
        "director",
        "consultant",
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
            (line for line in semantic_lines if any(keyword in line.lower() for keyword in self.ROLE_KEYWORDS)),
            None,
        )
        company = self._select_company(semantic_lines, role)
        name = None
        for line in semantic_lines:
            words = [word for word in re.split(r"\s+", line) if word]
            if (
                len(words) in {2, 3}
                and not any(char.isdigit() for char in line)
                and not any(keyword in line.lower() for keyword in self.ROLE_KEYWORDS)
                and not any(token.isupper() and len(token) > 3 for token in words)
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
            role_index = semantic_lines.index(role)
            neighbors = []
            if role_index > 0:
                neighbors.append(semantic_lines[role_index - 1])
            if role_index + 1 < len(semantic_lines):
                neighbors.append(semantic_lines[role_index + 1])
            for neighbor in neighbors:
                if neighbor != role:
                    return neighbor
        ranked = sorted(semantic_lines, key=lambda line: (-len(line), line.lower()))
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
        self.ocr = PaddleOcrService(context)
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
        return {
            "status": self.ocr.status.get("status", "UNKNOWN"),
            "backend": "paddleocr",
        }

    def shutdown(self) -> None:
        self.ocr.shutdown()


LlmBusinessCardParser = StructuredFieldParser
