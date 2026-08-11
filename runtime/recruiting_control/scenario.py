"""Reusable, deterministic command data for the synthetic G1a happy path.

Every value in this module is invented fixture data.  Building the scenario
does not read files, open network connections, or contact an external system.
"""

import copy
from typing import Any, Dict, List


JsonObject = Dict[str, Any]

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64

TENANT_ID = "tenant-synthetic"
APPLICATION_CASE_ID = "case-001"
INTERVIEW_ROUND_ID = "round-001"
INTERVIEW_SESSION_ID = "session-001"


def actor(actor_type: str, actor_id: str, role: str) -> JsonObject:
    """Build an invented actor snapshot suitable for a command envelope."""

    return {
        "actor_type": actor_type,
        "actor_id": actor_id,
        "role": role,
        "authority_snapshot_id": f"authority:{actor_id}:v1",
        "authn_context_id": f"authn:{actor_id}:session-1",
    }


WORKFLOW = actor("SERVICE", "workflow-1", "WORKFLOW_SERVICE")
EVIDENCE = actor("SERVICE", "evidence-1", "EVIDENCE_SERVICE")
INTERVIEWER = actor("HUMAN", "interviewer-1", "EVALUATION_OWNER")
DECIDER = actor("HUMAN", "decider-1", "RECRUITER")
OPS_ADMIN = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")
CONNECTOR = actor("SERVICE", "connector-1", "CONNECTOR_SERVICE")
QUALITY_REVIEWER = actor("HUMAN", "quality-1", "QUALITY_REVIEWER")


def projection_request(
    acting: JsonObject = QUALITY_REVIEWER,
    tenant_id: str = TENANT_ID,
    application_case_id: str = APPLICATION_CASE_ID,
) -> JsonObject:
    """Build an authenticated, synthetic projection request."""

    return {
        "tenant_id": tenant_id,
        "application_case_id": application_case_id,
        "actor_context": copy.deepcopy(acting),
    }


def command(
    command_type: str,
    aggregate_type: str,
    aggregate_id: str,
    expected_version: int,
    payload: JsonObject,
    command_no: int,
    acting: JsonObject,
) -> JsonObject:
    """Build one deterministic synthetic command envelope."""

    total_minutes = 10 * 60 + command_no
    requested_hour, requested_minute = divmod(total_minutes, 60)
    return {
        "schema_version": "1.0.0",
        "command_id": f"cmd-{command_no:02d}",
        "command_type": command_type,
        "tenant_id": TENANT_ID,
        "target": {
            "aggregate_type": aggregate_type,
            "aggregate_id": aggregate_id,
            "application_case_id": APPLICATION_CASE_ID,
            "interview_round_id": INTERVIEW_ROUND_ID,
            "interview_session_id": INTERVIEW_SESSION_ID,
        },
        "expected_aggregate_version": expected_version,
        "lifecycle_epoch": 1,
        "idempotency_key": f"synthetic:g1a:{command_no:02d}",
        "correlation_id": "run-001",
        "requested_at": (
            f"2026-08-10T{requested_hour:02d}:{requested_minute:02d}:00Z"
        ),
        "actor_context": copy.deepcopy(acting),
        "payload": copy.deepcopy(payload),
    }


