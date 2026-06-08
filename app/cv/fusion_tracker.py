from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from app.cv.classical_card_detector import CardPose, clamp

if TYPE_CHECKING:
    from app.services.hand_tracker_service import HandMeasurement


@dataclass
class FusionMeasurement:
    visible: bool
    score: Optional[float]
    rating: Optional[float]
    fusion_state: str
    source: str
    confidence: float
    x_normalized: Optional[float]
    timestamp: float
    debug: Dict[str, Any] = field(default_factory=dict)


class CardHandFusionTracker:
    def __init__(
        self,
        *,
        min_hand_stable_frames: int,
        max_initial_offset_norm: float,
        min_card_stable_frames: int,
        reacquire_tolerance_norm: float,
        ambiguous_tolerance_norm: float,
        allow_displayed_score_drift: bool,
        lost_hold_max_duration_s: float,
        score_ema_alpha: float,
        hand_to_card_validate_timeout_s: float,
    ):
        self.min_hand_stable_frames = max(1, int(min_hand_stable_frames))
        self.max_initial_offset_norm = max(0.0, float(max_initial_offset_norm))
        self.min_card_stable_frames = max(1, int(min_card_stable_frames))
        self.reacquire_tolerance_norm = max(0.0, float(reacquire_tolerance_norm))
        self.ambiguous_tolerance_norm = max(self.reacquire_tolerance_norm, float(ambiguous_tolerance_norm))
        self.allow_displayed_score_drift = bool(allow_displayed_score_drift)
        self.lost_hold_max_duration_s = max(0.0, float(lost_hold_max_duration_s))
        self.score_ema_alpha = clamp(float(score_ema_alpha), 0.0, 1.0)
        self.hand_to_card_validate_timeout_s = max(0.0, float(hand_to_card_validate_timeout_s))
        self.reset()

    def reset(self) -> None:
        self.fusion_state = "NO_TARGET"
        self.displayed_score: Optional[float] = None
        self.hand_to_score_offset = 0.0
        self.card_to_score_offset = 0.0
        self.card_anchor_acquired = False
        self.card_stable_frames = 0
        self.hand_stable_frames = 0
        self.last_visible_time: Optional[float] = None
        self.last_card_measurement: Optional[CardPose] = None
        self.last_hand_measurement: Optional[HandMeasurement] = None
        self.validate_started_at: Optional[float] = None
        self.lost_hold_anchor_score: Optional[float] = None
        self.lost_hold_entered_from: Optional[str] = None
        self.lost_hold_started_at: Optional[float] = None

    def update(
        self,
        card_measurement: Optional[CardPose],
        hand_measurement: Optional[HandMeasurement],
        *,
        now: Optional[float] = None,
    ) -> FusionMeasurement:
        timestamp = time.monotonic() if now is None else now
        card_valid = bool(
            card_measurement is not None
            and card_measurement.visible
            and card_measurement.is_business_card
            and card_measurement.x_normalized is not None
        )
        hand_valid = bool(
            hand_measurement is not None
            and hand_measurement.visible
            and hand_measurement.valid
            and hand_measurement.proxy_x_normalized is not None
        )

        if card_valid:
            self.last_card_measurement = card_measurement
            self.card_stable_frames += 1
            self.card_anchor_acquired = True
        else:
            self.card_stable_frames = 0

        if hand_valid:
            self.last_hand_measurement = hand_measurement
            self.hand_stable_frames += 1
        else:
            self.hand_stable_frames = 0

        if self.fusion_state == "NO_TARGET":
            return self._handle_no_target(card_measurement, hand_measurement, card_valid, hand_valid, timestamp)
        if self.fusion_state in {"CARD_OBSERVED", "CARD_REACQUIRED"}:
            return self._handle_card_primary(card_measurement, hand_measurement, card_valid, hand_valid, timestamp)
        if self.fusion_state in {"CARD_TO_HAND_PENDING", "CARD_TO_HAND_MERGE"}:
            return self._handle_card_to_hand(card_measurement, hand_measurement, card_valid, hand_valid, timestamp)
        if self.fusion_state == "HAND_PROXY_ACTIVE":
            return self._handle_hand_active(card_measurement, hand_measurement, card_valid, hand_valid, timestamp)
        if self.fusion_state in {"HAND_TO_CARD_VALIDATE", "HAND_TO_CARD_AMBIGUOUS"}:
            return self._handle_hand_to_card(card_measurement, hand_measurement, card_valid, hand_valid, timestamp)
        if self.fusion_state in {
            "LOST_HOLD",
            "LOST_TO_HAND_PENDING",
            "LOST_TO_HAND_MERGE",
            "LOST_REACQUIRE_AMBIGUOUS",
        }:
            return self._handle_lost_hold(card_measurement, hand_measurement, card_valid, hand_valid, timestamp)

        self.fusion_state = "NO_TARGET"
        return self._emit(
            visible=False,
            score=None,
            fusion_state="NO_TARGET",
            source="lost",
            confidence=0.0,
            timestamp=timestamp,
        )

    def get_status(self) -> Dict[str, Any]:
        return {
            "status": "READY",
            "fusion_state": self.fusion_state,
            "displayed_score": self.displayed_score,
            "lost_hold_anchor_score": self.lost_hold_anchor_score,
            "lost_hold_entered_from": self.lost_hold_entered_from,
        }

    def _handle_no_target(self, card_measurement, hand_measurement, card_valid, hand_valid, timestamp: float) -> FusionMeasurement:
        if card_valid:
            self.card_to_score_offset = 0.0
            self.validate_started_at = None
            self.fusion_state = "CARD_OBSERVED"
            return self._emit_card(card_measurement, fusion_state="CARD_OBSERVED", timestamp=timestamp)

        if hand_valid:
            return self._emit(
                visible=False,
                score=None,
                fusion_state="NO_TARGET",
                source="hand_without_card_anchor",
                confidence=float(hand_measurement.confidence),
                timestamp=timestamp,
                debug={"reason": "Hand tracking requires a confirmed business-card anchor"},
            )

        return self._emit(
            visible=False,
            score=None,
            fusion_state="NO_TARGET",
            source="lost",
            confidence=0.0,
            timestamp=timestamp,
        )

    def _handle_card_primary(self, card_measurement, hand_measurement, card_valid, hand_valid, timestamp: float) -> FusionMeasurement:
        if card_valid and hand_valid and self.hand_stable_frames >= self.min_hand_stable_frames:
            anchor_score = self.displayed_score if self.displayed_score is not None else self._card_score(card_measurement)
            hand_score = self._hand_score(hand_measurement)
            offset = anchor_score - hand_score
            if abs(offset) <= self.max_initial_offset_norm:
                self.hand_to_score_offset = offset
                self.fusion_state = "CARD_TO_HAND_MERGE"
                return self._emit(
                    visible=True,
                    score=anchor_score,
                    fusion_state="CARD_TO_HAND_MERGE",
                    source="hand_proxy_with_card_anchor",
                    confidence=float(hand_measurement.confidence),
                    timestamp=timestamp,
                    debug={"hand_to_score_offset": self.hand_to_score_offset},
                )

        if card_valid and hand_valid:
            self.fusion_state = "CARD_OBSERVED"
            return self._emit_card(card_measurement, fusion_state="CARD_OBSERVED", timestamp=timestamp)

        if card_valid:
            self.fusion_state = "CARD_OBSERVED"
            return self._emit_card(card_measurement, fusion_state="CARD_OBSERVED", timestamp=timestamp)

        if hand_valid:
            self.fusion_state = "CARD_TO_HAND_PENDING"
            return self._emit(
                visible=self.displayed_score is not None,
                score=self.displayed_score,
                fusion_state="CARD_TO_HAND_PENDING",
                source="last_confirmed_user_score",
                confidence=float(hand_measurement.confidence),
                timestamp=timestamp,
                debug={"hand_stable_frames": self.hand_stable_frames},
            )

        return self._enter_lost_hold(timestamp)

    def _handle_card_to_hand(self, card_measurement, hand_measurement, card_valid, hand_valid, timestamp: float) -> FusionMeasurement:
        anchor_score = self.displayed_score
        if hand_valid and anchor_score is not None:
            hand_score = self._hand_score(hand_measurement)
            if self.hand_stable_frames >= self.min_hand_stable_frames:
                if self.fusion_state == "CARD_TO_HAND_PENDING":
                    offset = anchor_score - hand_score
                    if abs(offset) <= self.max_initial_offset_norm:
                        self.hand_to_score_offset = offset
                        self.fusion_state = "CARD_TO_HAND_MERGE"
                        return self._emit(
                            visible=True,
                            score=anchor_score,
                            fusion_state="CARD_TO_HAND_MERGE",
                            source="hand_proxy_with_card_anchor",
                            confidence=float(hand_measurement.confidence),
                            timestamp=timestamp,
                            debug={"hand_to_score_offset": self.hand_to_score_offset},
                        )

                self.fusion_state = "HAND_PROXY_ACTIVE"
                return self._emit(
                    visible=True,
                    score=hand_score + self.hand_to_score_offset,
                    fusion_state="HAND_PROXY_ACTIVE",
                    source="hand_proxy_with_card_anchor",
                    confidence=float(hand_measurement.confidence),
                    timestamp=timestamp,
                    debug={"hand_to_score_offset": self.hand_to_score_offset},
                )

            self.fusion_state = "CARD_TO_HAND_PENDING"
            return self._emit(
                visible=True,
                score=anchor_score,
                fusion_state="CARD_TO_HAND_PENDING",
                source="last_confirmed_user_score",
                confidence=float(hand_measurement.confidence),
                timestamp=timestamp,
                debug={"hand_stable_frames": self.hand_stable_frames},
            )

        if card_valid:
            self.fusion_state = "CARD_OBSERVED"
            return self._emit_card(card_measurement, fusion_state="CARD_OBSERVED", timestamp=timestamp)

        return self._enter_lost_hold(timestamp)

    def _handle_hand_active(self, card_measurement, hand_measurement, card_valid, hand_valid, timestamp: float) -> FusionMeasurement:
        if hand_valid:
            self.validate_started_at = None
            self.fusion_state = "HAND_PROXY_ACTIVE"
            return self._emit(
                visible=True,
                score=self._hand_score(hand_measurement) + self.hand_to_score_offset,
                fusion_state="HAND_PROXY_ACTIVE",
                source="hand_proxy_with_card_anchor",
                confidence=float(hand_measurement.confidence),
                timestamp=timestamp,
                debug={
                    "hand_to_score_offset": self.hand_to_score_offset,
                    "card_visible": bool(card_valid),
                },
            )

        if card_valid:
            return self._evaluate_hand_to_card(card_measurement, timestamp)

        return self._enter_lost_hold(timestamp)

    def _handle_hand_to_card(self, card_measurement, hand_measurement, card_valid, hand_valid, timestamp: float) -> FusionMeasurement:
        if hand_valid:
            self.validate_started_at = None
            self.fusion_state = "HAND_PROXY_ACTIVE"
            return self._emit(
                visible=True,
                score=self._hand_score(hand_measurement) + self.hand_to_score_offset,
                fusion_state="HAND_PROXY_ACTIVE",
                source="hand_proxy_with_card_anchor",
                confidence=float(hand_measurement.confidence),
                timestamp=timestamp,
                debug={"hand_to_score_offset": self.hand_to_score_offset},
            )

        if card_valid:
            return self._evaluate_hand_to_card(card_measurement, timestamp)

        return self._enter_lost_hold(timestamp)

    def _handle_lost_hold(self, card_measurement, hand_measurement, card_valid, hand_valid, timestamp: float) -> FusionMeasurement:
        anchor_score = self.lost_hold_anchor_score if self.lost_hold_anchor_score is not None else self.displayed_score
        if anchor_score is None:
            self.fusion_state = "NO_TARGET"
            return self._emit(
                visible=False,
                score=None,
                fusion_state="NO_TARGET",
                source="lost",
                confidence=0.0,
                timestamp=timestamp,
            )

        if hand_valid:
            if self.hand_stable_frames < self.min_hand_stable_frames:
                self.fusion_state = "LOST_TO_HAND_PENDING"
                return self._emit(
                    visible=True,
                    score=anchor_score,
                    fusion_state="LOST_TO_HAND_PENDING",
                    source="last_confirmed_user_score",
                    confidence=float(hand_measurement.confidence),
                    timestamp=timestamp,
                    debug={"anchor_score": anchor_score},
                )

            if self.fusion_state == "LOST_TO_HAND_MERGE":
                self.fusion_state = "HAND_PROXY_ACTIVE"
                return self._emit(
                    visible=True,
                    score=self._hand_score(hand_measurement) + self.hand_to_score_offset,
                    fusion_state="HAND_PROXY_ACTIVE",
                    source="hand_proxy_with_lost_hold_anchor",
                    confidence=float(hand_measurement.confidence),
                    timestamp=timestamp,
                    debug={"anchor_score": anchor_score, "hand_to_score_offset": self.hand_to_score_offset},
                )

            self.hand_to_score_offset = anchor_score - self._hand_score(hand_measurement)
            self.fusion_state = "LOST_TO_HAND_MERGE"
            return self._emit(
                visible=True,
                score=anchor_score,
                fusion_state="LOST_TO_HAND_MERGE",
                source="hand_proxy_with_lost_hold_anchor",
                confidence=float(hand_measurement.confidence),
                timestamp=timestamp,
                debug={"anchor_score": anchor_score, "hand_to_score_offset": self.hand_to_score_offset},
            )

        if card_valid:
            card_score = self._card_score(card_measurement, use_offset=False)
            delta = abs(card_score - anchor_score)
            if self.card_stable_frames >= self.min_card_stable_frames and delta <= self.reacquire_tolerance_norm:
                self.card_to_score_offset = anchor_score - card_score
                self.validate_started_at = None
                self.fusion_state = "CARD_REACQUIRED"
                return self._emit(
                    visible=True,
                    score=anchor_score,
                    fusion_state="CARD_REACQUIRED",
                    source="card_reacquired_with_alignment",
                    confidence=float(card_measurement.confidence),
                    timestamp=timestamp,
                    debug={"anchor_score": anchor_score, "delta": delta},
                )

            self.fusion_state = "LOST_REACQUIRE_AMBIGUOUS"
            return self._emit(
                visible=True,
                score=anchor_score,
                fusion_state="LOST_REACQUIRE_AMBIGUOUS",
                source="last_confirmed_user_score",
                confidence=float(card_measurement.confidence),
                timestamp=timestamp,
                debug={"anchor_score": anchor_score, "delta": delta},
            )

        if self.lost_hold_started_at is not None and (timestamp - self.lost_hold_started_at) > self.lost_hold_max_duration_s:
            self.fusion_state = "NO_TARGET"
            self.displayed_score = None
            self.lost_hold_anchor_score = None
            return self._emit(
                visible=False,
                score=None,
                fusion_state="NO_TARGET",
                source="lost",
                confidence=0.0,
                timestamp=timestamp,
            )

        self.fusion_state = "LOST_HOLD"
        return self._emit(
            visible=True,
            score=anchor_score,
            fusion_state="LOST_HOLD",
            source="last_confirmed_user_score",
            confidence=0.0,
            timestamp=timestamp,
            debug={"anchor_score": anchor_score},
        )

    def _evaluate_hand_to_card(self, card_measurement: CardPose, timestamp: float) -> FusionMeasurement:
        anchor_score = self.displayed_score
        if anchor_score is None:
            self.fusion_state = "CARD_OBSERVED"
            return self._emit_card(card_measurement, fusion_state="CARD_OBSERVED", timestamp=timestamp)

        card_score = self._card_score(card_measurement, use_offset=False)
        delta = abs(card_score - anchor_score)
        self.fusion_state = "HAND_TO_CARD_VALIDATE"
        if self.validate_started_at is None:
            self.validate_started_at = timestamp

        if self.card_stable_frames >= self.min_card_stable_frames and delta <= self.reacquire_tolerance_norm:
            self.card_to_score_offset = anchor_score - card_score
            self.validate_started_at = None
            self.fusion_state = "CARD_REACQUIRED"
            return self._emit(
                visible=True,
                score=anchor_score,
                fusion_state="CARD_REACQUIRED",
                source="card_reacquired_with_alignment",
                confidence=float(card_measurement.confidence),
                timestamp=timestamp,
                debug={"delta": delta},
            )

        if self.card_stable_frames < self.min_card_stable_frames:
            return self._emit(
                visible=True,
                score=anchor_score,
                fusion_state="HAND_TO_CARD_VALIDATE",
                source="last_confirmed_user_score",
                confidence=float(card_measurement.confidence),
                timestamp=timestamp,
                debug={"delta": delta, "card_stable_frames": self.card_stable_frames},
            )

        if delta <= self.ambiguous_tolerance_norm:
            elapsed = timestamp - (self.validate_started_at or timestamp)
            if elapsed < self.hand_to_card_validate_timeout_s:
                return self._emit(
                    visible=True,
                    score=anchor_score,
                    fusion_state="HAND_TO_CARD_VALIDATE",
                    source="last_confirmed_user_score",
                    confidence=float(card_measurement.confidence),
                    timestamp=timestamp,
                    debug={"delta": delta, "validate_elapsed_s": elapsed},
                )

        self.fusion_state = "HAND_TO_CARD_AMBIGUOUS"
        return self._emit(
            visible=True,
            score=anchor_score,
            fusion_state="HAND_TO_CARD_AMBIGUOUS",
            source="last_confirmed_user_score",
            confidence=float(card_measurement.confidence),
            timestamp=timestamp,
            debug={"delta": delta},
        )

    def _enter_lost_hold(self, timestamp: float) -> FusionMeasurement:
        if self.displayed_score is None:
            self.fusion_state = "NO_TARGET"
            return self._emit(
                visible=False,
                score=None,
                fusion_state="NO_TARGET",
                source="lost",
                confidence=0.0,
                timestamp=timestamp,
            )

        if self.fusion_state != "LOST_HOLD":
            self.lost_hold_anchor_score = self.displayed_score
            self.lost_hold_entered_from = self.fusion_state
            self.lost_hold_started_at = timestamp
            self.hand_to_score_offset = 0.0
            self.card_to_score_offset = 0.0
        self.validate_started_at = None
        self.fusion_state = "LOST_HOLD"
        return self._emit(
            visible=True,
            score=self.lost_hold_anchor_score,
            fusion_state="LOST_HOLD",
            source="last_confirmed_user_score",
            confidence=0.0,
            timestamp=timestamp,
            debug={
                "anchor_score": self.lost_hold_anchor_score,
                "entered_from": self.lost_hold_entered_from,
            },
        )

    def _emit_card(self, card_measurement: CardPose, *, fusion_state: str, timestamp: float) -> FusionMeasurement:
        raw_score = self._card_score(card_measurement)
        score = raw_score if self.displayed_score is None else self._smooth_score(raw_score, fusion_state=fusion_state)
        return self._emit(
            visible=True,
            score=score,
            fusion_state=fusion_state,
            source=card_measurement.source or "card_detector",
            confidence=float(card_measurement.confidence),
            timestamp=timestamp,
            debug={"detector_source": card_measurement.source},
        )

    def _emit(
        self,
        *,
        visible: bool,
        score: Optional[float],
        fusion_state: str,
        source: str,
        confidence: float,
        timestamp: float,
        debug: Optional[Dict[str, Any]] = None,
    ) -> FusionMeasurement:
        if score is not None:
            score = clamp(score)
            self.displayed_score = score
            self.last_visible_time = timestamp
        elif not visible:
            self.last_visible_time = None

        rating = None if score is None else round(score * 10.0, 1)
        return FusionMeasurement(
            visible=visible,
            score=score,
            rating=rating,
            fusion_state=fusion_state,
            source=source,
            confidence=confidence,
            x_normalized=score,
            timestamp=timestamp,
            debug=debug or {},
        )

    def _smooth_score(self, score: float, *, fusion_state: str) -> float:
        if self.displayed_score is None:
            return clamp(score)
        if not self.allow_displayed_score_drift and fusion_state in {"HAND_TO_CARD_VALIDATE", "HAND_TO_CARD_AMBIGUOUS"}:
            return self.displayed_score
        alpha = self.score_ema_alpha
        return clamp((alpha * score) + ((1.0 - alpha) * self.displayed_score))

    def _card_score(self, card_measurement: CardPose, *, use_offset: bool = True) -> float:
        raw = clamp(float(card_measurement.x_normalized or 0.0))
        if not use_offset:
            return raw
        return clamp(raw + self.card_to_score_offset)

    @staticmethod
    def _hand_score(hand_measurement: HandMeasurement) -> float:
        return clamp(float(hand_measurement.proxy_x_normalized or 0.0))