#!/usr/bin/env python3
"""Dependency-free structural lint for the G1a product contracts.

This deliberately does not claim to implement JSON Schema 2020-12. The
implementation repository must still run a standards-compliant validator.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent
CONTROL_PATH = ROOT / "contracts/recruiting-agent-g1a-control.schema.json"
EVENT_PATH = ROOT / "contracts/recruiting-agent-g1a-event.schema.json"
PRD_PATH = ROOT / "招聘Agent_G1_MVP_PRD.md"
MATRIX_PATH = ROOT / "招聘Agent_G1a_需求追踪矩阵.md"
PACKAGE_PATH = ROOT / "招聘Agent_G1a_工程开工包.md"


def walk(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk(value)


def resolve_local_ref(schema: dict[str, Any], ref: str) -> Any:
    if not ref.startswith("#/"):
        raise AssertionError(f"only local refs are allowed in v1: {ref}")
    current: Any = schema
    for token in ref[2:].split("/"):
        token = token.replace("~1", "/").replace("~0", "~")
        current = current[token]
    return current


def table_ids(text: str, prefix: str) -> list[str]:
    pattern = re.compile(rf"^\| ({re.escape(prefix)}-\d{{3}}) \|", re.MULTILINE)
    return pattern.findall(text)


def pass_check(label: str, count: int | str) -> None:
    print(f"PASS | {label} | {count}")


def check_links(markdown_path: Path) -> int:
    text = markdown_path.read_text(encoding="utf-8")
    links = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    checked = 0
    for raw_target in links:
        target = raw_target.strip().strip("<>").split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = (markdown_path.parent / candidate).resolve()
        if not candidate.exists():
            raise AssertionError(f"broken link in {markdown_path.name}: {raw_target}")
        checked += 1
    return checked


def main() -> int:
    control = json.loads(CONTROL_PATH.read_text(encoding="utf-8"))
    event = json.loads(EVENT_PATH.read_text(encoding="utf-8"))

    for path, schema in ((CONTROL_PATH, control), (EVENT_PATH, event)):
        refs = [node["$ref"] for node in walk(schema) if "$ref" in node]
        for ref in refs:
            resolve_local_ref(schema, ref)
        pass_check(f"{path.name}: local refs resolve", len(refs))

    command_enum = control["$defs"]["CommandType"]["enum"]
    command_branches = control["$defs"]["CommandEnvelope"]["allOf"][0]["oneOf"]
    command_map = [branch["properties"]["command_type"]["const"] for branch in command_branches]
    assert len(command_enum) == len(set(command_enum)) == 19
    assert len(command_map) == len(set(command_map)) == 19
    assert set(command_enum) == set(command_map)
    for branch in command_branches:
        payload = resolve_local_ref(control, branch["properties"]["payload"]["$ref"])
        assert payload["type"] == "object"
        assert payload.get("additionalProperties") is False
    pass_check("command enum exactly covered by closed payload branches", len(command_enum))

    event_enum = event["$defs"]["EventType"]["enum"]
    event_branches = event["$defs"]["DomainEventEnvelope"]["allOf"][0]["oneOf"]
    event_map: list[str] = []
    for branch in event_branches:
        selector = branch["properties"]["event_type"]
        event_map.extend([selector["const"]] if "const" in selector else selector["enum"])
        payload = resolve_local_ref(event, branch["properties"]["payload"]["$ref"])
        assert payload["type"] == "object"
        assert payload.get("additionalProperties") is False
    assert len(event_enum) == len(set(event_enum)) == 24
    assert len(event_map) == len(set(event_map)) == 24
    assert set(event_enum) == set(event_map)
    pass_check("event enum exactly covered by closed payload branches", len(event_enum))

    assert set(control["$defs"]["AggregateType"]["enum"]) == set(
        event["$defs"]["AggregateType"]["enum"]
    )
    pass_check("aggregate enums equal across contracts", 7)

    error_codes = control["$defs"]["ErrorCode"]["enum"]
    assert len(error_codes) == len(set(error_codes))
    pass_check("error codes unique", len(error_codes))

    forbidden_event_keys = {
        "candidate_name",
        "email",
        "phone",
        "resume_text",
        "recording_url",
        "transcript_text",
        "transcript_body",
    }
    event_keys: set[str] = set()
    for node in walk(event):
        event_keys.update(node.keys())
    assert not event_keys.intersection(forbidden_event_keys)
    pass_check("event contract omits forbidden raw-content keys", len(forbidden_event_keys))

    prd_text = PRD_PATH.read_text(encoding="utf-8")
    matrix_text = MATRIX_PATH.read_text(encoding="utf-8")
    prd_fr = table_ids(prd_text, "FR")
    prd_at = table_ids(prd_text, "AT")
    matrix_fr = table_ids(matrix_text, "FR")
    matrix_at = table_ids(matrix_text, "AT")
    expected_fr = [f"FR-{index:03d}" for index in range(1, 33)]
    expected_at = [f"AT-{index:03d}" for index in range(1, 16)]
    assert prd_fr == expected_fr
    assert prd_at == expected_at
    assert matrix_fr == expected_fr
    assert matrix_at == expected_at
    pass_check("PRD and matrix FR coverage", len(matrix_fr))
    pass_check("PRD and matrix AT coverage", len(matrix_at))

    package_story_ids = set(re.findall(r"\bG1A-\d{3}\b", PACKAGE_PATH.read_text(encoding="utf-8")))
    matrix_story_ids = set(re.findall(r"\bG1A-\d{3}\b", matrix_text))
    missing_story_ids = sorted(matrix_story_ids - package_story_ids)
    assert not missing_story_ids, f"matrix references unknown stories: {missing_story_ids}"
    pass_check("matrix backlog references resolve", len(matrix_story_ids))

    markdown_paths = [
        PACKAGE_PATH,
        MATRIX_PATH,
        ROOT / "contracts/README.md",
        ROOT / "招聘Agent_领域与事件规格.md",
        ROOT / "招聘Agent推进看板.md",
    ]
    link_count = sum(check_links(path) for path in markdown_paths)
    pass_check("local Markdown links resolve", link_count)

    board = (ROOT / "招聘Agent推进看板.md").read_text(encoding="utf-8")
    gate = (ROOT / "招聘Agent_Gate0执行包.md").read_text(encoding="utf-8")
    assert "No-go" in board and "No-go" in gate
    assert "真实数据" in board and "外部" in board
    pass_check("release status remains explicit No-go", 2)

    print("NOTE | structural lint only; full JSON Schema 2020-12 fixture validation remains a CI requirement")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, KeyError, json.JSONDecodeError) as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise SystemExit(1)

