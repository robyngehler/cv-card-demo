from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass
class CameraPropertySpec:
    key: str
    cv2_prop: str
    default_min: float
    default_max: float
    default_step: float
    supports_auto: bool = False
    auto_prop: str | None = None


class CameraControlService:
    service_name = "camera_control"

    PROPERTY_SPECS = (
        CameraPropertySpec("exposure", "CAP_PROP_EXPOSURE", -13.0, 0.0, 1.0, supports_auto=True, auto_prop="CAP_PROP_AUTO_EXPOSURE"),
        CameraPropertySpec("focus", "CAP_PROP_FOCUS", 0.0, 255.0, 1.0, supports_auto=True, auto_prop="CAP_PROP_AUTOFOCUS"),
        CameraPropertySpec("zoom", "CAP_PROP_ZOOM", 0.0, 500.0, 1.0),
        CameraPropertySpec("sharpness", "CAP_PROP_SHARPNESS", 0.0, 255.0, 1.0),
        CameraPropertySpec("brightness", "CAP_PROP_BRIGHTNESS", 0.0, 255.0, 1.0),
        CameraPropertySpec("contrast", "CAP_PROP_CONTRAST", 0.0, 255.0, 1.0),
        CameraPropertySpec("saturation", "CAP_PROP_SATURATION", 0.0, 255.0, 1.0),
        CameraPropertySpec("gain", "CAP_PROP_GAIN", 0.0, 255.0, 1.0),
        CameraPropertySpec("white_balance", "CAP_PROP_WB_TEMPERATURE", 2800.0, 6500.0, 100.0, supports_auto=True, auto_prop="CAP_PROP_AUTO_WB"),
    )

    AUTO_KEY_MAP = {
        "auto_exposure": "exposure",
        "auto_focus": "focus",
        "auto_white_balance": "white_balance",
    }

    def __init__(self, context):
        self.context = context
        self.last_error: str | None = None
        # Optional per-control slider bounds from config (camera.controls.<key>).
        # The V4L2 driver advertises a far wider exposure range than is usable,
        # so the booth operator can cap it here for a meaningful slider.
        self.control_overrides = (context.config.get("camera", {}) or {}).get("controls", {}) or {}

    def get_status(self) -> Dict[str, Any]:
        camera = self.context.get_service("camera", default=None)
        if camera is None:
            return {"status": "NOT_INITIALIZED", "last_error": self.last_error}
        if not getattr(camera, "opened", False):
            return {"status": "CAMERA_CLOSED", "last_error": self.last_error}
        return {"status": "READY", "last_error": self.last_error}

    def get_capabilities(self) -> Dict[str, Any]:
        camera, cv2 = self._resolve_camera_and_cv2()
        if camera is None or cv2 is None:
            return {
                "status": "NOT_READY",
                "settings": self._build_unavailable_settings(),
                "last_error": self.last_error,
            }

        settings = {}
        backend = self._backend_name(camera)
        for spec in self.PROPERTY_SPECS:
            prop_id = getattr(cv2, spec.cv2_prop, None)
            auto_prop_id = getattr(cv2, spec.auto_prop, None) if spec.auto_prop else None
            supported, value = self._read_property(camera, prop_id)
            min_value, max_value = self._effective_range(spec, value, backend)

            auto_supported = False
            auto_value = None
            if spec.supports_auto and auto_prop_id is not None:
                auto_supported, auto_raw = self._read_property(camera, auto_prop_id)
                auto_value = self._normalize_auto_value(spec.key, auto_raw) if auto_supported else None

            settings[spec.key] = {
                "value": value,
                "min": min_value,
                "max": max_value,
                "step": spec.default_step,
                "supported": supported,
                "auto": auto_value if auto_supported else False,
                "auto_supported": auto_supported,
            }

        return {
            "status": "OK",
            "device_index": getattr(camera, "device_index", None),
            "backend": self._backend_name(camera),
            "settings": settings,
            "last_error": self.last_error,
        }

    def get_settings(self) -> Dict[str, Any]:
        payload = self.get_capabilities()
        return payload

    def apply_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        camera, cv2 = self._resolve_camera_and_cv2()
        if camera is None or cv2 is None:
            return {
                "status": "NOT_READY",
                "applied": {},
                "rejected": {key: "camera_not_ready" for key in updates.keys()},
                "last_error": self.last_error,
            }

        applied: Dict[str, bool] = {}
        rejected: Dict[str, str] = {}
        backend = self._backend_name(camera)

        # Properties the caller explicitly wants left in auto mode this request.
        # We must not force those back to manual when their value is also sent.
        explicit_auto_on = {
            self.AUTO_KEY_MAP[k]
            for k, v in (updates or {}).items()
            if k in self.AUTO_KEY_MAP and bool(v)
        }

        for key, value in (updates or {}).items():
            if key in self.AUTO_KEY_MAP:
                prop_key = self.AUTO_KEY_MAP[key]
                spec = self._spec_by_key(prop_key)
                if spec is None or spec.auto_prop is None:
                    rejected[key] = "unsupported"
                    continue
                auto_prop_id = getattr(cv2, spec.auto_prop, None)
                if auto_prop_id is None:
                    rejected[key] = "unsupported"
                    continue

                # Try the primary encoding first, then fallback values for cameras with quirky drivers
                primary_value = self._encode_auto_value(prop_key, bool(value), backend=backend)
                fallback_values = self._get_auto_value_fallbacks(prop_key, bool(value), backend=backend)

                ok = self._set_property(camera, auto_prop_id, primary_value)
                if not ok and fallback_values:
                    for fb_value in fallback_values:
                        ok = self._set_property(camera, auto_prop_id, fb_value)
                        if ok:
                            break

                applied[key] = bool(ok)
                if not ok:
                    rejected[key] = "set_failed"
                continue

            spec = self._spec_by_key(key)
            if spec is None:
                rejected[key] = "unknown_setting"
                continue

            prop_id = getattr(cv2, spec.cv2_prop, None)
            if prop_id is None:
                rejected[key] = "unsupported"
                continue

            try:
                numeric = float(value)
            except Exception:
                rejected[key] = "invalid_value"
                continue

            # A manual value only takes effect when the matching auto-mode is OFF.
            # V4L2 silently ignores CAP_PROP_EXPOSURE while auto-exposure is active,
            # so switch the property to manual before writing the value (unless the
            # caller explicitly asked to keep auto on in the same request).
            if spec.supports_auto and spec.auto_prop and key not in explicit_auto_on:
                self._force_manual_mode(camera, cv2, spec, backend)

            supported, current_value = self._read_property(camera, prop_id)
            min_value, max_value = self._effective_range(spec, current_value if supported else numeric, backend)
            clamped = min(max_value, max(min_value, numeric))

            ok = self._set_property(camera, prop_id, clamped)
            if not ok:
                applied[key] = False
                rejected[key] = "set_failed"
                continue
            # Trust capture.set() returning True — V4L2 and other drivers often
            # quantise values silently, so a readback tolerance check causes
            # false readback_mismatch failures and makes the UI slider jump back.
            applied[key] = True

        status = "OK" if not rejected else "PARTIAL"
        refreshed = self.get_capabilities()
        applied_readback = {}
        refreshed_settings = refreshed.get("settings", {})
        for key in applied.keys():
            # Only include keys that were actually applied successfully.
            # Including failed keys would cause the frontend to overwrite its
            # draft value with the camera's current value, making sliders jump back.
            if applied.get(key) and key in refreshed_settings:
                applied_readback[key] = refreshed_settings[key].get("value")

        return {
            "status": status,
            "applied": applied,
            "applied_values": applied_readback,
            "rejected": rejected,
            "settings": refreshed_settings,
            "last_error": self.last_error,
        }

    def restart_camera(self) -> Dict[str, Any]:
        camera = self.context.get_service("camera", default=None)
        if camera is None:
            self.last_error = "camera_service_unavailable"
            return {"status": "NOT_READY", "last_error": self.last_error}

        try:
            camera.close()
            camera.open()
            self.last_error = None
            return {
                "status": "OK",
                "device_index": getattr(camera, "device_index", None),
                "frame_shape": getattr(camera, "frame_shape", None),
                "last_error": None,
            }
        except Exception as exc:
            self.last_error = str(exc)
            return {"status": "ERROR", "last_error": self.last_error}

    def _resolve_camera_and_cv2(self) -> Tuple[Any, Any]:
        camera = self.context.get_service("camera", default=None)
        if camera is None or not getattr(camera, "opened", False):
            self.last_error = "camera_not_ready"
            return None, None

        capture = getattr(camera, "capture", None)
        if capture is None:
            self.last_error = "camera_capture_missing"
            return None, None

        try:
            import cv2
        except Exception:
            self.last_error = "opencv_unavailable"
            return None, None

        self.last_error = None
        return camera, cv2

    def _read_property(self, camera, prop_id) -> Tuple[bool, Any]:
        capture = getattr(camera, "capture", None)
        if capture is None or prop_id is None:
            return False, None
        try:
            value = capture.get(prop_id)
        except Exception:
            return False, None
        if value is None:
            return False, None
        if isinstance(value, float) and (value != value):
            return False, None
        return True, value

    def _set_property(self, camera, prop_id, value: float) -> bool:
        capture = getattr(camera, "capture", None)
        if capture is None or prop_id is None:
            return False
        try:
            result = capture.set(prop_id, float(value))
            return bool(result)
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def _force_manual_mode(self, camera, cv2, spec: CameraPropertySpec, backend: str) -> None:
        """Switch an auto-capable property (e.g. exposure) to manual so a written
        value is honoured. Tries the primary encoding, then driver fallbacks."""
        if not (spec.supports_auto and spec.auto_prop):
            return
        auto_prop_id = getattr(cv2, spec.auto_prop, None)
        if auto_prop_id is None:
            return
        primary = self._encode_auto_value(spec.key, False, backend=backend)
        if self._set_property(camera, auto_prop_id, primary):
            return
        for fallback in self._get_auto_value_fallbacks(spec.key, False, backend=backend):
            if self._set_property(camera, auto_prop_id, fallback):
                return

    def _spec_by_key(self, key: str) -> CameraPropertySpec | None:
        for spec in self.PROPERTY_SPECS:
            if spec.key == key:
                return spec
        return None

    def _build_unavailable_settings(self) -> Dict[str, Dict[str, Any]]:
        payload = {}
        for spec in self.PROPERTY_SPECS:
            payload[spec.key] = {
                "value": None,
                "min": spec.default_min,
                "max": spec.default_max,
                "step": spec.default_step,
                "supported": False,
                "auto": False,
                "auto_supported": False,
            }
        return payload

    def _effective_range(self, spec: CameraPropertySpec, current_value: Any, backend: str) -> Tuple[float, float]:
        min_value = float(spec.default_min)
        max_value = float(spec.default_max)

        numeric_value = None
        try:
            if current_value is not None:
                numeric_value = float(current_value)
        except Exception:
            numeric_value = None

        if numeric_value is not None and math.isfinite(numeric_value):
            if numeric_value < min_value:
                min_value = numeric_value
            if numeric_value > max_value:
                max_value = numeric_value

        # Logitech/V4L2 exposure often reports absolute units (>0) instead of log2 negatives.
        if spec.key == "exposure" and backend == "v4l2":
            if numeric_value is not None and numeric_value > 0:
                min_value = 1.0
                max_value = max(max_value, 4095.0)

        # Config overrides win over the driver-reported / dynamic range so the UI
        # slider stays within a usable band (e.g. exposure 0..255 instead of 4095).
        override = self.control_overrides.get(spec.key) or {}
        if "min" in override:
            min_value = float(override["min"])
        if "max" in override:
            max_value = float(override["max"])

        if min_value > max_value:
            min_value, max_value = max_value, min_value

        return min_value, max_value

    def _backend_name(self, camera) -> str:
        capture = getattr(camera, "capture", None)
        if capture is None:
            return "opencv"
        backend_name = getattr(capture, "getBackendName", None)
        if callable(backend_name):
            try:
                return str(backend_name()).lower()
            except Exception:
                return "opencv"
        return "opencv"

    def _normalize_auto_value(self, key: str, raw_value: float) -> bool:
        if key == "exposure":
            # V4L2 commonly reports 0.25 (manual) and 0.75 (auto).
            return bool(raw_value >= 0.5)
        return bool(raw_value >= 0.5)

    def _encode_auto_value(self, key: str, enabled: bool, backend: str = "opencv") -> float:
        if key == "exposure":
            if backend == "v4l2":
                return 0.75 if enabled else 0.25
            # CAP_PROP_AUTO_EXPOSURE is backend-specific; 1.0/0.0 is a common fallback.
            return 1.0 if enabled else 0.0
        return 1.0 if enabled else 0.0

    def _get_auto_value_fallbacks(self, key: str, enabled: bool, backend: str = "opencv") -> list:
        """
        Get fallback values for auto properties when primary encoding fails.
        Some camera drivers have quirky auto-property support.
        """
        if key == "exposure":
            if enabled:
                # Try common "auto" values when primary fails
                return [1.0, 0.75, 3.0, 0.5]
            else:
                # Try common "manual" values
                return [0.0, 0.25, 0.1]
        return [1.0, 0.0]
