import copy
import unittest

from runtime.recruiting_control.synthetic import (
    build_synthetic_control,
    build_synthetic_control_at_awaiting_outcome,
    build_synthetic_control_at_evidence_processing,
)
from runtime.tests.test_g1a_walking_skeleton import (
    DECIDER,
    EVIDENCE,
    SHA_A,
    SHA_C,
    SHA_D,
    WORKFLOW,
    actor,
    build_g1a_happy_path_commands,
    command,
    projection_request,
)


class CommandGateTest(unittest.TestCase):
    def test_same_key_same_payload_replays_and_changed_payload_is_rejected_without_second_event(self):
        control = build_synthetic_control()
        original = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-001",
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
        )

        applied = control.submit(original)
        replayed_results = [control.submit(copy.deepcopy(original)) for _ in range(10)]
        changed = copy.deepcopy(original)
        changed["command_id"] = "cmd-idempotency-conflict"
        changed["payload"]["ended_at"] = "2026-08-10T09:46:00Z"
        rejected = control.submit(changed)

        self.assertEqual("APPLIED", applied["status"])
        for replayed in replayed_results:
            self.assertEqual("REPLAYED", replayed["status"])
            self.assertEqual(applied["emitted_event_ids"], replayed["emitted_event_ids"])
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("IDEMPOTENCY_KEY_REUSED", rejected["error"]["code"])
        projection = control.read(projection_request())
        self.assertEqual(1, projection["event_count"])
        self.assertEqual(1, projection["sessions"]["session-001"]["version"])

    def test_case_pause_blocks_queued_work_until_authorized_resume(self):
        control = build_synthetic_control()
        operator = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")
        pause = command(
            "PauseScope",
            "APPLICATION_CASE",
            "case-001",
            1,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason_code": "SYNTHETIC_SAFETY_REVIEW",
                "cancellation_token": "cancel-case-001-epoch-1",
                "effective_at": "2026-08-10T10:00:00Z",
            },
            20,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(pause)["status"])

        queued_work = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:001",
            },
            21,
            WORKFLOW,
        )
        blocked = control.submit(queued_work)
        self.assertEqual("REJECTED", blocked["status"])
        self.assertEqual("CASE_PAUSED_OR_CLOSED", blocked["error"]["code"])

        paused = control.read(projection_request(acting=operator))
        self.assertTrue(paused["case"]["paused"])
        self.assertNotIn("session-001", paused["sessions"])
        resume = command(
            "ResumeScope",
            "APPLICATION_CASE",
            "case-001",
            2,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason": "Synthetic review completed",
                "resume_token": paused["case"]["resume_token"],
            },
            22,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(resume)["status"])
        after_resume = copy.deepcopy(queued_work)
        after_resume["command_id"] = "cmd-after-resume"
        after_resume["idempotency_key"] = "synthetic:g1a:after-resume"
        self.assertEqual("APPLIED", control.submit(after_resume)["status"])

    def test_service_identity_cannot_submit_human_round_decision(self):
        control = build_synthetic_control_at_awaiting_outcome()
        forged = command(
            "RecordRoundDecision",
            "INTERVIEW_ROUND",
            "round-001",
            4,
            {
                "decision_id": "decision-forged",
                "decision_type": "FINAL_ROUND_COMPLETE",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "decision_basis_ref": "fixture:forged-decision-basis",
                "submitted_at": "2026-08-10T10:40:00Z",
            },
            40,
            WORKFLOW,
        )
        before = control.read(projection_request())
        rejected = control.submit(forged)
        after = control.read(projection_request())
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("DECISION_REQUIRES_HUMAN", rejected["error"]["code"])
        self.assertEqual("AWAITING_OUTCOME", after["rounds"]["round-001"]["state"])
        self.assertIsNone(after["rounds"]["round-001"]["archive"])
        self.assertEqual(before["event_count"], after["event_count"])

    def test_stale_version_and_case_epoch_are_rejected_without_creating_a_fact(self):
        base = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:001",
            },
            50,
            WORKFLOW,
        )

        version_control = build_synthetic_control()
        stale_version = copy.deepcopy(base)
        stale_version["expected_aggregate_version"] = 1
        version_result = version_control.submit(stale_version)
        self.assertEqual("REJECTED", version_result["status"])
        self.assertEqual("VERSION_CONFLICT", version_result["error"]["code"])

        epoch_control = build_synthetic_control()
        stale_epoch = copy.deepcopy(base)
        stale_epoch["command_id"] = "cmd-stale-epoch"
        stale_epoch["idempotency_key"] = "synthetic:g1a:stale-epoch"
        stale_epoch["lifecycle_epoch"] = 2
        epoch_result = epoch_control.submit(stale_epoch)
        self.assertEqual("REJECTED", epoch_result["status"])
        self.assertEqual("LIFECYCLE_EPOCH_MISMATCH", epoch_result["error"]["code"])

        for control in (version_control, epoch_control):
            projection = control.read(projection_request())
            self.assertNotIn("session-001", projection["sessions"])
            self.assertEqual(0, projection["event_count"])

    def test_unsupported_critical_claim_cannot_create_evaluation_draft(self):
        control = build_synthetic_control_at_evidence_processing()
        unsupported = command(
            "RecordEvaluationDraftGenerated",
            "EVALUATION_PACKAGE",
            "evaluation-001",
            0,
            {
                "interview_round_id": "round-001",
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
                "draft_ref": "fixture:evaluation:draft:unsupported",
                "claim_manifest_ref": "fixture:evaluation:claims:unsupported",
                "critical_claim_count": 2,
                "supported_critical_claim_count": 1,
                "decision_fields_present": False,
                "tool_execution_count": 0,
            },
            60,
            EVIDENCE,
        )
        rejected = control.submit(unsupported)
        projection = control.read(projection_request())
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("EVIDENCE_VALIDATION_FAILED", rejected["error"]["code"])
        self.assertNotIn("evaluation-001", projection["evaluations"])
        self.assertEqual(0, projection["event_count"])

    def test_unknown_consent_receipt_blocks_completed_interview_import(self):
        control = build_synthetic_control()
        ended = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:001",
            },
            70,
            WORKFLOW,
        )
        self.assertEqual("APPLIED", control.submit(ended)["status"])
        attempted_import = command(
            "ImportCompletedInterview",
            "INTERVIEW_ROUND",
            "round-001",
            1,
            {
                "interview_session_id": "session-001",
                "scorecard_pin": {
                    "object_type": "SCORECARD",
                    "object_id": "scorecard-001",
                    "version": 1,
                    "content_hash": SHA_A,
                },
                "evidence_route": "RECORDING",
                "source_artifact_ref": "fixture:recording:001",
                "source_artifact_sha256": "b" * 64,
                "consent_snapshot_refs": [
                    {
                        "participant_id": "participant-001",
                        "purposes": ["RECORDING", "TRANSCRIPTION", "EVALUATION_SUPPORT"],
                        "notice_version": "notice-v1",
                        "decision": "GRANTED",
                        "valid_at": "2026-08-10T09:00:00Z",
                        "receipt_ref": "fixture:consent:unknown",
                    }
                ],
                "import_reason": "SYNTHETIC_CONSENT_NEGATIVE",
            },
            71,
            WORKFLOW,
        )
        rejected = control.submit(attempted_import)
        projection = control.read(projection_request())
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("CONSENT_MISSING", rejected["error"]["code"])
        self.assertEqual("PLANNED", projection["rounds"]["round-001"]["state"])
        self.assertEqual(1, projection["rounds"]["round-001"]["version"])
        self.assertEqual(1, projection["event_count"])

    def test_authorization_is_checked_before_idempotency_replay(self):
        control = build_synthetic_control()
        original = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-auth-order-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:auth-order-001",
            },
            80,
            WORKFLOW,
        )
        self.assertEqual("APPLIED", control.submit(original)["status"])

        stolen_replay = copy.deepcopy(original)
        stolen_replay["command_id"] = "cmd-stolen-replay"
        stolen_replay["actor_context"] = actor(
            "SERVICE", "intruder-1", "WORKFLOW_SERVICE"
        )
        rejected = control.submit(stolen_replay)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("AUTHORIZATION_DENIED", rejected["error"]["code"])

    def test_only_current_authorized_recruiter_can_record_round_decision(self):
        control = build_synthetic_control_at_awaiting_outcome()
        quality_reviewer = actor("HUMAN", "quality-1", "QUALITY_REVIEWER")
        attempted = command(
            "RecordRoundDecision",
            "INTERVIEW_ROUND",
            "round-001",
            4,
            {
                "decision_id": "decision-wrong-human-role",
                "decision_type": "FINAL_ROUND_COMPLETE",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "decision_basis_ref": "fixture:decision-basis:wrong-role",
                "submitted_at": "2026-08-10T11:22:00Z",
            },
            81,
            quality_reviewer,
        )
        rejected = control.submit(attempted)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("AUTHORIZATION_DENIED", rejected["error"]["code"])

        mismatched_snapshot = command(
            "RecordRoundDecision",
            "INTERVIEW_ROUND",
            "round-001",
            4,
            {
                "decision_id": "decision-mismatched-snapshot",
                "decision_type": "FINAL_ROUND_COMPLETE",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "decision_basis_ref": "fixture:decision-basis:mismatched-snapshot",
                "submitted_at": "2026-08-10T11:23:00Z",
            },
            87,
            DECIDER,
        )
        mismatched_snapshot["actor_context"][
            "authority_snapshot_id"
        ] = "authority:workflow-1:v1"
        rejected_snapshot = control.submit(mismatched_snapshot)
        self.assertEqual("AUTHORIZATION_DENIED", rejected_snapshot["error"]["code"])

    def test_current_case_epoch_is_authoritative_for_existing_child(self):
        control = build_synthetic_control_at_evidence_processing()
        control._db.execute(
            "UPDATE aggregates SET lifecycle_epoch = 2 WHERE tenant_id = ? "
            "AND aggregate_type = 'APPLICATION_CASE' AND aggregate_id = ?",
            ("tenant-synthetic", "case-001"),
        )
        control._db.commit()
        artifact = copy.deepcopy(build_g1a_happy_path_commands()[2])
        artifact["command_id"] = "cmd-stale-child-epoch"
        artifact["idempotency_key"] = "synthetic:g1a:stale-child-epoch"
        artifact["expected_aggregate_version"] = 3
        artifact["lifecycle_epoch"] = 2
        rejected = control.submit(artifact)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("LIFECYCLE_EPOCH_MISMATCH", rejected["error"]["code"])

    def test_scope_binding_rejects_missing_case_forged_case_and_payload_id(self):
        missing_case_control = build_synthetic_control()
        missing_case = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-missing-case-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:missing-case-001",
            },
            83,
            WORKFLOW,
        )
        missing_case["target"]["application_case_id"] = "case-missing"
        rejected_missing = missing_case_control.submit(missing_case)
        self.assertEqual("AUTHORIZATION_DENIED", rejected_missing["error"]["code"])

        forged_control = build_synthetic_control()
        ended = copy.deepcopy(missing_case)
        ended["target"]["application_case_id"] = "case-001"
        ended["command_id"] = "cmd-ended-before-forgery"
        ended["idempotency_key"] = "synthetic:g1a:ended-before-forgery"
        self.assertEqual("APPLIED", forged_control.submit(ended)["status"])
        forged_control._db.execute(
            "INSERT INTO aggregates (tenant_id, aggregate_type, aggregate_id, "
            "application_case_id, version, lifecycle_epoch, state_json) "
            "VALUES (?, 'APPLICATION_CASE', ?, ?, 1, 1, ?)",
            (
                "tenant-synthetic",
                "case-other",
                "case-other",
                forged_control._json(
                    {"stage": "INTERVIEWING", "paused": False, "synthetic_only": True}
                ),
            ),
        )
        forged_control._db.commit()
        forged = command(
            "RegisterEvidenceArtifact",
            "INTERVIEW_SESSION",
            "session-001",
            1,
            {
                "interview_session_id": "session-001",
                "artifact_id": "artifact-forged",
                "artifact_type": "RECORDING",
                "artifact_version": 1,
                "content_ref": "fixture:recording:forged",
                "sha256": "b" * 64,
                "source": "PROVIDER",
                "processing_purpose": "INTERVIEW_EVALUATION_SUPPORT",
                "consent_snapshot_refs": [
                    {
                        "participant_id": "participant-001",
                        "purposes": ["RECORDING"],
                        "notice_version": "notice-v1",
                        "decision": "GRANTED",
                        "valid_at": "2026-08-10T09:00:00Z",
                        "receipt_ref": "fixture:consent:001",
                    }
                ],
                "retention_class": "SYNTHETIC_EPHEMERAL",
            },
            84,
            EVIDENCE,
        )
        forged["target"]["application_case_id"] = "case-other"
        rejected_forged = forged_control.submit(forged)
        self.assertEqual("REFERENCE_SCOPE_MISMATCH", rejected_forged["error"]["code"])

        mismatch_control = build_synthetic_control_at_evidence_processing()
        mismatch = command(
            "RecordEvaluationDraftGenerated",
            "EVALUATION_PACKAGE",
            "evaluation-001",
            0,
            {
                "interview_round_id": "round-001",
                "evaluation_id": "evaluation-forged",
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
                "draft_ref": "fixture:evaluation:draft:mismatch",
                "claim_manifest_ref": "fixture:evaluation:claims:mismatch",
                "critical_claim_count": 1,
                "supported_critical_claim_count": 1,
                "decision_fields_present": False,
                "tool_execution_count": 0,
            },
            85,
            EVIDENCE,
        )
        rejected_mismatch = mismatch_control.submit(mismatch)
        self.assertEqual("REFERENCE_SCOPE_MISMATCH", rejected_mismatch["error"]["code"])

    def test_projection_requires_current_authority_and_redacts_control_tokens(self):
        control = build_synthetic_control()
        with self.assertRaises(ValueError):
            control.read(
                {"tenant_id": "tenant-synthetic", "application_case_id": "case-001"}
            )
        with self.assertRaises(PermissionError):
            control.read(
                projection_request(
                    acting=actor("HUMAN", "quality-stale", "QUALITY_REVIEWER")
                )
            )

        operator = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")
        pause = command(
            "PauseScope",
            "APPLICATION_CASE",
            "case-001",
            1,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason_code": "SYNTHETIC_READ_POLICY",
                "cancellation_token": "cancel-read-policy-001",
                "effective_at": "2026-08-10T11:26:00Z",
            },
            86,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(pause)["status"])
        workflow_projection = control.read(projection_request(acting=WORKFLOW))
        self.assertNotIn("resume_token", workflow_projection["case"])
        self.assertNotIn("cancellation_token", workflow_projection["case"])
        operator_projection = control.read(projection_request(acting=operator))
        self.assertIn("resume_token", operator_projection["case"])

    def test_new_session_cannot_reference_a_round_from_another_case(self):
        control = build_synthetic_control()
        control._db.execute(
            "INSERT INTO aggregates (tenant_id, aggregate_type, aggregate_id, "
            "application_case_id, version, lifecycle_epoch, state_json) "
            "VALUES (?, 'APPLICATION_CASE', ?, ?, 1, 1, ?)",
            (
                "tenant-synthetic",
                "case-other",
                "case-other",
                control._json(
                    {"stage": "INTERVIEWING", "paused": False, "synthetic_only": True}
                ),
            ),
        )
        control._db.commit()
        cross_round = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-cross",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-cross",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:cross",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-cross-round-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:cross-round-001",
            },
            88,
            WORKFLOW,
        )
        cross_round["target"].update(
            {
                "application_case_id": "case-other",
                "interview_session_id": "session-cross",
            }
        )
        rejected = control.submit(cross_round)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("REFERENCE_SCOPE_MISMATCH", rejected["error"]["code"])

    def test_stale_session_epoch_cannot_be_imported_into_current_round(self):
        control = build_synthetic_control()
        ended, import_command = build_g1a_happy_path_commands()[:2]
        self.assertEqual("APPLIED", control.submit(ended)["status"])
        control._db.execute(
            "UPDATE aggregates SET lifecycle_epoch = 2 WHERE tenant_id = ? "
            "AND application_case_id = ? AND aggregate_type IN "
            "('APPLICATION_CASE', 'INTERVIEW_ROUND')",
            ("tenant-synthetic", "case-001"),
        )
        control._db.commit()
        import_command["command_id"] = "cmd-import-stale-session"
        import_command["idempotency_key"] = "synthetic:g1a:import-stale-session"
        import_command["lifecycle_epoch"] = 2
        rejected = control.submit(import_command)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("LIFECYCLE_EPOCH_MISMATCH", rejected["error"]["code"])

    def test_evaluation_must_match_current_round_and_current_version(self):
        control = build_synthetic_control_at_awaiting_outcome()
        round_two_state = {
            "state": "EVIDENCE_PROCESSING",
            "is_final_round": False,
            "archive": None,
            "synthetic_only": True,
        }
        control._db.execute(
            "INSERT INTO aggregates (tenant_id, aggregate_type, aggregate_id, "
            "application_case_id, version, lifecycle_epoch, state_json) "
            "VALUES (?, 'INTERVIEW_ROUND', ?, ?, 2, 1, ?)",
            (
                "tenant-synthetic",
                "round-002",
                "case-001",
                control._json(round_two_state),
            ),
        )
        control._db.commit()
        publish_cross_round = command(
            "PublishEvaluationForReview",
            "INTERVIEW_ROUND",
            "round-002",
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
            89,
            WORKFLOW,
        )
        publish_cross_round["target"]["interview_round_id"] = "round-002"
        rejected_round = control.submit(publish_cross_round)
        self.assertEqual("REFERENCE_SCOPE_MISMATCH", rejected_round["error"]["code"])

        awaiting_confirmation = {
            "state": "AWAITING_CONFIRMATION",
            "is_final_round": True,
            "archive": None,
            "synthetic_only": True,
            "current_evaluation_id": "evaluation-001",
            "current_evaluation_version": 1,
            "review_policy_ref": "fixture:review-policy:v1",
            "confirmation_owner_id": "interviewer-1",
        }
        control._db.execute(
            "UPDATE aggregates SET version = 3, state_json = ? WHERE tenant_id = ? "
            "AND aggregate_type = 'INTERVIEW_ROUND' AND aggregate_id = ?",
            (control._json(awaiting_confirmation), "tenant-synthetic", "round-001"),
        )
        control._db.commit()
        stale_version = command(
            "ReachConfirmationQuorum",
            "INTERVIEW_ROUND",
            "round-001",
            3,
            {
                "evaluation_id": "evaluation-001",
                "evaluation_version": 999,
                "confirmation_ids": ["review-001"],
                "review_policy_ref": "fixture:review-policy:v1",
            },
            90,
            WORKFLOW,
        )
        rejected_version = control.submit(stale_version)
        self.assertEqual("EVALUATION_VERSION_STALE", rejected_version["error"]["code"])

    def test_case_bound_fixture_references_cannot_be_reused_by_another_tenant(self):
        control = build_synthetic_control()
        for aggregate_type, aggregate_id, state in [
            (
                "APPLICATION_CASE",
                "case-002",
                {"stage": "INTERVIEWING", "paused": False, "synthetic_only": True},
            ),
            (
                "INTERVIEW_ROUND",
                "round-002",
                {
                    "state": "PLANNED",
                    "is_final_round": True,
                    "archive": None,
                    "synthetic_only": True,
                },
            ),
        ]:
            control._db.execute(
                "INSERT INTO aggregates (tenant_id, aggregate_type, aggregate_id, "
                "application_case_id, version, lifecycle_epoch, state_json) "
                "VALUES (?, ?, ?, ?, 1, 1, ?)",
                (
                    "tenant-synthetic-2",
                    aggregate_type,
                    aggregate_id,
                    "case-002",
                    control._json(state),
                ),
            )
        control._db.commit()

        workflow_two = actor("SERVICE", "workflow-2", "WORKFLOW_SERVICE")
        ended, imported = copy.deepcopy(build_g1a_happy_path_commands()[:2])
        for envelope in (ended, imported):
            envelope["tenant_id"] = "tenant-synthetic-2"
            envelope["actor_context"] = workflow_two
            envelope["correlation_id"] = "tenant-two-run"
            envelope["target"].update(
                {
                    "application_case_id": "case-002",
                    "interview_round_id": "round-002",
                    "interview_session_id": "session-002",
                }
            )
        ended["command_id"] = "tenant-two-ended"
        ended["idempotency_key"] = "tenant-two:ended:001"
        ended["target"]["aggregate_id"] = "session-002"
        ended["payload"].update(
            {
                "interview_round_id": "round-002",
                "interview_session_id": "session-002",
            }
        )
        imported["command_id"] = "tenant-two-import"
        imported["idempotency_key"] = "tenant-two:import:001"
        imported["target"]["aggregate_id"] = "round-002"
        imported["payload"]["interview_session_id"] = "session-002"

        self.assertEqual("APPLIED", control.submit(ended)["status"])
        rejected = control.submit(imported)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertIn(
            rejected["error"]["code"],
            {"CONSENT_MISSING", "SCORECARD_MISSING", "BINDING_NOT_FOUND"},
        )

    def test_case_bound_fixture_references_cannot_be_reused_by_another_case(self):
        control = build_synthetic_control()
        for aggregate_type, aggregate_id, state in [
            (
                "APPLICATION_CASE",
                "case-other",
                {"stage": "INTERVIEWING", "paused": False, "synthetic_only": True},
            ),
            (
                "INTERVIEW_ROUND",
                "round-other",
                {
                    "state": "PLANNED",
                    "is_final_round": True,
                    "archive": None,
                    "synthetic_only": True,
                },
            ),
        ]:
            control._db.execute(
                "INSERT INTO aggregates (tenant_id, aggregate_type, aggregate_id, "
                "application_case_id, version, lifecycle_epoch, state_json) "
                "VALUES (?, ?, ?, ?, 1, 1, ?)",
                (
                    "tenant-synthetic",
                    aggregate_type,
                    aggregate_id,
                    "case-other",
                    control._json(state),
                ),
            )
        control._db.commit()

        ended, imported = copy.deepcopy(build_g1a_happy_path_commands()[:2])
        for envelope in (ended, imported):
            envelope["correlation_id"] = "case-other-run"
            envelope["target"].update(
                {
                    "application_case_id": "case-other",
                    "interview_round_id": "round-other",
                    "interview_session_id": "session-other",
                }
            )
        ended["command_id"] = "case-other-ended"
        ended["idempotency_key"] = "case-other:ended:001"
        ended["target"]["aggregate_id"] = "session-other"
        ended["payload"].update(
            {
                "interview_round_id": "round-other",
                "interview_session_id": "session-other",
            }
        )
        imported["command_id"] = "case-other-import"
        imported["idempotency_key"] = "case-other:import:001"
        imported["target"]["aggregate_id"] = "round-other"
        imported["payload"]["interview_session_id"] = "session-other"

        self.assertEqual("APPLIED", control.submit(ended)["status"])
        rejected = control.submit(imported)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertIn(
            rejected["error"]["code"],
            {"CONSENT_MISSING", "SCORECARD_MISSING", "BINDING_NOT_FOUND"},
        )

    def test_only_the_round_current_evaluation_can_be_reviewed_or_reach_quorum(self):
        control = build_synthetic_control_at_evidence_processing()
        happy = build_g1a_happy_path_commands()
        draft_one = copy.deepcopy(happy[4])
        draft_two = copy.deepcopy(happy[4])
        draft_two["command_id"] = "cmd-draft-two"
        draft_two["idempotency_key"] = "synthetic:g1a:draft-two"
        draft_two["target"]["aggregate_id"] = "evaluation-002"
        draft_two["payload"].update(
            {
                "evaluation_id": "evaluation-002",
                "draft_ref": "fixture:evaluation:draft:002",
                "claim_manifest_ref": "fixture:evaluation:claims:002",
            }
        )
        self.assertEqual("APPLIED", control.submit(draft_one)["status"])
        self.assertEqual("APPLIED", control.submit(draft_two)["status"])
        self.assertEqual("APPLIED", control.submit(copy.deepcopy(happy[5]))["status"])

        review_two = copy.deepcopy(happy[6])
        review_two["command_id"] = "cmd-review-two"
        review_two["idempotency_key"] = "synthetic:g1a:review-two"
        review_two["target"]["aggregate_id"] = "evaluation-002"
        review_two["payload"].update(
            {"review_id": "review-002", "evaluation_id": "evaluation-002"}
        )
        rejected_review = control.submit(review_two)
        self.assertEqual("REJECTED", rejected_review["status"])
        self.assertEqual(
            "EVALUATION_VERSION_STALE", rejected_review["error"]["code"]
        )

        evaluation_two = control._load_aggregate(
            "tenant-synthetic", "EVALUATION_PACKAGE", "evaluation-002", "case-001"
        )[2]
        evaluation_two["state"] = "CONFIRMED"
        evaluation_two["review"] = {
            "review_id": "review-002",
            "actor_id": "interviewer-1",
            "disposition": "CONFIRM",
        }
        control._db.execute(
            "UPDATE aggregates SET version = 2, state_json = ? WHERE tenant_id = ? "
            "AND aggregate_type = 'EVALUATION_PACKAGE' AND aggregate_id = ?",
            (control._json(evaluation_two), "tenant-synthetic", "evaluation-002"),
        )
        control._db.commit()
        quorum_two = copy.deepcopy(happy[7])
        quorum_two["command_id"] = "cmd-quorum-two"
        quorum_two["idempotency_key"] = "synthetic:g1a:quorum-two"
        quorum_two["payload"].update(
            {
                "evaluation_id": "evaluation-002",
                "confirmation_ids": ["review-002"],
            }
        )
        rejected_quorum = control.submit(quorum_two)
        self.assertEqual("REJECTED", rejected_quorum["status"])
        self.assertEqual(
            "EVALUATION_VERSION_STALE", rejected_quorum["error"]["code"]
        )

    def test_transcript_versions_are_monotonic_and_duplicate_facts_are_not_emitted(self):
        control = build_synthetic_control()
        commands = build_g1a_happy_path_commands()
        for envelope in commands[:3]:
            self.assertEqual("APPLIED", control.submit(copy.deepcopy(envelope))["status"])

        transcript_v2 = copy.deepcopy(commands[3])
        transcript_v2["payload"]["transcript_version"] = 2
        transcript_v2["payload"]["run_id"] = "transcript-run-v2"
        self.assertEqual("APPLIED", control.submit(transcript_v2)["status"])

        stale_v1 = copy.deepcopy(commands[3])
        stale_v1["command_id"] = "cmd-transcript-stale-v1"
        stale_v1["idempotency_key"] = "synthetic:g1a:transcript-stale-v1"
        stale_v1["expected_aggregate_version"] = 3
        rejected_stale = control.submit(stale_v1)
        self.assertEqual("REJECTED", rejected_stale["status"])
        self.assertEqual("EXTERNAL_REVISION_STALE", rejected_stale["error"]["code"])

        duplicate_v2 = copy.deepcopy(transcript_v2)
        duplicate_v2["command_id"] = "cmd-transcript-duplicate-v2"
        duplicate_v2["idempotency_key"] = "synthetic:g1a:transcript-duplicate-v2"
        duplicate_v2["expected_aggregate_version"] = 3
        rejected_duplicate = control.submit(duplicate_v2)
        self.assertEqual("REJECTED", rejected_duplicate["status"])
        self.assertEqual(
            "EXTERNAL_REVISION_STALE", rejected_duplicate["error"]["code"]
        )

        projection = control.read(projection_request())
        self.assertEqual(1, len(projection["sessions"]["session-001"]["transcripts"]))
        self.assertEqual(
            2,
            projection["sessions"]["session-001"]["transcripts"][0][
                "transcript_version"
            ],
        )
        self.assertEqual(4, projection["event_count"])


if __name__ == "__main__":
    unittest.main()
