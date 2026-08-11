"""Deterministic, synthetic-only G1a recruiting control plane.

This module deliberately uses only the Python standard library.  It proves a
small set of control semantics with synthetic data; it is not a production
transport, identity provider, connector, or model runtime.
"""

import copy
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ._contract_validation import ContractValidationError, validate_or_raise


JsonObject = Dict[str, Any]

_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CONTROL_SCHEMA = _REPOSITORY_ROOT / "contracts" / "recruiting-agent-g1a-control.schema.json"
_EVENT_SCHEMA = _REPOSITORY_ROOT / "contracts" / "recruiting-agent-g1a-event.schema.json"


class RecruitingCaseControl:
    """Deep module exposing one write interface and one read interface."""

    _SUPPORTED = {
        "RegisterCompletedSessionFact",
        "ImportCompletedInterview",
        "RegisterEvidenceArtifact",
        "RecordTranscriptOutcome",
        "RecordEvaluationDraftGenerated",
        "PublishEvaluationForReview",
        "SubmitEvaluationReview",
        "ReachConfirmationQuorum",
        "RecordRoundDecision",
        "PauseScope",
        "ResumeScope",
        "RequestExternalAction",
        "RecordExternalActionResult",
    }

    _WORKFLOW_COMMANDS = {
        "RegisterCompletedSessionFact",
        "ImportCompletedInterview",
        "PublishEvaluationForReview",
        "ReachConfirmationQuorum",
        "RequestExternalAction",
    }
    _EVIDENCE_COMMANDS = {
        "RegisterEvidenceArtifact",
        "RecordTranscriptOutcome",
        "RecordEvaluationDraftGenerated",
    }
    _RIGHTS_ACTION_TYPES = {
        "DELETE_DERIVED_DATA",
        "COMPLETE_DATA_DELETION",
        "FULFILL_PRIVACY_REQUEST",
    }
    _TARGET_AGGREGATE_BY_COMMAND = {
        "RegisterCompletedSessionFact": "INTERVIEW_SESSION",
        "ImportCompletedInterview": "INTERVIEW_ROUND",
        "RegisterEvidenceArtifact": "INTERVIEW_SESSION",
        "RecordTranscriptOutcome": "INTERVIEW_SESSION",
        "RecordEvaluationDraftGenerated": "EVALUATION_PACKAGE",
        "PublishEvaluationForReview": "INTERVIEW_ROUND",
        "SubmitEvaluationReview": "EVALUATION_PACKAGE",
        "ReachConfirmationQuorum": "INTERVIEW_ROUND",
        "RecordRoundDecision": "INTERVIEW_ROUND",
        "PauseScope": "APPLICATION_CASE",
        "ResumeScope": "APPLICATION_CASE",
        "RequestExternalAction": "ACTION_EXECUTION",
        "RecordExternalActionResult": "ACTION_EXECUTION",
    }

    def __init__(self, connection: sqlite3.Connection):
        self._db = connection
        self._db.row_factory = sqlite3.Row
        self._create_schema()

    def submit(self, envelope: JsonObject) -> JsonObject:
        """Submit one command intent and atomically commit its observable facts."""

        try:
            validate_or_raise(envelope, _CONTROL_SCHEMA)
        except (ContractValidationError, ValueError) as error:
            return self._rejected(envelope, "SCHEMA_INVALID", "command.schema_invalid")

        canonical_hash = self._canonical_command_hash(envelope)
        tenant_id = envelope["tenant_id"]
        idempotency_key = envelope["idempotency_key"]

        self._db.execute("BEGIN IMMEDIATE")
        try:
            preflight_error = self._validate_authority_and_scope(envelope)
            if preflight_error:
                code, message = preflight_error
                self._db.rollback()
                return self._rejected_result(
                    envelope, code, message, retryable=False
                )

            prior = self._db.execute(
                "SELECT payload_hash, command_id, result_json FROM command_results "
                "WHERE tenant_id = ? AND idempotency_key = ?",
                (tenant_id, idempotency_key),
            ).fetchone()
            if prior:
                if prior["payload_hash"] != canonical_hash:
                    result = self._rejected_result(
                        envelope,
                        "IDEMPOTENCY_KEY_REUSED",
                        "command.idempotency_key_reused",
                        retryable=False,
                    )
                    self._db.commit()
                    return result
                first = json.loads(prior["result_json"])
                if first["status"] == "REJECTED":
                    self._db.commit()
                    return first
                replayed = copy.deepcopy(first)
                replayed["status"] = "REPLAYED"
                replayed["replayed_of_command_id"] = prior["command_id"]
                replayed["command_id"] = envelope["command_id"]
                replayed["completed_at"] = envelope["requested_at"]
                self._validate_result(replayed)
                self._db.commit()
                return replayed

            reused_command_id = self._db.execute(
                "SELECT idempotency_key FROM command_results "
                "WHERE tenant_id = ? AND command_id = ?",
                (tenant_id, envelope["command_id"]),
            ).fetchone()
            if reused_command_id:
                result = self._rejected_result(
                    envelope,
                    "IDEMPOTENCY_KEY_REUSED",
                    "command.command_id_reused_with_another_key",
                    retryable=False,
                )
                self._db.commit()
                return result

            result = self._apply(envelope)
            self._db.execute(
                "INSERT INTO command_results "
                "(tenant_id, idempotency_key, payload_hash, command_id, result_json) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    tenant_id,
                    idempotency_key,
                    canonical_hash,
                    envelope["command_id"],
                    self._json(result),
                ),
            )
            self._db.commit()
            return result
        except Exception:
            self._db.rollback()
            raise

    def read(self, request: JsonObject) -> JsonObject:
        """Return a side-effect-free projection derived from current facts."""

        tenant_id = request.get("tenant_id")
        case_id = request.get("application_case_id")
        actor = request.get("actor_context")
        if not tenant_id or not case_id or not isinstance(actor, dict):
            raise ValueError(
                "tenant_id, application_case_id and actor_context are required"
            )
        read_error = self._validate_projection_actor(actor, tenant_id, case_id)
        if read_error:
            raise PermissionError(read_error)
        case_fact = self._load_aggregate(
            tenant_id, "APPLICATION_CASE", case_id, case_id
        )
        if not case_fact:
            raise KeyError("application case is not visible in the requested scope")

        rows = self._db.execute(
            "SELECT aggregate_type, aggregate_id, version, lifecycle_epoch, state_json "
            "FROM aggregates WHERE tenant_id = ? AND application_case_id = ?",
            (tenant_id, case_id),
        ).fetchall()
        cases: Dict[str, JsonObject] = {}
        rounds: Dict[str, JsonObject] = {}
        sessions: Dict[str, JsonObject] = {}
        evaluations: Dict[str, JsonObject] = {}
        actions: Dict[str, JsonObject] = {}
        for row in rows:
            state = json.loads(row["state_json"])
            projection = copy.deepcopy(state)
            self._redact_projection_state(
                projection, row["aggregate_type"], actor["role"]
            )
            projection["version"] = row["version"]
            projection["lifecycle_epoch"] = row["lifecycle_epoch"]
            aggregate_type = row["aggregate_type"]
            if aggregate_type == "APPLICATION_CASE":
                cases[row["aggregate_id"]] = projection
            elif aggregate_type == "INTERVIEW_ROUND":
                rounds[row["aggregate_id"]] = projection
            elif aggregate_type == "INTERVIEW_SESSION":
                sessions[row["aggregate_id"]] = projection
            elif aggregate_type == "EVALUATION_PACKAGE":
                evaluations[row["aggregate_id"]] = projection
            elif aggregate_type == "ACTION_EXECUTION":
                outbox_state = self._outbox_state_for_scope(
                    tenant_id, case_id, row["aggregate_id"]
                )
                projection["outbox_state"] = outbox_state
                if outbox_state == "SUPPRESSED":
                    projection["domain_state_before_control"] = projection.get(
                        "state"
                    )
                    projection["state"] = "SUPPRESSED"
                actions[row["aggregate_id"]] = projection

        event_rows = self._db.execute(
            "SELECT event_type, event_json FROM domain_events "
            "WHERE tenant_id = ? AND application_case_id = ? "
            "ORDER BY rowid",
            (tenant_id, case_id),
        ).fetchall()
        event_types = [row["event_type"] for row in event_rows]
        event_envelopes = (
            [json.loads(row["event_json"]) for row in event_rows]
            if actor["role"] in {"QUALITY_REVIEWER", "PRIVACY_ADMIN"}
            else []
        )
        outbox_pending_count = self._db.execute(
            "SELECT COUNT(*) FROM outbox WHERE tenant_id = ? AND application_case_id = ? "
            "AND state = 'PENDING'",
            (tenant_id, case_id),
        ).fetchone()[0]
        outbox_rows = self._db.execute(
            "SELECT state, COUNT(*) AS count FROM outbox "
            "WHERE tenant_id = ? AND application_case_id = ? GROUP BY state",
            (tenant_id, case_id),
        ).fetchall()
        return {
            "tenant_id": tenant_id,
            "application_case_id": case_id,
            "case": cases.get(case_id),
            "rounds": rounds,
            "sessions": sessions,
            "evaluations": evaluations,
            "actions": actions,
            "event_count": len(event_types),
            "event_types": event_types,
            "event_envelopes": event_envelopes,
            "outbox_pending_count": outbox_pending_count,
            "outbox_state_counts": {
                row["state"]: row["count"] for row in outbox_rows
            },
        }

    def _apply(self, envelope: JsonObject) -> JsonObject:
        command_type = envelope["command_type"]
        if command_type not in self._SUPPORTED:
            return self._rejected_result(
                envelope,
                "INVALID_TRANSITION",
                "command.not_implemented_in_synthetic_slice",
                retryable=False,
            )

        target = envelope["target"]
        current = self._load_aggregate(
            envelope["tenant_id"],
            target["aggregate_type"],
            target["aggregate_id"],
            target["application_case_id"],
        )
        case_fact = self._load_aggregate(
            envelope["tenant_id"],
            "APPLICATION_CASE",
            target["application_case_id"],
            target["application_case_id"],
        )
        current_version = current[0] if current else 0
        current_epoch = case_fact[1]
        current_state = current[2] if current else {}

        if envelope["expected_aggregate_version"] != current_version:
            return self._rejected_result(
                envelope,
                "VERSION_CONFLICT",
                "command.version_conflict",
                retryable=True,
                current_version=current_version,
            )
        if envelope["lifecycle_epoch"] != current_epoch:
            return self._rejected_result(
                envelope,
                "LIFECYCLE_EPOCH_MISMATCH",
                "command.lifecycle_epoch_mismatch",
                retryable=False,
                current_version=current_version,
            )
        if current and current[1] != current_epoch:
            return self._rejected_result(
                envelope,
                "LIFECYCLE_EPOCH_MISMATCH",
                "command.child_aggregate_epoch_is_stale",
                retryable=False,
                current_version=current_version,
            )
        if (
            self._case_is_stopped(envelope)
            and command_type != "ResumeScope"
            and not self._is_pause_exempt(envelope, current_state)
        ):
            return self._rejected_result(
                envelope,
                "CASE_PAUSED_OR_CLOSED",
                "command.case_paused",
                retryable=False,
                current_version=current_version,
            )

        handler = getattr(self, "_handle_" + command_type)
        outcome = handler(envelope, copy.deepcopy(current_state))
        if outcome[0] is None:
            code, message = outcome[2]
            return self._rejected_result(
                envelope,
                code,
                message,
                retryable=False,
                current_version=current_version,
            )

        new_state, event_specs, _ = outcome
        new_version = current_version + 1
        self._store_aggregate(envelope, new_version, new_state)
        event_ids = self._append_events(envelope, new_version, event_specs)
        requested_action_ids: List[str] = []
        if command_type == "RequestExternalAction":
            self._enqueue_action(envelope)
            requested_action_ids.append(envelope["payload"]["action_id"])
        elif command_type == "RecordExternalActionResult":
            self._complete_outbox_action(envelope)
        elif command_type == "PauseScope":
            self._suppress_pending_outbox(envelope)
        return self._applied_result(envelope, new_version, event_ids, requested_action_ids)

    def _handle_RegisterCompletedSessionFact(
        self, envelope: JsonObject, state: JsonObject
    ) -> Tuple[Optional[JsonObject], List[Tuple[str, JsonObject]], Optional[Tuple[str, str]]]:
        payload = envelope["payload"]
        target = envelope["target"]
        if state:
            return None, [], ("INVALID_TRANSITION", "session.end_fact_already_registered")
        if payload["interview_session_id"] != target.get("interview_session_id"):
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "session.reference_mismatch")
        round_fact = self._load_aggregate(
            envelope["tenant_id"],
            "INTERVIEW_ROUND",
            payload["interview_round_id"],
            target["application_case_id"],
        )
        if not round_fact:
            return None, [], (
                "REFERENCE_SCOPE_MISMATCH",
                "session.round_not_bound_to_case",
            )
        if round_fact[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "session.round_epoch_is_stale",
            )
        new_state = {
            "state": "ENDED",
            "interview_round_id": payload["interview_round_id"],
            "ended_at": payload["ended_at"],
            "participant_snapshot_ref": payload["participant_snapshot_ref"],
            "occurrence_proof_ref": payload["occurrence_proof_ref"],
            "observed_start_missing": payload["observed_start_missing"],
            "artifacts": [],
            "transcripts": [],
        }
        event = {
            "interview_round_id": payload["interview_round_id"],
            "interview_session_id": payload["interview_session_id"],
            "ended_at": payload["ended_at"],
            "outcome": "COMPLETED",
            "observed_start_missing": payload["observed_start_missing"],
            "participant_snapshot_ref": payload["participant_snapshot_ref"],
        }
        return new_state, [("InterviewSessionEnded", event)], None

    def _handle_ImportCompletedInterview(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state.get("state") not in {"PLANNED", "READY_TO_SCHEDULE"}:
            return None, [], ("INVALID_TRANSITION", "round.not_importable")
        session = self._load_aggregate(
            envelope["tenant_id"],
            "INTERVIEW_SESSION",
            payload["interview_session_id"],
            envelope["target"]["application_case_id"],
        )
        if not session or session[2].get("state") != "ENDED":
            return None, [], ("BINDING_NOT_FOUND", "round.ended_session_not_found")
        if session[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "round.ended_session_epoch_is_stale",
            )
        if session[2].get("interview_round_id") != envelope["target"].get("interview_round_id"):
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "round.session_scope_mismatch")
        if not self._consent_refs_are_current(
            envelope, payload.get("consent_snapshot_refs", [])
        ):
            return None, [], ("CONSENT_MISSING", "round.current_consent_missing")
        if not self._version_pin_is_current(envelope, payload["scorecard_pin"]):
            return None, [], ("SCORECARD_MISSING", "round.scorecard_pin_invalid")
        source_artifact_binding = {
            "content_ref": payload["source_artifact_ref"],
            "sha256": payload["source_artifact_sha256"],
        }
        if not self._scoped_reference_is_current(
            envelope, "source_artifact_binding", source_artifact_binding
        ):
            return None, [], (
                "BINDING_NOT_FOUND",
                "round.source_artifact_binding_invalid",
            )
        from_round_state = state["state"]
        state["state"] = "EVIDENCE_PROCESSING"
        state["imported_session_ids"] = [payload["interview_session_id"]]
        state["scorecard_pin"] = payload["scorecard_pin"]
        state["evidence_route"] = payload["evidence_route"]
        state["source_artifact_ref"] = payload["source_artifact_ref"]
        state["source_artifact_sha256"] = payload["source_artifact_sha256"]
        event = {
            "interview_round_id": envelope["target"]["interview_round_id"],
            "interview_session_id": payload["interview_session_id"],
            "from_round_state": from_round_state,
            "to_round_state": "EVIDENCE_PROCESSING",
            "scorecard_version": payload["scorecard_pin"]["version"],
            "source_artifact_sha256": payload["source_artifact_sha256"],
        }
        return state, [("CompletedInterviewImported", event)], None

    def _handle_RegisterEvidenceArtifact(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state.get("state") != "ENDED":
            return None, [], ("INVALID_TRANSITION", "artifact.session_not_ended")
        if not self._session_round_is_processing_evidence(envelope, state):
            return None, [], (
                "INVALID_TRANSITION",
                "artifact.round_not_processing",
            )
        if not self._consent_refs_are_current(
            envelope, payload.get("consent_snapshot_refs", [])
        ):
            return None, [], ("CONSENT_MISSING", "artifact.current_consent_missing")
        source_artifact_binding = {
            "content_ref": payload["content_ref"],
            "sha256": payload["sha256"],
        }
        if not self._scoped_reference_is_current(
            envelope, "source_artifact_binding", source_artifact_binding
        ):
            return None, [], (
                "BINDING_NOT_FOUND",
                "artifact.content_binding_not_registered",
            )
        artifacts = state.setdefault("artifacts", [])
        key = (payload["artifact_id"], payload["artifact_version"])
        if any((item["artifact_id"], item["artifact_version"]) == key for item in artifacts):
            return None, [], ("ARTIFACT_ALREADY_BOUND", "artifact.already_bound")
        artifacts.append(
            {
                "artifact_id": payload["artifact_id"],
                "artifact_version": payload["artifact_version"],
                "artifact_type": payload["artifact_type"],
                "sha256": payload["sha256"],
                "content_ref": payload["content_ref"],
            }
        )
        event = {
            "interview_session_id": payload["interview_session_id"],
            "artifact_id": payload["artifact_id"],
            "artifact_type": payload["artifact_type"],
            "artifact_version": payload["artifact_version"],
            "checksum": payload["sha256"],
            "consent_snapshot_ref": payload["consent_snapshot_refs"][0][
                "receipt_ref"
            ],
            "retention_class": payload["retention_class"],
        }
        return state, [("RecordingAssetAvailable", event)], None

    def _handle_RecordTranscriptOutcome(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if not self._session_round_is_processing_evidence(envelope, state):
            return None, [], (
                "INVALID_TRANSITION",
                "transcript.round_not_processing",
            )
        artifact_exists = any(
            item["artifact_id"] == payload["artifact_id"]
            and item["artifact_version"] == payload["artifact_version"]
            for item in state.get("artifacts", [])
        )
        if not artifact_exists:
            return None, [], ("BINDING_NOT_FOUND", "transcript.artifact_not_found")
        if payload["outcome"] != "COMPLETED":
            return None, [], ("AUDIO_LOW_QUALITY", "transcript.rejected")
        if not any(item["name"] == "speaker_confidence" and item["value"] >= 0.9 for item in payload["quality_signals"]):
            return None, [], ("SPEAKER_UNCERTAIN", "transcript.speaker_uncertain")
        transcripts = state.setdefault("transcripts", [])
        current_versions = [
            item["transcript_version"]
            for item in transcripts
            if item["transcript_id"] == payload["transcript_id"]
        ]
        if current_versions and payload["transcript_version"] <= max(current_versions):
            return None, [], (
                "EXTERNAL_REVISION_STALE",
                "transcript.version_not_monotonic",
            )
        transcripts.append(
            {
                "transcript_id": payload["transcript_id"],
                "transcript_version": payload["transcript_version"],
                "artifact_id": payload["artifact_id"],
                "artifact_version": payload["artifact_version"],
                "segments_ref": payload["segments_ref"],
                "quality_signals": payload["quality_signals"],
            }
        )
        event = {
            "transcript_id": payload["transcript_id"],
            "transcript_version": payload["transcript_version"],
            "artifact_id": payload["artifact_id"],
            "artifact_version": payload["artifact_version"],
            "language": payload["language"],
            "speaker_map_version": payload["speaker_map_version"],
            "segments_ref": payload["segments_ref"],
            "quality_manifest_ref": "quality-manifest:" + payload["run_id"],
        }
        return state, [("TranscriptReady", event)], None

    def _handle_RecordEvaluationDraftGenerated(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state:
            return None, [], ("INVALID_TRANSITION", "evaluation.already_exists")
        round_fact = self._load_aggregate(
            envelope["tenant_id"],
            "INTERVIEW_ROUND",
            payload["interview_round_id"],
            envelope["target"]["application_case_id"],
        )
        if not round_fact or round_fact[2].get("state") != "EVIDENCE_PROCESSING":
            return None, [], ("INVALID_TRANSITION", "evaluation.round_not_processing")
        if round_fact[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "evaluation.round_epoch_is_stale",
            )
        if not self._round_has_transcript(
            envelope["tenant_id"],
            envelope["target"]["application_case_id"],
            payload["interview_round_id"],
            envelope["lifecycle_epoch"],
        ):
            return None, [], ("BINDING_NOT_FOUND", "evaluation.transcript_missing")
        if not self._version_pin_is_current(envelope, payload["scorecard_pin"]):
            return None, [], ("SCORECARD_MISSING", "evaluation.scorecard_pin_invalid")
        if not self._version_pin_is_current(envelope, payload["profile_pin"]):
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "evaluation.profile_pin_invalid")
        if not self._scoped_reference_is_current(
            envelope, "evidence_set_hash", payload["evidence_set_hash"]
        ):
            return None, [], ("EVIDENCE_VALIDATION_FAILED", "evaluation.evidence_set_hash_invalid")
        if payload["supported_critical_claim_count"] != payload["critical_claim_count"]:
            return None, [], ("EVIDENCE_VALIDATION_FAILED", "evaluation.critical_claim_unsupported")
        if payload["decision_fields_present"] or payload["tool_execution_count"]:
            return None, [], ("EVIDENCE_VALIDATION_FAILED", "evaluation.forbidden_output")
        new_state = {
            "state": "DRAFT",
            "interview_round_id": payload["interview_round_id"],
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "evidence_set_hash": payload["evidence_set_hash"],
            "scorecard_pin": payload["scorecard_pin"],
            "profile_pin": payload["profile_pin"],
            "draft_ref": payload["draft_ref"],
            "claim_manifest_ref": payload["claim_manifest_ref"],
            "review": None,
        }
        event = {
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "evidence_set_hash": payload["evidence_set_hash"],
            "scorecard_version": payload["scorecard_pin"]["version"],
            "profile_version": payload["profile_pin"]["version"],
            "model_version": payload["model_version"],
            "prompt_version": payload["prompt_version"],
            "template_version": payload["template_version"],
            "claim_manifest_ref": payload["claim_manifest_ref"],
        }
        return new_state, [("EvaluationDraftGenerated", event)], None

    def _handle_PublishEvaluationForReview(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state.get("state") != "EVIDENCE_PROCESSING":
            return None, [], ("INVALID_TRANSITION", "round.not_ready_for_review")
        evaluation = self._load_aggregate(
            envelope["tenant_id"],
            "EVALUATION_PACKAGE",
            payload["evaluation_id"],
            envelope["target"]["application_case_id"],
        )
        if not evaluation:
            return None, [], ("BINDING_NOT_FOUND", "round.evaluation_draft_missing")
        if evaluation[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "round.evaluation_epoch_is_stale",
            )
        if evaluation[2].get("interview_round_id") != envelope["target"].get(
            "interview_round_id"
        ):
            return None, [], (
                "REFERENCE_SCOPE_MISMATCH",
                "round.evaluation_belongs_to_another_round",
            )
        if evaluation[2].get("state") != "DRAFT":
            return None, [], ("BINDING_NOT_FOUND", "round.evaluation_draft_missing")
        if evaluation[2].get("evaluation_version") != payload["evaluation_version"]:
            return None, [], ("EVALUATION_VERSION_STALE", "round.evaluation_version_stale")
        if payload["evidence_coverage"] != 1:
            return None, [], ("EVIDENCE_VALIDATION_FAILED", "round.evidence_coverage_incomplete")
        if not self._scoped_reference_is_current(
            envelope, "validation_run_ref", payload["validation_run_ref"]
        ):
            return None, [], ("EVIDENCE_VALIDATION_FAILED", "round.validation_run_unknown")
        if not self._scoped_reference_is_current(
            envelope, "review_policy_ref", payload["review_policy_ref"]
        ):
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "round.review_policy_unknown")
        state["state"] = "AWAITING_CONFIRMATION"
        state["current_evaluation_id"] = payload["evaluation_id"]
        state["current_evaluation_version"] = payload["evaluation_version"]
        state["confirmation_owner_id"] = payload["confirmation_owner_id"]
        state["review_policy_ref"] = payload["review_policy_ref"]
        event = {
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "evidence_coverage": payload["evidence_coverage"],
            "review_policy_ref": payload["review_policy_ref"],
            "confirmation_owner_id": payload["confirmation_owner_id"],
            "due_at": payload["due_at"],
        }
        return state, [("EvaluationPackageReadyForReview", event)], None

    def _handle_SubmitEvaluationReview(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state.get("state") != "DRAFT":
            return None, [], ("INVALID_TRANSITION", "evaluation.not_reviewable")
        if state.get("evaluation_version") != payload["evaluation_version"]:
            return None, [], ("EVALUATION_VERSION_STALE", "evaluation.review_version_stale")
        round_fact = self._load_aggregate(
            envelope["tenant_id"],
            "INTERVIEW_ROUND",
            state["interview_round_id"],
            envelope["target"]["application_case_id"],
        )
        if not round_fact or round_fact[2].get("state") != "AWAITING_CONFIRMATION":
            return None, [], ("INVALID_TRANSITION", "evaluation.round_not_awaiting_confirmation")
        if round_fact[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "evaluation.review_round_epoch_is_stale",
            )
        if (
            round_fact[2].get("current_evaluation_id") != payload["evaluation_id"]
            or round_fact[2].get("current_evaluation_version")
            != payload["evaluation_version"]
        ):
            return None, [], (
                "EVALUATION_VERSION_STALE",
                "evaluation.review_not_current_for_round",
            )
        if envelope["actor_context"]["actor_id"] != round_fact[2].get("confirmation_owner_id"):
            return None, [], ("AUTHORIZATION_DENIED", "evaluation.not_confirmation_owner")
        if payload["disposition"] != "CONFIRM":
            return None, [], ("INVALID_TRANSITION", "evaluation.changes_not_implemented")
        state["state"] = "CONFIRMED"
        state["review"] = {
            "review_id": payload["review_id"],
            "actor_id": envelope["actor_context"]["actor_id"],
            "disposition": payload["disposition"],
        }
        event = {
            "review_id": payload["review_id"],
            "reviewer_id": envelope["actor_context"]["actor_id"],
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "disposition": payload["disposition"],
        }
        return state, [("EvaluationReviewSubmitted", event)], None

    def _handle_ReachConfirmationQuorum(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state.get("state") != "AWAITING_CONFIRMATION":
            return None, [], ("INVALID_TRANSITION", "round.not_awaiting_confirmation")
        if (
            state.get("current_evaluation_id") != payload["evaluation_id"]
            or state.get("current_evaluation_version")
            != payload["evaluation_version"]
        ):
            return None, [], (
                "EVALUATION_VERSION_STALE",
                "round.confirmation_not_for_current_evaluation",
            )
        evaluation = self._load_aggregate(
            envelope["tenant_id"],
            "EVALUATION_PACKAGE",
            payload["evaluation_id"],
            envelope["target"]["application_case_id"],
        )
        if not evaluation or evaluation[2].get("state") != "CONFIRMED":
            return None, [], ("INVALID_TRANSITION", "round.evaluation_not_confirmed")
        if evaluation[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "round.confirmed_evaluation_epoch_is_stale",
            )
        if evaluation[2].get("interview_round_id") != envelope["target"].get(
            "interview_round_id"
        ):
            return None, [], (
                "REFERENCE_SCOPE_MISMATCH",
                "round.confirmed_evaluation_belongs_to_another_round",
            )
        if evaluation[2].get("evaluation_version") != payload["evaluation_version"]:
            return None, [], (
                "EVALUATION_VERSION_STALE",
                "round.confirmed_evaluation_version_is_stale",
            )
        review = evaluation[2].get("review") or {}
        if review.get("review_id") not in payload["confirmation_ids"]:
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "round.confirmation_not_current")
        if payload["review_policy_ref"] != state.get("review_policy_ref"):
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "round.review_policy_stale")
        state["state"] = "AWAITING_OUTCOME"
        state["confirmation_ids"] = payload["confirmation_ids"]
        event = {
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "confirmation_ids": payload["confirmation_ids"],
            "review_policy_ref": payload["review_policy_ref"],
        }
        return state, [("EvaluationConfirmed", event)], None

    def _handle_RecordRoundDecision(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if state.get("state") != "AWAITING_OUTCOME":
            return None, [], ("INVALID_TRANSITION", "round.not_awaiting_outcome")
        if payload["evaluation_id"] != state.get("current_evaluation_id") or payload["evaluation_version"] != state.get("current_evaluation_version"):
            return None, [], ("EVALUATION_VERSION_STALE", "round.decision_evaluation_stale")
        if payload["decision_type"] == "FINAL_ROUND_COMPLETE" and not state.get("is_final_round"):
            return None, [], ("INVALID_TRANSITION", "round.not_final")
        evaluation = self._load_aggregate(
            envelope["tenant_id"],
            "EVALUATION_PACKAGE",
            payload["evaluation_id"],
            envelope["target"]["application_case_id"],
        )
        if not evaluation or evaluation[2].get("state") != "CONFIRMED":
            return None, [], ("INVALID_TRANSITION", "round.confirmed_evaluation_missing")
        if evaluation[1] != envelope["lifecycle_epoch"]:
            return None, [], (
                "LIFECYCLE_EPOCH_MISMATCH",
                "round.decision_evaluation_epoch_is_stale",
            )
        if evaluation[2].get("interview_round_id") != envelope["target"].get(
            "interview_round_id"
        ):
            return None, [], (
                "REFERENCE_SCOPE_MISMATCH",
                "round.decision_evaluation_belongs_to_another_round",
            )
        if evaluation[2].get("evaluation_version") != payload["evaluation_version"]:
            return None, [], (
                "EVALUATION_VERSION_STALE",
                "round.decision_evaluation_version_is_stale",
            )
        session_ids = list(state.get("imported_session_ids", []))
        session_versions: List[JsonObject] = []
        evidence_artifacts: List[JsonObject] = []
        transcript_versions: List[JsonObject] = []
        for session_id in session_ids:
            session = self._load_aggregate(
                envelope["tenant_id"],
                "INTERVIEW_SESSION",
                session_id,
                envelope["target"]["application_case_id"],
            )
            if not session or session[1] != envelope["lifecycle_epoch"]:
                return None, [], (
                    "LIFECYCLE_EPOCH_MISMATCH",
                    "round.decision_session_epoch_is_stale",
                )
            session_versions.append(
                {"session_id": session_id, "session_version": session[0]}
            )
            evidence_artifacts.extend(
                {
                    "session_id": session_id,
                    "artifact_id": item["artifact_id"],
                    "artifact_version": item["artifact_version"],
                    "checksum": item["sha256"],
                }
                for item in session[2].get("artifacts", [])
            )
            transcript_versions.extend(
                {
                    "session_id": session_id,
                    "transcript_id": item["transcript_id"],
                    "transcript_version": item["transcript_version"],
                    "artifact_id": item["artifact_id"],
                    "artifact_version": item["artifact_version"],
                }
                for item in session[2].get("transcripts", [])
            )
        session_versions.sort(key=lambda item: item["session_id"])
        evidence_artifacts.sort(
            key=lambda item: (
                item["session_id"],
                item["artifact_id"],
                item["artifact_version"],
            )
        )
        transcript_versions.sort(
            key=lambda item: (
                item["session_id"],
                item["transcript_id"],
                item["transcript_version"],
            )
        )
        archive = {
            "decision_id": payload["decision_id"],
            "decision_type": payload["decision_type"],
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "evaluation_aggregate_version": evaluation[0],
            "evidence_set_hash": evaluation[2]["evidence_set_hash"],
            "session_ids": sorted(session_ids),
            "session_versions": session_versions,
            "evidence_artifact_ids": sorted(
                {item["artifact_id"] for item in evidence_artifacts}
            ),
            "evidence_artifacts": evidence_artifacts,
            "transcript_versions": transcript_versions,
            "confirmation_ids": sorted(state.get("confirmation_ids", [])),
            "decision_record_version": envelope["expected_aggregate_version"] + 1,
            "lifecycle_epoch": envelope["lifecycle_epoch"],
        }
        archive["archive_hash"] = hashlib.sha256(self._json(archive).encode("utf-8")).hexdigest()
        archive["archive_manifest_ref"] = "archive-manifest:" + archive["archive_hash"]
        state["state"] = "COMPLETED"
        state["archive"] = archive
        decision_event = {
            "decision_id": payload["decision_id"],
            "decision_type": payload["decision_type"],
            "human_actor_id": envelope["actor_context"]["actor_id"],
            "evaluation_id": payload["evaluation_id"],
            "evaluation_version": payload["evaluation_version"],
            "decision_basis_ref": payload["decision_basis_ref"],
        }
        completion_event = {
            "interview_round_id": envelope["target"]["interview_round_id"],
            "decision_id": payload["decision_id"],
            "decision_type": payload["decision_type"],
            "confirmed_evaluation_id": payload["evaluation_id"],
            "confirmed_evaluation_version": payload["evaluation_version"],
            "evidence_set_hash": evaluation[2]["evidence_set_hash"],
            "completed_at": payload["submitted_at"],
            "archive_manifest_ref": archive["archive_manifest_ref"],
        }
        return state, [
            ("RoundDecisionRecorded", decision_event),
            ("InterviewRoundCompleted", completion_event),
        ], None

    def _handle_RequestExternalAction(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        target = envelope["target"]
        if target["aggregate_type"] != "ACTION_EXECUTION" or payload["action_id"] != target["aggregate_id"]:
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "action.target_mismatch")
        if state:
            return None, [], ("INVALID_TRANSITION", "action.already_exists")
        policy_snapshot_ref = self._scoped_reference_singleton(
            envelope, "action_policy_snapshot_ref"
        )
        if not policy_snapshot_ref:
            return None, [], (
                "BINDING_NOT_FOUND",
                "action.policy_snapshot_not_bound_to_case",
            )
        new_state = {
            "state": "REQUESTED",
            "action_id": payload["action_id"],
            "action_type": payload["action_type"],
            "target_ref": payload["target_ref"],
            "business_revision": payload["business_revision"],
            "payload_ref": payload["payload_ref"],
            "payload_hash": payload["payload_hash"],
            "risk_class": payload["risk_class"],
            "policy_snapshot_ref": policy_snapshot_ref,
            "attempts": [],
        }
        event = {
            "action_id": payload["action_id"],
            "action_type": payload["action_type"],
            "target_ref": payload["target_ref"],
            "business_revision": payload["business_revision"],
            "payload_hash": payload["payload_hash"],
            "risk_class": payload["risk_class"],
            "policy_snapshot_ref": new_state["policy_snapshot_ref"],
        }
        return new_state, [("AutomationActionRequested", event)], None

    def _handle_RecordExternalActionResult(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        if not state or state.get("action_id") != payload["action_id"]:
            return None, [], ("BINDING_NOT_FOUND", "action.not_found")
        outbox_state = self._outbox_state(envelope, payload["action_id"])
        required_outbox_state = (
            "SUPPRESSED" if payload["outcome"] == "CANCELLED" else "PENDING"
        )
        if outbox_state != required_outbox_state:
            return None, [], (
                "INVALID_TRANSITION",
                "action.outbox_not_pending_after_control_preflight",
            )
        if state.get("state") in {"SUCCEEDED", "CANCELLED"}:
            return None, [], ("INVALID_TRANSITION", "action.already_terminal")
        if payload["outcome"] == "CANCELLED" and payload.get("retryable") is not False:
            return None, [], (
                "INVALID_TRANSITION",
                "action.cancelled_result_must_not_be_retryable",
            )
        if any(item["attempt_no"] == payload["attempt_no"] for item in state.get("attempts", [])):
            return None, [], ("INVALID_TRANSITION", "action.attempt_already_recorded")
        attempt = {
            "attempt_no": payload["attempt_no"],
            "outcome": payload["outcome"],
            "observed_at": payload["observed_at"],
        }
        for optional in (
            "connector_receipt_ref",
            "external_resource_ref",
            "error_code",
            "retryable",
        ):
            if optional in payload:
                attempt[optional] = payload[optional]
        state.setdefault("attempts", []).append(attempt)
        state["state"] = payload["outcome"]
        event_type = {
            "SUCCEEDED": "AutomationActionSucceeded",
            "FAILED": "AutomationActionFailed",
            "CANCELLED": "AutomationActionCancelled",
        }[payload["outcome"]]
        event = {
            "action_id": payload["action_id"],
            "attempt_no": payload["attempt_no"],
            "outcome": payload["outcome"],
            "observed_at": payload["observed_at"],
        }
        if payload["outcome"] == "SUCCEEDED":
            event["connector_receipt_ref"] = payload["connector_receipt_ref"]
            if "external_resource_ref" in payload:
                event["external_resource_ref"] = payload["external_resource_ref"]
        elif payload["outcome"] == "FAILED":
            event["error_code"] = payload["error_code"]
            event["retryable"] = payload["retryable"]
        else:
            control_token = self._outbox_suppression_token(
                envelope, payload["action_id"]
            )
            if not control_token:
                return None, [], (
                    "BINDING_NOT_FOUND",
                    "action.suppression_cancellation_token_not_found",
                )
            state["cancellation_token"] = control_token
            event["error_code"] = payload["error_code"]
            event["retryable"] = payload["retryable"]
            event["cancellation_token"] = control_token
        return state, [(event_type, event)], None

    def _handle_PauseScope(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        target = envelope["target"]
        if target["aggregate_type"] != "APPLICATION_CASE":
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "control.case_scope_only")
        if payload.get("scope_type") != "APPLICATION_CASE" or payload.get("scope_id") != target["aggregate_id"]:
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "control.scope_mismatch")
        if state.get("paused"):
            return None, [], ("INVALID_TRANSITION", "control.already_paused")
        token_material = "{}|{}|{}|{}".format(
            envelope["tenant_id"],
            payload["scope_id"],
            payload["cancellation_token"],
            envelope["lifecycle_epoch"],
        )
        resume_token = "resume:" + hashlib.sha256(token_material.encode("utf-8")).hexdigest()
        state["paused"] = True
        state["pause_reason_code"] = payload["reason_code"]
        state["cancellation_token"] = payload["cancellation_token"]
        state["resume_token"] = resume_token
        state["paused_at"] = payload["effective_at"]
        event = {
            "scope_type": payload["scope_type"],
            "scope_id": payload["scope_id"],
            "reason_code": payload["reason_code"],
            "control_token": payload["cancellation_token"],
            "effective_at": payload["effective_at"],
        }
        event_specs: List[Tuple[str, JsonObject]] = [("CasePaused", event)]
        for action_id in self._suppressible_pending_outbox_action_ids(envelope):
            event_specs.append(
                (
                    "ExternalActionSuppressed",
                    {
                        "action_id": action_id,
                        "reason_code": payload["reason_code"],
                        "control_state_version": envelope[
                            "expected_aggregate_version"
                        ]
                        + 1,
                        "suppressed_at": payload["effective_at"],
                    },
                )
            )
        return state, event_specs, None

    def _handle_ResumeScope(self, envelope: JsonObject, state: JsonObject):
        payload = envelope["payload"]
        target = envelope["target"]
        if target["aggregate_type"] != "APPLICATION_CASE":
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "control.case_scope_only")
        if payload.get("scope_type") != "APPLICATION_CASE" or payload.get("scope_id") != target["aggregate_id"]:
            return None, [], ("REFERENCE_SCOPE_MISMATCH", "control.scope_mismatch")
        if not state.get("paused"):
            return None, [], ("INVALID_TRANSITION", "control.not_paused")
        if payload.get("resume_token") != state.get("resume_token"):
            return None, [], ("RESUME_TOKEN_INVALID", "control.resume_token_invalid")
        state["paused"] = False
        state["resumed_at"] = envelope["requested_at"]
        state["resume_reason"] = payload["reason"]
        state["resume_token"] = None
        event = {
            "scope_type": payload["scope_type"],
            "scope_id": payload["scope_id"],
            "reason_code": "AUTHORIZED_RESUME",
            "control_token": payload["resume_token"],
            "effective_at": envelope["requested_at"],
        }
        return state, [("CaseResumed", event)], None

    def _create_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS aggregates (
                tenant_id TEXT NOT NULL,
                aggregate_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                lifecycle_epoch INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, aggregate_type, aggregate_id)
            );
            CREATE TABLE IF NOT EXISTS command_results (
                tenant_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                command_id TEXT NOT NULL,
                result_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, idempotency_key),
                UNIQUE (tenant_id, command_id)
            );
            CREATE TABLE IF NOT EXISTS domain_events (
                event_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                aggregate_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                aggregate_version INTEGER NOT NULL,
                event_ordinal INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                correlation_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, event_id)
            );
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS scoped_references (
                tenant_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                lifecycle_epoch INTEGER NOT NULL,
                reference_kind TEXT NOT NULL,
                value_json TEXT NOT NULL,
                PRIMARY KEY (
                    tenant_id,
                    application_case_id,
                    lifecycle_epoch,
                    reference_kind,
                    value_json
                )
            );
            CREATE TABLE IF NOT EXISTS outbox (
                action_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                state TEXT NOT NULL,
                suppression_token TEXT,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (tenant_id, action_id)
            );
            """
        )
        self._db.commit()

    def _validate_actor(
        self,
        command_type: str,
        actor: JsonObject,
        tenant_id: str,
        application_case_id: str,
        lifecycle_epoch: int,
    ) -> Optional[str]:
        if not self._authority_grant_is_current(
            actor, tenant_id, application_case_id
        ):
            return "command.authority_grant_not_current_for_scope"
        if command_type in self._WORKFLOW_COMMANDS:
            if actor.get("actor_type") != "SERVICE" or actor.get("role") != "WORKFLOW_SERVICE":
                return "command.actor_not_workflow_service"
        elif command_type in self._EVIDENCE_COMMANDS:
            if actor.get("actor_type") != "SERVICE" or actor.get("role") != "EVIDENCE_SERVICE":
                return "command.actor_not_evidence_service"
        elif command_type == "SubmitEvaluationReview":
            if actor.get("actor_type") != "HUMAN" or actor.get("role") != "EVALUATION_OWNER":
                return "command.review_requires_owner_human"
        elif command_type == "RecordRoundDecision":
            if actor.get("actor_type") != "HUMAN":
                return "command.decision_requires_human"
            if actor.get("role") != "RECRUITER":
                return "command.decision_requires_recruiter"
            if not self._scoped_reference_is_current_for_scope(
                tenant_id,
                application_case_id,
                lifecycle_epoch,
                "authorized_round_decider_actor_id",
                actor.get("actor_id"),
            ):
                return "command.decision_actor_not_authorized"
        elif command_type in {"PauseScope", "ResumeScope"}:
            if actor.get("actor_type") != "HUMAN" or actor.get("role") not in {
                "RECRUITING_OPS_ADMIN",
                "PRIVACY_ADMIN",
            }:
                return "command.control_requires_authorized_human"
        elif command_type == "RecordExternalActionResult":
            if actor.get("actor_type") != "SERVICE" or actor.get("role") != "CONNECTOR_SERVICE":
                return "command.actor_not_connector_service"
        return None

    def _validate_authority_and_scope(
        self, envelope: JsonObject
    ) -> Optional[Tuple[str, str]]:
        command_type = envelope["command_type"]
        if command_type not in self._SUPPORTED:
            return "INVALID_TRANSITION", "command.not_implemented_in_synthetic_slice"
        actor_error = self._validate_actor(
            command_type,
            envelope["actor_context"],
            envelope["tenant_id"],
            envelope["target"]["application_case_id"],
            envelope["lifecycle_epoch"],
        )
        if actor_error:
            code = (
                "DECISION_REQUIRES_HUMAN"
                if command_type == "RecordRoundDecision"
                and envelope["actor_context"].get("actor_type") != "HUMAN"
                else "AUTHORIZATION_DENIED"
            )
            return code, actor_error
        scope_error = self._validate_scope_binding(envelope)
        if scope_error:
            return "REFERENCE_SCOPE_MISMATCH", scope_error
        return None

    def _validate_scope_binding(self, envelope: JsonObject) -> Optional[str]:
        target = envelope["target"]
        payload = envelope["payload"]
        command_type = envelope["command_type"]
        expected_type = self._TARGET_AGGREGATE_BY_COMMAND[command_type]
        if target["aggregate_type"] != expected_type:
            return "command.target_aggregate_type_mismatch"

        case_id = target["application_case_id"]
        case_fact = self._load_aggregate(
            envelope["tenant_id"], "APPLICATION_CASE", case_id, case_id
        )
        if not case_fact:
            return "command.application_case_not_found"

        current_any_scope = self._load_aggregate(
            envelope["tenant_id"], expected_type, target["aggregate_id"]
        )
        if current_any_scope and current_any_scope[3] != case_id:
            return "command.target_belongs_to_another_case"

        if expected_type == "APPLICATION_CASE":
            if target["aggregate_id"] != case_id:
                return "command.case_target_mismatch"
            if payload.get("scope_type") != "APPLICATION_CASE":
                return "command.only_application_case_scope_is_implemented"
            if payload.get("scope_id") != case_id:
                return "command.control_scope_id_mismatch"
        elif expected_type == "INTERVIEW_SESSION":
            if target.get("interview_session_id") != target["aggregate_id"]:
                return "command.session_target_mismatch"
            if payload.get("interview_session_id") != target["aggregate_id"]:
                return "command.session_payload_mismatch"
            if command_type == "RegisterCompletedSessionFact":
                if target.get("interview_round_id") != payload.get("interview_round_id"):
                    return "command.session_round_mismatch"
        elif expected_type == "INTERVIEW_ROUND":
            if target.get("interview_round_id") != target["aggregate_id"]:
                return "command.round_target_mismatch"
            if command_type == "ImportCompletedInterview":
                if target.get("interview_session_id") != payload.get(
                    "interview_session_id"
                ):
                    return "command.import_session_mismatch"
        elif expected_type == "EVALUATION_PACKAGE":
            if payload.get("evaluation_id") != target["aggregate_id"]:
                return "command.evaluation_payload_mismatch"
            if command_type == "RecordEvaluationDraftGenerated":
                if target.get("interview_round_id") != payload.get(
                    "interview_round_id"
                ):
                    return "command.evaluation_round_mismatch"
        elif expected_type == "ACTION_EXECUTION":
            if payload.get("action_id") != target["aggregate_id"]:
                return "command.action_payload_mismatch"
        return None

    def _validate_projection_actor(
        self, actor: JsonObject, tenant_id: str, application_case_id: str
    ) -> Optional[str]:
        required = {
            "actor_type",
            "actor_id",
            "role",
            "authority_snapshot_id",
            "authn_context_id",
        }
        if set(actor) != required:
            return "projection.actor_context_invalid"
        if actor.get("role") not in set(self._metadata("projection_reader_roles") or []):
            return "projection.role_not_authorized"
        if not self._authority_grant_is_current(
            actor, tenant_id, application_case_id
        ):
            return "projection.authority_grant_not_current_for_scope"
        return None

    def _authority_grant_is_current(
        self, actor: JsonObject, tenant_id: str, application_case_id: str
    ) -> bool:
        for grant in self._metadata("authority_grants") or []:
            if (
                grant.get("actor_type") == actor.get("actor_type")
                and grant.get("actor_id") == actor.get("actor_id")
                and grant.get("role") == actor.get("role")
                and grant.get("authority_snapshot_id")
                == actor.get("authority_snapshot_id")
                and grant.get("tenant_id") == tenant_id
                and application_case_id
                in set(grant.get("application_case_ids") or [])
            ):
                return True
        return False

    @staticmethod
    def _redact_projection_state(
        projection: JsonObject, aggregate_type: str, role: str
    ) -> None:
        if aggregate_type in {"APPLICATION_CASE", "ACTION_EXECUTION"} and role not in {
            "RECRUITING_OPS_ADMIN",
            "PRIVACY_ADMIN",
        }:
            projection.pop("resume_token", None)
            projection.pop("cancellation_token", None)
        if role not in {"EVALUATION_OWNER", "QUALITY_REVIEWER", "PRIVACY_ADMIN"}:
            for key in (
                "draft_ref",
                "claim_manifest_ref",
                "payload_ref",
            ):
                projection.pop(key, None)
            for artifact in projection.get("artifacts", []):
                artifact.pop("content_ref", None)
            for transcript in projection.get("transcripts", []):
                transcript.pop("segments_ref", None)

    def _load_aggregate(
        self,
        tenant_id: str,
        aggregate_type: str,
        aggregate_id: str,
        application_case_id: Optional[str] = None,
    ):
        scope_clause = ""
        parameters: List[Any] = [tenant_id, aggregate_type, aggregate_id]
        if application_case_id is not None:
            scope_clause = " AND application_case_id = ?"
            parameters.append(application_case_id)
        row = self._db.execute(
            "SELECT version, lifecycle_epoch, state_json, application_case_id "
            "FROM aggregates WHERE tenant_id = ? AND aggregate_type = ? "
            "AND aggregate_id = ?" + scope_clause,
            parameters,
        ).fetchone()
        if not row:
            return None
        return (
            row["version"],
            row["lifecycle_epoch"],
            json.loads(row["state_json"]),
            row["application_case_id"],
        )

    def _store_aggregate(self, envelope: JsonObject, version: int, state: JsonObject) -> None:
        target = envelope["target"]
        self._db.execute(
            "INSERT INTO aggregates "
            "(tenant_id, aggregate_type, aggregate_id, application_case_id, version, lifecycle_epoch, state_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(tenant_id, aggregate_type, aggregate_id) DO UPDATE SET "
            "version=excluded.version, lifecycle_epoch=excluded.lifecycle_epoch, state_json=excluded.state_json",
            (
                envelope["tenant_id"],
                target["aggregate_type"],
                target["aggregate_id"],
                target["application_case_id"],
                version,
                envelope["lifecycle_epoch"],
                self._json(state),
            ),
        )

    def _append_events(
        self,
        envelope: JsonObject,
        aggregate_version: int,
        event_specs: Iterable[Tuple[str, JsonObject]],
    ) -> List[str]:
        event_ids: List[str] = []
        target = envelope["target"]
        for ordinal, (event_type, payload) in enumerate(event_specs, start=1):
            event_material = "{}|{}|{}".format(
                envelope["tenant_id"], envelope["command_id"], ordinal
            )
            event_id = "evt:" + hashlib.sha256(
                event_material.encode("utf-8")
            ).hexdigest()
            actor = envelope["actor_context"]
            event = {
                "schema_version": "1.0.0",
                "event_id": event_id,
                "event_type": event_type,
                "tenant_id": envelope["tenant_id"],
                "aggregate_type": target["aggregate_type"],
                "aggregate_id": target["aggregate_id"],
                "aggregate_version": aggregate_version,
                "application_case_id": target["application_case_id"],
                "lifecycle_epoch": envelope["lifecycle_epoch"],
                "occurred_at": envelope["requested_at"],
                "recorded_at": envelope["requested_at"],
                "actor_ref": {
                    "actor_type": actor["actor_type"],
                    "actor_id": actor["actor_id"],
                    "authority_snapshot_id": actor["authority_snapshot_id"],
                },
                "correlation_id": envelope["correlation_id"],
                "causation_id": envelope.get("causation_id", envelope["command_id"]),
                "trace_id": envelope["correlation_id"],
                "data_classification": "INTERNAL",
                "payload": copy.deepcopy(payload),
            }
            if event_type == "InterviewSessionEnded":
                for field in (
                    "source_system",
                    "source_event_id",
                    "source_resource_version",
                ):
                    event[field] = envelope["payload"][field]
            validate_or_raise(event, _EVENT_SCHEMA)
            self._db.execute(
                "INSERT INTO domain_events "
                "(event_id, tenant_id, application_case_id, aggregate_type, aggregate_id, "
                "aggregate_version, event_ordinal, event_type, payload_json, correlation_id, "
                "occurred_at, event_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event_id,
                    envelope["tenant_id"],
                    target["application_case_id"],
                    target["aggregate_type"],
                    target["aggregate_id"],
                    aggregate_version,
                    ordinal,
                    event_type,
                    self._json(payload),
                    envelope["correlation_id"],
                    envelope["requested_at"],
                    self._json(event),
                ),
            )
            event_ids.append(event_id)
        return event_ids

    def _applied_result(
        self,
        envelope: JsonObject,
        version: int,
        event_ids: List[str],
        requested_action_ids: Optional[List[str]] = None,
    ) -> JsonObject:
        result = {
            "schema_version": "1.0.0",
            "command_id": envelope["command_id"],
            "status": "APPLIED",
            "tenant_id": envelope["tenant_id"],
            "target": copy.deepcopy(envelope["target"]),
            "aggregate_version": version,
            "lifecycle_epoch": envelope["lifecycle_epoch"],
            "emitted_event_ids": event_ids,
            "requested_action_ids": requested_action_ids or [],
            "completed_at": envelope["requested_at"],
            "trace_id": envelope["correlation_id"],
        }
        self._validate_result(result)
        return result

    def _rejected(self, envelope: Any, code: str, message: str) -> JsonObject:
        if not isinstance(envelope, dict):
            envelope = {}
        fallback_target: JsonObject = {
            "aggregate_type": "APPLICATION_CASE",
            "aggregate_id": "unknown",
            "application_case_id": "unknown",
        }
        supplied_target = envelope.get("target")
        if isinstance(supplied_target, dict):
            aggregate_type = supplied_target.get("aggregate_type")
            if aggregate_type in set(self._TARGET_AGGREGATE_BY_COMMAND.values()):
                fallback_target["aggregate_type"] = aggregate_type
            for field in (
                "aggregate_id",
                "application_case_id",
                "interview_round_id",
                "interview_session_id",
            ):
                value = supplied_target.get(field)
                if self._is_contract_identifier(value):
                    fallback_target[field] = value
        safe = {
            "command_id": self._safe_identifier(
                envelope.get("command_id"), "unknown-command"
            ),
            "tenant_id": self._safe_identifier(
                envelope.get("tenant_id"), "unknown-tenant"
            ),
            "target": fallback_target,
            "lifecycle_epoch": (
                envelope["lifecycle_epoch"]
                if isinstance(envelope.get("lifecycle_epoch"), int)
                and not isinstance(envelope.get("lifecycle_epoch"), bool)
                and envelope["lifecycle_epoch"] >= 1
                else 1
            ),
            "requested_at": "1970-01-01T00:00:00Z",
            "correlation_id": self._safe_identifier(
                envelope.get("correlation_id"), "unknown-trace"
            ),
        }
        return self._rejected_result(safe, code, message, retryable=False)

    def _rejected_result(
        self,
        envelope: JsonObject,
        code: str,
        message: str,
        retryable: bool,
        current_version: Optional[int] = None,
    ) -> JsonObject:
        error: JsonObject = {
            "code": code,
            "retryable": retryable,
            "message_key": message,
        }
        if current_version is not None:
            error["current_aggregate_version"] = current_version
        result = {
            "schema_version": "1.0.0",
            "command_id": envelope["command_id"],
            "status": "REJECTED",
            "tenant_id": envelope["tenant_id"],
            "target": copy.deepcopy(envelope["target"]),
            "lifecycle_epoch": envelope["lifecycle_epoch"],
            "error": error,
            "completed_at": envelope["requested_at"],
            "trace_id": envelope["correlation_id"],
        }
        self._validate_result(result)
        return result

    @staticmethod
    def _is_contract_identifier(value: Any) -> bool:
        if not isinstance(value, str) or not (1 <= len(value) <= 128):
            return False
        return all(
            character.isascii()
            and (character.isalnum() or character in "._:-")
            for character in value
        ) and value[0].isalnum()

    @classmethod
    def _safe_identifier(cls, value: Any, fallback: str) -> str:
        return value if cls._is_contract_identifier(value) else fallback

    @staticmethod
    def _validate_result(result: JsonObject) -> None:
        validate_or_raise(result, _CONTROL_SCHEMA)

    def _canonical_command_hash(self, envelope: JsonObject) -> str:
        material = {
            "command_type": envelope["command_type"],
            "tenant_id": envelope["tenant_id"],
            "target": envelope["target"],
            "expected_aggregate_version": envelope["expected_aggregate_version"],
            "lifecycle_epoch": envelope["lifecycle_epoch"],
            "payload": envelope["payload"],
            "actor": {
                "actor_type": envelope["actor_context"]["actor_type"],
                "actor_id": envelope["actor_context"]["actor_id"],
                "role": envelope["actor_context"]["role"],
                "authority_snapshot_id": envelope["actor_context"][
                    "authority_snapshot_id"
                ],
            },
        }
        return hashlib.sha256(self._json(material).encode("utf-8")).hexdigest()

    def _enqueue_action(self, envelope: JsonObject) -> None:
        payload = envelope["payload"]
        self._db.execute(
            "INSERT INTO outbox "
            "(action_id, tenant_id, application_case_id, state, suppression_token, "
            "payload_json, created_at, updated_at) "
            "VALUES (?, ?, ?, 'PENDING', NULL, ?, ?, ?)",
            (
                payload["action_id"],
                envelope["tenant_id"],
                envelope["target"]["application_case_id"],
                self._json(payload),
                envelope["requested_at"],
                envelope["requested_at"],
            ),
        )

    def _complete_outbox_action(self, envelope: JsonObject) -> None:
        payload = envelope["payload"]
        expected_state = "SUPPRESSED" if payload["outcome"] == "CANCELLED" else "PENDING"
        cursor = self._db.execute(
            "UPDATE outbox SET state = ?, updated_at = ? "
            "WHERE tenant_id = ? AND application_case_id = ? AND action_id = ? "
            "AND state = ?",
            (
                "COMPLETED"
                if payload["outcome"] == "SUCCEEDED"
                else payload["outcome"],
                payload["observed_at"],
                envelope["tenant_id"],
                envelope["target"]["application_case_id"],
                payload["action_id"],
                expected_state,
            ),
        )
        if cursor.rowcount != 1:
            raise RuntimeError("outbox action was not pending in the scoped tenant/case")

    def _outbox_state(self, envelope: JsonObject, action_id: str) -> Optional[str]:
        return self._outbox_state_for_scope(
            envelope["tenant_id"],
            envelope["target"]["application_case_id"],
            action_id,
        )

    def _outbox_state_for_scope(
        self, tenant_id: str, application_case_id: str, action_id: str
    ) -> Optional[str]:
        row = self._db.execute(
            "SELECT state FROM outbox WHERE tenant_id = ? "
            "AND application_case_id = ? AND action_id = ?",
            (
                tenant_id,
                application_case_id,
                action_id,
            ),
        ).fetchone()
        return row["state"] if row else None

    def _outbox_suppression_token(
        self, envelope: JsonObject, action_id: str
    ) -> Optional[str]:
        row = self._db.execute(
            "SELECT suppression_token FROM outbox WHERE tenant_id = ? "
            "AND application_case_id = ? AND action_id = ? AND state = 'SUPPRESSED'",
            (
                envelope["tenant_id"],
                envelope["target"]["application_case_id"],
                action_id,
            ),
        ).fetchone()
        return row["suppression_token"] if row else None

    def _suppress_pending_outbox(self, envelope: JsonObject) -> None:
        for action_id in self._suppressible_pending_outbox_action_ids(envelope):
            self._db.execute(
                "UPDATE outbox SET state = 'SUPPRESSED', suppression_token = ?, "
                "updated_at = ? "
                "WHERE tenant_id = ? AND application_case_id = ? "
                "AND action_id = ? AND state = 'PENDING'",
                (
                    envelope["payload"]["cancellation_token"],
                    envelope["requested_at"],
                    envelope["tenant_id"],
                    envelope["target"]["application_case_id"],
                    action_id,
                ),
            )

    def _suppressible_pending_outbox_action_ids(
        self, envelope: JsonObject
    ) -> List[str]:
        rows = self._db.execute(
            "SELECT action_id, payload_json FROM outbox WHERE tenant_id = ? "
            "AND application_case_id = ? AND state = 'PENDING' ORDER BY action_id",
            (
                envelope["tenant_id"],
                envelope["target"]["application_case_id"],
            ),
        ).fetchall()
        return [
            row["action_id"]
            for row in rows
            if json.loads(row["payload_json"]).get("action_type")
            not in self._RIGHTS_ACTION_TYPES
        ]

    def _is_pause_exempt(
        self, envelope: JsonObject, current_state: JsonObject
    ) -> bool:
        command_type = envelope["command_type"]
        payload = envelope["payload"]
        if command_type == "RequestExternalAction":
            return payload.get("action_type") in self._RIGHTS_ACTION_TYPES
        if command_type == "RecordExternalActionResult":
            if current_state.get("action_type") in self._RIGHTS_ACTION_TYPES:
                return True
            return (
                payload.get("outcome") == "CANCELLED"
                and self._outbox_state(envelope, payload["action_id"])
                == "SUPPRESSED"
            )
        return False

    def _case_is_stopped(self, envelope: JsonObject) -> bool:
        case_id = envelope["target"].get("application_case_id")
        case = self._load_aggregate(
            envelope["tenant_id"], "APPLICATION_CASE", case_id, case_id
        )
        return bool(
            case
            and (
                case[2].get("paused")
                or case[2].get("stage") in {"CLOSED", "WITHDRAWN"}
            )
        )

    def _consent_refs_are_current(
        self, envelope: JsonObject, refs: List[JsonObject]
    ) -> bool:
        if not refs:
            return False
        return all(
            ref.get("decision") == "GRANTED"
            and self._scoped_reference_is_current(
                envelope, "consent_receipt_ref", ref.get("receipt_ref")
            )
            for ref in refs
        )

    def _version_pin_is_current(
        self, envelope: JsonObject, pin: JsonObject
    ) -> bool:
        return self._scoped_reference_is_current(envelope, "version_pin", pin)

    def _scoped_reference_is_current(
        self, envelope: JsonObject, reference_kind: str, value: Any
    ) -> bool:
        return self._scoped_reference_is_current_for_scope(
            envelope["tenant_id"],
            envelope["target"]["application_case_id"],
            envelope["lifecycle_epoch"],
            reference_kind,
            value,
        )

    def _scoped_reference_is_current_for_scope(
        self,
        tenant_id: str,
        application_case_id: str,
        lifecycle_epoch: int,
        reference_kind: str,
        value: Any,
    ) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM scoped_references WHERE tenant_id = ? "
            "AND application_case_id = ? AND lifecycle_epoch = ? "
            "AND reference_kind = ? "
            "AND value_json = ?",
            (
                tenant_id,
                application_case_id,
                lifecycle_epoch,
                reference_kind,
                self._json(value),
            ),
        ).fetchone()
        return row is not None

    def _scoped_reference_singleton(
        self, envelope: JsonObject, reference_kind: str
    ) -> Any:
        rows = self._db.execute(
            "SELECT value_json FROM scoped_references WHERE tenant_id = ? "
            "AND application_case_id = ? AND lifecycle_epoch = ? "
            "AND reference_kind = ? ORDER BY value_json",
            (
                envelope["tenant_id"],
                envelope["target"]["application_case_id"],
                envelope["lifecycle_epoch"],
                reference_kind,
            ),
        ).fetchall()
        if len(rows) != 1:
            return None
        return json.loads(rows[0]["value_json"])

    def _metadata(self, key: str) -> Any:
        row = self._db.execute("SELECT value_json FROM metadata WHERE key = ?", (key,)).fetchone()
        return json.loads(row["value_json"]) if row else None

    def _round_has_transcript(
        self,
        tenant_id: str,
        case_id: str,
        round_id: str,
        lifecycle_epoch: int,
    ) -> bool:
        rows = self._db.execute(
            "SELECT state_json FROM aggregates WHERE tenant_id = ? AND application_case_id = ? "
            "AND aggregate_type = 'INTERVIEW_SESSION' AND lifecycle_epoch = ?",
            (tenant_id, case_id, lifecycle_epoch),
        ).fetchall()
        return any(
            json.loads(row["state_json"]).get("interview_round_id") == round_id
            and json.loads(row["state_json"]).get("transcripts")
            for row in rows
        )

    def _session_round_is_processing_evidence(
        self, envelope: JsonObject, session_state: JsonObject
    ) -> bool:
        round_id = session_state.get("interview_round_id")
        if not round_id:
            return False
        round_fact = self._load_aggregate(
            envelope["tenant_id"],
            "INTERVIEW_ROUND",
            round_id,
            envelope["target"]["application_case_id"],
        )
        return bool(
            round_fact
            and round_fact[1] == envelope["lifecycle_epoch"]
            and round_fact[2].get("state") == "EVIDENCE_PROCESSING"
        )

    @staticmethod
    def _json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
