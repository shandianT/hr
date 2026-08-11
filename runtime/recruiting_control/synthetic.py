"""Synthetic-only fixture builder for local behaviour tests."""

import json
import sqlite3

from .control import RecruitingCaseControl


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def build_synthetic_control() -> RecruitingCaseControl:
    """Create a deterministic control plane with no real person or provider data."""

    connection = sqlite3.connect(":memory:")
    control = RecruitingCaseControl(connection)
    case_state = {
        "stage": "INTERVIEWING",
        "paused": False,
        "synthetic_only": True,
    }
    round_state = {
        "state": "PLANNED",
        "is_final_round": True,
        "archive": None,
        "synthetic_only": True,
    }
    connection.execute(
        "INSERT INTO aggregates "
        "(tenant_id, aggregate_type, aggregate_id, application_case_id, version, lifecycle_epoch, state_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "tenant-synthetic",
            "APPLICATION_CASE",
            "case-001",
            "case-001",
            1,
            1,
            _json(case_state),
        ),
    )
    connection.execute(
        "INSERT INTO aggregates "
        "(tenant_id, aggregate_type, aggregate_id, application_case_id, version, lifecycle_epoch, state_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "tenant-synthetic",
            "INTERVIEW_ROUND",
            "round-001",
            "case-001",
            1,
            1,
            _json(round_state),
        ),
    )
    metadata = {
        "authority_grants": [
            {
                "actor_type": actor_type,
                "actor_id": actor_id,
                "role": role,
                "authority_snapshot_id": "authority:{}:v1".format(actor_id),
                "tenant_id": tenant_id,
                "application_case_ids": case_ids,
            }
            for actor_type, actor_id, role, tenant_id, case_ids in [
                ("SERVICE", "workflow-1", "WORKFLOW_SERVICE", "tenant-synthetic", ["case-001", "case-other"]),
                ("SERVICE", "workflow-2", "WORKFLOW_SERVICE", "tenant-synthetic-2", ["case-002"]),
                ("SERVICE", "evidence-1", "EVIDENCE_SERVICE", "tenant-synthetic", ["case-001", "case-other"]),
                ("HUMAN", "interviewer-1", "EVALUATION_OWNER", "tenant-synthetic", ["case-001"]),
                ("HUMAN", "decider-1", "RECRUITER", "tenant-synthetic", ["case-001"]),
                ("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN", "tenant-synthetic", ["case-001"]),
                ("HUMAN", "privacy-1", "PRIVACY_ADMIN", "tenant-synthetic", ["case-001"]),
                ("SERVICE", "connector-1", "CONNECTOR_SERVICE", "tenant-synthetic", ["case-001"]),
                ("HUMAN", "quality-1", "QUALITY_REVIEWER", "tenant-synthetic", ["case-001", "case-other"]),
                ("HUMAN", "quality-2", "QUALITY_REVIEWER", "tenant-synthetic-2", ["case-002"]),
            ]
        ],
        "projection_reader_roles": [
            "WORKFLOW_SERVICE",
            "EVIDENCE_SERVICE",
            "EVALUATION_OWNER",
            "RECRUITER",
            "RECRUITING_OPS_ADMIN",
            "PRIVACY_ADMIN",
            "QUALITY_REVIEWER",
        ],
    }
    scoped_references = [
        (
            "tenant-synthetic",
            "case-001",
            1,
            "authorized_round_decider_actor_id",
            "decider-1",
        ),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "source_artifact_binding",
            {"content_ref": "fixture:recording:001", "sha256": SHA_B},
        ),
        ("tenant-synthetic", "case-001", 1, "evidence_set_hash", SHA_C),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "consent_receipt_ref",
            "fixture:consent:001",
        ),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "validation_run_ref",
            "fixture:validation:001",
        ),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "review_policy_ref",
            "fixture:review-policy:v1",
        ),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "action_policy_snapshot_ref",
            "fixture:action-policy:v1",
        ),
        (
            "tenant-synthetic-2",
            "case-002",
            1,
            "action_policy_snapshot_ref",
            "fixture:action-policy:tenant-2:v1",
        ),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "version_pin",
            {
                "object_type": "SCORECARD",
                "object_id": "scorecard-001",
                "version": 1,
                "content_hash": SHA_A,
            },
        ),
        (
            "tenant-synthetic",
            "case-001",
            1,
            "version_pin",
            {
                "object_type": "ROLE_PROFILE",
                "object_id": "profile-001",
                "version": 1,
                "content_hash": SHA_D,
            },
        ),
    ]
    for key, value in metadata.items():
        connection.execute(
            "INSERT INTO metadata (key, value_json) VALUES (?, ?)",
            (key, _json(value)),
        )
    for tenant_id, case_id, lifecycle_epoch, reference_kind, value in scoped_references:
        connection.execute(
            "INSERT INTO scoped_references "
            "(tenant_id, application_case_id, lifecycle_epoch, reference_kind, value_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (tenant_id, case_id, lifecycle_epoch, reference_kind, _json(value)),
        )
    connection.commit()
    return control


