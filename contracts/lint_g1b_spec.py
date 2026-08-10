#!/usr/bin/env python3
"""Dependency-free consistency lint for the G1b product specification.

This checks document coverage and domain consistency only. It does not prove
implementation, model quality, legal approval, user adoption, or release.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRD = ROOT / "招聘Agent_G1b_终面评估包_PRD.md"
MATRIX = ROOT / "招聘Agent_G1b_需求追踪矩阵.md"
CONTEXT = ROOT / "CONTEXT.md"
DOMAIN = ROOT / "招聘Agent_领域与事件规格.md"
TOTAL_PLAN = ROOT / "招聘Agent产品落地总方案.md"
BOARD = ROOT / "招聘Agent推进看板.md"
GATE = ROOT / "招聘Agent_Gate0执行包.md"
PROTOTYPE_EVIDENCE = ROOT / "招聘Agent控制塔_原型验收记录.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def table_ids(text: str, prefix: str) -> list[str]:
    return re.findall(rf"^\| ({re.escape(prefix)}-\d{{3}}) \|", text, re.MULTILINE)


def check_links(path: Path) -> int:
    text = read(path)
    targets = re.findall(r"\[[^\]]+\]\(([^)]+)\)", text)
    checked = 0
    for raw in targets:
        target = raw.strip().strip("<>").split("#", 1)[0]
        if not target or target.startswith(("http://", "https://", "mailto:")):
            continue
        candidate = Path(target)
        assert not candidate.is_absolute(), f"nonportable absolute link in {path.name}: {raw}"
        candidate = (path.parent / candidate).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError as exc:
            raise AssertionError(f"link escapes repository in {path.name}: {raw}") from exc
        assert candidate.exists(), f"broken link in {path.name}: {raw}"
        checked += 1
    return checked


def passed(label: str, count: int | str) -> None:
    print(f"PASS | {label} | {count}")


def main() -> int:
    prd = read(PRD)
    matrix = read(MATRIX)
    context = read(CONTEXT)
    domain = read(DOMAIN)
    total_plan = read(TOTAL_PLAN)
    board = read(BOARD)
    gate = read(GATE)
    prototype = read(PROTOTYPE_EVIDENCE)

    expected_fr = [f"FR-{index:03d}" for index in range(101, 141)]
    expected_at = [f"AT-{index:03d}" for index in range(101, 119)]
    assert table_ids(prd, "FR") == expected_fr
    assert table_ids(matrix, "FR") == expected_fr
    passed("PRD and matrix FR coverage", len(expected_fr))
    assert table_ids(prd, "AT") == expected_at
    assert table_ids(matrix, "AT") == expected_at
    passed("PRD and matrix AT coverage", len(expected_at))

    terms = [
        "必需轮次（Required Round）",
        "轮次完成件（Round Completion Record）",
        "轮次豁免（Round Waiver）",
        "面前追问简报（Interview Brief）",
        "跨轮问题（Cross-round Issue）",
        "终面评估包（Final Assessment Package）",
        "终面评估就绪（Final Assessment Ready）",
        "终面评估包失效（Final Assessment Invalidation）",
    ]
    for term in terms:
        assert term in context, f"missing glossary term: {term}"
    passed("G1b canonical terms present in CONTEXT", len(terms))

    adr_files = sorted((ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    adr_numbers = [path.name[:4] for path in adr_files]
    assert adr_numbers == [f"{index:04d}" for index in range(1, len(adr_files) + 1)]
    g1b_adrs = [path for path in adr_files if path.name.startswith(("0005-", "0006-"))]
    assert len(g1b_adrs) == 2
    for path in g1b_adrs:
        assert "status: accepted" in read(path)
    passed("ADR numbering is contiguous and G1b decisions remain accepted", len(adr_files))

    aggregates = ["InterviewBrief", "CrossRoundIssue", "FinalAssessmentPackage"]
    commands = [
        "AmendInterviewPlan",
        "ActivateRound",
        "CreateRepeatRound",
        "RecordRoundWaiver",
        "PublishInterviewBrief",
        "ClassifyCrossRoundIssue",
        "ResolveCrossRoundIssue",
        "CompileFinalAssessmentPackage",
        "InvalidateFinalAssessmentPackage",
        "CreateFinalAssessmentReviewTask",
        "MarkFinalAssessmentReady",
    ]
    events = [
        "InterviewPlanPinned",
        "InterviewPlanAmended",
        "InterviewRoundRepeated",
        "RoundCompletionRecordInvalidated",
        "InterviewBriefPublished",
        "InterviewBriefInvalidated",
        "CrossRoundIssueDetected",
        "CrossRoundIssueClassified",
        "CrossRoundIssueResolved",
        "FinalAssessmentPackageReady",
        "FinalAssessmentPackageInvalidated",
        "FinalAssessmentReviewTaskCreated",
        "FinalAssessmentMarkedReady",
    ]
    for item in aggregates + commands + events:
        assert item in domain, f"domain spec missing: {item}"
    passed("G1b aggregates present in domain spec", len(aggregates))
    passed("G1b commands present in domain spec", len(commands))
    passed("G1b events present in domain spec", len(events))

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
    assert stage_rows == expected_stages
    passed("ApplicationCase remains exactly six stages", len(stage_rows))

    assert "FINAL_ASSESSMENT_READY` 只表示材料就绪" in prd, "PRD readiness wording missing"
    assert "FINAL_ASSESSMENT_READY` 不等于 HIRE/NO_HIRE" in domain, "domain decision separation wording missing"
    assert "RecordFinalDecision" in domain and "有权限的人" in domain, "human final-decision gate missing"
    assert "Agent 不能生成招聘建议、排名" in domain, "no-agent-decision invariant missing"
    passed("readiness remains separate from final human decision", 4)

    assert "| FR | 40 | 40 | 0 | 0 | 0 |" in matrix, "FR zero-evidence snapshot missing"
    assert "| AT | 18 | 18 | 0 | 0 | 0 |" in matrix, "AT zero-evidence snapshot missing"
    assert "完整正常链" in prototype and "跑完两轮" in prototype and "FINAL_ASSESSMENT_READY" in prototype, "bounded two-round prototype evidence missing"
    assert "不能证明其余 17 个 G1b 场景" in matrix, "prototype limitation wording missing"
    passed("prototype evidence is explicitly bounded", 2)

    linked_files = [PRD, MATRIX, DOMAIN, TOTAL_PLAN, BOARD]
    link_count = sum(check_links(path) for path in linked_files)
    passed("local Markdown links resolve", link_count)

    assert "No-go" in prd and "No-go" in board and "No-go" in gate
    assert "真实数据" in board and "外部" in board
    passed("release status remains explicit No-go", 3)

    assert "G1b 多轮与终面评估包 PRD" in total_plan
    assert "G1b 多轮与终面评估包 PRD" in board
    assert "E-014" in gate
    passed("portfolio and Gate 0 are synchronized", 3)

    print("NOTE | document lint only; implementation, legal, model, user and release evidence remain absent")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise SystemExit(1)
