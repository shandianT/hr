#!/usr/bin/env python3
"""Dependency-free consistency lint for the G3 product specification.

This proves static product/domain traceability only. It does not prove lawful
data access, implementation, statistical validity, fairness, user adoption,
autonomy evidence, profile publication, or release.
"""

from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PRD = ROOT / "招聘Agent_G3_结果回流与画像治理_PRD.md"
MATRIX = ROOT / "招聘Agent_G3_需求追踪矩阵.md"
VALIDATION = ROOT / "招聘Agent_G3_产品规格验收记录.md"
CONTEXT = ROOT / "CONTEXT.md"
DOMAIN = ROOT / "招聘Agent_领域与事件规格.md"
ADR_0009 = ROOT / "docs/adr/0009-outcomes-do-not-auto-train-role-profiles.md"
DESIGN = ROOT / "docs/招聘Agent_Hermes式Agent与UI设计原则.md"
CLAUDE_TASK = ROOT / "交付/Claude原型设计任务书.md"
PACKAGE_MANIFEST = ROOT / "交付/Claude原型设计包清单.md"
TOTAL_PLAN = ROOT / "招聘Agent产品落地总方案.md"
BOARD = ROOT / "招聘Agent推进看板.md"
GATE = ROOT / "招聘Agent_Gate0执行包.md"
README = ROOT / "README.md"
LINT = ROOT / "contracts/lint_g3_spec.py"