def build_synthetic_control_at_awaiting_outcome() -> RecruitingCaseControl:
    """Create a synthetic precondition used only to test the HUMAN decision gate."""

    control = build_synthetic_control()
    connection = control._db
    round_state = {
        "state": "AWAITING_OUTCOME",
        "is_final_round": True,
        "archive": None,
        "synthetic_only": True,
        "imported_session_ids": [],
        "current_evaluation_id": "evaluation-001",
        "current_evaluation_version": 1,
        "confirmation_ids": ["review-001"],
    }
    evaluation_state = {
        "state": "CONFIRMED",
        "interview_round_id": "round-001",
        "evaluation_id": "evaluation-001",
        "evaluation_version": 1,
        "evidence_set_hash": SHA_C,
        "review": {
            "review_id": "review-001",
            "actor_id": "interviewer-1",
            "disposition": "CONFIRM",
        },
        "synthetic_only": True,
    }
    connection.execute(
        "UPDATE aggregates SET version = 4, state_json = ? "
        "WHERE tenant_id = ? AND aggregate_type = 'INTERVIEW_ROUND' AND aggregate_id = ?",
        (_json(round_state), "tenant-synthetic", "round-001"),
    )
    connection.execute(
        "INSERT INTO aggregates "
        "(tenant_id, aggregate_type, aggregate_id, application_case_id, version, lifecycle_epoch, state_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "tenant-synthetic",
            "EVALUATION_PACKAGE",
            "evaluation-001",
            "case-001",
            2,
            1,
            _json(evaluation_state),
        ),
    )
    connection.commit()
    return control


def build_synthetic_control_at_evidence_processing() -> RecruitingCaseControl:
    """Create a valid evidence-processing precondition for validation tests."""

    control = build_synthetic_control()
    connection = control._db
    round_state = {
        "state": "EVIDENCE_PROCESSING",
        "is_final_round": True,
        "archive": None,
        "synthetic_only": True,
        "imported_session_ids": ["session-001"],
        "scorecard_pin": {
            "object_type": "SCORECARD",
            "object_id": "scorecard-001",
            "version": 1,
            "content_hash": SHA_A,
        },
        "evidence_route": "RECORDING",
        "source_artifact_sha256": SHA_B,
    }
    session_state = {
        "state": "ENDED",
        "interview_round_id": "round-001",
        "synthetic_only": True,
        "artifacts": [
            {
                "artifact_id": "artifact-001",
                "artifact_version": 1,
                "artifact_type": "RECORDING",
                "sha256": SHA_B,
                "content_ref": "fixture:recording:001",
            }
        ],
        "transcripts": [
            {
                "transcript_id": "transcript-001",
                "transcript_version": 1,
                "artifact_id": "artifact-001",
                "segments_ref": "fixture:transcript:segments:001",
                "quality_signals": [
                    {"name": "speaker_confidence", "value": 0.96, "threshold_version": "v1"}
                ],
            }
        ],
    }
    connection.execute(
        "UPDATE aggregates SET version = 2, state_json = ? "
        "WHERE tenant_id = ? AND aggregate_type = 'INTERVIEW_ROUND' AND aggregate_id = ?",
        (_json(round_state), "tenant-synthetic", "round-001"),
    )
    connection.execute(
        "INSERT INTO aggregates "
        "(tenant_id, aggregate_type, aggregate_id, application_case_id, version, lifecycle_epoch, state_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "tenant-synthetic",
            "INTERVIEW_SESSION",
            "session-001",
            "case-001",
            3,
            1,
            _json(session_state),
        ),
    )
    connection.commit()
    return control


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
