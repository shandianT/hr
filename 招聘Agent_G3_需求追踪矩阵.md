# 招聘 Agent G3 需求追踪矩阵

> 版本：v0.1
> 日期：2026-08-10
> 基线：[G3 结果回流与画像治理 PRD](./招聘Agent_G3_结果回流与画像治理_PRD.md)
> 口径：SPEC 只表示产品模块、命令/事件、目标测试与证据槽已对应；当前没有真实数据批准、实现、真人验收、A0/A1/A2 或画像发布证据。

## 1. 状态规则

| 状态 | 含义 |
|---|---|
| UNMAPPED | 尚未绑定产品模块、命令/事件或测试 |
| SPEC | 产品行为、危险场景和目标证据槽齐全 |
| IMPLEMENTED | 实现与行为/契约测试通过，尚未完成真实环境和真人验证 |
| VERIFIED | 数据目的、目标环境、真人任务、公平/权利/故障演练和 Owner 验收齐全 |
| RELEASED | 对应动作通过 D0–D4 与 A0/A1/A2 放权、监控和回滚门 |

证据 ID 是未来实现、评测、试点和治理产生的占位符，不是现有证据。

## 2. FR-301..360

| ID | 产品要求（压缩表述） | 产品模块 / 关键命令或事件 | 目标测试 | 证据槽 | 当前 |
|---|---|---|---|---|---|
| FR-301 | 批准来源只形成不可变 SourceAssertion，不直接成为 canonical | 结果对账箱 / RecordOutcomeSourceAssertion | G3-OBS-301：来源授权与断言隔离 | EV-G3-FR301 | SPEC |
| FR-302 | 各结果阶段独立观察 | Outcome Taxonomy / OutcomeSourceAssertionRecorded / OutcomeObservationReconciled | G3-OBS-302：阶段不可折叠 | EV-G3-FR302 | SPEC |
| FR-303 | 最终决定只引用 ApplicationCase HUMAN 事实 | Decision seam / FinalHiringDecisionRecorded | G3-OBS-303：决定所有权 | EV-G3-FR303 | SPEC |
| FR-304 | CLOSED/沉默/缺失不推断结果 | Observation Gate | G3-OBS-304：关闭原因非标签 | EV-G3-FR304 | SPEC |
| FR-305 | 观察幂等、纠正追加修订且唯一 current canonical | OutcomeObservation / CorrectOutcomeObservation | G3-OBS-305：重放/同键异载/canonical 修订 | EV-G3-FR305 | SPEC |
| FR-306 | 观察钉住租户/岗/周期/受控雇佣关联/实际暴露版本 | OutcomeReconciliationKey / EmploymentLinkageRef / exposure history | G3-OBS-306：身份歧义/作用域/暴露 | EV-G3-FR306 | SPEC |
| FR-307 | 多源只按 current policy/Steward 解析 canonical | ReconcileOutcomeObservation / ConfirmOutcomeObservation / DisputeOutcomeObservation | G3-OBS-307：冲突不投票/取最新 | EV-G3-FR307 | SPEC |
| FR-308 | 生命周期与成熟度正交 | OutcomeLabel State | G3-OBS-308：PENDING/UNKNOWN/CENSORED | EV-G3-FR308 | SPEC |
| FR-309 | 决定 supersede/纠正/删除/用途变化全链失效 | InvalidateOutcomeObservation / lineage invalidator | G3-OBS-309：候选至发布全链召回 | EV-G3-FR309 | SPEC |
| FR-310 | 只按版本化策略派生 Label | DeriveOutcomeLabelDraft | G3-LABEL-310：策略钉住 | EV-G3-FR310 | SPEC |
| FR-311 | 历史决定不是能力真值 | Outcome Label Gate | G3-LABEL-311：选择事实隔离 | EV-G3-FR311 | SPEC |
| FR-312 | 任职后信号需额外目的批准 | Post-hire Data Gate | G3-LABEL-312：未批准目的阻断 | EV-G3-FR312 | SPEC |
| FR-313 | 学习字段白名单与代理门 | Feature Policy | G3-LABEL-313：新字段默认拒绝 | EV-G3-FR313 | SPEC |
| FR-314 | 录制/辅助/权利等选择影响为零 | Excluded Signal Gate | G3-LABEL-314：禁用信号全路径 | EV-G3-FR314 | SPEC |
| FR-315 | 未成熟/缺失/删失不作负例 | Verify/ExcludeOutcomeLabel | G3-LABEL-315：成熟窗口矩阵 | EV-G3-FR315 | SPEC |
| FR-316 | Cohort 披露完整分母与选择机制 | 队列健康台 | G3-COHORT-316：幸存者样本阻断 | EV-G3-FR316 | SPEC |
| FR-317 | Snapshot 不可变且钉住完整分区/holdout 未打开状态 | SealAnalysisCohortSnapshot | G3-COHORT-317：封存与分区访问 | EV-G3-FR317 | SPEC |
| FR-318 | 人与时间切分阻断泄漏 | Feature/Partition Manifest | G3-COHORT-318：实体/时间泄漏 | EV-G3-FR318 | SPEC |
| FR-319 | 岗位隔离且禁止跨租户学习 | Cohort Scope Gate | G3-COHORT-319：合池与租户隔离 | EV-G3-FR319 | SPEC |
| FR-320 | 保护属性只在隔离公平域 | Fairness Audit Boundary | G3-COHORT-320：业务链零暴露 | EV-G3-FR320 | SPEC |
| FR-321 | SEALED Cohort/FROZEN candidate/预注册后首次开 holdout 并可重放 Run | OpenConfirmatoryHoldout / StartAgentRun | G3-EVAL-321：前置顺序/首次访问/重放 | EV-G3-FR321 | SPEC |
| FR-322 | candidate hash 冻结且 holdout untouched 后预注册 | CreateProfileCandidateRevision / PreregisterFeedbackStudy | G3-EVAL-322：候选先冻结/口径冻结 | EV-G3-FR322 | SPEC |
| FR-323 | 因果主张需 current CausalDesignManifest | Claim Type Gate / CausalDesignManifest | G3-EVAL-323：无设计只允许关联 | EV-G3-FR323 | SPEC |
| FR-324 | 小样本/宽区间/选择性标签不产生 ReleaseEligibility | Release Gate Assessment | G3-EVAL-324：INCONCLUSIVE 不可人工覆盖 | EV-G3-FR324 | SPEC |
| FR-325 | candidate 仅在 untouched holdout 确认且同 holdout 禁止调参 | CandidateGenerationManifest / holdout access receipt | G3-EVAL-325：同集生成验证硬阻断 | EV-G3-FR325 | SPEC |
| FR-326 | 重要 slice 伤害不能被平均掩盖 | Fairness Guardrail | G3-EVAL-326：最差 slice 门 | EV-G3-FR326 | SPEC |
| FR-327 | 报告披露 label health/n/CI/反证/限制 | FeedbackStudyAnalysisReady | G3-EVAL-327：报告完整性 | EV-G3-FR327 | SPEC |
| FR-328 | SEALED Cohort 后 Candidate 仅用 discovery/train/dev 形成并冻结 | CreateProfileCandidateRevision | G3-PROP-328：generation manifest/base/delta/hash | EV-G3-FR328 | SPEC |
| FR-329 | Proposal 从 Gate 到审阅/批准/授权且有修改/拒绝/失效生命周期 | OpenProfileChangeProposal / StageFeedbackStudyEvidence | G3-PROP-329：提案非候选/画像/指针 | EV-G3-FR329 | SPEC |
| FR-330 | 任一 causal input 变化同步失效至授权/pending/active | InvalidateFeedbackStudy / InvalidateProfileChangeProposal | G3-PROP-330：全链失效与读取门 | EV-G3-FR330 | SPEC |
| FR-331 | Agent 仅用 train/dev 生成候选并执行预注册评测 | Profile Governance Agent | G3-PROP-331：无 canonical/holdout 调参/批准权 | EV-G3-FR331 | SPEC |
| FR-332 | 每个 Proposal 一个当前权威任务且失效/修改即撤回 | OpenProfileChangeReviewTask | G3-REVIEW-332：任务唯一性/旧任务只读 | EV-G3-FR332 | SPEC |
| FR-333 | 首屏展示 Diff/依据/风险/Release Gate/范围/回滚 | 画像审阅台 | G3-REVIEW-333：30 秒理解门与后果 | EV-G3-FR333 | SPEC |
| FR-334 | 细节渐进披露且数据最小化 | Evidence/Audit Drawer | G3-REVIEW-334：最小披露 | EV-G3-FR334 | SPEC |
| FR-335 | 批准/要求修改/拒绝中性且修改撤回旧资格/批准 | RequestProfileProposalRevision / RejectProfileChangeProposal | G3-REVIEW-335：无诱导/新 Candidate+Study | EV-G3-FR335 | SPEC |
| FR-336 | current/expiry D0–D4 全 PASS 才 RELEASE_ELIGIBLE 且人不可覆盖 | RecordProfileReleaseGateAssessment / MarkProfileProposalReleaseEligible | G3-REVIEW-336：Gate 当前性/独立 Owner/veto | EV-G3-FR336 | SPEC |
| FR-337 | 两个不同 HUMAN 对同一 eligibility hash 批准 | RecordProfileProposalApproval | G3-REVIEW-337：职责分离/quorum/旧任务 | EV-G3-FR337 | SPEC |
| FR-338 | 双批准后另需当前 HUMAN Publication Authorization | AuthorizeProfilePublication / ProfilePublicationAuthorized | G3-PUB-338：批准与授权分离 | EV-G3-FR338 | SPEC |
| FR-339 | CONTROL_PLANE Prepare 创建 PENDING_SYNC 且不改 pointer | PrepareProfilePublication / ProfilePublicationPrepared | G3-PUB-339：两阶段 prepare | EV-G3-FR339 | SPEC |
| FR-340 | 关键回执完整后 CONTROL_PLANE Commit 原子更新唯一 pointer | AcceptProfilePublicationSyncReceipt / CommitProfilePublication | G3-PUB-340：关键回执/原子 commit/并发 | EV-G3-FR340 | SPEC |
| FR-341 | 新版本只影响未来周期 | PublicationScope | G3-PUB-341：在途 pin 保持 | EV-G3-FR341 | SPEC |
| FR-342 | 关键同步缺失保持 PENDING_SYNC 与旧 pointer | Publication Reconciliation / ProfilePublicationSyncReceiptAccepted | G3-PUB-342：required receipt/部分成功/恢复 | EV-G3-FR342 | SPEC |
| FR-343 | 画像生效/排名/淘汰/回滚无 A3 | Autonomy Policy | G3-SAFE-343：永久红色动作 | EV-G3-FR343 | SPEC |
| FR-344 | CausalDesign 下记录稳定 assignment 与真实 exposure 全分母 | ProfileExposureLedger / AssignProfileExposure | G3-SAFE-344：分配/暴露/污染/不依从 | EV-G3-FR344 | SPEC |
| FR-345 | P0 Freeze 提升 safety_epoch；影响未知则逐 RoleProfile tenant 全域 fence | FreezeProfilePublication | G3-SAFE-345：发布竞态/未知影响定界 | EV-G3-FR345 | SPEC |
| FR-346 | Freeze 仍允许权利与安全补偿 | Safety Compensation Gate | G3-SAFE-346：冻结下删除 | EV-G3-FR346 | SPEC |
| FR-347 | HUMAN 授权 FROZEN 回滚至此前批准/仍允许版本 | AuthorizeProfileRollback | G3-SAFE-347：授权/目标/epoch/A0 计划 | EV-G3-FR347 | SPEC |
| FR-348 | CONTROL_PLANE 原子回滚新建修订并使 FROZEN→ACTIVE/A0 | RollbackProfilePublication | G3-SAFE-348：当前 epoch/不重写历史 | EV-G3-FR348 | SPEC |
| FR-349 | 回滚恢复 ACTIVE 仍只回 A0 再逐动作取证 | Recovery Gate | G3-SAFE-349：状态恢复不等于放权恢复 | EV-G3-FR349 | SPEC |
| FR-350 | 批准来源自动启动 canonical→candidate→Study→Proposal | G3 Orchestrator | G3-HARNESS-350：零 HR 点火/异常唯一 | EV-G3-FR350 | SPEC |
| FR-351 | Activity Rail 分离调度/Agent/Proposal/Publication 状态族 | Agent Activity Rail / domain projections | G3-HARNESS-351：Run 创建即 RUNNING/分析不冒充发布 | EV-G3-FR351 | SPEC |
| FR-352 | 可见原因/版本/holdout 状态/下一步/Owner/恢复点 | Activity Rail / ExceptionBundle | G3-HARNESS-352：可观察接管/最小披露 | EV-G3-FR352 | SPEC |
| FR-353 | typed tool/最小权限/策略门/预算 | Deterministic Harness | G3-HARNESS-353：模型无业务写权 | EV-G3-FR353 | SPEC |
| FR-354 | trace/checkpoint/receipt/retry/compensation | RunCheckpoint | G3-HARNESS-354：恢复凭证 | EV-G3-FR354 | SPEC |
| FR-355 | Gate 过期/待批准/待授权/PENDING_SYNC 等诚实呈现 | Reconciliation Panel | G3-UX-355：请求/Prepare 不冒充事实 | EV-G3-FR355 | SPEC |
| FR-356 | 一页一个当前职责决定，批准与授权分任务 | Decision Card | G3-UX-356：中性 One primary action | EV-G3-FR356 | SPEC |
| FR-357 | 克制企业视觉而非 AI 炫技 | Design System | G3-UX-357：视觉回归 | EV-G3-FR357 | SPEC |
| FR-358 | 无障碍/缩放/语言/时区可用 | Accessibility Gate | G3-UX-358：WCAG 目标路径 | EV-G3-FR358 | SPEC |
| FR-359 | canonical 至 exposure/rollback 全链动作可追责 | Audit Timeline | G3-GOV-359：actor/version/epoch/pointer/receipt | EV-G3-FR359 | SPEC |
| FR-360 | 每次处理/批准/授权/发布阶段前重验目的/控制/租户 | Processing Preflight | G3-GOV-360：同步读取门/越界 P0 | EV-G3-FR360 | SPEC |