def build_g1a_happy_path_commands() -> List[JsonObject]:
    """Return the fresh nine-command chain that completes the synthetic round.

    Commands 1-8 stop at ``AWAITING_OUTCOME``.  Command 9 is an independent
    HUMAN round decision and is the only command that creates the final archive.
    """

    return [
        command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            INTERVIEW_SESSION_ID,
            0,
            {
                "interview_round_id": INTERVIEW_ROUND_ID,
                "interview_session_id": INTERVIEW_SESSION_ID,
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:001",
            },
            1,
            WORKFLOW,
        ),
        command(
            "ImportCompletedInterview",
            "INTERVIEW_ROUND",
            INTERVIEW_ROUND_ID,
            1,
            {
                "interview_session_id": INTERVIEW_SESSION_ID,
                "scorecard_pin": {
                    "object_type": "SCORECARD",
                    "object_id": "scorecard-001",
                    "version": 1,
                    "content_hash": SHA_A,
                },
                "evidence_route": "RECORDING",
                "source_artifact_ref": "fixture:recording:001",
                "source_artifact_sha256": SHA_B,
                "consent_snapshot_refs": [
                    {
                        "participant_id": "participant-001",
                        "purposes": [
                            "RECORDING",
                            "TRANSCRIPTION",
                            "EVALUATION_SUPPORT",
                        ],
                        "notice_version": "notice-v1",
                        "decision": "GRANTED",
                        "valid_at": "2026-08-10T09:00:00Z",
                        "receipt_ref": "fixture:consent:001",
                    }
                ],
                "import_reason": "SYNTHETIC_G1A_WALKING_SKELETON",
            },
            2,
            WORKFLOW,
        ),
        command(
            "RegisterEvidenceArtifact",
            "INTERVIEW_SESSION",
            INTERVIEW_SESSION_ID,
            1,
            {
                "interview_session_id": INTERVIEW_SESSION_ID,
                "artifact_id": "artifact-001",
                "artifact_type": "RECORDING",
                "artifact_version": 1,
                "content_ref": "fixture:recording:001",
                "sha256": SHA_B,
                "source": "PROVIDER",
                "processing_purpose": "INTERVIEW_EVALUATION_SUPPORT",
                "consent_snapshot_refs": [
                    {
                        "participant_id": "participant-001",
                        "purposes": [
                            "RECORDING",
                            "TRANSCRIPTION",
                            "EVALUATION_SUPPORT",
                        ],
                        "notice_version": "notice-v1",
                        "decision": "GRANTED",
                        "valid_at": "2026-08-10T09:00:00Z",
                        "receipt_ref": "fixture:consent:001",
                    }
                ],
                "retention_class": "SYNTHETIC_EPHEMERAL",
            },
            3,
            EVIDENCE,
        ),
        command(
            "RecordTranscriptOutcome",
            "INTERVIEW_SESSION",
            INTERVIEW_SESSION_ID,
            2,
            {
                "interview_session_id": INTERVIEW_SESSION_ID,
                "artifact_id": "artifact-001",
                "artifact_version": 1,
                "run_id": "transcript-run-001",
                "outcome": "COMPLETED",
                "transcript_id": "transcript-001",
                "transcript_version": 1,
                "language": "zh-CN",
                "speaker_map_version": 1,
                "quality_signals": [
                    {
                        "name": "word_error_rate_estimate",
                        "value": 0.08,
                        "threshold_version": "v1",
                    },
                    {
                        "name": "speaker_confidence",
                        "value": 0.96,
                        "threshold_version": "v1",
                    },
                    {
                        "name": "timestamp_coverage",
                        "value": 1.0,
                        "threshold_version": "v1",
                    },
                ],
                "segments_ref": "fixture:transcript:segments:001",
            },
            4,
            EVIDENCE,
        ),
        command(
            "RecordEvaluationDraftGenerated",
            "EVALUATION_PACKAGE",
            "evaluation-001",
            0,
            {
                "interview_round_id": INTERVIEW_ROUND_ID,
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "evidence_set_hash": SHA_C,
                "scorecard_pin": {
                    "object_type": "SCORECARD",
                    "object_id": "scorecard-001",
                    "version": 1,
                    "content_hash": SHA_A,
                },
                "profile_pin": {
                    "object_type": "ROLE_PROFILE",
                    "object_id": "profile-001",
                    "version": 1,
                    "content_hash": SHA_D,
                },
                "model_version": "synthetic-evaluator-v1",
                "prompt_version": "synthetic-prompt-v1",
                "template_version": "evaluation-template-v1",
                "draft_ref": "fixture:evaluation:draft:001",
                "claim_manifest_ref": "fixture:evaluation:claims:001",
                "critical_claim_count": 2,
                "supported_critical_claim_count": 2,
                "decision_fields_present": False,
                "tool_execution_count": 0,
            },
            5,
            EVIDENCE,
        ),
        command(
            "PublishEvaluationForReview",
            "INTERVIEW_ROUND",
            INTERVIEW_ROUND_ID,
            2,
            {
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "evidence_coverage": 1.0,
                "validation_run_ref": "fixture:validation:001",
                "review_policy_ref": "fixture:review-policy:v1",
                "confirmation_owner_id": "interviewer-1",
                "due_at": "2026-08-11T10:00:00Z",
            },
            6,
            WORKFLOW,
        ),
        command(
            "SubmitEvaluationReview",
            "EVALUATION_PACKAGE",
            "evaluation-001",
            1,
            {
                "review_id": "review-001",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "disposition": "CONFIRM",
                "comment_ref": "fixture:review-comment:001",
            },
            7,
            INTERVIEWER,
        ),
        command(
            "ReachConfirmationQuorum",
            "INTERVIEW_ROUND",
            INTERVIEW_ROUND_ID,
            3,
            {
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "confirmation_ids": ["review-001"],
                "review_policy_ref": "fixture:review-policy:v1",
            },
            8,
            WORKFLOW,
        ),
        command(
            "RecordRoundDecision",
            "INTERVIEW_ROUND",
            INTERVIEW_ROUND_ID,
            4,
            {
                "decision_id": "decision-001",
                "decision_type": "FINAL_ROUND_COMPLETE",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "decision_basis_ref": "fixture:decision-basis:001",
                "submitted_at": "2026-08-10T10:09:00Z",
            },
            9,
            DECIDER,
        ),
    ]
