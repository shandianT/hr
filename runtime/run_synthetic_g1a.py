#!/usr/bin/env python3
"""Run the reusable synthetic G1a happy path and print a JSON summary."""

import json
from typing import Any

from recruiting_control.scenario import (
    APPLICATION_CASE_ID,
    INTERVIEW_ROUND_ID,
    TENANT_ID,
    build_g1a_happy_path_commands,
    projection_request,
)
from recruiting_control.synthetic import build_synthetic_control


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    control = build_synthetic_control()
    for envelope in build_g1a_happy_path_commands():
        result = control.submit(envelope)
        if result["status"] != "APPLIED":
            raise RuntimeError("synthetic command failed: " + _canonical_json(result))

    projection = control.read(projection_request())
    round_projection = projection["rounds"][INTERVIEW_ROUND_ID]
    if round_projection["state"] != "COMPLETED" or not round_projection["archive"]:
        raise RuntimeError("synthetic round did not reach COMPLETED")

    summary = {
        "synthetic_only": round_projection["synthetic_only"],
        "round_state": round_projection["state"],
        "archive_hash": round_projection["archive"]["archive_hash"],
        "event_count": projection["event_count"],
    }
    print(_canonical_json(summary))


if __name__ == "__main__":
    main()