## 3. AT-301..330

| ID | 场景与预期 | 主要覆盖 FR | 目标自动化层 | 证据槽 | 当前 |
|---|---|---|---|---|---|
| AT-301 | 多阶段折叠或 SourceAssertion 直升 canonical 时硬拒绝 | FR-301 FR-302 FR-303 | Schema + domain | EV-G3-AT301 | SPEC |
| AT-302 | 未成熟/删失保持未知，不作负例 | FR-304 FR-308 FR-315 | Domain + property | EV-G3-AT302 | SPEC |
| AT-303 | 决定 supersede/纠正/删除从 Candidate 至 ACTIVE 全链失效 | FR-305 FR-309 FR-330 FR-345 FR-359 | Event + sync read gate + freeze | EV-G3-AT303 | SPEC |
| AT-304 | 多源/雇佣关联冲突不自动合并投票且 canonical 唯一 | FR-306 FR-307 FR-308 | Identity + domain + concurrency | EV-G3-AT304 | SPEC |
| AT-305 | hired-only 使 D1 失败；无因果设计还使 D3 失败，不得外推/发布 | FR-311 FR-316 FR-324 FR-336 | Cohort + claim + release gate | EV-G3-AT305 | SPEC |
| AT-306 | 历史决定不能成为能力真值 | FR-303 FR-310 FR-311 | Policy red-team | EV-G3-AT306 | SPEC |
| AT-307 | 决策后字段触发时间泄漏阻断 | FR-317 FR-318 | Dataset lint | EV-G3-AT307 | SPEC |
| AT-308 | 同 Person 跨岗进入 train/test 被阻断 | FR-318 FR-319 | Dataset lint | EV-G3-AT308 | SPEC |
| AT-309 | 不可比岗位无证据不得合池 | FR-306 FR-319 | Cohort gate | EV-G3-AT309 | SPEC |
| AT-310 | 跨租户混用触发 safety_epoch Freeze 并取消 pending | FR-319 FR-345 FR-360 | Security + concurrency red-team | EV-G3-AT310 | SPEC |
| AT-311 | 保护属性进入业务链触发 P0 | FR-313 FR-320 | Privacy/fairness | EV-G3-AT311 | SPEC |
| AT-312 | 代理替换敏感使 D2 FAIL，双批准也不能覆盖 | FR-313 FR-320 FR-326 FR-336 | Counterfactual + release gate | EV-G3-AT312 | SPEC |
| AT-313 | 录制/无录制选择影响学习为零 | FR-314 FR-320 | Excluded-signal test | EV-G3-AT313 | SPEC |
| AT-314 | 辅助/权利/申诉信号硬隔离 | FR-312 FR-314 FR-360 | Purpose red-team | EV-G3-AT314 | SPEC |
| AT-315 | 删除命中 Candidate/Gate/授权/pending/产物并全链回执 | FR-309 FR-317 FR-330 FR-346 FR-359 | Lineage + deletion + freeze | EV-G3-AT315 | SPEC |
| AT-316 | 目的/供应商训练越界被拒绝 | FR-312 FR-313 FR-360 | Processing preflight | EV-G3-AT316 | SPEC |
| AT-317 | INCONCLUSIVE/宽 CI 即使双人点击也无 ReleaseEligibility | FR-324 FR-327 FR-336 FR-337 | Statistical + release gate | EV-G3-AT317 | SPEC |
| AT-318 | 同一 holdout 生成/调参/验证或偷看后复用被硬阻断 | FR-317 FR-321 FR-322 FR-325 FR-328 | Candidate manifest + holdout access + protocol | EV-G3-AT318 | SPEC |
| AT-319 | 无 CausalDesign/稳定 assignment/actual exposure 的伪因果被拒绝 | FR-316 FR-323 FR-327 FR-344 | Claim lint + exposure ledger | EV-G3-AT319 | SPEC |
| AT-320 | slice 退化或 Gate 过期/FAIL/VETO 即使双批准也不放行 | FR-326 FR-327 FR-336 FR-337 | Fairness + current release gate | EV-G3-AT320 | SPEC |
| AT-321 | Proposal 修改/拒绝、越权/同人兼签/旧任务均不能批准授权发布 | FR-328 FR-329 FR-331 FR-332 FR-335 FR-337 FR-338 FR-343 | Lifecycle + auth + separation + idempotency | EV-G3-AT321 | SPEC |
| AT-322 | 双批准+独立授权后 Prepare，关键回执齐才 Commit future pointer | FR-338 FR-339 FR-340 FR-341 FR-342 FR-344 FR-355 | Two-phase publication + exposure projection | EV-G3-AT322 | SPEC |
| AT-323 | Freeze 竞态/未知影响由新 epoch 与逐 RoleProfile tenant fence 收敛 | FR-340 FR-343 FR-345 FR-355 | Concurrency + safety + impact boundary | EV-G3-AT323 | SPEC |
| AT-324 | HUMAN 绑定 frozen epoch 授权 CONTROL_PLANE 原子回滚 FROZEN→ACTIVE/A0 | FR-347 FR-348 FR-349 FR-359 | Auth + domain + audit | EV-G3-AT324 | SPEC |
| AT-325 | 缺授权/trace/safety_epoch/关键回执/recovery 时 pointer 不变 | FR-338 FR-339 FR-340 FR-342 FR-353 FR-354 FR-359 | Harness + publication preflight | EV-G3-AT325 | SPEC |
| AT-326 | 自动启动后工具故障/重放从 checkpoint 恢复且状态族分离 | FR-321 FR-350 FR-351 FR-352 FR-354 | Orchestration + fault injection | EV-G3-AT326 | SPEC |
| AT-327 | Freeze 下删除/限制/纠正仍执行 | FR-346 FR-360 | Safety compensation | EV-G3-AT327 | SPEC |
| AT-328 | 七角色权限/状态/原因/恢复任务关键误解为零 | FR-333 FR-334 FR-335 FR-336 FR-337 FR-338 FR-351 FR-352 FR-355 FR-356 | Role-based usability study | EV-G3-AT328 | SPEC |
| AT-329 | 键盘/读屏/缩放/非颜色/时区语言走通 | FR-357 FR-358 | Accessibility | EV-G3-AT329 | SPEC |
| AT-330 | 视觉通过但任务理解/恢复失败仍 No-go | FR-355 FR-356 FR-357 FR-358 FR-359 | Usability + visual | EV-G3-AT330 | SPEC |

