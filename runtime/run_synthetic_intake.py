#!/usr/bin/env python3
"""Run the synthetic resume-intake happy path and duplicate-source path."""

import json

from recruiting_intake import build_synthetic_intake
from recruiting_intake.scenario import projection_request, run_fixture


def main() -> None:
    control = build_synthetic_intake()
    normal = run_fixture(control, "NORMAL")
    duplicate = run_fixture(control, "DUPLICATE_ATS")
    projection = control.read(projection_request())
    if normal["outcome"] != "CASE_OPENED":
        raise RuntimeError("synthetic resume did not open a case")
    if duplicate["outcome"] != "DUPLICATE_ATTACHED":
        raise RuntimeError("synthetic duplicate did not attach to the current case")
    summary = {
        "synthetic_only": True,
        "normal_outcome": normal["outcome"],
        "duplicate_outcome": duplicate["outcome"],
        "submission_count": len(projection["submissions"]),
        "application_case_count": len(projection["cases"]),
        "application_case_opened_effects": projection["business_effect_counts"].get(
            "ApplicationCaseOpened", 0
        ),
        "source_count": len(
            projection["submissions"][normal["submission_id"]]["sources"]
        ),
        "tool_execution_count": projection["tool_execution_count"],
        "external_action_count": projection["external_action_count"],
    }
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
