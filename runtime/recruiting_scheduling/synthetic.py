"""Stateful synthetic provider adapters and a fixture-only scheduling builder."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from copy import deepcopy
from typing import Any, Dict, Optional

try:
    from runtime.recruiting_screening.scenario import run_normal_screening
    from runtime.recruiting_screening.synthetic import (
        SyntheticClock,
        _normal_seed_commands,
    )
except ModuleNotFoundError:
    from recruiting_screening.scenario import run_normal_screening
    from recruiting_screening.synthetic import SyntheticClock, _normal_seed_commands

from .control import RecruitingSchedulingControl, _SYNTHETIC_ADAPTER_CAPABILITY


JsonObject = Dict[str, Any]


class SyntheticCalendarAdapter:
    """Synthetic busy/free reader and idempotent calendar-event writer."""

    def __init__(self) -> None:
        self._synthetic_capability = _SYNTHETIC_ADAPTER_CAPABILITY
        self._effects: Dict[str, JsonObject] = {}
        self._effect_cases: Dict[str, str] = {}
        self._cancellations: Dict[str, JsonObject] = {}
        self._cancellation_cases: Dict[str, str] = {}
        self._slot_reservations: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._lose_next_response = False
        self._availability_revision = 1
        self._available_slots = [
            {
                "slot_ref": "slot-2026-08-18-1000-asia-shanghai",
                "starts_at": "2026-08-18T02:00:00Z",
                "ends_at": "2026-08-18T03:00:00Z",
                "display_timezone": "Asia/Shanghai",
            }
        ]

    def read_availability(self, request: JsonObject) -> JsonObject:
        return {
            "provider": "synthetic-calendar",
            "provider_account_ref": "calendar-account:tenant-synthetic",
            "revision": self._availability_revision,
            "observed_at": request["observed_at"],
            "expires_at": "2026-08-11T12:30:00Z",
            "slots": deepcopy(self._available_slots),
            "snapshot_hash": _hash(
                {
                    "revision": self._availability_revision,
                    "slots": self._available_slots,
                    "scope_hash": request["scope_hash"],
                }
            ),
            "synthetic_only": True,
        }

    def replace_availability(self, slots: list) -> None:
        """Deterministically change the synthetic busy/free source revision."""

        self._availability_revision += 1
        self._available_slots = deepcopy(slots)

    def create_event(self, operation: JsonObject) -> JsonObject:
        with self._lock:
            key = operation["provider_idempotency_key"]
            existing = self._effects.get(key)
            if existing:
                receipt = deepcopy(existing)
            else:
                slot_ref = operation["slot"]["slot_ref"]
                holder = self._slot_reservations.get(slot_ref)
                if holder and holder != key:
                    return {
                        "outcome": "SLOT_RESERVATION_CONFLICT",
                        "provider": "synthetic-calendar",
                        "slot_ref": slot_ref,
                        "synthetic_only": True,
                    }
                receipt = self._create_once("CALENDAR_EVENT", operation)
                self._slot_reservations[slot_ref] = key
        if self._lose_next_response:
            self._lose_next_response = False
            return {
                "outcome": "UNKNOWN_AFTER_WRITE",
                "provider": "synthetic-calendar",
                "synthetic_only": True,
            }
        return receipt

    def lose_next_success_response(self) -> None:
        self._lose_next_response = True

    def reconcile_event(self, operation: JsonObject) -> Optional[JsonObject]:
        receipt = self._effects.get(operation["provider_idempotency_key"])
        return deepcopy(receipt) if receipt else None

    def callback_observation(self, action_id: str) -> JsonObject:
        receipt = self._effects[action_id]
        return {
            "provider_event_id": "calendar-callback:{}".format(action_id),
            "provider_account_ref": "calendar-account:tenant-synthetic",
            "provider_idempotency_key": action_id,
            "receipt": deepcopy(receipt),
        }

    def _create_once(self, resource_kind: str, operation: JsonObject) -> JsonObject:
        key = operation["provider_idempotency_key"]
        existing = self._effects.get(key)
        if existing:
            return deepcopy(existing)
        receipt = {
            "provider": "synthetic-calendar",
            "provider_receipt_id": "calendar-receipt:{}".format(operation["action_id"]),
            "external_resource_ref": "calendar-event:{}".format(
                operation["appointment_revision"]
            ),
            "external_resource_revision": 1,
            "resource_kind": resource_kind,
            "appointment_revision": operation["appointment_revision"],
            "scope_hash": operation["scope_hash"],
            "synthetic_only": True,
        }
        self._effects[key] = deepcopy(receipt)
        self._effect_cases[key] = operation["application_case_id"]
        return receipt

    def effect_count(self, application_case_id: Optional[str] = None) -> int:
        if application_case_id is None:
            return len(self._effects)
        return sum(
            case_id == application_case_id for case_id in self._effect_cases.values()
        )

    def cancel_event(self, operation: JsonObject) -> JsonObject:
        key = operation["provider_idempotency_key"]
        existing = self._cancellations.get(key)
        if existing:
            return deepcopy(existing)
        receipt = {
            "provider": "synthetic-calendar",
            "provider_receipt_id": "calendar-cancel-receipt:{}".format(
                operation["action_id"]
            ),
            "external_resource_ref": operation["source_receipt"][
                "external_resource_ref"
            ],
            "external_resource_revision": 2,
            "resource_kind": "CALENDAR_EVENT_CANCEL",
            "appointment_revision": operation["appointment_revision"],
            "scope_hash": operation["scope_hash"],
            "synthetic_only": True,
        }
        self._cancellations[key] = deepcopy(receipt)
        self._cancellation_cases[key] = operation["application_case_id"]
        return receipt

    def cancellation_count(self, application_case_id: Optional[str] = None) -> int:
        if application_case_id is None:
            return len(self._cancellations)
        return sum(
            case_id == application_case_id
            for case_id in self._cancellation_cases.values()
        )


class SyntheticMeetingAdapter:
    """Synthetic idempotent meeting-resource writer."""

    def __init__(self) -> None:
        self._synthetic_capability = _SYNTHETIC_ADAPTER_CAPABILITY
        self._effects: Dict[str, JsonObject] = {}
        self._effect_cases: Dict[str, str] = {}

    def create_meeting(self, operation: JsonObject) -> JsonObject:
        key = operation["provider_idempotency_key"]
        existing = self._effects.get(key)
        if existing:
            return deepcopy(existing)
        receipt = {
            "provider": "synthetic-meeting",
            "provider_receipt_id": "meeting-receipt:{}".format(operation["action_id"]),
            "external_resource_ref": "meeting:{}".format(
                operation["appointment_revision"]
            ),
            "external_resource_revision": 1,
            "resource_kind": "MEETING_RESOURCE",
            "appointment_revision": operation["appointment_revision"],
            "scope_hash": operation["scope_hash"],
            "synthetic_only": True,
        }
        self._effects[key] = deepcopy(receipt)
        self._effect_cases[key] = operation["application_case_id"]
        return receipt

    def effect_count(self, application_case_id: Optional[str] = None) -> int:
        if application_case_id is None:
            return len(self._effects)
        return sum(
            case_id == application_case_id for case_id in self._effect_cases.values()
        )


class SyntheticInvitationAdapter:
    """Synthetic invitation writer; a write receipt is not delivery or read."""

    def __init__(self) -> None:
        self._synthetic_capability = _SYNTHETIC_ADAPTER_CAPABILITY
        self._effects: Dict[str, JsonObject] = {}
        self._effect_cases: Dict[str, str] = {}

    def write_invitation(self, operation: JsonObject) -> JsonObject:
        key = operation["provider_idempotency_key"]
        existing = self._effects.get(key)
        if existing:
            return deepcopy(existing)
        receipt = {
            "provider": "synthetic-invitation",
            "provider_receipt_id": "invitation-write-receipt:{}".format(
                operation["action_id"]
            ),
            "external_resource_ref": "invitation:{}".format(
                operation["appointment_revision"]
            ),
            "external_resource_revision": 1,
            "resource_kind": "INVITATION_WRITE",
            "appointment_revision": operation["appointment_revision"],
            "scope_hash": operation["scope_hash"],
            "delivery_status": "NOT_OBSERVED",
            "read_status": "NOT_OBSERVED",
            "synthetic_only": True,
        }
        self._effects[key] = deepcopy(receipt)
        self._effect_cases[key] = operation["application_case_id"]
        return receipt

    def effect_count(self, application_case_id: Optional[str] = None) -> int:
        if application_case_id is None:
            return len(self._effects)
        return sum(
            case_id == application_case_id for case_id in self._effect_cases.values()
        )


class SyntheticSchedulingAdapters:
    """Explicit synthetic adapter bundle injected into the scheduling module."""

    __slots__ = (
        "_synthetic_capability",
        "_calendar",
        "_meeting",
        "_invitation",
    )

    def __init__(
        self,
        *,
        calendar: Optional[SyntheticCalendarAdapter] = None,
        meeting: Optional[SyntheticMeetingAdapter] = None,
        invitation: Optional[SyntheticInvitationAdapter] = None,
    ) -> None:
        selected = (
            calendar or SyntheticCalendarAdapter(),
            meeting or SyntheticMeetingAdapter(),
            invitation or SyntheticInvitationAdapter(),
        )
        if any(
            getattr(adapter, "_synthetic_capability", None)
            is not _SYNTHETIC_ADAPTER_CAPABILITY
            for adapter in selected
        ):
            raise TypeError("SyntheticSchedulingAdapters accepts synthetic adapters only")
        self._synthetic_capability = _SYNTHETIC_ADAPTER_CAPABILITY
        self._calendar, self._meeting, self._invitation = selected

    @property
    def calendar(self) -> SyntheticCalendarAdapter:
        return self._calendar

    @property
    def meeting(self) -> SyntheticMeetingAdapter:
        return self._meeting

    @property
    def invitation(self) -> SyntheticInvitationAdapter:
        return self._invitation


def build_synthetic_scheduling(
    *,
    adapters: Optional[SyntheticSchedulingAdapters] = None,
    clock: Optional[SyntheticClock] = None,
    recruitment_cycle_id: str = "cycle-2026-q3",
) -> RecruitingSchedulingControl:
    """Reach HUMAN INVITE, then seed one explicitly fixture-only ready Session."""

    active_clock = clock or SyntheticClock("2026-08-11T12:00:00Z")
    control = RecruitingSchedulingControl(
        sqlite3.connect(":memory:", check_same_thread=False),
        adapters=adapters or SyntheticSchedulingAdapters(),
        clock=active_clock,
    )
    application_key = {
        "tenant_id": "tenant-synthetic",
        "candidate_id": "candidate-lina",
        "requisition_id": "req-ai-product",
        "recruitment_cycle_id": recruitment_cycle_id,
    }
    case_id = "case-{}".format(_hash(application_key)[:12])
    commands = _normal_seed_commands(case_id)
    commands[0]["payload"]["application_intent_key"] = (
        "candidate-lina:req-ai-product:{}".format(recruitment_cycle_id)
    )
    commands[1]["payload"]["routing_candidates"][0][
        "recruitment_cycle_id"
    ] = recruitment_cycle_id
    for envelope in commands:
        result = control.submit(envelope)
        if result["status"] not in {"APPLIED", "REPLAYED"}:
            raise AssertionError(result)
    control.bind_synthetic_case(case_id)
    run_normal_screening(control, decision="INVITE")
    control._seed_fixture_ready_session(case_id)
    return control


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
