"""Public-seam walking skeleton for synthetic interview scheduling."""

import sqlite3
import unittest
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from runtime.recruiting_scheduling.control import RecruitingSchedulingControl
from runtime.recruiting_scheduling.scenario import (
    BOOKING_RESOURCE_KINDS,
    WORKER_ACTOR,
    WORKFLOW_ACTOR,
    commit_booking_command,
    execute_action_command,
    open_coordination_command,
    operations_request,
    pause_case_command,
    propose_appointment_command,
    publish_proposal_command,
    queue_action_command,
    queue_compensation_command,
    reconcile_action_command,
    record_recording_notice_delivery_command,
    record_provider_observation_command,
    record_selection_command,
    supersede_appointment_command,
)
from runtime.recruiting_scheduling.synthetic import (
    SyntheticSchedulingAdapters,
    build_synthetic_scheduling,
)
from runtime.recruiting_screening.synthetic import SyntheticClock


class SchedulingWalkingSkeletonTest(unittest.TestCase):
    def test_selection_is_not_booking_and_three_current_receipts_commit_once(self):
        adapters = SyntheticSchedulingAdapters()
        control = build_synthetic_scheduling(adapters=adapters)

        opened = control.submit(open_coordination_command(control, suffix="normal"))
        self.assertEqual("APPLIED", opened["status"])
        forged_publish = publish_proposal_command(control, suffix="normal-forged")
        forged_publish["payload"]["coordination_request_revision"] = True
        rejected = control.submit(forged_publish)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("INVALID_SCHEDULING_PAYLOAD", rejected["error"]["code"])
        published = control.submit(publish_proposal_command(control, suffix="normal"))
        self.assertEqual("APPLIED", published["status"])
        selected = control.submit(record_selection_command(control, suffix="normal"))
        self.assertEqual("APPLIED", selected["status"])

        projection = control.read(operations_request(control))
        session = _ops_session(control, projection)
        self.assertEqual("PROPOSAL_OPEN", session["scheduling_state"])
        self.assertIsNone(session["current_booking"])
        self.assertEqual(0, projection["synthetic_external_effect_count"])

        proposed = control.submit(propose_appointment_command(control, suffix="normal"))
        self.assertEqual("APPLIED", proposed["status"])
        action_ids = {}
        for resource_kind in BOOKING_RESOURCE_KINDS:
            queued = control.submit(
                queue_action_command(control, resource_kind, suffix="normal")
            )
            self.assertEqual("APPLIED", queued["status"])
            action_ids[resource_kind] = queued["data"]["action_id"]

        for resource_kind in BOOKING_RESOURCE_KINDS[:2]:
            executed = control.submit(
                execute_action_command(
                    control,
                    action_ids[resource_kind],
                    suffix="normal-{}".format(resource_kind.lower()),
                )
            )
            self.assertEqual("APPLIED", executed["status"])

        incomplete = control.submit(commit_booking_command(control, suffix="incomplete"))
        self.assertEqual("REJECTED", incomplete["status"])
        self.assertEqual("BOOKING_RECEIPTS_INCOMPLETE", incomplete["error"]["code"])

        invitation_kind = BOOKING_RESOURCE_KINDS[-1]
        delivered = control.submit(
            execute_action_command(
                control,
                action_ids[invitation_kind],
                suffix="normal-invitation",
            )
        )
        self.assertEqual("APPLIED", delivered["status"])
        boolean_revision = commit_booking_command(
            control, suffix="normal-boolean-revision"
        )
        boolean_revision["payload"]["appointment_revision"] = True
        rejected = control.submit(boolean_revision)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("INVALID_SCHEDULING_PAYLOAD", rejected["error"]["code"])
        committed = control.submit(commit_booking_command(control, suffix="normal"))
        self.assertEqual("APPLIED", committed["status"])

        late_observation = adapters.calendar.callback_observation(
            action_ids["CALENDAR_EVENT"]
        )
        late_observation["provider_event_id"] += ":after-booking"
        late_callback = control.submit(
            record_provider_observation_command(
                control,
                action_ids["CALENDAR_EVENT"],
                late_observation,
                suffix="normal-late-callback",
            )
        )
        self.assertEqual("APPLIED", late_callback["status"])
        self.assertEqual(
            "PROVIDER_OBSERVATION_RECORDED", late_callback["data"]["effect"]
        )
        current_compensation = control.submit(
            queue_compensation_command(
                control,
                action_ids["CALENDAR_EVENT"],
                suffix="normal-current-booking-cancel",
            )
        )
        self.assertEqual("REJECTED", current_compensation["status"])
        self.assertEqual(
            "SAFETY_COMPENSATION_NOT_ALLOWED",
            current_compensation["error"]["code"],
        )

        projection = control.read(operations_request(control))
        session = _ops_session(control, projection)
        self.assertEqual("BOOKED", session["scheduling_state"])
        self.assertEqual(1, len(session["booking_history"]))
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["CALENDAR_EVENT"])
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["MEETING_RESOURCE"])
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["INVITATION_WRITE"])
        self.assertEqual(0, projection["invitation_delivery_receipt_count"])
        self.assertEqual(0, projection["invitation_read_receipt_count"])
        self.assertEqual(0, projection["synthetic_calendar_cancellation_count"])
        self.assertEqual(0, projection["real_external_effect_count"])

    def test_wrong_and_cross_tenant_invitation_recipients_are_blocked_before_action_creation(self):
        bad_recipients = (
            {
                "tenant_id": "tenant-other",
                "participant_id": "candidate-lina",
                "role": "CANDIDATE",
            },
            {
                "tenant_id": "tenant-synthetic",
                "participant_id": "candidate-other",
                "role": "CANDIDATE",
            },
        )
        for index, recipient in enumerate(bad_recipients):
            with self.subTest(recipient=recipient):
                control = build_synthetic_scheduling()
                _run_to_pending_appointment(control, suffix="recipient-{}".format(index))

                unknown_field = queue_action_command(
                    control,
                    "CALENDAR_EVENT",
                    suffix="recipient-{}-unknown-field".format(index),
                )
                unknown_field["payload"]["unexpected"] = "must-not-pass"
                rejected = control.submit(unknown_field)
                self.assertEqual("REJECTED", rejected["status"])
                self.assertEqual(
                    "INVALID_SCHEDULING_PAYLOAD", rejected["error"]["code"]
                )

                wrong_case = queue_action_command(
                    control,
                    "CALENDAR_EVENT",
                    suffix="recipient-{}-wrong-case".format(index),
                )
                wrong_case["payload"]["application_case_id"] = "case-other"
                rejected = control.submit(wrong_case)
                self.assertEqual("REJECTED", rejected["status"])
                self.assertEqual("ACTION_SCOPE_MISMATCH", rejected["error"]["code"])

                boolean_revision = queue_action_command(
                    control,
                    "CALENDAR_EVENT",
                    suffix="recipient-{}-boolean-revision".format(index),
                )
                boolean_revision["payload"]["appointment_revision"] = True
                rejected = control.submit(boolean_revision)
                self.assertEqual("REJECTED", rejected["status"])
                self.assertEqual(
                    "INVALID_SCHEDULING_PAYLOAD", rejected["error"]["code"]
                )

                result = control.submit(
                    queue_action_command(
                        control,
                        "INVITATION_WRITE",
                        suffix="recipient-{}".format(index),
                        recipient_ref=recipient,
                    )
                )

                self.assertEqual("REJECTED", result["status"])
                self.assertEqual("RECIPIENT_SCOPE_MISMATCH", result["error"]["code"])
                projection = control.read(operations_request(control))
                self.assertEqual([], projection["scheduling_action_executions"])
                self.assertEqual(0, projection["synthetic_external_effect_count"])

    def test_expired_proposal_cannot_record_candidate_selection(self):
        clock = SyntheticClock("2026-08-11T12:00:00Z")
        control = build_synthetic_scheduling(clock=clock)
        self.assertEqual(
            "APPLIED",
            control.submit(open_coordination_command(control, suffix="expired"))["status"],
        )
        self.assertEqual(
            "APPLIED",
            control.submit(publish_proposal_command(control, suffix="expired"))["status"],
        )
        stale_credential = record_selection_command(
            control, suffix="expired-stale-credential"
        )
        stale_credential["payload"]["coordination_credential_revision"] = 0
        rejected = control.submit(stale_credential)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("COORDINATION_CREDENTIAL_STALE", rejected["error"]["code"])
        boolean_version = record_selection_command(
            control, suffix="expired-boolean-version"
        )
        boolean_version["payload"]["proposal_version"] = True
        rejected = control.submit(boolean_version)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("INVALID_SCHEDULING_PAYLOAD", rejected["error"]["code"])
        clock.set("2026-08-11T12:31:00Z")

        result = control.submit(record_selection_command(control, suffix="expired"))

        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("PROPOSAL_EXPIRED", result["error"]["code"])
        session = _ops_session(control)
        self.assertIsNone(session["current_selection"])
        self.assertEqual("PROPOSAL_OPEN", session["scheduling_state"])

    def test_availability_change_after_selection_blocks_appointment_and_all_writes(self):
        adapters = SyntheticSchedulingAdapters()
        control = build_synthetic_scheduling(adapters=adapters)
        self.assertEqual(
            "APPLIED",
            control.submit(open_coordination_command(control, suffix="conflict"))["status"],
        )
        self.assertEqual(
            "APPLIED",
            control.submit(publish_proposal_command(control, suffix="conflict"))["status"],
        )
        self.assertEqual(
            "APPLIED",
            control.submit(record_selection_command(control, suffix="conflict"))["status"],
        )
        stale_selection = propose_appointment_command(
            control, suffix="conflict-stale-selection"
        )
        stale_selection["payload"]["selection_action_id"] = "selection:forged"
        rejected = control.submit(stale_selection)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("STALE_SELECTION_REVISION", rejected["error"]["code"])
        offered_slot = deepcopy(_ops_session(control)["current_proposal"]["slots"][0])
        offered_slot["starts_at"] = "2026-08-18T05:00:00Z"
        offered_slot["ends_at"] = "2026-08-18T06:00:00Z"
        adapters.calendar.replace_availability([offered_slot])

        result = control.submit(propose_appointment_command(control, suffix="conflict"))

        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("SLOT_CONFLICT", result["error"]["code"])
        projection = control.read(operations_request(control))
        session = _ops_session(control, projection)
        self.assertIsNone(session["pending_appointment_revision"])
        self.assertEqual([], projection["scheduling_action_executions"])
        self.assertEqual(0, projection["synthetic_external_effect_count"])

    def test_provider_success_with_lost_response_requires_reconciliation_not_rewrite(self):
        adapters = SyntheticSchedulingAdapters()
        control = build_synthetic_scheduling(adapters=adapters)
        _run_to_pending_appointment(control, suffix="lost-response")
        queued = control.submit(
            queue_action_command(control, "CALENDAR_EVENT", suffix="lost-response")
        )
        self.assertEqual("APPLIED", queued["status"])
        action_id = queued["data"]["action_id"]
        boolean_version = execute_action_command(
            control, action_id, suffix="lost-response-boolean-version"
        )
        boolean_version["payload"]["expected_action_version"] = True
        rejected = control.submit(boolean_version)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("INVALID_SCHEDULING_PAYLOAD", rejected["error"]["code"])
        self.assertEqual(0, adapters.calendar.effect_count(control.synthetic_case_id))
        adapters.calendar.lose_next_success_response()

        unknown = control.submit(
            execute_action_command(control, action_id, suffix="lost-response")
        )

        self.assertEqual("APPLIED", unknown["status"])
        self.assertEqual("ACTION_OUTCOME_UNKNOWN", unknown["data"]["effect"])
        projection = control.read(operations_request(control))
        self.assertEqual("OUTCOME_UNKNOWN", projection["scheduling_action_executions"][0]["state"])
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["CALENDAR_EVENT"])

        retry = control.submit(
            execute_action_command(control, action_id, suffix="lost-response-retry")
        )
        self.assertEqual("REJECTED", retry["status"])
        self.assertEqual("RECONCILIATION_REQUIRED", retry["error"]["code"])
        self.assertEqual(
            1,
            control.read(operations_request(control))["synthetic_resource_effect_counts"]
            ["CALENDAR_EVENT"],
        )

        reconciled = control.submit(
            reconcile_action_command(control, action_id, suffix="lost-response")
        )
        self.assertEqual("APPLIED", reconciled["status"])
        projection = control.read(operations_request(control))
        self.assertEqual("SUCCEEDED", projection["scheduling_action_executions"][0]["state"])
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["CALENDAR_EVENT"])

    def test_duplicate_provider_callbacks_record_one_receipt_and_one_effect(self):
        adapters = SyntheticSchedulingAdapters()
        control = build_synthetic_scheduling(adapters=adapters)
        _run_to_pending_appointment(control, suffix="duplicate-callback")
        queued = control.submit(
            queue_action_command(control, "CALENDAR_EVENT", suffix="duplicate-callback")
        )
        action_id = queued["data"]["action_id"]
        adapters.calendar.lose_next_success_response()
        self.assertEqual(
            "ACTION_OUTCOME_UNKNOWN",
            control.submit(
                execute_action_command(control, action_id, suffix="duplicate-callback")
            )["data"]["effect"],
        )
        observation = adapters.calendar.callback_observation(action_id)

        missing_receipt_id = deepcopy(observation)
        missing_receipt_id["receipt"].pop("provider_receipt_id")
        rejected = control.submit(
            record_provider_observation_command(
                control,
                action_id,
                missing_receipt_id,
                suffix="duplicate-callback-missing-receipt-id",
            )
        )
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual(
            "PROVIDER_OBSERVATION_SCOPE_MISMATCH", rejected["error"]["code"]
        )

        first = control.submit(
            record_provider_observation_command(
                control,
                action_id,
                observation,
                suffix="duplicate-callback-0",
            )
        )
        self.assertEqual("APPLIED", first["status"])

        stale_receipt = deepcopy(observation)
        stale_receipt["provider_event_id"] = "calendar-callback:stale-receipt"
        stale_receipt["receipt"]["external_resource_revision"] = 0
        stale_receipt["receipt"]["external_resource_ref"] = "calendar-event:stale"
        rejected = control.submit(
            record_provider_observation_command(
                control,
                action_id,
                stale_receipt,
                suffix="duplicate-callback-stale-receipt",
            )
        )
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual(
            "STALE_PROVIDER_RECEIPT_REVISION", rejected["error"]["code"]
        )

        for ordinal in range(1, 10):
            result = control.submit(
                record_provider_observation_command(
                    control,
                    action_id,
                    observation,
                    suffix="duplicate-callback-{}".format(ordinal),
                )
            )
            self.assertEqual("APPLIED", result["status"])

        projection = control.read(operations_request(control))
        action = projection["scheduling_action_executions"][0]
        self.assertEqual("SUCCEEDED", action["state"])
        self.assertEqual(1, len(action["provider_observation_ids"]))
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["CALENDAR_EVENT"])

    def test_old_revision_callback_is_history_and_compensation_not_booking(self):
        for mode in ("callback", "reconcile"):
            with self.subTest(mode=mode):
                adapters = SyntheticSchedulingAdapters()
                control = build_synthetic_scheduling(adapters=adapters)
                suffix = "old-revision-{}".format(mode)
                _run_to_pending_appointment(control, suffix=suffix)
                queued = control.submit(
                    queue_action_command(control, "CALENDAR_EVENT", suffix=suffix)
                )
                old_action_id = queued["data"]["action_id"]
                adapters.calendar.lose_next_success_response()
                control.submit(
                    execute_action_command(control, old_action_id, suffix=suffix)
                )
                old_observation = adapters.calendar.callback_observation(old_action_id)
                self.assertEqual(
                    "APPLIED",
                    control.submit(
                        supersede_appointment_command(control, suffix=suffix)
                    )["status"],
                )
                self.assertEqual(
                    "APPLIED",
                    control.submit(
                        propose_appointment_command(
                            control, suffix="{}-replacement".format(suffix)
                        )
                    )["status"],
                )

                if mode == "callback":
                    observed = control.submit(
                        record_provider_observation_command(
                            control,
                            old_action_id,
                            old_observation,
                            suffix="{}-late-callback".format(suffix),
                        )
                    )
                    expected_effect = "STALE_PROVIDER_OBSERVATION_RECORDED"
                else:
                    observed = control.submit(
                        reconcile_action_command(
                            control,
                            old_action_id,
                            suffix="{}-late-reconcile".format(suffix),
                        )
                    )
                    expected_effect = "STALE_ACTION_RECONCILED"

                self.assertEqual("APPLIED", observed["status"])
                self.assertEqual(expected_effect, observed["data"]["effect"])
                projection = control.read(operations_request(control))
                session = _ops_session(control, projection)
                self.assertEqual(
                    2,
                    session["pending_appointment_revision"]["appointment_revision"],
                )
                self.assertIsNone(session["current_booking"])
                old_action = next(
                    item
                    for item in projection["scheduling_action_executions"]
                    if item["action_id"] == old_action_id
                )
                self.assertEqual("COMPENSATION_REQUIRED", old_action["state"])
                self.assertEqual(
                    1,
                    projection["synthetic_resource_effect_counts"]["CALENDAR_EVENT"],
                )

    def test_case_pause_blocks_production_action_but_allows_calendar_compensation(self):
        adapters = SyntheticSchedulingAdapters()
        control = build_synthetic_scheduling(adapters=adapters)
        _run_to_pending_appointment(control, suffix="pause")
        calendar = control.submit(
            queue_action_command(control, "CALENDAR_EVENT", suffix="pause")
        )
        meeting = control.submit(
            queue_action_command(control, "MEETING_RESOURCE", suffix="pause")
        )
        self.assertEqual(
            "APPLIED",
            control.submit(
                execute_action_command(
                    control, calendar["data"]["action_id"], suffix="pause-calendar"
                )
            )["status"],
        )
        active_compensation = control.submit(
            queue_compensation_command(
                control,
                calendar["data"]["action_id"],
                suffix="active-cancel-calendar",
            )
        )
        self.assertEqual("REJECTED", active_compensation["status"])
        self.assertEqual(
            "SAFETY_COMPENSATION_NOT_ALLOWED",
            active_compensation["error"]["code"],
        )
        self.assertEqual(
            "APPLIED", control.submit(pause_case_command(control, suffix="pause"))["status"]
        )

        paused_queue = control.submit(
            queue_action_command(control, "INVITATION_WRITE", suffix="pause-after-pause")
        )
        self.assertEqual("REJECTED", paused_queue["status"])
        self.assertEqual("CASE_PAUSED_OR_CLOSED", paused_queue["error"]["code"])

        late_observation = adapters.calendar.callback_observation(
            calendar["data"]["action_id"]
        )
        late_observation["provider_event_id"] += ":paused"
        late_callback = control.submit(
            record_provider_observation_command(
                control,
                calendar["data"]["action_id"],
                late_observation,
                suffix="pause-late-callback",
            )
        )
        self.assertEqual("APPLIED", late_callback["status"])
        self.assertEqual(
            "STALE_PROVIDER_OBSERVATION_RECORDED",
            late_callback["data"]["effect"],
        )

        blocked = control.submit(
            execute_action_command(
                control, meeting["data"]["action_id"], suffix="pause-meeting"
            )
        )

        self.assertEqual("APPLIED", blocked["status"])
        self.assertEqual("ACTION_BLOCKED", blocked["data"]["effect"])
        self.assertEqual("CASE_PAUSED_OR_CLOSED", blocked["data"]["reason"])
        projection = control.read(operations_request(control))
        self.assertEqual(1, projection["synthetic_resource_effect_counts"]["CALENDAR_EVENT"])
        self.assertEqual(0, projection["synthetic_resource_effect_counts"]["MEETING_RESOURCE"])

        queued_compensation = control.submit(
            queue_compensation_command(
                control,
                calendar["data"]["action_id"],
                suffix="pause-cancel-calendar",
            )
        )
        self.assertEqual("APPLIED", queued_compensation["status"])
        compensated = control.submit(
            execute_action_command(
                control,
                queued_compensation["data"]["action_id"],
                suffix="pause-cancel-calendar",
            )
        )
        self.assertEqual("APPLIED", compensated["status"])
        projection = control.read(operations_request(control))
        self.assertEqual(1, projection["synthetic_calendar_cancellation_count"])
        self.assertIsNone(
            _ops_session(control, projection)["current_booking"]
        )

    def test_case_pause_after_all_receipts_still_blocks_booking_commit(self):
        control = build_synthetic_scheduling()
        _run_to_pending_appointment(control, suffix="pause-before-commit")
        for resource_kind in BOOKING_RESOURCE_KINDS:
            queued = control.submit(
                queue_action_command(
                    control, resource_kind, suffix="pause-before-commit"
                )
            )
            self.assertEqual(
                "APPLIED",
                control.submit(
                    execute_action_command(
                        control,
                        queued["data"]["action_id"],
                        suffix="pause-before-commit-{}".format(
                            resource_kind.lower()
                        ),
                    )
                )["status"],
            )
        self.assertEqual(
            "APPLIED",
            control.submit(
                pause_case_command(control, suffix="pause-before-commit")
            )["status"],
        )

        result = control.submit(
            commit_booking_command(control, suffix="pause-before-commit")
        )

        self.assertEqual("REJECTED", result["status"])
        self.assertEqual("CASE_PAUSED_OR_CLOSED", result["error"]["code"])
        session = _ops_session(control)
        self.assertIsNone(session["current_booking"])

    def test_two_cases_sharing_calendar_adapter_can_reserve_slot_at_most_once(self):
        adapters = SyntheticSchedulingAdapters()
        first = build_synthetic_scheduling(
            adapters=adapters, recruitment_cycle_id="cycle-2026-shared-a"
        )
        second = build_synthetic_scheduling(
            adapters=adapters, recruitment_cycle_id="cycle-2026-shared-b"
        )
        _run_to_pending_appointment(first, suffix="shared-a")
        _run_to_pending_appointment(second, suffix="shared-b")
        first_action = first.submit(
            queue_action_command(first, "CALENDAR_EVENT", suffix="shared-a")
        )["data"]["action_id"]
        second_action = second.submit(
            queue_action_command(second, "CALENDAR_EVENT", suffix="shared-b")
        )["data"]["action_id"]
        first_command = execute_action_command(first, first_action, suffix="shared-a")
        second_command = execute_action_command(second, second_action, suffix="shared-b")

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(
                pool.map(
                    lambda item: item[0].submit(item[1]),
                    ((first, first_command), (second, second_command)),
                )
            )

        effects = sorted(result["data"]["effect"] for result in results)
        self.assertEqual(
            ["SLOT_RESERVATION_CONFLICT", "SYNTHETIC_RESOURCE_RECEIPT_RECORDED"],
            effects,
        )
        case_effect_counts = [
            control.read(operations_request(control))["synthetic_resource_effect_counts"]
            ["CALENDAR_EVENT"]
            for control in (first, second)
        ]
        expected_case_counts = [
            1
            if result["data"]["effect"] == "SYNTHETIC_RESOURCE_RECEIPT_RECORDED"
            else 0
            for result in results
        ]
        self.assertEqual(expected_case_counts, case_effect_counts)
        sessions = (_ops_session(first), _ops_session(second))
        self.assertTrue(all(session["current_booking"] is None for session in sessions))

    def test_recording_notice_delivery_is_not_invitation_delivery_or_consent(self):
        control = build_synthetic_scheduling()
        _run_to_booked(control, suffix="notice")
        before = control.read(operations_request(control))
        self.assertEqual(1, before["synthetic_resource_effect_counts"]["INVITATION_WRITE"])
        self.assertEqual(0, before["recording_notice_delivery_count"])
        self.assertEqual(0, before["consent_receipt_count"])

        leaking_notice = record_recording_notice_delivery_command(
            control, suffix="notice-extra-field"
        )
        leaking_notice["payload"]["participant_ref"]["email"] = "private@example.test"
        rejected = control.submit(leaking_notice)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual("NOTICE_DELIVERY_SCOPE_MISMATCH", rejected["error"]["code"])

        result = control.submit(
            record_recording_notice_delivery_command(control, suffix="notice")
        )

        self.assertEqual("APPLIED", result["status"])
        projection = control.read(operations_request(control))
        session = _ops_session(control, projection)
        self.assertEqual(1, projection["recording_notice_delivery_count"])
        self.assertEqual(0, projection["consent_receipt_count"])
        self.assertEqual(0, projection["invitation_delivery_receipt_count"])
        self.assertEqual(0, projection["invitation_read_receipt_count"])
        self.assertEqual("UNDECIDED", session["capture_mode"])
        self.assertEqual([], session["consent_receipts"])

    def test_services_read_only_one_case_and_purpose_specific_scheduling_view(self):
        immutable_adapters = SyntheticSchedulingAdapters()
        with self.assertRaises(AttributeError):
            immutable_adapters.calendar = object()
        with self.assertRaises(TypeError):
            SyntheticSchedulingAdapters(calendar=object())
        connection = sqlite3.connect(":memory:")
        try:
            with self.assertRaises(TypeError):
                RecruitingSchedulingControl(connection, adapters=object())
        finally:
            connection.close()

        tampered = build_synthetic_scheduling()
        pending_command = open_coordination_command(
            tampered, suffix="tampered-adapter"
        )
        tampered._adapters = object()
        rejected = tampered.submit(pending_command)
        self.assertEqual("REJECTED", rejected["status"])
        self.assertEqual(
            "SYNTHETIC_ADAPTER_BOUNDARY_VIOLATION", rejected["error"]["code"]
        )
        with self.assertRaises(RuntimeError):
            tampered.read(operations_request(tampered))

        control = build_synthetic_scheduling()
        ops = control.read(operations_request(control))
        session_id = next(iter(ops["interview_sessions"]))
        requests = (
            (WORKFLOW_ACTOR, "SCHEDULING_CASE_CONTEXT"),
            (WORKER_ACTOR, "BOOKING_RECONCILIATION_VIEW"),
        )
        for actor, view in requests:
            with self.subTest(view=view):
                result = control.read(
                    {
                        "tenant_id": "tenant-synthetic",
                        "application_case_id": control.synthetic_case_id,
                        "interview_session_id": session_id,
                        "view": view,
                        "actor_context": actor,
                    }
                )
                self.assertEqual(control.synthetic_case_id, result["application_case_id"])
                self.assertEqual(session_id, result["session"]["session_id"])
                text = str(result).casefold()
                for prohibited in (
                    "raw_text",
                    "match_assessments",
                    "department_decisions",
                    "filename",
                    "email",
                    "phone",
                ):
                    self.assertNotIn(prohibited, text)

        with self.assertRaises(PermissionError):
            control.read(
                {
                    "tenant_id": "tenant-synthetic",
                    "interview_session_id": session_id,
                    "view": "SCHEDULING_CASE_CONTEXT",
                    "actor_context": WORKFLOW_ACTOR,
                }
            )
        with self.assertRaises(PermissionError):
            control.read(
                {
                    "tenant_id": "tenant-other",
                    "application_case_id": control.synthetic_case_id,
                    "interview_session_id": session_id,
                    "view": "SCHEDULING_CASE_CONTEXT",
                    "actor_context": WORKFLOW_ACTOR,
                }
            )


