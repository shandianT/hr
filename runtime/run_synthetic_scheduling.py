#!/usr/bin/env python3
"""Run bounded synthetic interview-scheduling acceptance scenarios."""

import json

from recruiting_scheduling import (
    SyntheticSchedulingAdapters,
    build_synthetic_scheduling,
)
from recruiting_scheduling.scenario import (
    BOOKING_RESOURCE_KINDS,
    commit_booking_command,
    execute_action_command,
    open_coordination_command,
    operations_request,
    propose_appointment_command,
    publish_proposal_command,
    queue_action_command,
    reconcile_action_command,
    record_recording_notice_delivery_command,
    record_selection_command,
)


def main() -> None:
    normal = build_synthetic_scheduling()
    _require(normal.submit(open_coordination_command(normal, suffix="runner")))
    _require(normal.submit(publish_proposal_command(normal, suffix="runner")))
    selection = normal.submit(record_selection_command(normal, suffix="runner"))
    _require(selection)
    before_booking = normal.read(operations_request(normal))
    _require(normal.submit(propose_appointment_command(normal, suffix="runner")))
    for resource_kind in BOOKING_RESOURCE_KINDS:
        queued = normal.submit(
            queue_action_command(normal, resource_kind, suffix="runner")
        )
        _require(queued)
        _require(
            normal.submit(
                execute_action_command(
                    normal,
                    queued["data"]["action_id"],
                    suffix="runner-{}".format(resource_kind.lower()),
                )
            )
        )
    committed = normal.submit(commit_booking_command(normal, suffix="runner"))
    _require(committed)
    _require(
        normal.submit(
            record_recording_notice_delivery_command(normal, suffix="runner")
        )
    )
    normal_projection = normal.read(operations_request(normal))
    normal_session = next(iter(normal_projection["interview_sessions"].values()))

    lost_adapters = SyntheticSchedulingAdapters()
    lost = build_synthetic_scheduling(adapters=lost_adapters)
    _require(lost.submit(open_coordination_command(lost, suffix="runner-lost")))
    _require(lost.submit(publish_proposal_command(lost, suffix="runner-lost")))
    _require(lost.submit(record_selection_command(lost, suffix="runner-lost")))
    _require(lost.submit(propose_appointment_command(lost, suffix="runner-lost")))
    queued = lost.submit(
        queue_action_command(lost, "CALENDAR_EVENT", suffix="runner-lost")
    )
    _require(queued)
    lost_adapters.calendar.lose_next_success_response()
    unknown = lost.submit(
        execute_action_command(
            lost, queued["data"]["action_id"], suffix="runner-lost"
        )
    )
    _require(unknown)
    reconciled = lost.submit(
        reconcile_action_command(
            lost, queued["data"]["action_id"], suffix="runner-lost"
        )
    )
    _require(reconciled)
    lost_projection = lost.read(operations_request(lost))

    if before_booking["synthetic_external_effect_count"] != 0:
        raise AssertionError("candidate selection unexpectedly wrote a provider resource")
    if normal_session["scheduling_state"] != "BOOKED":
        raise AssertionError("three current receipts did not commit one Booking")
    if normal_projection["consent_receipt_count"] != 0:
        raise AssertionError("recording notice delivery created consent")
    if unknown["data"]["effect"] != "ACTION_OUTCOME_UNKNOWN":
        raise AssertionError(unknown)
    if reconciled["data"]["effect"] != "ACTION_RECONCILED":
        raise AssertionError(reconciled)

    print(
        json.dumps(
            {
                "synthetic_only": True,
                "fixture_round_materialized": False,
                "candidate_selection_booking_created": selection["data"][
                    "booking_created"
                ],
                "normal": {
                    "scheduling_state": normal_session["scheduling_state"],
                    "booking_count": len(normal_session["booking_history"]),
                    "resource_effect_counts": normal_projection[
                        "synthetic_resource_effect_counts"
                    ],
                    "recording_notice_delivery_count": normal_projection[
                        "recording_notice_delivery_count"
                    ],
                    "consent_receipt_count": normal_projection[
                        "consent_receipt_count"
                    ],
                },
                "lost_response": {
                    "first_effect": unknown["data"]["effect"],
                    "reconciliation_effect": reconciled["data"]["effect"],
                    "calendar_resource_effect_count": lost_projection[
                        "synthetic_resource_effect_counts"
                    ]["CALENDAR_EVENT"],
                },
                "real_external_effect_count": 0,
                "not_proven": [
                    "real_calendar_or_meeting_connectors",
                    "real_invitation_delivery_or_read",
                    "real_candidate_authentication",
                    "materialized_interview_plan_or_round",
                    "production_outbox_or_distributed_worker",
                ],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )


def _require(result):
    if result["status"] != "APPLIED":
        raise AssertionError(result)


if __name__ == "__main__":
    main()
