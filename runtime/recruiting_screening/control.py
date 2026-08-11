"""Deterministic synthetic screening and department-decision kernel."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, Optional, Tuple

try:  # Repository-root imports used by tests and package callers.
    from runtime.recruiting_intake.control import ResumeIntakeControl
except ModuleNotFoundError:  # Direct ``python runtime/run_*.py`` execution.
    from recruiting_intake.control import ResumeIntakeControl


JsonObject = Dict[str, Any]


class RecruitingG2Control(ResumeIntakeControl):
    """Deep G2 module sharing the intake module's authoritative Case rows."""

    _SCREENING_TARGETS = {
        "PinScreeningInput": "APPLICATION_CASE",
        "PublishMatchAssessment": "MATCH_ASSESSMENT",
        "OpenDepartmentDecisionRequest": "APPLICATION_CASE",
        "QueueDepartmentDelivery": "ACTION_EXECUTION",
        "ExecuteSyntheticDelivery": "ACTION_EXECUTION",
        "AdvanceReminderOrdinal": "APPLICATION_CASE",
        "RecordDepartmentDecision": "APPLICATION_CASE",
        "ResumeDepartmentDecisionRequest": "APPLICATION_CASE",
        "InvalidateCurrentMatchAssessment": "APPLICATION_CASE",
    }
    _SCREENING_ACTORS = {
        "PinScreeningInput": {
            ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW")
        },
        "PublishMatchAssessment": {
            ("SERVICE", "match-generator", "MATCH_GENERATOR")
        },
        "OpenDepartmentDecisionRequest": {
            ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW")
        },
        "QueueDepartmentDelivery": {
            ("SERVICE", "delivery-worker", "DELIVERY_WORKER")
        },
        "ExecuteSyntheticDelivery": {
            ("SERVICE", "delivery-worker", "DELIVERY_WORKER")
        },
        "AdvanceReminderOrdinal": {
            ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW")
        },
        # Decision attempts reach the domain gate so SERVICE/AGENT receive the
        # stable HUMAN_AUTHORITY_REQUIRED result instead of being mistaken for
        # a valid recruiting decision.
        "RecordDepartmentDecision": {
            ("HUMAN", "hiring-owner-1", "HIRING_OWNER"),
            ("HUMAN", "hiring-owner-2", "HIRING_OWNER"),
            ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW"),
            ("AGENT", "screening-agent", "SCREENING_AGENT"),
        },
        "ResumeDepartmentDecisionRequest": {
            ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW")
        },
        "InvalidateCurrentMatchAssessment": {
            ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW")
        },
    }
    _SCREENING_READ_ACTORS = {
        ("HUMAN", "product-demo-user", "RECRUITING_OPS"),
        ("HUMAN", "hiring-owner-1", "HIRING_OWNER"),
    }
    _SERVICE_READ_VIEWS = {
        ("SERVICE", "screening-workflow", "SCREENING_WORKFLOW"): "SCREENING_CASE_CONTEXT",
        ("SERVICE", "match-generator", "MATCH_GENERATOR"): "MATCH_GENERATION_CONTEXT",
        ("SERVICE", "delivery-worker", "DELIVERY_WORKER"): "DELIVERY_CONTEXT",
    }
    _INVALIDATION_REASONS = {
        "STRUCTURED_RESUME_VERSION_CHANGED",
        "ROLE_PROFILE_VERSION_CHANGED",
        "SCREENING_POLICY_VERSION_CHANGED",
        "SOURCE_FACT_CORRECTED",
        "MANUAL_SCREENING_RESTART",
    }

    _PROHIBITED_FIELDS = {
        "age",
        "birth_date",
        "candidate_score",
        "decision",
        "disability",
        "ethnicity",
        "gender",
        "marital_status",
        "name",
        "nationality",
        "personality_score",
        "photo",
        "political_affiliation",
        "ranking",
        "recommendation",
        "religion",
        "reproductive_status",
        "school",
        "sex",
        "university",
        "date_of_birth",
        "dob",
        "family_status",
        "出生日期",
        "姓名",
        "学校",
        "年龄",
        "性别",
        "政治面貌",
        "民族",
        "婚姻状况",
        "婚育",
        "宗教",
        "照片",
        "生育状况",
    }
    _PROHIBITED_KEYS = {
        "auto_reject",
        "candidate_score",
        "decision",
        "hiring_decision",
        "personality_score",
        "rank",
        "ranking",
        "recommendation",
        "决定",
        "得分",
        "推荐",
        "排名",
    }
    _INJECTION_MARKERS = {
        "ignore previous instructions",
        "ignore all instructions",
        "send an email",
        "system prompt",
        "tool call",
        "忽略之前",
        "忽略以上",
        "忽略所有",
        "调用工具",
        "发送邮件",
        "读取密钥",
        "系统提示词",
        "无视先前",
        "无视之前",
        "发一封邮件",
        "直接推进",
        "优先推进",
        "推荐进入",
        "直接拒绝",
        "自动淘汰",
    }
    _PROHIBITED_TEXT_MARKERS = {
        "birth date",
        "date of birth",
        "gender",
        "male candidate",
        "female candidate",
        "marital status",
        "school background",
        "university background",
        "出生日期",
        "名校",
        "学校背景",
        "毕业于",
        "年龄",
        "性别",
        "男性",
        "女性",
        "政治面貌",
        "民族",
        "婚育",
        "生育状况",
    }
    _APPROVED_DIMENSION_SUMMARIES = {
        "SUPPORT": "存在可回到原文的支持证据。",
        "COUNTER_EVIDENCE": "存在可回到原文的反证。",
        "UNKNOWN": "当前材料证据不足，保持未知。",
        "NOT_APPLICABLE": "当前岗位画像将此维度标记为不适用。",
    }

    def __init__(
        self,
        connection: sqlite3.Connection,
        *,
        synthetic_now: str = "2026-08-11T12:00:00Z",
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        super().__init__(connection)
        self._authority_grants.update(
            {
                (
                    "tenant-synthetic",
                    "SERVICE",
                    "screening-workflow",
                    "SCREENING_WORKFLOW",
                ),
                (
                    "tenant-synthetic",
                    "SERVICE",
                    "match-generator",
                    "MATCH_GENERATOR",
                ),
                (
                    "tenant-synthetic",
                    "SERVICE",
                    "delivery-worker",
                    "DELIVERY_WORKER",
                ),
                (
                    "tenant-synthetic",
                    "AGENT",
                    "screening-agent",
                    "SCREENING_AGENT",
                ),
                (
                    "tenant-synthetic",
                    "HUMAN",
                    "hiring-owner-2",
                    "HIRING_OWNER",
                ),
            }
        )
        fixed_now = _parse_time(synthetic_now)
        self._clock = clock or (lambda: fixed_now)
        self._profile = {
            "profile_id": "profile-ai-product",
            "version": 3,
            "publication_revision": 2,
            "state": "ACTIVE",
            "safety_epoch": 4,
            "requisition_id": "req-ai-product",
            "allowed_fields": ["ai_product_years"],
            "criteria": [
                {
                    "criterion_ref": "criterion-ai-product",
                    "criterion_type": "MUST_HAVE",
                },
                {
                    "criterion_ref": "criterion-user-discovery",
                    "criterion_type": "COMPETENCY",
                },
            ],
        }
        self._screening_configuration = {
            "allowed_field_policy_ref": {
                "policy_id": "field-policy-screening",
                "version": 2,
            },
            "matching_policy_ref": {"policy_id": "match-policy", "version": 5},
            "generator_ref": {
                "generator_id": "synthetic-matcher",
                "version": 1,
            },
        }
        self._owner = {
            "tenant_id": "tenant-synthetic",
            "actor_id": "hiring-owner-1",
            "role": "HIRING_OWNER",
            "department_id": "dept-product",
            "authority_revision": 7,
            "active": True,
        }
        self._install_screening_schema()

    def read(self, request: JsonObject) -> JsonObject:
        if not isinstance(request, dict) or not isinstance(
            request.get("tenant_id"), str
        ):
            raise PermissionError("tenant_id and actor_context must be valid strings")
        actor_context = request.get("actor_context")
        if not isinstance(actor_context, dict) or not all(
            isinstance(actor_context.get(key), str)
            and actor_context.get(key)
            for key in ("actor_type", "actor_id", "role")
        ):
            raise PermissionError("tenant_id and actor_context must be valid strings")
        actor_key = (
            actor_context["actor_type"],
            actor_context["actor_id"],
            actor_context["role"],
        )
        service_view = self._SERVICE_READ_VIEWS.get(actor_key)
        if service_view is not None:
            if (
                request.get("view") != service_view
                or set(request)
                != {
                    "tenant_id",
                    "actor_context",
                    "view",
                    "application_case_id",
                }
                or (
                    request["tenant_id"],
                    actor_key[0],
                    actor_key[1],
                    actor_key[2],
                )
                not in self._authority_grants
            ):
                raise PermissionError("service projection must be case-bound and purpose-bound")
            return self._read_service_case(request, service_view)
        if actor_key not in self._SCREENING_READ_ACTORS:
            raise PermissionError("current actor is not authorized for this projection")
        projection = super().read(request)
        tenant_id = request["tenant_id"]

        assessments = {}
        for row in self._db.execute(
            "SELECT assessment_id, version, state_json FROM match_assessments "
            "WHERE tenant_id = ? ORDER BY assessment_id",
            (tenant_id,),
        ):
            state = json.loads(row["state_json"])
            state["version"] = row["version"]
            assessments[row["assessment_id"]] = state

        actions = []
        for row in self._db.execute(
            "SELECT action_id, version, state_json FROM screening_action_executions "
            "WHERE tenant_id = ? ORDER BY action_id",
            (tenant_id,),
        ):
            state = json.loads(row["state_json"])
            state["version"] = row["version"]
            actions.append(state)

        tasks = []
        screening_exceptions = []
        for case in projection["cases"].values():
            request_state = case.get("department_decision_request")
            if request_state and request_state.get("status") in {"OPEN", "ON_HOLD"}:
                tasks.append(deepcopy(request_state))
            exception = case.get("screening_exception")
            if exception and exception.get("status") == "OPEN":
                screening_exceptions.append(deepcopy(exception))
        for action in actions:
            exception = action.get("exception")
            if (
                isinstance(exception, dict)
                and exception.get("status") == "OPEN"
            ):
                screening_exceptions.append(deepcopy(exception))

        projection.update(
            {
                "match_assessments": assessments,
                "department_decision_tasks": tasks,
                "action_executions": actions,
                "screening_exception_bundles": screening_exceptions,
                # These are deterministic simulated receipts.  This kernel
                # never contacts a real messaging system.
                "external_effect_count": sum(
                    action["state"] == "SUCCEEDED" for action in actions
                ),
                "simulated_delivery_receipt_count": sum(
                    action["state"] == "SUCCEEDED" for action in actions
                ),
                "real_external_effect_count": 0,
                "automatic_rejection_count": sum(
                    1
                    for case in projection["cases"].values()
                    for decision in case.get("department_decisions", [])
                    if decision.get("actor", {}).get("actor_type") != "HUMAN"
                ),
                "candidate_rejection_communication_count": sum(
                    action.get("action_type") == "CANDIDATE_REJECTION"
                    and action["state"] == "SUCCEEDED"
                    for action in actions
                ),
            }
        )
        return projection

    def _read_service_case(
        self, request: JsonObject, service_view: str
    ) -> JsonObject:
        """Return one closed, purpose-specific Case view without tenant scans."""

        tenant_id = request["tenant_id"]
        case_id = request.get("application_case_id")
        if not isinstance(case_id, str) or not case_id:
            raise PermissionError("service projection must be case-bound and purpose-bound")
        loaded = self._load_case(tenant_id, case_id)
        if not loaded:
            # PermissionError deliberately avoids disclosing whether another
            # tenant or an unknown Case owns this identifier.
            raise PermissionError("service projection must be case-bound and purpose-bound")
        version, case = loaded
        case_header = {
            "application_case_id": case_id,
            "version": version,
            "state": case.get("state"),
            "lifecycle_epoch": case.get("lifecycle_epoch"),
        }
        base = {
            "synthetic_only": True,
            "view": service_view,
            "application_case_id": case_id,
        }
        if service_view == "SCREENING_CASE_CONTEXT":
            return {
                **base,
                "case": {
                    **case_header,
                    "current_structured_resume_ref": deepcopy(
                        case.get("current_structured_resume_ref")
                    ),
                    "screening_input_manifest": deepcopy(
                        case.get("screening_input_manifest")
                    ),
                    "current_match_assessment_ref": deepcopy(
                        case.get("current_match_assessment_ref")
                    ),
                    "department_decision_request": deepcopy(
                        case.get("department_decision_request")
                    ),
                    "next_department_request_sequence": case.get(
                        "department_request_sequence", 0
                    )
                    + 1,
                },
            }
        if service_view == "MATCH_GENERATION_CONTEXT":
            manifest = case.get("screening_input_manifest")
            return {
                **base,
                "case": case_header,
                "screening_input_manifest": deepcopy(manifest),
                "role_criteria": deepcopy(self._profile["criteria"]),
                "allowed_evidence_fields": self._allowed_evidence_fields(
                    tenant_id, manifest
                ),
            }
        if service_view == "DELIVERY_CONTEXT":
            actions = []
            for row in self._db.execute(
                "SELECT action_id, version, state_json "
                "FROM screening_action_executions "
                "WHERE tenant_id = ? "
                "AND json_extract(state_json, '$.application_case_id') = ? "
                "ORDER BY action_id",
                (tenant_id, case_id),
            ):
                action = json.loads(row["state_json"])
                actions.append(
                    {
                        key: deepcopy(action.get(key))
                        for key in (
                            "action_id",
                            "state",
                            "action_type",
                            "request_id",
                            "request_revision",
                            "sla_generation",
                            "cancellation_epoch",
                            "ordinal",
                            "attempt_count",
                            "max_attempts",
                            "blocked_reason",
                            "exception",
                        )
                    }
                )
                actions[-1]["version"] = row["version"]
            return {
                **base,
                "case": {
                    **case_header,
                    "department_decision_request": deepcopy(
                        case.get("department_decision_request")
                    ),
                },
                "action_executions": actions,
            }
        raise PermissionError("service projection must be case-bound and purpose-bound")

    def _allowed_evidence_fields(
        self, tenant_id: str, manifest: Any
    ) -> list[JsonObject]:
        if not isinstance(manifest, dict) or manifest.get("status") != "CURRENT":
            return []
        resume_ref = manifest.get("structured_resume_ref")
        if not isinstance(resume_ref, dict):
            return []
        loaded = self._load_submission(tenant_id, resume_ref.get("submission_id"))
        if not loaded:
            return []
        _, submission = loaded
        versions = submission.get("structured_resume_versions", [])
        if (
            not versions
            or type(resume_ref.get("version")) is not int
            or versions[-1].get("version") != resume_ref["version"]
        ):
            return []
        allowed = set(manifest.get("allowed_fields", []))
        fields = []
        for field in versions[-1].get("routable_fields", []):
            if (
                not isinstance(field, dict)
                or field.get("name") not in allowed
                or not isinstance(field.get("locator"), str)
            ):
                continue
            fields.append(
                {
                    "source_ref": "{}:resume:{}".format(
                        resume_ref["submission_id"], resume_ref["version"]
                    ),
                    "field_name": field["name"],
                    "value": deepcopy(field.get("value")),
                    "locator": field["locator"],
                    "excerpt_hash": evidence_atom_hash(field, resume_ref["version"]),
                }
            )
        return fields

    def _validate_envelope(self, envelope: Any) -> Optional[Tuple[str, str]]:
        if not isinstance(envelope, dict):
            return "INVALID_COMMAND", "命令信封必须是结构化对象。"
        required_strings = {
            "command_id",
            "idempotency_key",
            "command_type",
            "tenant_id",
            "aggregate_type",
            "aggregate_id",
        }
        if not all(
            isinstance(envelope.get(key), str) and envelope.get(key)
            for key in required_strings
        ):
            return "INVALID_COMMAND", "命令信封标识必须是非空字符串。"
        actor = envelope.get("actor")
        if not isinstance(actor, dict) or not all(
            isinstance(actor.get(key), str) and actor.get(key)
            for key in ("actor_type", "actor_id", "role")
        ):
            return "INVALID_COMMAND", "命令 actor 字段必须是非空字符串。"
        if not isinstance(envelope.get("payload"), dict):
            return "INVALID_COMMAND", "命令 payload 必须是结构化对象。"
        base_error = super()._validate_envelope(envelope)
        if base_error:
            return base_error
        command_type = envelope["command_type"]
        target = self._SCREENING_TARGETS.get(command_type)
        if not target:
            return None
        if envelope["aggregate_type"] != target:
            return (
                "AGGREGATE_TARGET_MISMATCH",
                "命令目标聚合与该命令的唯一写入对象不一致。",
            )
        actor = envelope["actor"]
        actor_grant = (
            actor.get("actor_type"),
            actor.get("actor_id"),
            actor.get("role"),
        )
        if actor_grant not in self._SCREENING_ACTORS[command_type]:
            return "AUTHORIZATION_DENIED", "当前授权主体不能提交这一类命令。"
        return None

    def _handle_OpenOrAttachApplicationCase(
        self, envelope: JsonObject
    ) -> JsonObject:
        """Invalidate current screening facts when intake adds a new resume."""

        payload_error = self._validate_open_or_attach_payload(envelope)
        if payload_error:
            return self._rejected(envelope, payload_error[0], payload_error[1])
        result = super()._handle_OpenOrAttachApplicationCase(envelope)
        if result.get("status") != "APPLIED":
            return result
        case_id = result["data"]["application_case_id"]
        loaded = self._load_case(envelope["tenant_id"], case_id)
        if not loaded:
            return result
        version, case = loaded
        effect = result["data"].get("effect")
        selects_new_resume = effect == "CASE_OPENED" or (
            effect == "ATTACHED_TO_EXISTING_CASE" and bool(result.get("event_ids"))
        )
        if not selects_new_resume:
            return result
        current_resume_ref = self._latest_structured_resume_ref(
            envelope["tenant_id"], envelope["payload"]["submission_id"]
        )
        if not current_resume_ref:
            return self._rejected(
                envelope,
                "RESUME_VERSION_NOT_CURRENT",
                "开案来源没有可用的当前结构化简历。",
            )
        case["current_structured_resume_ref"] = current_resume_ref
        case["department_request_sequence"] = case.get(
            "department_request_sequence", 0
        )
        selected_event = self._append_event(
            envelope["tenant_id"],
            "CurrentStructuredResumeSelected",
            case_id,
            {
                "application_case_id": case_id,
                "submission_id": current_resume_ref["submission_id"],
                "structured_resume_version": current_resume_ref["version"],
            },
        )
        result.setdefault("event_ids", []).append(selected_event)
        if effect == "CASE_OPENED":
            self._save_case(envelope["tenant_id"], case_id, version + 1, case)
            result["data"]["case_version"] = version + 1
            return result
        if case.get("state") not in {
            "RECEIVED",
            "SCREENING",
            "AWAITING_DEPARTMENT_DECISION",
        }:
            self._save_case(envelope["tenant_id"], case_id, version + 1, case)
            result["data"]["case_version"] = version + 1
            return result
        manifest = case.get("screening_input_manifest")
        request = case.get("department_decision_request")
        if not manifest and not request:
            self._save_case(envelope["tenant_id"], case_id, version + 1, case)
            result["data"]["case_version"] = version + 1
            result["data"]["screening_effect"] = "CURRENT_RESUME_SELECTED"
            return result
        if isinstance(manifest, dict):
            manifest["status"] = "INVALIDATED"
            manifest["invalidation_reason"] = "NEW_RESUME_ATTACHED"
            if case.get("screening_input_history"):
                case["screening_input_history"][-1] = deepcopy(manifest)
        if isinstance(request, dict) and request.get("status") in {"OPEN", "ON_HOLD"}:
            superseded = deepcopy(request)
            superseded.update(
                {
                    "status": "SUPERSEDED",
                    "cancellation_epoch": request["cancellation_epoch"] + 1,
                    "superseded_reason": "NEW_RESUME_ATTACHED",
                }
            )
            self._replace_request_history(case, superseded)
        resolved_exception_id = self._resolve_screening_exception(
            case,
            resolution="SCREENING_INPUT_INVALIDATED",
            causal_ref=envelope["payload"].get("submission_id"),
        )
        superseded_action_exception_ids = self._settle_request_actions(
            envelope["tenant_id"],
            case,
            request,
            reason="NEW_RESUME_ATTACHED",
            exception_status="SUPERSEDED",
        )
        case.update(
            {
                "state": "SCREENING",
                "screening_input_manifest": None,
                "current_match_assessment_ref": None,
                "department_decision_request": None,
            }
        )
        self._save_case(envelope["tenant_id"], case_id, version + 1, case)
        invalidated = self._append_event(
            envelope["tenant_id"],
            "ScreeningInputInvalidatedByNewSubmission",
            case_id,
            {
                "application_case_id": case_id,
                "new_submission_id": envelope["payload"].get("submission_id"),
                "reason": "NEW_RESUME_ATTACHED",
            },
        )
        result["event_ids"].append(invalidated)
        if resolved_exception_id:
            result["event_ids"].append(
                self._append_event(
                    envelope["tenant_id"],
                    "ExceptionBundleResolved",
                    case_id,
                    {
                        "application_case_id": case_id,
                        "exception_id": resolved_exception_id,
                        "resolution": "SCREENING_INPUT_INVALIDATED",
                    },
                )
            )
        for exception_id in superseded_action_exception_ids:
            result["event_ids"].append(
                self._append_event(
                    envelope["tenant_id"],
                    "ActionExceptionSupersededByCaseTransition",
                    case_id,
                    {
                        "application_case_id": case_id,
                        "exception_id": exception_id,
                        "status": "SUPERSEDED",
                        "reason": "NEW_RESUME_ATTACHED",
                    },
                )
            )
        result["data"]["screening_effect"] = "CURRENT_SCREENING_INVALIDATED"
        result["data"]["case_version"] = version + 1
        return result

    def _validate_open_or_attach_payload(
        self, envelope: JsonObject
    ) -> Optional[Tuple[str, str]]:
        payload = envelope.get("payload")
        allowed = {
            "submission_id",
            "routing_revision",
            "expected_case_version",
            "expected_lifecycle_epoch",
            "application_case_id_reservation",
            "application_key",
        }
        if not isinstance(payload, dict) or set(payload) - allowed:
            return "INVALID_COMMAND", "开案 payload 包含未声明字段。"
        if not isinstance(payload.get("submission_id"), str) or not payload[
            "submission_id"
        ].strip():
            return "INVALID_COMMAND", "submission_id 必须是非空字符串。"
        for field in (
            "routing_revision",
            "expected_case_version",
            "expected_lifecycle_epoch",
        ):
            if type(payload.get(field)) is not int:
                return "INVALID_COMMAND", "开案版本字段必须是严格整数。"
        reservation = payload.get("application_case_id_reservation")
        if reservation is not None and (
            not isinstance(reservation, str) or not reservation.strip()
        ):
            return "INVALID_COMMAND", "Case 预留标识必须是非空字符串。"
        if reservation is not None and reservation != envelope["aggregate_id"]:
            return "AGGREGATE_TARGET_MISMATCH", "Case 预留标识与命令目标不一致。"
        application_key = payload.get("application_key")
        if application_key is not None:
            required = {
                "tenant_id",
                "candidate_id",
                "requisition_id",
                "recruitment_cycle_id",
            }
            if (
                not isinstance(application_key, dict)
                or set(application_key) != required
                or not all(
                    isinstance(application_key.get(key), str)
                    and application_key[key].strip()
                    for key in required
                )
            ):
                return "INVALID_COMMAND", "ApplicationKey 必须是封闭的非空字符串对象。"
        return None

    def _latest_structured_resume_ref(
        self, tenant_id: str, submission_id: str
    ) -> Optional[JsonObject]:
        loaded = self._load_submission(tenant_id, submission_id)
        if not loaded:
            return None
        _, submission = loaded
        versions = submission.get("structured_resume_versions", [])
        if not versions or type(versions[-1].get("version")) is not int:
            return None
        return {
            "submission_id": submission_id,
            "version": versions[-1]["version"],
        }

    def _handle_PinScreeningInput(self, envelope: JsonObject) -> JsonObject:
        loaded = self._load_case(envelope["tenant_id"], envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        stale = self._validate_case_expectations(envelope, version, case)
        if stale:
            return stale
        if case["state"] not in {"RECEIVED", "SCREENING"}:
            return self._rejected(
                envelope, "INVALID_TRANSITION", "当前案件阶段不能钉住筛选输入。"
            )
        payload = envelope["payload"]
        resume_ref = payload.get("structured_resume_ref", {})
        profile_ref = payload.get("role_profile_ref", {})
        if not isinstance(resume_ref, dict) or not isinstance(profile_ref, dict):
            return self._rejected(
                envelope, "INVALID_COMMAND", "简历与岗位画像引用必须是结构化对象。"
            )
        source_error = self._validate_current_sources(case, resume_ref, profile_ref)
        if source_error:
            return self._rejected(envelope, source_error[0], source_error[1])

        allowed_fields = payload.get("allowed_fields")
        if not isinstance(allowed_fields, list) or not allowed_fields:
            return self._rejected(
                envelope, "INVALID_COMMAND", "筛选输入必须声明允许字段。"
            )
        if not all(isinstance(item, str) and item.strip() for item in allowed_fields):
            return self._rejected(
                envelope, "INVALID_COMMAND", "允许字段必须是非空字段名。"
            )
        normalized_fields = {item.strip().casefold() for item in allowed_fields}
        if (
            normalized_fields & self._PROHIBITED_FIELDS
            or not normalized_fields.issubset(set(self._profile["allowed_fields"]))
        ):
            return self._rejected(
                envelope,
                "FIELD_POLICY_VIOLATION",
                "筛选输入包含保护、代理或当前政策未允许的字段。",
            )
        required_pins = {
            "allowed_field_policy_ref",
            "matching_policy_ref",
            "generator_ref",
        }
        if not required_pins.issubset(payload):
            return self._rejected(
                envelope, "INVALID_COMMAND", "筛选策略或生成器版本没有钉住。"
            )
        if any(
            payload.get(key) != expected
            for key, expected in self._screening_configuration.items()
        ):
            return self._rejected(
                envelope,
                "SCREENING_CONFIGURATION_STALE",
                "筛选策略或生成器不是服务端当前生效版本。",
            )

        manifest_body = {
            "structured_resume_ref": resume_ref,
            "role_profile_ref": profile_ref,
            "allowed_fields": sorted(normalized_fields),
            "allowed_field_policy_ref": payload["allowed_field_policy_ref"],
            "matching_policy_ref": payload["matching_policy_ref"],
            "generator_ref": payload["generator_ref"],
        }
        manifest_hash = _hash(manifest_body)
        prior_history = case.setdefault("screening_input_history", [])
        manifest = {
            "manifest_id": "manifest:{}:{}".format(
                envelope["aggregate_id"], len(prior_history) + 1
            ),
            "revision": len(prior_history) + 1,
            "manifest_hash": manifest_hash,
            "status": "CURRENT",
            **deepcopy(manifest_body),
            "synthetic_only": True,
        }
        prior_history.append(deepcopy(manifest))
        case.update(
            {
                "state": "SCREENING",
                "screening_input_manifest": manifest,
                "current_match_assessment_ref": None,
                "department_decision_request": None,
                "department_decisions": case.get("department_decisions", []),
                "department_request_history": case.get(
                    "department_request_history", []
                ),
                "screening_exception": None,
            }
        )
        self._save_case(envelope["tenant_id"], envelope["aggregate_id"], version + 1, case)
        event_id = self._append_event(
            envelope["tenant_id"],
            "ScreeningInputPinned",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                "manifest_id": manifest["manifest_id"],
                "manifest_hash": manifest_hash,
                "structured_resume_version": resume_ref["version"],
                "role_profile_version": profile_ref["version"],
                "case_version": version + 1,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "SCREENING_INPUT_PINNED",
                "application_case_id": envelope["aggregate_id"],
                "manifest_id": manifest["manifest_id"],
                "manifest_hash": manifest_hash,
                "case_version": version + 1,
            },
        )

    def _handle_PublishMatchAssessment(self, envelope: JsonObject) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        payload = envelope["payload"]
        case_id = payload.get("application_case_id")
        loaded = self._load_case(tenant_id, case_id)
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        case_version, case = loaded
        if case["state"] != "SCREENING" or not case.get(
            "screening_input_manifest"
        ):
            return self._rejected(
                envelope, "INVALID_TRANSITION", "案件没有当前筛选输入。"
            )
        if (
            type(payload.get("expected_case_version")) is not int
            or payload.get("expected_case_version") != case_version
        ):
            return self._rejected(
                envelope, "STALE_CASE_VERSION", "匹配材料没有钉住当前案件版本。"
            )
        if (
            type(payload.get("expected_lifecycle_epoch")) is not int
            or payload.get("expected_lifecycle_epoch") != case["lifecycle_epoch"]
        ):
            return self._rejected(
                envelope,
                "STALE_CASE_VERSION",
                "匹配材料没有钉住当前案件生命周期代次。",
            )
        manifest = case["screening_input_manifest"]
        if (
            manifest.get("status") != "CURRENT"
            or payload.get("screening_manifest_hash") != manifest["manifest_hash"]
        ):
            return self._rejected(
                envelope, "MATCH_INPUT_STALE", "匹配材料引用的筛选输入已不是当前版本。"
            )
        if self._db.execute(
            "SELECT 1 FROM match_assessments WHERE tenant_id = ? AND assessment_id = ?",
            (tenant_id, envelope["aggregate_id"]),
        ).fetchone():
            return self._rejected(
                envelope, "AGGREGATE_CONFLICT", "匹配材料标识已被占用。"
            )
        validation_error = self._validate_assessment_payload(payload, manifest)
        if validation_error:
            return self._rejected(envelope, validation_error[0], validation_error[1])

        evidence_count = sum(
            len(item.get("evidence_atoms", [])) for item in payload["dimensions"]
        )
        assessment = {
            "assessment_id": envelope["aggregate_id"],
            "application_case_id": case_id,
            "state": "READY",
            "screening_manifest_id": manifest["manifest_id"],
            "screening_manifest_hash": manifest["manifest_hash"],
            "structured_resume_ref": deepcopy(manifest["structured_resume_ref"]),
            "role_profile_ref": deepcopy(manifest["role_profile_ref"]),
            "dimensions": deepcopy(payload["dimensions"]),
            "result_band": payload["result_band"],
            "evidence_coverage": evidence_count,
            "generator_ref": deepcopy(manifest["generator_ref"]),
            "matching_policy_ref": deepcopy(manifest["matching_policy_ref"]),
            "prohibited_feature_check": "PASSED",
            "contains_hiring_decision": False,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO match_assessments "
            "(tenant_id, assessment_id, application_case_id, manifest_hash, version, state_json) "
            "VALUES (?, ?, ?, ?, 1, ?)",
            (
                tenant_id,
                envelope["aggregate_id"],
                case_id,
                manifest["manifest_hash"],
                _canonical(assessment),
            ),
        )
        event_id = self._append_event(
            tenant_id,
            "MatchAssessmentReady",
            envelope["aggregate_id"],
            {
                "application_case_id": case_id,
                "assessment_id": envelope["aggregate_id"],
                "assessment_version": 1,
                "input_manifest_hash": manifest["manifest_hash"],
                "result_band": payload["result_band"],
                "evidence_coverage": evidence_count,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "MATCH_ASSESSMENT_READY",
                "assessment_id": envelope["aggregate_id"],
                "assessment_version": 1,
                "result_band": payload["result_band"],
            },
        )

    def _handle_OpenDepartmentDecisionRequest(
        self, envelope: JsonObject
    ) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        loaded = self._load_case(tenant_id, envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        stale = self._validate_case_expectations(envelope, version, case)
        if stale:
            return stale
        if case["state"] != "SCREENING" or not case.get(
            "screening_input_manifest"
        ):
            return self._rejected(
                envelope, "INVALID_TRANSITION", "当前案件不能打开部门决定请求。"
            )
        payload = envelope["payload"]
        assessment = self._load_assessment(
            tenant_id,
            payload.get("assessment_id"),
            payload.get("assessment_version"),
        )
        if not assessment or assessment.get("state") != "READY":
            return self._rejected(
                envelope, "ASSESSMENT_NOT_READY", "只有 READY 匹配材料可进入人审。"
            )
        manifest = case["screening_input_manifest"]
        if (
            assessment["application_case_id"] != envelope["aggregate_id"]
            or assessment["screening_manifest_id"] != manifest["manifest_id"]
            or assessment["screening_manifest_hash"] != manifest["manifest_hash"]
            or payload.get("screening_manifest_hash") != manifest["manifest_hash"]
        ):
            return self._rejected(
                envelope, "ASSESSMENT_NOT_CURRENT", "匹配材料不是案件当前输入的产物。"
            )
        owner = payload.get("owner_ref", {})
        owner_error = self._validate_owner(owner, tenant_id)
        if owner_error:
            return self._rejected(envelope, owner_error[0], owner_error[1])
        if case.get("department_decision_request") and case[
            "department_decision_request"
        ].get("status") in {"OPEN", "ON_HOLD"}:
            return self._rejected(
                envelope,
                "CURRENT_REQUEST_EXISTS",
                "案件已经存在唯一当前部门决定请求。",
            )
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not request_id.strip():
            return self._rejected(envelope, "INVALID_COMMAND", "缺少部门请求标识。")
        request_sequence = case.get("department_request_sequence", 0) + 1
        expected_request_id = "department-request:{}:{}".format(
            envelope["aggregate_id"], request_sequence
        )
        if request_id != expected_request_id:
            return self._rejected(
                envelope,
                "REQUEST_ID_NOT_CURRENT",
                "部门请求标识必须绑定 Case 单调请求序号。",
            )
        request = {
            "request_id": request_id,
            "request_sequence": request_sequence,
            "revision": 1,
            "status": "OPEN",
            "assessment_ref": {
                "assessment_id": assessment["assessment_id"],
                "version": payload["assessment_version"],
                "manifest_hash": assessment["screening_manifest_hash"],
            },
            "owner_ref": deepcopy(owner),
            "allowed_decisions": ["INVITE", "HOLD", "REJECT"],
            "due_at": _format_time(self._now + timedelta(hours=4)),
            "sla_generation": request_sequence,
            "reminder_ordinal": 0,
            "max_reminders": 2,
            "quiet_hours": {"start_hour": 22, "end_hour": 8},
            "cancellation_epoch": request_sequence,
            "synthetic_only": True,
        }
        case.update(
            {
                "state": "AWAITING_DEPARTMENT_DECISION",
                "current_match_assessment_ref": deepcopy(request["assessment_ref"]),
                "department_decision_request": request,
                "department_request_sequence": request_sequence,
            }
        )
        case.setdefault("department_request_history", []).append(deepcopy(request))
        self._save_case(tenant_id, envelope["aggregate_id"], version + 1, case)
        pinned_event = self._append_event(
            tenant_id,
            "CurrentMatchAssessmentPinned",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                **deepcopy(request["assessment_ref"]),
                "request_generation": request_sequence,
            },
        )
        opened_event = self._append_event(
            tenant_id,
            "DepartmentDecisionRequestOpened",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                "request_id": request_id,
                "revision": 1,
                "assessment_id": assessment["assessment_id"],
                "assessment_version": payload["assessment_version"],
                "allowed_decisions": request["allowed_decisions"],
                "owner_actor_id": owner["actor_id"],
                "due_at": request["due_at"],
            },
        )
        return self._applied(
            envelope,
            [pinned_event, opened_event],
            {
                "effect": "DEPARTMENT_DECISION_REQUEST_OPENED",
                "application_case_id": envelope["aggregate_id"],
                "request_id": request_id,
                "request_revision": 1,
                "case_version": version + 1,
            },
        )

    def _handle_QueueDepartmentDelivery(self, envelope: JsonObject) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        payload = envelope["payload"]
        loaded = self._load_case(tenant_id, payload.get("application_case_id"))
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        case_version, case = loaded
        if (
            type(payload.get("expected_case_version")) is not int
            or payload.get("expected_case_version") != case_version
        ):
            return self._rejected(
                envelope, "STALE_CASE_VERSION", "外发排队没有钉住当前案件版本。"
            )
        if (
            type(payload.get("expected_lifecycle_epoch")) is not int
            or payload.get("expected_lifecycle_epoch") != case["lifecycle_epoch"]
        ):
            return self._rejected(
                envelope,
                "STALE_CASE_VERSION",
                "外发排队没有钉住当前案件生命周期代次。",
            )
        request = case.get("department_decision_request")
        current_error = self._validate_current_request(payload, case, request)
        if current_error:
            return self._rejected(envelope, current_error[0], current_error[1])
        recipient = payload.get("recipient_ref", {})
        recipient_error = self._validate_recipient(recipient, tenant_id, request)
        if recipient_error:
            return self._rejected(
                envelope, recipient_error[0], recipient_error[1]
            )
        action_type = payload.get("action_type")
        ordinal = payload.get("ordinal")
        if not isinstance(action_type, str) or action_type not in {
            "INITIAL_NOTICE",
            "REMINDER",
        }:
            return self._rejected(
                envelope, "ACTION_POLICY_BLOCKED", "当前切片不允许该外发动作。"
            )
        if type(ordinal) is not int or ordinal < 0:
            return self._rejected(
                envelope, "INVALID_COMMAND", "外发 ordinal 必须是非负整数。"
            )
        if action_type == "INITIAL_NOTICE" and ordinal != 0:
            return self._rejected(envelope, "INVALID_COMMAND", "初始通知 ordinal 必须为 0。")
        if action_type == "REMINDER" and (
            not isinstance(ordinal, int)
            or ordinal < 1
            or ordinal > request["reminder_ordinal"]
        ):
            return self._rejected(
                envelope, "REMINDER_NOT_AUTHORIZED", "催办 ordinal 尚未被当前请求授权。"
            )
        expected_action_id = _action_id(request, action_type, ordinal)
        if envelope["aggregate_id"] != expected_action_id:
            return self._rejected(
                envelope,
                "AGGREGATE_TARGET_MISMATCH",
                "外发动作必须指向当前请求和 ordinal 的唯一 ActionExecution。",
            )
        existing = self._db.execute(
            "SELECT state_json FROM screening_action_executions "
            "WHERE tenant_id = ? AND action_key = ?",
            (tenant_id, expected_action_id),
        ).fetchone()
        if existing:
            return self._applied(
                envelope,
                [],
                {
                    "effect": "ACTION_ALREADY_QUEUED",
                    "action_id": expected_action_id,
                },
            )
        action = {
            "action_id": expected_action_id,
            "action_type": action_type,
            "state": "QUEUED",
            "application_case_id": payload["application_case_id"],
            "case_lifecycle_epoch": case["lifecycle_epoch"],
            "request_id": request["request_id"],
            "request_revision": request["revision"],
            "sla_generation": request["sla_generation"],
            "cancellation_epoch": request["cancellation_epoch"],
            "ordinal": ordinal,
            "recipient_ref": deepcopy(recipient),
            "payload_summary": {
                "application_case_id": payload["application_case_id"],
                "request_id": request["request_id"],
                "request_revision": request["revision"],
                "deep_link_token_hash": _hash(
                    {
                        "case_id": payload["application_case_id"],
                        "request_id": request["request_id"],
                        "revision": request["revision"],
                    }
                ),
                "due_at": request["due_at"],
            },
            "attempt_count": 0,
            "max_attempts": 2,
            "receipt": None,
            "blocked_reason": None,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO screening_action_executions "
            "(tenant_id, action_id, action_key, version, state_json) VALUES (?, ?, ?, 1, ?)",
            (tenant_id, expected_action_id, expected_action_id, _canonical(action)),
        )
        event_id = self._append_event(
            tenant_id,
            "AutomationActionRequested",
            expected_action_id,
            {
                "application_case_id": payload["application_case_id"],
                "action_id": expected_action_id,
                "action_type": action_type,
                "request_id": request["request_id"],
                "request_revision": request["revision"],
                "sla_generation": request["sla_generation"],
                "ordinal": ordinal,
                "recipient_actor_id": recipient["actor_id"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "ACTION_QUEUED", "action_id": expected_action_id},
        )

    def _handle_ExecuteSyntheticDelivery(self, envelope: JsonObject) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        row = self._db.execute(
            "SELECT version, state_json FROM screening_action_executions "
            "WHERE tenant_id = ? AND action_id = ?",
            (tenant_id, envelope["aggregate_id"]),
        ).fetchone()
        if not row:
            return self._rejected(envelope, "NOT_FOUND", "外发动作不存在。")
        action = json.loads(row["state_json"])
        if action.get("state") == "SUPERSEDED":
            # The transition that cancelled the request already settled this
            # authority record.  A late worker receives a deterministic no-op
            # and can never revive or deliver the old Action.
            return self._applied(
                envelope,
                [],
                {
                    "effect": "ACTION_BLOCKED",
                    "action_id": envelope["aggregate_id"],
                    "reason": "ACTION_SUPERSEDED",
                },
            )
        if envelope["payload"].get("expected_action_version") != row["version"]:
            return self._rejected(
                envelope, "STALE_ACTION_VERSION", "外发执行没有钉住当前动作版本。"
            )
        if action["state"] not in {"QUEUED", "RETRYABLE_FAILED"}:
            return self._rejected(
                envelope, "INVALID_TRANSITION", "当前动作已经结算。"
            )
        if action["attempt_count"] >= action.get("max_attempts", 2):
            return self._rejected(
                envelope, "RETRY_BUDGET_EXHAUSTED", "外发动作已耗尽有限重试预算。"
            )

        loaded = self._load_case(tenant_id, action["application_case_id"])
        block_reason = None
        if not loaded:
            block_reason = "CASE_NOT_CURRENT"
        else:
            _, case = loaded
            request = case.get("department_decision_request")
            if (
                case["state"] != "AWAITING_DEPARTMENT_DECISION"
                or case["lifecycle_epoch"] != action["case_lifecycle_epoch"]
                or not request
                or request.get("status") != "OPEN"
                or request.get("request_id") != action["request_id"]
                or request.get("revision") != action["request_revision"]
                or request.get("sla_generation") != action["sla_generation"]
                or request.get("cancellation_epoch")
                != action["cancellation_epoch"]
            ):
                block_reason = "REQUEST_NOT_CURRENT"
            elif self._validate_recipient(
                action["recipient_ref"], tenant_id, request
            ):
                block_reason = "RECIPIENT_SCOPE_MISMATCH"
            elif action["action_type"] == "REMINDER" and self._in_quiet_hours(
                request
            ):
                block_reason = "QUIET_HOURS"

        if block_reason:
            action.update(
                {
                    "state": "BLOCKED",
                    "blocked_reason": block_reason,
                    "attempt_count": action["attempt_count"] + 1,
                }
            )
            self._save_action(tenant_id, envelope["aggregate_id"], row["version"] + 1, action)
            event_id = self._append_event(
                tenant_id,
                "AutomationActionBlocked",
                envelope["aggregate_id"],
                {
                    "application_case_id": action["application_case_id"],
                    "action_id": action["action_id"],
                    "reason": block_reason,
                    "request_id": action["request_id"],
                    "request_revision": action["request_revision"],
                },
            )
            return self._applied(
                envelope,
                [event_id],
                {
                    "effect": "ACTION_BLOCKED",
                    "action_id": action["action_id"],
                    "reason": block_reason,
                },
            )

        outcome = envelope["payload"].get("synthetic_outcome", "SUCCESS")
        action["attempt_count"] += 1
        if outcome == "SUCCESS":
            action.update(
                {
                    "state": "SUCCEEDED",
                    "receipt": {
                        "provider": "synthetic-delivery-adapter",
                        "provider_receipt_id": "receipt:{}".format(
                            action["action_id"]
                        ),
                        "delivered_at": _format_time(self._now),
                        "synthetic_only": True,
                    },
                }
            )
            event_type = "AutomationActionSucceeded"
            effect = "SYNTHETIC_DELIVERY_RECEIPT_RECORDED"
        elif outcome == "RETRYABLE_FAILURE":
            exhausted = action["attempt_count"] >= action.get("max_attempts", 2)
            action["state"] = "BLOCKED" if exhausted else "RETRYABLE_FAILED"
            action["blocked_reason"] = (
                "RETRY_BUDGET_EXHAUSTED" if exhausted else None
            )
            action["receipt"] = {
                "provider": "synthetic-delivery-adapter",
                "error_code": "SYNTHETIC_TEMPORARY_FAILURE",
                "synthetic_only": True,
            }
            if exhausted:
                action["exception"] = {
                    "bundle_id": "exception:delivery:{}".format(action["action_id"]),
                    "status": "OPEN",
                    "code": "DELIVERY_RETRY_EXHAUSTED",
                    "application_case_id": action["application_case_id"],
                    "action_id": action["action_id"],
                    "request_id": action["request_id"],
                    "request_revision": action["request_revision"],
                    "facts": {
                        "attempt_count": action["attempt_count"],
                        "max_attempts": action.get("max_attempts", 2),
                    },
                    "options": ["CHECK_PROVIDER", "USE_APPROVED_MANUAL_ROUTE"],
                    "synthetic_only": True,
                }
            event_type = "AutomationActionFailed"
            effect = (
                "RETRY_BUDGET_EXHAUSTED"
                if exhausted
                else "SYNTHETIC_DELIVERY_FAILED"
            )
        else:
            return self._rejected(
                envelope, "INVALID_COMMAND", "未知的合成外发结果。"
            )
        self._save_action(tenant_id, envelope["aggregate_id"], row["version"] + 1, action)
        event_id = self._append_event(
            tenant_id,
            event_type,
            envelope["aggregate_id"],
            {
                "application_case_id": action["application_case_id"],
                "action_id": action["action_id"],
                "action_type": action["action_type"],
                "request_id": action["request_id"],
                "request_revision": action["request_revision"],
                "ordinal": action["ordinal"],
                "synthetic_only": True,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": effect, "action_id": action["action_id"]},
        )

    def _handle_AdvanceReminderOrdinal(self, envelope: JsonObject) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        loaded = self._load_case(tenant_id, envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        stale = self._validate_case_expectations(envelope, version, case)
        if stale:
            return stale
        request = case.get("department_decision_request")
        current_error = self._validate_current_request(
            envelope["payload"], case, request
        )
        if current_error:
            return self._rejected(envelope, current_error[0], current_error[1])
        if self._now < _parse_time(request["due_at"]):
            return self._rejected(
                envelope, "REMINDER_NOT_DUE", "当前请求尚未到催办时间。"
            )
        if self._in_quiet_hours(request):
            return self._rejected(
                envelope, "QUIET_HOURS", "当前处于静默时段，未消耗催办 ordinal。"
            )
        previous_ordinal = request["reminder_ordinal"]
        if previous_ordinal > 0:
            previous_action_id = _action_id(request, "REMINDER", previous_ordinal)
            previous_row = self._db.execute(
                "SELECT state_json FROM screening_action_executions "
                "WHERE tenant_id = ? AND action_id = ?",
                (tenant_id, previous_action_id),
            ).fetchone()
            previous_action = (
                json.loads(previous_row["state_json"]) if previous_row else None
            )
            if not previous_action or previous_action.get("state") != "SUCCEEDED":
                return self._rejected(
                    envelope,
                    "PREVIOUS_REMINDER_NOT_DELIVERED",
                    "上一 ordinal 尚无合成送达回执，不能继续催办或上报。",
                )
        if request["reminder_ordinal"] >= request["max_reminders"]:
            current_exception = case.get("screening_exception")
            same_open_exception = (
                isinstance(current_exception, dict)
                and current_exception.get("status") == "OPEN"
                and current_exception.get("request_revision") == request["revision"]
                and current_exception.get("sla_generation")
                == request["sla_generation"]
            )
            if not same_open_exception:
                exception = {
                    "bundle_id": "exception:department-overdue:{}:r{}:g{}".format(
                        request["request_id"],
                        request["revision"],
                        request["sla_generation"],
                    ),
                    "status": "OPEN",
                    "code": "DEPARTMENT_DECISION_OVERDUE",
                    "application_case_id": envelope["aggregate_id"],
                    "request_id": request["request_id"],
                    "request_revision": request["revision"],
                    "sla_generation": request["sla_generation"],
                    "owner_role": "RECRUITING_OPS",
                    "facts": {
                        "reminders_sent": request["reminder_ordinal"],
                        "max_reminders": request["max_reminders"],
                    },
                    "options": ["REASSIGN_OWNER", "EXTEND_SLA", "PAUSE_CASE"],
                    "synthetic_only": True,
                }
                case["screening_exception"] = exception
                self._save_case(tenant_id, envelope["aggregate_id"], version + 1, case)
                breached = self._append_event(
                    tenant_id,
                    "SlaDeadlineBreached",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "request_id": request["request_id"],
                        "generation": request["sla_generation"],
                        "due_at": request["due_at"],
                        "owner_actor_id": request["owner_ref"]["actor_id"],
                    },
                )
                opened = self._append_event(
                    tenant_id,
                    "ExceptionBundleOpened",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "exception_id": exception["bundle_id"],
                        "code": exception["code"],
                        "request_id": request["request_id"],
                    },
                )
                events = [breached, opened]
            else:
                events = []
            return self._applied(
                envelope,
                events,
                {
                    "effect": "REMINDER_LIMIT_EXHAUSTED",
                    "exception_id": case["screening_exception"]["bundle_id"],
                },
            )

        request["reminder_ordinal"] += 1
        request["due_at"] = _format_time(_parse_time(request["due_at"]) + timedelta(hours=1))
        self._replace_request_history(case, request)
        self._save_case(tenant_id, envelope["aggregate_id"], version + 1, case)
        event_id = self._append_event(
            tenant_id,
            "DepartmentReminderOrdinalAdvanced",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                "request_id": request["request_id"],
                "request_revision": request["revision"],
                "generation": request["sla_generation"],
                "ordinal": request["reminder_ordinal"],
                "channel": "SYNTHETIC_MESSAGE",
                "not_before": _format_time(self._now),
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "REMINDER_AUTHORIZED",
                "ordinal": request["reminder_ordinal"],
                "case_version": version + 1,
            },
        )

    def _handle_RecordDepartmentDecision(self, envelope: JsonObject) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        loaded = self._load_case(tenant_id, envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        stale = self._validate_case_expectations(envelope, version, case)
        if stale:
            return stale
        actor = envelope["actor"]
        if actor.get("actor_type") != "HUMAN":
            return self._rejected(
                envelope,
                "HUMAN_AUTHORITY_REQUIRED",
                "INVITE、HOLD、REJECT 只能由当前授权 HUMAN 主动提交。",
            )
        request = case.get("department_decision_request")
        current_error = self._validate_current_request(
            envelope["payload"], case, request
        )
        if current_error:
            return self._rejected(envelope, current_error[0], current_error[1])
        if (
            actor.get("actor_id") != request["owner_ref"]["actor_id"]
            or actor.get("role") != "HIRING_OWNER"
            or envelope["payload"].get("authority_revision")
            != request["owner_ref"]["authority_revision"]
            or self._validate_owner(request["owner_ref"], tenant_id)
        ):
            return self._rejected(
                envelope,
                "HUMAN_AUTHORITY_REQUIRED",
                "当前 HUMAN 不是该请求的有效用人负责人。",
            )
        decision_type = envelope["payload"].get("decision_type")
        raw_reason = envelope["payload"].get("reason")
        reason = raw_reason.strip() if isinstance(raw_reason, str) else ""
        if decision_type not in request["allowed_decisions"] or not reason:
            return self._rejected(
                envelope, "INVALID_COMMAND", "决定类型或人工依据不完整。"
            )
        revisit_at = envelope["payload"].get("revisit_at")
        if decision_type == "HOLD":
            try:
                revisit_due = _parse_time(revisit_at) if revisit_at else None
            except (TypeError, ValueError):
                revisit_due = None
            if not revisit_due or revisit_due <= self._now:
                return self._rejected(
                    envelope,
                    "INVALID_COMMAND",
                    "HOLD 必须给出未来的 revisit_at。",
                )
        if envelope["payload"].get("assessment_ref") != request["assessment_ref"]:
            return self._rejected(
                envelope, "ASSESSMENT_NOT_CURRENT", "决定没有引用当前匹配材料。"
            )
        decision_id = envelope["payload"].get(
            "decision_id", "decision:{}:{}".format(request["request_id"], version)
        )
        if not isinstance(decision_id, str) or not decision_id.strip():
            return self._rejected(envelope, "INVALID_COMMAND", "人工决定标识无效。")
        if any(
            item.get("decision_id") == decision_id
            for item in case.get("department_decisions", [])
        ):
            return self._rejected(
                envelope, "DECISION_ID_CONFLICT", "该人工决定标识已经用于其他决定。"
            )
        decision = {
            "decision_id": decision_id,
            "decision_type": decision_type,
            "request_id": request["request_id"],
            "request_revision": request["revision"],
            "assessment_ref": deepcopy(request["assessment_ref"]),
            "actor": deepcopy(actor),
            "authority_revision": envelope["payload"]["authority_revision"],
            "reason": reason,
            "recorded_at": _format_time(self._now),
            "synthetic_only": True,
        }
        case.setdefault("department_decisions", []).append(decision)
        recorded = self._append_event(
            tenant_id,
            "DepartmentDecisionRecorded",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                "decision_id": decision["decision_id"],
                "decision_type": decision_type,
                "request_id": request["request_id"],
                "request_revision": request["revision"],
                "human_actor_id": actor["actor_id"],
                "assessment_id": request["assessment_ref"]["assessment_id"],
            },
        )
        resolution_events = []
        exception = case.get("screening_exception")
        if isinstance(exception, dict) and exception.get("status") == "OPEN":
            exception.update(
                {
                    "status": "RESOLVED",
                    "resolution": "HUMAN_DECISION_RECORDED",
                    "resolved_at": _format_time(self._now),
                    "decision_ref": decision_id,
                }
            )
            resolution_events.append(
                self._append_event(
                    tenant_id,
                    "ExceptionBundleResolved",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "exception_id": exception["bundle_id"],
                        "resolution": exception["resolution"],
                        "decision_id": decision_id,
                    },
                )
            )
        for exception_id in self._settle_request_actions(
            tenant_id,
            case,
            request,
            reason="HUMAN_{}".format(decision_type),
            exception_status="RESOLVED",
        ):
            resolution_events.append(
                self._append_event(
                    tenant_id,
                    "ActionExceptionResolvedByCaseTransition",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "exception_id": exception_id,
                        "status": "RESOLVED",
                        "reason": "HUMAN_{}".format(decision_type),
                    },
                )
            )
        if decision_type == "HOLD":
            old_revision = request["revision"]
            request.update(
                {
                    "revision": old_revision + 1,
                    "status": "ON_HOLD",
                    "revisit_at": revisit_at,
                    "sla_generation": request["sla_generation"] + 1,
                    "reminder_ordinal": 0,
                    "cancellation_epoch": request["cancellation_epoch"] + 1,
                }
            )
            self._replace_request_history(case, request, append_revision=True)
            event_id = self._append_event(
                tenant_id,
                "DepartmentDecisionRequestHeld",
                envelope["aggregate_id"],
                {
                    "application_case_id": envelope["aggregate_id"],
                    "request_id": request["request_id"],
                    "old_revision": old_revision,
                    "new_revision": request["revision"],
                    "decision_id": decision["decision_id"],
                    "reason": reason,
                    "revisit_at": revisit_at,
                    "generation": request["sla_generation"],
                    "cancellation_epoch": request["cancellation_epoch"],
                },
            )
            events = [recorded, *resolution_events, event_id]
            effect = "DEPARTMENT_REQUEST_HELD"
        else:
            request["status"] = "CLOSED"
            request["closed_at"] = _format_time(self._now)
            request["decision_ref"] = decision["decision_id"]
            request["cancellation_epoch"] += 1
            case["state"] = "INTERVIEWING" if decision_type == "INVITE" else "CLOSED"
            self._replace_request_history(case, request)
            closed = self._append_event(
                tenant_id,
                "DepartmentDecisionRequestClosed",
                envelope["aggregate_id"],
                {
                    "application_case_id": envelope["aggregate_id"],
                    "request_id": request["request_id"],
                    "request_revision": request["revision"],
                    "decision_id": decision["decision_id"],
                    "reason": "HUMAN_{}".format(decision_type),
                    "closed_at": request["closed_at"],
                },
            )
            events = [recorded, *resolution_events, closed]
            effect = "HUMAN_{}_RECORDED".format(decision_type)
        self._save_case(tenant_id, envelope["aggregate_id"], version + 1, case)
        return self._applied(
            envelope,
            events,
            {
                "effect": effect,
                "decision_id": decision["decision_id"],
                "case_version": version + 1,
                "request_revision": request["revision"],
            },
        )

    def _handle_ResumeDepartmentDecisionRequest(
        self, envelope: JsonObject
    ) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        loaded = self._load_case(tenant_id, envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        stale = self._validate_case_expectations(envelope, version, case)
        if stale:
            return stale
        request = case.get("department_decision_request")
        payload = envelope["payload"]
        if (
            case["state"] != "AWAITING_DEPARTMENT_DECISION"
            or not request
            or request.get("status") != "ON_HOLD"
            or payload.get("request_id") != request.get("request_id")
            or payload.get("request_revision") != request.get("revision")
            or payload.get("sla_generation") != request.get("sla_generation")
        ):
            return self._rejected(
                envelope, "STALE_REQUEST_REVISION", "HOLD 请求已不是当前修订。"
            )
        if self._now < _parse_time(request["revisit_at"]):
            return self._rejected(
                envelope, "HOLD_REVISIT_NOT_DUE", "尚未到人工设定的回访时间。"
            )
        if (
            not case.get("current_match_assessment_ref")
            or case["current_match_assessment_ref"] != request["assessment_ref"]
            or self._validate_owner(request["owner_ref"], tenant_id)
        ):
            return self._rejected(
                envelope, "REQUEST_NOT_CURRENT", "材料或 Owner 已不再当前。"
            )
        old_revision = request["revision"]
        request.update(
            {
                "revision": old_revision + 1,
                "status": "OPEN",
                "revisit_at": None,
                "sla_generation": request["sla_generation"] + 1,
                "reminder_ordinal": 0,
                "due_at": _format_time(self._now + timedelta(hours=4)),
                "cancellation_epoch": request["cancellation_epoch"] + 1,
            }
        )
        self._replace_request_history(case, request, append_revision=True)
        self._save_case(tenant_id, envelope["aggregate_id"], version + 1, case)
        event_id = self._append_event(
            tenant_id,
            "DepartmentDecisionRequestResumed",
            envelope["aggregate_id"],
            {
                "application_case_id": envelope["aggregate_id"],
                "request_id": request["request_id"],
                "old_revision": old_revision,
                "new_revision": request["revision"],
                "generation": request["sla_generation"],
                "due_at": request["due_at"],
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "DEPARTMENT_REQUEST_RESUMED",
                "request_revision": request["revision"],
                "sla_generation": request["sla_generation"],
                "case_version": version + 1,
            },
        )

    def _handle_InvalidateCurrentMatchAssessment(
        self, envelope: JsonObject
    ) -> JsonObject:
        tenant_id = envelope["tenant_id"]
        loaded = self._load_case(tenant_id, envelope["aggregate_id"])
        if not loaded:
            return self._rejected(envelope, "NOT_FOUND", "申请案件不存在。")
        version, case = loaded
        stale = self._validate_case_expectations(envelope, version, case)
        if stale:
            return stale
        payload = envelope["payload"]
        current = case.get("current_match_assessment_ref")
        if not current or payload.get("assessment_ref") != current:
            return self._rejected(
                envelope, "ASSESSMENT_NOT_CURRENT", "目标材料不是当前材料。"
            )
        cause_error = self._validate_invalidation_cause(payload)
        if cause_error:
            return self._rejected(envelope, cause_error[0], cause_error[1])
        reason = payload["reason"].strip()
        causal_input_ref = payload["causal_input_ref"].strip()
        causal_input_version = payload["causal_input_version"]
        request = case.get("department_decision_request")
        events = []
        if request and request.get("status") in {"OPEN", "ON_HOLD"}:
            superseded = deepcopy(request)
            superseded.update(
                {
                    "status": "SUPERSEDED",
                    "cancellation_epoch": request["cancellation_epoch"] + 1,
                    "superseded_reason": reason,
                }
            )
            self._replace_request_history(case, superseded)
            events.append(
                self._append_event(
                    tenant_id,
                    "DepartmentDecisionRequestSuperseded",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "request_id": request["request_id"],
                        "request_revision": request["revision"],
                        "reason": reason,
                    },
                )
            )
        for exception_id in self._settle_request_actions(
            tenant_id,
            case,
            request,
            reason="SCREENING_INPUT_INVALIDATED",
            exception_status="SUPERSEDED",
        ):
            events.append(
                self._append_event(
                    tenant_id,
                    "ActionExceptionSupersededByCaseTransition",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "exception_id": exception_id,
                        "status": "SUPERSEDED",
                        "reason": "SCREENING_INPUT_INVALIDATED",
                    },
                )
            )
        resolved_exception_id = self._resolve_screening_exception(
            case,
            resolution="SCREENING_INPUT_INVALIDATED",
            causal_ref=causal_input_ref,
        )
        if resolved_exception_id:
            events.append(
                self._append_event(
                    tenant_id,
                    "ExceptionBundleResolved",
                    envelope["aggregate_id"],
                    {
                        "application_case_id": envelope["aggregate_id"],
                        "exception_id": resolved_exception_id,
                        "resolution": "SCREENING_INPUT_INVALIDATED",
                    },
                )
            )
        manifest = case.get("screening_input_manifest")
        if manifest:
            manifest["status"] = "INVALIDATED"
            manifest["invalidation_reason"] = reason
            if case.get("screening_input_history"):
                case["screening_input_history"][-1] = deepcopy(manifest)
        case.update(
            {
                "state": "SCREENING",
                "screening_input_manifest": None,
                "current_match_assessment_ref": None,
                "department_decision_request": None,
            }
        )
        self._save_case(tenant_id, envelope["aggregate_id"], version + 1, case)
        events.insert(
            0,
            self._append_event(
                tenant_id,
                "CurrentMatchAssessmentInvalidated",
                envelope["aggregate_id"],
                {
                    "application_case_id": envelope["aggregate_id"],
                    "assessment_id": current["assessment_id"],
                    "assessment_version": current["version"],
                    "reason": reason,
                    "causal_input_ref": causal_input_ref,
                    "causal_input_version": causal_input_version,
                },
            ),
        )
        return self._applied(
            envelope,
            events,
            {
                "effect": "CURRENT_MATCH_ASSESSMENT_INVALIDATED",
                "case_version": version + 1,
            },
        )

    def _validate_invalidation_cause(
        self, payload: JsonObject
    ) -> Optional[Tuple[str, str]]:
        allowed = {
            "expected_case_version",
            "expected_lifecycle_epoch",
            "assessment_ref",
            "reason",
            "causal_input_ref",
            "causal_input_version",
        }
        if set(payload) - allowed:
            return "INVALID_COMMAND", "失效命令包含未声明字段。"
        causal_ref = payload.get("causal_input_ref")
        if (
            not isinstance(causal_ref, str)
            or not causal_ref.strip()
            or len(causal_ref.strip()) > 128
            or any(
                not (character.isalnum() or character in "-_:./")
                for character in causal_ref.strip()
            )
        ):
            return "INVALID_COMMAND", "因果输入引用必须是受控非空标识。"
        causal_version = payload.get("causal_input_version")
        if type(causal_version) is not int or causal_version < 1:
            return "INVALID_COMMAND", "因果输入版本必须是正整数。"
        raw_reason = payload.get("reason")
        if not isinstance(raw_reason, str):
            return "INVALID_COMMAND", "失效原因必须是受控字符串。"
        reason = raw_reason.strip()
        controlled_reason = (
            3 <= len(reason) <= 64
            and reason[0].isalpha()
            and all(character.isupper() or character.isdigit() or character == "_" for character in reason)
        )
        if reason not in self._INVALIDATION_REASONS and not controlled_reason:
            return "INVALID_COMMAND", "失效原因不在受控枚举中。"
        return None

    def _validate_current_sources(
        self, case: JsonObject, resume_ref: JsonObject, profile_ref: JsonObject
    ) -> Optional[Tuple[str, str]]:
        if not isinstance(resume_ref, dict) or not isinstance(profile_ref, dict):
            return "INVALID_COMMAND", "简历与岗位画像引用必须是结构化对象。"
        if resume_ref != case.get("current_structured_resume_ref"):
            return "RESUME_VERSION_NOT_CURRENT", "结构化简历不是 Case 当前简历。"
        submission_id = resume_ref.get("submission_id")
        if submission_id not in case.get("submission_ids", []):
            return "RESUME_VERSION_NOT_CURRENT", "结构化简历不属于当前申请案件。"
        loaded = self._load_submission(case["application_key"]["tenant_id"], submission_id)
        if not loaded:
            return "RESUME_VERSION_NOT_CURRENT", "当前结构化简历不存在。"
        _, submission = loaded
        versions = submission.get("structured_resume_versions", [])
        if (
            not versions
            or type(resume_ref.get("version")) is not int
            or resume_ref.get("version") != versions[-1]["version"]
        ):
            return "RESUME_VERSION_NOT_CURRENT", "结构化简历版本已不是当前版本。"
        if versions[-1].get("quality_score", 0) < 0.7:
            return "RESUME_VERSION_UNREADABLE", "结构化简历质量不足。"
        expected_profile = {
            "profile_id": self._profile["profile_id"],
            "version": self._profile["version"],
            "publication_revision": self._profile["publication_revision"],
            "safety_epoch": self._profile["safety_epoch"],
        }
        if self._profile["state"] != "ACTIVE" or profile_ref != expected_profile:
            return "ROLE_PROFILE_NOT_CURRENT", "岗位画像不是当前 ACTIVE 已发布版本。"
        if case["application_key"]["requisition_id"] != self._profile[
            "requisition_id"
        ]:
            return "ROLE_PROFILE_SCOPE_MISMATCH", "岗位画像不属于当前岗位需求。"
        return None

    def _validate_assessment_payload(
        self, payload: JsonObject, manifest: JsonObject
    ) -> Optional[Tuple[str, str]]:
        allowed_payload_keys = {
            "application_case_id",
            "expected_case_version",
            "expected_lifecycle_epoch",
            "screening_manifest_hash",
            "dimensions",
            "result_band",
        }
        if set(payload) - allowed_payload_keys:
            if self._contains_prohibited_content(payload):
                return (
                    "PROHIBITED_FEATURE_DETECTED",
                    "材料包含保护/代理特征、提示注入或禁止的决定/排名字段。",
                )
            return "MATCH_VALIDATION_FAILED", "匹配材料包含未声明的顶层字段。"
        dimensions = payload.get("dimensions")
        if not isinstance(dimensions, list) or not dimensions:
            return "MATCH_VALIDATION_FAILED", "匹配材料缺少逐维证据。"
        if not all(isinstance(item, dict) for item in dimensions):
            return "MATCH_VALIDATION_FAILED", "画像维度必须是结构化对象。"
        expected = {
            item["criterion_ref"]: item["criterion_type"]
            for item in self._profile["criteria"]
        }
        actual = [item.get("criterion_ref") for item in dimensions]
        if not all(isinstance(item, str) for item in actual):
            return "MATCH_VALIDATION_FAILED", "画像维度标识必须是字符串。"
        if set(actual) != set(expected) or len(actual) != len(expected):
            return "MATCH_VALIDATION_FAILED", "画像维度缺失或重复。"
        result_band = payload.get("result_band")
        if not isinstance(result_band, str) or result_band not in {
            "HIGH",
            "MEDIUM",
            "LOW",
            "INSUFFICIENT",
        }:
            return "MATCH_VALIDATION_FAILED", "result band 无效。"
        if self._contains_prohibited_content(payload):
            return (
                "PROHIBITED_FEATURE_DETECTED",
                "材料包含保护/代理特征、提示注入或禁止的决定/排名字段。",
            )
        allowed_fields = set(manifest["allowed_fields"])
        resume_ref = manifest["structured_resume_ref"]
        loaded_resume = self._load_submission(
            "tenant-synthetic", resume_ref["submission_id"]
        )
        if not loaded_resume:
            return "MATCH_INPUT_STALE", "匹配材料引用的结构化简历不存在。"
        _, submission = loaded_resume
        versions = submission.get("structured_resume_versions", [])
        if not versions or versions[-1]["version"] != resume_ref["version"]:
            return "MATCH_INPUT_STALE", "匹配材料引用的结构化简历已不是当前版本。"
        source_fields = {
            (field["name"], field["locator"]): field
            for field in versions[-1].get("routable_fields", [])
            if isinstance(field, dict)
            and field.get("name") in allowed_fields
            and isinstance(field.get("locator"), str)
        }
        expected_source_ref = "{}:resume:{}".format(
            resume_ref["submission_id"], resume_ref["version"]
        )
        valid_findings = {"SUPPORT", "COUNTER_EVIDENCE", "UNKNOWN", "NOT_APPLICABLE"}
        for dimension in dimensions:
            if set(dimension) != {
                "criterion_ref",
                "criterion_type",
                "finding",
                "summary",
                "evidence_atoms",
            }:
                return "MATCH_VALIDATION_FAILED", "画像维度不符合封闭结构。"
            criterion_ref = dimension.get("criterion_ref")
            if (
                not isinstance(criterion_ref, str)
                or dimension.get("criterion_type") != expected.get(criterion_ref)
                or (
                    "summary" in dimension
                    and not isinstance(dimension.get("summary"), str)
                )
            ):
                return "MATCH_VALIDATION_FAILED", "画像维度与当前岗位标准不一致。"
            finding = dimension.get("finding")
            atoms = dimension.get("evidence_atoms", [])
            if (
                not isinstance(finding, str)
                or finding not in valid_findings
                or not isinstance(atoms, list)
            ):
                return "MATCH_VALIDATION_FAILED", "画像维度结论无效。"
            if dimension.get("summary") != self._APPROVED_DIMENSION_SUMMARIES.get(
                finding
            ):
                return (
                    "MATCH_VALIDATION_FAILED",
                    "画像摘要不是当前策略允许的确定性表达。",
                )
            if finding in {"SUPPORT", "COUNTER_EVIDENCE"} and not atoms:
                return "MATCH_VALIDATION_FAILED", "事实性结论必须有来源证据。"
            for atom in atoms:
                if not isinstance(atom, dict):
                    return "MATCH_VALIDATION_FAILED", "证据单元必须是结构化对象。"
                if set(atom) != {
                    "source_ref",
                    "locator",
                    "field_name",
                    "excerpt_hash",
                }:
                    return "MATCH_VALIDATION_FAILED", "证据单元不符合封闭结构。"
                if not {"source_ref", "locator", "field_name", "excerpt_hash"}.issubset(
                    atom
                ):
                    return "MATCH_VALIDATION_FAILED", "证据单元缺少原文定位。"
                if not all(
                    isinstance(atom.get(key), str) and atom.get(key)
                    for key in ("source_ref", "locator", "field_name", "excerpt_hash")
                ):
                    return "MATCH_VALIDATION_FAILED", "证据单元字段类型无效。"
                if atom["field_name"] not in allowed_fields:
                    return "FIELD_POLICY_VIOLATION", "证据引用了未允许字段。"
                source_field = source_fields.get(
                    (atom["field_name"], atom["locator"])
                )
                if (
                    atom["source_ref"] != expected_source_ref
                    or not source_field
                    or atom["excerpt_hash"]
                    != evidence_atom_hash(source_field, resume_ref["version"])
                ):
                    return "MATCH_VALIDATION_FAILED", "证据单元无法回到当前简历原文定位。"
        return None

    def _contains_prohibited_content(self, payload: JsonObject) -> bool:
        def walk(value: Any, key: Optional[str] = None) -> bool:
            normalized_key = str(key).strip().casefold() if key is not None else None
            if normalized_key in self._PROHIBITED_KEYS:
                return True
            if isinstance(value, dict):
                return any(walk(item, item_key) for item_key, item in value.items())
            if isinstance(value, list):
                return any(walk(item) for item in value)
            if isinstance(value, str):
                normalized = value.strip().casefold()
                if normalized_key in {"field_name", "feature_name", "source_field"}:
                    if normalized in self._PROHIBITED_FIELDS:
                        return True
                return any(
                    marker in normalized
                    for marker in (
                        self._INJECTION_MARKERS | self._PROHIBITED_TEXT_MARKERS
                    )
                )
            return False

        return walk(payload)

    def _validate_case_expectations(
        self, envelope: JsonObject, version: int, case: JsonObject
    ) -> Optional[JsonObject]:
        payload = envelope["payload"]
        if (
            type(payload.get("expected_case_version")) is not int
            or type(payload.get("expected_lifecycle_epoch")) is not int
            or payload.get("expected_case_version") != version
            or payload.get("expected_lifecycle_epoch") != case["lifecycle_epoch"]
        ):
            return self._rejected(
                envelope,
                "STALE_CASE_VERSION",
                "命令没有钉住当前 Case 版本和生命周期代次。",
            )
        return None

    def _validate_current_request(
        self,
        payload: JsonObject,
        case: JsonObject,
        request: Optional[JsonObject],
    ) -> Optional[Tuple[str, str]]:
        if (
            case.get("state") != "AWAITING_DEPARTMENT_DECISION"
            or not request
            or request.get("status") != "OPEN"
        ):
            return "REQUEST_NOT_CURRENT", "部门决定请求已不在当前 OPEN 状态。"
        if (
            type(payload.get("request_revision")) is not int
            or type(payload.get("sla_generation")) is not int
            or
            payload.get("request_id") != request.get("request_id")
            or payload.get("request_revision") != request.get("revision")
            or payload.get("sla_generation") != request.get("sla_generation")
        ):
            return "STALE_REQUEST_REVISION", "命令引用了旧请求或 SLA generation。"
        return None

    def _validate_owner(
        self, owner: JsonObject, tenant_id: str
    ) -> Optional[Tuple[str, str]]:
        expected = deepcopy(self._owner)
        if not expected.pop("active") or tenant_id != expected["tenant_id"] or owner != expected:
            return "DEPARTMENT_OWNER_MISSING", "当前部门 Owner 不存在或权限已失效。"
        return None

    def _validate_recipient(
        self, recipient: JsonObject, tenant_id: str, request: JsonObject
    ) -> Optional[Tuple[str, str]]:
        if not isinstance(recipient, dict) or not isinstance(request, dict):
            return "RECIPIENT_SCOPE_MISMATCH", "外发收件人引用必须是结构化对象。"
        if (
            recipient.get("tenant_id") != tenant_id
            or recipient != request.get("owner_ref")
            or self._validate_owner(recipient, tenant_id)
        ):
            return (
                "RECIPIENT_SCOPE_MISMATCH",
                "外发收件人与当前租户、部门请求或权限修订不一致。",
            )
        return None

    def _load_case(
        self, tenant_id: str, application_case_id: Optional[str]
    ) -> Optional[Tuple[int, JsonObject]]:
        if not isinstance(application_case_id, str) or not application_case_id:
            return None
        row = self._db.execute(
            "SELECT version, state_json FROM application_cases "
            "WHERE tenant_id = ? AND application_case_id = ?",
            (tenant_id, application_case_id),
        ).fetchone()
        if not row:
            return None
        return row["version"], json.loads(row["state_json"])

    def _save_case(
        self, tenant_id: str, case_id: str, version: int, state: JsonObject
    ) -> None:
        self._db.execute(
            "UPDATE application_cases SET version = ?, state_json = ? "
            "WHERE tenant_id = ? AND application_case_id = ?",
            (version, _canonical(state), tenant_id, case_id),
        )

    def _load_assessment(
        self, tenant_id: str, assessment_id: Any, version: Any
    ) -> Optional[JsonObject]:
        if not isinstance(assessment_id, str) or type(version) is not int:
            return None
        row = self._db.execute(
            "SELECT version, state_json FROM match_assessments "
            "WHERE tenant_id = ? AND assessment_id = ?",
            (tenant_id, assessment_id),
        ).fetchone()
        if not row or version != row["version"]:
            return None
        state = json.loads(row["state_json"])
        state["version"] = row["version"]
        return state

    def _save_action(
        self, tenant_id: str, action_id: str, version: int, state: JsonObject
    ) -> None:
        self._db.execute(
            "UPDATE screening_action_executions SET version = ?, state_json = ? "
            "WHERE tenant_id = ? AND action_id = ?",
            (version, _canonical(state), tenant_id, action_id),
        )

    def _replace_request_history(
        self, case: JsonObject, request: JsonObject, *, append_revision: bool = False
    ) -> None:
        case["department_decision_request"] = request
        history = case.setdefault("department_request_history", [])
        if append_revision or not history:
            history.append(deepcopy(request))
        else:
            history[-1] = deepcopy(request)

    def _resolve_screening_exception(
        self,
        case: JsonObject,
        *,
        resolution: str,
        causal_ref: Any = None,
    ) -> Optional[str]:
        exception = case.get("screening_exception")
        if not isinstance(exception, dict) or exception.get("status") != "OPEN":
            return None
        exception.update(
            {
                "status": "RESOLVED",
                "resolution": resolution,
                "resolved_at": _format_time(self._now),
                "causal_ref": causal_ref,
            }
        )
        return exception.get("bundle_id")

    def _settle_request_actions(
        self,
        tenant_id: str,
        case: JsonObject,
        request: Optional[JsonObject],
        *,
        reason: str,
        exception_status: str,
    ) -> list[str]:
        """Settle request-bound Actions at the authority record, in-transaction."""

        if not isinstance(request, dict):
            return []
        settled_exception_ids = []
        for row in self._db.execute(
            "SELECT action_id, version, state_json "
            "FROM screening_action_executions WHERE tenant_id = ? "
            "AND json_extract(state_json, '$.application_case_id') = ?",
            (tenant_id, case.get("application_case_id")),
        ):
            action = json.loads(row["state_json"])
            if (
                action.get("application_case_id")
                != case.get("application_case_id")
                or action.get("request_id") != request.get("request_id")
                or action.get("request_revision") != request.get("revision")
                or action.get("state") in {"SUCCEEDED", "SUPERSEDED"}
            ):
                continue
            action.update(
                {
                    "prior_state": action.get("state"),
                    "state": "SUPERSEDED",
                    "superseded_reason": reason,
                    "superseded_at": _format_time(self._now),
                }
            )
            exception = action.get("exception")
            if isinstance(exception, dict) and exception.get("status") == "OPEN":
                exception["status"] = exception_status
                exception["settled_at"] = _format_time(self._now)
                if exception_status == "RESOLVED":
                    exception["resolution"] = reason
                else:
                    exception["superseded_reason"] = reason
                if exception.get("bundle_id"):
                    settled_exception_ids.append(exception["bundle_id"])
            self._save_action(
                tenant_id, row["action_id"], row["version"] + 1, action
            )
        return settled_exception_ids

    def _in_quiet_hours(self, request: JsonObject) -> bool:
        hour = self._now.hour
        quiet = request["quiet_hours"]
        return hour >= quiet["start_hour"] or hour < quiet["end_hour"]

    @property
    def _now(self) -> datetime:
        """Read the injected clock at each business gate."""

        return self._clock()

    @property
    def synthetic_case_id(self) -> str:
        case_id = getattr(self, "_synthetic_case_id", None)
        if not isinstance(case_id, str) or not case_id:
            raise RuntimeError("synthetic Case has not been bound")
        return case_id

    def bind_synthetic_case(self, application_case_id: str) -> None:
        """Bind scenario helpers to one seeded Case without a tenant-wide read."""

        if (
            not isinstance(application_case_id, str)
            or not application_case_id
            or not self._load_case("tenant-synthetic", application_case_id)
        ):
            raise ValueError("synthetic Case does not exist")
        prior = getattr(self, "_synthetic_case_id", application_case_id)
        if prior != application_case_id:
            raise ValueError("synthetic control is already bound to another Case")
        self._synthetic_case_id = application_case_id

    def _install_screening_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS match_assessments (
                tenant_id TEXT NOT NULL,
                assessment_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                manifest_hash TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, assessment_id)
            );
            CREATE TABLE IF NOT EXISTS screening_action_executions (
                tenant_id TEXT NOT NULL,
                action_id TEXT NOT NULL,
                action_key TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, action_id),
                UNIQUE (tenant_id, action_key)
            );
            """
        )
        self._db.commit()


def _action_id(request: JsonObject, action_type: str, ordinal: int) -> str:
    return "action:{}:{}:{}:{}:{}".format(
        request["request_id"],
        request["revision"],
        request["sla_generation"],
        action_type.lower(),
        ordinal,
    )


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        character in "0123456789abcdef" for character in value
    )


def evidence_atom_hash(field: JsonObject, resume_version: int) -> str:
    """Bind an evidence atom to the exact current structured-resume fact."""

    return _hash(
        {
            "field_name": field["name"],
            "value": field["value"],
            "locator": field["locator"],
            "resume_version": resume_version,
        }
    )


def _parse_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc)


def _format_time(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