def _ops_session(control, projection=None):
    current = projection or control.read(operations_request(control))
    sessions = current["interview_sessions"]
    if len(sessions) != 1:
        raise AssertionError("fixture must expose exactly one InterviewSession")
    return next(iter(sessions.values()))


def _run_to_pending_appointment(control, *, suffix):
    opened = control.submit(open_coordination_command(control, suffix=suffix))
    if opened["status"] != "APPLIED":
        raise AssertionError(opened)
    published = control.submit(publish_proposal_command(control, suffix=suffix))
    if published["status"] != "APPLIED":
        raise AssertionError(published)
    selected = control.submit(record_selection_command(control, suffix=suffix))
    if selected["status"] != "APPLIED":
        raise AssertionError(selected)
    proposed = control.submit(propose_appointment_command(control, suffix=suffix))
    if proposed["status"] != "APPLIED":
        raise AssertionError(proposed)


def _run_to_booked(control, *, suffix):
    _run_to_pending_appointment(control, suffix=suffix)
    for resource_kind in BOOKING_RESOURCE_KINDS:
        queued = control.submit(
            queue_action_command(control, resource_kind, suffix=suffix)
        )
        if queued["status"] != "APPLIED":
            raise AssertionError(queued)
        executed = control.submit(
            execute_action_command(
                control,
                queued["data"]["action_id"],
                suffix="{}-{}".format(suffix, resource_kind.lower()),
            )
        )
        if executed["status"] != "APPLIED":
            raise AssertionError(executed)
    committed = control.submit(commit_booking_command(control, suffix=suffix))
    if committed["status"] != "APPLIED":
        raise AssertionError(committed)


if __name__ == "__main__":
    unittest.main()