MANIFEST_INPUTS = [
    PRD,
    MATRIX,
    CONTEXT,
    DOMAIN,
    ADR_0009,
    DESIGN,
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
    checked = 0
    for raw in re.findall(r"\[[^\]]+\]\(([^)]+)\)", read(path)):
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
    required_files = MANIFEST_INPUTS + [VALIDATION, CLAUDE_TASK, PACKAGE_MANIFEST]
    for path in required_files:
        assert path.exists(), f"missing required file: {path.relative_to(ROOT)}"

    prd = read(PRD)
    matrix = read(MATRIX)
    context = read(CONTEXT)
    domain = read(DOMAIN)
    total_plan = read(TOTAL_PLAN)
    board = read(BOARD)
    gate = read(GATE)
    readme = read(README)
    design = read(DESIGN)
    claude_task = read(CLAUDE_TASK)
    package_manifest = read(PACKAGE_MANIFEST)
    validation = read(VALIDATION)

    expected_fr = [f"FR-{index:03d}" for index in range(301, 361)]
    expected_at = [f"AT-{index:03d}" for index in range(301, 331)]
    assert table_ids(prd, "FR") == expected_fr, "PRD FR IDs must be continuous and unique"
    assert table_ids(matrix, "FR") == expected_fr, "matrix FR IDs must match PRD exactly"
    assert table_ids(prd, "AT") == expected_at, "PRD AT IDs must be continuous and unique"
    assert table_ids(matrix, "AT") == expected_at, "matrix AT IDs must match PRD exactly"
    passed("PRD and matrix FR/AT coverage", f"{len(expected_fr)}/{len(expected_at)}")

    fr_rows = matrix_rows(matrix, "FR")
    at_rows = matrix_rows(matrix, "AT")
    assert all(len(row) == 6 for row in fr_rows + at_rows), "matrix rows must have six cells"
    test_ids: list[str] = []
    for row in fr_rows:
        identifier = row[0]
        number = identifier.split("-", 1)[1]
        assert row[4] == f"EV-G3-FR{number}", f"wrong FR evidence slot: {identifier}"
        assert row[5] == "SPEC", f"FR state must remain SPEC: {identifier}"
        found = re.findall(r"G3-[A-Z0-9-]+", row[3])
        assert found, f"missing stable target-test ID: {identifier}"
        test_ids.append(found[0])
    assert len(test_ids) == len(set(test_ids)), "FR target-test IDs must be unique"
    for row in at_rows:
        identifier = row[0]
        number = identifier.split("-", 1)[1]
        assert row[4] == f"EV-G3-AT{number}", f"wrong AT evidence slot: {identifier}"
        assert row[5] == "SPEC", f"AT state must remain SPEC: {identifier}"
        assert row[3], f"AT target automation layer missing: {identifier}"
    passed("matrix shape, evidence slots and SPEC state", len(fr_rows) + len(at_rows))

    expected_fr_set = set(expected_fr)
    covered: set[str] = set()
    for row in at_rows:
        references = set(re.findall(r"FR-\d{3}", row[2]))
        assert references, f"AT has no FR mapping: {row[0]}"
        assert references <= expected_fr_set, f"AT references out-of-range FR: {row[0]}"
        covered.update(references)
    assert covered == expected_fr_set, f"FRs without AT coverage: {sorted(expected_fr_set - covered)}"
    passed("every G3 FR is covered by AT", len(covered))

    for snapshot in [
        "| FR | 60 | 60 | 0 | 0 | 0 |",
        "| AT | 30 | 30 | 0 | 0 | 0 |",
        "| 横向 Gate | 9 | 9 | 0 | 0 | 0 |",
    ]:
        assert snapshot in matrix, f"zero-evidence snapshot missing: {snapshot}"
    assert "IMPLEMENTED、VERIFIED 或 RELEASED" in matrix
    passed("coverage snapshot preserves zero implementation claims", 3)

    terms = [
        "结果观察（Outcome Observation）",
        "结果标注（Outcome Label）",
        "任职后表现信号（Post-hire Performance Signal）",
        "分析队列快照（Analysis Cohort Snapshot）",
        "结果回流研究（Feedback Study）",
        "画像候选修订（Profile Candidate Revision）",
        "画像变更提案（Profile Change Proposal）",
        "画像发布修订（Profile Publication Revision）",
        "画像发布回滚（Profile Publication Rollback）",
        "Agent 运行检查点（Agent Run Checkpoint）",
    ]
    for term in terms:
        assert term in context, f"missing G3 glossary term: {term}"
    passed("G3 canonical terms present in CONTEXT", len(terms))

    adr_files = sorted((ROOT / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    numbers = [path.name[:4] for path in adr_files]
    assert numbers == [f"{index:04d}" for index in range(1, len(adr_files) + 1)]
    assert ADR_0009 in adr_files and "status: accepted" in read(ADR_0009)
    assert "结果观察不是真值" in read(ADR_0009)
    passed("ADR numbering and G3 decision accepted", len(adr_files))

    aggregates = [
        "ProcessingControl",
        "ActionExecution",
        "OutcomeObservation",
        "OutcomeLabel",
        "AnalysisCohortSnapshot",
        "FeedbackStudy",
        "AgentRun",
        "ProfileCandidateRevision",
        "ProfileChangeProposal",
        "RoleProfile",
        "ProfileExposureLedger",
    ]
    aggregate_section = domain.split("## 4. 聚合根", 1)[1].split("## 5.", 1)[0]
    aggregate_names = {row[0] for row in markdown_rows(aggregate_section)}
    assert set(aggregates) <= aggregate_names, "required G3 aggregates must be aggregate-table rows"

    commands = [
        "SupersedeFinalDecision",
        "ApplyProcessingRestriction",
        "ApplyDeletionDirective",
        "RecordOutcomeSourceAssertion",
        "ReconcileOutcomeObservation",
        "ReferenceHiringDecisionObservation",
        "ConfirmOutcomeObservation",
        "DisputeOutcomeObservation",
        "CorrectOutcomeObservation",
        "InvalidateOutcomeObservation",
        "DeriveOutcomeLabelDraft",
        "VerifyOutcomeLabel",
        "ExcludeOutcomeLabel",
        "InvalidateOutcomeLabel",
        "OpenAnalysisCohortSnapshot",
        "SealAnalysisCohortSnapshot",
        "InvalidateAnalysisCohortSnapshot",
        "CreateProfileCandidateRevision",
        "InvalidateProfileCandidateRevision",
        "PreregisterFeedbackStudy",
        "OpenConfirmatoryHoldout",
        "AcceptOfflineEvaluationReport",
        "InvalidateFeedbackStudy",
        "StartAgentRun",
        "CommitRunCheckpoint",
        "RecordToolResult",
        "CompleteAgentRun",
        "InvalidateAgentRun",
        "OpenProfileChangeProposal",
        "StageFeedbackStudyEvidence",
        "RecordProfileReleaseGateAssessment",
        "MarkProfileProposalReleaseEligible",
        "AttachFeedbackStudyEvidence",
        "OpenProfileChangeReviewTask",
        "RequestProfileProposalRevision",
        "RejectProfileChangeProposal",
        "SupersedeProfileChangeProposal",
        "InvalidateProfileChangeProposal",
        "RecordProfileProposalApproval",
        "RecallProfileProposalApproval",
        "AuthorizeProfilePublication",
        "PrepareProfilePublication",
        "RequestProfilePublicationSyncAction",
        "AcceptProfilePublicationSyncReceipt",
        "CommitProfilePublication",
        "FreezeProfilePublication",
        "CancelProfilePublicationSyncAction",
        "AuthorizeProfileRollback",
        "RollbackProfilePublication",
        "AssignProfileExposure",
        "RecordActualProfileExposure",
        "RecordProfileExposureContamination",
    ]
    command_section = domain.split("## 12. 关键迁移门", 1)[1].split("### 12.1", 1)[0]
    command_rows: dict[str, list[str]] = {}
    for row in markdown_rows(command_section):
        match = re.match(r"([A-Z][A-Za-z0-9]+)", row[0])
        if match:
            command_rows[match.group(1)] = row
    command_names = set(command_rows)
    assert set(commands) <= command_names, "required G3 commands must be migration-table rows"

    events = [
        "FinalHiringDecisionRecorded",
        "FinalHiringDecisionSuperseded",
        "ProcessingRestrictionApplied",
        "DeletionDirectiveApplied",
        "OutcomeSourceAssertionRecorded",
        "OutcomeObservationReconciled",
        "OutcomeObservationConfirmed",
        "OutcomeObservationDisputed",
        "OutcomeObservationCorrected",
        "OutcomeObservationInvalidated",
        "OutcomeLabelDrafted",
        "OutcomeLabelVerified",
        "OutcomeLabelExcluded",
        "OutcomeLabelInvalidated",
        "AnalysisCohortSnapshotOpened",
        "AnalysisCohortSnapshotSealed",
        "AnalysisCohortSnapshotInvalidated",
        "ProfileCandidateRevisionFrozen",
        "ProfileCandidateRevisionInvalidated",
        "FeedbackStudyPreregistered",
        "ConfirmatoryHoldoutOpened",
        "AgentRunStarted",
        "AgentRunCheckpointCommitted",
        "AgentToolResultRecorded",
        "AgentRunSucceeded",
        "AgentRunInvalidated",
        "FeedbackStudyAnalysisReady",
        "FeedbackStudyInvalidated",
        "ProfileChangeProposalOpened",
        "ProfileStudyEvidenceStaged",
        "ProfileReleaseGateAssessmentRecorded",
        "ProfileReleaseEligibilityEstablished",
        "ProfileReleaseEligibilityInvalidated",
        "ProfileStudyEvidenceAttached",
        "ProfileChangeProposalReviewReady",
        "ProfileChangeReviewTaskOpened",
        "ProfileProposalRevisionRequested",
        "ProfileChangeProposalRejected",
        "ProfileChangeProposalSuperseded",
        "ProfileChangeProposalInvalidated",
        "ProfileApprovalSubmitted",
        "ProfileChangeProposalApproved",
        "ProfileChangeProposalApprovalRecalled",
        "ProfilePublicationAuthorized",
        "ProfilePublicationPrepared",
        "ProfilePublicationSyncReceiptAccepted",
        "ProfilePublicationCommitted",
        "ProfilePublicationFrozen",
        "ProfileRollbackAuthorized",
        "ProfilePublicationRolledBack",
        "ProfileExposureAssigned",
        "ActualProfileExposureRecorded",
        "ProfileExposureContaminationRecorded",
    ]
    event_section = domain.split("## 14. 领域事件目录", 1)[1].split("## 15.", 1)[0]
    event_names = re.findall(r"^\| ([A-Z][A-Za-z0-9]+) \|", event_section, re.MULTILINE)
    duplicates = sorted({name for name in event_names if event_names.count(name) > 1})
    assert not duplicates, f"duplicate event rows: {duplicates}"
    assert set(events) <= set(event_names), "required G3 events must be event-table rows"
    passed("G3 aggregates, commands and events are explicit", f"{len(aggregates)}/{len(commands)}/{len(events)}")

    stage_section = domain.split("## 7. 申请案件顶层阶段", 1)[1].split("允许迁移：", 1)[0]
    stage_rows = re.findall(r"^\| ([A-Z_]+) \|", stage_section, re.MULTILINE)
    assert stage_rows == [
        "RECEIVED",
        "SCREENING",
        "AWAITING_DEPARTMENT_DECISION",
        "INTERVIEWING",
        "FINAL_ASSESSMENT_READY",
        "CLOSED",
    ]
    assert "FinalHiringDecisionRecorded" in domain and "ApplicationCase" in domain
    seam_section = domain.split("### 12.1 跨聚合 seam", 1)[1].split("## 13.", 1)[0]
    seam_rows = markdown_rows(seam_section)

    def seam_exists(source: str, event: str, consumer: str) -> bool:
        return any(
            len(row) >= 5
            and row[0] == source
            and event in row[2]
            and consumer in row[3]
            for row in seam_rows
        )

    required_seams = [
        ("RecordFinalDecision", "FinalHiringDecisionRecorded", "ReferenceHiringDecisionObservation"),
        ("SupersedeFinalDecision", "FinalHiringDecisionSuperseded", "CorrectOutcomeObservation"),
        ("InvalidateOutcomeObservation", "OutcomeObservationInvalidated", "InvalidateOutcomeLabel"),
        ("SealAnalysisCohortSnapshot", "AnalysisCohortSnapshotSealed", "CreateProfileCandidateRevision"),
        ("CreateProfileCandidateRevision", "ProfileCandidateRevisionFrozen", "PreregisterFeedbackStudy"),
        ("OpenConfirmatoryHoldout", "ConfirmatoryHoldoutOpened", "StartAgentRun"),
        ("CompleteAgentRun", "AgentRunSucceeded", "AcceptOfflineEvaluationReport"),
        ("AcceptOfflineEvaluationReport", "FeedbackStudyAnalysisReady", "OpenProfileChangeProposal"),
        ("AuthorizeProfilePublication", "ProfilePublicationAuthorized", "PrepareProfilePublication"),
        ("PrepareProfilePublication", "ProfilePublicationPrepared", "RequestProfilePublicationSyncAction"),
        ("CommitProfilePublication", "ProfilePublicationCommitted", "新 Case pinning"),
        ("InvalidateAnalysisCohortSnapshot", "AnalysisCohortSnapshotInvalidated", "InvalidateProfileCandidateRevision"),
        ("InvalidateAnalysisCohortSnapshot", "AnalysisCohortSnapshotInvalidated", "InvalidateAgentRun"),
        ("InvalidateAnalysisCohortSnapshot", "AnalysisCohortSnapshotInvalidated", "InvalidateFeedbackStudy"),
        ("InvalidateProfileCandidateRevision", "ProfileCandidateRevisionInvalidated", "InvalidateFeedbackStudy"),
        ("InvalidateAgentRun", "AgentRunInvalidated", "InvalidateFeedbackStudy"),
        ("InvalidateFeedbackStudy", "FeedbackStudyInvalidated", "InvalidateProfileChangeProposal"),
        ("InvalidateProfileChangeProposal", "ProfileChangeProposalInvalidated", "FreezeProfilePublication"),
        ("ApplyProcessingRestriction / ApplyDeletionDirective", "ProcessingRestrictionApplied", "InvalidateOutcomeObservation"),
        ("FreezeProfilePublication", "ProfilePublicationFrozen", "CancelProfilePublicationSyncAction"),
    ]
    for source, event, consumer in required_seams:
        assert seam_exists(source, event, consumer), (
            f"G3 cross-aggregate seam missing: {source} -> {event} -> {consumer}"
        )
    for forbidden in [
        "PreregisterFeedbackStudy | FeedbackStudy | FeedbackStudyPreregistered | OpenAnalysisCohortSnapshot",
        "AppendProfileCandidateRevision",
        "PublishApprovedProfileRevision",
        "ProfileCandidateRevisionDrafted",
        "ProfileVersionPublished",
    ]:
        assert forbidden not in domain, f"stale G3 lifecycle remains: {forbidden}"
    passed("ApplicationCase stays six stages and G3 seams are closed", len(required_seams))

    invariant_section = domain.split("## 15. 跨对象不变量", 1)[1].split("## 16.", 1)[0]
    domain_invariants = re.findall(
        r"^\d+\. (INV-G3-[A-Z0-9-]+)：", invariant_section, re.MULTILINE
    )
    prd_invariant_section = prd.split("## 11. 稳定不变量", 1)[1].split("## 12.", 1)[0]
    prd_invariants = re.findall(
        r"^- (INV-G3-[A-Z0-9-]+)$", prd_invariant_section, re.MULTILINE
    )
    assert len(domain_invariants) == len(set(domain_invariants)), "duplicate G3 domain invariant"
    assert len(prd_invariants) == len(set(prd_invariants)), "duplicate G3 PRD invariant"
    assert domain_invariants == prd_invariants, "PRD and domain G3 invariant lists must match exactly"
    assert len(domain_invariants) == 44, "G3 invariant baseline must contain exactly 44 IDs"
    for required in [
        "INV-G3-CANONICAL-OUTCOME-UNIQUENESS",
        "INV-G3-REFERENCE-SCOPE",
        "INV-G3-DRAFT-ONLY-EXCLUDE",
        "INV-G3-RUN-STARTS-RUNNING",
        "INV-G3-NO-HOLDOUT-CANDIDATE-TUNING",
        "INV-G3-RELEASE-GATE-CURRENT",
        "INV-G3-PUBLICATION-TWO-PHASE",
        "INV-G3-FULL-CASCADE-INVALIDATION",
        "INV-G3-CONTROL-LINEAGE",
        "INV-G3-EXPOSURE-LEDGER",
        "INV-G3-PUBLICATION-SAFETY-EPOCH",
        "INV-G3-AUTHORITY-SEPARATION",
        "INV-G3-RECONCILIATION-BEFORE-LABEL",
        "INV-G3-UNKNOWN-IMPACT-GLOBAL-FENCE",
    ]:
        assert required in domain_invariants, f"required G3 invariant missing: {required}"
    passed("stable G3 invariants agree across PRD and domain", len(domain_invariants))

    def command_text(name: str) -> str:
        return " | ".join(command_rows[name])

    def require_command_tokens(name: str, tokens: list[str]) -> None:
        text_value = command_text(name)
        for token in tokens:
            assert token in text_value, f"{name} missing semantic gate: {token}"

    command_gate = domain.split("## 11. 通用命令门", 1)[1].split("## 12.", 1)[0]
    for token in [
        "Case-bound G1/G2 门",
        "G3 分析/治理门",
        "SEALED AnalysisCohortSnapshot",
        "历史 CLOSED Case 只可",
        "CONTROL_PLANE",
        "普通 Service 均不能替代",
    ]:
        assert token in command_gate, f"split command gate missing: {token}"

    require_command_tokens(
        "RecordOutcomeSourceAssertion",
        ["OutcomeReconciliationKey", "canonical pointer 不变", "来源业务键/修订"],
    )
    require_command_tokens(
        "ReconcileOutcomeObservation",
        ["source_set_hash", "不含来源", "不得按最新到达或多数投票"],
    )
    exclude_text = command_text("ExcludeOutcomeLabel")
    assert "DRAFT→EXCLUDED" in exclude_text and "DRAFT/VERIFIED" not in exclude_text
    require_command_tokens(
        "CreateProfileCandidateRevision",
        ["SEALED Cohort", "discovery/train/dev", "confirmatory holdout", "opaque ref", "access ledger 为空", "content hash 冻结"],
    )
    require_command_tokens(
        "PreregisterFeedbackStudy",
        ["FROZEN candidate", "holdout 从未打开", "CausalDesignManifest", "ASSOCIATIONAL"],
    )
    require_command_tokens(
        "OpenConfirmatoryHoldout",
        ["首次且仅一次", "access receipt", "禁止改变 Candidate"],
    )
    start_run = command_text("StartAgentRun")
    assert "创建 AgentRun" in start_run and "初态即 RUNNING" in start_run
    require_command_tokens(
        "MarkProfileProposalReleaseEligible",
        ["D0–D4", "全 PASS", "未过期", "无 veto", "ProfileReleaseEligibilitySnapshot"],
    )
    require_command_tokens(
        "RecordProfileReleaseGateAssessment",
        ["PASS/FAIL/INCONCLUSIVE/VETO", "expires_at", "确定性投影为 EXPIRED"],
    )
    require_command_tokens(
        "RecordProfileProposalApproval",
        ["现场重验 D0–D4", "两个不同", "human_actor_id", "一人兼双角色不能满足 quorum"],
    )
    require_command_tokens(
        "AuthorizeProfilePublication",
        ["HUMAN", "双人 quorum", "D0–D4", "Agent/Service/CONTROL_PLANE 不得代签"],
    )
    require_command_tokens(
        "PrepareProfilePublication",
        ["CONTROL_PLANE", "PENDING_SYNC", "current pointer 不变", "safety_epoch"],
    )
    require_command_tokens(
        "CommitProfilePublication",
        ["CONTROL_PLANE", "required receipts", "current pointer", "safety_epoch"],
    )
    require_command_tokens(
        "FreezeProfilePublication",
        ["FROZEN", "提升 safety_epoch", "CANCEL 当前 PENDING_SYNC", "cancellation token"],
    )
    require_command_tokens(
        "RollbackProfilePublication",
        ["FROZEN→ACTIVE", "CONTROL_PLANE", "HUMAN rollback authorization", "恢复 A0"],
    )
    require_command_tokens(
        "AssignProfileExposure",
        ["CausalDesignManifest", "稳定 allocation policy", "不按用户采纳自选"],
    )
    idempotency_section = domain.split("### 16.1 幂等键", 1)[1].split("### 16.2", 1)[0]
    for token in [
        "G3 canonical 解析",
        "G3 Candidate 冻结",
        "G3 首次打开 holdout",
        "G3 Gate Assessment",
        "G3 发布授权",
        "G3 Prepare 发布",
        "G3 Commit 发布",
        "G3 Freeze",
        "G3 回滚执行",
        "G3 暴露分配",
        "G3 血缘失效",
    ]:
        assert token in idempotency_section, f"G3 idempotency key missing: {token}"
    passed("G3 lifecycle and release gates are executable semantics", 13)

    prd_at_rows = {row[0]: " | ".join(row) for row in markdown_rows(prd) if re.fullmatch(r"AT-3\d{2}", row[0])}
    at_semantics = {
        "AT-303": ["Candidate", "ReleaseEligibility", "PENDING_SYNC", "ACTIVE", "Freeze"],
        "AT-304": ["SourceAssertion", "canonical revision", "不投票"],
        "AT-305": ["hired", "denominator", "ReleaseEligibility"],
        "AT-317": ["INCONCLUSIVE", "两位业务审批人", "ReleaseEligibility"],
        "AT-318": ["confirmatory holdout", "新 Candidate", "新 Study"],
        "AT-319": ["CausalDesignManifest", "actual exposure", "只能写关联"],
        "AT-320": ["D0–D4", "过期/FAIL/VETO", "双人"],
        "AT-321": ["同一人兼签", "Publication Authorization", "新 Candidate/Study"],
        "AT-322": ["PENDING_SYNC", "pointer 不变", "Commit"],
        "AT-323": ["safety_epoch", "迟到命令拒绝", "影响边界未知"],
        "AT-324": ["FROZEN→ACTIVE", "CONTROL_PLANE", "A0"],
        "AT-325": ["required sync receipt", "pointer 不变"],
    }
    for identifier, tokens in at_semantics.items():
        assert identifier in prd_at_rows, f"PRD AT row missing: {identifier}"
        for token in tokens:
            assert token in prd_at_rows[identifier], f"{identifier} missing dangerous-path token: {token}"
    passed("high-risk G3 AT semantics are pinned", len(at_semantics))

    for stale_reference in [
        "OutcomeObservationRecorded",
        "RecordOutcomeObservation",
        "ObservationKey /",
        "AppendProfileCandidateRevision",
        "PublishApprovedProfileRevision",
        "ProfileVersionPublished",
    ]:
        assert stale_reference not in matrix, f"matrix references stale domain symbol: {stale_reference}"

    for token in [
        "PENDING",
        "RIGHT_CENSORED",
        "UNKNOWN",
        "denominator",
        "as_of",
        "maturity_window",
        "confidence interval",
        "exposure history",
        "ProfileChangeProposal",
        "ProfileVersion",
        "A3",
    ]:
        assert token in prd or token in domain, f"G3 lifecycle/quality token missing: {token}"
    assert "画像调权、排名、淘汰、发布、回滚与招聘决定永久禁止" in prd
    assert "两个不同 HUMAN 主体" in prd and "同一人兼任双角色不能满足 quorum" in domain
    assert "One primary action" in design and "Quiet by default" in design
    assert "模型不是业务状态机" in design and "ActionExecution" in design
    for token in [
        "Agent harness 的工程隐喻",
        "不是产品名、视觉品牌或 UI 风格",
        "不授予 checkpoint 保留或恢复正文的权力",
        "当前等待对象、下次检查时间和最晚升级时间",
        "提交你的决定",
        "发布授权人（Publication Authorizer）",
        "批准不等于授权，授权不等于发布准备，发布准备不等于生效",
        "发布记录已创建，等待同步",
        "已生效（仅未来招聘）",
    ]:
        assert token in design, f"Hermes/UI design boundary missing: {token}"
    for token in [
        "业务端主导航固定控制在六项以内",
        "角色 × 可见 × CTA × 禁止动作",
        "发布授权人（Publication Authorizer）",
        "Agent、提案、发布三类状态",
        "G3 必须可点击的八个危险分支",
        "提交你的决定",
        "批准不等于授权，授权不等于发布准备，发布准备不等于生效",
        "发布记录已创建等待同步",
    ]:
        assert token in claude_task, f"Claude task semantic missing: {token}"
    danger_section = claude_task.split("### G3 必须可点击的八个危险分支", 1)[1].split("## 9.", 1)[0]
    assert len(re.findall(r"^\d+\. \*\*", danger_section, re.MULTILINE)) == 8
    for token in ["## Must Read", "## Product Reference", "## Audit Only"]:
        assert token in package_manifest, f"package reading priority missing: {token}"
    passed("G3 quality, autonomy and Hermes-style UI boundaries are explicit", 26)

    linked_files = [
        PRD,
        MATRIX,
        DOMAIN,
        DESIGN,
        CLAUDE_TASK,
        PACKAGE_MANIFEST,
        TOTAL_PLAN,
        BOARD,
        GATE,
        README,
        VALIDATION,
    ]
    link_count = sum(check_links(path) for path in linked_files)
    passed("local Markdown links resolve", link_count)

    for text, name in [(prd, "PRD"), (board, "board"), (gate, "gate"), (readme, "README")]:
        assert "No-go" in text, f"{name} must preserve No-go"
    assert "G3 结果回流与画像治理 PRD" in total_plan
    assert "G3 结果回流与画像治理" in board
    assert "E-018" in gate
    assert "60 FR/30 AT" in board and "60 FR/30 AT" in gate
    assert "44 个稳定不变量" in board and "44 个稳定不变量" in gate
    assert "IMPLEMENTED/VERIFIED/RELEASED=0" in board
    gate_rows = {row[0]: row for row in markdown_rows(gate) if re.fullmatch(r"E-\d{3}", row[0])}
    for index in range(19, 31):
        identifier = f"E-{index:03d}"
        assert identifier in gate_rows, f"missing G3 evidence slot: {identifier}"
        assert gate_rows[identifier][2:6] == ["—", "—", "—", "—"], (
            f"unearned G3 evidence must remain blank: {identifier}"
        )
    for role in [
        "Hiring Owner",
        "HRBP/Profile Governance",
        "Publication Authorizer",
        "Data Steward",
        "Privacy/Fairness",
        "Analyst",
        "招聘运营",
    ]:
        assert role in " | ".join(gate_rows["E-026"]), f"E-026 missing usability role: {role}"
    passed("portfolio, Gate and zero-implementation boundary are synchronized", 19)

    expected_hash = manifest_sha256(MANIFEST_INPUTS)
    assert f"权威输入 SHA-256：{expected_hash}" in validation, "validation input hash is stale"
    assert "## 已证明" in validation and "## 未证明" in validation
    for limitation in [
        "真实结果数据合法",
        "统计有效性",
        "公平",
        "工程实现",
        "Hermes runtime",
        "真人采用",
        "A0/A1/A2",
        "画像发布",
        "发布",
    ]:
        assert limitation in validation, f"validation limitation missing: {limitation}"
    passed("validation record is current and bounded", expected_hash[:12])

    print(
        "NOTE | document lint only; lawful data, implementation, statistical/fairness "
        "validity, users, autonomy evidence, profile publication and release remain absent"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAIL | {exc}", file=sys.stderr)
        raise SystemExit(1)