## 4. 稳定不变量覆盖

以下 `INV-G3-*` 必须与 PRD、领域规格完全一致且唯一；FR/AT 的目标测试和横向 Gate 共同验证它们，不因单项审批、视觉走查或文档 lint 被覆盖：

- INV-G3-OUTCOME-NOT-GROUND-TRUTH
- INV-G3-DECISION-OWNERSHIP
- INV-G3-STAGE-LABEL-SEPARATION
- INV-G3-DELAYED-LABEL-NOT-NEGATIVE
- INV-G3-SELECTIVE-LABEL
- INV-G3-JOB-SCOPE
- INV-G3-CANONICAL-OUTCOME-UNIQUENESS
- INV-G3-CORRECTION-INVALIDATES-DERIVATIVES
- INV-G3-COHORT-DENOMINATOR
- INV-G3-FROZEN-SNAPSHOT
- INV-G3-NO-SURVIVOR-ONLY
- INV-G3-NO-TEMPORAL-LEAKAGE
- INV-G3-NO-IDENTITY-LEAKAGE
- INV-G3-NO-CROSS-TENANT-LEARNING
- INV-G3-PURPOSE-BOUND-LINEAGE
- INV-G3-PROTECTED-ATTR-AUDIT-ONLY
- INV-G3-SMALL-SAMPLE-NO-INFERENCE
- INV-G3-NO-CAUSAL-CLAIM-WITHOUT-DESIGN
- INV-G3-EVALUATION-NOT-APPROVAL
- INV-G3-PROPOSAL-NOT-PROFILE
- INV-G3-NO-AUTO-DRIFT
- INV-G3-HUMAN-PUBLICATION
- INV-G3-STALE-BASE-CANNOT-PUBLISH
- INV-G3-FUTURE-ONLY-PUBLISH
- INV-G3-PUBLISHED-IMMUTABLE
- INV-G3-NO-A3-PROFILE-MUTATION
- INV-G3-FREEZE-FIRST
- INV-G3-ROLLBACK-NOT-REWRITE
- INV-G3-ROLLBACK-TO-A0
- INV-G3-TRACEABLE-RECOVERY
- INV-G3-USABILITY-NOT-AESTHETICS
- INV-G3-REFERENCE-SCOPE
- INV-G3-DRAFT-ONLY-EXCLUDE
- INV-G3-RUN-STARTS-RUNNING
- INV-G3-NO-HOLDOUT-CANDIDATE-TUNING
- INV-G3-RELEASE-GATE-CURRENT
- INV-G3-PUBLICATION-TWO-PHASE
- INV-G3-FULL-CASCADE-INVALIDATION
- INV-G3-CONTROL-LINEAGE
- INV-G3-EXPOSURE-LEDGER
- INV-G3-PUBLICATION-SAFETY-EPOCH
- INV-G3-AUTHORITY-SEPARATION
- INV-G3-RECONCILIATION-BEFORE-LABEL
- INV-G3-UNKNOWN-IMPACT-GLOBAL-FENCE

