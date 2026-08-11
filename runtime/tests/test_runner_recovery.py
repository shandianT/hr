import os
import copy
import tempfile
import unittest

from runtime.recruiting_control.runner import DeterministicWorkflowRunner, SimulatedRunnerCrash
from runtime.recruiting_control.synthetic import build_synthetic_control
from runtime.tests.test_g1a_walking_skeleton import (
    DECIDER,
    WORKFLOW,
    actor,
    command,
    projection_request,
)


class RunnerRecoveryTest(unittest.TestCase):
    def test_command_committed_before_checkpoint_replays_after_runner_restart(self):
        control = build_synthetic_control()
        automatic_step = command(
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
            40,
            WORKFLOW,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            checkpoint_path = os.path.join(temp_dir, "runner.sqlite3")
            runner = DeterministicWorkflowRunner(control, checkpoint_path)
            run_id = runner.start("g1a-synthetic-v1", [automatic_step])
            started = runner.read_run(run_id)
            checkpointed_step_id = started["next_step_id"]
            self.assertIsNotNone(checkpointed_step_id)
            self.assertIsNone(started["current_step_id"])

            with self.assertRaises(SimulatedRunnerCrash):
                runner.tick(run_id, simulate_crash_after_submit=True)

            crashed = runner.read_run(run_id)
            self.assertEqual(checkpointed_step_id, crashed["next_step_id"])
            self.assertIsNone(crashed["current_step_id"])

            after_crash = control.read(projection_request())
            self.assertEqual(1, after_crash["event_count"])
            self.assertEqual(1, after_crash["sessions"]["session-001"]["version"])

            restarted = DeterministicWorkflowRunner(control, checkpoint_path)
            progress = restarted.tick(run_id)
            self.assertEqual("REPLAYED", progress["last_command_status"])
            self.assertEqual("COMPLETED", progress["state"])
            self.assertEqual(1, progress["next_step_index"])
            self.assertEqual(checkpointed_step_id, progress["current_step_id"])
            self.assertIsNone(progress["next_step_id"])
            after_recovery = control.read(projection_request())
            self.assertEqual(1, after_recovery["event_count"])

    def test_runner_can_resume_a_paused_step_with_a_new_run_epoch(self):
        control = build_synthetic_control()
        automatic_step = command(
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
                "source_event_id": "meeting-ended-resume-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:resume-001",
            },
            44,
            WORKFLOW,
        )
        operator = actor("HUMAN", "ops-1", "RECRUITING_OPS_ADMIN")

        with tempfile.TemporaryDirectory() as temp_dir:
            runner = DeterministicWorkflowRunner(
                control, os.path.join(temp_dir, "runner.sqlite3")
            )
            run_id = runner.start("g1a-pause-resume-v1", [automatic_step])
            step_id = runner.read_run(run_id)["next_step_id"]

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
                    "effective_at": "2026-08-10T10:45:00Z",
                },
                45,
                operator,
            )
            self.assertEqual("APPLIED", control.submit(pause)["status"])

            blocked = runner.tick(run_id)
            self.assertEqual("NEEDS_HUMAN", blocked["state"])
            self.assertEqual("REJECTED", blocked["last_command_status"])
            self.assertEqual(1, blocked["run_epoch"])
            self.assertIsNone(blocked["current_step_id"])
            self.assertEqual(step_id, blocked["next_step_id"])

            paused_case = control.read(
                projection_request(acting=operator)
            )["case"]
            resume_scope = command(
                "ResumeScope",
                "APPLICATION_CASE",
                "case-001",
                2,
                {
                    "scope_type": "APPLICATION_CASE",
                    "scope_id": "case-001",
                    "reason": "Synthetic safety review completed",
                    "resume_token": paused_case["resume_token"],
                },
                46,
                operator,
            )
            self.assertEqual("APPLIED", control.submit(resume_scope)["status"])

            restarted = DeterministicWorkflowRunner(
                control, os.path.join(temp_dir, "runner.sqlite3")
            )
            resumed = restarted.resume(
                run_id, resumed_at="2026-08-10T10:47:00Z"
            )
            self.assertEqual("RUNNING", resumed["state"])
            self.assertEqual(2, resumed["run_epoch"])
            self.assertIsNone(resumed["last_command_status"])
            self.assertIsNone(resumed["current_step_id"])
            self.assertEqual(step_id, resumed["next_step_id"])

            completed = restarted.tick(run_id)
            self.assertEqual("COMPLETED", completed["state"])
            self.assertEqual("APPLIED", completed["last_command_status"])
            self.assertEqual(2, completed["run_epoch"])
            self.assertEqual(step_id, completed["current_step_id"])
            self.assertIsNone(completed["next_step_id"])

            projection = control.read(projection_request())
            self.assertEqual(1, projection["sessions"]["session-001"]["version"])
            self.assertEqual(
                ["CasePaused", "CaseResumed", "InterviewSessionEnded"],
                projection["event_types"],
            )

    def test_runner_refuses_to_start_with_a_human_decision_step(self):
        control = build_synthetic_control()
        human_decision = command(
            "RecordRoundDecision",
            "INTERVIEW_ROUND",
            "round-001",
            1,
            {
                "decision_id": "decision-should-not-run",
                "decision_type": "FINAL_ROUND_COMPLETE",
                "evaluation_id": "evaluation-001",
                "evaluation_version": 1,
                "decision_basis_ref": "fixture:decision-basis:forbidden-runner",
                "submitted_at": "2026-08-10T10:50:00Z",
            },
            41,
            DECIDER,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = DeterministicWorkflowRunner(
                control, os.path.join(temp_dir, "runner.sqlite3")
            )
            with self.assertRaisesRegex(ValueError, "SERVICE commands only"):
                runner.start("g1a-forbidden-human-v1", [human_decision])
        projection = control.read(projection_request())
        self.assertEqual("PLANNED", projection["rounds"]["round-001"]["state"])
        self.assertEqual(0, projection["event_count"])

    def test_runner_refuses_system_actor_as_well_as_human_actor(self):
        control = build_synthetic_control()
        automatic_step = command(
            "RegisterCompletedSessionFact",
            "INTERVIEW_SESSION",
            "session-system-001",
            0,
            {
                "interview_round_id": "round-001",
                "interview_session_id": "session-system-001",
                "ended_at": "2026-08-10T09:45:00Z",
                "participant_snapshot_ref": "fixture:participants:system",
                "source_system": "SYNTHETIC_MEETING",
                "source_event_id": "meeting-ended-system-001",
                "source_resource_version": "1",
                "observed_start_missing": True,
                "occurrence_proof_ref": "fixture:occurrence-proof:system-001",
            },
            47,
            WORKFLOW,
        )
        automatic_step["target"]["interview_session_id"] = "session-system-001"
        system_step = copy.deepcopy(automatic_step)
        system_step["actor_context"]["actor_type"] = "SYSTEM"
        with tempfile.TemporaryDirectory() as temp_dir:
            runner = DeterministicWorkflowRunner(
                control, os.path.join(temp_dir, "runner.sqlite3")
            )
            with self.assertRaisesRegex(ValueError, "SERVICE commands only"):
                runner.start("g1a-forbidden-system-v1", [system_step])


if __name__ == "__main__":
    unittest.main()
