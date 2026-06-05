from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class AppContext:
    config: Dict[str, Any]
    logger: Any = None
    state_machine: Any = None
    services: Dict[str, Any] = field(default_factory=dict)
    runtime: Dict[str, Any] = field(default_factory=lambda: {
        "boot_id": None,
        "start_time": None,
        "current_state": None,
        "substate": None,
        "degraded_flags": {},
    })


def create_app_context(config, logger=None):
    return AppContext(config=config, logger=logger)
