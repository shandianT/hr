"""Deterministic synthetic interview-scheduling control plane."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional, Tuple

try:
    from runtime.recruiting_screening.control import RecruitingG2Control
except ModuleNotFoundError:
    from recruiting_screening.control import RecruitingG2Control


JsonObject = Dict[str, Any]
_SYNTHETIC_ADAPTER_CAPABILITY = object()


class RecruitingSchedulingControl(RecruitingG2Control):
    """Own scheduling facts behind the business ``submit`` / ``read`` seam.

    The inherited synthetic Case binding helpers are fixture-only harness
    surface, not scheduling business APIs.
    """

    _SCHEDULING_TARGETS = {
        "OpenCandidateCoordinationRequest": "INTERVIEW_SESSION",
        "PublishSchedulingProposal": "INTERVIEW_SESSION",
        "RecordCandidateSlotSelection": "INTERVIEW_SESSION",
        "ProposeAppointmentRevision": "INTERVIEW_SESSION",
        "QueueSchedulingAction": "ACTION_EXECUTION",
        "ExecuteSchedulingAction": "ACTION_EXECUTION",
        "ReconcileSchedulingAction": "ACTION_EXECUTION",
        "RecordSchedulingProviderObservation": "ACTION_EXECUTION",
        "CommitBooking": "INTERVIEW_SESSION",
        "SupersedeAppointmentRevision": "INTERVIEW_SESSION",
        "PauseScope": "APPLICATION_CASE",
        "QueueSchedulingCompensation": "ACTION_EXECUTION",
        "RecordRecordingNoticeDelivery": "INTERVIEW_SESSION",
    }
    _SCHEDULING_ACTORS = {
        "OpenCandidateCoordinationRequest": {
            ("SERVICE", "scheduling-workflow", "SCHEDULING_WORKFLOW")
        },
        "PublishSchedulingProposal": {
            ("SERVICE", "scheduling-workflow", "SCHEDULING_WORKFLOW")
        },
        "RecordCandidateSlotSelection": {
            ("EXTERNAL_PARTICIPANT", "candidate-lina", "CANDIDATE")
        },
        "ProposeAppointmentRevision": {
            ("SERVICE", "scheduling-workflow", "SCHEDULING_WORKFLOW")
        },
        "QueueSchedulingAction": {
            ("SERVICE", "scheduling-worker", "SCHEDULING_WORKER")
        },
        "ExecuteSchedulingAction": {
            ("SERVICE", "scheduling-worker", "SCHEDULING_WORKER")
        },
        "ReconcileSchedulingAction": {
            ("SERVICE", "scheduling-worker", "SCHEDULING_WORKER")
        },
        "RecordSchedulingProviderObservation": {
            (
                "SERVICE",
                "provider-callback-gateway",
                "SCHEDULING_PROVIDER_CALLBACK",
            )
        },
        "CommitBooking": {
            ("SERVICE", "scheduling-workflow", "SCHEDULING_WORKFLOW")
        },
        "SupersedeAppointmentRevision": {
            ("SERVICE", "scheduling-workflow", "SCHEDULING_WORKFLOW")
        },
        "PauseScope": {("HUMAN", "product-demo-user", "RECRUITING_OPS")},
        "QueueSchedulingCompensation": {
            ("SERVICE", "scheduling-worker", "SCHEDULING_WORKER")
        },
        "RecordRecordingNoticeDelivery": {
            ("SERVICE", "scheduling-workflow", "SCHEDULING_WORKFLOW")
        },
    }
    _RESOURCE_KINDS = (
        "CALENDAR_EVENT",
        "MEETING_RESOURCE",
        "INVITATION_WRITE",
    )

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        adapters: Any,
        synthetic_now: str = "2026-08-11T12:00:00Z",
        clock: Optional[Callable[[], Any]] = None,
    ) -> None:
        if (
            getattr(adapters, "_synthetic_capability", None)
            is not _SYNTHETIC_ADAPTER_CAPABILITY
        ):
            raise TypeError(
                "RecruitingSchedulingControl accepts synthetic adapters only"
            )
        super().__init__(connection, synthetic_now=synthetic_now, clock=clock)
        self._adapters = adapters
        self._adapter_identity = (
            adapters,
            adapters.calendar,
            adapters.meeting,
            adapters.invitation,
        )
        self._authority_grants.update(
            {
                (
                    "tenant-synthetic",
                    "SERVICE",
                    "scheduling-workflow",
                    "SCHEDULING_WORKFLOW",
                ),
                (
                    "tenant-synthetic",
                    "SERVICE",
                    "scheduling-worker",
                    "SCHEDULING_WORKER",
                ),
                (
                    "tenant-synthetic",
                    "EXTERNAL_PARTICIPANT",
                    "candidate-lina",
                    "CANDIDATE",
                ),
                (
                    "tenant-synthetic",
                    "SERVICE",
                    "provider-callback-gateway",
                    "SCHEDULING_PROVIDER_CALLBACK",
                ),
            }
        )
        self._install_scheduling_schema()

    def read(self, request: JsonObject) -> JsonObject:
        self._require_synthetic_adapters()
        service_views = {
            (
                "SERVICE",
                "scheduling-workflow",
                "SCHEDULING_WORKFLOW",
            ): "SCHEDULING_CASE_CONTEXT",
            (
                "SERVICE",
                "scheduling-worker",
                "SCHEDULING_WORKER",
            ): "BOOKING_RECONCILIATION_VIEW",
        }
        actor = request.get("actor_context") if isinstance(request, dict) else None
        actor_key = (
            actor.get("actor_type"),
            actor.get("actor_id"),
            actor.get("role"),
        ) if isinstance(actor, dict) else None
        expected_view = service_views.get(actor_key)
        if expected_view is not None:
            expected_keys = {
                "tenant_id",
                "application_case_id",
                "interview_session_id",
                "view",
                "actor_context",
            }
            if (
                set(request) != expected_keys
                or request.get("view") != expected_view
                or (
                    request.get("tenant_id"),
                    actor_key[0],
                    actor_key[1],
                    actor_key[2],
                )
                not in self._authority_grants
            ):
                raise PermissionError(
                    "scheduling service projection must be case-bound and purpose-bound"
                )
            return self._read_scheduling_service_case(request, expected_view)
        if isinstance(request, dict) and request.get("view") == "SCHEDULING_CASE_VIEW":
            expected = {
                "tenant_id",
                "application_case_id",
                "view",
                "actor_context",
            }
            actor = request.get("actor_context")
            if (
                set(request) != expected
                or request.get("tenant_id") != "tenant-synthetic"
                or actor
                != {
                    "actor_type": "HUMAN",
                    "actor_id": "product-demo-user",
                    "role": "RECRUITING_OPS",
                }
            ):
                raise PermissionError("scheduling projection must be case-bound")
            return self._read_scheduling_case(
                request["tenant_id"], request.get("application_case_id")
            )
        return super().read(request)

    def _read_scheduling_service_case(
        self, request: JsonObject, view: str
    ) -> JsonObject:
        tenant_id = request["tenant_id"]
        case_id = request["application_case_id"]
        session_id = request["interview_session_id"]
        case_loaded = self._load_case(tenant_id, case_id)
        session_loaded = self._load_session(tenant_id, session_id)
        if (
            not case_loaded
            or not session_loaded
            or session_loaded[1].get("application_case_id") != case_id
        ):
            raise PermissionError(
                "scheduling service projection must be case-bound and purpose-bound"
            )
        case_version, case = case_loaded
        session_version, session = session_loaded
        session_projection = {
            "session_id": session_id,
            "version": session_version,
            "application_case_id": case_id,
            "case_lifecycle_epoch": session.get("case_lifecycle_epoch"),
            "round_ref": deepcopy(session.get("round_ref")),
            "scheduling_state": session.get("scheduling_state"),
            "coordination_request": deepcopy(session.get("coordination_request")),
            "current_proposal": deepcopy(session.get("current_proposal")),
            "current_selection": deepcopy(session.get("current_selection")),
            "pending_appointment_revision": deepcopy(
                session.get("pending_appointment_revision")
            ),
            "current_booking": deepcopy(session.get("current_booking")),
            "participants": [
                {
                    "tenant_id": item["tenant_id"],
                    "participant_id": item["participant_id"],
                    "role": item["role"],
                    "timezone": item["timezone"],
                }
                for item in session.get("participants", [])
            ],
            "recording_notice_deliveries": deepcopy(
                session.get("recording_notice_deliveries", [])
            ),
            "consent_receipt_count": len(session.get("consent_receipts", [])),
            "capture_mode": session.get("capture_mode"),
            "fixture_only": session.get("fixture_only", False),
        }
        result = {
            "synthetic_only": True,
            "view": view,
            "application_case_id": case_id,
            "case": {
                "application_case_id": case_id,
                "version": case_version,
                "state": case.get("state"),
                "lifecycle_epoch": case.get("lifecycle_epoch"),
                "scheduling_control": deepcopy(case.get("scheduling_control")),
            },
            "session": session_projection,
        }
        if view == "BOOKING_RECONCILIATION_VIEW":
            actions = []
            for row in self._db.execute(
                "SELECT action_id, version, state_json "
                "FROM scheduling_action_executions "
                "WHERE tenant_id = ? AND application_case_id = ? ORDER BY action_id",
                (tenant_id, case_id),
            ):
                action = json.loads(row["state_json"])
                if action.get("session_id") != session_id:
                    continue
                actions.append(
                    {
                        key: deepcopy(action.get(key))
                        for key in (
                            "action_id",
                            "application_case_id",
                            "session_id",
                            "appointment_revision",
                            "resource_kind",
                            "action_category",
                            "state",
                            "attempt_count",
                            "blocked_reason",
                            "receipt",
                            "provider_observation_ids",
                        )
                    }
                )
                actions[-1]["version"] = row["version"]
            result["scheduling_action_executions"] = actions
        return result

    def _read_scheduling_case(self, tenant_id: str, case_id: Any) -> JsonObject:
        loaded_case = self._load_case(tenant_id, case_id) if isinstance(case_id, str) else None
        if not loaded_case:
            raise PermissionError("scheduling projection must be case-bound")
        case_version, case = loaded_case
        sessions = {}
        for row in self._db.execute(
            "SELECT session_id, version, state_json FROM interview_sessions "
            "WHERE tenant_id = ? AND application_case_id = ? ORDER BY session_id",
            (tenant_id, case_id),
        ):
            state = json.loads(row["state_json"])
            state["version"] = row["version"]
            sessions[row["session_id"]] = state
        actions = []
        for row in self._db.execute(
            "SELECT action_id, version, state_json FROM scheduling_action_executions "
            "WHERE tenant_id = ? AND application_case_id = ? ORDER BY action_id",
            (tenant_id, case_id),
        ):
            state = json.loads(row["state_json"])
            state["version"] = row["version"]
            actions.append(state)
        counts = {
            "CALENDAR_EVENT": self._adapters.calendar.effect_count(case_id),
            "MEETING_RESOURCE": self._adapters.meeting.effect_count(case_id),
            "INVITATION_WRITE": self._adapters.invitation.effect_count(case_id),
        }
        return {
            "synthetic_only": True,
            "application_case_id": case_id,
            "case": {
                "application_case_id": case_id,
                "version": case_version,
                "state": case.get("state"),
                "lifecycle_epoch": case.get("lifecycle_epoch"),
                "scheduling_control": deepcopy(case.get("scheduling_control")),
            },
            "interview_sessions": sessions,
            "scheduling_action_executions": actions,
            "synthetic_resource_effect_counts": counts,
            "synthetic_external_effect_count": sum(counts.values()),
            "invitation_delivery_receipt_count": 0,
            "invitation_read_receipt_count": 0,
            "recording_notice_delivery_count": sum(
                len(session.get("recording_notice_deliveries", []))
                for session in sessions.values()
            ),
            "consent_receipt_count": sum(
                len(session.get("consent_receipts", []))
                for session in sessions.values()
            ),
            "synthetic_calendar_cancellation_count": self._adapters.calendar.cancellation_count(
                case_id
            ),
            "real_external_effect_count": 0,
        }

    def _validate_envelope(self, envelope: Any) -> Optional[Tuple[str, str]]:
        if not self._synthetic_adapters_are_current():
            return (
                "SYNTHETIC_ADAPTER_BOUNDARY_VIOLATION",
                "合成运行时 Adapter 身份或能力已变化，拒绝继续执行。",
            )
        error = super()._validate_envelope(envelope)
        if error:
            return error
        command_type = envelope["command_type"]
        target = self._SCHEDULING_TARGETS.get(command_type)
        if not target:
            return None
        if envelope["aggregate_type"] != target:
            return (
                "AGGREGATE_TARGET_MISMATCH",
                "命令目标聚合与约面命令的唯一写入对象不一致。",
            )
        actor = envelope["actor"]
        actor_key = (actor["actor_type"], actor["actor_id"], actor["role"])
        if actor_key not in self._SCHEDULING_ACTORS[command_type]:
            return "AUTHORIZATION_DENIED", "当前主体无权提交这一约面命令。"
        return None

    def _seed_fixture_ready_session(self, application_case_id: str) -> None:
        """Fixture-only seed; this does not claim InterviewPlan materialization."""

        loaded = self._load_case("tenant-synthetic", application_case_id)
        if not loaded or loaded[1].get("state") != "INTERVIEWING":
            raise ValueError("fixture Session requires one HUMAN INVITE Case")
        _, case = loaded
        session_id = "session:{}:round-1:required-1".format(application_case_id)
        state = {
            "session_id": session_id,
            "application_case_id": application_case_id,
            "case_lifecycle_epoch": case["lifecycle_epoch"],
            "round_ref": {
                "round_id": "round:{}:1".format(application_case_id),
                "state": "READY_TO_SCHEDULE",
                "required": True,
                "fixture_only": True,
                "plan_materialized": False,
            },
            "scheduling_state": "NOT_STARTED",
            "coordination_request": None,
            "proposal_history": [],
            "current_proposal": None,
            "selection_history": [],
            "current_selection": None,
            "appointment_revision_sequence": 0,
            "appointment_history": [],
            "pending_appointment_revision": None,
            "current_booking": None,
            "booking_history": [],
            "recording_notice_deliveries": [],
            "consent_receipts": [],
            "capture_mode": "UNDECIDED",
            "participants": [
                {
                    "tenant_id": "tenant-synthetic",
                    "participant_id": "candidate-lina",
                    "role": "CANDIDATE",
                    "timezone": "Asia/Shanghai",
                },
                {
                    "tenant_id": "tenant-synthetic",
                    "participant_id": "interviewer-1",
                    "role": "INTERVIEWER",
                    "timezone": "Asia/Shanghai",
                },
            ],
            "fixture_only": True,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO interview_sessions "
            "(tenant_id, session_id, application_case_id, version, state_json) "
            "VALUES (?, ?, ?, 1, ?)",
            (
                "tenant-synthetic",
                session_id,
                application_case_id,
                _canonical(state),
            ),
        )
        self._db.commit()

    def _handle_OpenCandidateCoordinationRequest(self, envelope: JsonObject) -> JsonObject:
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "NOT_STARTED")
        if error:
            return self._rejected(envelope, error[0], error[1])
        request_id = "coordination:{}:1".format(session["session_id"])
        session["coordination_request"] = {
            "request_id": request_id,
            "revision": 1,
            "status": "OPEN",
            "purpose": "INTERVIEW_SCHEDULING",
            "candidate_participant_id": "candidate-lina",
            "expires_at": "2026-08-11T13:00:00Z",
            "credential_revision": 1,
        }
        session["scheduling_state"] = "COORDINATING"
        self._save_session(envelope["tenant_id"], session["session_id"], version + 1, session)
        event_id = self._append_event(
            envelope["tenant_id"],
            "CandidateCoordinationRequestOpened",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "request_id": request_id,
                "request_revision": 1,
                "fixture_only": True,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "COORDINATION_OPENED", "request_id": request_id},
        )

    def _handle_PublishSchedulingProposal(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_session_version",
                "expected_lifecycle_epoch",
                "coordination_request_id",
                "coordination_request_revision",
            },
            integer_keys={
                "expected_session_version",
                "expected_lifecycle_epoch",
                "coordination_request_revision",
            },
            string_keys={"coordination_request_id"},
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "约面命令字段或版本类型不符合封闭契约。",
            )
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "COORDINATING")
        if error:
            return self._rejected(envelope, error[0], error[1])
        request = session["coordination_request"]
        if (
            request.get("status") != "OPEN"
            or payload["coordination_request_id"] != request["request_id"]
            or payload["coordination_request_revision"] != request["revision"]
        ):
            return self._rejected(
                envelope,
                "STALE_COORDINATION_REQUEST",
                "时段提案没有绑定当前候选人协调请求。",
            )
        availability = self._adapters.calendar.read_availability(
            {
                "observed_at": self._now.isoformat().replace("+00:00", "Z"),
                "scope_hash": _hash(
                    {
                        "session_id": session["session_id"],
                        "participants": session["participants"],
                        "duration_minutes": 60,
                    }
                ),
            }
        )
        proposal = {
            "proposal_id": "proposal:{}:1".format(session["session_id"]),
            "version": 1,
            "status": "OPEN",
            "coordination_request_ref": {
                "request_id": request["request_id"],
                "revision": request["revision"],
            },
            "availability_snapshot_ref": {
                "provider": availability["provider"],
                "revision": availability["revision"],
                "snapshot_hash": availability["snapshot_hash"],
                "expires_at": availability["expires_at"],
            },
            "slots": deepcopy(availability["slots"]),
            "expires_at": availability["expires_at"],
        }
        session["current_proposal"] = proposal
        session["proposal_history"].append(deepcopy(proposal))
        session["scheduling_state"] = "PROPOSAL_OPEN"
        self._save_session(envelope["tenant_id"], session["session_id"], version + 1, session)
        event_id = self._append_event(
            envelope["tenant_id"],
            "SchedulingProposalPublished",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "proposal_id": proposal["proposal_id"],
                "proposal_version": 1,
                "availability_snapshot_hash": availability["snapshot_hash"],
                "expires_at": proposal["expires_at"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "PROPOSAL_PUBLISHED",
                "proposal_id": proposal["proposal_id"],
                "proposal_version": 1,
            },
        )

    def _handle_RecordCandidateSlotSelection(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_session_version",
                "expected_lifecycle_epoch",
                "proposal_id",
                "proposal_version",
                "slot_ref",
                "selection_action_id",
                "coordination_credential_revision",
            },
            integer_keys={
                "expected_session_version",
                "expected_lifecycle_epoch",
                "proposal_version",
                "coordination_credential_revision",
            },
            string_keys={"proposal_id", "slot_ref", "selection_action_id"},
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "候选人选时字段或版本类型不符合封闭契约。",
            )
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "PROPOSAL_OPEN")
        if error:
            return self._rejected(envelope, error[0], error[1])
        proposal = session["current_proposal"]
        request = session.get("coordination_request") or {}
        if (
            payload["coordination_credential_revision"]
            != request.get("credential_revision")
            or envelope["actor"]["actor_id"]
            != request.get("candidate_participant_id")
        ):
            return self._rejected(
                envelope,
                "COORDINATION_CREDENTIAL_STALE",
                "候选人协调凭据已失效或不属于当前候选人。",
            )
        if _parse_time(proposal["expires_at"]) <= self._now:
            return self._rejected(
                envelope, "PROPOSAL_EXPIRED", "候选人使用的时段提案已过期。"
            )
        if (
            payload.get("proposal_id") != proposal["proposal_id"]
            or payload.get("proposal_version") != proposal["version"]
            or payload.get("slot_ref")
            not in {slot["slot_ref"] for slot in proposal["slots"]}
        ):
            return self._rejected(
                envelope, "STALE_PROPOSAL_REVISION", "候选人选择没有引用当前时段提案。"
            )
        selection = {
            "selection_action_id": payload.get("selection_action_id"),
            "revision": len(session["selection_history"]) + 1,
            "proposal_id": proposal["proposal_id"],
            "proposal_version": proposal["version"],
            "slot_ref": payload["slot_ref"],
            "candidate_actor_id": envelope["actor"]["actor_id"],
        }
        session["current_selection"] = selection
        session["selection_history"].append(deepcopy(selection))
        self._save_session(envelope["tenant_id"], session["session_id"], version + 1, session)
        event_id = self._append_event(
            envelope["tenant_id"],
            "CandidateSlotSelectionRecorded",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                **selection,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "SELECTION_RECORDED", "booking_created": False},
        )

    def _handle_ProposeAppointmentRevision(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_session_version",
                "expected_lifecycle_epoch",
                "selection_action_id",
                "selection_revision",
            },
            integer_keys={
                "expected_session_version",
                "expected_lifecycle_epoch",
                "selection_revision",
            },
            string_keys={"selection_action_id"},
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "预约修订字段或版本类型不符合封闭契约。",
            )
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "PROPOSAL_OPEN")
        if error:
            return self._rejected(envelope, error[0], error[1])
        selection = session.get("current_selection")
        if not selection:
            return self._rejected(envelope, "SELECTION_REQUIRED", "尚无当前候选人选时意图。")
        if (
            payload["selection_action_id"] != selection["selection_action_id"]
            or payload["selection_revision"] != selection["revision"]
        ):
            return self._rejected(
                envelope,
                "STALE_SELECTION_REVISION",
                "预约修订没有绑定当前候选人选时记录。",
            )
        availability = self._adapters.calendar.read_availability(
            {
                "observed_at": self._now.isoformat().replace("+00:00", "Z"),
                "scope_hash": _hash(
                    {
                        "session_id": session["session_id"],
                        "participants": session["participants"],
                        "duration_minutes": 60,
                    }
                ),
            }
        )
        proposal = session.get("current_proposal") or {}
        offered_slot = next(
            (
                item
                for item in proposal.get("slots", [])
                if item.get("slot_ref") == selection["slot_ref"]
            ),
            None,
        )
        slot = next(
            (
                item
                for item in availability["slots"]
                if item["slot_ref"] == selection["slot_ref"]
            ),
            None,
        )
        if not slot or not offered_slot or _canonical(slot) != _canonical(offered_slot):
            return self._rejected(envelope, "SLOT_CONFLICT", "选中时段在执行前重验时已冲突。")
        revision = session["appointment_revision_sequence"] + 1
        scope_hash = _hash(
            {
                "tenant_id": envelope["tenant_id"],
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "appointment_revision": revision,
                "slot": slot,
                "participants": session["participants"],
            }
        )
        pending = {
            "appointment_revision": revision,
            "status": "PENDING",
            "selection_ref": deepcopy(selection),
            "slot": deepcopy(slot),
            "participants": deepcopy(session["participants"]),
            "availability_snapshot_ref": {
                "provider": availability["provider"],
                "revision": availability["revision"],
                "snapshot_hash": availability["snapshot_hash"],
            },
            "required_resource_kinds": list(self._RESOURCE_KINDS),
            "scope_hash": scope_hash,
            "action_ids": {},
        }
        session["appointment_revision_sequence"] = revision
        session["pending_appointment_revision"] = pending
        session["appointment_history"].append(deepcopy(pending))
        session["scheduling_state"] = "BOOKING_PENDING"
        self._save_session(envelope["tenant_id"], session["session_id"], version + 1, session)
        event_id = self._append_event(
            envelope["tenant_id"],
            "AppointmentRevisionProposed",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "appointment_revision": revision,
                "scope_hash": scope_hash,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "APPOINTMENT_REVISION_PROPOSED", "appointment_revision": revision},
        )

    def _handle_QueueSchedulingAction(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "application_case_id",
                "session_id",
                "appointment_revision",
                "resource_kind",
                "recipient_ref",
            },
            integer_keys={"appointment_revision"},
            string_keys={"application_case_id", "session_id", "resource_kind"},
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "约面动作字段或预约修订类型不符合封闭契约。",
            )
        loaded = self._load_session(envelope["tenant_id"], payload.get("session_id"))
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        _, session = loaded
        if payload["application_case_id"] != session["application_case_id"]:
            return self._rejected(
                envelope,
                "ACTION_SCOPE_MISMATCH",
                "约面动作声明的案件与会话归属不一致。",
            )
        if not self._case_allows_production(
            envelope["tenant_id"],
            session["application_case_id"],
            session["case_lifecycle_epoch"],
        ):
            return self._rejected(
                envelope,
                "CASE_PAUSED_OR_CLOSED",
                "案件控制事实已阻断生产性约面动作创建。",
            )
        pending = session.get("pending_appointment_revision")
        resource_kind = payload.get("resource_kind")
        if (
            session.get("scheduling_state") != "BOOKING_PENDING"
            or not pending
            or payload.get("appointment_revision") != pending["appointment_revision"]
            or resource_kind not in self._RESOURCE_KINDS
        ):
            return self._rejected(
                envelope, "STALE_APPOINTMENT_REVISION", "动作没有绑定当前预约修订。"
            )
        if resource_kind == "INVITATION_WRITE":
            recipient = payload.get("recipient_ref")
            allowed_recipients = {
                (
                    participant["tenant_id"],
                    participant["participant_id"],
                    participant["role"],
                )
                for participant in pending["participants"]
            }
            if (
                not isinstance(recipient, dict)
                or set(recipient) != {"tenant_id", "participant_id", "role"}
                or (
                    recipient.get("tenant_id"),
                    recipient.get("participant_id"),
                    recipient.get("role"),
                )
                not in allowed_recipients
                or recipient.get("tenant_id") != envelope["tenant_id"]
            ):
                return self._rejected(
                    envelope,
                    "RECIPIENT_SCOPE_MISMATCH",
                    "邀请收件人没有绑定当前租户和参与人清单。",
                )
        expected_action_id = _action_id(session["session_id"], pending["appointment_revision"], resource_kind)
        if envelope["aggregate_id"] != expected_action_id:
            return self._rejected(
                envelope, "AGGREGATE_TARGET_MISMATCH", "动作标识没有绑定当前预约修订。"
            )
        existing = self._load_action(envelope["tenant_id"], expected_action_id)
        if existing:
            return self._applied(
                envelope, [], {"effect": "ACTION_ALREADY_QUEUED", "action_id": expected_action_id}
            )
        action = {
            "action_id": expected_action_id,
            "application_case_id": session["application_case_id"],
            "session_id": session["session_id"],
            "case_lifecycle_epoch": session["case_lifecycle_epoch"],
            "appointment_revision": pending["appointment_revision"],
            "resource_kind": resource_kind,
            "state": "QUEUED",
            "scope_hash": pending["scope_hash"],
            "slot": deepcopy(pending["slot"]),
            "provider_idempotency_key": expected_action_id,
            "recipient_ref": deepcopy(payload.get("recipient_ref")),
            "attempt_count": 0,
            "receipt": None,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO scheduling_action_executions "
            "(tenant_id, action_id, application_case_id, action_key, version, state_json) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (
                envelope["tenant_id"],
                expected_action_id,
                session["application_case_id"],
                expected_action_id,
                _canonical(action),
            ),
        )
        event_id = self._append_event(
            envelope["tenant_id"],
            "AutomationActionRequested",
            expected_action_id,
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "appointment_revision": pending["appointment_revision"],
                "action_id": expected_action_id,
                "resource_kind": resource_kind,
            },
        )
        return self._applied(
            envelope, [event_id], {"effect": "ACTION_QUEUED", "action_id": expected_action_id}
        )

    def _handle_ExecuteSchedulingAction(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {"expected_action_version"},
            integer_keys={"expected_action_version"},
            string_keys=set(),
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "动作版本必须是封闭契约中的严格整数。",
            )
        loaded = self._load_action(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "约面动作不存在。")
        version, action = loaded
        if payload["expected_action_version"] != version:
            return self._rejected(envelope, "STALE_ACTION_VERSION", "动作版本已经变化。")
        if action["state"] == "OUTCOME_UNKNOWN":
            return self._rejected(
                envelope,
                "RECONCILIATION_REQUIRED",
                "Provider 写入结果不明，必须先按原业务幂等键对账。",
            )
        if action["state"] != "QUEUED":
            return self._rejected(envelope, "INVALID_TRANSITION", "动作已经结算。")
        if action.get("action_category") == "SAFETY_COMPENSATION":
            source_loaded = self._load_action(
                envelope["tenant_id"], action.get("source_action_id")
            )
            if not source_loaded:
                return self._rejected(
                    envelope,
                    "SAFETY_COMPENSATION_NOT_ALLOWED",
                    "待补偿日历资源已经不存在。",
                )
            source_version, source = source_loaded
            compensation_allowed = bool(
                not self._action_is_current_booking_resource(
                    envelope["tenant_id"], source
                )
                and (
                    source.get("state") == "COMPENSATION_REQUIRED"
                    or not self._case_allows_production(
                        envelope["tenant_id"],
                        source["application_case_id"],
                        source["case_lifecycle_epoch"],
                    )
                    or not self._action_targets_current_revision(
                        envelope["tenant_id"], source
                    )
                )
            )
            if (
                not compensation_allowed
                or source.get("state")
                not in {"SUCCEEDED", "COMPENSATION_REQUIRED"}
                or source.get("receipt") != action.get("source_receipt")
            ):
                return self._rejected(
                    envelope,
                    "SAFETY_COMPENSATION_NOT_ALLOWED",
                    "当前日历资源仍有效，不能执行安全补偿。",
                )
            receipt = self._adapters.calendar.cancel_event(action)
            action["attempt_count"] += 1
            action["state"] = "SUCCEEDED"
            action["receipt"] = receipt
            source["state"] = "COMPENSATED"
            source["compensation_action_id"] = action["action_id"]
            source["compensation_receipt"] = deepcopy(receipt)
            self._save_action(
                envelope["tenant_id"],
                source["action_id"],
                source_version + 1,
                source,
            )
            self._save_action(
                envelope["tenant_id"], action["action_id"], version + 1, action
            )
            event_id = self._append_event(
                envelope["tenant_id"],
                "AutomationActionSucceeded",
                action["action_id"],
                {
                    "application_case_id": action["application_case_id"],
                    "session_id": action["session_id"],
                    "action_id": action["action_id"],
                    "resource_kind": action["resource_kind"],
                    "action_category": "SAFETY_COMPENSATION",
                    "provider_receipt_id": receipt["provider_receipt_id"],
                },
            )
            return self._applied(
                envelope,
                [event_id],
                {
                    "effect": "SAFETY_COMPENSATION_RECORDED",
                    "action_id": action["action_id"],
                },
            )
        session_loaded = self._load_session(envelope["tenant_id"], action["session_id"])
        if not session_loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        _, session = session_loaded
        case_loaded = self._load_case(
            envelope["tenant_id"], action["application_case_id"]
        )
        if (
            not case_loaded
            or case_loaded[1].get("state") != "INTERVIEWING"
            or case_loaded[1].get("lifecycle_epoch")
            != action["case_lifecycle_epoch"]
            or (case_loaded[1].get("scheduling_control") or {}).get("status")
            == "PAUSED"
        ):
            action["attempt_count"] += 1
            action["state"] = "BLOCKED"
            action["blocked_reason"] = "CASE_PAUSED_OR_CLOSED"
            self._save_action(
                envelope["tenant_id"], action["action_id"], version + 1, action
            )
            event_id = self._append_event(
                envelope["tenant_id"],
                "AutomationActionBlocked",
                action["action_id"],
                {
                    "application_case_id": action["application_case_id"],
                    "session_id": action["session_id"],
                    "action_id": action["action_id"],
                    "reason": "CASE_PAUSED_OR_CLOSED",
                },
            )
            return self._applied(
                envelope,
                [event_id],
                {
                    "effect": "ACTION_BLOCKED",
                    "action_id": action["action_id"],
                    "reason": "CASE_PAUSED_OR_CLOSED",
                },
            )
        pending = session.get("pending_appointment_revision")
        if (
            session.get("scheduling_state") != "BOOKING_PENDING"
            or not pending
            or pending["appointment_revision"] != action["appointment_revision"]
            or pending["scope_hash"] != action["scope_hash"]
        ):
            return self._rejected(
                envelope, "STALE_APPOINTMENT_REVISION", "动作执行前预约修订已失效。"
            )
        operation = deepcopy(action)
        if action["resource_kind"] == "CALENDAR_EVENT":
            receipt = self._adapters.calendar.create_event(operation)
        elif action["resource_kind"] == "MEETING_RESOURCE":
            receipt = self._adapters.meeting.create_meeting(operation)
        else:
            receipt = self._adapters.invitation.write_invitation(operation)
        action["attempt_count"] += 1
        if receipt.get("outcome") == "SLOT_RESERVATION_CONFLICT":
            action["state"] = "CONFLICTED"
            action["blocked_reason"] = "SLOT_CONFLICT"
            self._save_action(
                envelope["tenant_id"], action["action_id"], version + 1, action
            )
            event_id = self._append_event(
                envelope["tenant_id"],
                "AutomationActionFailed",
                action["action_id"],
                {
                    "application_case_id": action["application_case_id"],
                    "session_id": action["session_id"],
                    "appointment_revision": action["appointment_revision"],
                    "action_id": action["action_id"],
                    "resource_kind": action["resource_kind"],
                    "error_code": "SLOT_CONFLICT",
                },
            )
            return self._applied(
                envelope,
                [event_id],
                {"effect": "SLOT_RESERVATION_CONFLICT", "action_id": action["action_id"]},
            )
        if receipt.get("outcome") == "UNKNOWN_AFTER_WRITE":
            action["state"] = "OUTCOME_UNKNOWN"
            action["receipt"] = None
            self._save_action(
                envelope["tenant_id"], action["action_id"], version + 1, action
            )
            event_id = self._append_event(
                envelope["tenant_id"],
                "AutomationActionOutcomeUnknown",
                action["action_id"],
                {
                    "application_case_id": action["application_case_id"],
                    "session_id": action["session_id"],
                    "appointment_revision": action["appointment_revision"],
                    "action_id": action["action_id"],
                    "resource_kind": action["resource_kind"],
                },
            )
            return self._applied(
                envelope,
                [event_id],
                {"effect": "ACTION_OUTCOME_UNKNOWN", "action_id": action["action_id"]},
            )
        action["state"] = "SUCCEEDED"
        action["receipt"] = receipt
        self._save_action(envelope["tenant_id"], action["action_id"], version + 1, action)
        event_id = self._append_event(
            envelope["tenant_id"],
            "AutomationActionSucceeded",
            action["action_id"],
            {
                "application_case_id": action["application_case_id"],
                "session_id": action["session_id"],
                "appointment_revision": action["appointment_revision"],
                "action_id": action["action_id"],
                "resource_kind": action["resource_kind"],
                "provider_receipt_id": receipt["provider_receipt_id"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "SYNTHETIC_RESOURCE_RECEIPT_RECORDED", "action_id": action["action_id"]},
        )

    def _handle_ReconcileSchedulingAction(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {"expected_action_version"},
            integer_keys={"expected_action_version"},
            string_keys=set(),
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "对账动作版本必须是封闭契约中的严格整数。",
            )
        loaded = self._load_action(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "约面动作不存在。")
        version, action = loaded
        if payload["expected_action_version"] != version:
            return self._rejected(envelope, "STALE_ACTION_VERSION", "动作版本已经变化。")
        if action["state"] != "OUTCOME_UNKNOWN":
            return self._rejected(
                envelope, "INVALID_TRANSITION", "只有结果不明的动作需要对账。"
            )
        if action["resource_kind"] != "CALENDAR_EVENT":
            return self._rejected(
                envelope, "RECONCILIATION_UNSUPPORTED", "当前纵切尚未支持该资源对账。"
            )
        receipt = self._adapters.calendar.reconcile_event(action)
        if not receipt:
            return self._rejected(
                envelope, "PROVIDER_EFFECT_NOT_FOUND", "Provider 对账未找到原动作效果。"
            )
        is_current = bool(
            self._action_is_current_booking_resource(
                envelope["tenant_id"], action
            )
            or (
                self._case_allows_production(
                    envelope["tenant_id"],
                    action["application_case_id"],
                    action["case_lifecycle_epoch"],
                )
                and self._action_targets_current_revision(
                    envelope["tenant_id"], action
                )
            )
        )
        action["state"] = "SUCCEEDED" if is_current else "COMPENSATION_REQUIRED"
        action["receipt"] = receipt
        self._save_action(
            envelope["tenant_id"], action["action_id"], version + 1, action
        )
        event_id = self._append_event(
            envelope["tenant_id"],
            "AutomationActionSucceeded" if is_current else "StaleProviderResourceObserved",
            action["action_id"],
            {
                "application_case_id": action["application_case_id"],
                "session_id": action["session_id"],
                "appointment_revision": action["appointment_revision"],
                "action_id": action["action_id"],
                "resource_kind": action["resource_kind"],
                "provider_receipt_id": receipt["provider_receipt_id"],
                "reconciled": True,
                "compensation_required": not is_current,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "ACTION_RECONCILED"
                if is_current
                else "STALE_ACTION_RECONCILED",
                "action_id": action["action_id"],
            },
        )

    def _handle_RecordSchedulingProviderObservation(
        self, envelope: JsonObject
    ) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_action_version",
                "provider_event_id",
                "provider_account_ref",
                "provider_idempotency_key",
                "receipt",
            },
            integer_keys={"expected_action_version"},
            string_keys={
                "provider_event_id",
                "provider_account_ref",
                "provider_idempotency_key",
            },
        ):
            return self._rejected(
                envelope,
                "PROVIDER_OBSERVATION_SCOPE_MISMATCH",
                "Provider 观察字段或动作版本不符合封闭契约。",
            )
        loaded = self._load_action(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(
                envelope,
                "PROVIDER_OBSERVATION_SCOPE_MISMATCH",
                "Provider 观察无法绑定当前租户动作。",
            )
        version, action = loaded
        if payload["expected_action_version"] != version:
            return self._rejected(envelope, "STALE_ACTION_VERSION", "动作版本已经变化。")
        event_id = payload["provider_event_id"]
        seen = action.setdefault("provider_observation_ids", [])
        if event_id in seen:
            return self._applied(
                envelope,
                [],
                {
                    "effect": "PROVIDER_OBSERVATION_ALREADY_RECORDED",
                    "action_id": action["action_id"],
                },
            )
        receipt = payload.get("receipt")
        if (
            action.get("state") not in {"OUTCOME_UNKNOWN", "SUCCEEDED"}
            or payload.get("provider_account_ref")
            != "calendar-account:tenant-synthetic"
            or payload.get("provider_idempotency_key")
            != action["provider_idempotency_key"]
            or action.get("resource_kind") != "CALENDAR_EVENT"
            or not _calendar_receipt_shape_is_valid(receipt)
            or receipt.get("appointment_revision")
            != action["appointment_revision"]
            or receipt.get("resource_kind") != action["resource_kind"]
            or receipt.get("scope_hash") != action["scope_hash"]
        ):
            return self._rejected(
                envelope,
                "PROVIDER_OBSERVATION_SCOPE_MISMATCH",
                "Provider 观察没有绑定当前动作与预约修订。",
            )
        existing_receipt = action.get("receipt")
        if (
            receipt["external_resource_revision"] < 1
            or (
                isinstance(existing_receipt, dict)
                and (
                    receipt["external_resource_ref"]
                    != existing_receipt.get("external_resource_ref")
                    or receipt["external_resource_revision"]
                    < existing_receipt.get("external_resource_revision", 0)
                )
            )
        ):
            return self._rejected(
                envelope,
                "STALE_PROVIDER_RECEIPT_REVISION",
                "Provider 回执修订落后或指向另一外部资源。",
            )
        if (
            isinstance(existing_receipt, dict)
            and receipt["external_resource_revision"]
            == existing_receipt.get("external_resource_revision")
            and receipt != existing_receipt
        ):
            return self._rejected(
                envelope,
                "PROVIDER_RECEIPT_CONFLICT",
                "同一 Provider 回执修订携带了不同内容。",
            )
        seen.append(event_id)
        is_current = bool(
            self._action_is_current_booking_resource(
                envelope["tenant_id"], action
            )
            or (
                self._case_allows_production(
                    envelope["tenant_id"],
                    action["application_case_id"],
                    action["case_lifecycle_epoch"],
                )
                and self._action_targets_current_revision(
                    envelope["tenant_id"], action
                )
            )
        )
        action["state"] = "SUCCEEDED" if is_current else "COMPENSATION_REQUIRED"
        action["receipt"] = deepcopy(receipt)
        self._save_action(
            envelope["tenant_id"], action["action_id"], version + 1, action
        )
        domain_event_id = self._append_event(
            envelope["tenant_id"],
            "AutomationActionSucceeded" if is_current else "StaleProviderResourceObserved",
            action["action_id"],
            {
                "application_case_id": action["application_case_id"],
                "session_id": action["session_id"],
                "appointment_revision": action["appointment_revision"],
                "action_id": action["action_id"],
                "resource_kind": action["resource_kind"],
                "provider_event_id": event_id,
                "provider_receipt_id": receipt["provider_receipt_id"],
                "compensation_required": not is_current,
            },
        )
        return self._applied(
            envelope,
            [domain_event_id],
            {
                "effect": "PROVIDER_OBSERVATION_RECORDED"
                if is_current
                else "STALE_PROVIDER_OBSERVATION_RECORDED",
                "action_id": action["action_id"],
            },
        )

    def _handle_SupersedeAppointmentRevision(
        self, envelope: JsonObject
    ) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_session_version",
                "expected_lifecycle_epoch",
                "appointment_revision",
                "reason",
            },
            integer_keys={
                "expected_session_version",
                "expected_lifecycle_epoch",
                "appointment_revision",
            },
            string_keys={"reason"},
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "替代预约修订命令不符合封闭契约。",
            )
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "BOOKING_PENDING")
        if error:
            return self._rejected(envelope, error[0], error[1])
        pending = session.get("pending_appointment_revision")
        if (
            not pending
            or payload["appointment_revision"] != pending["appointment_revision"]
        ):
            return self._rejected(
                envelope, "STALE_APPOINTMENT_REVISION", "待替代预约修订已不是当前修订。"
            )
        pending["status"] = "SUPERSEDED"
        pending["superseded_reason"] = payload["reason"]
        session["appointment_history"][-1] = deepcopy(pending)
        session["pending_appointment_revision"] = None
        session["scheduling_state"] = "PROPOSAL_OPEN"
        self._save_session(
            envelope["tenant_id"], session["session_id"], version + 1, session
        )
        event_id = self._append_event(
            envelope["tenant_id"],
            "AppointmentRevisionAborted",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "appointment_revision": pending["appointment_revision"],
                "reason": pending["superseded_reason"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "APPOINTMENT_REVISION_SUPERSEDED",
                "appointment_revision": pending["appointment_revision"],
            },
        )

    def _handle_CommitBooking(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_session_version",
                "expected_lifecycle_epoch",
                "appointment_revision",
            },
            integer_keys={
                "expected_session_version",
                "expected_lifecycle_epoch",
                "appointment_revision",
            },
            string_keys=set(),
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "提交 Booking 的预约修订必须是封闭契约中的严格整数。",
            )
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "BOOKING_PENDING")
        if error:
            return self._rejected(envelope, error[0], error[1])
        pending = session["pending_appointment_revision"]
        if payload["appointment_revision"] != pending["appointment_revision"]:
            return self._rejected(
                envelope, "STALE_APPOINTMENT_REVISION", "提交的预约修订不是当前待提交修订。"
            )
        receipts = {}
        for kind in self._RESOURCE_KINDS:
            action_id = _action_id(session["session_id"], pending["appointment_revision"], kind)
            if kind == "CALENDAR_EVENT":
                cancellation_id = "compensation:{}:cancel".format(action_id)
                cancellation = self._load_action(
                    envelope["tenant_id"], cancellation_id
                )
                if cancellation and cancellation[1].get("state") in {
                    "QUEUED",
                    "SUCCEEDED",
                }:
                    return self._rejected(
                        envelope,
                        "BOOKING_RESOURCE_CANCELLED",
                        "当前预约修订的日历资源已进入取消流程。",
                    )
            action_loaded = self._load_action(envelope["tenant_id"], action_id)
            if not action_loaded or action_loaded[1].get("state") != "SUCCEEDED":
                return self._rejected(
                    envelope, "BOOKING_RECEIPTS_INCOMPLETE", "当前预约修订的必需外部回执尚未齐全。"
                )
            action = action_loaded[1]
            receipt = action.get("receipt")
            if (
                not isinstance(receipt, dict)
                or receipt.get("appointment_revision") != pending["appointment_revision"]
                or receipt.get("resource_kind") != kind
                or receipt.get("scope_hash") != pending["scope_hash"]
            ):
                return self._rejected(
                    envelope, "BOOKING_RECEIPTS_INCOMPLETE", "外部回执与当前预约修订不一致。"
                )
            receipts[kind] = deepcopy(receipt)
        receipt_set_hash = _hash(receipts)
        booking = {
            "booking_id": "booking:{}:{}".format(
                session["session_id"], pending["appointment_revision"]
            ),
            "appointment_revision": pending["appointment_revision"],
            "slot": deepcopy(pending["slot"]),
            "receipt_set_hash": receipt_set_hash,
            "resource_receipts": receipts,
            "status": "CURRENT",
        }
        pending["status"] = "COMMITTED"
        session["appointment_history"][-1] = deepcopy(pending)
        session["current_booking"] = booking
        session["booking_history"].append(deepcopy(booking))
        session["pending_appointment_revision"] = None
        session["scheduling_state"] = "BOOKED"
        self._save_session(envelope["tenant_id"], session["session_id"], version + 1, session)
        event_id = self._append_event(
            envelope["tenant_id"],
            "InterviewBookingCommitted",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "appointment_revision": booking["appointment_revision"],
                "booking_id": booking["booking_id"],
                "booking_receipt_set_hash": receipt_set_hash,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "BOOKING_COMMITTED", "booking_id": booking["booking_id"]},
        )

    def _handle_PauseScope(self, envelope: JsonObject) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_case_version",
                "expected_lifecycle_epoch",
                "scope",
                "reason",
            },
            integer_keys={"expected_case_version", "expected_lifecycle_epoch"},
            string_keys={"scope", "reason"},
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "案件暂停命令不符合封闭契约。",
            )
        loaded = self._load_case(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        if (
            payload["expected_case_version"] != version
            or payload["expected_lifecycle_epoch"] != case.get("lifecycle_epoch")
            or payload["scope"] != "SCHEDULING_PRODUCTION"
        ):
            return self._rejected(
                envelope,
                "STALE_CASE_VERSION",
                "案件控制事实没有绑定当前案件版本。",
            )
        case["scheduling_control"] = {
            "status": "PAUSED",
            "scope": "SCHEDULING_PRODUCTION",
            "reason": payload.get("reason"),
        }
        case["lifecycle_epoch"] += 1
        self._save_case(
            envelope["tenant_id"], envelope["aggregate_id"], version + 1, case
        )
        event_id = self._append_event(
            envelope["tenant_id"],
            "CasePaused",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                "scope": "SCHEDULING_PRODUCTION",
                "new_lifecycle_epoch": case["lifecycle_epoch"],
                "reason": payload.get("reason"),
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "CASE_SCHEDULING_PAUSED", "case_version": version + 1},
        )

    def _handle_QueueSchedulingCompensation(
        self, envelope: JsonObject
    ) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "application_case_id",
                "session_id",
                "source_action_id",
                "source_action_version",
                "operation",
            },
            integer_keys={"source_action_version"},
            string_keys={
                "application_case_id",
                "session_id",
                "source_action_id",
                "operation",
            },
        ):
            return self._rejected(
                envelope,
                "INVALID_SCHEDULING_PAYLOAD",
                "安全补偿命令不符合封闭契约。",
            )
        source_loaded = self._load_action(
            envelope["tenant_id"], payload["source_action_id"]
        )
        if not source_loaded:
            return self._rejected(envelope, "NOT_FOUND", "待补偿动作不存在。")
        source_version, source = source_loaded
        expected_id = "compensation:{}:cancel".format(source["action_id"])
        compensation_allowed = bool(
            not self._action_is_current_booking_resource(
                envelope["tenant_id"], source
            )
            and (
                source.get("state") == "COMPENSATION_REQUIRED"
                or not self._case_allows_production(
                    envelope["tenant_id"],
                    source["application_case_id"],
                    source["case_lifecycle_epoch"],
                )
                or not self._action_targets_current_revision(
                    envelope["tenant_id"], source
                )
            )
        )
        if (
            envelope["aggregate_id"] != expected_id
            or payload["source_action_version"] != source_version
            or payload["operation"] != "CANCEL_CALENDAR_EVENT"
            or payload["application_case_id"] != source["application_case_id"]
            or payload["session_id"] != source["session_id"]
            or source.get("resource_kind") != "CALENDAR_EVENT"
            or source.get("state") not in {"SUCCEEDED", "COMPENSATION_REQUIRED"}
            or not isinstance(source.get("receipt"), dict)
            or not compensation_allowed
        ):
            return self._rejected(
                envelope,
                "SAFETY_COMPENSATION_NOT_ALLOWED",
                "补偿动作没有绑定已发生的日历资源。",
            )
        existing = self._load_action(envelope["tenant_id"], expected_id)
        if existing:
            return self._applied(
                envelope,
                [],
                {"effect": "ACTION_ALREADY_QUEUED", "action_id": expected_id},
            )
        action = {
            "action_id": expected_id,
            "application_case_id": source["application_case_id"],
            "session_id": source["session_id"],
            "case_lifecycle_epoch": source["case_lifecycle_epoch"],
            "appointment_revision": source["appointment_revision"],
            "resource_kind": "CALENDAR_EVENT_CANCEL",
            "action_category": "SAFETY_COMPENSATION",
            "state": "QUEUED",
            "scope_hash": source["scope_hash"],
            "provider_idempotency_key": expected_id,
            "source_action_id": source["action_id"],
            "source_receipt": deepcopy(source["receipt"]),
            "attempt_count": 0,
            "receipt": None,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO scheduling_action_executions "
            "(tenant_id, action_id, application_case_id, action_key, version, state_json) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (
                envelope["tenant_id"],
                expected_id,
                source["application_case_id"],
                expected_id,
                _canonical(action),
            ),
        )
        event_id = self._append_event(
            envelope["tenant_id"],
            "AutomationActionRequested",
            expected_id,
            {
                "application_case_id": source["application_case_id"],
                "session_id": source["session_id"],
                "action_id": expected_id,
                "action_category": "SAFETY_COMPENSATION",
                "source_action_id": source["action_id"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "ACTION_QUEUED", "action_id": expected_id},
        )

    def _handle_RecordRecordingNoticeDelivery(
        self, envelope: JsonObject
    ) -> JsonObject:
        payload = envelope["payload"]
        if not _closed_payload(
            payload,
            {
                "expected_session_version",
                "expected_lifecycle_epoch",
                "booking_id",
                "participant_ref",
                "purposes",
                "notice_version",
                "channel",
                "receipt_ref",
            },
            integer_keys={"expected_session_version", "expected_lifecycle_epoch"},
            string_keys={"booking_id", "notice_version", "channel", "receipt_ref"},
        ):
            return self._rejected(
                envelope,
                "NOTICE_DELIVERY_SCOPE_MISMATCH",
                "录制告知回执没有绑定当前会话、参与人和告知版本。",
            )
        loaded = self._load_session(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "面试会话不存在。")
        version, session = loaded
        error = self._session_gate(envelope, version, session, "BOOKED")
        if error:
            return self._rejected(envelope, error[0], error[1])
        participant = payload.get("participant_ref")
        allowed = {
            (
                item["tenant_id"],
                item["participant_id"],
                item["role"],
            )
            for item in session["participants"]
        }
        if (
            payload.get("booking_id") != session["current_booking"]["booking_id"]
            or not isinstance(participant, dict)
            or set(participant) != {"tenant_id", "participant_id", "role"}
            or (
                participant.get("tenant_id"),
                participant.get("participant_id"),
                participant.get("role"),
            )
            not in allowed
            or participant.get("tenant_id") != envelope["tenant_id"]
            or payload.get("purposes") != ["INTERVIEW_RECORDING"]
            or payload.get("notice_version") != "recording-notice:v1"
            or payload.get("channel") != "COORDINATION_PAGE"
            or not isinstance(payload.get("receipt_ref"), str)
        ):
            return self._rejected(
                envelope,
                "NOTICE_DELIVERY_SCOPE_MISMATCH",
                "录制告知回执没有绑定当前会话、参与人和告知版本。",
        )
        delivery = {
            "participant_ref": {
                "tenant_id": participant["tenant_id"],
                "participant_id": participant["participant_id"],
                "role": participant["role"],
            },
            "purposes": ["INTERVIEW_RECORDING"],
            "notice_version": payload["notice_version"],
            "channel": payload["channel"],
            "receipt_ref": payload["receipt_ref"],
            "consent_created": False,
        }
        session["recording_notice_deliveries"].append(delivery)
        self._save_session(
            envelope["tenant_id"], session["session_id"], version + 1, session
        )
        event_id = self._append_event(
            envelope["tenant_id"],
            "RecordingNoticeDelivered",
            session["session_id"],
            {
                "application_case_id": session["application_case_id"],
                "session_id": session["session_id"],
                "participant_id": participant["participant_id"],
                "purposes": ["INTERVIEW_RECORDING"],
                "notice_version": payload["notice_version"],
                "channel": payload["channel"],
                "receipt_ref": payload["receipt_ref"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "RECORDING_NOTICE_DELIVERY_RECORDED", "consent_created": False},
        )

    def _synthetic_adapters_are_current(self) -> bool:
        try:
            current = (
                self._adapters,
                self._adapters.calendar,
                self._adapters.meeting,
                self._adapters.invitation,
            )
        except (AttributeError, TypeError):
            return False
        expected = getattr(self, "_adapter_identity", None)
        return bool(
            isinstance(expected, tuple)
            and len(expected) == 4
            and all(current_item is expected_item for current_item, expected_item in zip(current, expected))
            and all(
                getattr(item, "_synthetic_capability", None)
                is _SYNTHETIC_ADAPTER_CAPABILITY
                for item in current
            )
        )

    def _require_synthetic_adapters(self) -> None:
        if not self._synthetic_adapters_are_current():
            raise RuntimeError(
                "synthetic adapter identity changed; projection claim is unavailable"
            )

    def _case_allows_production(
        self, tenant_id: str, application_case_id: str, lifecycle_epoch: int
    ) -> bool:
        case_loaded = self._load_case(tenant_id, application_case_id)
        return bool(
            case_loaded
            and case_loaded[1].get("state") == "INTERVIEWING"
            and case_loaded[1].get("lifecycle_epoch") == lifecycle_epoch
            and (case_loaded[1].get("scheduling_control") or {}).get("status")
            != "PAUSED"
        )

    def _action_targets_current_revision(
        self, tenant_id: str, action: JsonObject
    ) -> bool:
        session_loaded = self._load_session(tenant_id, action.get("session_id"))
        if not session_loaded:
            return False
        session = session_loaded[1]
        pending = session.get("pending_appointment_revision")
        return bool(
            session.get("application_case_id") == action.get("application_case_id")
            and session.get("scheduling_state") == "BOOKING_PENDING"
            and pending
            and pending.get("appointment_revision")
            == action.get("appointment_revision")
            and pending.get("scope_hash") == action.get("scope_hash")
        )

    def _action_is_current_booking_resource(
        self, tenant_id: str, action: JsonObject
    ) -> bool:
        session_loaded = self._load_session(tenant_id, action.get("session_id"))
        if not session_loaded:
            return False
        session = session_loaded[1]
        booking = session.get("current_booking")
        if (
            session.get("scheduling_state") != "BOOKED"
            or not isinstance(booking, dict)
            or booking.get("status") != "CURRENT"
            or booking.get("appointment_revision")
            != action.get("appointment_revision")
        ):
            return False
        booking_receipt = (booking.get("resource_receipts") or {}).get(
            action.get("resource_kind")
        )
        action_receipt = action.get("receipt")
        return bool(
            isinstance(booking_receipt, dict)
            and isinstance(action_receipt, dict)
            and booking_receipt.get("scope_hash") == action.get("scope_hash")
            and booking_receipt.get("external_resource_ref")
            == action_receipt.get("external_resource_ref")
        )

    def _session_gate(
        self,
        envelope: JsonObject,
        version: int,
        session: JsonObject,
        expected_state: str,
    ) -> Optional[Tuple[str, str]]:
        payload = envelope["payload"]
        if (
            type(payload.get("expected_session_version")) is not int
            or type(payload.get("expected_lifecycle_epoch")) is not int
        ):
            return (
                "INVALID_SCHEDULING_PAYLOAD",
                "约面命令版本必须是严格整数。",
            )
        if payload.get("expected_session_version") != version:
            return "STALE_SESSION_VERSION", "面试会话版本已经变化。"
        if payload.get("expected_lifecycle_epoch") != session["case_lifecycle_epoch"]:
            return "STALE_CASE_VERSION", "申请案件生命周期代次已经变化。"
        case_loaded = self._load_case(envelope["tenant_id"], session["application_case_id"])
        if (
            not case_loaded
            or case_loaded[1].get("state") != "INTERVIEWING"
            or case_loaded[1].get("lifecycle_epoch")
            != session["case_lifecycle_epoch"]
            or (case_loaded[1].get("scheduling_control") or {}).get("status")
            == "PAUSED"
        ):
            return (
                "CASE_PAUSED_OR_CLOSED",
                "案件控制事实已阻断生产性约面状态迁移。",
            )
        if session.get("scheduling_state") != expected_state:
            return "INVALID_TRANSITION", "面试会话不在该命令要求的当前状态。"
        return None

    def _load_session(self, tenant_id: str, session_id: Any) -> Optional[Tuple[int, JsonObject]]:
        if not isinstance(session_id, str):
            return None
        row = self._db.execute(
            "SELECT version, state_json FROM interview_sessions "
            "WHERE tenant_id = ? AND session_id = ?",
            (tenant_id, session_id),
        ).fetchone()
        if not row:
            return None
        return row["version"], json.loads(row["state_json"])

    def _save_session(self, tenant_id: str, session_id: str, version: int, state: JsonObject) -> None:
        self._db.execute(
            "UPDATE interview_sessions SET version = ?, state_json = ? "
            "WHERE tenant_id = ? AND session_id = ?",
            (version, _canonical(state), tenant_id, session_id),
        )

    def _load_action(self, tenant_id: str, action_id: Any) -> Optional[Tuple[int, JsonObject]]:
        if not isinstance(action_id, str):
            return None
        row = self._db.execute(
            "SELECT version, state_json FROM scheduling_action_executions "
            "WHERE tenant_id = ? AND action_id = ?",
            (tenant_id, action_id),
        ).fetchone()
        if not row:
            return None
        return row["version"], json.loads(row["state_json"])

    def _save_action(self, tenant_id: str, action_id: str, version: int, state: JsonObject) -> None:
        self._db.execute(
            "UPDATE scheduling_action_executions SET version = ?, state_json = ? "
            "WHERE tenant_id = ? AND action_id = ?",
            (version, _canonical(state), tenant_id, action_id),
        )

    def _install_scheduling_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS interview_sessions (
                tenant_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, session_id)
            );
            CREATE TABLE IF NOT EXISTS scheduling_action_executions (
                tenant_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                action_key TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, action_id),
                UNIQUE (tenant_id, action_key)
            );
            """
        )
        self._db.commit()


