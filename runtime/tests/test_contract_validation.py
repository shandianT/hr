import copy
import unittest
from pathlib import Path

from runtime.recruiting_control._contract_validation import validate_or_raise
from runtime.recruiting_control.synthetic import build_synthetic_control


CONTROL_SCHEMA = (
    Path(__file__).resolve().parents[2]
    / "contracts"
    / "recruiting-agent-g1a-control.schema.json"
)


def completed_session_command():
    return {
        "schema_version": "1.0.0",
        "command_id": "cmd-contract-001",
        "command_type": "RegisterCompletedSessionFact",
        "tenant_id": "tenant-synthetic",
        "target": {
            "aggregate_type": "INTERVIEW_SESSION",
            "aggregate_id": "session-001",
            "application_case_id": "case-001",
            "interview_round_id": "round-001",
            "interview_session_id": "session-001",
        },
        "expected_aggregate_version": 0,
        "lifecycle_epoch": 1,
        "idempotency_key": "contract:completed-session:001",
        "correlation_id": "run-contract-001",
        "requested_at": "2026-08-10T10:01:00Z",
        "actor_context": {
            "actor_type": "SERVICE",
            "actor_id": "workflow-1",
            "role": "WORKFLOW_SERVICE",
            "authority_snapshot_id": "authority:workflow-1:v1",
            "authn_context_id": "authn:workflow-1:session-1",
        },
        "payload": {
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
    }


class ContractValidationTest(unittest.TestCase):
    def test_valid_command_passes(self):
        validate_or_raise(completed_session_command(), CONTROL_SCHEMA)

    def test_max_length_command_id_still_returns_a_valid_applied_result(self):
        control = build_synthetic_control()
        command = completed_session_command()
        command["command_id"] = "a" * 128
        command["idempotency_key"] = "contract:max-command-id:001"

        result = control.submit(command)

        self.assertEqual("APPLIED", result["status"])
        self.assertEqual(1, len(result["emitted_event_ids"]))
        self.assertLessEqual(len(result["emitted_event_ids"][0]), 128)
        validate_or_raise(result, CONTROL_SCHEMA)

    def test_missing_completed_session_end_time_is_rejected(self):
        command = completed_session_command()
        del command["payload"]["ended_at"]

        with self.assertRaises(ValueError):
            validate_or_raise(command, CONTROL_SCHEMA)

    def test_succeeded_external_action_requires_connector_receipt(self):
        command = copy.deepcopy(completed_session_command())
        command.update(
            {
                "command_id": "cmd-contract-002",
                "command_type": "RecordExternalActionResult",
                "idempotency_key": "contract:external-result:002",
                "actor_context": {
                    "actor_type": "SERVICE",
                    "actor_id": "connector-1",
                    "role": "CONNECTOR_SERVICE",
                    "authority_snapshot_id": "authority:connector-1:v1",
                    "authn_context_id": "authn:connector-1:session-1",
                },
                "target": {
                    "aggregate_type": "ACTION_EXECUTION",
                    "aggregate_id": "action-001",
                    "application_case_id": "case-001",
                },
                "payload": {
                    "action_id": "action-001",
                    "attempt_no": 1,
                    "outcome": "SUCCEEDED",
                    "observed_at": "2026-08-10T10:02:00Z",
                },
            }
        )

        with self.assertRaises(ValueError):
            validate_or_raise(command, CONTROL_SCHEMA)

    def test_control_returns_a_contract_valid_result_for_malformed_input(self):
        control = build_synthetic_control()
        result = control.submit({"bad": True})
        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("SCHEMA_INVALID", result["error"]["code"])
        validate_or_raise(result, CONTROL_SCHEMA)

    def test_additional_properties_and_failed_result_condition_are_enforced(self):
        command = completed_session_command()
        command["unexpected"] = True
        with self.assertRaises(ValueError):
            validate_or_raise(command, CONTROL_SCHEMA)

        failed_result = copy.deepcopy(completed_session_command())
        failed_result.update(
            {
                "command_id": "cmd-contract-003",
                "command_type": "RecordExternalActionResult",
                "idempotency_key": "contract:external-result:003",
                "actor_context": {
                    "actor_type": "SERVICE",
                    "actor_id": "connector-1",
                    "role": "CONNECTOR_SERVICE",
                    "authority_snapshot_id": "authority:connector-1:v1",
                    "authn_context_id": "authn:connector-1:session-1",
                },
                "target": {
                    "aggregate_type": "ACTION_EXECUTION",
                    "aggregate_id": "action-001",
                    "application_case_id": "case-001",
                },
                "payload": {
                    "action_id": "action-001",
                    "attempt_no": 1,
                    "outcome": "FAILED",
                    "observed_at": "2026-08-10T10:03:00Z",
                },
            }
        )
        with self.assertRaises(ValueError):
            validate_or_raise(failed_result, CONTROL_SCHEMA)

    def test_rfc3339_lowercase_separator_and_published_leap_second_are_accepted(self):
        lowercase = completed_session_command()
        lowercase["requested_at"] = "2026-08-10t10:01:00z"
        validate_or_raise(lowercase, CONTROL_SCHEMA)

        leap_second = completed_session_command()
        leap_second["requested_at"] = "1990-12-31T23:59:60Z"
        validate_or_raise(leap_second, CONTROL_SCHEMA)

        invalid_leap_second = completed_session_command()
        invalid_leap_second["requested_at"] = "2026-08-10T10:01:60Z"
        with self.assertRaises(ValueError):
            validate_or_raise(invalid_leap_second, CONTROL_SCHEMA)


if __name__ == "__main__":
    unittest.main()
