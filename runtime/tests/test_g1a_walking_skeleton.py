import unittest
from pathlib import Path

from runtime.recruiting_control import RecruitingCaseControl
from runtime.recruiting_control._contract_validation import validate_or_raise
from runtime.recruiting_control.scenario import (
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
from runtime.recruiting_control.synthetic import build_synthetic_control


class G1aWalkingSkeletonTest(unittest.TestCase):
    def test_completed_session_reaches_immutable_round_archive_only_after_human_decision(self):
        control = build_synthetic_control()
        self.assertIsInstance(control, RecruitingCaseControl)
        initial = control.read(projection_request())
        self.assertEqual("PLANNED", initial["rounds"]["round-001"]["state"])
        self.assertEqual(1, initial["rounds"]["round-001"]["version"])
        self.assertTrue(initial["rounds"]["round-001"]["is_final_round"])

        commands = build_g1a_happy_path_commands()
        self.assertEqual(9, len(commands))

        for envelope in commands[:8]:
            result = control.submit(envelope)
            self.assertEqual("APPLIED", result["status"], result)

        before_decision = control.read(projection_request())
        self.assertEqual("AWAITING_OUTCOME", before_decision["rounds"]["round-001"]["state"])
        self.assertIsNone(before_decision["rounds"]["round-001"]["archive"])

        decision = commands[8]
        self.assertEqual("APPLIED", control.submit(decision)["status"])

        completed = control.read(projection_request())
        round_projection = completed["rounds"]["round-001"]
        self.assertEqual("COMPLETED", round_projection["state"])
        self.assertEqual("decision-001", round_projection["archive"]["decision_id"])
        self.assertEqual("FINAL_ROUND_COMPLETE", round_projection["archive"]["decision_type"])
        self.assertEqual("evaluation-001", round_projection["archive"]["evaluation_id"])
        self.assertEqual(1, round_projection["archive"]["evaluation_version"])
        self.assertEqual(SHA_C, round_projection["archive"]["evidence_set_hash"])
        self.assertEqual(["session-001"], round_projection["archive"]["session_ids"])
        self.assertEqual(["artifact-001"], round_projection["archive"]["evidence_artifact_ids"])
        self.assertEqual(
            [
                {
                    "session_id": "session-001",
                    "session_version": 3,
                }
            ],
            round_projection["archive"]["session_versions"],
        )
        self.assertEqual(
            [
                {
                    "artifact_id": "artifact-001",
                    "artifact_version": 1,
                    "checksum": "b" * 64,
                    "session_id": "session-001",
                }
            ],
            round_projection["archive"]["evidence_artifacts"],
        )
        self.assertEqual(
            [
                {
                    "artifact_id": "artifact-001",
                    "artifact_version": 1,
                    "session_id": "session-001",
                    "transcript_id": "transcript-001",
                    "transcript_version": 1,
                }
            ],
            round_projection["archive"]["transcript_versions"],
        )
        self.assertEqual(2, round_projection["archive"]["evaluation_aggregate_version"])
        self.assertEqual(["review-001"], round_projection["archive"]["confirmation_ids"])
        self.assertEqual(5, round_projection["archive"]["decision_record_version"])
        self.assertEqual(1, round_projection["archive"]["lifecycle_epoch"])
        self.assertEqual(
            ["RoundDecisionRecorded", "InterviewRoundCompleted"],
            completed["event_types"][-2:],
        )
        self.assertNotIn("FinalAssessmentPackageReady", completed["event_types"])
        event_schema = (
            Path(__file__).resolve().parents[2]
            / "contracts"
            / "recruiting-agent-g1a-event.schema.json"
        )
        self.assertEqual(10, len(completed["event_envelopes"]))
        for event in completed["event_envelopes"]:
            validate_or_raise(event, event_schema)
            self.assertEqual("INTERNAL", event["data_classification"])
            self.assertEqual("tenant-synthetic", event["tenant_id"])
            self.assertEqual("case-001", event["application_case_id"])

        second_decision = command(
            "RecordRoundDecision",
            "INTERVIEW_ROUND",
            "round-001",
            5,
            {
                "decision_id": "decision-002",
                "decision_type": "STOP_PROCESS",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "decision_basis_ref": "fixture:decision-basis:002",
                "submitted_at": "2026-08-10T10:10:00Z",
            },
            10,
            DECIDER,
        )
        rejected = control.submit(second_decision)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("INVALID_TRANSITION", rejected["error"]["code"])
        unchanged = control.read(projection_request())["rounds"]["round-001"]
        self.assertEqual(5, unchanged["version"])
        self.assertEqual("decision-001", unchanged["archive"]["decision_id"])

    def test_archive_hash_changes_when_an_evidence_artifact_version_is_added(self):
        baseline = build_synthetic_control()
        for envelope in build_g1a_happy_path_commands():
            self.assertEqual("APPLIED", baseline.submit(envelope)["status"])
        baseline_archive = baseline.read(projection_request())["rounds"]["round-001"][
            "archive"
        ]

        revised = build_synthetic_control()
        commands = build_g1a_happy_path_commands()
        for envelope in commands[:4]:
            self.assertEqual("APPLIED", revised.submit(envelope)["status"])
        artifact_v2 = command(
            "RegisterEvidenceArtifact",
            "INTERVIEW_SESSION",
            "session-001",
            3,
            {
                **commands[2]["payload"],
                "artifact_version": 2,
            },
            20,
            EVIDENCE,
        )
        self.assertEqual("APPLIED", revised.submit(artifact_v2)["status"])
        for envelope in commands[4:]:
            self.assertEqual("APPLIED", revised.submit(envelope)["status"])
        revised_archive = revised.read(projection_request())["rounds"]["round-001"][
            "archive"
        ]

        self.assertNotEqual(baseline_archive["archive_hash"], revised_archive["archive_hash"])
        self.assertEqual(
            [1, 2],
            [item["artifact_version"] for item in revised_archive["evidence_artifacts"]],
        )
        self.assertEqual(4, revised_archive["session_versions"][0]["session_version"])

    def test_late_session_evidence_is_rejected_after_confirmation_and_not_archived(self):
        control = build_synthetic_control()
        commands = build_g1a_happy_path_commands()
        for envelope in commands[:8]:
            self.assertEqual("APPLIED", control.submit(envelope)["status"])

        before_late_evidence = control.read(projection_request())
        self.assertEqual(
            "AWAITING_OUTCOME",
            before_late_evidence["rounds"]["round-001"]["state"],
        )
        self.assertEqual(3, before_late_evidence["sessions"]["session-001"]["version"])

        late_transcript = command(
            "RecordTranscriptOutcome",
            "INTERVIEW_SESSION",
            "session-001",
            3,
            {
                **commands[3]["payload"],
                "run_id": "transcript-run-late",
                "transcript_id": "transcript-late",
                "transcript_version": 1,
                "segments_ref": "fixture:transcript:segments:late",
            },
            20,
            EVIDENCE,
        )
        late_artifact = command(
            "RegisterEvidenceArtifact",
            "INTERVIEW_SESSION",
            "session-001",
            3,
            {
                **commands[2]["payload"],
                "artifact_id": "artifact-late",
                "artifact_version": 2,
            },
            21,
            EVIDENCE,
        )

        transcript_result = control.submit(late_transcript)
        artifact_result = control.submit(late_artifact)
        self.assertEqual("REJECTED", transcript_result["status"])
        self.assertEqual("INVALID_TRANSITION", transcript_result["error"]["code"])
        self.assertEqual(
            "transcript.round_not_processing",
            transcript_result["error"]["message_key"],
        )
        self.assertEqual("REJECTED", artifact_result["status"])
        self.assertEqual("INVALID_TRANSITION", artifact_result["error"]["code"])
        self.assertEqual(
            "artifact.round_not_processing",
            artifact_result["error"]["message_key"],
        )

        after_late_evidence = control.read(projection_request())
        self.assertEqual(
            before_late_evidence["sessions"]["session-001"],
            after_late_evidence["sessions"]["session-001"],
        )
        self.assertEqual(
            before_late_evidence["event_count"],
            after_late_evidence["event_count"],
        )

        self.assertEqual("APPLIED", control.submit(commands[8])["status"])
        archive = control.read(projection_request())["rounds"]["round-001"]["archive"]
        self.assertEqual(["artifact-001"], archive["evidence_artifact_ids"])
        self.assertEqual(
            [("artifact-001", 1)],
            [
                (item["artifact_id"], item["artifact_version"])
                for item in archive["evidence_artifacts"]
            ],
        )
        self.assertEqual(
            [("transcript-001", 1)],
            [
                (item["transcript_id"], item["transcript_version"])
                for item in archive["transcript_versions"]
            ],
        )
        self.assertEqual(3, archive["session_versions"][0]["session_version"])


if __name__ == "__main__":
    unittest.main()
