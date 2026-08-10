#!/usr/bin/env python3
"""Dependency-free consistency lint for the G2 product specification.

This validates document structure, traceability, domain boundaries and explicit
evidence limits. It does not prove implementation, connector behavior, model
quality, legal approval, human adoption, autonomy maturity or release.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRD = ROOT / "招聘Agent_G2_收件筛选约面_PRD.md"
MATRIX = ROOT / "招聘Agent_G2_需求追踪矩阵.md"
CONTEXT = ROOT / "CONTEXT.md"
DOMAIN = ROOT / "招聘Agent_领域与事件规格.md"
TOTAL_PLAN = ROOT / "招聘Agent产品落地总方案.md"
BOARD = ROOT / "招聘Agent推进看板.md"
GATE = ROOT / "招聘Agent_Gate0执行包.md"
README = ROOT / "README.md"
ADR_0007 = ROOT / "docs/adr/0007-scheduling-proposal-is-not-a-booking.md"
ADR_0008 = ROOT / "docs/adr/0008-recording-notice-is-not-consent.md"
VALIDATION = ROOT / "招聘Agent_G2_产品规格验收记录.md"
LINT = Path(__file__).resolve()

MANIFEST_INPUTS = [
    PRD,
    MATRIX,
    CONTEXT,
    DOMAIN,
    ADR_0007,
    ADR_0008,
    TOTAL_PLAN,
    BOARD,
    GATE,
    README,
    LINT,
]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def table_ids(text: str, prefix: str) -> list[str]:
    return re.findall(rf"^\| ({re.escape(prefix)}-\d{{3}}) \|", text, re.MULTILINE)


def matrix_rows(text: str, prefix: str) -> list[list[str]]:
    rows: list[list[str]] = []
    pattern = re.compile(rf"^{re.escape(prefix)}-\d{{3}}$")
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and pattern.fullmatch(cells[0]):
            rows.append(cells)
    return rows


def markdown_rows(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        if not line.startswith("| "):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if not cells or not cells[0] or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append(cells)
    return rows


def check_links(path: Path) -> int:
    text = read(path)
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    checked = 0
    for raw in targets:
        target = raw.strip().strip("<>").split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = (path.parent / candidate).resolve()
        assert candidate.exists(), f"broken link in {path.name}: {raw}"
        checked += 1
    return checked


def manifest_sha256(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix().encode("utf-8")
        digest.update(relative)
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def passed(label: str, count: int | str) -> None:
    print(f"PASS | {label} | {count}")


def main() -> int:
    required_files = [
        PRD,
        MATRIX,
        CONTEXT,
        DOMAIN,
        TOTAL_PLAN,
        BOARD,
        GATE,
        README,
        ADR_0007,
        ADR_0008,
        VALIDATION,
    ]
    for path in required_files:
        assert path.exists(), f"missing required file: {path.relative_to(ROOT)}"

    prd = read(PRD)
    matrix = read(MATRIX)
    context = read(CONTEXT)
    domain = read(DOMAIN)
    total_plan = read(TOTAL_PLAN)
    board = read(BOARD)
    gate = read(GATE)
    validation = read(VALIDATION)

    expected_fr = [f"FR-{index:03d}" for index in range(201, 265)]
    expected_at = [f"AT-{index:03d}" for index in range(201, 229)]
    assert table_ids(prd, "FR") == expected_fr, "PRD FR IDs must be continuous and unique"
    assert table_ids(matrix, "FR") == expected_fr, "matrix FR IDs must match PRD exactly"
    passed("PRD and matrix FR coverage", len(expected_fr))
    assert table_ids(prd, "AT") == expected_at, "PRD AT IDs must be continuous and unique"
    assert table_ids(matrix, "AT") == expected_at, "matrix AT IDs must match PRD exactly"
    passed("PRD and matrix AT coverage", len(expected_at))

    fr_rows = matrix_rows(matrix, "FR")
    at_rows = matrix_rows(matrix, "AT")
    assert all(len(row) == 6 for row in fr_rows), "every FR matrix row must have six cells"
    assert all(len(row) == 6 for row in at_rows), "every AT matrix row must have six cells"
    test_ids: list[str] = []
    for row in fr_rows:
        identifier = row[0]
        number = identifier.split("-", 1)[1]
        assert row[4] == f"EV-G2-FR{number}", f"wrong FR evidence slot: {identifier}"
        assert row[5] == "SPEC", f"FR current state must remain SPEC: {identifier}"
        found = re.findall(r"G2-[A-Z0-9-]+", row[3])
        assert found, f"missing stable target-test ID: {identifier}"
        test_ids.append(found[0])
    assert len(test_ids) == len(set(test_ids)), "FR target-test IDs must be unique"
    for row in at_rows:
        identifier = row[0]
        number = identifier.split("-", 1)[1]
        assert row[4] == f"EV-G2-AT{number}", f"wrong AT evidence slot: {identifier}"
        assert row[5] == "SPEC", f"AT current state must remain SPEC: {identifier}"
        assert row[3], f"AT automation layer must be present: {identifier}"
    passed("matrix row shape, evidence slots and SPEC state", len(fr_rows) + len(at_rows))

    expected_fr_set = set(expected_fr)
    covered: set[str] = set()
    for row in at_rows:
        references = set(re.findall(r"FR-\d{3}", row[2]))
        assert references, f"AT has no FR mapping: {row[0]}"
        assert references <= expected_fr_set, f"AT references out-of-range FR: {row[0]}"
        covered.update(references)
    missing_coverage = sorted(expected_fr_set - covered)
    assert not missing_coverage, f"FRs without AT coverage: {missing_coverage}"
    passed("every G2 FR is covered by at least one AT", len(covered))

    assert "| FR | 64 | 64 | 0 | 0 | 0 |" in matrix, "FR zero-evidence snapshot missing"
    assert "| AT | 28 | 28 | 0 | 0 | 0 |" in matrix, "AT zero-evidence snapshot missing"
    assert "IMPLEMENTED、VERIFIED 或 RELEASED" in matrix, "evidence limitation wording missing"
    passed("coverage snapshot preserves zero implementation claims", 2)

    terms = [
        "招聘周期（Recruitment Cycle）",
        "结构化简历版本（Structured Resume Version）",
        "申请路由（Application Routing）",
        "筛选输入清单（Screening Input Manifest）",
        "人岗匹配材料（Match Assessment）",
        "部门决定请求（Department Decision Request）",
        "候选人协调请求（Candidate Coordination Request）",
        "时段提案（Scheduling Proposal）",
        "预约修订（Appointment Revision）",
        "面试预定（Interview Booking）",
        "录制告知（Recording Notice）",
        "采集选择凭证（Consent Receipt）",
        "采集闸门（Capture Gate）",
        "无录制路线（No-recording Route）",
        "面试证据交接（Interview Evidence Handoff）",
        "处理控制事实（Processing Control Fact）",
    ]
    for term in terms:
        assert term in context, f"missing G2 glossary term: {term}"
    passed("G2 canonical terms present in CONTEXT", len(terms))

    adr_files = sorted((ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    adr_numbers = [path.name[:4] for path in adr_files]
    assert adr_numbers == [f"{index:04d}" for index in range(1, len(adr_files) + 1)]
    assert adr_numbers[-2:] == ["0007", "0008"], "G2 ADRs must be 0007 and 0008"
    for path in [ADR_0007, ADR_0008]:
        assert "status: accepted" in read(path), f"ADR not accepted: {path.name}"
    assert "不等于面试预定" in read(ADR_0007)
    assert "录制告知不等于采集授权" in read(ADR_0008)
    passed("ADR numbering and G2 decisions accepted", len(adr_files))

    aggregates = [
        "ResumeSubmission",
        "ApplicationCase",
        "MatchAssessment",
        "InterviewRound",
        "InterviewSession",
        "ConsentReceipt",
        "ProcessingControl",
        "ActionExecution",
        "ExceptionBundle",
    ]
    commands = [
        "RegisterResumeSubmission",
        "RecordStructuredResumeVersion",
        "ResolveApplicationRouting",
        "SupersedeApplicationRouting",
        "SupersedeSubmissionCaseLink",
        "CloseMisroutedApplicationCase",
        "OpenOrAttachApplicationCase",
        "PinScreeningInput",
        "PublishMatchAssessment",
        "OpenDepartmentDecisionRequest",
        "InvalidateCurrentMatchAssessment",
        "RecordDepartmentDecision",
        "ResumeDepartmentDecisionRequest",
        "AdvanceReminderOrdinal",
        "OpenCandidateCoordinationRequest",
        "PublishSchedulingProposal",
        "RecordCandidateSlotSelection",
        "ProposeAppointmentRevision",
        "CommitBooking",
        "RequestReschedule",
        "CommitBookingCancellation",
        "RecordRecordingNoticeDelivery",
        "RecordParticipantRecordingChoice",
        "RecordParticipantJoined",
        "RecordParticipantLeft",
        "EvaluateCaptureGate",
        "StartInterview",
        "MarkInterviewRoundInProgress",
        "RequestCaptureStart",
        "ConfirmCaptureStarted",
        "RequestCaptureStop",
        "ConfirmCaptureStopped",
        "MarkCaptureStateMismatch",
        "FinishInterview",
        "CreateInterviewEvidenceHandoff",
        "InvalidateInterviewEvidenceHandoff",
        "AcceptInterviewEvidenceHandoff",
        "InvalidateRoundEvidenceInput",
        "RecallFinalAssessmentReadiness",
    ]
    events = [
        "ResumeSubmissionReceived",
        "StructuredResumeVersionCreated",
        "ApplicationRoutingResolved",
        "ApplicationRoutingReviewRequired",
        "ApplicationRoutingSuperseded",
        "ResumeSubmissionCaseLinkSuperseded",
        "MisroutedApplicationCaseClosed",
        "ApplicationCaseOpened",
        "ScreeningInputPinned",
        "CurrentMatchAssessmentPinned",
        "CurrentMatchAssessmentInvalidated",
        "DepartmentDecisionRequestOpened",
        "DepartmentDecisionRequestHeld",
        "DepartmentDecisionRequestResumed",
        "CandidateCoordinationRequestOpened",
        "SchedulingProposalPublished",
        "CandidateSlotSelectionRecorded",
        "AppointmentRevisionProposed",
        "AppointmentRevisionAborted",
        "InterviewBookingCommitted",
        "InterviewBookingInvalidated",
        "InterviewBookingCancelled",
        "RecordingNoticeDelivered",
        "ParticipantConsentRecorded",
        "ParticipantConsentWithdrawn",
        "SessionParticipantJoined",
        "CaptureGateEvaluated",
        "InterviewSessionStarted",
        "CaptureStartRequested",
        "CaptureStarted",
        "CaptureStopRequested",
        "CaptureStopped",
        "CaptureStateMismatchDetected",
        "InterviewEvidenceHandoffCreated",
        "InterviewEvidenceHandoffSuperseded",
        "InterviewEvidenceHandoffInvalidated",
        "InterviewEvidenceHandoffAccepted",
        "RoundEvidenceInputInvalidated",
        "FinalAssessmentReadinessRecalled",
    ]
    aggregate_section = domain.split("## 4. 聚合根", 1)[1].split("## 5.", 1)[0]
    aggregate_names = {
        row[0]
        for row in markdown_rows(aggregate_section)
        if re.fullmatch(r"[A-Z][A-Za-z0-9]+", row[0])
    }
    assert set(aggregates) <= aggregate_names, "required G2 aggregates must be table rows"

    command_section = domain.split("## 12. 关键迁移门", 1)[1].split("### 12.1", 1)[0]
    command_rows = markdown_rows(command_section)
    command_names: set[str] = set()
    command_by_name: dict[str, list[str]] = {}
    for row in command_rows:
        match = re.match(r"([A-Z][A-Za-z0-9]+)", row[0])
        if not match:
            continue
        name = match.group(1)
        command_names.add(name)
        command_by_name.setdefault(name, row)
    assert set(commands) <= command_names, "required G2 commands must be migration-table rows"

    event_section = domain.split("## 14. 领域事件目录", 1)[1].split("## 15. 跨对象不变量", 1)[0]
    event_names = re.findall(r"^\| ([A-Z][A-Za-z0-9]+) \|", event_section, re.MULTILINE)
    duplicates = sorted({name for name in event_names if event_names.count(name) > 1})
    assert not duplicates, f"duplicate domain event rows: {duplicates}"
    assert set(events) <= set(event_names), "required G2 events must be event-table rows"
    passed("G2 aggregates present in domain spec", len(aggregates))
    passed("G2 commands present in domain spec", len(commands))
    passed("G2 events present and unique in domain spec", len(events))

    stage_section = domain.split("## 7. 申请案件顶层阶段", 1)[1].split("允许迁移：", 1)[0]
    stage_rows = re.findall(r"^\| ([A-Z_]+) \|", stage_section, re.MULTILINE)
    expected_stages = [
        "RECEIVED",
        "SCREENING",
        "AWAITING_DEPARTMENT_DECISION",
        "INTERVIEWING",
        "FINAL_ASSESSMENT_READY",
        "CLOSED",
    ]
    assert stage_rows == expected_stages, f"unexpected ApplicationCase stages: {stage_rows}"
    assert "页面状态是投影，不是第四套真相" in domain, "page projection boundary missing"
    scheduling_section = domain.split("### 8.3 G2 会话协调与预约", 1)[1].split(
        "### 8.4 G2 面试与采集", 1
    )[0]
    for token in ["Round=SCHEDULED", "全部", "BOOKED"]:
        assert token in scheduling_section, f"multi-session scheduling rule missing token: {token}"
    passed("ApplicationCase remains six stages and scheduling is projected", len(stage_rows))

    handoff_section = domain.split("### 8.5 G2 G1 交接", 1)[1].split("## 9.", 1)[0]
    for token in [
        "RECORDED_EVIDENCE",
        "AUTHORIZED_NOTES_ONLY",
        "RECORDING",
        "NOTES_ONLY",
        "current_handoff_ref",
        "capture history/final reconciliation refs",
    ]:
        assert token in handoff_section, f"G1 handoff route/lifecycle token missing: {token}"
    assert "InterviewEvidenceHandoffInvalidated" in event_names

    round_start_command = " ".join(command_by_name["MarkInterviewRoundInProgress"])
    assert "SCHEDULING/SCHEDULED→IN_PROGRESS" in round_start_command
    assert "后续 Booking 不得回退 Round" in round_start_command

    create_handoff_command = " ".join(command_by_name["CreateInterviewEvidenceHandoff"])
    for token in [
        "InterviewSession=ENDED",
        "STARTING/ON/STOPPING/状态未知",
        "RECORDED_EVIDENCE 要求 STOPPED",
        "片段隔离/删除/处置完成",
    ]:
        assert token in create_handoff_command, f"handoff settlement gate missing: {token}"

    assert "Round" not in command_by_name["StartInterview"][1]
    assert "Round" not in command_by_name["CreateInterviewEvidenceHandoff"][1]
    assert "Case" not in command_by_name["InvalidateFinalAssessmentPackage"][1]
    seam_section = domain.split("### 12.1 跨聚合 seam", 1)[1].split("## 13.", 1)[0]
    expected_seams = [
        (
            "StartInterview",
            "InterviewSession",
            "InterviewSessionStarted",
            "MarkInterviewRoundInProgress",
            "InterviewRound",
        ),
        (
            "CreateInterviewEvidenceHandoff",
            "InterviewSession",
            "InterviewEvidenceHandoffCreated",
            "AcceptInterviewEvidenceHandoff",
            "InterviewRound",
        ),
        (
            "InvalidateInterviewEvidenceHandoff",
            "InterviewSession",
            "InterviewEvidenceHandoffInvalidated",
            "InvalidateRoundEvidenceInput",
            "InterviewRound",
        ),
        (
            "InvalidateFinalAssessmentPackage",
            "FinalAssessmentPackage",
            "FinalAssessmentPackageInvalidated",
            "RecallFinalAssessmentReadiness",
            "ApplicationCase",
        ),
    ]
    actual_seams = [
        tuple(row)
        for row in markdown_rows(seam_section)
        if row[0] in {item[0] for item in expected_seams}
    ]
    assert actual_seams == expected_seams, "cross-aggregate seam table drifted"
    passed("G2 evidence handoff and single-aggregate seams are explicit", len(expected_seams))

    invariants = [
        "INV-G2-ROUTED-ONLY",
        "INV-G2-ROUTING-CORRECTION",
        "INV-G2-NO-AUTO-REJECT",
        "INV-G2-HUMAN-DECISION",
        "INV-G2-PROPOSAL-NOT-BOOKING",
        "INV-G2-CURRENT-REVISION",
        "INV-G2-NOTICE-NOT-CONSENT",
        "INV-G2-NO-RECORDING-EQUIVALENCE",
        "INV-G2-LATE-JOINER-GATE",
        "INV-G2-CAPTURE-CONFIRMATION",
        "INV-G2-CONTROL-SCOPE",
        "INV-G2-CONTROL-PREFLIGHT",
        "INV-G2-NO-LLM-ACTION",
        "INV-G2-SAFETY-COMPENSATION",
        "INV-G2-G1-HANDOFF",
        "INV-G2-G1-HANDOFF-INVALIDATION",
        "INV-CONTROL-SINGLE-AGGREGATE",
    ]
    assert len(invariants) == len(set(invariants)), "G2 invariant IDs must be unique"
    for invariant in invariants:
        assert invariant in prd, f"PRD missing invariant: {invariant}"
        assert invariant in domain, f"domain missing invariant: {invariant}"
    passed("stable G2 invariants agree across PRD and domain", len(invariants))

    prd_at_rows = {row[0]: row for row in matrix_rows(prd, "AT")}
    at_214 = " ".join(prd_at_rows["AT-214"])
    assert "Round 进入 IN_PROGRESS" in at_214
    assert "不得把 Round 回退为 SCHEDULED" in at_214
    assert "InterviewEvidenceHandoffInvalidated" in " ".join(prd_at_rows["AT-226"])
    at_226 = " ".join(prd_at_rows["AT-226"])
    assert "未结算交接被硬拒绝" in at_226
    assert "STARTING/ON/STOPPING/未知" in at_226
    assert all(
        token in " ".join(prd_at_rows["AT-228"])
        for token in [
            "RECORDED_EVIDENCE",
            "AUTHORIZED_NOTES_ONLY",
            "capture history",
        ]
    )
    at_mapping = {row[0]: set(re.findall(r"FR-\d{3}", row[2])) for row in at_rows}
    assert {"FR-258", "FR-264"} <= at_mapping["AT-226"]
    passed("multi-session start and settled handoff routes are acceptance-covered", 5)

    linked_files = [PRD, MATRIX, DOMAIN, TOTAL_PLAN, BOARD, GATE, README, VALIDATION]
    link_count = sum(check_links(path) for path in linked_files)
    passed("local Markdown links resolve", link_count)

    assert "No-go" in prd and "No-go" in board and "No-go" in gate
    assert "真实数据" in board and "外部" in board
    assert "G2 从收件到可信面试交接 PRD" in total_plan
    assert "G2 收件筛选约面 PRD" in board
    assert "E-015" in gate and "e91eb5a" in gate
    assert "E-016" in gate
    passed("portfolio, repository evidence and Gate remain synchronized", 5)

    roadmap_pattern = re.compile(
        r"ROADMAP-RB1：G1a=(W\d+–\d+)；G1b=(W\d+–\d+)；G2=(W\d+–\d+)"
    )
    plan_roadmap = roadmap_pattern.search(total_plan)
    board_roadmap = roadmap_pattern.search(board)
    assert plan_roadmap and board_roadmap, "ROADMAP-RB1 missing from plan or board"
    assert plan_roadmap.groups() == board_roadmap.groups() == ("W3–4", "W5–8", "W9–16")
    for token in [
        "建议的 16 周工程顺序",
        "G2 影子准备",
        "不构成 G2 阶段进入或动作放权",
    ]:
        assert token in board, f"board roadmap qualifier missing: {token}"
    passed("plan and board roadmap baseline agree", 3)

    expected_hash = manifest_sha256(MANIFEST_INPUTS)
    assert f"权威输入 SHA-256：{expected_hash}" in validation, "validation input hash is stale"
    assert "## 已证明" in validation and "## 未证明" in validation
    not_proven = [
        "工程实现",
        "真实账号连接器",
        "模型质量",
        "法律批准",
        "真人采用",
        "A0/A1/A2/A3",
        "外部发送",
        "发布",
        "G1a 交接契约扩展",
    ]
    for item in not_proven:
        assert item in validation, f"validation limitation missing: {item}"
    passed("validation record is current and bounded", expected_hash[:12])

    print(
        "NOTE | document lint only; implementation, connectors, legal approval, "
        "model quality, users, autonomy evidence and release remain absent"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise SystemExit(1)
