from __future__ import annotations

from typing import Any, Dict, Optional

from app.cv.fusion_tracker import CardHandFusionTracker as FusionTrackerEngine
from app.cv.fusion_tracker import FusionMeasurement


class CardHandFusionService:
    service_name = "fusion_tracker"

    def __init__(self, context):
        self.context = context
        fusion_config = context.config.get("tracking", {}).get("fusion", {})
        card_to_hand = fusion_config.get("card_to_hand", {})
        hand_to_card = fusion_config.get("hand_to_card", {})
        lost_hold = fusion_config.get("lost_hold", {})
        smoothing = fusion_config.get("smoothing", {})

        self.engine = FusionTrackerEngine(
            min_hand_stable_frames=int(card_to_hand.get("min_hand_stable_frames", 2)),
            max_initial_offset_norm=float(card_to_hand.get("max_initial_offset_norm", 0.35)),
            min_card_stable_frames=int(hand_to_card.get("min_card_stable_frames", 3)),
            reacquire_tolerance_norm=float(hand_to_card.get("reacquire_tolerance_norm", 0.04)),
            ambiguous_tolerance_norm=float(hand_to_card.get("ambiguous_tolerance_norm", 0.12)),
            allow_displayed_score_drift=bool(hand_to_card.get("allow_displayed_score_drift", False)),
            lost_hold_max_duration_s=float(lost_hold.get("max_duration_s", 0.5)),
            score_ema_alpha=float(smoothing.get("score_ema_alpha", 0.35)),
            hand_to_card_validate_timeout_s=float(hand_to_card.get("validate_timeout_s", 0.25)),
        )

    def reset(self) -> None:
        self.engine.reset()

    def update(
        self,
        card_measurement,
        hand_measurement,
        *,
        now: Optional[float] = None,
        **_: Any,
    ) -> FusionMeasurement:
        return self.engine.update(card_measurement, hand_measurement, now=now)

    def get_status(self) -> Dict[str, Any]:
        return self.engine.get_status()


CardHandFusionTracker = CardHandFusionService