def _action_id(session_id: str, appointment_revision: int, resource_kind: str) -> str:
    return "action:{}:{}:{}".format(
        session_id, appointment_revision, resource_kind.lower()
    )


def _closed_payload(
    payload: Any,
    keys: set,
    *,
    integer_keys: set,
    string_keys: set,
) -> bool:
    return bool(
        isinstance(payload, dict)
        and set(payload) == keys
        and all(type(payload.get(key)) is int for key in integer_keys)
        and all(
            isinstance(payload.get(key), str) and bool(payload.get(key))
            for key in string_keys
        )
    )


def _calendar_receipt_shape_is_valid(receipt: Any) -> bool:
    if not isinstance(receipt, dict):
        return False
    expected_keys = {
        "provider",
        "provider_receipt_id",
        "external_resource_ref",
        "external_resource_revision",
        "resource_kind",
        "appointment_revision",
        "scope_hash",
        "synthetic_only",
    }
    return bool(
        set(receipt) == expected_keys
        and all(
            isinstance(receipt.get(key), str) and bool(receipt.get(key))
            for key in (
                "provider",
                "provider_receipt_id",
                "external_resource_ref",
                "resource_kind",
                "scope_hash",
            )
        )
        and type(receipt.get("external_resource_revision")) is int
        and type(receipt.get("appointment_revision")) is int
        and receipt.get("synthetic_only") is True
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc
    )