## 5. 横向发布门

| Gate | 目标断言 | 目标证据槽 | 当前 |
|---|---|---|---|
| G3-X-DECISION-OWNERSHIP | G3 只引用 ApplicationCase HUMAN 决定 | EV-G3-X01 | SPEC |
| G3-X-LABEL-LIFECYCLE | SourceAssertion→唯一 canonical→Label，阶段、成熟/删失和冲突可纠正 | EV-G3-X02 | SPEC |
| G3-X-COHORT-INTEGRITY | 完整 denominator、选择机制、person/time/job split 与冻结分区 | EV-G3-X03 | SPEC |
| G3-X-PURPOSE-FAIRNESS | 租户/用途/权利/保护属性、D2 公平与代理门 | EV-G3-X04 | SPEC |
| G3-X-EVALUATION-INTEGRITY | SEALED→train/dev frozen candidate→预注册→untouched holdout、D1 泄漏外推、D2 CI/slice、D3 因果设计 | EV-G3-X05 | SPEC |
| G3-X-HUMAN-PUBLICATION | current ReleaseEligibility、双 HUMAN、独立授权、CONTROL_PLANE 两阶段、future-only、无 A3 | EV-G3-X06 | SPEC |
| G3-X-FREEZE-ROLLBACK | safety_epoch Freeze 优先、完整失效、权利补偿、HUMAN rollback FROZEN→ACTIVE/A0 | EV-G3-X07 | SPEC |
| G3-X-HARNESS-RECOVERY | typed tool、checkpoint、trace、replay、回执、补偿 | EV-G3-X08 | SPEC |
| G3-X-USABILITY-ACCESSIBILITY | 七角色权限、状态理解、恢复与 WCAG 目标 | EV-G3-X09 | SPEC |

## 6. 覆盖快照

| 类型 | 总数 | SPEC | IMPLEMENTED | VERIFIED | RELEASED |
|---|---:|---:|---:|---:|---:|
| FR | 60 | 60 | 0 | 0 | 0 |
| AT | 30 | 30 | 0 | 0 | 0 |
| 横向 Gate | 9 | 9 | 0 | 0 | 0 |

任何条目升为 IMPLEMENTED、VERIFIED 或 RELEASED 前必须填入可定位证据，并说明它证明什么、不证明什么。文档 lint 通过只能维持 SPEC，不能推导数据合法、模型有效、真人可用或画像可发布。
