from __future__ import annotations

import logging
import multiprocessing as mp
import os
import queue as stdlib_queue
import re
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("cv-card-demo")


def _field(value: Optional[str], confidence: float, source: str) -> Dict[str, Any]:
    return {
        "value": value,
        "confidence": confidence if value else 0.0,
        "source": source if value else "missing",
    }


# --- OCR worker subprocess (proposal Fix 3 + Fix 4) ------------------------

def _ocr_worker_main(request_q: Any, response_q: Any) -> None:
    """Entry point for the dedicated OCR subprocess.

    Paddle predictors are NOT thread-safe and their C++ runtime can segfault
    on aarch64 (Cortex-A78) — especially when several native ML runtimes share
    one process (Paddle/OpenCV/MediaPipe each bring their own OpenMP/BLAS).
    Running OCR in a dedicated ``spawn`` subprocess isolates Paddle completely:
    a crash only kills this worker; the parent restarts it with backoff.

    GPU path: change device='cpu' to device='gpu:0' once paddlepaddle-gpu is
    available for aarch64/JetPack. YOLO and Paddle can share the Jetson GPU —
    the CUDA driver serializes device access across processes.
    """
    # Fix 4 — thread pinning must be set BEFORE paddle/numpy import. Competing
    # OpenMP/OpenBLAS/MKL runtimes on Cortex-A78 are a documented crash source.
    os.environ.setdefault("OMP_NUM_THREADS", "2")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    # MKL-DNN assumes x86 ISA features → null-pointer crashes on ARM64.
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("FLAGS_call_stack_level", "2")

    try:
        from paddleocr import PaddleOCR

        # Fix 4 — lightweight mobile det+rec models. Rectified card crops do not
        # need the medium-tier defaults; mobile models cut init time and memory.
        ocr = PaddleOCR(
            lang="en",
            device="cpu",
            enable_mkldnn=False,
            cpu_threads=2,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            text_detection_model_name="PP-OCRv5_mobile_det",
            text_recognition_model_name="en_PP-OCRv5_mobile_rec",
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
            # PaddleOCR 3.x returns OCRResult objects holding weak-method refs
            # that cannot be pickled — extract plain strings before queuing.
            lines: List[str] = []
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
    """Supervises the OCR subprocess with a bounded restart policy (Fix 3).

    Lifecycle:
      OCR request -> enqueue -> wait with per-job timeout
        on timeout/crash -> restart worker with backoff (1s, 2s, 5s, ...)
        after MAX_CRASHES within CRASH_WINDOW_S -> disable OCR temporarily;
          the snapshot pipeline continues without OCR and re-tries after the
          cooldown.
    """

    MAX_CRASHES = 4
    CRASH_WINDOW_S = 120.0
    DISABLE_COOLDOWN_S = 300.0
    BACKOFF_STEPS = (1.0, 2.0, 5.0, 10.0)
    JOB_TIMEOUT_S = 30.0

    def __init__(self, context):
        self.context = context
        self.status: Dict[str, Any] = {"status": "NOT_INITIALIZED"}
        # Serialize subprocess requests — the worker is single-threaded, so a
        # response always corresponds to the one pending request.
        self._lock = threading.Lock()
        self._worker: Optional[mp.Process] = None
        self._request_q: Optional[Any] = None
        self._response_q: Optional[Any] = None
        self._req_counter = 0
        # Crash bookkeeping for the temporary-disable policy.
        self._crash_times: List[float] = []
        self._disabled_until = 0.0
        self._start_worker(init_timeout=120.0)

    def _start_worker(self, init_timeout: float = 30.0) -> None:
        if self._worker and self._worker.is_alive():
            try:
                self._worker.terminate()
                self._worker.join(timeout=3)
            except Exception:
                pass

        # spawn = fresh interpreter: no inherited CUDA context, no MediaPipe/
        # TFLite state, no half-initialized OpenMP. Never fork for ML runtimes.
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

    def _record_crash_and_maybe_disable(self) -> None:
        """Track crashes in a sliding window; disable OCR if too frequent."""
        now = time.monotonic()
        self._crash_times = [t for t in self._crash_times if now - t < self.CRASH_WINDOW_S]
        self._crash_times.append(now)
        backoff = self.BACKOFF_STEPS[min(len(self._crash_times) - 1, len(self.BACKOFF_STEPS) - 1)]
        if len(self._crash_times) >= self.MAX_CRASHES:
            self._disabled_until = now + self.DISABLE_COOLDOWN_S
            self.status = {"status": "DISABLED", "last_error": "too many OCR crashes"}
            logger.warning(
                "OCR disabled for %.0fs after %d crashes in %.0fs",
                self.DISABLE_COOLDOWN_S, len(self._crash_times), self.CRASH_WINDOW_S,
            )
            return
        logger.warning("OCR worker crashed (%d in window); restarting after %.0fs backoff",
                       len(self._crash_times), backoff)
        time.sleep(backoff)
        self._start_worker(init_timeout=30.0)

    def extract_text(self, image_path: str) -> Dict[str, Any]:
        now = time.monotonic()
        if self._disabled_until and now < self._disabled_until:
            return {"status": "DISABLED", "raw_text": "", "lines": []}
        if self._disabled_until and now >= self._disabled_until:
            # Cooldown elapsed — clear the crash window and try a fresh worker.
            self._disabled_until = 0.0
            self._crash_times.clear()
            with self._lock:
                self._start_worker(init_timeout=30.0)

        if self.status.get("status") != "READY":
            return {"status": self.status.get("status", "UNAVAILABLE"), "raw_text": "", "lines": []}

        with self._lock:
            if not self._worker.is_alive():
                self._record_crash_and_maybe_disable()
                if self.status.get("status") != "READY":
                    return {"status": self.status.get("status", "UNAVAILABLE"), "raw_text": "", "lines": []}

            req_id = self._req_counter
            self._req_counter += 1
            self._request_q.put({"id": req_id, "image_path": image_path})

            # Poll with worker-alive check so a mid-inference segfault is noticed
            # immediately instead of waiting the whole job timeout.
            deadline = time.monotonic() + self.JOB_TIMEOUT_S
            response = None
            crashed = False
            while time.monotonic() < deadline:
                if not self._worker.is_alive():
                    crashed = True
                    break
                try:
                    response = self._response_q.get(timeout=1.0)
                    break
                except stdlib_queue.Empty:
                    continue

            if crashed or response is None:
                self._record_crash_and_maybe_disable()
                return {"status": "ERROR", "raw_text": "", "lines": [], "error": "worker crash or timeout"}

        if response.get("error"):
            return {"status": "ERROR", "raw_text": "", "lines": [], "error": response["error"]}
        lines = response.get("lines") or []
        return {"status": "OK", "raw_text": "\n".join(lines), "lines": lines}

    def get_status(self) -> Dict[str, Any]:
        return {"status": self.status.get("status", "UNKNOWN"), "backend": "paddleocr"}

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
        "engineer", "manager", "lead", "researcher", "professor",
        "ceo", "cto", "cfo", "coo", "director", "consultant",
        # business-card titles that are NOT names — common false positives
        "officer", "chief", "head", "founder", "president", "owner",
        "vice", "partner", "specialist", "coordinator", "scientist",
        "architect", "analyst",
    )

    # Markers that indicate a company / address / contact line rather than a
    # person's name. Used so all-caps person names (e.g. "ROBERT BRÜCKNER")
    # are still accepted while company headers are skipped.
    COMPANY_MARKERS = (
        "gmbh", "inc", "ltd", "llc", "corp", "co.", "group", "invest",
        "trade", "technologies", "solutions", "systems", "university",
        "institute", "&", "straße", "strasse", "str.",
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
            low = line.lower()
            words = [w for w in re.split(r"\s+", line) if w]
            if (
                len(words) in {2, 3}
                and not any(c.isdigit() for c in line)
                and not any(kw in low for kw in self.ROLE_KEYWORDS)
                and not any(m in low for m in self.COMPANY_MARKERS)
                # skip contact lines that slipped past the regex extractor
                and "@" not in line
                and "www" not in low
                and ".com" not in low
                and "http" not in low
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
        return self.ocr.get_status()

    def shutdown(self) -> None:
        self.ocr.shutdown()


LlmBusinessCardParser = StructuredFieldParser
