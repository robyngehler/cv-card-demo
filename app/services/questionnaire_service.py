from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, Optional


@dataclass
class QuestionDefinition:
    id: str
    label: str
    min_label: str = "0"
    max_label: str = "10"
    min_motion_norm: float = 0.03
    small_motion_epsilon: float = 0.005
    active_motion_duration_s: float = 1.0
    idle_before_countdown_s: float = 3.0
    countdown_s: float = 3.0
    snapshot_on_confirm: bool = True


class ConfigDrivenQuestionnaireRuntime:
    service_name = "questionnaire"

    def __init__(self, context):
        self.context = context
        self.questions = self._load_questions()
        # Brief "Hallo <name>" greeting hold at the start of a new session,
        # before scoring begins. 0 disables it.
        self.greeting_duration_s = float(
            context.config.get("questionnaire", {}).get("greeting_duration_s", 4.0)
        )
        self.status: Dict[str, Any] = {
            "status": "READY" if self.questions else "EMPTY",
            "question_count": len(self.questions),
        }

    def ensure_session(
        self,
        *,
        candidate_id: Optional[str] = None,
        identity_status: Optional[str] = None,
        resume_policy: str = "resume_incomplete_or_new",
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        timestamp = time.monotonic() if now is None else now
        session = self.context.runtime.get("session", {})
        if session.get("session_id") and not session.get("completed"):
            if candidate_id is None or candidate_id == session.get("candidate_id"):
                self.context.runtime.setdefault("questionnaire", {})["active"] = True
                return session

        identity = self.context.get_service("identity", default=None)
        persistence = self.context.get_service("persistence", default=None)
        if candidate_id is None and identity is not None:
            candidate_id = identity.create_temporary_candidate_id()

        if identity_status is None:
            identity_status = self._default_identity_status(candidate_id)

        resumed_progress = None
        if (
            persistence is not None
            and candidate_id is not None
            and resume_policy == "resume_incomplete_or_new"
        ):
            resumed_progress = persistence.get_candidate_session_progress(candidate_id)

        if resumed_progress is not None and int(resumed_progress.get("answers_count", 0)) < len(self.questions):
            session_id = resumed_progress["session_id"]
            question_index = int(resumed_progress.get("answers_count", 0))
            completed = False
        else:
            if identity is not None:
                session_id = identity.create_session_id()
            else:
                session_id = f"session_{int(time.time())}"
            question_index = 0
            completed = False

        question = self.current_question(index=question_index)

        # Load candidate name from persistence if available
        candidate_name = None
        if persistence is not None and candidate_id is not None:
            candidate = persistence.find_candidate(candidate_id)
            if candidate is not None:
                candidate_name = candidate.get("name")

        session_payload = {
            "session_id": session_id,
            "candidate_id": candidate_id,
            "candidate_name": candidate_name,
            "identity_status": identity_status,
            "card_identity_state": identity_status,
            "question_index": question_index,
            "current_question_id": question.id if question is not None else None,
            "current_score": None,
            "last_motion_time": None,
            "first_motion_time": None,
            "stable_since": None,
            "countdown_started_at": None,
            "phase": "WAIT_FOR_MOVEMENT",
            "answers": [],
            "completed": completed,
            "started_at_monotonic": timestamp,
            "last_score": None,
            "question_start_score": None,
            "latest_motion": 0.0,
            "acc_question_motion": 0.0,
        }
        self.context.runtime["session"] = session_payload
        questionnaire_runtime = self.context.runtime.setdefault("questionnaire", {})
        questionnaire_runtime["active"] = True
        questionnaire_runtime["pending_snapshot"] = False
        questionnaire_runtime["last_completed_question_id"] = None
        self.context.runtime.setdefault("tracking", {})["countdown_visible"] = False

        if persistence is not None and candidate_id is not None:
            persistence.ensure_candidate(candidate_id=candidate_id, identity_status=identity_status)
            persistence.create_session(
                session_id=session_id,
                candidate_id=candidate_id,
                state="ACTIVE",
            )

        return session_payload

    def current_question(self, *, index: Optional[int] = None) -> Optional[QuestionDefinition]:
        if not self.questions:
            return None
        if index is None:
            index = int(self.context.runtime.get("session", {}).get("question_index", 0) or 0)
        if index < 0 or index >= len(self.questions):
            return None
        return self.questions[index]

    def update(self, fusion_measurement, *, now: Optional[float] = None) -> Dict[str, Any]:
        timestamp = time.monotonic() if now is None else now
        session = self.context.runtime.get("session", {})
        question = self.current_question()
        if question is None or not session.get("session_id") or fusion_measurement.score is None:
            return self._ui_context(question=None, countdown_remaining_s=None)

        # Greeting hold: on the first question of a fresh session, show the
        # "Hallo <name>" panel for greeting_duration_s before scoring starts.
        if (
            self.greeting_duration_s > 0.0
            and int(session.get("question_index", 0) or 0) == 0
            and not session.get("greeting_done")
        ):
            started = session.get("started_at_monotonic")
            if started is not None and (timestamp - float(started)) < self.greeting_duration_s:
                session["phase"] = "GREETING"
                return self._ui_context(question=question, countdown_remaining_s=None)
            session["greeting_done"] = True

        score = float(fusion_measurement.score)
        session["current_score"] = score
        previous_score = session.get("last_score")
        question_start_score = session.get("question_start_score")
        if question_start_score is None:
            question_start_score = score
            session["question_start_score"] = score

        latest_motion = 0.0 if previous_score is None else abs(score - float(previous_score))
        acc_question_motion = abs(score - float(question_start_score))
        session["latest_motion"] = latest_motion
        session["acc_question_motion"] = acc_question_motion
        session["last_score"] = score

        has_latest_motion = latest_motion >= question.small_motion_epsilon
        has_required_motion = acc_question_motion >= question.min_motion_norm

        if has_latest_motion:
            session["stable_since"] = None
            session["countdown_started_at"] = None
            self.context.runtime.setdefault("tracking", {})["countdown_visible"] = False
            if has_required_motion:
                if session.get("first_motion_time") is None:
                    session["first_motion_time"] = timestamp
                session["last_motion_time"] = timestamp
                session["phase"] = "ACTIVE_SCORING"
            else:
                session["phase"] = "WAIT_FOR_MOVEMENT"
        else:
            if session.get("stable_since") is None:
                session["stable_since"] = timestamp

            if not has_required_motion:
                session["phase"] = "WAIT_FOR_MOVEMENT"
            else:
                first_motion_time = session.get("first_motion_time")
                active_duration = 0.0
                if first_motion_time is not None and has_required_motion:
                    active_duration = max(0.0, timestamp - float(first_motion_time))

                idle_duration = max(0.0, timestamp - float(session.get("stable_since") or timestamp))
                if active_duration < question.active_motion_duration_s:
                    session["phase"] = "ACTIVE_SCORING"
                elif idle_duration < question.idle_before_countdown_s:
                    session["phase"] = "WAIT_FOR_STABILITY"
                else:
                    if session.get("countdown_started_at") is None:
                        session["countdown_started_at"] = timestamp
                    session["phase"] = "COUNTDOWN"
                    self.context.runtime.setdefault("tracking", {})["countdown_visible"] = True

        countdown_remaining_s = None
        if session.get("phase") == "COUNTDOWN":
            countdown_started_at = session.get("countdown_started_at") or timestamp
            elapsed = timestamp - countdown_started_at
            countdown_remaining_s = max(0.0, question.countdown_s - elapsed)
            if countdown_remaining_s <= 0.0:
                session["phase"] = "SNAPSHOT_PENDING"
                self.context.runtime.setdefault("questionnaire", {})["pending_snapshot"] = bool(
                    question.snapshot_on_confirm
                )
                self.context.runtime.setdefault("tracking", {})["countdown_visible"] = False

        return self._ui_context(question=question, countdown_remaining_s=countdown_remaining_s)

    def consume_snapshot_request(self) -> bool:
        questionnaire_runtime = self.context.runtime.setdefault("questionnaire", {})
        pending = bool(questionnaire_runtime.get("pending_snapshot"))
        questionnaire_runtime["pending_snapshot"] = False
        return pending

    def build_answer_payload(self, fusion_measurement) -> Dict[str, Any]:
        question = self.current_question()
        session = self.context.runtime.get("session", {})
        return {
            "session_id": session.get("session_id"),
            "candidate_id": session.get("candidate_id"),
            "identity_status": session.get("identity_status"),
            "question_id": question.id if question is not None else None,
            "score": fusion_measurement.score,
            "rating": fusion_measurement.rating,
            "source": fusion_measurement.source,
            "timestamp": fusion_measurement.timestamp,
            "fusion_state": fusion_measurement.fusion_state,
        }

    def complete_snapshot(self, answer_payload: Dict[str, Any]) -> Dict[str, Any]:
        session = self.context.runtime.get("session", {})
        answers = session.setdefault("answers", [])
        answers.append(answer_payload)
        self.context.runtime.setdefault("questionnaire", {})["last_completed_question_id"] = answer_payload.get(
            "question_id"
        )

        next_index = int(session.get("question_index", 0) or 0) + 1
        next_question = self.current_question(index=next_index)
        if next_question is None:
            session["completed"] = True
            session["phase"] = "DONE"
            self.context.runtime.setdefault("questionnaire", {})["active"] = False
            return {"completed": True, "next_question_id": None}

        session["question_index"] = next_index
        session["current_question_id"] = next_question.id
        session["current_score"] = None
        session["last_motion_time"] = None
        session["first_motion_time"] = None
        session["stable_since"] = None
        session["countdown_started_at"] = None
        session["phase"] = "WAIT_FOR_MOVEMENT"
        session["last_score"] = None
        session["question_start_score"] = None
        session["latest_motion"] = 0.0
        session["acc_question_motion"] = 0.0
        self.context.runtime.setdefault("tracking", {})["countdown_visible"] = False
        return {"completed": False, "next_question_id": next_question.id}

    def get_status(self) -> Dict[str, Any]:
        session = self.context.runtime.get("session", {})
        payload = dict(self.status)
        payload["session"] = {
            "session_id": session.get("session_id"),
            "candidate_id": session.get("candidate_id"),
            "question_index": session.get("question_index"),
            "current_question_id": session.get("current_question_id"),
            "phase": session.get("phase"),
            "completed": session.get("completed"),
        }
        return payload

    def _load_questions(self) -> list[QuestionDefinition]:
        question_config = self.context.config.get("questionnaire", {}).get("questions") or [
            {
                "id": "experience",
                "label": "How was your experience?",
            },
            {
                "id": "team",
                "label": "How was the team?",
            },
        ]
        questions = []
        for entry in question_config:
            questions.append(
                QuestionDefinition(
                    id=str(entry.get("id") or f"question_{len(questions) + 1}"),
                    label=str(entry.get("label") or "Question"),
                    min_label=str(entry.get("min_label", "0")),
                    max_label=str(entry.get("max_label", "10")),
                    min_motion_norm=float(entry.get("min_motion_norm", 0.03)),
                    small_motion_epsilon=float(entry.get("small_motion_epsilon", 0.005)),
                    active_motion_duration_s=float(entry.get("active_motion_duration_s", 1.0)),
                    idle_before_countdown_s=float(entry.get("idle_before_countdown_s", 3.0)),
                    countdown_s=float(entry.get("countdown_s", 3.0)),
                    snapshot_on_confirm=bool(entry.get("snapshot_on_confirm", True)),
                )
            )
        return questions

    def _ui_context(
        self,
        *,
        question: Optional[QuestionDefinition],
        countdown_remaining_s: Optional[float],
    ) -> Dict[str, Any]:
        session = self.context.runtime.get("session", {})
        payload = {
            "question_id": question.id if question is not None else session.get("current_question_id"),
            "question_label": question.label if question is not None else None,
            "question_min_label": question.min_label if question is not None else None,
            "question_max_label": question.max_label if question is not None else None,
            "phase": session.get("phase", "WAIT_FOR_MOVEMENT"),
            "countdown_remaining_s": countdown_remaining_s,
            "question_index": session.get("question_index", 0),
            "answers_count": len(session.get("answers", [])),
            "session_id": session.get("session_id"),
            "candidate_id": session.get("candidate_id"),
            "identity_status": session.get("identity_status"),
            "message": self._phase_message(session.get("phase", "WAIT_FOR_MOVEMENT")),
        }
        return payload

    @staticmethod
    def _default_identity_status(candidate_id: Optional[str]) -> str:
        if candidate_id and str(candidate_id).startswith("tmp_"):
            return "TEMPORARY"
        return "RESOLVED"

    @staticmethod
    def _phase_message(phase: str) -> str:
        if phase == "GREETING":
            return "Welcome!"
        if phase == "WAIT_FOR_MOVEMENT":
            return "Move the business card to set your rating."
        if phase == "ACTIVE_SCORING":
            return "Live score is active."
        if phase == "WAIT_FOR_STABILITY":
            return "Hold the card steady to confirm your selection."
        if phase == "COUNTDOWN":
            return "Snapshot countdown is running."
        if phase == "SNAPSHOT_PENDING":
            return "Preparing snapshot capture."
        if phase == "DONE":
            return "Questionnaire complete."
        return "Place a business card to begin."