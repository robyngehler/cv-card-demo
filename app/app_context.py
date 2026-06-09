from dataclasses import dataclass, field
from typing import Any, Dict


_UNSET = object()


def _build_session_state() -> Dict[str, Any]:
    return {
        "session_id": None,
        "candidate_id": None,
        "identity_status": "UNKNOWN",
        "card_identity_state": "UNKNOWN",
        "question_index": 0,
        "current_question_id": None,
        "current_score": None,
        "last_motion_time": None,
        "first_motion_time": None,
        "stable_since": None,
        "countdown_started_at": None,
        "phase": "WAIT_FOR_MOVEMENT",
        "answers": [],
        "completed": False,
        "last_score": None,
        "question_start_score": None,
        "latest_motion": 0.0,
        "acc_question_motion": 0.0,
    }


def _build_runtime_state() -> Dict[str, Any]:
    return {
        "boot_id": None,
        "start_time": None,
        "current_state": None,
        "ui_mode": "RUN",
        "substate": None,
        "last_ui_snapshot_ts": 0.0,
        "last_ui_snapshot": None,
        "degraded_flags": {},
        "last_error": None,
        "last_frame": None,
        "last_detection": None,
        "last_candidate": None,
        "last_candidate_frame": None,
        "last_card_measurement": None,
        "last_hand_measurement": None,
        "last_fusion_measurement": None,
        "last_identity_precheck": None,
        "tracking": {
            "source": "idle",
            "fusion_state": "NO_TARGET",
            "last_visible_score": None,
            "countdown_visible": False,
        },
        "questionnaire": {
            "active": False,
            "pending_snapshot": False,
            "last_completed_question_id": None,
        },
        "session": _build_session_state(),
        "snapshot": {
            "pending": False,
            "last_snapshot_id": None,
            "last_snapshot_path": None,
        },
        "debug": {},
    }


@dataclass
class AppContext:
    config: Dict[str, Any]
    logger: Any = None
    state_machine: Any = None
    services: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=_build_runtime_state)

    def register_service(self, name: str, service: Any) -> Any:
        self.services[name] = service
        return service

    def get_service(self, service_name_or_type: Any, default: Any = _UNSET) -> Any:
        if isinstance(service_name_or_type, str):
            service = self.services.get(service_name_or_type, _UNSET)
        else:
            service = _UNSET
            for candidate in self.services.values():
                if isinstance(candidate, service_name_or_type):
                    service = candidate
                    break

        if service is _UNSET:
            if default is _UNSET:
                raise KeyError(f"Service not found: {service_name_or_type}")
            return default
        return service

    def reset_session_runtime(self) -> None:
        self.runtime["session"] = _build_session_state()
        self.runtime.setdefault("questionnaire", {})["active"] = False
        self.runtime["questionnaire"]["pending_snapshot"] = False
        self.runtime["questionnaire"]["last_completed_question_id"] = None
        self.runtime.setdefault("tracking", {})["countdown_visible"] = False


def create_app_context(config, logger=None):
    return AppContext(config=config, logger=logger)
