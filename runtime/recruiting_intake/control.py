"""Deterministic, synthetic-only resume intake control plane."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from copy import deepcopy
from typing import Any, Dict, Iterable, Optional


class ResumeIntakeControl:
    """Own intake state transitions behind ``submit`` and ``read``."""

    def __init__(self, connection: sqlite3.Connection):
        self._db = connection
        self._db.row_factory = sqlite3.Row
        self._authority_grants = {
            (
                "tenant-synthetic",
                "SERVICE",
                "intake-workflow",
                "INTAKE_WORKFLOW",
            ),
            (
                "tenant-synthetic",
                "SERVICE",
                "resume-parser",
                "UNTRUSTED_CONTENT_PARSER",
            ),
            (
                "tenant-synthetic",
                "HUMAN",
                "hiring-owner-1",
                "HIRING_OWNER",
            ),
            (
                "tenant-synthetic",
                "HUMAN",
                "product-demo-user",
                "RECRUITING_OPS",
            ),
        }
        self._install_schema()

    def submit(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and apply one command, returning a stable CommandResult."""

        validation_error = self._validate_envelope(envelope)
        if validation_error:
            return self._rejected(envelope, validation_error[0], validation_error[1])

        tenant_id = envelope["tenant_id"]
        idem = envelope["idempotency_key"]
        canonical = _canonical(
            {
                "command_type": envelope["command_type"],
                "aggregate_type": envelope["aggregate_type"],
                "aggregate_id": envelope["aggregate_id"],
                "actor": envelope["actor"],
                "payload": envelope["payload"],
            }
        )
        payload_hash = _sha256(canonical)
        prior = self._db.execute(
            "SELECT payload_hash, result_json FROM command_results "
            "WHERE tenant_id = ? AND idempotency_key = ?",
            (tenant_id, idem),
        ).fetchone()
        if prior:
            if prior["payload_hash"] != payload_hash:
                return self._rejected(
                    envelope,
                    "IDEMPOTENCY_CONFLICT",
                    "同一幂等键对应了不同请求，未覆盖原事实。",
                )
            replay = json.loads(prior["result_json"])
            replay["status"] = "REPLAYED"
            return replay

        try:
            self._db.execute("BEGIN")
            handler = getattr(
                self,
                "_handle_{}".format(envelope["command_type"]),
                None,
            )
            if handler is None:
                result = self._rejected(
                    envelope,
                    "UNSUPPORTED_COMMAND",
                    "当前收件切片尚未实现该命令。",
                )
            else:
                result = handler(envelope)
            self._db.execute(
                "INSERT INTO command_results "
                "(tenant_id, idempotency_key, payload_hash, result_json) VALUES (?, ?, ?, ?)",
                (tenant_id, idem, payload_hash, _canonical(result)),
            )
            self._db.commit()
            return result
        except Exception:
            self._db.rollback()
            raise

    def read(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Return the current synthetic projection for one tenant."""

        tenant_id = request.get("tenant_id")
        if not tenant_id:
            raise ValueError("tenant_id is required")
        actor = request.get("actor_context")
        if not isinstance(actor, dict):
            raise PermissionError("actor_context is required")
        grant = (
            tenant_id,
            actor.get("actor_type"),
            actor.get("actor_id"),
            actor.get("role"),
        )
        if grant not in self._authority_grants:
            raise PermissionError("current actor is not authorized for this tenant")

        submissions: Dict[str, Dict[str, Any]] = {}
        for row in self._db.execute(
            "SELECT submission_id, version, state_json FROM submissions WHERE tenant_id = ?",
            (tenant_id,),
        ):
            state = json.loads(row["state_json"])
            state["version"] = row["version"]
            for resume_version in state.get("structured_resume_versions", []):
                resume_version["protected_fields"] = [
                    {
                        "name": field["name"],
                        "classification": "PROTECTED",
                        "redacted": True,
                    }
                    for field in resume_version.get("protected_fields", [])
                ]
                resume_version["quarantined_fields"] = [
                    {
                        "name": field["name"],
                        "classification": "QUARANTINED_UNRECOGNIZED",
                        "redacted": True,
                    }
                    for field in resume_version.get("quarantined_fields", [])
                ]
            submissions[row["submission_id"]] = state

        cases: Dict[str, Dict[str, Any]] = {}
        for row in self._db.execute(
            "SELECT application_case_id, version, state_json FROM application_cases "
            "WHERE tenant_id = ?",
            (tenant_id,),
        ):
            state = json.loads(row["state_json"])
            state["version"] = row["version"]
            cases[row["application_case_id"]] = state
            for submission_id in state["submission_ids"]:
                if submission_id in submissions:
                    submissions[submission_id]["application_case_id"] = row[
                        "application_case_id"
                    ]

        review_tasks = [
            deepcopy(state["review_task"])
            for state in submissions.values()
            if (state.get("review_task") or {}).get("status") == "OPEN"
        ]
        exception_bundles = [
            deepcopy(state["exception"])
            for state in submissions.values()
            if (state.get("exception") or {}).get("status") == "OPEN"
        ]
        events = list(
            self._db.execute(
                "SELECT event_type, event_json FROM events WHERE tenant_id = ? ORDER BY sequence_no",
                (tenant_id,),
            )
        )
        counts: Dict[str, int] = {}
        for row in events:
            counts[row["event_type"]] = counts.get(row["event_type"], 0) + 1

        tool_execution_count = sum(
            version.get("safety_counters", {}).get("tool_execution_count", 0)
            for state in submissions.values()
            for version in state.get("structured_resume_versions", [])
        )
        external_action_count = sum(
            version.get("safety_counters", {}).get("external_action_count", 0)
            for state in submissions.values()
            for version in state.get("structured_resume_versions", [])
        )
        return {
            "synthetic_only": True,
            "submissions": submissions,
            "cases": cases,
            "review_tasks": review_tasks,
            "exception_bundles": exception_bundles,
            "event_types": [row["event_type"] for row in events],
            "event_envelopes": [json.loads(row["event_json"]) for row in events],
            "business_effect_counts": counts,
            "tool_execution_count": tool_execution_count,
            "external_action_count": external_action_count,
        }

    def _handle_RegisterResumeSubmission(self, envelope: Dict[str, Any]) -> Dict[str, Any]:
        tenant_id = envelope["tenant_id"]
        payload = envelope["payload"]
        source = payload.get("source", {})
        required_source = {
            "channel",
            "source_event_id",
            "message_id",
            "attachment_id",
            "filename",
        }
        if not required_source.issubset(source):
            return self._rejected(
                envelope, "INVALID_COMMAND", "来源、消息和附件标识不完整。"
            )
        if not source.get("approved", False):
            return self._rejected(
                envelope, "SOURCE_NOT_ALLOWED", "来源不在当前批准范围内。"
            )

        if source.get("approved_source_ref") != "approved-source:synthetic:v1":
            return self._rejected(
                envelope,
                "SOURCE_NOT_ALLOWED",
                "来源没有绑定当前批准目录修订。",
            )
        content_sha256 = payload.get("content_sha256")
        application_intent_key = payload.get("application_intent_key")
        if not application_intent_key or not _is_sha256(content_sha256):
            return self._rejected(
                envelope, "INVALID_COMMAND", "缺少申请意图键或内容校验值。"
            )
        dedupe_fingerprint = _sha256(
            _canonical(
                {
                    "content_sha256": content_sha256,
                    "application_intent_key": application_intent_key,
                }
            )
        )
        registration_manifest_hash = _sha256(
            _canonical(
                {
                    "purpose": payload.get("purpose", "RECRUITING_INTAKE"),
                    "mime_type": payload.get("mime_type"),
                    "encrypted": bool(payload.get("encrypted")),
                    "corrupt": bool(payload.get("corrupt")),
                    "malicious": bool(payload.get("malicious")),
                    "scan_verdict": payload.get("scan_verdict", "PASS"),
                    "source": source,
                }
            )
        )
        stop_reason = _attachment_stop_reason(payload)

        source_key = "{}:{}".format(source["channel"], source["source_event_id"])
        attachment_key = "{}:{}".format(source["channel"], source["attachment_id"])
        observed_source = self._db.execute(
            "SELECT submission_id, content_sha256, dedupe_fingerprint, "
            "registration_manifest_hash, security_disposition "
            "FROM source_observations "
            "WHERE tenant_id = ? AND (source_key = ? OR attachment_key = ?)",
            (tenant_id, source_key, attachment_key),
        ).fetchone()
        if observed_source:
            if (
                observed_source["content_sha256"] != content_sha256
                or observed_source["dedupe_fingerprint"] != dedupe_fingerprint
                or observed_source["registration_manifest_hash"]
                != registration_manifest_hash
            ):
                return self._rejected(
                    envelope,
                    "SOURCE_EVENT_CONFLICT",
                    "同一来源事件或附件被复用于不同内容，未覆盖原事实。",
                )
            if observed_source["security_disposition"] == "BLOCKED":
                return self._rejected(
                    envelope,
                    "DUPLICATE_SOURCE_UNSAFE",
                    "该来源事件已有不可变的安全阻断事实，不能通过重放附加到案件。",
                )
            case_id = self._case_id_for_submission(
                tenant_id, observed_source["submission_id"]
            )
            return self._applied(
                envelope,
                [],
                {
                    "effect": "DUPLICATE_ATTACHED",
                    "submission_id": observed_source["submission_id"],
                    "application_case_id": case_id,
                },
            )

        duplicate = self._db.execute(
            "SELECT submission_id, version, state_json FROM submissions "
            "WHERE tenant_id = ? AND dedupe_fingerprint = ?",
            (tenant_id, dedupe_fingerprint),
        ).fetchone()
        if duplicate:
            if stop_reason:
                self._insert_source_observation(
                    tenant_id,
                    duplicate["submission_id"],
                    source_key,
                    attachment_key,
                    content_sha256,
                    dedupe_fingerprint,
                    registration_manifest_hash,
                    "BLOCKED",
                )
                return self._rejected(
                    envelope,
                    "DUPLICATE_SOURCE_UNSAFE",
                    "新的重复来源没有通过当前附件安全门，未附加到既有投递或案件。",
                )
            state = json.loads(duplicate["state_json"])
            public_source_key = _source_key(source)
            if public_source_key not in {_source_key(item) for item in state["sources"]}:
                state["sources"].append(_public_source(source))
                new_version = duplicate["version"] + 1
                self._db.execute(
                    "UPDATE submissions SET version = ?, state_json = ? "
                    "WHERE tenant_id = ? AND submission_id = ?",
                    (
                        new_version,
                        _canonical(state),
                        tenant_id,
                        duplicate["submission_id"],
                    ),
                )
                event_id = self._append_event(
                    tenant_id,
                    "ResumeSubmissionSourceAttached",
                    duplicate["submission_id"],
                    {
                        "submission_id": duplicate["submission_id"],
                        "source_channel": source["channel"],
                        "content_sha256": content_sha256,
                        "submission_version": new_version,
                    },
                )
                self._insert_source_observation(
                    tenant_id,
                    duplicate["submission_id"],
                    source_key,
                    attachment_key,
                    content_sha256,
                    dedupe_fingerprint,
                    registration_manifest_hash,
                    "ACCEPTED",
                )
            else:
                event_id = None
            case_id = self._case_id_for_submission(tenant_id, duplicate["submission_id"])
            return self._applied(
                envelope,
                [event_id] if event_id else [],
                {
                    "effect": "DUPLICATE_ATTACHED",
                    "submission_id": duplicate["submission_id"],
                    "application_case_id": case_id,
                },
            )

        submission_id = envelope["aggregate_id"]
        if self._load_submission(tenant_id, submission_id):
            return self._rejected(
                envelope, "AGGREGATE_CONFLICT", "投递标识已被其他事实占用。"
            )

        state = {
            "submission_id": submission_id,
            "state": "RECEIVED",
            "activity": "NEEDS_HUMAN" if stop_reason else "ACTIVE",
            "suspension": "RUNNING",
            "purpose": payload.get("purpose", "RECRUITING_INTAKE"),
            "content_sha256": content_sha256,
            "filename": source["filename"],
            "sources": [_public_source(source)],
            "attachment_gate": "BLOCKED" if stop_reason else "PASSED",
            "stop_reason": stop_reason,
            "structured_resume_versions": [],
            "identity_candidates": [],
            "routing_candidates": [],
            "routing_revision": None,
            "application_case_id": None,
            "untrusted_content_findings": [],
            "review_task": None,
            "exception": _exception_projection(submission_id, stop_reason)
            if stop_reason
            else None,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO submissions "
            "(tenant_id, submission_id, dedupe_fingerprint, version, state_json) "
            "VALUES (?, ?, ?, 1, ?)",
            (tenant_id, submission_id, dedupe_fingerprint, _canonical(state)),
        )
        self._insert_source_observation(
            tenant_id,
            submission_id,
            source_key,
            attachment_key,
            content_sha256,
            dedupe_fingerprint,
            registration_manifest_hash,
            "BLOCKED" if stop_reason else "ACCEPTED",
        )
        event_ids = [
            self._append_event(
                tenant_id,
                "ResumeSubmissionReceived",
                submission_id,
                {
                    "submission_id": submission_id,
                    "source_channel": source["channel"],
                    "content_sha256": content_sha256,
                    "purpose": state["purpose"],
                },
            )
        ]
        if stop_reason:
            event_ids.append(
                self._append_event(
                    tenant_id,
                    "AttachmentGateBlocked",
                    submission_id,
                    {"submission_id": submission_id, "reason": stop_reason},
                )
            )
        else:
            event_ids.append(
                self._append_event(
                    tenant_id,
                    "AttachmentGatePassed",
                    submission_id,
                    {
                        "submission_id": submission_id,
                        "content_sha256": content_sha256,
                    },
                )
            )
        return self._applied(
            envelope,
            event_ids,
            {
                "effect": "SUBMISSION_REGISTERED",
                "submission_id": submission_id,
                "blocked": bool(stop_reason),
            },
        )

    def _handle_RecordStructuredResumeVersion(
        self, envelope: Dict[str, Any]
    ) -> Dict[str, Any]:
        tenant_id = envelope["tenant_id"]
        submission = self._load_submission(tenant_id, envelope["aggregate_id"])
        if not submission:
            return self._rejected(envelope, "NOT_FOUND", "投递不存在。")
        version, state = submission
        if state["attachment_gate"] != "PASSED":
            return self._rejected(
                envelope, "INVALID_TRANSITION", "附件未通过安全门，不能解析。"
            )
        if state["state"] not in {"RECEIVED", "PARSING"}:
            return self._rejected(
                envelope, "INVALID_TRANSITION", "当前投递状态不允许追加解析版本。"
            )
        payload = envelope["payload"]
        quality_score = payload.get("quality_score")
        if isinstance(quality_score, bool) or not isinstance(
            quality_score, (int, float)
        ):
            return self._rejected(envelope, "INVALID_COMMAND", "缺少解析质量信号。")
        prior_exception = state.get("exception")
        attempts = prior_exception.get("attempt_count", 0) if prior_exception else 0
        retry_budget = prior_exception.get("retry_budget", 2) if prior_exception else 2
        if (
            prior_exception
            and prior_exception.get("reason") == "PARSE_QUALITY_TOO_LOW"
            and attempts >= retry_budget
        ):
            return self._rejected(
                envelope,
                "RETRY_BUDGET_EXHAUSTED",
                "解析重试预算已耗尽，等待当前 Owner 选择恢复路线。",
            )
        if quality_score < 0.7:
            exception = _exception_projection(
                envelope["aggregate_id"], "PARSE_QUALITY_TOO_LOW"
            )
            exception["attempt_count"] = attempts + 1
            state.update(
                {
                    "state": "PARSING",
                    "activity": "NEEDS_HUMAN",
                    "stop_reason": "PARSE_QUALITY_TOO_LOW",
                    "exception": exception,
                }
            )
            self._save_submission(tenant_id, envelope["aggregate_id"], version + 1, state)
            event_id = self._append_event(
                tenant_id,
                "ResumeParsingFailed",
                envelope["aggregate_id"],
                {
                    "submission_id": envelope["aggregate_id"],
                    "reason": "PARSE_QUALITY_TOO_LOW",
                    "quality_score": quality_score,
                },
            )
            return self._applied(
                envelope,
                [event_id],
                {"effect": "PARSING_BLOCKED", "submission_id": envelope["aggregate_id"]},
            )

        parser_output_error = _validate_parser_output(payload)
        if parser_output_error:
            return self._rejected(
                envelope, "INVALID_PARSER_OUTPUT", parser_output_error
            )
        fields = payload["fields"]
        if any(
            payload.get(counter, 0) != 0
            for counter in (
                "tool_execution_count",
                "external_read_count",
                "external_action_count",
            )
        ):
            return self._rejected(
                envelope,
                "UNTRUSTED_CONTENT_EFFECT_REJECTED",
                "不可信材料解析不得携带工具、额外读取或外部动作效果。",
            )
        normalized = []
        for field in fields:
            if not {"name", "value", "locator", "confidence"}.issubset(field):
                return self._rejected(
                    envelope, "INVALID_COMMAND", "字段缺少定位或置信信号。"
                )
            if (
                isinstance(field["confidence"], bool)
                or not isinstance(field["confidence"], (int, float))
                or not 0 <= field["confidence"] <= 1
            ):
                return self._rejected(envelope, "INVALID_COMMAND", "字段置信信号无效。")
            normalized.append(deepcopy(field))
        protected_names = {
            "age",
            "birth_date",
            "date_of_birth",
            "disability",
            "ethnicity",
            "gender",
            "marital_status",
            "photo",
            "political_affiliation",
            "reproductive_status",
            "religion",
        }
        routable_names = {
            "ai_product_years",
            "city",
            "current_title",
            "degree",
            "education",
            "email",
            "major",
            "name",
            "phone",
            "product_years",
            "skills",
            "work_experience",
        }
        protected = []
        routable = []
        quarantined = []
        for field in normalized:
            canonical_name = _canonical_field_name(field["name"])
            if (
                canonical_name in protected_names
                or field.get("classification") in {"PROTECTED", "SENSITIVE"}
            ):
                protected.append(field)
            elif canonical_name in routable_names:
                routable.append(field)
            else:
                quarantined.append(field)
        resume_version = len(state["structured_resume_versions"]) + 1
        structured = {
            "version": resume_version,
            "parser_version": payload.get("parser_version", "synthetic-parser-v1"),
            "source_content_sha256": state["content_sha256"],
            "quality_score": quality_score,
            "routable_fields": routable,
            "protected_fields": protected,
            "quarantined_fields": quarantined,
            "safety_counters": {
                "tool_execution_count": 0,
                "external_read_count": 0,
                "external_action_count": 0,
            },
        }
        findings = _prompt_injection_findings(payload.get("raw_text", ""))
        state.update(
            {
                "state": "PARSING",
                "activity": "ACTIVE",
                "stop_reason": None,
                "identity_candidates": deepcopy(payload.get("identity_candidates", [])),
                "routing_candidates": deepcopy(payload.get("routing_candidates", [])),
                "untrusted_content_findings": findings,
                "exception": None,
            }
        )
        state["structured_resume_versions"].append(structured)
        self._save_submission(tenant_id, envelope["aggregate_id"], version + 1, state)
        event_id = self._append_event(
            tenant_id,
            "StructuredResumeVersionCreated",
            envelope["aggregate_id"],
            {
                "submission_id": envelope["aggregate_id"],
                "structured_resume_version": resume_version,
                "source_content_sha256": state["content_sha256"],
                "field_count": len(normalized),
                "protected_field_count": len(protected),
                "quarantined_field_count": len(quarantined),
                "untrusted_finding_count": len(findings),
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "STRUCTURED_VERSION_CREATED",
                "submission_id": envelope["aggregate_id"],
                "structured_resume_version": resume_version,
            },
        )

    def _handle_ResolveApplicationRouting(
        self, envelope: Dict[str, Any]
    ) -> Dict[str, Any]:
        tenant_id = envelope["tenant_id"]
        submission = self._load_submission(tenant_id, envelope["aggregate_id"])
        if not submission:
            return self._rejected(envelope, "NOT_FOUND", "投递不存在。")
        version, state = submission
        payload = envelope["payload"]
        actor = envelope["actor"]
        human_review = payload.get("decision_mode") == "HUMAN_REVIEW"
        if human_review and (
            actor.get("actor_type") != "HUMAN"
            or actor.get("role") != "HIRING_OWNER"
        ):
            return self._rejected(
                envelope,
                "HUMAN_AUTHORITY_REQUIRED",
                "身份或路由冲突只能由当前授权人判断。",
            )
        if not human_review and (
            actor.get("actor_type") != "SERVICE"
            or actor.get("role") != "INTAKE_WORKFLOW"
        ):
            return self._rejected(
                envelope,
                "AUTHORIZATION_DENIED",
                "只有当前收件工作流服务可提交唯一自动路由。",
            )
        if not state["structured_resume_versions"]:
            return self._rejected(
                envelope, "INVALID_TRANSITION", "没有当前结构化简历版本。"
            )
        if human_review:
            allowed_state = "ROUTING_REVIEW_REQUIRED"
        else:
            allowed_state = "PARSING"
        if state["state"] != allowed_state:
            return self._rejected(
                envelope,
                "INVALID_TRANSITION",
                "当前投递状态不允许执行这类路由判断。",
            )

        if human_review:
            selected_candidate = payload.get("selected_candidate_id")
            selected_requisition = payload.get("selected_requisition_id")
            selected_cycle = payload.get("selected_recruitment_cycle_id")
            decision_reason = payload.get("reason", "").strip()
            if not all(
                [selected_candidate, selected_requisition, selected_cycle, decision_reason]
            ):
                return self._rejected(
                    envelope, "INVALID_COMMAND", "人工判断必须给出完整申请键和判断依据。"
                )
            allowed_candidates = {
                item.get("candidate_id") for item in state["identity_candidates"]
            }
            allowed_routes = {
                (item.get("requisition_id"), item.get("recruitment_cycle_id"))
                for item in state["routing_candidates"]
            }
            if selected_candidate not in allowed_candidates or (
                selected_requisition,
                selected_cycle,
            ) not in allowed_routes:
                return self._rejected(
                    envelope,
                    "DECISION_OUT_OF_SCOPE",
                    "人工判断必须来自当前候选项，不能写入未展示的身份或路由。",
                )
            matching_routes = [
                item
                for item in state["routing_candidates"]
                if item.get("requisition_id") == selected_requisition
                and item.get("recruitment_cycle_id") == selected_cycle
            ]
            if len(matching_routes) != 1:
                return self._rejected(
                    envelope,
                    "ROUTE_CONFLICT_UNRESOLVED",
                    "同一岗位与招聘周期存在多条冲突权威记录，必须先完成路由事实对账。",
                )
            selected_route = matching_routes[0]
            if (
                selected_route.get("requisition_status") != "OPEN"
                or selected_route.get("cycle_status") != "ACTIVE"
            ):
                return self._rejected(
                    envelope,
                    "ROUTE_NOT_ACTIONABLE",
                    "人工判断不能把已关闭岗位或非活动招聘周期变成可开案路由。",
                )
            routing = {
                "candidate_id": selected_candidate,
                "requisition_id": selected_requisition,
                "recruitment_cycle_id": selected_cycle,
                "resolution_basis": "HUMAN_REVIEW",
                "actor_id": actor["actor_id"],
                "decision_reason": decision_reason,
            }
            if state.get("review_task"):
                state["review_task"]["status"] = "COMPLETED"
        else:
            identities = state["identity_candidates"]
            routes = state["routing_candidates"]
            trusted_identity_bases = {
                "APPROVED_SOURCE_ID",
                "UNIQUE_DIRECTORY_MATCH",
                "UNIQUE_SIGNALS",
            }
            trusted_route_bases = {
                "APPROVED_SOURCE_MAPPING",
                "SUBJECT_REQUISITION_CODE",
            }
            identity_conflict = any(
                item.get("conflict_codes")
                or item.get("basis") not in trusted_identity_bases
                for item in identities
            )
            route_not_current = any(
                item.get("requisition_status") != "OPEN"
                or item.get("cycle_status") != "ACTIVE"
                or not set(item.get("basis", []))
                or not set(item.get("basis", [])).issubset(trusted_route_bases)
                for item in routes
            )
            if (
                len(identities) != 1
                or len(routes) != 1
                or identity_conflict
                or route_not_current
            ):
                reason = (
                    "IDENTITY_AMBIGUITY"
                    if len(identities) != 1 or identity_conflict
                    else "REQUISITION_OR_CYCLE_AMBIGUITY"
                )
                state.update(
                    {
                        "state": "ROUTING_REVIEW_REQUIRED",
                        "activity": "NEEDS_HUMAN",
                        "stop_reason": reason,
                        "review_task": _review_task_projection(
                            envelope["aggregate_id"], reason, identities, routes
                        ),
                    }
                )
                self._save_submission(
                    tenant_id, envelope["aggregate_id"], version + 1, state
                )
                event_id = self._append_event(
                    tenant_id,
                    "ApplicationRoutingReviewRequired",
                    envelope["aggregate_id"],
                    {
                        "submission_id": envelope["aggregate_id"],
                        "reason": reason,
                        "identity_candidate_count": len(identities),
                        "routing_candidate_count": len(routes),
                    },
                )
                return self._applied(
                    envelope,
                    [event_id],
                    {
                        "effect": "ROUTING_REVIEW_REQUIRED",
                        "submission_id": envelope["aggregate_id"],
                        "reason": reason,
                    },
                )
            route = routes[0]
            routing = {
                "candidate_id": identities[0]["candidate_id"],
                "requisition_id": route["requisition_id"],
                "recruitment_cycle_id": route["recruitment_cycle_id"],
                "resolution_basis": "UNIQUE_APPROVED_SIGNALS",
                "actor_id": actor["actor_id"],
            }

        state.update(
            {
                "state": "ROUTED",
                "activity": "ACTIVE",
                "stop_reason": None,
                "routing_revision": {
                    "revision": 1
                    if state["routing_revision"] is None
                    else state["routing_revision"]["revision"] + 1,
                    **routing,
                },
            }
        )
        self._save_submission(tenant_id, envelope["aggregate_id"], version + 1, state)
        event_id = self._append_event(
            tenant_id,
            "ApplicationRoutingResolved",
            envelope["aggregate_id"],
            {
                "submission_id": envelope["aggregate_id"],
                "routing_revision": state["routing_revision"]["revision"],
                "candidate_id": routing["candidate_id"],
                "requisition_id": routing["requisition_id"],
                "recruitment_cycle_id": routing["recruitment_cycle_id"],
                "resolution_basis": routing["resolution_basis"],
                "actor_id": routing["actor_id"],
                "decision_reason": routing.get("decision_reason"),
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {"effect": "ROUTED", "submission_id": envelope["aggregate_id"]},
        )

    def _handle_OpenOrAttachApplicationCase(
        self, envelope: Dict[str, Any]
    ) -> Dict[str, Any]:
        tenant_id = envelope["tenant_id"]
        submission_id = envelope["payload"].get(
            "submission_id", envelope["aggregate_id"]
        )
        submission = self._load_submission(tenant_id, submission_id)
        if not submission:
            return self._rejected(envelope, "NOT_FOUND", "投递不存在。")
        _, state = submission
        if state["state"] != "ROUTED" or not state.get("routing_revision"):
            return self._rejected(
                envelope,
                "INVALID_TRANSITION",
                "只有当前 ROUTED 且申请键完整的投递才能开案。",
            )
        if envelope["payload"].get("routing_revision") != state[
            "routing_revision"
        ]["revision"]:
            return self._rejected(
                envelope,
                "STALE_ROUTING_REVISION",
                "开案命令没有钉住当前路由修订。",
            )
        routing = state["routing_revision"]
        application_key = {
            "tenant_id": tenant_id,
            "candidate_id": routing["candidate_id"],
            "requisition_id": routing["requisition_id"],
            "recruitment_cycle_id": routing["recruitment_cycle_id"],
        }
        key_hash = _sha256(_canonical(application_key))
        application_case_id = "case-{}".format(key_hash[:12])
        if envelope["aggregate_id"] != application_case_id:
            return self._rejected(
                envelope,
                "AGGREGATE_TARGET_MISMATCH",
                "开案命令必须直接指向当前 ApplicationKey 对应的唯一 Case 聚合。",
            )
        existing = self._db.execute(
            "SELECT application_case_id, version, state_json FROM application_cases "
            "WHERE tenant_id = ? AND application_key_hash = ?",
            (tenant_id, key_hash),
        ).fetchone()
        if existing:
            case_state = json.loads(existing["state_json"])
            if (
                envelope["payload"].get("expected_case_version")
                != existing["version"]
                or envelope["payload"].get("expected_lifecycle_epoch")
                != case_state["lifecycle_epoch"]
            ):
                return self._rejected(
                    envelope,
                    "STALE_CASE_VERSION",
                    "附加来源前必须钉住当前 Case 版本和生命周期代次。",
                )
            if submission_id not in case_state["submission_ids"]:
                case_state["submission_ids"].append(submission_id)
                new_version = existing["version"] + 1
                self._db.execute(
                    "UPDATE application_cases SET version = ?, state_json = ? "
                    "WHERE tenant_id = ? AND application_case_id = ?",
                    (
                        new_version,
                        _canonical(case_state),
                        tenant_id,
                        existing["application_case_id"],
                    ),
                )
                event_id = self._append_event(
                    tenant_id,
                    "ResumeSubmissionAttachedToCase",
                    existing["application_case_id"],
                    {
                        "application_case_id": existing["application_case_id"],
                        "submission_id": submission_id,
                        "application_key_hash": key_hash,
                    },
                )
            else:
                event_id = None
            return self._applied(
                envelope,
                [event_id] if event_id else [],
                {
                    "effect": "ATTACHED_TO_EXISTING_CASE",
                    "submission_id": submission_id,
                    "application_case_id": existing["application_case_id"],
                },
            )

        if (
            envelope["payload"].get("expected_case_version") != 0
            or envelope["payload"].get("expected_lifecycle_epoch") != 1
        ):
            return self._rejected(
                envelope,
                "STALE_CASE_VERSION",
                "新建 Case 必须声明不存在的当前版本和首个生命周期代次。",
            )
        case_state = {
            "application_case_id": application_case_id,
            "state": "RECEIVED",
            "activity": "ACTIVE",
            "suspension": "RUNNING",
            "lifecycle_epoch": 1,
            "application_key": application_key,
            "application_key_hash": key_hash,
            "submission_ids": [submission_id],
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO application_cases "
            "(tenant_id, application_case_id, application_key_hash, version, state_json) "
            "VALUES (?, ?, ?, 1, ?)",
            (tenant_id, application_case_id, key_hash, _canonical(case_state)),
        )
        event_id = self._append_event(
            tenant_id,
            "ApplicationCaseOpened",
            application_case_id,
            {
                "application_case_id": application_case_id,
                "submission_id": submission_id,
                "application_key_hash": key_hash,
                "lifecycle_epoch": 1,
            },
        )
        return self._applied(
            envelope,
            [event_id],
            {
                "effect": "CASE_OPENED",
                "submission_id": submission_id,
                "application_case_id": application_case_id,
            },
        )

    def _install_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS command_results (
                tenant_id TEXT NOT NULL,
                idempotency_key TEXT NOT NULL,
                payload_hash TEXT NOT NULL,
                result_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, idempotency_key)
            );
            CREATE TABLE IF NOT EXISTS submissions (
                tenant_id TEXT NOT NULL,
                submission_id TEXT NOT NULL,
                dedupe_fingerprint TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, submission_id),
                UNIQUE (tenant_id, dedupe_fingerprint)
            );
            CREATE TABLE IF NOT EXISTS source_observations (
                tenant_id TEXT NOT NULL,
                source_key TEXT NOT NULL,
                attachment_key TEXT NOT NULL,
                submission_id TEXT NOT NULL,
                content_sha256 TEXT NOT NULL,
                dedupe_fingerprint TEXT NOT NULL,
                registration_manifest_hash TEXT NOT NULL,
                security_disposition TEXT NOT NULL,
                PRIMARY KEY (tenant_id, source_key),
                UNIQUE (tenant_id, attachment_key)
            );
            CREATE TABLE IF NOT EXISTS application_cases (
                tenant_id TEXT NOT NULL,
                application_case_id TEXT NOT NULL,
                application_key_hash TEXT NOT NULL,
                version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (tenant_id, application_case_id),
                UNIQUE (tenant_id, application_key_hash)
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence_no INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                aggregate_id TEXT NOT NULL,
                event_json TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    def _load_submission(
        self, tenant_id: str, submission_id: str
    ) -> Optional[tuple[int, Dict[str, Any]]]:
        row = self._db.execute(
            "SELECT version, state_json FROM submissions "
            "WHERE tenant_id = ? AND submission_id = ?",
            (tenant_id, submission_id),
        ).fetchone()
        if not row:
            return None
        return row["version"], json.loads(row["state_json"])

    def _save_submission(
        self, tenant_id: str, submission_id: str, version: int, state: Dict[str, Any]
    ) -> None:
        self._db.execute(
            "UPDATE submissions SET version = ?, state_json = ? "
            "WHERE tenant_id = ? AND submission_id = ?",
            (version, _canonical(state), tenant_id, submission_id),
        )

    def _append_event(
        self,
        tenant_id: str,
        event_type: str,
        aggregate_id: str,
        payload: Dict[str, Any],
    ) -> str:
        ordinal = self._db.execute(
            "SELECT COUNT(*) AS n FROM events WHERE tenant_id = ?",
            (tenant_id,),
        ).fetchone()["n"] + 1
        event_id = "evt-intake-{:04d}".format(ordinal)
        event = {
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id,
            "aggregate_id": aggregate_id,
            "occurred_at": "2026-08-11T00:00:{:02d}Z".format(min(ordinal, 59)),
            "data_classification": "INTERNAL",
            "payload": payload,
            "synthetic_only": True,
        }
        self._db.execute(
            "INSERT INTO events (tenant_id, event_type, aggregate_id, event_json) "
            "VALUES (?, ?, ?, ?)",
            (tenant_id, event_type, aggregate_id, _canonical(event)),
        )
        return event_id

    def _case_id_for_submission(self, tenant_id: str, submission_id: str) -> Optional[str]:
        for row in self._db.execute(
            "SELECT application_case_id, state_json FROM application_cases WHERE tenant_id = ?",
            (tenant_id,),
        ):
            if submission_id in json.loads(row["state_json"])["submission_ids"]:
                return row["application_case_id"]
        return None

    def _insert_source_observation(
        self,
        tenant_id: str,
        submission_id: str,
        source_key: str,
        attachment_key: str,
        content_sha256: str,
        dedupe_fingerprint: str,
        registration_manifest_hash: str,
        security_disposition: str,
    ) -> None:
        self._db.execute(
            "INSERT INTO source_observations "
            "(tenant_id, source_key, attachment_key, submission_id, content_sha256, "
            "dedupe_fingerprint, registration_manifest_hash, security_disposition) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                tenant_id,
                source_key,
                attachment_key,
                submission_id,
                content_sha256,
                dedupe_fingerprint,
                registration_manifest_hash,
                security_disposition,
            ),
        )

    def _validate_envelope(
        self, envelope: Any
    ) -> Optional[tuple[str, str]]:
        required = {
            "command_id",
            "idempotency_key",
            "command_type",
            "tenant_id",
            "aggregate_type",
            "aggregate_id",
            "actor",
            "payload",
        }
        if not isinstance(envelope, dict) or not required.issubset(envelope):
            return "INVALID_COMMAND", "命令信封字段不完整。"
        if not isinstance(envelope["payload"], dict) or not isinstance(
            envelope["actor"], dict
        ):
            return "INVALID_COMMAND", "命令 actor 或 payload 无效。"
        if not {"actor_type", "actor_id", "role"}.issubset(envelope["actor"]):
            return "INVALID_COMMAND", "命令 actor 字段不完整。"
        grant = (
            envelope["tenant_id"],
            envelope["actor"].get("actor_type"),
            envelope["actor"].get("actor_id"),
            envelope["actor"].get("role"),
        )
        if grant not in self._authority_grants:
            return "AUTHORIZATION_DENIED", "当前 actor 没有该租户的有效授权。"
        command_actor_grants = {
            "RegisterResumeSubmission": {
                ("SERVICE", "intake-workflow", "INTAKE_WORKFLOW")
            },
            "RecordStructuredResumeVersion": {
                ("SERVICE", "resume-parser", "UNTRUSTED_CONTENT_PARSER")
            },
            "ResolveApplicationRouting": {
                ("SERVICE", "intake-workflow", "INTAKE_WORKFLOW"),
                ("HUMAN", "hiring-owner-1", "HIRING_OWNER"),
            },
            "OpenOrAttachApplicationCase": {
                ("SERVICE", "intake-workflow", "INTAKE_WORKFLOW")
            },
        }
        actor_grant = (
            envelope["actor"].get("actor_type"),
            envelope["actor"].get("actor_id"),
            envelope["actor"].get("role"),
        )
        allowed_actors = command_actor_grants.get(envelope["command_type"])
        if allowed_actors is not None and actor_grant not in allowed_actors:
            return "AUTHORIZATION_DENIED", "当前授权主体不能提交这一类命令。"
        expected_targets = {
            "RegisterResumeSubmission": "RESUME_SUBMISSION",
            "RecordStructuredResumeVersion": "RESUME_SUBMISSION",
            "ResolveApplicationRouting": "RESUME_SUBMISSION",
            "OpenOrAttachApplicationCase": "APPLICATION_CASE",
        }
        expected_target = expected_targets.get(envelope["command_type"])
        if expected_target and envelope["aggregate_type"] != expected_target:
            return (
                "AGGREGATE_TARGET_MISMATCH",
                "命令目标聚合与该命令的唯一写入对象不一致。",
            )
        return None

    @staticmethod
    def _applied(
        envelope: Dict[str, Any], event_ids: Iterable[str], data: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "command_id": envelope.get("command_id"),
            "status": "APPLIED",
            "event_ids": list(event_ids),
            "data": data,
            "error": None,
        }

    @staticmethod
    def _rejected(
        envelope: Any, code: str, message: str
    ) -> Dict[str, Any]:
        return {
            "command_id": envelope.get("command_id")
            if isinstance(envelope, dict)
            else None,
            "status": "REJECTED",
            "event_ids": [],
            "data": None,
            "error": {"code": code, "message": message},
        }


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _review_task_projection(
    submission_id: str,
    reason: str,
    identities: Iterable[Dict[str, Any]],
    routes: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "task_id": "review:{}".format(submission_id),
        "submission_id": submission_id,
        "task_type": "APPLICATION_ROUTING_REVIEW",
        "owner_role": "HIRING_OWNER",
        "reason": reason,
        "identity_candidates": deepcopy(list(identities)),
        "routing_candidates": deepcopy(list(routes)),
        "due_at": "2026-08-11T04:00:00Z",
        "status": "OPEN",
        "synthetic_only": True,
    }


def _exception_projection(
    submission_id: str, reason: Optional[str]
) -> Optional[Dict[str, Any]]:
    if not reason:
        return None
    return {
        "bundle_id": "exception:{}".format(submission_id),
        "submission_id": submission_id,
        "reason": reason,
        "owner_role": "RECRUITING_OPS",
        "retry_budget": 2,
        "attempt_count": 0,
        "recovery_options": ["REQUEST_SAFE_ATTACHMENT", "MANUAL_REVIEW"],
        "status": "OPEN",
        "synthetic_only": True,
    }


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(
        char in "0123456789abcdef" for char in value
    )


def _canonical_field_name(value: Any) -> str:
    normalized = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
    aliases = {
        "性别": "gender",
        "sex": "gender",
        "出生日期": "birth_date",
        "出生年月": "birth_date",
        "年龄": "age",
        "婚姻状况": "marital_status",
        "婚姻状态": "marital_status",
        "生育状况": "reproductive_status",
        "生育状态": "reproductive_status",
        "pregnancy": "reproductive_status",
        "pregnancy_status": "reproductive_status",
        "残障": "disability",
        "残疾": "disability",
        "民族": "ethnicity",
        "宗教": "religion",
        "宗教信仰": "religion",
        "政治面貌": "political_affiliation",
        "照片": "photo",
        "头像": "photo",
    }
    return aliases.get(normalized, normalized)


def _validate_parser_output(payload: Dict[str, Any]) -> Optional[str]:
    parser_version = payload.get("parser_version")
    fields = payload.get("fields")
    identities = payload.get("identity_candidates")
    routes = payload.get("routing_candidates")
    raw_text = payload.get("raw_text", "")
    if not isinstance(parser_version, str) or not parser_version.strip():
        return "parser_version 必须是非空字符串。"
    if not isinstance(fields, list) or not fields:
        return "解析结果必须包含非空字段数组。"
    if not isinstance(identities, list) or not isinstance(routes, list):
        return "身份候选与岗位路由候选必须是数组。"
    if not isinstance(raw_text, str):
        return "原文观察必须是字符串，不能作为可执行结构。"

    field_keys = {"name", "value", "locator", "confidence", "classification"}
    classifications = {None, "STANDARD", "PROTECTED", "SENSITIVE"}
    for field in fields:
        if not isinstance(field, dict) or not {
            "name",
            "value",
            "locator",
            "confidence",
        }.issubset(field):
            return "字段对象缺少名称、值、定位或置信信号。"
        if not set(field).issubset(field_keys):
            return "字段对象包含当前 closed schema 未批准的属性。"
        if not isinstance(field["name"], str) or not field["name"].strip():
            return "字段名称必须是非空字符串。"
        if not isinstance(field["locator"], str) or not field["locator"].strip():
            return "字段定位必须是非空字符串。"
        classification = field.get("classification")
        if classification is not None and not isinstance(classification, str):
            return "字段分类必须是字符串。"
        if classification not in classifications:
            return "字段分类不在当前 closed schema 中。"

    identity_bases = {
        "APPROVED_SOURCE_ID",
        "MODEL_OUTPUT",
        "REUSED_PHONE",
        "SHARED_EMAIL",
        "UNIQUE_DIRECTORY_MATCH",
        "UNIQUE_SIGNALS",
    }
    for identity in identities:
        if not isinstance(identity, dict) or not {
            "candidate_id",
            "basis",
        }.issubset(identity):
            return "身份候选必须包含 candidate_id 和 basis。"
        if not set(identity).issubset({"candidate_id", "basis", "conflict_codes"}):
            return "身份候选包含当前 closed schema 未批准的属性。"
        if not isinstance(identity["candidate_id"], str) or not identity[
            "candidate_id"
        ].strip():
            return "candidate_id 必须是非空字符串。"
        if not isinstance(identity["basis"], str):
            return "身份候选 basis 必须是字符串。"
        if identity["basis"] not in identity_bases:
            return "身份候选 basis 不在当前 closed schema 中。"
        conflicts = identity.get("conflict_codes", [])
        if not isinstance(conflicts, list) or not all(
            isinstance(item, str) for item in conflicts
        ):
            return "身份冲突码必须是字符串数组。"

    route_keys = {
        "requisition_id",
        "recruitment_cycle_id",
        "requisition_status",
        "cycle_status",
        "basis",
    }
    route_bases = {
        "APPROVED_SOURCE_MAPPING",
        "FREE_TEXT_TITLE",
        "MODEL_OUTPUT",
        "SUBJECT_REQUISITION_CODE",
    }
    for route in routes:
        if not isinstance(route, dict) or not route_keys.issubset(route):
            return "路由候选缺少岗位、周期、状态或 basis。"
        if not set(route).issubset(route_keys):
            return "路由候选包含当前 closed schema 未批准的属性。"
        if not all(
            isinstance(route[key], str) and route[key].strip()
            for key in ("requisition_id", "recruitment_cycle_id")
        ):
            return "岗位与招聘周期标识必须是非空字符串。"
        if not isinstance(route["requisition_status"], str):
            return "岗位状态必须是字符串。"
        if route["requisition_status"] not in {"OPEN", "CLOSED", "UNKNOWN"}:
            return "岗位状态不在当前 closed schema 中。"
        if not isinstance(route["cycle_status"], str):
            return "招聘周期状态必须是字符串。"
        if route["cycle_status"] not in {"ACTIVE", "CLOSED", "INACTIVE", "UNKNOWN"}:
            return "招聘周期状态不在当前 closed schema 中。"
        bases = route["basis"]
        if not isinstance(bases, list) or not bases or not all(
            isinstance(item, str) and item in route_bases for item in bases
        ):
            return "路由 basis 必须是当前 closed schema 的非空字符串数组。"
    return None


def _source_key(source: Dict[str, Any]) -> str:
    return "{}:{}:{}".format(
        source.get("channel"),
        source.get("source_event_id"),
        source.get("attachment_id"),
    )


def _public_source(source: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "channel": source["channel"],
        "source_event_id": source["source_event_id"],
        "message_id": source["message_id"],
        "attachment_id": source["attachment_id"],
        "filename": source["filename"],
        "received_at": source.get("received_at", "2026-08-11T00:00:00Z"),
    }


def _attachment_stop_reason(payload: Dict[str, Any]) -> Optional[str]:
    if payload.get("encrypted"):
        return "ATTACHMENT_ENCRYPTED"
    if payload.get("corrupt"):
        return "ATTACHMENT_CORRUPT"
    if payload.get("malicious"):
        return "ATTACHMENT_MALICIOUS"
    if payload.get("scan_verdict", "PASS") != "PASS":
        return "ATTACHMENT_SCAN_UNKNOWN"
    if payload.get("mime_type") not in {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }:
        return "ATTACHMENT_UNSUPPORTED"
    return None


def _prompt_injection_findings(raw_text: str) -> list[Dict[str, Any]]:
    lowered = raw_text.lower()
    patterns = [
        "ignore previous",
        "send an email",
        "call tool",
        "read secret",
        "忽略之前",
        "发送邮件",
        "调用工具",
    ]
    if any(pattern in lowered for pattern in patterns):
        return [
            {
                "kind": "PROMPT_INJECTION_PATTERN",
                "disposition": "QUARANTINED_AS_UNTRUSTED_TEXT",
            }
        ]
    return []
