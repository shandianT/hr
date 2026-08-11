"""Product scenarios and command builders for the synthetic screening slice."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

TENANT = "tenant-synthetic"
SCREENING_ACTOR = {
    "actor_type": "SERVICE",
    "actor_id": "screening-workflow",
    "role": "SCREENING_WORKFLOW",
}
GENERATOR_ACTOR = {
    "actor_type": "SERVICE",
    "actor_id": "match-generator",
    "role": "MATCH_GENERATOR",
}
DELIVERY_ACTOR = {
    "actor_type": "SERVICE",
    "actor_id": "delivery-worker",
    "role": "DELIVERY_WORKER",
}
HUMAN_ACTOR = {
    "actor_type": "HUMAN",
    "actor_id": "hiring-owner-1",
    "role": "HIRING_OWNER",
}
OWNER_REF = {
    "tenant_id": TENANT,
    "actor_id": "hiring-owner-1",
    "role": "HIRING_OWNER",
    "department_id": "dept-product",
    "authority_revision": 7,
}
PROFILE_REF = {
    "profile_id": "profile-ai-product",
    "version": 3,
    "publication_revision": 2,
    "safety_epoch": 4,
}


def projection_request() -> Dict[str, Any]:
    return {
        "tenant_id": TENANT,
        "actor_context": {
            "actor_type": "HUMAN",
            "actor_id": "product-demo-user",
            "role": "RECRUITING_OPS",
        },
    }


def current_case(control: Any) -> Dict[str, Any]:
    """Human test/UI observation helper; operational builders do not use it."""

    projection = control.read(projection_request())
    if len(projection["cases"]) != 1:
        raise AssertionError(projection["cases"])
    return next(iter(projection["cases"].values()))


def _service_case(
    control: Any, actor: Dict[str, Any], view: str
) -> Dict[str, Any]:
    result = control.read(
        {
            "tenant_id": TENANT,
            "application_case_id": control.synthetic_case_id,
            "view": view,
            "actor_context": deepcopy(actor),
        }
    )
    return result["case"]


def _screening_case(control: Any) -> Dict[str, Any]:
    return _service_case(control, SCREENING_ACTOR, "SCREENING_CASE_CONTEXT")


def _delivery_case(control: Any) -> Dict[str, Any]:
    return _service_case(control, DELIVERY_ACTOR, "DELIVERY_CONTEXT")


def _match_context(control: Any) -> Dict[str, Any]:
    return control.read(
        {
            "tenant_id": TENANT,
            "application_case_id": control.synthetic_case_id,
            "view": "MATCH_GENERATION_CONTEXT",
            "actor_context": deepcopy(GENERATOR_ACTOR),
        }
    )


def pin_command(control: Any, suffix: str = "normal", **overrides: Any) -> Dict[str, Any]:
    case = _screening_case(control)
    payload = {
        "expected_case_version": case["version"],
        "expected_lifecycle_epoch": case["lifecycle_epoch"],
        "structured_resume_ref": deepcopy(case["current_structured_resume_ref"]),
        "role_profile_ref": deepcopy(PROFILE_REF),
        "allowed_fields": ["ai_product_years"],
        "allowed_field_policy_ref": {
            "policy_id": "field-policy-screening",
            "version": 2,
        },
        "matching_policy_ref": {"policy_id": "match-policy", "version": 5},
        "generator_ref": {"generator_id": "synthetic-matcher", "version": 1},
    }
    payload.update(overrides)
    return command(
        "PinScreeningInput",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        SCREENING_ACTOR,
        payload,
    )


def assessment_command(
    control: Any,
    *,
    suffix: str = "normal",
    result_band: str = "HIGH",
    dimensions: Optional[list] = None,
    **overrides: Any
) -> Dict[str, Any]:
    context = _match_context(control)
    case = context["case"]
    manifest = context["screening_input_manifest"]
    if dimensions is None:
        evidence = context["allowed_evidence_fields"]
        first_atom = None
        if evidence:
            first_atom = {
                key: evidence[0][key]
                for key in ("source_ref", "locator", "field_name", "excerpt_hash")
            }
        dimensions = []
        for criterion in context["role_criteria"]:
            supported = (
                criterion["criterion_ref"] == "criterion-ai-product"
                and first_atom is not None
            )
            dimensions.append(
                {
                    "criterion_ref": criterion["criterion_ref"],
                    "criterion_type": criterion["criterion_type"],
                    "finding": "SUPPORT" if supported else "UNKNOWN",
                    "summary": "存在可回到原文的支持证据。"
                    if supported
                    else "当前材料证据不足，保持未知。",
                    "evidence_atoms": [deepcopy(first_atom)] if supported else [],
                }
            )
    payload = {
        "application_case_id": case["application_case_id"],
        "expected_case_version": case["version"],
        "expected_lifecycle_epoch": case["lifecycle_epoch"],
        "screening_manifest_hash": manifest["manifest_hash"],
        "dimensions": dimensions,
        "result_band": result_band,
    }
    payload.update(overrides)
    return command(
        "PublishMatchAssessment",
        "MATCH_ASSESSMENT",
        "assessment:{}:{}".format(case["application_case_id"], suffix),
        suffix,
        GENERATOR_ACTOR,
        payload,
    )


def open_request_command(
    control: Any,
    assessment_id: str,
    *,
    suffix: str = "normal",
    **overrides: Any
) -> Dict[str, Any]:
    case = _screening_case(control)
    request_sequence = case["next_department_request_sequence"]
    payload = {
        "expected_case_version": case["version"],
        "expected_lifecycle_epoch": case["lifecycle_epoch"],
        "assessment_id": assessment_id,
        "assessment_version": 1,
        "screening_manifest_hash": case["screening_input_manifest"]["manifest_hash"],
        "request_id": "department-request:{}:{}".format(
            case["application_case_id"], request_sequence
        ),
        "owner_ref": deepcopy(OWNER_REF),
    }
    payload.update(overrides)
    return command(
        "OpenDepartmentDecisionRequest",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        SCREENING_ACTOR,
        payload,
    )


def queue_delivery_command(
    control: Any,
    *,
    action_type: str,
    ordinal: int,
    suffix: str,
    recipient_ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    case = _delivery_case(control)
    request = case["department_decision_request"]
    action_id = "action:{}:{}:{}:{}:{}".format(
        request["request_id"],
        request["revision"],
        request["sla_generation"],
        action_type.lower(),
        ordinal,
    )
    return command(
        "QueueDepartmentDelivery",
        "ACTION_EXECUTION",
        action_id,
        suffix,
        DELIVERY_ACTOR,
        {
            "application_case_id": case["application_case_id"],
            "expected_case_version": case["version"],
            "expected_lifecycle_epoch": case["lifecycle_epoch"],
            "request_id": request["request_id"],
            "request_revision": request["revision"],
            "sla_generation": request["sla_generation"],
            "action_type": action_type,
            "ordinal": ordinal,
            "recipient_ref": deepcopy(recipient_ref or request["owner_ref"]),
        },
    )


def execute_delivery_command(
    action_id: str,
    *,
    suffix: str,
    synthetic_outcome: str = "SUCCESS",
    expected_action_version: int = 1,
) -> Dict[str, Any]:
    return command(
        "ExecuteSyntheticDelivery",
        "ACTION_EXECUTION",
        action_id,
        suffix,
        DELIVERY_ACTOR,
        {
            "expected_action_version": expected_action_version,
            "synthetic_outcome": synthetic_outcome,
        },
    )


def decision_command(
    control: Any,
    decision_type: str,
    *,
    suffix: str,
    actor: Optional[Dict[str, Any]] = None,
    revisit_at: Optional[str] = None,
    **overrides: Any
) -> Dict[str, Any]:
    case = _screening_case(control)
    request = case["department_decision_request"]
    payload = {
        "expected_case_version": case["version"],
        "expected_lifecycle_epoch": case["lifecycle_epoch"],
        "request_id": request["request_id"],
        "request_revision": request["revision"],
        "sla_generation": request["sla_generation"],
        "assessment_ref": deepcopy(request["assessment_ref"]),
        "authority_revision": request["owner_ref"]["authority_revision"],
        "decision_id": "decision:{}:{}".format(request["request_id"], suffix),
        "decision_type": decision_type,
        "reason": "当前授权用人负责人基于证据材料作出合成人工决定。",
    }
    if revisit_at:
        payload["revisit_at"] = revisit_at
    payload.update(overrides)
    return command(
        "RecordDepartmentDecision",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        actor or HUMAN_ACTOR,
        payload,
    )


def reminder_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    case = _screening_case(control)
    request = case["department_decision_request"]
    return command(
        "AdvanceReminderOrdinal",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        SCREENING_ACTOR,
        {
            "expected_case_version": case["version"],
            "expected_lifecycle_epoch": case["lifecycle_epoch"],
            "request_id": request["request_id"],
            "request_revision": request["revision"],
            "sla_generation": request["sla_generation"],
        },
    )


def resume_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    case = _screening_case(control)
    request = case["department_decision_request"]
    return command(
        "ResumeDepartmentDecisionRequest",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        SCREENING_ACTOR,
        {
            "expected_case_version": case["version"],
            "expected_lifecycle_epoch": case["lifecycle_epoch"],
            "request_id": request["request_id"],
            "request_revision": request["revision"],
            "sla_generation": request["sla_generation"],
        },
    )


def invalidate_command(control: Any, *, suffix: str) -> Dict[str, Any]:
    case = _screening_case(control)
    return command(
        "InvalidateCurrentMatchAssessment",
        "APPLICATION_CASE",
        case["application_case_id"],
        suffix,
        SCREENING_ACTOR,
        {
            "expected_case_version": case["version"],
            "expected_lifecycle_epoch": case["lifecycle_epoch"],
            "assessment_ref": deepcopy(case["current_match_assessment_ref"]),
            "reason": "STRUCTURED_RESUME_VERSION_CHANGED",
            "causal_input_ref": "submission-001",
            "causal_input_version": 2,
        },
    )


def run_to_open_request(
    control: Any, *, result_band: str = "HIGH", suffix: str = "normal"
) -> Dict[str, Any]:
    _require_applied(control.submit(pin_command(control, suffix)))
    assessment = control.submit(
        assessment_command(control, suffix=suffix, result_band=result_band)
    )
    _require_applied(assessment)
    assessment_id = assessment["data"]["assessment_id"]
    _require_applied(
        control.submit(
            open_request_command(control, assessment_id, suffix=suffix)
        )
    )
    return {
        "application_case_id": control.synthetic_case_id,
        "assessment_id": assessment_id,
    }


def run_normal_screening(
    control: Any, *, decision: Optional[str] = None
) -> Dict[str, Any]:
    summary = run_to_open_request(control)
    queued = control.submit(
        queue_delivery_command(
            control,
            action_type="INITIAL_NOTICE",
            ordinal=0,
            suffix="initial-notice",
        )
    )
    _require_applied(queued)
    _require_applied(
        control.submit(
            execute_delivery_command(
                queued["data"]["action_id"], suffix="initial-notice"
            )
        )
    )
    if decision:
        _require_applied(
            control.submit(
                decision_command(control, decision, suffix=decision.lower())
            )
        )
    return {
        **summary,
        "projection_request": projection_request(),
        "synthetic_only": True,
    }


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


def _require_applied(result: Dict[str, Any]) -> None:
    if result["status"] not in {"APPLIED", "REPLAYED"}:
        raise AssertionError(result)
