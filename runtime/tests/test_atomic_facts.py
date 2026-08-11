import copy
import sqlite3
import unittest

from runtime.recruiting_control.synthetic import build_synthetic_control
from runtime.tests.test_g1a_walking_skeleton import (
    WORKFLOW,
    actor,
    command,
    projection_request,
)


class AtomicFactsTest(unittest.TestCase):
    def test_external_action_request_result_and_replay_have_one_business_effect(self):
        control = build_synthetic_control()
        request = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-001",
            0,
            {
                "action_id": "action-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:confirmation-owner:interviewer-1",
                "business_revision": "round-001-evaluation-001-v1",
                "payload_ref": "fixture:confirmation-task:001",
                "payload_hash": "e" * 64,
                "risk_class": "LOW",
            },
            30,
            WORKFLOW,
        )

        applied = control.submit(request)
        replayed = control.submit(copy.deepcopy(request))
        self.assertEqual("APPLIED", applied["status"])
        self.assertEqual(["action-001"], applied["requested_action_ids"])
        self.assertEqual("REPLAYED", replayed["status"])
        queued = control.read(projection_request())
        self.assertEqual("REQUESTED", queued["actions"]["action-001"]["state"])
        self.assertEqual(1, queued["outbox_pending_count"])

        connector = actor("SERVICE", "connector-1", "CONNECTOR_SERVICE")
        result = command(
            "RecordExternalActionResult",
            "ACTION_EXECUTION",
            "action-001",
            1,
            {
                "action_id": "action-001",
                "attempt_no": 1,
                "outcome": "SUCCEEDED",
                "connector_receipt_ref": "fixture:connector-receipt:001",
                "external_resource_ref": "fixture:synthetic-delivery:001",
                "observed_at": "2026-08-10T10:31:00Z",
            },
            31,
            connector,
        )
        self.assertEqual("APPLIED", control.submit(result)["status"])
        completed = control.read(projection_request())
        self.assertEqual("SUCCEEDED", completed["actions"]["action-001"]["state"])
        self.assertEqual(1, len(completed["actions"]["action-001"]["attempts"]))
        self.assertEqual(0, completed["outbox_pending_count"])

    def test_schema_invalid_success_receipt_cannot_complete_outbox(self):
        control = build_synthetic_control()
        request = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-schema-001",
            0,
            {
                "action_id": "action-schema-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:confirmation-owner:interviewer-1",
                "business_revision": "round-001-evaluation-001-v1",
                "payload_ref": "fixture:confirmation-task:schema-001",
                "payload_hash": "f" * 64,
                "risk_class": "LOW",
            },
            32,
            WORKFLOW,
        )
        self.assertEqual("APPLIED", control.submit(request)["status"])
        connector = actor("SERVICE", "connector-1", "CONNECTOR_SERVICE")
        invalid_result = command(
            "RecordExternalActionResult",
            "ACTION_EXECUTION",
            "action-schema-001",
            1,
            {
                "action_id": "action-schema-001",
                "attempt_no": 1,
                "outcome": "SUCCEEDED",
                "observed_at": "2026-08-10T10:33:00Z",
            },
            33,
            connector,
        )
        rejected = control.submit(invalid_result)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("SCHEMA_INVALID", rejected["error"]["code"])
        projection = control.read(projection_request())
        self.assertEqual("REQUESTED", projection["actions"]["action-schema-001"]["state"])
        self.assertEqual(1, projection["outbox_pending_count"])

    def test_pause_suppresses_queued_action_and_late_success_cannot_revive_it(self):
        control = build_synthetic_control()
        request = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-paused-001",
            0,
            {
                "action_id": "action-paused-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:confirmation-owner:interviewer-1",
                "business_revision": "round-001-evaluation-001-v1",
                "payload_ref": "fixture:confirmation-task:paused-001",
                "payload_hash": "d" * 64,
                "risk_class": "LOW",
            },
            34,
            WORKFLOW,
        )
        self.assertEqual("APPLIED", control.submit(request)["status"])
        operator = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")
        pause = command(
            "PauseScope",
            "APPLICATION_CASE",
            "case-001",
            1,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason_code": "SYNTHETIC_ACTION_SAFETY",
                "cancellation_token": "cancel-action-paused-001",
                "effective_at": "2026-08-10T10:35:00Z",
            },
            35,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(pause)["status"])
        paused = control.read(projection_request(acting=operator))
        self.assertEqual(0, paused["outbox_pending_count"])
        self.assertEqual(1, paused["outbox_state_counts"]["SUPPRESSED"])
        self.assertIn("ExternalActionSuppressed", paused["event_types"])

        connector = actor("SERVICE", "connector-1", "CONNECTOR_SERVICE")
        late_result = command(
            "RecordExternalActionResult",
            "ACTION_EXECUTION",
            "action-paused-001",
            1,
            {
                "action_id": "action-paused-001",
                "attempt_no": 1,
                "outcome": "SUCCEEDED",
                "connector_receipt_ref": "fixture:connector-receipt:late-001",
                "observed_at": "2026-08-10T10:36:00Z",
            },
            36,
            connector,
        )
        blocked = control.submit(late_result)
        self.assertEqual("CASE_PAUSED_OR_CLOSED", blocked["error"]["code"])

        resume = command(
            "ResumeScope",
            "APPLICATION_CASE",
            "case-001",
            2,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason": "Synthetic action safety review completed",
                "resume_token": paused["case"]["resume_token"],
            },
            37,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(resume)["status"])
        after_resume = copy.deepcopy(late_result)
        after_resume["command_id"] = "cmd-late-after-resume"
        after_resume["idempotency_key"] = "synthetic:g1a:late-after-resume"
        rejected = control.submit(after_resume)
        self.assertEqual("INVALID_TRANSITION", rejected["error"]["code"])
        final = control.read(
            projection_request(
                acting=actor("HUMAN", "privacy-1", "PRIVACY_ADMIN")
            )
        )
        self.assertEqual("SUPPRESSED", final["actions"]["action-paused-001"]["state"])
        self.assertEqual(1, final["outbox_state_counts"]["SUPPRESSED"])

    def test_event_and_outbox_failures_roll_back_all_observable_facts(self):
        event_control = build_synthetic_control()
        event_control._db.execute(
            "CREATE TRIGGER fail_domain_event BEFORE INSERT ON domain_events "
            "BEGIN SELECT RAISE(ABORT, 'forced event failure'); END"
        )
        ended = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-rollback-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-rollback-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:v1",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-rollback-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:rollback-001",
            },
            38,
            WORKFLOW,
        )
        ended["target"]["interview_session_id"] = "session-rollback-001"
        with self.assertRaises(sqlite3.IntegrityError):
            event_control.submit(ended)
        event_projection = event_control.read(projection_request())
        self.assertNotIn("session-rollback-001", event_projection["sessions"])
        self.assertEqual(0, event_projection["event_count"])

        outbox_control = build_synthetic_control()
        outbox_control._db.execute(
            "CREATE TRIGGER fail_outbox BEFORE INSERT ON outbox "
            "BEGIN SELECT RAISE(ABORT, 'forced outbox failure'); END"
        )
        request = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-rollback-001",
            0,
            {
                "action_id": "action-rollback-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:confirmation-owner:interviewer-1",
                "business_revision": "round-001-evaluation-001-v1",
                "payload_ref": "fixture:confirmation-task:rollback-001",
                "payload_hash": "c" * 64,
                "risk_class": "LOW",
            },
            39,
            WORKFLOW,
        )
        with self.assertRaises(sqlite3.IntegrityError):
            outbox_control.submit(request)
        outbox_projection = outbox_control.read(projection_request())
        self.assertNotIn("action-rollback-001", outbox_projection["actions"])
        self.assertEqual(0, outbox_projection["event_count"])
        self.assertEqual(0, outbox_projection["outbox_pending_count"])

    def test_event_and_action_ids_are_isolated_by_tenant(self):
        control = build_synthetic_control()
        control._db.execute(
            "INSERT INTO aggregates (tenant_id, aggregate_type, aggregate_id, "
            "application_case_id, version, lifecycle_epoch, state_json) "
            "VALUES (?, 'APPLICATION_CASE', ?, ?, 1, 1, ?)",
            (
                "tenant-synthetic-2",
                "case-002",
                "case-002",
                control._json(
                    {"stage": "INTERVIEWING", "paused": False, "synthetic_only": True}
                ),
            ),
        )
        control._db.commit()
        with self.assertRaises(PermissionError):
            control.read(
                projection_request(
                    acting=WORKFLOW,
                    tenant_id="tenant-synthetic-2",
                    application_case_id="case-002",
                )
            )
        first = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-shared-001",
            0,
            {
                "action_id": "action-shared-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:owner:shared",
                "business_revision": "shared-revision-v1",
                "payload_ref": "fixture:payload:shared",
                "payload_hash": "a" * 64,
                "risk_class": "LOW",
            },
            40,
            WORKFLOW,
        )
        second = copy.deepcopy(first)
        second["tenant_id"] = "tenant-synthetic-2"
        second["target"]["application_case_id"] = "case-002"
        second["actor_context"] = actor(
            "SERVICE", "workflow-2", "WORKFLOW_SERVICE"
        )
        self.assertEqual("APPLIED", control.submit(first)["status"])
        self.assertEqual("APPLIED", control.submit(second)["status"])
        first_projection = control.read(projection_request())
        second_projection = control.read(
            projection_request(
                acting=actor("HUMAN", "quality-2", "QUALITY_REVIEWER"),
                tenant_id="tenant-synthetic-2",
                application_case_id="case-002",
            )
        )
        self.assertIn("action-shared-001", first_projection["actions"])
        self.assertIn("action-shared-001", second_projection["actions"])
        self.assertEqual(1, first_projection["event_count"])
        self.assertEqual(1, second_projection["event_count"])

    def test_rights_action_survives_pause_and_suppressed_action_can_acknowledge_cancel(self):
        control = build_synthetic_control()
        ordinary = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-ordinary-001",
            0,
            {
                "action_id": "action-ordinary-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:owner:ordinary",
                "business_revision": "ordinary-revision-v1",
                "payload_ref": "fixture:payload:ordinary",
                "payload_hash": "1" * 64,
                "risk_class": "LOW",
            },
            41,
            WORKFLOW,
        )
        rights = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-rights-001",
            0,
            {
                "action_id": "action-rights-001",
                "action_type": "DELETE_DERIVED_DATA",
                "target_ref": "fixture:privacy-request:001",
                "business_revision": "privacy-request-001-v1",
                "payload_ref": "fixture:deletion:payload:001",
                "payload_hash": "2" * 64,
                "risk_class": "HIGH",
            },
            42,
            WORKFLOW,
        )
        self.assertEqual("APPLIED", control.submit(ordinary)["status"])
        self.assertEqual("APPLIED", control.submit(rights)["status"])
        operator = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")
        pause = command(
            "PauseScope",
            "APPLICATION_CASE",
            "case-001",
            1,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason_code": "SYNTHETIC_RIGHTS_CONTINUE",
                "cancellation_token": "cancel-rights-continue-001",
                "effective_at": "2026-08-10T10:43:00Z",
            },
            43,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(pause)["status"])
        paused = control.read(projection_request(acting=operator))
        self.assertEqual("SUPPRESSED", paused["actions"]["action-ordinary-001"]["state"])
        self.assertEqual("REQUESTED", paused["actions"]["action-rights-001"]["state"])
        self.assertEqual(1, paused["outbox_state_counts"]["SUPPRESSED"])
        self.assertEqual(1, paused["outbox_state_counts"]["PENDING"])

        connector = actor("SERVICE", "connector-1", "CONNECTOR_SERVICE")
        rights_result = command(
            "RecordExternalActionResult",
            "ACTION_EXECUTION",
            "action-rights-001",
            1,
            {
                "action_id": "action-rights-001",
                "attempt_no": 1,
                "outcome": "SUCCEEDED",
                "connector_receipt_ref": "fixture:connector-receipt:rights-001",
                "observed_at": "2026-08-10T10:44:00Z",
            },
            44,
            connector,
        )
        self.assertEqual("APPLIED", control.submit(rights_result)["status"])

        cancellation = command(
            "RecordExternalActionResult",
            "ACTION_EXECUTION",
            "action-ordinary-001",
            1,
            {
                "action_id": "action-ordinary-001",
                "attempt_no": 1,
                "outcome": "CANCELLED",
                "error_code": "CONTROL_CANCELLED",
                "retryable": False,
                "observed_at": "2026-08-10T10:45:00Z",
            },
            45,
            connector,
        )
        self.assertEqual("APPLIED", control.submit(cancellation)["status"])
        completed = control.read(projection_request())
        self.assertEqual("SUCCEEDED", completed["actions"]["action-rights-001"]["state"])
        self.assertEqual("CANCELLED", completed["actions"]["action-ordinary-001"]["state"])
        self.assertIn("AutomationActionCancelled", completed["event_types"])

    def test_cancel_ack_uses_the_token_that_suppressed_the_action(self):
        control = build_synthetic_control()
        request = command(
            "RequestExternalAction",
            "ACTION_EXECUTION",
            "action-cancel-token-001",
            0,
            {
                "action_id": "action-cancel-token-001",
                "action_type": "DELIVER_CONFIRMATION_TASK",
                "target_ref": "fixture:owner:cancel-token",
                "business_revision": "cancel-token-revision-v1",
                "payload_ref": "fixture:payload:cancel-token",
                "payload_hash": "4" * 64,
                "risk_class": "LOW",
            },
            47,
            WORKFLOW,
        )
        self.assertEqual("APPLIED", control.submit(request)["status"])
        operator = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")
        first_pause = command(
            "PauseScope",
            "APPLICATION_CASE",
            "case-001",
            1,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason_code": "SYNTHETIC_FIRST_CANCEL",
                "cancellation_token": "cancel-cycle-one",
                "effective_at": "2026-08-10T10:48:00Z",
            },
            48,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(first_pause)["status"])
        paused = control.read(projection_request(acting=operator))
        resume = command(
            "ResumeScope",
            "APPLICATION_CASE",
            "case-001",
            2,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason": "Synthetic first pause reviewed",
                "resume_token": paused["case"]["resume_token"],
            },
            49,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(resume)["status"])
        second_pause = command(
            "PauseScope",
            "APPLICATION_CASE",
            "case-001",
            3,
            {
                "scope_type": "APPLICATION_CASE",
                "scope_id": "case-001",
                "reason_code": "SYNTHETIC_SECOND_CANCEL",
                "cancellation_token": "cancel-cycle-two",
                "effective_at": "2026-08-10T10:50:00Z",
            },
            50,
            operator,
        )
        self.assertEqual("APPLIED", control.submit(second_pause)["status"])
        cancellation = command(
            "RecordExternalActionResult",
            "ACTION_EXECUTION",
            "action-cancel-token-001",
            1,
            {
                "action_id": "action-cancel-token-001",
                "attempt_no": 1,
                "outcome": "CANCELLED",
                "error_code": "CONTROL_CANCELLED",
                "retryable": False,
                "observed_at": "2026-08-10T10:51:00Z",
            },
            51,
            actor("SERVICE", "connector-1", "CONNECTOR_SERVICE"),
        )
        self.assertEqual("APPLIED", control.submit(cancellation)["status"])
        final = control.read(
            projection_request(
                acting=actor("HUMAN", "privacy-1", "PRIVACY_ADMIN")
            )
        )
        cancelled_event = next(
            event
            for event in final["event_envelopes"]
            if event["event_type"] == "AutomationActionCancelled"
        )
        self.assertEqual(
            "cancel-cycle-one", cancelled_event["payload"]["cancellation_token"]
        )
        self.assertEqual(
            "cancel-cycle-one",
            final["actions"]["action-cancel-token-001"]["cancellation_token"],
        )

    def test_reused_command_id_with_another_idempotency_key_is_structured_rejection(self):
        control = build_synthetic_control()
        original = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-command-id-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-command-id-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:command-id",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-command-id-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:command-id-001",
            },
            46,
            WORKFLOW,
        )
        original["target"]["interview_session_id"] = "session-command-id-001"
        self.assertEqual("APPLIED", control.submit(original)["status"])
        reused = copy.deepcopy(original)
        reused["idempotency_key"] = "synthetic:g1a:another-key-for-same-command"
        rejected = control.submit(reused)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("IDEMPOTENCY_KEY_REUSED", rejected["error"]["code"])
        projection = control.read(projection_request())
        self.assertEqual(1, projection["event_count"])


if __name__ == "__main__":
    unittest.main()
