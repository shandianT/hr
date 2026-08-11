"""Synthetic-only G2 screening fixture builder."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Optional

from .control import RecruitingG2Control


class SyntheticClock:
    """Mutable deterministic clock adapter used only by synthetic scenarios."""

    def __init__(self, now: str):
        self.set(now)

    def __call__(self) -> datetime:
        return self._now

    def set(self, now: str) -> None:
        self._now = datetime.fromisoformat(now.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )


def build_synthetic_screening(
    *,
    synthetic_now: str = "2026-08-11T12:00:00Z",
    clock: Optional[SyntheticClock] = None,
) -> RecruitingG2Control:
    """Build one shared control and seed it through the real intake NORMAL path."""

    control = RecruitingG2Control(
        sqlite3.connect(":memory:"),
        synthetic_now=synthetic_now,
        clock=clock,
    )
    application_key = {
        "tenant_id": "tenant-synthetic",
        "candidate_id": "candidate-lina",
        "requisition_id": "req-ai-product",
        "recruitment_cycle_id": "cycle-2026-q3",
    }
    key_hash = hashlib.sha256(
        json.dumps(
            application_key,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    case_id = "case-{}".format(key_hash[:12])
    for envelope in _normal_seed_commands(case_id):
        result = control.submit(envelope)
        if result["status"] not in {"APPLIED", "REPLAYED"}:
            raise AssertionError(result)
    control.bind_synthetic_case(case_id)
    return control


def _normal_seed_commands(case_id: str):
    intake_actor = {
        "actor_type": "SERVICE",
        "actor_id": "intake-workflow",
        "role": "INTAKE_WORKFLOW",
    }
    parser_actor = {
        "actor_type": "SERVICE",
        "actor_id": "resume-parser",
        "role": "UNTRUSTED_CONTENT_PARSER",
    }
    submission_id = "submission-001"
    return [
        _command(
            "RegisterResumeSubmission",
            "RESUME_SUBMISSION",
            submission_id,
            "normal-register",
            intake_actor,
            {
                "purpose": "RECRUITING_INTAKE",
                "content_sha256": "1" * 64,
                "application_intent_key": "candidate-lina:req-ai-product:cycle-2026-q3",
                "mime_type": "application/pdf",
                "encrypted": False,
                "corrupt": False,
                "source": {
                    "channel": "EMAIL",
                    "source_event_id": "source:email:normal",
                    "message_id": "message:normal",
                    "attachment_id": "attachment:normal",
                    "filename": "NORMAL_合成简历.pdf",
                    "approved": True,
                    "approved_source_ref": "approved-source:synthetic:v1",
                },
            },
        ),
        _command(
            "RecordStructuredResumeVersion",
            "RESUME_SUBMISSION",
            submission_id,
            "normal-parse",
            parser_actor,
            {
                "parser_version": "synthetic-parser-v1",
                "quality_score": 0.94,
                "fields": [
                    {
                        "name": "name",
                        "value": "林可欣",
                        "locator": "P1 · 标题",
                        "confidence": 0.99,
                        "classification": "STANDARD",
                    },
                    {
                        "name": "city",
                        "value": "上海",
                        "locator": "P1 · 基本信息",
                        "confidence": 0.96,
                        "classification": "STANDARD",
                    },
                    {
                        "name": "ai_product_years",
                        "value": 3,
                        "locator": "P1 · 经历 01",
                        "confidence": 0.91,
                        "classification": "STANDARD",
                    },
                    {
                        "name": "gender",
                        "value": "不展示",
                        "locator": "P1 · 基本信息",
                        "confidence": 0.88,
                        "classification": "PROTECTED",
                    },
                ],
                "identity_candidates": [
                    {"candidate_id": "candidate-lina", "basis": "UNIQUE_SIGNALS"}
                ],
                "routing_candidates": [
                    {
                        "requisition_id": "req-ai-product",
                        "recruitment_cycle_id": "cycle-2026-q3",
                        "requisition_status": "OPEN",
                        "cycle_status": "ACTIVE",
                        "basis": [
                            "SUBJECT_REQUISITION_CODE",
                            "APPROVED_SOURCE_MAPPING",
                        ],
                    }
                ],
                "raw_text": "Synthetic resume content only.",
            },
        ),
        _command(
            "ResolveApplicationRouting",
            "RESUME_SUBMISSION",
            submission_id,
            "normal-route",
            intake_actor,
            {"decision_mode": "AUTO_UNIQUE"},
        ),
        _command(
            "OpenOrAttachApplicationCase",
            "APPLICATION_CASE",
            case_id,
            "normal-open",
            intake_actor,
            {
                "submission_id": submission_id,
                "routing_revision": 1,
                "expected_case_version": 0,
                "expected_lifecycle_epoch": 1,
            },
        ),
    ]


def _command(command_type, aggregate_type, aggregate_id, suffix, actor, payload):
    return {
        "command_id": "cmd:{}".format(suffix),
        "idempotency_key": "idem:{}".format(suffix),
        "command_type": command_type,
        "tenant_id": "tenant-synthetic",
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "actor": actor,
        "payload": payload,
    }
