"""Command builders for the synthetic scheduling walking skeleton."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional


TENANT = "tenant-synthetic"
BOOKING_RESOURCE_KINDS = (
    "CALENDAR_EVENT",
    "MEETING_RESOURCE",
    "INVITATION_WRITE",
)
WORKFLOW_ACTOR = {
    "actor_type": "SERVICE",
    "actor_id": "scheduling-workflow",
    "role": "SCHEDULING_WORKFLOW",
}
WORKER_ACTOR = {
    "actor_type": "SERVICE",
    "actor_id": "scheduling-worker",
    "role": "SCHEDULING_WORKER",
}
CALLBACK_ACTOR = {
    "actor_type": "SERVICE",
    "actor_id": "provider-callback-gateway",
    "role": "SCHEDULING_PROVIDER_CALLBACK",
}
CANDIDATE_ACTOR = {
    "actor_type": "EXTERNAL_PARTICIPANT",
    "actor_id": "candidate-lina",
    "role": "CANDIDATE",
}
OPS_ACTOR = {
    "actor_type": "HUMAN",
    "actor_id": "product-demo-user",
    "role": "RECRUITING_OPS",
}


def operations_request(control: Any) -> Dict[str, Any]:
    return {
        "tenant_id": TENANT,
        "application_case_id": control.synthetic_case_id,
        "view": "SCHEDULING_CASE_VIEW",
        "actor_context": deepcopy(OPS_ACTOR),
    }


def _fixture_session_id(control: Any) -> str:
    return "session:{}:round-1:required-1".format(control.synthetic_case_id)


def _workflow_request(control: Any) -> Dict[str, Any]:
    return {
        "tenant_id": TENANT,
        "application_case_id": control.synthetic_case_id,
        "interview_session_id": _fixture_session_id(control),
        "view": "SCHEDULING_CASE_CONTEXT",
        "actor_context": deepcopy(WORKFLOW_ACTOR),
    }


def _worker_request(control: Any) -> Dict[str, Any]:
    return {
        "tenant_id": TENANT,
        "application_case_id": control.synthetic_case_id,
        "interview_session_id": _fixture_session_id(control),
        "view": "BOOKING_RECONCILIATION_VIEW",
        "actor_context": deepcopy(WORKER_ACTOR),
    }


def pause_case_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    case = control.read(_workflow_request(control))["case"]
    return command(
        "PauseScope",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        OPS_ACTOR,
        {
            "expected_case_version": case["version"],
            "expected_lifecycle_epoch": case["lifecycle_epoch"],
            "scope": "SCHEDULING_PRODUCTION",
            "reason": "SYNTHETIC_CASE_CONTROL",
        },
    )


def _session(control: Any) -> Dict[str, Any]:
    return control.read(_workflow_request(control))["session"]


def _worker_projection(control: Any) -> Dict[str, Any]:
    return control.read(_worker_request(control))


def open_coordination_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    session = _session(control)
    return command(
        "OpenCandidateCoordinationRequest",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        WORKFLOW_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
        },
    )


def publish_proposal_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    session = _session(control)
    request = session["coordination_request"]
    return command(
        "PublishSchedulingProposal",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        WORKFLOW_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
            "coordination_request_id": request["request_id"],
            "coordination_request_revision": request["revision"],
        },
    )


def record_selection_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    session = _session(control)
    proposal = session["current_proposal"]
    return command(
        "RecordCandidateSlotSelection",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        CANDIDATE_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
            "proposal_id": proposal["proposal_id"],
            "proposal_version": proposal["version"],
            "slot_ref": proposal["slots"][0]["slot_ref"],
            "selection_action_id": "selection:{}:{}".format(
                proposal["proposal_id"], suffix
            ),
            "coordination_credential_revision": 1,
        },
    )


def propose_appointment_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    session = _session(control)
    selection = session["current_selection"]
    return command(
        "ProposeAppointmentRevision",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        WORKFLOW_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
            "selection_action_id": selection["selection_action_id"],
            "selection_revision": selection["revision"],
        },
    )


def queue_action_command(
    control: Any,
    resource_kind: str,
    *,
    suffix: str,
    recipient_ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    session = _worker_projection(control)["session"]
    pending = session["pending_appointment_revision"]
    action_id = "action:{}:{}:{}".format(
        session["session_id"],
        pending["appointment_revision"],
        resource_kind.lower(),
    )
    if recipient_ref is None and resource_kind == "INVITATION_WRITE":
        recipient_ref = {
            "tenant_id": TENANT,
            "participant_id": "candidate-lina",
            "role": "CANDIDATE",
        }
    return command(
        "QueueSchedulingAction",
        "ACTION_EXECUTION",
        action_id,
        "{}-{}".format(suffix, resource_kind.lower()),
        WORKER_ACTOR,
        {
            "application_case_id": session["application_case_id"],
            "session_id": session["session_id"],
            "appointment_revision": pending["appointment_revision"],
            "resource_kind": resource_kind,
            "recipient_ref": deepcopy(recipient_ref),
        },
    )


def queue_compensation_command(
    control: Any, source_action_id: str, *, suffix: str
) -> Dict[str, Any]:
    projection = _worker_projection(control)
    source = next(
        item
        for item in projection["scheduling_action_executions"]
        if item["action_id"] == source_action_id
    )
    action_id = "compensation:{}:cancel".format(source_action_id)
    return command(
        "QueueSchedulingCompensation",
        "ACTION_EXECUTION",
        action_id,
        suffix,
        WORKER_ACTOR,
        {
            "application_case_id": source["application_case_id"],
            "session_id": source["session_id"],
            "source_action_id": source_action_id,
            "source_action_version": source["version"],
            "operation": "CANCEL_CALENDAR_EVENT",
        },
    )


def execute_action_command(
    control: Any, action_id: str, *, suffix: str
) -> Dict[str, Any]:
    projection = _worker_projection(control)
    action = next(
        item
        for item in projection["scheduling_action_executions"]
        if item["action_id"] == action_id
    )
    return command(
        "ExecuteSchedulingAction",
        "ACTION_EXECUTION",
        action_id,
        suffix,
        WORKER_ACTOR,
        {"expected_action_version": action["version"]},
    )


def reconcile_action_command(
    control: Any, action_id: str, *, suffix: str
) -> Dict[str, Any]:
    projection = _worker_projection(control)
    action = next(
        item
        for item in projection["scheduling_action_executions"]
        if item["action_id"] == action_id
    )
    return command(
        "ReconcileSchedulingAction",
        "ACTION_EXECUTION",
        action_id,
        suffix,
        WORKER_ACTOR,
        {"expected_action_version": action["version"]},
    )


def record_provider_observation_command(
    control: Any,
    action_id: str,
    observation: Dict[str, Any],
    *,
    suffix: str,
) -> Dict[str, Any]:
    projection = _worker_projection(control)
    action = next(
        item
        for item in projection["scheduling_action_executions"]
        if item["action_id"] == action_id
    )
    return command(
        "RecordSchedulingProviderObservation",
        "ACTION_EXECUTION",
        action_id,
        suffix,
        CALLBACK_ACTOR,
        {
            "expected_action_version": action["version"],
            "provider_event_id": observation["provider_event_id"],
            "provider_account_ref": observation["provider_account_ref"],
            "provider_idempotency_key": observation["provider_idempotency_key"],
            "receipt": deepcopy(observation["receipt"]),
        },
    )


def commit_booking_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    session = _session(control)
    pending = session["pending_appointment_revision"]
    return command(
        "CommitBooking",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        WORKFLOW_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
            "appointment_revision": pending["appointment_revision"],
        },
    )


def supersede_appointment_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    session = _session(control)
    pending = session["pending_appointment_revision"]
    return command(
        "SupersedeAppointmentRevision",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        WORKFLOW_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
            "appointment_revision": pending["appointment_revision"],
            "reason": "SYNTHETIC_RESCHEDULE",
        },
    )


def record_recording_notice_delivery_command(
    control: Any, *, suffix: str
) -> Dict[str, Any]:
    session = _session(control)
    return command(
        "RecordRecordingNoticeDelivery",
        "INTERVIEW_SESSION",
        session["session_id"],
        suffix,
        WORKFLOW_ACTOR,
        {
            "expected_session_version": session["version"],
            "expected_lifecycle_epoch": session["case_lifecycle_epoch"],
            "booking_id": session["current_booking"]["booking_id"],
            "participant_ref": {
                "tenant_id": TENANT,
                "participant_id": "candidate-lina",
                "role": "CANDIDATE",
            },
            "purposes": ["INTERVIEW_RECORDING"],
            "notice_version": "recording-notice:v1",
            "channel": "COORDINATION_PAGE",
            "receipt_ref": "notice-receipt:{}".format(suffix),
        },
    )


def command(
    command_type: str,
    aggregate_type: str,
    aggregate_id: str,
    suffix: str,
    actor: Dict[str, Any],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    unique = "{}:{}".format(command_type, suffix)
    return {
        "command_id": "cmd:{}".format(unique),
        "idempotency_key": "idem:{}".format(unique),
        "command_type": command_type,
        "tenant_id": TENANT,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "actor": deepcopy(actor),
        "payload": deepcopy(payload),
    }
