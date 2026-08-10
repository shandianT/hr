# 招聘 Agent 领域与事件规格

版本：v0.6
日期：2026-08-10  
状态：Gate 0 评审稿  
适用范围：G1a 面后单轮闭环、G1b 多轮终面包、G2 从收件到有限托管、G3 结果回流与画像治理

相关材料：

- [领域语言](./CONTEXT.md)
- [G1a MVP PRD](./招聘Agent_G1_MVP_PRD.md)
- [ADR-0001：申请案件是业务主线](./docs/adr/0001-application-case-is-the-workflow-root.md)
- [ADR-0002：确定性控制面拥有外部动作](./docs/adr/0002-deterministic-control-plane-owns-actions.md)
- [G1a 工程开工包](./招聘Agent_G1a_工程开工包.md)
- [G1a 机器契约](./contracts/README.md)
- [G1b 多轮与终面评估包 PRD](./招聘Agent_G1b_终面评估包_PRD.md)
- [ADR-0005：终面评估包是不可变编译物](./docs/adr/0005-final-assessment-package-is-an-immutable-compilation.md)
- [ADR-0006：面前追问简报采用分阶段披露](./docs/adr/0006-interview-brief-uses-staged-disclosure.md)
- [G2 收件筛选约面 PRD](./招聘Agent_G2_收件筛选约面_PRD.md)
- [ADR-0007：时段提案不等于面试预定](./docs/adr/0007-scheduling-proposal-is-not-a-booking.md)
- [ADR-0008：录制告知不等于采集授权](./docs/adr/0008-recording-notice-is-not-consent.md)
- [G3 结果回流与画像治理 PRD](./招聘Agent_G3_结果回流与画像治理_PRD.md)
- [ADR-0009：结果观察不是真值](./docs/adr/0009-outcomes-do-not-auto-train-role-profiles.md)
- [Hermes 式 Agent 与 UI 设计原则](./docs/招聘Agent_Hermes式Agent与UI设计原则.md)

## 1. 建模结论

1. 申请案件的业务键是“租户 × 候选人 × 岗位需求 × 招聘周期”，不是邮件、手机号或会议。
2. 人或岗位尚未唯一解析的邮件先属于简历投递，不能创建缺少业务键的“半个案件”。
3. 案件顶层阶段只回答“招聘走到哪一大段”；约面、排期、面试和确认由当前轮次子状态表达。
4. 业务阶段、运行状态和暂停状态彼此正交；异常不是一个招聘阶段。
5. 面试轮次是一项目标明确的评价阶段；面试会话是一次实际会面。改期和技术重试通常不创建新轮次。
6. 评价材料和招聘决定是两个对象；模型只能产生前者的草稿。
7. 已确认评价、决定、画像、评分卡和流程版本不可原地覆盖。
8. G1 导入已结束面试必须使用受控命令，不能由后台任意跳状态。
9. 一个案件只有一个当前筛选输入清单和一个当前匹配材料指针；卡片与通知不拥有第二份当前材料。
10. 候选人选时只形成预约意图；InterviewSession 拥有当前有效预定，InterviewRound 的排期状态由全部必需会话推导。
11. 面试开始与采集开始分离；录制告知、参与人选择、采集闸门和平台实际采集是四类事实。
12. PAUSED/CLOSED 阻断生产性外部动作，但不能阻断停止采集、取消会议、撤销链接和删除资产等安全补偿。
13. 部门/最终决定作为 ApplicationCase 内不可变记录，轮次决定作为 InterviewRound 内不可变记录；纠正使用 supersede，不建立跨聚合双写的 DecisionRecord 真相源。
14. ApplicationKey 在开案后不可原地修改；已应用路由被纠正时，旧投递关系及其生产动作先失效，旧案件的关闭/保留与补偿范围获得明确裁决后，再打开或附加正确案件。
15. 处理控制必须绑定主体、案件/会话、目的与数据范围；候选人案件撤回、参与人采集选择和隐私权利请求不是一个全局开关。
16. 平台采集请求与平台已开始/已停止是不同事实；G1 证据交接也必须有当前指针、失效和替代生命周期。
17. 人工最终招聘决定继续由 ApplicationCase 拥有并发出权威事件；G3 只能引用，不能复制成第二份决定真相。
18. 结果观察、结果标注、分析队列、研究、画像候选修订、批准和发布是七类不同事实；任一前置完成都不自动推导后一层完成。
19. 任职后表现通常只对已录用者可见；完整分母、成熟期、缺失/删失、选择机制和时间切分未冻结前不得形成发布型画像提案。
20. Agent 只生成观察/标注草稿、固定协议评测和画像候选修订；招聘决定与批准/发布授权由拥有事实且有权限的人提交，画像 Prepare/Commit/回滚只由确定性 CONTROL_PLANE 消费当前 HUMAN 授权执行。

## 2. 分阶段领域范围

| 阶段 | 必须具备 | 本阶段不要求 |
|---|---|---|
| G1a | 申请案件、面试轮次、已结束会话导入、录音/转写、证据评价、面试官确认、人工轮次决定、轮次归档 | 邮件自动建案、约面、多轮终面包 |
| G1b | 多轮计划、轮次依赖、各轮评价串联、缺项/冲突、终面评估包 | 简历筛选与日历生产自动化 |
| G2 | 简历投递、身份/岗位路由、匹配评价、部门决策、候选人协调、日历、同意、催办与动作级 A0–A3 | 画像自动改权重、跨岗位自动学习 |
| G3 | 结果观察与纠正、标注成熟、分析队列、结果回流研究、画像候选修订、双人批准、独立发布授权、未来周期两阶段发布、冻结与回滚 | 自动调权、跨租户学习、把历史决定当真值、未批准的任职后数据处理 |

完整目标不变：G1a/G1b 建立可信材料引擎，G2 扩大无人推动的流程半径，G3 只在可解释、可纠正和可回滚的治理链中改善未来岗位标准。

## 3. 上下文边界

| 上下文 | 拥有的数据与决定 | 案件域如何使用 |
|---|---|---|
| 人员身份 | 候选人身份、合并/拆分、联系方式权属 | 只引用 CandidatePerson ID 和必要快照 |
| 岗位与标准 | 岗位需求、招聘周期、画像、评分卡、面试流程 | 在案件/轮次开始时钉住不可变版本 |
| 招聘案件 | 申请阶段、轮次、评价、决定、动作和异常 | 本规格的核心 |
| 隐私与权利 | 告知、同意、撤回、限制、删除和保留例外 | 在处理时读取有效凭证/控制事实 |
| 证据资产 | 简历、录音、逐字稿、屏幕材料 | 案件域保存受控引用、版本和哈希 |
| 连接器 | 邮箱、IM、日历、会议、ATS 的外部资源 | 通过动作执行与回执交互 |
| 结果登记 | Offer、入职、留任、任职表现的权威来源、观察修订和纠正 | 只消费批准来源与当前版本，不反向拥有招聘决定 |
| 画像治理 | 队列、研究、候选修订、审批、发布、冻结和回滚 | 通过事件引用案件、结果、画像和控制事实，不同步双写 |

## 4. 聚合根

| 聚合根 | 阶段 | 核心职责 | 强一致边界 |
|---|---|---|---|
| ResumeSubmission | G2 | 保存来源投递、附件引用、内容指纹、结构化简历版本和当前路由解析 | 同一来源附件只接受一次；只有当前 ROUTED 解析可用于开案 |
| ApplicationCase | G1/G2 | 保存 ApplicationKey、案件阶段、当前筛选输入/匹配材料指针、部门/最终决定、计划钉住和关闭事实 | 唯一有权改变案件顶层阶段 |
| MatchAssessment | G2 | 保存指定筛选输入下的不可变逐项证据和匹配材料 | 低分不能直接产生淘汰；是否为当前材料由 ApplicationCase 指针决定 |
| InterviewRound | G1/G2 | 管理一轮评价目标、必需会话、评分卡、确认策略和人工决定 | 是否已排期/完成必须聚合全部必需会话，单会话回调不能直接提交轮次 |
| InterviewSession | G1/G2 | 管理一次实际会面、协调请求、时段提案、预约修订、当前预定、参与人、采集模式、当前证据交接和产物 | 唯一有权提交或失效本会话的预定、采集与交接事实 |
| InterviewBrief | G1b/G2 | 保存下一轮证据缺口、建议问题、披露策略、受众与反馈版本 | 每个 Round/受众修订只有一个当前可分发版本；输入变化即失效 |
| EvaluationPackage | G1/G2 | 保存证据集合、逐维评价草稿、人工修改和确认 | 确认只对同一评价版本有效 |
| CrossRoundIssue | G1b/G2 | 保存跨轮问题候选、双方依据、严重度、阻断性和解决记录 | 同一 causal input/问题键只有一个活动问题；Agent 不拥有最终分类权 |
| FinalAssessmentPackage | G1b/G2 | 钉住各轮评价/决定版本，保存缺项、冲突和总体摘要 | 输入失效时必须立即失效 |
| ConsentReceipt | 隐私/G2 | 保存一位参与人对特定会话、目的和告知版本的采集选择与撤回修订 | 不由 Invitation、Presence 或其他参与人的选择推导 |
| ProcessingControl | 隐私/G2 | 按 data_subject_ref + case/session/purpose/operation/data_scope 保存限制处理、删除与保留例外的当前控制修订 | 只在声明范围内优先阻断普通编排和动作；不得误伤其他案件或主体 |
| ActionExecution | G1/G2 | 保存外部动作授权、幂等键、尝试和连接器回执 | 保障业务效果只发生一次 |
| ExceptionBundle | G1/G2 | 保存事实、风险、尝试、选项、责任人、时限和恢复凭证 | 同一原因/资源版本只有一个活动异常 |
| OutcomeObservation | G3 | 按 OutcomeReconciliationKey 保存多来源 SourceAssertion、不可变解析修订及当前确认/争议/失效指针 | 同一主体/岗位/阶段/窗口/用途恰有一个当前 canonical revision；权威招聘决定只引用不复制 |
| OutcomeLabel | G3 | 保存标注策略、成熟度、观察依据、验证/排除和当前修订 | 只有当前允许且满足成熟规则的观察可形成可用标注 |
| AnalysisCohortSnapshot | G3 | 保存完整分母、成员、纳排、as_of、成熟/缺失/删失、分区与血缘 | SEALED 后不可增删或换标注；变化只能失效并建新快照 |
| FeedbackStudy | G3 | 保存预注册假设、基线/候选、队列、指标门、报告、限制与当前性 | 开始后不得事后改变假设、分区或主要指标 |
| AgentRun | G3 | 保存输入清单、有限步骤、checkpoint、工具回执、人审交接和恢复凭证 | 工具/模型成功只产生候选产物，不提交招聘或画像事实 |
| ProfileCandidateRevision | G3 | 保存基于当前 ProfileVersion、仅用 discovery/train/dev 输入形成的不可变 ProfileDelta 与生成清单 | candidate hash 在首次打开 confirmatory holdout 前冻结；任何修改创建新 revision 与新 Study |
| ProfileChangeProposal | G3 | 引用候选修订和研究证据，保存 D0–D4 Release Gate、权威审阅任务、拒绝/修改与双人批准 | 批准只绑定同一 candidate/study/gate/scope hash；不拥有当前画像指针 |
| RoleProfile | G3 | 保存不可变 ProfileVersion、PublicationRevision、待同步发布、required receipt 引用、当前发布指针、安全纪元、冻结与回滚记录 | 唯一有权为声明的未来范围 Prepare/Commit、冻结或回滚画像指针；同一 role/scope 至多一个 PENDING_SYNC，Prepare 永不更新 current pointer |
| ProfileExposureLedger | G3/A2 | 保存一个 Study × ApplicationCase 的稳定分配、实际 ProfileVersion 暴露、偏离与污染修订 | 分配不由是否采纳 Proposal 推断；实际暴露与分配意图分离且不可静默重写 |

决定记录不是独立聚合根：部门和最终决定归 ApplicationCase，轮次决定归 InterviewRound。每条决定仍不可变、带 HUMAN actor 与权限快照；纠正通过 supersede 新记录完成，不能原地覆盖。

## 5. 核心值对象

| 值对象 | 内容 |
|---|---|
| ApplicationKey | tenant_id、person_id、requisition_id、recruitment_cycle_id |
| ActorRef | actor_type、actor_id、role、authority_snapshot_id |
| VersionPin | object_type、object_id、version、content_hash |
| EvidencePointer | source_type、source_id、source_version、locator、speaker_id、content_hash |
| ConsentSnapshot | participant_id、purposes、notice_version、decision、valid_at、receipt_ref |
| ActionPolicySnapshot | action_type、autonomy_level、limits、policy_version |
| IdempotencyKey | scope、business_key、revision |
| RuntimeReason | code、owner、wake_condition、deadline |
| DecisionBasis | material_id、version、supporting_refs |
| DataScope | tenant、department、requisition、allowed_fields |
| ResumeToken | target_aggregate、expected_version、intended_command、expires_at |
| RoundCompletionRecord | round_id/version、confirmed_evaluation_id/version、decision_id/version、evidence_set_hash、completed_at |
| FinalInputManifest | interview_plan_version、profile/scorecard pin、completion_record_refs、waiver_refs、evidence_hashes、manifest_hash |
| DisclosurePolicySnapshot | disclosure_phase、audience_refs、allowed/blocked fields、purpose、policy_version |
| CrossRoundIssueKey | issue_type、scorecard_dimension、causal_input_refs、causal_versions |
| TaskRevision | task_id、business_revision、audience_revision、displayed_package_version |
| ScreeningInputManifest | structured_resume_version、profile_version、allowed_field_policy、generation_policy、manifest_hash |
| SchedulingConstraintSnapshot | participants、roles、timezones、duration、windows、rooms、policy_version |
| AvailabilitySnapshotRef | provider、subject_refs、observed_at、expires_at、snapshot_hash |
| BookingRequirementsSnapshot | calendar_event、meeting_resource、invitation_write、required_session_refs、policy_version |
| BookingReceiptSet | appointment_revision、action_refs、external_resource_revisions、receipt_hash |
| CapturePolicySnapshot | session、purposes、media_entry_participant_scope、notice_version、no_recording_route、policy_version |
| ProcessingControlSetSnapshot | control_refs/revisions、target case/session、purpose、operation、data categories、evaluated_at、snapshot_hash |
| ControlSnapshot | processing_control_set_hash、case_epoch、current_routing_revision、suspension、captured_at |
| GovernanceControlSnapshot | processing_control_set_hash、lineage_epoch、tenant/job/cycle/purpose scope、allowed field/retention policy versions、captured_at、snapshot_hash |
| HandoffInputManifest | case/round/session/appointment refs、capture_mode、evidence_route、consent/control refs、capture history/segment/final reconciliation refs、asset_or_notes refs、input_hash |
| ExternalResourceRevision | provider、resource_type、resource_id、revision_or_etag、observed_at |
| ActionCategory | PRODUCTION / SAFETY_COMPENSATION；决定 PAUSED/CLOSED 后是否仍允许执行 |
| OutcomeReconciliationKey | tenant、canonical subject ref、case 或 employment assignment ref、job/requisition scope、outcome_stage、measurement_window、purpose；不含 source_system/source business key |
| SourceAssertionRef | source system/business key、source/authority revision、asserted value、effective/observed/received time、content hash |
| ObservationWindow | measurement_start/end、maturity_at、as_of、censoring_reason |
| EmploymentLinkageRef | tenant、candidate person/case、employee/assignment refs、authority/purpose、revision；不创建跨租户全局身份 |
| LabelingPolicyPin | purpose、target_definition、eligible_types、maturity/censor_rules、excluded_signals、version |
| CohortEligibilityManifest | job/cycle scope、denominator query、eligibility/exclusion、as_of、lineage hash |
| FeatureAvailabilityManifest | prediction_at、当时可用字段、allowed field policy、post-decision exclusion |
| PartitionManifest | person-group split、temporal cutoff、train/dev/test refs、不可解析的 confirmatory holdout opaque ref、hash |
| HoldoutAccessFence | cohort/partition/study/candidate hashes、SEALED_UNOPENED/OPENED、first access actor/purpose/time/receipt、access token policy/version |
| SelectiveLabelDisclosure | label-producing population、hired-only coverage、missingness、禁止外推范围 |
| FeedbackStudyPlan | hypothesis、baseline/candidate、metrics、guardrails、minimum sample、stop rules、claim type |
| CandidateGenerationManifest | sealed cohort ref、discovery/train/dev partitions、feature cutoff、generator/prompt/policy versions、禁止 holdout refs、input hash |
| CausalDesignManifest | treatment、assignment unit、estimand、random/quasi-experimental method、overlap、interference/contamination、noncompliance、analysis plan、approval ref |
| OfflineEvaluationManifest | study/cohort/candidate refs、code/model/prompt/evaluator versions、seed、environment hash |
| ProfileDelta | base profile ref、维度/锚点/证据规则差异、禁用信号检查、content hash |
| PublicationScope | tenant、requisition/template、future recruitment cycle、effective_at、eligible future cases |
| ApprovalQuorumSnapshot | 两个不同 human_actor_id 的 HiringOwner + HRBP/ProfileGovernance、authority revisions、candidate/study/release eligibility/scope hash |
| ProfileReleaseEligibilitySnapshot | proposal/candidate/study/scope/input hashes、D0–D4 current assessments、owner/authority/evidence/policy refs、evaluated_at、expires_at、validity=CURRENT/INVALIDATED、snapshot hash |
| ProfilePublicationAuthorization | HUMAN actor/authority、proposal/candidate/study/release eligibility/scope hashes、effective_at、rollback target、authorized_at、expires_at、authorization hash |
| PublicationSyncRequirementSet | publication revision、required target/action pairs、target business revisions、policy versions、requirement hash |
| PublicationSyncReceiptSet | publication revision、required action refs、AutomationActionSucceeded receipt refs、external target revisions、accepted_at、receipt set hash |
| ProfileSafetyFence | role/scope、safety_epoch、freeze reason/authority、pending cancellation token/invalidated receipt refs、frozen_at |
| ProfileExposureAssignment | experiment/study、case、arm、assignment unit、allocation policy/version、assigned_at、assignment hash |
| RunCheckpoint | run_epoch、step_id、input_manifest_hash、tool/version、args/result hash、attempt、next_step、resume_token |

关键实体归属：

- ResumeSubmission 内：StructuredResumeVersion、RoutingResolution。
- ApplicationCase 内：ScreeningInputManifest、CurrentMatchAssessmentRef、DepartmentDecisionRequest、FinalAssessmentReviewTask、部门/最终 DecisionRecord。
- InterviewRound 内：SessionRequirement、轮次 DecisionRecord、RoundCompletionRecord。
- InterviewSession 内：CandidateCoordinationRequest、SchedulingProposal、SlotSelection、AppointmentRevision、InterviewBooking、ParticipantPresence、CaptureGateEvaluation、InterviewEvidenceHandoff 和 current_handoff_ref。
- 隐私上下文：ConsentReceipt 与 ProcessingControl 分别拥有参与人选择和带作用域的禁止性控制；InterviewSession 只保存当前引用快照。
- ActionExecution 内：ActionAttempt、ConnectorReceipt、CompensationLink。
- OutcomeObservation 内：SourceAssertion 与 canonical OutcomeRevision；OutcomeLabel 只引用完整 source_set/resolution hash、观察修订和 LabelingPolicyPin。
- AnalysisCohortSnapshot 内：denominator、成员/排除清单、成熟/缺失/删失统计和 PartitionManifest。
- FeedbackStudy 内：FeedbackStudyPlan、当前 Cohort 引用、接受的离线报告及限制；离线执行使用 AgentRun.kind=OFFLINE_EVALUATION。
- ProfileCandidateRevision 独立拥有 ProfileDelta 与 CandidateGenerationManifest；ProfileChangeProposal 只引用 candidate/study，并拥有 Release Gate assessments、ReviewTask revision、拒绝/修改、批准与独立 HUMAN 发布授权记录；RoleProfile 独立拥有 ProfileVersion、PublicationRevision、PublicationSyncRequirement/ReceiptSet、safety_epoch 与 current_published_version_ref。
- ProfileExposureLedger 内：稳定 Assignment、ActualExposure、Contamination/Deviation revisions；它不修改 ApplicationCase 的画像钉住事实。

## 6. 简历投递与开案

### 6.1 ResumeSubmission 路由状态

| 状态 | 含义 |
|---|---|
| RECEIVED | 来源消息/附件已去重接收 |
| PARSING | 正在提取可用于身份与岗位路由的信号 |
| ROUTING_REVIEW_REQUIRED | 人、岗位或批次存在缺失/冲突 |
| ROUTED | 已唯一解析到候选人、岗位需求和招聘周期 |
| REJECTED_AS_NON_APPLICATION | 经规则/人工确认不是有效申请 |

只有 ROUTED 才能执行 OpenApplicationCase。一个投递可作为同一案件的新来源附加，但不能因转发或 ATS 重复回调创建两个案件。ApplicationKey 在开案后不可变；路由纠正必须新建 RoutingResolution 修订，不能原地把旧 Case 改成另一个岗位或周期。

### 6.2 OpenApplicationCase 门

- ApplicationKey 四部分全部确定。
- 同租户不存在同一有效 ApplicationKey。
- 来源投递没有归属到冲突案件。
- 候选人和岗位均处于允许处理范围。
- 命令包含 expected_version 和幂等键。
- 若该投递的旧路由已经开案，旧 Case 已按 ROUTING_CORRECTED/MISROUTED 阻断生产动作并关闭，或已有明确人工裁决；正确案件才能打开或附加。

## 7. 申请案件顶层阶段

ApplicationCase.stage 只允许以下六个值：

| 阶段 | 含义 | 不表示 |
|---|---|---|
| RECEIVED | 已形成唯一申请案件，等待筛选前置条件 | 不表示所有简历字段无误 |
| SCREENING | 正在形成或修订人岗匹配材料 | 不表示 Agent 有淘汰权 |
| AWAITING_DEPARTMENT_DECISION | 当前匹配卡可审阅，等待人类决定 | 不表示流程异常 |
| INTERVIEWING | 已进入面试计划，具体进展由轮次推导 | 不复制待约面/已排期等状态 |
| FINAL_ASSESSMENT_READY | 必需轮次满足，终面评估包完整可审 | 不等于录用 |
| CLOSED | 人工淘汰、候选人撤回、需求关闭、重复合并或最终决定结束 | Agent 不得自动重开 |

允许迁移：

- RECEIVED → SCREENING
- SCREENING → AWAITING_DEPARTMENT_DECISION
- AWAITING_DEPARTMENT_DECISION → SCREENING（当前材料失效）
- AWAITING_DEPARTMENT_DECISION → INTERVIEWING（人决定进入面试）
- INTERVIEWING → FINAL_ASSESSMENT_READY
- FINAL_ASSESSMENT_READY → INTERVIEWING（最终决定前输入失效）
- 任一非 CLOSED → CLOSED（有合法来源的撤回、人工决定或需求关闭）

CLOSED 对 Agent 是终态。管理员纠错重开必须增加 lifecycle_epoch，旧生命周期的消息、会议和动作永远不自动恢复。

### 7.1 部门决定请求生命周期

DepartmentDecisionRequest 是 ApplicationCase 内的权威人审实体，只允许 OPEN、ON_HOLD、CLOSED、SUPERSEDED：

- `OpenDepartmentDecisionRequest` 在同一个 ApplicationCase 事务内钉住当前 MatchAssessment、创建请求并把 Case 从 SCREENING 推到 AWAITING_DEPARTMENT_DECISION；不能先迁移阶段、后补任务。
- 当前材料、Owner 或权限失效时，`InvalidateCurrentMatchAssessment` 同时撤销当前指针和请求，并把 Case 从 AWAITING_DEPARTMENT_DECISION 带回 SCREENING。
- HUMAN 提交 HOLD 时，同一 request_id 产生新的 ON_HOLD revision，保存 reason、revisit_at 和 SLA generation；HOLD 不关闭请求、不发送催办。
- 到达 revisit_at 后，`ResumeDepartmentDecisionRequest` 只按人已设定的恢复条件生成新的 OPEN revision 和 SLA generation，不替人作招聘决定；旧卡片随 revision 失效。
- INVITE/REJECT 生效时请求 CLOSED；材料或 Owner 被替代时请求 SUPERSEDED。Case 处于 AWAITING_DEPARTMENT_DECISION 时必须恰有一个当前 OPEN 或 ON_HOLD 请求。

## 8. 面试轮次子状态

| 状态 | 含义 |
|---|---|
| PLANNED | 来自钉住的流程版本，前置轮次未满足 |
| READY_TO_SCHEDULE | 前置条件满足，可启动约面 |
| SCHEDULING | 正在找时段或提交日历写入 |
| SCHEDULED | 有效预约成功，邀请有回执 |
| IN_PROGRESS | 面试会话已开始 |
| EVIDENCE_PROCESSING | 会话结束，正在处理录音/转写/证据/评价 |
| AWAITING_CONFIRMATION | 评价通过机器校验，等待指定人确认同一版本 |
| AWAITING_OUTCOME | 确认策略满足，等待授权人作轮次决定 |
| COMPLETED | 有有效人工轮次决定且归档完成 |
| CANCELLED | 流程修订取消本轮 |
| WAIVED | 授权人显式豁免并记录原因 |

轮次决定：

- ADVANCE_TO_NEXT
- REPEAT_ROUND
- STOP_PROCESS
- FINAL_ROUND_COMPLETE

FINAL_ROUND_COMPLETE 表示终轮材料完成，不等于 HIRE/NO_HIRE。

### 8.1 G1a 受控导入

ImportCompletedInterview 允许 PLANNED 或 READY_TO_SCHEDULE 直接进入 EVIDENCE_PROCESSING，但必须满足：

- 案件、轮次、真实发生时间和参与人明确。
- 评分卡版本已钉住。
- 录音/笔记的合法性和同意凭证可证明。
- 媒体指纹未在其他活动会话中导入。
- 记录 observed_start_missing 等缺失事实，不伪造中间状态。

### 8.2 G1b 简报、问题与终面包生命周期

InterviewBrief.status：

| 状态 | 含义 |
|---|---|
| DRAFT | 已形成建议问题草稿，尚未通过披露/合规校验 |
| BLOCKED | 命中禁用特征、诱导性、无依据或受众/输入问题，不能分发 |
| CURRENT | 当前 Round、受众修订和输入清单下唯一可分发版本 |
| INVALIDATED | Round、受众、评分卡、披露策略或输入变化，只能历史只读 |

CrossRoundIssue.status：

| 状态 | 含义 |
|---|---|
| CANDIDATE | Agent/规则提出需要复核的问题候选，不代表已判定事实冲突 |
| CLASSIFIED | 有权限的人或批准规则已确定类型、严重度和阻断性 |
| RESOLVED | 已补证、澄清范围、承认信息不足或授权非阻断，保存解决记录 |
| SUPERSEDED | causal input 变化，旧问题不再适用；新版本需要重新检测 |

FinalAssessmentPackage.status：

| 状态 | 含义 |
|---|---|
| DRAFT | 已冻结输入清单或生成摘要，尚未通过完整性门 |
| BLOCKED | 存在缺项、版本失配、无证据关键 claim、决定字段或未处理 P0/P1 |
| READY | 当前输入下完整、有效、无阻断项的不可变版本 |
| INVALIDATED | 任一钉住输入被替代、撤回、删除、过期或不再兼容 |

一个 READY 包仍不等于 `ApplicationCase.stage=FINAL_ASSESSMENT_READY`；只有当前最终审阅任务创建成功、最终决策人权限有效，控制面才能执行 MarkFinalAssessmentReady。外部通知失败只改变 RuntimeEnvelope/异常，不创造第二个权威任务。

`FINAL_ASSESSMENT_READY` 不等于 HIRE/NO_HIRE、终面通过或案件关闭；最终招聘决定仍必须由有权限的人主动提交。

包有效性不是缓存布尔值：编译、读取、分发和任何最终决定写入前，都必须校验 Input Manifest 中的轮次完成件、豁免、证据、计划/画像/评分卡版本仍为当前且允许使用。事件负责传播失效，读取/写入门负责在传播延迟时阻止旧包继续使用。

### 8.3 G2 会话协调与预约

InterviewSession.lifecycle_state：

| 状态 | 含义 |
|---|---|
| PLANNED | 会话需求已建立，尚未实际开始 |
| IN_PROGRESS | 面试会面已经开始；不表示正在录制 |
| ENDED | 会面已结束，等待或已形成 G1 交接 |
| CANCELLED | 当前会话需求被计划修订或有权限的人取消 |

InterviewSession.scheduling_state：

| 状态 | 含义 |
|---|---|
| NOT_STARTED | 尚未打开候选人协调请求 |
| COORDINATING | 正在收集时区/可用时间或形成时段提案 |
| PROPOSAL_OPEN | 有一个当前可选择的时段提案 |
| BOOKING_PENDING | 候选人已选择，当前预约修订正在写入/对账 |
| BOOKED | 有一个当前有效 InterviewBooking |
| RESCHEDULING | 旧 Booking 仍有效，同时存在一个待提交的新预约修订 |
| CANCELLATION_PENDING | 当前 Booking 正在执行安全取消/对账 |
| CANCELLED | 当前 Booking 已取消且没有待提交修订 |

预约规则：

- SchedulingProposal 和 SlotSelection 都不是 Booking。
- AppointmentRevision 不可变；一个 Session 最多同时有一个已提交有效修订和一个待提交修订。
- BookingRequirementsSnapshot 要求的日历、会议和邀请写入回执齐全、当前且同一修订时，才能 CommitBooking。
- 外部重复会议是对账/补偿异常，不能形成第二个业务 Booking。
- 尚无必需会话开始时，一轮只有一个必需会话则该会话 BOOKED 才投影 Round=SCHEDULED；有多个必需会话必须全部 BOOKED。仍未开始时，任一必需会话失去当前 Booking 则 Round 回 SCHEDULING。任一必需 Session 已开始后，Round 进入或保持 IN_PROGRESS，即使其他必需 Session 仍在约面；未排期要求继续显示在 Session 层，后续 Booking 不得把 Round 回退为 SCHEDULED。

### 8.4 G2 面试与采集

InterviewSession.capture_mode：

| 值 | 含义 |
|---|---|
| UNDECIDED | 当前参与人或选择尚未满足，不能开始采集 |
| RECORDING | 当前参与人/目的允许音视频采集 |
| NO_RECORDING | 明确不采集音视频，面试仍正常进行 |

InterviewEvidenceHandoff.evidence_route：

| 值 | 含义 |
|---|---|
| RECORDED_EVIDENCE | 引用当前允许使用且 checksum 已确认的录制资产 |
| AUTHORIZED_NOTES_ONLY | 本次交接不引用音视频证据，只引用批准来源的人工笔记；不改写“曾请求、部分采集、撤回后隔离或删除”等真实采集历史 |

InterviewSession.capture_state：

| 状态 | 含义 |
|---|---|
| OFF | 未开始采集 |
| STARTING | 当前闸门通过，正在请求平台开始采集 |
| ON | 平台回执与控制面一致，采集进行中 |
| STOPPING | 撤回、参与人变化、面试结束或控制事实要求停止 |
| STOPPED | 平台已证明停止 |
| BLOCKED | 闸门不通过、平台能力不足或状态不明，禁止开始/继续采集 |

CaptureGateEvaluation 只能产生 ALLOW_RECORDING、REQUIRE_NO_RECORDING 或 BLOCK_CAPTURE_AND_ESCALATE。闸门参与人集合是“当前在场且其媒体可能进入平台采集”的所有人，不能通过漏标“被采集人”绕过晚加入者。StartInterview 只改变会面事实，不能隐式请求采集；晚加入、参与人选择撤回、目的/告知版本变化、处理限制和平台状态变化都必须产生新的闸门评估。拒绝录制及其原因不能进入 MatchAssessment、EvaluationPackage、InterviewBrief 或招聘决定依据。

平台采集采用请求/确认两段式：RequestCaptureStart 只能进入 STARTING，当前 Provider 开始回执经版本校验后才能 ConfirmCaptureStarted→ON；RequestCaptureStop 只能进入 STOPPING，当前 Provider 停止回执经校验后才能 ConfirmCaptureStopped→STOPPED。停止失败、状态未知或迟到开始回执不得伪造 STOPPED，必须保持 STOPPING 或进入 BLOCKED，并触发 P0 停止、对账和事件响应。

### 8.5 G2 G1 交接

采集模式只描述会议是否采集；证据路线才描述交给 G1 的输入，并与 G1a 受控导入枚举显式映射：

| G2 evidence_route | G1a evidence_route | 必需引用 | 禁止引用 |
|---|---|---|---|
| RECORDED_EVIDENCE | RECORDING | recording artifact id/version/checksum、Consent/ProcessingControl/Capture reconciliation refs | 失效、未对账或用途不允许的资产 |
| AUTHORIZED_NOTES_ONLY | NOTES_ONLY | notes id/version/hash、author/authority、来源范围和 limitation、capture history/final reconciliation refs | 作为证据的 recording/transcript refs、伪造的音视频质量结论 |

InterviewSession 只保留一个 current_handoff_ref。新资产/笔记修订、同意/控制变化、删除、超保留期或来源纠正会使当前 handoff 失效；替代输入必须创建更高 revision 并显式 supersede。传播延迟期间，G1 的读取/使用门仍必须重验 HandoffInputManifest，不能继续使用旧输入。

### 8.6 G3 结果回流与画像治理

G3 的业务主链固定为：

`批准来源断言 → canonical 结果解析 → 标注资格/成熟裁决 → 分析队列与分区封存 → 仅用 discovery/train/dev 生成并冻结画像候选修订 → 预注册 confirmatory Study → 首次打开 holdout 并可重放评测 → D0–D4 Release Eligibility → distinct-human 双人批准 → 独立 HUMAN publication authorization → CONTROL_PLANE Prepare(PENDING_SYNC) → required receipts → Commit future pointer → 暴露账本/监控/Freeze → HUMAN 授权的 CONTROL_PLANE 回滚`

任何一步都不能跳过或把前一层完成投影成后一层完成。

| 对象 | 状态 |
|---|---|
| OutcomeRevision.lifecycle | PROVISIONAL → CONFIRMED；当前修订可 DISPUTED / INVALIDATED；纠正时旧修订标 CORRECTED 并创建更高修订 |
| OutcomeLabel.lifecycle | DRAFT → VERIFIED / EXCLUDED；VERIFIED 可 SUPERSEDED / INVALIDATED |
| OutcomeLabel.maturity | PENDING / MATURE / RIGHT_CENSORED / UNKNOWN / NOT_ELIGIBLE，与 lifecycle 正交 |
| AnalysisCohortSnapshot | DRAFT → SEALED → INVALIDATED / ARCHIVED |
| FeedbackStudy | 创建即 PREREGISTERED → RUNNING → ANALYSIS_READY；任一当前阶段可 INVALIDATED / CANCELLED；人审状态只属于 ProfileChangeProposal |
| AgentRun.execution | 创建即 RUNNING；RUNNING ↔ WAITING_TOOL / WAITING_HUMAN / PAUSED → SUCCEEDED / FAILED / CANCELLED；validity 另为 CURRENT / INVALIDATED |
| ProfileCandidateRevision | FROZEN / INVALIDATED；FROZEN 后不可修改，任何差异产生新 aggregate/revision |
| ProfileChangeProposal.lifecycle | DRAFT → EVALUATION_PENDING → RELEASE_ELIGIBLE → REVIEW_READY → APPROVED → PUBLICATION_AUTHORIZED；RELEASE_ELIGIBLE/REVIEW_READY 可 REJECTED，要求修改回 EVALUATION_PENDING，开放状态可 SUPERSEDED |
| ProfileChangeProposal.validity | CURRENT / INVALIDATED；INVALIDATED 会撤回当前任务与批准，旧页面不可再写 |
| RoleProfile | ACTIVE / FROZEN；Freeze 提升 safety_epoch，只有当前回滚授权可从 FROZEN 回 ACTIVE |
| PublicationRevision | PENDING_SYNC → ACTIVE；PENDING_SYNC 可 CANCELLED，ACTIVE 可 SUPERSEDED / ROLLED_BACK；回滚创建 operation=ROLLBACK 的新 ACTIVE revision，PENDING_SYNC 永不可被新 Case pin |
| ProfileExposureLedger | ASSIGNED → EXPOSED / NOT_EXPOSED；任一状态可追加 CONTAMINATED / DEVIATED 观察，不覆盖分配历史 |

`RELEASE_ELIGIBLE` 要求同一 candidate/study/scope/input hash 下 D0–D4 当前 Gate Assessment 全部 PASS、未过期且无 veto；D0 数据与标签健康、D1 泄漏/选择性标注/外推范围、D2 指标/重要 slice/公平与代理风险、D3 claim 与因果设计、D4 用途/权限/血缘/回滚/运行准备缺一不可。AttachEvidence、进入 REVIEW_READY、批准、发布授权、Prepare 与 Commit 都必须重新计算或加载同一组 current assessment，`ANALYSIS_READY` 永不等于 `RELEASE_ELIGIBLE`。小样本、hired-only 外推、代理/公平失败、用途/删除失败或因果设计不足都不能由双人批准覆盖。

| Release Gate | 必须证明 | 典型非 PASS |
|---|---|---|
| D0 LABEL_AND_DATA_HEALTH | denominator、成熟/缺失/删失、canonical source set、label/control lineage 当前 | PENDING 当负例、来源冲突、分母缺失、删除未传播 |
| D1 LEAKAGE_AND_GENERALIZATION | prediction-time 特征、person/temporal split、selective-label 与允许外推范围 | 后见字段、同人跨分区、hired-only 外推 rejected/全漏斗 |
| D2 PERFORMANCE_FAIRNESS_PROXY | 预注册指标/重要 slice/精度、fairness/proxy 检查及反证 | INCONCLUSIVE、重要 slice harm、代理变量或受保护属性污染 |
| D3 CLAIM_AND_CAUSALITY | claim_type 与证据设计匹配；因果主张有批准 CausalDesignManifest 与 exposure plan | 用普通离线关联声称提升、无 assignment/exposure/contamination 计划 |
| D4 PURPOSE_AUTHORITY_OPERABILITY | purpose/authority/retention、base/current、未来范围、rollback target、required sync/监控与 A0 恢复准备 | 用途/权限过期、base stale、在途迁移、无回滚/同步/监控准备 |

`APPROVED` 只表示两个不同 HUMAN 主体批准了同一候选修订、当前 ProfileReleaseEligibilitySnapshot 和发布范围；两个签名必须来自不同 `human_actor_id`，不能由同一人兼任两个角色。批准后还必须由一个当前有发布权限的 HUMAN 对精确 authorization hash 单独执行 `AuthorizeProfilePublication`，才能进入 `PUBLICATION_AUTHORIZED`；授权人可以是两位批准人之一，但这是另一笔带独立权限快照、时效和幂等键的显式授权，不能从批准推导。批准、授权与执行是三类事实。`CONTROL_PLANE` 随后执行两阶段发布：`PrepareProfilePublication` 只创建不可变 ProfileVersion 与 `PENDING_SYNC` PublicationRevision，并声明 required sync actions；只有全部当前回执被 RoleProfile 接受后，`CommitProfilePublication` 才把该修订转为 ACTIVE 并在同一 RoleProfile 事务中更新 future-scope `current_published_version_ref`。新版本默认只适用于声明的未来招聘周期和新开案件，在途 ApplicationCase 继续使用既有 VersionPin。

任职后表现通常只对已录用者可观察。AnalysisCohortSnapshot 必须保留完整 denominator、选择机制、成熟/缺失/删失、as_of 与不可外推范围；历史 reject、offer、hire 是流程或选择事实，不是能力真值。CandidateGenerationManifest 禁止引用 confirmatory test/holdout；candidate hash 冻结后才能预注册 Study，任何候选修改必须新建 Study，不能在同一 holdout 上循环调参。无当前、批准的 CausalDesignManifest 时 claim_type 强制为 ASSOCIATIONAL；A2 必须记录 assignment、actual exposure、contamination 与 noncompliance，不能按是否采纳 Proposal 自选分组。

Profile Governance Agent 可以归一化来源断言草稿、生成标注草稿、使用 discovery/train/dev 形成候选修订、执行已预注册的 confirmatory 评测并整理审阅包；它不能确认 canonical 事实、改变队列分母/分区/研究指标、打开后反复使用 holdout，也不能批准、授权发布、提交发布 pointer、解冻或回滚画像。长任务只能从已提交 Agent Run Checkpoint 恢复，输入清单改变会使旧 resume_token 失效。Freeze 会提升 safety_epoch、发出 pending publication cancellation token 并立即阻断未提交发布；回滚只能消费绑定当前冻结 safety_epoch 的 HUMAN 授权，由 CONTROL_PLANE 创建新的 PublicationRevision、把 RoleProfile 从 FROZEN 恢复为 ACTIVE，并把受影响自动化等级恢复到 A0。

## 9. 正交运行状态

每个受编排对象有 RuntimeEnvelope：

| 字段 | 可选值 / 含义 |
|---|---|
| suspension | RUNNING / PAUSED |
| activity | ACTIVE / WAITING_EXTERNAL / RETRYING / NEEDS_HUMAN |
| reason_code | 结构化原因 |
| owner_ref | 当前责任人 |
| entered_at | 进入时间 |
| wake_condition | 唤醒条件 |
| deadline_at | 最晚时间 |
| next_retry_at / retry_count | 重试计划 |
| exception_bundle_id | 关联异常 |
| resume_token | 恢复凭证 |

显示优先级：

1. suspension=PAUSED 时一律显示 PAUSED，并硬阻断生产性写动作；已授权的安全停止/补偿继续执行。
2. 否则显示 activity。
3. 未关闭异常继续留在 blocker 列表，不能被暂停状态覆盖。

运行状态变化不得隐式改变业务阶段。PAUSED 也不能用于隐藏 SLA 超时。

## 10. 页面状态是投影，不是第四套真相

| 页面文案 | 推导规则 |
|---|---|
| 已接收 | Case=RECEIVED |
| 待复核 | Submission/Case 的运行态为 NEEDS_HUMAN，原因为解析/身份/路由 |
| 待部门决定 | Case=AWAITING_DEPARTMENT_DECISION |
| 待约面 | Case=INTERVIEWING 且 Round=READY_TO_SCHEDULE/SCHEDULING |
| 已排期 | Round=SCHEDULED |
| 面试处理中 | Round=IN_PROGRESS/EVIDENCE_PROCESSING |
| 待确认 | Round=AWAITING_CONFIRMATION |
| 待轮次决定 | Round=AWAITING_OUTCOME |
| 待下一轮 | 前轮已完成、下一轮尚未激活的编排投影 |
| 面前简报待处理 | 当前 Round 已激活，InterviewBrief=DRAFT/BLOCKED 或当前受众任务未建立 |
| 待终面汇总 | Case=INTERVIEWING，适用必需 Round 均 COMPLETED/WAIVED，当前 FinalAssessmentPackage 非 READY |
| 终面评估就绪 | Case=FINAL_ASSESSMENT_READY |
| 已关闭 | Case=CLOSED |
| 结果冲突待裁决 | OutcomeObservation.current revision=DISPUTED；展示来源差异和 Steward 下一步，不显示“成功/失败” |
| 固定评测运行中 | FeedbackStudy=RUNNING 且 current AgentRun 的 execution/runtime 投影；Checkpoint/等待/恢复点可展开 |
| 画像提案待人审 | ProfileChangeProposal=REVIEW_READY 且 current ReviewTask 有效；D0–D4、限制、发布范围和回滚目标可见 |
| 发布同步中 | RoleProfile=ACTIVE 且存在 current PublicationRevision=PENDING_SYNC；展示 required receipts 缺口，不显示“已发布” |
| 画像已发布 | RoleProfile=ACTIVE 且 current pointer 指向 ProfilePublicationCommitted 的 ACTIVE revision |
| 画像已冻结 | RoleProfile=FROZEN；展示安全原因、safety_epoch、影响范围、pending cancellation 和 HUMAN 回滚授权入口 |

API 不接受“直接写页面状态”。所有显示状态由业务事实推导。

## 11. 通用命令门

每条改变状态或外部世界的命令先过通用门，再按命令类型进入互斥的 Case-bound 或 G3 治理门；不得把 G3 的多案件分析引用误判为“同一案件”，也不得用 G3 范围门绕过案件隔离。

通用门：

1. tenant、字段、目的与 actor/authority 当前，所有引用对象同租户且版本/哈希仍有效。
2. expected_aggregate_version 乐观锁；同一幂等键未被不同负载使用。
3. 当前 processing_control_set_hash、target_business_revision、purpose、operation、data scope 与命令一致；删除、限制、来源失权或用途变化优先阻断普通动作。
4. 当前动作符合 ActionPolicySnapshot 和 A0–A3；招聘决定、画像双人批准、发布授权和回滚授权的 actor_type 必须为 HUMAN 且权限匹配。
5. 本地事务只写一个聚合及其 Outbox；跨聚合只消费事件后加载当前事实，再发带 expected_version 与幂等键的新命令。

Case-bound G1/G2 门：

6. 所有业务引用必须同一 case_id；current lifecycle_epoch、current_routing_revision、target revision 与命令一致。
7. 生产性动作要求 Case 未 CLOSED、未删除、未 PAUSED；SAFETY_COMPENSATION 仅允许白名单停止/撤销/删除动作并引用原动作/外部资源修订。
8. 录制、转写或新用途处理的 Notice、参与人选择、处理目的和最新 Capture Gate 仍有效。

G3 分析/治理门：

9. 命令声明 tenant、job/requisition/template scope、recruitment cycle 或 analysis window、purpose、processing_control_set_hash 与 lineage epoch；引用多个案件只允许经当前 `SEALED AnalysisCohortSnapshot`，不得向 G3 命令传入未封存的任意 case 列表。
10. 历史 CLOSED Case 只可在批准目的、字段、保留和血缘范围内只读引用；G3 不得改变其阶段、决定、画像钉住或在途事实。ProfileExposureLedger 只可引用同 tenant 的明确 Study × Case。
11. Candidate/Study/Proposal/Publication 的 base、candidate、cohort、partition、holdout、D0–D4 eligibility、scope、authority、safety_epoch 与 required receipt set 必须逐级 current；任一上游 invalidated、过期、FAIL/VETO 或 hash 不一致即拒绝。
12. `HUMAN` 只拥有批准、发布授权与回滚授权；`CONTROL_PLANE` 只可消费精确且当前的人类授权执行 Prepare/Commit/Rollback。Agent、LLM、普通 Service 均不能替代任一方。

## 12. 关键迁移门

| 命令 | 迁移/结果 | 额外条件 |
|---|---|---|
| RegisterResumeSubmission | 创建/重放 Submission RECEIVED | 来源批准；附件门通过；来源/附件/内容幂等；材料内指令不执行 |
| RecordStructuredResumeVersion | 追加不可变简历版本 | 字段带 locator/来源；原件可追溯；不覆盖历史 |
| ResolveApplicationRouting | Submission 当前路由→ROUTED | 候选人、岗位、周期唯一且允许处理；无冲突信号 |
| SupersedeApplicationRouting | ResumeSubmission 旧路由只读，建立新当前路由修订 | 有权限纠正；生成影响清单与撤销令牌；已应用关系先进入纠正闭环 |
| SupersedeSubmissionCaseLink | ApplicationCase 内旧投递关系→SUPERSEDED | ApplicationKey 不变；旧关系所因果产生的材料/任务/待执行动作失效；保留历史，不搬决定或会议 |
| CloseMisroutedApplicationCase | ApplicationCase→CLOSED(ROUTING_CORRECTED/MISROUTED) | 当前 HUMAN 或批准的确定性纠错规则；若有其他有效来源/外部效果则先开异常包决定范围；技术关闭不形成 REJECT 或拒信 |
| OpenOrAttachApplicationCase | 创建 Case RECEIVED 或附加来源到同键 Case | INV-G2-ROUTED-ONLY；ApplicationKey 完整唯一；旧关系已 supersede 且关闭/补偿范围已有明确裁决；同人多岗隔离 |
| PinScreeningInput | Case RECEIVED/SCREENING→SCREENING | 当前简历可读；目标 RoleProfile=ACTIVE，画像引用来自 scope 匹配的 committed current_published_version_ref 与 current safety_epoch，PENDING_SYNC/FROZEN 不可 pin；允许字段/策略明确；旧材料/任务按影响失效 |
| PublishMatchAssessment | MatchAssessment DRAFT→READY；Case 不变 | 当前 ScreeningInputManifest；必填维度完成；结论有原文证据；无决定/排名；INV-G2-NO-AUTO-REJECT |
| OpenDepartmentDecisionRequest | ApplicationCase SCREENING→AWAITING_DEPARTMENT_DECISION；原子钉住当前材料并创建唯一请求 | 引用 READY MatchAssessment；Owner/权限/截止/选项当前；同一事务内不出现“有阶段无任务” |
| InvalidateCurrentMatchAssessment | ApplicationCase AWAITING_DEPARTMENT_DECISION→SCREENING | 当前材料/输入/Owner/权限失效；同事务撤销当前指针与请求，旧卡片不可写 |
| RecordDepartmentDecision(INVITE) | →INTERVIEWING | 有权限的人；引用当前匹配材料；面试流程可钉住 |
| RecordDepartmentDecision(HOLD) | 请求 OPEN→ON_HOLD；Case 保持 AWAITING_DEPARTMENT_DECISION | 有权限的人；不可变 HUMAN 决定、reason、revisit_at、新 SLA generation 齐全；停止催办 |
| ResumeDepartmentDecisionRequest | 请求 ON_HOLD→OPEN 新 revision；Case 不变 | revisit_at 到期；材料、Owner、权限和阶段仍当前；只恢复人审，不替人决定 |
| RecordDepartmentDecision(REJECT) | →CLOSED | 只能人工；拒绝信是独立外发动作 |
| AdvanceReminderOrdinal | 决定请求不变；追加下一次催办授权 | 当前 Owner/任务/阶段；静默时段、上限和 generation 通过 |
| AmendInterviewPlan | Case 仍 INTERVIEWING；生成新计划版本与影响清单 | 只能有权限的人；图无环；受影响 Round/Brief/Package/Task 失效 |
| ActivateRound | PLANNED→READY_TO_SCHEDULE | 当前计划适用；所有前置轮次完成件/豁免有效；人类决定允许继续；评分卡已钉住 |
| CreateRepeatRound | 新建 Round，原 Round 不变 | 来源决定为 HUMAN 的 REPEAT_ROUND；新 ID、来源关系、序号和幂等键唯一 |
| RecordRoundWaiver | PLANNED/READY_TO_SCHEDULE→WAIVED | 只能有权限的人；范围、原因、依据和权限快照齐全；不生成能力证据 |
| OpenCandidateCoordinationRequest | Session NOT_STARTED→COORDINATING | 当前 Round 已激活；参与人角色/时区/约束当前；候选人入口限时限用途 |
| PublishSchedulingProposal | Session COORDINATING→PROPOSAL_OPEN | 忙闲/约束快照当前；proposal version/expiry；不等于 Booking |
| RecordCandidateSlotSelection | 追加当前选择意图 | 当前 proposal/version、candidate actor、selection_action_id；不改变为 BOOKED |
| ProposeAppointmentRevision | Session→BOOKING_PENDING 或 RESCHEDULING | 执行前重读忙闲/控制；一个有效修订加至多一个待提交修订 |
| CommitBooking | Session BOOKING_PENDING/RESCHEDULING→BOOKED | 当前修订的 BookingReceiptSet 完整；外部资源版本一致；尚无会话开始时 Round 由全部必需 Session 投影，已 IN_PROGRESS 时不得回退 |
| RequestReschedule | Session BOOKED→RESCHEDULING | 新预约修订；旧 Booking 在新提交前继续有效 |
| CommitBookingCancellation | Session→CANCELLED 或回协调 | SAFETY_COMPENSATION 可在 PAUSED/CLOSED 执行；外部资源已对账 |
| RecordRecordingNoticeDelivery | 追加 NoticeReceipt | 当前 session/purpose/text version/recipient/channel；不产生 ConsentReceipt |
| RecordParticipantRecordingChoice | 追加/撤回 ConsentReceipt | 本人或合法代理；当前 session/purpose/notice version；不影响招聘评价 |
| RecordParticipantJoined | 更新 Presence revision | 来源可信；触发新的 Capture Gate，不继承他人选择 |
| RecordParticipantLeft | 更新 Presence revision | 来源可信；触发新的 Capture Gate；停止采集前仍按当前平台事实对账 |
| EvaluateCaptureGate | 追加 Gate Evaluation | 当前在场且媒体可能进入采集的参与人、目的、告知、选择、ProcessingControl set 和平台能力；只能 ALLOW_RECORDING/REQUIRE_NO_RECORDING/BLOCK |
| StartInterview | InterviewSession PLANNED→IN_PROGRESS | 当前 Booking 或批准导入；不隐式请求采集；NO_RECORDING 可正常开始 |
| MarkInterviewRoundInProgress | InterviewRound SCHEDULING/SCHEDULED→IN_PROGRESS；已 IN_PROGRESS 时幂等 | 消费当前必需 Session 的 InterviewSessionStarted；剩余 Session 继续独立约面；后续 Booking 不得回退 Round；expected_version/idempotency 当前 |
| RequestCaptureStart | Capture OFF/BLOCKED→STARTING | 最新 Gate=ALLOW_RECORDING；写 CaptureStartRequested + Outbox；只表示已请求 |
| ConfirmCaptureStarted | Capture STARTING→ON | 当前 Provider 回执匹配 session、attempt、gate、action 和 resource revision |
| RequestCaptureStop | Capture ON/STARTING/BLOCKED→STOPPING | 面试结束、晚加入、撤回、限制或异常；SAFETY_COMPENSATION 优先；立即隔离新处理 |
| ConfirmCaptureStopped | Capture STOPPING→STOPPED | 当前停止回执或可信对账证明已停；超时/未知不得乐观提交 |
| MarkCaptureStateMismatch | Capture STARTING/ON/STOPPING→BLOCKED | 平台状态未知、意外录制、无法停止或迟到开始；P0 停止、对账和事件响应 |
| ImportCompletedInterview | PLANNED/READY_TO_SCHEDULE→EVIDENCE_PROCESSING | 满足 G1a 受控导入门 |
| FinishInterview | Session IN_PROGRESS→ENDED | 当前采集已停止/对账；保留实际采集与控制快照 |
| CreateInterviewEvidenceHandoff | InterviewSession=ENDED 后创建不可变 handoff revision 并设 current_handoff_ref | STARTING/ON/STOPPING/状态未知时硬拒绝；RECORDED_EVIDENCE 要求 STOPPED、采集对账完成且当前最终资产可用；从未录制的 AUTHORIZED_NOTES_ONLY 要求 OFF/NO_RECORDING、无外部采集观测且对账完成；曾部分采集或撤回的 AUTHORIZED_NOTES_ONLY 要求 STOPPED、片段隔离/删除/处置完成且对账完成；当前资产或笔记版本钉住，不改 Round |
| InvalidateInterviewEvidenceHandoff | InterviewSession 当前 handoff→INVALIDATED | causal input 被替代、删除、超保留期或用途/控制不再允许；旧 Accepted 不能复活 |
| AcceptInterviewEvidenceHandoff | InterviewRound 汇入一个当前 Session handoff；全部必需输入齐后→EVIDENCE_PROCESSING | G1 接收幂等；每个必需 Session 只接受当前 revision；读取/使用前重验 |
| InvalidateRoundEvidenceInput | InterviewRound 撤销失效 handoff 的当前输入引用并保持/回到 EVIDENCE_PROCESSING | 消费当前 Handoff invalidated；旧评价/确认/完成件按 causal input 继续失效，替代输入需重新接受 |
| PublishEvaluationForReview | EVIDENCE_PROCESSING→AWAITING_CONFIRMATION | 证据集合/评分卡一致；关键结论证据覆盖 100% |
| ReachConfirmationQuorum | AWAITING_CONFIRMATION→AWAITING_OUTCOME | 必需 Reviewer 对同一评价版本确认；无未处理修改请求 |
| RecordRoundDecision | AWAITING_OUTCOME→COMPLETED | 人工决定；引用当前已确认评价 |
| PublishInterviewBrief | Brief DRAFT/BLOCKED→CURRENT | 当前 Round/受众/评分卡/Input Manifest；分阶段披露和问题策略通过 |
| RecordInterviewBriefFeedback | Brief 版本不变；追加隔离反馈 | 当前指定面试官；接受/编辑/忽略/报告问题；不得改候选人评价或画像 |
| ClassifyCrossRoundIssue | Issue CANDIDATE→CLASSIFIED | 批准规则或有权限的人；确定类型、严重度、阻断性和 Owner |
| ResolveCrossRoundIssue | Issue CLASSIFIED→RESOLVED | 有权限的人；补证/范围澄清/信息不足/非阻断记录齐全 |
| CompileFinalAssessmentPackage | Package 无当前版本/BLOCKED/INVALIDATED→READY 或 BLOCKED | FinalInputManifest 当前；仅完成件/有效豁免；证据/决定字段/问题门通过 |
| InvalidateFinalAssessmentPackage | FinalAssessmentPackage READY→INVALIDATED | 任一 causal input 失效；只写 Package 并发失效事件 |
| RecallFinalAssessmentReadiness | ApplicationCase FINAL_ASSESSMENT_READY→INTERVIEWING，并撤回本聚合内当前 FinalAssessmentReviewTask | 消费当前 Package invalidated；读取前重验；只写 ApplicationCase 与 Outbox |
| CreateFinalAssessmentReviewTask | 创建唯一当前权威任务 | Package READY；最终决策人权限有效；task revision 与 package version 绑定 |
| MarkFinalAssessmentReady | INTERVIEWING→FINAL_ASSESSMENT_READY | 必需轮次 COMPLETED/WAIVED；Package READY 且读取前重验；当前审阅任务已创建；无未处理 P0/P1 |
| RecordFinalDecision | FINAL_ASSESSMENT_READY→CLOSED，并追加不可变最终决定 | 有权限的人；引用当前终面评估包；发出 FinalHiringDecisionRecorded |
| SupersedeFinalDecision | ApplicationCase 追加更高决定修订 | 仅纠错且 HUMAN 有权限；旧决定只读；发出 FinalHiringDecisionSuperseded，不自动重发沟通 |
| RecordCandidateWithdrawal | 任一非 CLOSED→CLOSED | 来源可证明；同事务写取消令牌 |
| ReopenApplicationCase | CLOSED→上一个合法阶段 | 仅纠错；增加 lifecycle_epoch；所有旧外发无效 |
| ApplyProcessingRestriction | ProcessingControl 追加更高当前限制修订 | HUMAN/权利系统 authority、data subject、case/session 或 G3 lineage scope、purpose/operation/data categories、effective_at 与控制幂等键明确；只写本 ProcessingControl |
| ApplyDeletionDirective | ProcessingControl 追加更高当前删除修订 | HUMAN/权利系统 authority、data subject、case/session 或 G3 lineage scope、purpose/operation/data categories、保留例外与 deadline 明确；只写本 ProcessingControl，派生物由事件逐聚合失效 |
| RecordOutcomeSourceAssertion | OutcomeObservation 创建或追加 SourceAssertion；canonical pointer 不变 | OutcomeReconciliationKey、来源业务键/修订、岗位、阶段、窗口、用途及适用 EmploymentLinkageRef 批准；同一来源键低修订忽略、同修订异负载拒绝；不得自动合并身份 |
| ReconcileOutcomeObservation | OutcomeObservation 基于完整当前 source_set_hash 创建 PROVISIONAL 或 DISPUTED canonical OutcomeRevision；若已有 current revision，则旧修订→CORRECTED 并发 OutcomeObservationCorrected | OutcomeReconciliationKey 不含来源；authority/resolution policy 当前；冲突、迟到来源、缺关键来源不得按最新到达或多数投票自动 CONFIRMED；旧 Label 在新解析完成前已被读取门判 stale |
| ReferenceHiringDecisionObservation | OutcomeObservation 创建只读来源断言及 PROVISIONAL canonical 引用修订，并发 OutcomeSourceAssertionRecorded + OutcomeObservationReconciled | 消费时重新加载 ApplicationCase 当前 FinalDecision；OutcomeReconciliationKey 唯一；保留 ApplicationCase 所有权、HUMAN actor、决定版本与 source_set_hash，不复制决定 |
| ConfirmOutcomeObservation | OutcomeObservation 当前修订 PROVISIONAL/DISPUTED→CONFIRMED | Outcome Data Steward 或批准规则；来源权限、范围和冲突已解决 |
| DisputeOutcomeObservation | OutcomeObservation 当前修订→DISPUTED | 来源冲突或可信质疑；不得自动按最新到达/多数投票裁决 |
| CorrectOutcomeObservation | OutcomeObservation 旧修订→CORRECTED 并创建更高当前修订 | 有权限来源/Steward；原因、旧新引用和影响血缘齐全 |
| InvalidateOutcomeObservation | OutcomeObservation 当前修订→INVALIDATED | 删除、来源失权、用途变化、超保留或事实撤销；发失效事件 |
| DeriveOutcomeLabelDraft | OutcomeLabel 创建 DRAFT | 当前 Observation、LabelingPolicyPin、purpose、maturity_window 和 excluded signals 当前 |
| VerifyOutcomeLabel | OutcomeLabel DRAFT→VERIFIED 或保持 PENDING maturity | 当前观察 CONFIRMED；资格、成熟/删失和双重校验规则通过 |
| ExcludeOutcomeLabel | OutcomeLabel DRAFT→EXCLUDED | NOT_ELIGIBLE、RIGHT_CENSORED、UNKNOWN 或策略排除；已 VERIFIED 的标注只能 Invalidate/Supersede，不得事后改写为 EXCLUDED，更不得转成负例 |
| InvalidateOutcomeLabel | OutcomeLabel 当前修订→INVALIDATED | causal Observation/Policy/Control 失效；下游读取门同步阻断 |
| OpenAnalysisCohortSnapshot | 创建 AnalysisCohortSnapshot DRAFT | 批准且版本化的 eligibility、完整 denominator、as_of、岗位/周期/租户和 discovery/train/dev/confirmatory-holdout 分区规则；不引用尚不存在的 Candidate/Study |
| SealAnalysisCohortSnapshot | AnalysisCohortSnapshot DRAFT→SEALED | 成员/排除/成熟/缺失/删失计数、FeatureAvailabilityManifest、PartitionManifest 与 lineage hash 完整 |
| InvalidateAnalysisCohortSnapshot | AnalysisCohortSnapshot SEALED→INVALIDATED | 任一 causal Label/Control/Policy 失效；不可原地修补成员 |
| CreateProfileCandidateRevision | 创建 ProfileCandidateRevision FROZEN | 当前 base ProfileVersion 与 SEALED Cohort；CandidateGenerationManifest 只引用 discovery/train/dev，confirmatory holdout 仍是不可解析 opaque ref 且 access ledger 为空；content hash 冻结 |
| InvalidateProfileCandidateRevision | ProfileCandidateRevision FROZEN→INVALIDATED | base、生成输入、用途、控制或字段政策失效；不得原地修订 |
| PreregisterFeedbackStudy | 创建 FeedbackStudy PREREGISTERED | 当前 FROZEN candidate、SEALED Cohort、holdout 从未打开、假设、baseline/candidate、指标、重要 slice、最小样本/精度、停止规则和 claim type 冻结；CAUSAL 需当前批准且绑定 exact design hash 的 CausalDesignManifest，否则强制 ASSOCIATIONAL |
| OpenConfirmatoryHoldout | FeedbackStudy PREREGISTERED→RUNNING | Snapshot/candidate/plan/hash 与预注册完全一致；首次且仅一次把 opaque holdout ref 解析为该 Study 的限时访问令牌，记录 access receipt、访问主体/时间/目的；打开后禁止改变 Candidate/plan/partition |
| AcceptOfflineEvaluationReport | FeedbackStudy RUNNING→ANALYSIS_READY | AgentRun 当前 SUCCEEDED；checkpoint、tool receipt、manifest、label health、选择性标注/公平/因果限制完整；不等于 Release Eligible 或获批 |
| InvalidateFeedbackStudy | FeedbackStudy 当前状态→INVALIDATED | Cohort、baseline、candidate、用途或评测协议失效 |
| StartAgentRun | 创建 AgentRun，execution 初态即 RUNNING、validity=CURRENT | 消费已打开 confirmatory holdout 的当前 Study；typed tool、固定输入清单、有限步骤/预算、dry-run/trace/checkpoint 策略当前；不存在“已排队”领域态 |
| CommitRunCheckpoint | AgentRun 追加 Checkpoint | 仅在业务步骤/工具回执已持久化后；输入 hash 与 resume_token 当前 |
| RecordToolResult | AgentRun 追加工具尝试与回执 | args/result 最小哈希、provider receipt、attempt、错误与补偿引用；不提交业务事实 |
| CompleteAgentRun | AgentRun RUNNING→SUCCEEDED | 所有必需步骤与对账完成；仅形成候选产物 |
| InvalidateAgentRun | AgentRun validity CURRENT→INVALIDATED，提升 run_epoch 并生成 cancellation token | causal input 或控制变化；旧 resume_token、待执行 tool action 与成功报告不得继续使用；已发生外部效果进入对账/补偿 |
| OpenProfileChangeProposal | ProfileChangeProposal 创建 DRAFT | 当前 FROZEN candidate、base ProfileVersion、ANALYSIS_READY 且 CURRENT Study、job scope、Owner 与用途当前；不把分析完成当发布资格 |
| StageFeedbackStudyEvidence | ProfileChangeProposal DRAFT→EVALUATION_PENDING | 当前 Study/candidate/base/job scope 与报告一致；重验 Study、Run、Cohort、Candidate、control/lineage 均 CURRENT；只冻结 gate evaluation input hash，不创建可审阅/可发布 artifact |
| RecordProfileReleaseGateAssessment | ProfileChangeProposal EVALUATION_PENDING 追加 D0–D4 Gate Assessment | exact proposal/candidate/study/scope/input hash；独立 Owner、authority、evidence/policy、verdict=PASS/FAIL/INCONCLUSIVE/VETO、evaluated_at/expires_at；到达 expires_at 或 authority/evidence/policy 不再 current 时确定性投影为 EXPIRED；每个维度仅一个 current assessment，不可由 HiringOwner/HRBP 覆盖 |
| MarkProfileProposalReleaseEligible | ProfileChangeProposal EVALUATION_PENDING→RELEASE_ELIGIBLE | 现场重验 D0–D4 current assessment 全 PASS、未过期且无 veto，且上游/权限/用途 current；生成不可变 ProfileReleaseEligibilitySnapshot |
| AttachFeedbackStudyEvidence | ProfileChangeProposal RELEASE_ELIGIBLE→REVIEW_READY | 现场重验 Study/Candidate/Cohort/Run、exact D0–D4 与 ProfileReleaseEligibilitySnapshot current PASS/未过期/无 veto；生成绑定 eligibility hash 的不可变审阅 artifact；不创建任务、不批准 |
| OpenProfileChangeReviewTask | ProfileChangeProposal REVIEW_READY 创建唯一当前权威任务，lifecycle 不变 | artifact hash、ProfileReleaseEligibilitySnapshot、D0–D4、HiringOwner/HRBP 权限、截止和版本再次现场重验 current |
| RequestProfileProposalRevision | ProfileChangeProposal RELEASE_ELIGIBLE/REVIEW_READY→EVALUATION_PENDING | 当前 HUMAN reviewer；reason 与 displayed artifact/eligibility hash；撤回当前任务/eligibility/批准/发布授权，候选变化必须新 Candidate + 新 Study |
| RejectProfileChangeProposal | ProfileChangeProposal RELEASE_ELIGIBLE/REVIEW_READY→REJECTED | 当前 HUMAN reviewer；reason、artifact/eligibility hash 与 authority current；拒绝是合法治理出口 |
| SupersedeProfileChangeProposal | ProfileChangeProposal 开放状态→SUPERSEDED | 有当前替代 Proposal 或 base/scope 变化；撤回任务、eligibility、批准与 publication authorization，不改 RoleProfile |
| InvalidateProfileChangeProposal | ProfileChangeProposal validity→INVALIDATED | Study/candidate/gate/用途/控制/权限任一失效，Gate verdict=FAIL/INCONCLUSIVE/VETO，或 assessment 确定性投影为 EXPIRED；同聚合撤回任务、eligibility、批准与 publication authorization |
| RecordProfileProposalApproval | ProfileChangeProposal REVIEW_READY→APPROVED 或保持 REVIEW_READY 直到 quorum | 每次写前现场重验 D0–D4 与上游 current；仅两个不同 `human_actor_id`，分别具 HiringOwner 与 HRBP/ProfileGovernance 当前权限，且签署 exact candidate/study/release_eligibility/scope hash；一人兼双角色不能满足 quorum |
| RecallProfileProposalApproval | ProfileChangeProposal APPROVED/PUBLICATION_AUTHORIZED→EVALUATION_PENDING | 当前批准人撤回且 Proposal 仍 CURRENT；清除批准、发布授权、eligibility 与任务；证据/控制失效必须走 InvalidateProfileChangeProposal，不得只 Recall |
| AuthorizeProfilePublication | ProfileChangeProposal APPROVED→PUBLICATION_AUTHORIZED | 仅当前有发布权限的 HUMAN；现场重验 exact 双人 quorum、D0–D4、candidate/study/base/scope、effective_at、rollback target 与 authority current；生成限时 ProfilePublicationAuthorization；Agent/Service/CONTROL_PLANE 不得代签 |
| PrepareProfilePublication | RoleProfile ACTIVE 下创建不可变 ProfileVersion 与 PublicationRevision=PENDING_SYNC；current pointer 不变 | 仅 CONTROL_PLANE 消费 current ProfilePublicationAuthorized；重验 D0–D4、base/current、future scope、authorization hash、safety_epoch；冻结 PublicationSyncRequirementSet 并发 ProfilePublicationPrepared，由消费者逐条创建 required actions |
| RequestProfilePublicationSyncAction | 创建 ActionExecution REQUESTED | 消费 ProfilePublicationPrepared；一个 required target/action 一条聚合命令，携带 publication revision、safety_epoch、requirement hash、target revision 与确定性 payload hash；不可批量双写 RoleProfile |
| AcceptProfilePublicationSyncReceipt | RoleProfile 为 PENDING_SYNC PublicationRevision 追加当前 required receipt 引用 | 消费 AutomationActionSucceeded；action/target/revision/policy/payload 与 RequirementSet 一致，属于当前 safety_epoch；迟到、非 required、重复异负载或外部 revision 不一致拒绝 |
| CommitProfilePublication | RoleProfile 的 PublicationRevision PENDING_SYNC→ACTIVE，并在同一事务更新 future-scope current pointer；旧 ACTIVE→SUPERSEDED | 仅 CONTROL_PLANE；全部 required receipts 当前且完整，receipt set hash、authorization、D0–D4、base/current、scope、expected_version、safety_epoch 现场重验；FROZEN、CANCELLED、旧 epoch 或 Agent/普通 Service 拒绝 |
| FreezeProfilePublication | RoleProfile ACTIVE→FROZEN（已 FROZEN 同 causal token 幂等），提升 safety_epoch，并 CANCEL 当前 PENDING_SYNC/生成 cancellation token | P0 公平、泄漏、跨租户、证据/用途/控制失效或影响未知；批准确定性安全规则可执行；立即阻断新 pin、Prepare/Commit，失效旧授权与 pending receipts，并取消/补偿未结 required sync actions；影响边界未知时由安全编排器对 tenant 内可能命中的每个 RoleProfile 分别发单聚合 Freeze 命令 |
| CancelProfilePublicationSyncAction | ActionExecution REQUESTED/AUTHORIZED/RETRYING→CANCELLED 或进入补偿 | 消费 ProfilePublicationFrozen 的 cancellation token；按 publication revision + old safety_epoch 命中；已成功外部效果必须对账/补偿，迟到成功不能恢复 pending publication |
| AuthorizeProfileRollback | RoleProfile 在 FROZEN 追加 HUMAN 回滚授权 | 绑定当前 safety_epoch；目标为此前批准且当前允许版本；影响范围、原因、current D0–D4 安全复核与 A0 恢复计划完整；不直接改 pointer |
| RollbackProfilePublication | RoleProfile FROZEN→ACTIVE 并再次提升 safety_epoch；旧 current PublicationRevision→ROLLED_BACK，创建 operation=ROLLBACK 的新 ACTIVE PublicationRevision 指向先前批准版本并原子更新 current pointer | 仅 CONTROL_PLANE 消费 exact current HUMAN rollback authorization；expected_version、冻结 epoch/影响清单/target hash 当前；提升后的 epoch 使冻结期授权/动作永久过期，所有受影响自动化动作恢复 A0；不改历史案件/评价/版本 |
| AssignProfileExposure | 创建/重放 ProfileExposureLedger ASSIGNED | 当前批准 A2 Study、exact CausalDesignManifest、future-scope Case、稳定 allocation policy、assignment unit 与幂等键；分配发生在 outcome/采纳前，不按用户采纳自选 |
| RecordActualProfileExposure | ProfileExposureLedger ASSIGNED→EXPOSED/NOT_EXPOSED | 消费 Case 当前 ScreeningInputManifest/ProfileVersion pin；实际暴露与 assignment 分开记录 |
| RecordProfileExposureContamination | ProfileExposureLedger 追加 CONTAMINATED/DEVIATED revision | 交叉接触、非依从、人工迁移或策略偏离来源可证明；不覆盖原 assignment/exposure |

### 12.1 跨聚合 seam

INV-CONTROL-SINGLE-AGGREGATE：下表每个命令事务只改变“唯一目标聚合”并写 Outbox；消费者必须重新加载全部当前事实，再用 expected_version 与幂等键提交下一条命令。

| 源命令 | 唯一目标聚合 | 发出事件 | 消费命令 | 唯一目标聚合 |
|---|---|---|---|---|
| StartInterview | InterviewSession | InterviewSessionStarted | MarkInterviewRoundInProgress | InterviewRound |
| CreateInterviewEvidenceHandoff | InterviewSession | InterviewEvidenceHandoffCreated | AcceptInterviewEvidenceHandoff | InterviewRound |
| InvalidateInterviewEvidenceHandoff | InterviewSession | InterviewEvidenceHandoffInvalidated | InvalidateRoundEvidenceInput | InterviewRound |
| InvalidateFinalAssessmentPackage | FinalAssessmentPackage | FinalAssessmentPackageInvalidated | RecallFinalAssessmentReadiness | ApplicationCase |
| RecordFinalDecision | ApplicationCase | FinalHiringDecisionRecorded | ReferenceHiringDecisionObservation | OutcomeObservation |
| SupersedeFinalDecision | ApplicationCase | FinalHiringDecisionSuperseded | CorrectOutcomeObservation；若新决定不允许作为该用途观察则 InvalidateOutcomeObservation | OutcomeObservation（每个被引用 observation 各一命令） |
| ConfirmOutcomeObservation | OutcomeObservation | OutcomeObservationConfirmed | DeriveOutcomeLabelDraft | OutcomeLabel |
| CorrectOutcomeObservation | OutcomeObservation | OutcomeObservationCorrected | InvalidateOutcomeLabel | 每个依赖 OutcomeLabel 各一命令 |
| InvalidateOutcomeObservation | OutcomeObservation | OutcomeObservationInvalidated | InvalidateOutcomeLabel | 每个依赖 OutcomeLabel 各一命令 |
| InvalidateOutcomeLabel | OutcomeLabel | OutcomeLabelInvalidated | InvalidateAnalysisCohortSnapshot | 每个依赖 AnalysisCohortSnapshot 各一命令 |
| SealAnalysisCohortSnapshot | AnalysisCohortSnapshot | AnalysisCohortSnapshotSealed | CreateProfileCandidateRevision | ProfileCandidateRevision |
| CreateProfileCandidateRevision | ProfileCandidateRevision | ProfileCandidateRevisionFrozen | PreregisterFeedbackStudy | FeedbackStudy |
| OpenConfirmatoryHoldout | FeedbackStudy | ConfirmatoryHoldoutOpened | StartAgentRun | AgentRun（创建即 RUNNING） |
| CompleteAgentRun | AgentRun | AgentRunSucceeded | AcceptOfflineEvaluationReport | FeedbackStudy |
| AcceptOfflineEvaluationReport | FeedbackStudy | FeedbackStudyAnalysisReady | OpenProfileChangeProposal | ProfileChangeProposal |
| AuthorizeProfilePublication | ProfileChangeProposal | ProfilePublicationAuthorized | PrepareProfilePublication | RoleProfile |
| PrepareProfilePublication | RoleProfile | ProfilePublicationPrepared | RequestProfilePublicationSyncAction | 每个 required ActionExecution 各一命令 |
| 外部 required sync 成功并落库 | ActionExecution | AutomationActionSucceeded | AcceptProfilePublicationSyncReceipt | RoleProfile |
| CommitProfilePublication | RoleProfile | ProfilePublicationCommitted | 新 Case pinning / 暴露记录编排 | ApplicationCase 或 ProfileExposureLedger 各自独立命令 |
| InvalidateAnalysisCohortSnapshot | AnalysisCohortSnapshot | AnalysisCohortSnapshotInvalidated | InvalidateProfileCandidateRevision | 每个依赖 ProfileCandidateRevision 各一命令 |
| InvalidateAnalysisCohortSnapshot | AnalysisCohortSnapshot | AnalysisCohortSnapshotInvalidated | InvalidateAgentRun | 每个依赖 AgentRun 各一命令 |
| InvalidateAnalysisCohortSnapshot | AnalysisCohortSnapshot | AnalysisCohortSnapshotInvalidated | InvalidateFeedbackStudy | 每个依赖 FeedbackStudy 各一命令 |
| InvalidateProfileCandidateRevision | ProfileCandidateRevision | ProfileCandidateRevisionInvalidated | InvalidateFeedbackStudy | 每个依赖 FeedbackStudy 各一命令 |
| InvalidateAgentRun | AgentRun | AgentRunInvalidated | InvalidateFeedbackStudy | 每个依赖 FeedbackStudy 各一命令 |
| InvalidateFeedbackStudy | FeedbackStudy | FeedbackStudyInvalidated | InvalidateProfileChangeProposal | 每个依赖 ProfileChangeProposal 各一命令；适用于 DRAFT/EVALUATION_PENDING/RELEASE_ELIGIBLE/REVIEW_READY/APPROVED/PUBLICATION_AUTHORIZED |
| InvalidateProfileChangeProposal | ProfileChangeProposal | ProfileChangeProposalInvalidated | FreezeProfilePublication（仅当 current/pending publication lineage 命中） | RoleProfile |
| ApplyProcessingRestriction / ApplyDeletionDirective | ProcessingControl | ProcessingRestrictionApplied / DeletionDirectiveApplied | InvalidateOutcomeObservation / InvalidateAnalysisCohortSnapshot / InvalidateProfileCandidateRevision / InvalidateAgentRun / InvalidateFeedbackStudy / InvalidateProfileChangeProposal | 每个被血缘命中的聚合各一命令；不得批量双写 |
| FreezeProfilePublication | RoleProfile | ProfilePublicationFrozen | CancelProfilePublicationSyncAction | 每个未结 required ActionExecution 各一命令 |

同聚合的后续命令不是跨聚合 seam，不放进上表：`RecordOutcomeSourceAssertion → ReconcileOutcomeObservation`、`PreregisterFeedbackStudy → OpenConfirmatoryHoldout`、`OpenProfileChangeProposal → StageFeedbackStudyEvidence`、`RecordProfileReleaseGateAssessment(FAIL/INCONCLUSIVE/VETO 或 expiry 投影) → InvalidateProfileChangeProposal`、`AcceptProfilePublicationSyncReceipt → CommitProfilePublication`、`AuthorizeProfileRollback → RollbackProfilePublication`。这些命令仍必须分别携带 expected_version/幂等键并重验当前状态；尤其 `OpenConfirmatoryHoldout` 只认本 FeedbackStudy 内已冻结的 preregistration，不能被投影成 Cohort 的反向依赖。

## 13. 事件信封

所有领域事件包含：

| 字段 | 含义 |
|---|---|
| event_id / event_type / schema_version | 事件身份与结构版本 |
| tenant_id | 租户边界 |
| aggregate_type / aggregate_id / aggregate_version | 权威聚合及版本 |
| case_id | Case-bound G1/G2 事件必填；G3 多案件分析事件不得伪造单一 case_id |
| scope_ref | G3 必填：job/cycle/purpose、cohort/study/publication scope 或明确 Study × Case exposure scope 的受控引用与哈希 |
| occurred_at / recorded_at | 业务发生与系统记录时间 |
| actor_ref | 人、系统或服务主体 |
| correlation_id / causation_id / trace_id | 业务链路 |
| source_system / source_event_id / source_resource_version | 外部来源去重与对账 |
| data_classification | 数据分级 |

事件总线只放稳定 ID、版本、哈希和受控摘要；不得放简历全文、录音、完整逐字稿或候选人联系方式。

## 14. 领域事件目录

### 14.1 收件与筛选

| 事件 | 触发 | 必要业务字段 | 主要消费者 |
|---|---|---|---|
| ResumeSubmissionReceived | 来源附件去重接收 | submission_id、source_ref、document_ref、sha256、requisition_hint | 解析器、收件 SLA |
| StructuredResumeVersionCreated | 解析/纠正落库 | resume_version、source_document_refs、parser_or_editor、field_locator_manifest、quality | 身份/岗位路由、审计 |
| ApplicationRoutingResolved | 当前人、岗位、周期唯一 | routing_version、person_id、requisition_id、cycle_id、method、conflict_check_ref | 案件中心 |
| ApplicationRoutingReviewRequired | 路由冲突/缺失 | routing_version、reason_code、candidate_refs、due_at | 异常中心 |
| ApplicationRoutingSuperseded | 有权限纠正当前路由 | old/new routing_version、reason、impact_manifest_ref、authority_ref | 案件/动作失效器 |
| ResumeSubmissionCaseLinkSuperseded | 已应用路由的投递关系被纠正 | submission_id、old_case_id、old/new routing_version、reason、impact_manifest_ref、authority_ref、cancellation_token | 旧材料/任务/动作失效器、正确开案门 |
| MisroutedApplicationCaseClosed | 误路由案件完成关闭裁决 | case_id、immutable_application_key、reason、human_or_policy_authority、remaining_source/effect refs | 正确开案门、补偿、审计 |
| ApplicationCaseOpened | 开案成功 | case_id、application_key、submission_ids | 案件编排器 |
| ResumeSubmissionAttachedToCase | 同一 ApplicationKey 新来源附加 | case_id、submission_id、resume_version、attachment_reason | 筛选输入重验 |
| ScreeningInputPinned | 筛选门通过 | manifest_id/hash、resume/profile/field/policy versions | 匹配引擎、案件审计 |
| MatchAssessmentReady | 匹配材料发布门通过 | assessment_id/version、input_manifest_hash、result_band、evidence_coverage | 案件中心 |
| CurrentMatchAssessmentPinned | Case 提交唯一当前指针 | assessment_id/version、input_manifest_hash、request_generation | 部门任务、页面投影 |
| CurrentMatchAssessmentInvalidated | 输入或政策版本失效 | assessment_id/version、reason、causal_input_ref/version、replacement_ref | 决策任务撤回、案件中心 |
| DepartmentDecisionRequestOpened | 当前匹配材料进入人审 | request_id/revision、assessment_id/version、allowed_decisions、reviewers、due_at | 产品任务、SLA、通知 |
| DepartmentDecisionRequestSuperseded | 材料/Owner/权限变化 | request_id/revision、reason、replacement_request_ref | 任务撤回、通知补偿 |
| DepartmentDecisionRequestHeld | HUMAN 提交 HOLD | request_id/old/new revision、decision_ref、reason、revisit_at、generation、cancellation_token | 产品任务、SLA、排队催办取消 |
| DepartmentDecisionRequestResumed | HOLD 到期且当前门通过 | request_id/old/new revision、generation、revisit_basis、due_at | 产品任务、SLA、通知 |
| DepartmentReminderOrdinalAdvanced | 当前催办授权生成 | request_id/revision、generation、ordinal、channel、not_before | 动作控制面 |
| DepartmentDecisionRecorded | 有权限人提交 | decision_id、decision_type、human_actor、basis_ref、revisit_at | 案件中心、面试流程 |
| DepartmentDecisionRequestClosed | 当前决定已生效或请求撤销 | request_id/revision、reason、decision_ref、closed_at | 产品任务、SLA、通知 |

### 14.2 面试、证据与评价

| 事件 | 触发 | 必要业务字段 | 主要消费者 |
|---|---|---|---|
| InterviewPlanPinned | 案件进入面试时锁定计划 | plan_id/version、graph_hash、required/optional/conditional steps、authority_ref | 轮次编排、审计 |
| InterviewPlanAmended | 有权限的人批准新版本 | old/new version、change_manifest_ref、affected_round_refs、authority_ref | 轮次、简报、终面包失效器 |
| InterviewRoundActivated | 前置轮次满足 | round_id、plan_step_id、sequence、scorecard_version | 约面编排器 |
| InterviewRoundRepeated | 人工决定要求重复一轮 | new_round_id、source_round_id、decision_id、reason、attempt_ordinal | 轮次编排、控制塔 |
| RoundWaiverRecorded | 有权限的人豁免适用轮次 | waiver_id/version、round_id、scope、reason、human_actor、authority_snapshot、evidence_impact | 完整性、终面包 |
| RoundWaiverSuperseded | 豁免被纠正/计划变化 | waiver_id/version、reason、replacement_ref | 完整性、终面包失效器 |
| CandidateCoordinationRequestOpened | 当前 Session 可约面 | request_id/revision、constraints_ref、candidate_timezone、token_policy、due_at | 候选人协调页、SLA |
| CandidateCoordinationRequestExpired | 请求过期/被替代 | request_id/revision、reason、replacement_ref | 协调页、通知撤回 |
| SchedulingProposalPublished | 当前约束/忙闲形成提案 | proposal_id/version、constraint/availability refs、slot_refs、expires_at | 候选人协调页 |
| SchedulingProposalSuperseded | 忙闲/参与人/控制变化 | proposal_id/version、reason、replacement_ref | 协调页、预约编排 |
| CandidateSlotSelectionRecorded | 候选人选当前提案 | proposal_id/version、selection_action_id、slot_ref、candidate_actor | 预约修订器 |
| AppointmentRevisionProposed | 重验后形成预约意图 | session_id、appointment_revision、slot/participant/resource requirement refs、previous_booking_ref | 动作控制面 |
| AppointmentRevisionAborted | 当前修订无法提交 | appointment_revision、reason、partial_resource_refs、compensation_refs | 对账、协调页、异常 |
| InterviewBookingCommitted | 当前修订所需外部写入均有回执 | session_id、appointment_revision、booking_receipt_set_hash、event/meeting/invitation refs | 轮次投影、通知、审计 |
| InterviewBookingInvalidated | 当前预定不再有效 | session_id、booking_ref/revision、reason、replacement_revision_ref | 轮次回 SCHEDULING、对账 |
| InterviewBookingCancelled | 外部资源取消/撤销完成 | session_id、booking_ref/revision、cancellation_receipts、reason | 轮次、协调页、审计 |
| RecordingNoticeDelivered | 当前告知写入/展示有回执 | session_id、participant_id、purposes、notice_version、channel、receipt_ref | 采集选择、审计 |
| ParticipantConsentRecorded | 参与人记录当前选择 | session_id、participant_id、purposes、decision、notice_version、receipt_ref | 采集闸门 |
| ParticipantConsentWithdrawn | 撤回当前目的 | session_id、participant_id、purposes、receipt_revision、effective_at | 采集停止、血缘处置、异常 |
| SessionParticipantJoined | 当前会话出现参与人 | session_id、participant_id、presence_revision、source_ref、joined_at | 采集闸门、审计 |
| SessionParticipantLeft | 当前会话参与人离开 | session_id、participant_id、presence_revision、source_ref、left_at | 采集闸门、审计 |
| CaptureGateEvaluated | 当前参与人/目的/控制重验 | session_id、gate_revision、participant/purpose/notice/consent/control refs、result、reason_codes | 会话、采集控制面 |
| InterviewSessionStarted | 当前会话开始 | appointment_revision、participant_snapshot_ref、capture_mode、started_at | 轮次、采集；不等于采集请求或开始 |
| CaptureStartRequested | 当前闸门允许并写出开始动作 | session_id、attempt_revision、gate_revision、action_id、provider_resource_revision | ActionExecution、对账 |
| CaptureStarted | 平台开始采集回执当前 | session_id、gate_revision、action_id、provider_resource_revision、started_at | 对账、审计 |
| CaptureStopRequested | 撤回/晚加入/结束/限制/异常要求停止 | session_id、attempt_revision、gate/control refs、action_id、reason、effective_at | ActionExecution、隔离、对账 |
| CaptureStopped | 平台停止采集回执当前 | session_id、gate_revision、action_id、provider_resource_revision、reason、stopped_at | 对账、血缘处置 |
| CaptureStateMismatchDetected | 平台状态未知、意外开始或无法停止 | session_id、attempt/gate/control refs、observed_state、expected_state、P0 exception_ref | 熔断、停止、事件响应 |
| InterviewSessionEnded | 当前会话结束 | ended_at、outcome、capture_mode、capture_state、observed_start_missing | 轮次、G1 交接 |
| InterviewEvidenceHandoffCreated | 当前 G1 输入完整 | handoff_id/revision、case/round/session/appointment refs、capture_mode、evidence_route、input_manifest_hash、capture_history/segment/final_reconciliation refs、asset_or_notes_refs | G1a 接收器 |
| InterviewEvidenceHandoffSuperseded | 替代输入成为当前 revision | old/new handoff refs、reason、causal_ref/version、superseded_at | G1a 读取门、轮次、审计 |
| InterviewEvidenceHandoffInvalidated | causal input 不再允许使用 | handoff_id/revision、reason、causal_ref/version、replacement_ref、invalidated_at | G1a 读取门、轮次、派生物失效器 |
| InterviewEvidenceHandoffAccepted | G1a 幂等接收 | handoff_id/revision、g1_input_ref、accepted_at | 轮次、控制塔 |
| RoundEvidenceInputInvalidated | 已接受 handoff 失效 | round_id、handoff_id/revision、reason、causal_ref/version、replacement_ref | 评价/确认/完成件失效器 |
| CompletedInterviewImported | G1a 受控导入门通过 | round_id、session_id、from/to round state、scorecard_version、source_artifact_sha256 | 轮次、证据管线；不得伪造排期/进行中事实 |
| RecordingAssetAvailable | 录音完整入库 | artifact_id/type/version、checksum、consent/control snapshot refs、retention_class | 转写/证据 |
| AuthorizedNotesAvailable | 批准的笔记证据可用，不声明会议从未采集 | notes_id/version、author/authority refs、source_scope、content_hash、retention_class | 证据处理；不得伪造逐字稿或抹去采集历史 |
| TranscriptReady | 转写版本完成 | transcript_id/version、language、speaker_map_version、quality | 评价生成 |
| TranscriptQualityRejected | 质量门失败 | failure_codes、affected_ranges、retryable | 重试、异常 |
| EvaluationDraftGenerated | 评价草稿生成 | evaluation_id/version、evidence_set_hash、scorecard/model/prompt version | 校验器 |
| EvaluationValidationFailed | 证据/策略失败 | failure_codes、affected_claim_ids、retryable | 重试、异常 |
| EvaluationPackageReadyForReview | 评价过发布门 | evaluation_id/version、evidence_coverage、review_policy、due_at | 面试官工作台 |
| EvaluationReviewSubmitted | Reviewer 提交 | review_id、reviewer、disposition、edit_diff_ref | 评价聚合 |
| EvaluationConfirmed | 确认策略满足 | evaluation_id/version、confirmation_ids | 轮次 |
| RoundDecisionRecorded | 授权人提交轮次结果 | decision_id/type、human_actor、evaluation version | 轮次、案件 |
| InterviewRoundCompleted | 确认与决定都完成 | round_id/version、completion_record_id/version、evaluation_id/version、decision_id/version、evidence_set_hash、completed_at | 下一轮、简报、终面包 |
| RoundCompletionRecordInvalidated | 评价/决定/证据不再当前有效 | completion_record_id/version、causal_input_ref/version、reason、replacement_ref | 轮次编排、简报/终面包失效器 |
| InterviewBriefGenerated | 当前缺口生成简报草稿 | brief_id/version、round_id、audience_revision、input_manifest_hash、scorecard/policy/model/prompt version | 简报校验器 |
| InterviewBriefValidationFailed | 披露/证据/问题策略失败 | brief_id/version、failure_codes、affected_question_ids、retryable | 质量、隐私、异常 |
| InterviewBriefPublished | 简报通过门成为当前版本 | brief_id/version、round_id、audience_revision、input_manifest_hash、due_at | 面试官任务、通知 |
| InterviewBriefFeedbackRecorded | 指定面试官反馈建议问题 | brief_id/version、question_id、disposition、edit_diff_ref、actor | 简报质量，不进入候选人评价 |
| InterviewBriefInvalidated | Round/受众/输入/策略变化 | brief_id/version、reason、causal_ref/version、replacement_ref | 任务撤回、控制塔 |
| CrossRoundIssueDetected | 发现问题候选 | issue_id/version、issue_key、causal_input_refs/versions、claim/evidence refs | 问题中心 |
| CrossRoundIssueClassified | 人/批准规则确定影响 | issue_id/version、type、severity、blocking、classifier/policy、owner、due_at | 包完整性、控制塔 |
| CrossRoundIssueResolved | 有权限人提交解决 | issue_id/version、resolution_type、resolution_ref、resolver、resolved_at | 包重验、审计 |
| CrossRoundIssueSuperseded | causal input 变化 | issue_id/version、reason、replacement_issue_ref | 问题中心、包重验 |
| FinalAssessmentCompilationRequested | 当前输入满足初步完整性 | compilation_id、input_manifest_hash、plan/profile/scorecard version、compiler_policy | 编译器、成本/SLA |
| FinalAssessmentPackageReady | 多轮完整性和发布门通过 | package_id/version、input_manifest_hash、completion/waiver refs、issue refs、content_hash、nonblocking_flags | 案件、最终审阅任务 |
| FinalAssessmentPackageInvalidated | 任一输入不再当前有效 | package_id/version、reason、causal_input_ref/version、replacement_ref | 案件、任务撤回、重编译 |
| FinalAssessmentReviewTaskCreated | 当前包进入权威产品待办 | task_id/revision、package_id/version、final_owner_ref/revision、due_at | 产品收件箱、通知 |
| FinalAssessmentReviewTaskDelivered | 安全通知获得回执 | task_id/revision、action_id、channel、receipt_ref | SLA、可信托管指标 |
| FinalAssessmentReviewTaskRetracted | 包/Owner/控制态变化 | task_id/revision、reason、cancellation_token | 产品收件箱、通知补偿 |
| FinalAssessmentMarkedReady | 包和权威任务当前有效 | package_id/version、task_id/revision、readiness_check_ref、marked_at | 案件、可信托管指标 |
| FinalAssessmentReadinessRecalled | 当前终面包失效后案件回退 | case_id、invalidated_package_ref、old/new case version、reason | 任务撤回、重编译、控制塔 |
| FinalHiringDecisionRecorded | 有权限的人提交当前最终决定 | decision_id/revision、decision_type、human_actor、authority_snapshot_id、package_id/version/content_hash、basis_ref、decided_at | Outcome Registry、经营指标；不得复制决定所有权 |
| FinalHiringDecisionSuperseded | 有权限的人纠正当前最终决定 | old/new decision refs、reason、human_actor、authority_snapshot、superseded_at | G3 派生物失效器、审计 |

### 14.3 动作、异常与控制

| 事件 | 触发 | 必要业务字段 | 主要消费者 |
|---|---|---|---|
| AutomationActionRequested | 编排器提出动作 | action_id/type/category、target_ref/revision、lifecycle_epoch、processing_control_set_hash、routing_revision、payload_hash、risk、policy | 动作控制面 |
| AutomationActionAuthorized | 策略/人批准 | authorization_type、approver、policy_version、limits、authorized_revision_set | 连接器 |
| AutomationActionSucceeded | 外部回执落库 | attempt_no、connector_receipt、external_resource_ref | 聚合、控制塔 |
| AutomationActionFailed | 一次尝试失败 | error_code、retryable、next_retry_at、connector_state | 重试、异常 |
| AutomationActionCancelled | 控制事实使动作失效 | reason、cancellation_token、cancelled_at | 连接器 |
| ExceptionBundleOpened | 需要人判断或重试耗尽 | exception_id、scope、code/severity、facts、options、owner、due_at、resume_token | 控制塔 |
| ExceptionBundleResolved | 人提交方案 | resolution_id、selected_option、resolver、supplied_refs、resume_token | 原编排器 |
| CasePaused | 人/策略/权利请求暂停 | reason、actor、cancellation_token | 所有执行器 |
| CaseResumed | 恢复门通过 | actor、reason、new_resume_token | 案件编排器 |
| CandidateWithdrawalRecorded | 可证明的候选人对明确案件撤回生效 | candidate_ref、case_ref、source_ref、case_epoch、effective_at | 案件关闭、动作取消、预约补偿；不默认扩到其他案件 |
| ProcessingRestrictionApplied | 带作用域限制生效 | data_subject_ref、case/session refs、purpose/operation/data scopes、control_revision、effective_at | 匹配范围内读取/生成/动作门 |
| ProcessingRestrictionReleased | 有效解除限制 | data_subject_ref、scope、old/new control_revision、authority/ref、effective_at | 受控恢复，不扩大范围 |
| DeletionDirectiveApplied | 带作用域删除指令进入执行 | data_subject_ref、case/session refs、purpose/operation/data scopes、control_revision、retention_exception_refs、due_at | 匹配血缘删除、派生物失效、审计 |
| SlaDeadlineBreached | 当前 generation 到期 | clock_id/type、target_ref、generation、due_at、owner | 催办、异常 |

AutomationActionSucceeded 只证明某次连接器动作获得回执；它不能单独提交 ApplicationCase、InterviewRound 或 InterviewBooking 等业务事实。拥有该事实的聚合必须加载完整当前回执集和控制状态后再执行领域命令。

### 14.4 结果回流与画像治理

| 事件 | 触发 | 必要业务字段 | 主要消费者 |
|---|---|---|---|
| OutcomeSourceAssertionRecorded | 批准来源断言按来源键/修订幂等接收 | observation_id、OutcomeReconciliationKey/hash、source system/business key/revision、authority/purpose/job/window refs、old/new source_set_hash、effective/observed/received time | canonical reconciler、血缘审计；不等于观察已确认 |
| OutcomeObservationReconciled | 对完整当前来源集执行解析 | observation old/new refs、OutcomeReconciliationKey/hash、source assertion refs、source_set_hash、resolution policy/version/hash、result=PROVISIONAL/DISPUTED、conflict refs | Steward 任务、确认门；替代旧 current 时同事务另发 OutcomeObservationCorrected |
| OutcomeObservationConfirmed | 当前 canonical 观察被确认 | observation ref/revision、OutcomeReconciliationKey/hash、source_set/resolution hash、confirmer/policy、authority snapshot、confirmed_at | 标注器 |
| OutcomeObservationDisputed | 来源冲突或可信质疑 | observation ref/revision、source_set_hash、conflict refs、reason、owner、due_at | Steward 任务、异常 |
| OutcomeObservationCorrected | 当前 canonical 观察追加纠正修订 | old/new refs、old/new source_set/resolution hashes、reason、authority、impact lineage ref、corrected_at | 每个依赖 Label 的失效命令 |
| OutcomeObservationInvalidated | 当前 canonical 观察不再允许使用 | observation ref/revision、OutcomeReconciliationKey/hash、source_set/resolution hash、reason、control/purpose/deletion refs、invalidated_at | 每个依赖 Label 的失效命令 |
| OutcomeLabelDrafted | 标注策略对当前 canonical 观察形成草稿 | label_id/revision、observation/source_set/resolution refs、policy/purpose、maturity_window、proposed target、excluded-signal check | Label verifier |
| OutcomeLabelVerified | 标注与成熟裁决通过 | label ref/revision、lifecycle、maturity、verifier/policy、basis refs | Cohort builder |
| OutcomeLabelExcluded | 观察不适合作为该用途标注 | label ref/revision、NOT_ELIGIBLE/RIGHT_CENSORED/UNKNOWN reason、policy | Cohort denominator、质量看板 |
| OutcomeLabelInvalidated | causal input 失效 | label ref/revision、causal observation/policy/control ref、reason、invalidated_at | Cohort 失效器 |
| AnalysisCohortSnapshotOpened | 当前 eligibility 规则创建 DRAFT 队列 | snapshot_id/revision、job/cycle/tenant/purpose scope、as_of、denominator/eligibility refs、processing control/lineage epoch | 数据质量门；不引用 Candidate/Study |
| AnalysisCohortSnapshotSealed | 完整分母与分区封存 | snapshot ref/revision、denominator/member/excluded/mature/missing/censored counts、feature/partition manifests、lineage hash | ProfileCandidateRevision builder；此时不创建 Study、不打开 holdout |
| AnalysisCohortSnapshotInvalidated | 当前快照血缘失效 | snapshot ref/revision、causal label/control/policy ref、reason、invalidated_at | Candidate/AgentRun/Study 各自失效命令、看板当前性 |
| ProfileCandidateRevisionFrozen | 仅用 discovery/train/dev 形成不可变候选修订 | candidate ref/hash、base profile ref、SEALED cohort/partition refs、CandidateGenerationManifest hash、prohibited/proxy checks、frozen_at | FeedbackStudy preregistration |
| ProfileCandidateRevisionInvalidated | 候选生成血缘不再当前 | candidate ref/hash、causal base/cohort/control/policy ref、reason、invalidated_at | 每个依赖 Study 的失效命令 |
| FeedbackStudyPreregistered | candidate 已冻结后研究计划冻结 | study_id/revision、SEALED cohort、FROZEN candidate、hypothesis、baseline、metrics/slices/minimum sample/stop rules、claim type、CausalDesignManifest/approval ref/hash 或 ASSOCIATIONAL 限制、holdout_unopened=true、preregistered_at | confirmatory holdout 开门、治理审计 |
| ConfirmatoryHoldoutOpened | exact 预注册研究首次打开 holdout | study/cohort/candidate/plan/partition refs/hashes、access receipt、actor/purpose、opened_at、first_access=true | AgentRun 编排器、审计；后续 candidate/plan 变化必须新 Study |
| AgentRunStarted | 固定输入长任务开始 | run_id/kind/run_epoch、input manifest hash、plan/budget/tool policy/checkpoint policy、started_at | 活动轨、SLA |
| AgentRunCheckpointCommitted | 安全恢复点提交 | run_id/run_epoch、step_id、input hash、tool/version、args/result hash、attempt、next step、resume token | 恢复器、审计 |
| AgentToolResultRecorded | 工具结果/回执持久化 | run/step/attempt、tool/version、args/result hash、provider receipt/error/compensation refs | 对账、checkpoint |
| AgentRunSucceeded | 所有固定步骤与对账完成 | run_id、output artifact refs/hashes、checkpoint/receipt manifest、completed_at | FeedbackStudy；不等于业务批准 |
| AgentRunInvalidated | 运行输入不再当前 | run_id、old/new run_epoch、causal ref/version、reason、cancellation token、invalidated_at | 待执行工具取消/补偿、Study invalidation、Proposal 读取门 |
| FeedbackStudyAnalysisReady | 当前离线报告被研究聚合接受 | study/run/snapshot/candidate refs、report id/hash、label health、metrics/confidence intervals、selective-label/generalization/fairness/proxy/causal/purpose limitations、accepted_at | ProfileChangeProposal；不等于 RELEASE_ELIGIBLE |
| FeedbackStudyInvalidated | 研究证据失效 | study ref/revision、causal cohort/candidate/run/control ref/version、reason、invalidated_at | 每个依赖 Proposal 的 Invalidate 命令；Proposal 事件再决定是否 Freeze，不能跳级双写 |
| ProfileChangeProposalOpened | 已有确认评测后建立治理流程 | proposal_id/revision、candidate/study/base profile/job scope refs/hashes、owners、purpose | Study evidence staging；不生成 Candidate |
| ProfileStudyEvidenceStaged | 当前研究证据冻结为 Gate 输入 | proposal/study/report/candidate/base/scope refs/hashes、limitations、current upstream/control check hash、gate input hash | D0–D4 evaluator；不表示可审阅 |
| ProfileReleaseGateAssessmentRecorded | 一个 D0–D4 维度形成当前裁决 | proposal/candidate/study/scope/input hash、gate D0..D4、verdict=PASS/FAIL/INCONCLUSIVE/VETO、owner/authority、evidence/policy refs、evaluated/expires at、assessment hash；EXPIRED 由当前时间/权限/证据/策略确定性投影 | Release eligibility projector、失效器 |
| ProfileReleaseEligibilityEstablished | 五个当前 Gate 全部通过 | proposal/candidate/study/scope/input hashes、D0–D4 assessment refs/hashes、evaluated/expires at、eligibility hash | AttachFeedbackStudyEvidence；不直接开任务/批准 |
| ProfileReleaseEligibilityInvalidated | 任一 Gate/上游/用途/权限不再 current | proposal/eligibility ref/hash、causal assessment/upstream/control ref、reason、invalidated_at | Proposal invalidation |
| ProfileStudyEvidenceAttached | current ReleaseEligibility 下形成不可变审阅 artifact | proposal/study/report/candidate/base/scope/artifact/eligibility refs/hashes、D0–D4 current check hash、limitations | 同聚合 ReviewReady 投影 |
| ProfileChangeProposalReviewReady | current ReleaseEligibility 进入人审 | proposal/artifact/eligibility refs/hashes、D0–D4 current check hash、risk/scope/rollback summary、reviewers、due_at | Profile review task |
| ProfileChangeReviewTaskOpened | 唯一产品内权威审阅任务创建 | task id/revision、proposal/artifact hash、HiringOwner/HRBP authority revisions、due_at | 画像治理工作台、通知 |
| ProfileProposalRevisionRequested | 当前 HUMAN 要求修改 | proposal/artifact/eligibility refs/hashes、human actor/authority、reason、requested_at | 任务撤回、治理工作台 |
| ProfileChangeProposalRejected | 当前 HUMAN 拒绝 | proposal/artifact/eligibility refs/hashes、human actor/authority、reason、rejected_at | 治理工作台、审计 |
| ProfileChangeProposalSuperseded | 新 Proposal 或 base/scope 替代旧提案 | old/new proposal refs、reason、superseded_at | 任务/eligibility/批准/publication authorization 撤回 |
| ProfileChangeProposalInvalidated | Study/candidate/gate/用途/控制/权限失效 | proposal/candidate/study/eligibility refs/hashes、causal ref/version、reason、invalidated_at | current/pending publication lineage Freeze、任务投影 |
| ProfileApprovalSubmitted | 一位有权限人批准当前版本 | proposal/candidate/study/release eligibility/scope hashes、human actor id/role/authority、submitted_at | distinct-human quorum 计算 |
| ProfileChangeProposalApproved | 双人 distinct HUMAN quorum 满足 | proposal/candidate/study/release eligibility/scope hashes、两个不同 human_actor_id/role/approval refs、rollback target、approved_at | 发布授权人任务；不直接发布 |
| ProfileChangeProposalApprovalRecalled | 当前批准人撤回 | proposal/approval/authorization refs、human actor/authority、reason、recalled_at | 任务投影；证据失效仍走 ProposalInvalidated |
| ProfilePublicationAuthorized | 发布权限人独立授权 | proposal/candidate/study/release eligibility/scope hashes、approval quorum hash、HUMAN actor/authority、effective/expiry、rollback target、authorization hash | CONTROL_PLANE Prepare 门 |
| ProfilePublicationPrepared | 两阶段发布的第一阶段完成 | role/scope、new profile/version/content hash、publication revision=PENDING_SYNC、base/previous current refs、proposal/study/eligibility/authorization refs、safety_epoch、PublicationSyncRequirementSet/hash、prepared_at | required ActionExecution；不得用于新 Case pin |
| ProfilePublicationSyncReceiptAccepted | 一个 required sync 回执被 RoleProfile 接受 | role/scope、publication revision、action/receipt/external target revision refs、requirement hash、current receipt set hash、safety_epoch、accepted_at | Commit readiness projector |
| ProfilePublicationCommitted | required receipts 齐全后提交 pointer | role/scope、profile/version/content hash、publication revision、previous current ref、future scope、proposal/study/eligibility/authorization refs、receipt set hash、safety_epoch、committed_by=CONTROL_PLANE、committed_at | 新 Case pinning、暴露账本、监控 |
| ProfilePublicationFrozen | 新案件引用与待提交发布被安全冻结 | role/scope、current/pending publication refs、old/new safety_epoch、pending cancellation token/receipt invalidation refs、reason/P0、actor/policy、frozen_at | 案件开立门、未结 ActionExecution 取消/补偿、事件响应 |
| ProfileRollbackAuthorized | 有权限人批准回滚 | role/scope、frozen safety_epoch、current/target approved versions、HUMAN actor/authority、impact/current safety review/A0 plan、authorization hash、authorized_at | CONTROL_PLANE rollback 门 |
| ProfilePublicationRolledBack | CONTROL_PLANE 创建 operation=ROLLBACK 的新 ACTIVE 修订并恢复 RoleProfile ACTIVE | role/scope、from/to version refs、old revision=ROLLED_BACK、new ACTIVE publication revision、frozen/new safety_epoch、authorization ref/hash、automation_level=A0、rolled_back_at | 新 Case pinning、监控、审计 |
| ProfileExposureAssigned | A2 因果/治理研究稳定分配 | ledger/study/case refs、CausalDesignManifest hash、arm/assignment unit、allocation policy/version/hash、assigned_at | Case pin/暴露对账 |
| ActualProfileExposureRecorded | 当前筛选输入证明实际暴露或未暴露 | ledger/study/case refs、assignment ref/hash、actual ProfileVersion pin 或 NOT_EXPOSED reason、observed_at | 因果分析、污染检测 |
| ProfileExposureContaminationRecorded | 交叉接触/偏离/不依从被追加 | ledger/study/case refs、assignment/exposure refs、contamination/deviation type、source ref、recorded_at | 因果限制、Study/Gate 重验 |

## 15. 跨对象不变量

1. 同租户活动 ApplicationKey 唯一；重复投递只增加来源，ApplicationKey 开案后不可原地修改。
2. INV-G2-ROUTED-ONLY：一个 ResumeSubmission 只有当前 RoutingResolution=ROUTED 且 ApplicationKey 完整时才能开案或附加来源；路由候选和置信度不是路由事实。
3. INV-G2-ROUTING-CORRECTION：一个 ResumeSubmission 只有一个当前案件关系；改键纠正先 supersede 旧关系、失效其材料/任务/动作，并在旧案件关闭或补偿范围获明确裁决后打开/附加正确案件；旧决定、会议和审计历史不搬运。
4. 同一候选人多岗位、多周期必须形成隔离案件；内容哈希只能查重，不能跨 ApplicationKey 合并业务。
5. 一个 ApplicationCase 同时只有一个当前 ScreeningInputManifest、一个当前 MatchAssessment 指针；处于 AWAITING_DEPARTMENT_DECISION 时还必须恰有一个 OPEN 或 ON_HOLD DepartmentDecisionRequest，页面、卡片和消息不拥有第二份真相。
6. INV-G2-HUMAN-DECISION：DepartmentDecision、RoundDecision、FinalDecision 的 Actor 必须是当前有权限的 HUMAN；沉默、超时和模型分数都不是决定。
7. INV-G2-NO-AUTO-REJECT：低匹配分、必要条件缺失、解析失败和模型输出不能关闭案件、发拒信或阻止人工查看。
8. 画像在筛选时、流程在进入面试时、评分卡在轮次激活时钉住；在途版本变化不静默迁移。
9. 决定记录归拥有业务迁移的聚合：部门/最终决定归 ApplicationCase，轮次决定归 InterviewRound；决定不可变，纠正用 supersede。
10. HOLD 只让当前 DepartmentDecisionRequest 进入 ON_HOLD 并停止催办；到期恢复产生新 revision/generation，不能复活旧卡片或由系统代作决定。
11. 一个 InterviewSession 最多同时有一个已提交有效 AppointmentRevision 和一个待提交修订；改期失败时旧 Booking 继续有效。
12. INV-G2-PROPOSAL-NOT-BOOKING：SchedulingProposal 和 SlotSelection 都不改变为 BOOKED，只有当前修订的 BookingReceiptSet 完整才能 CommitBooking。
13. 尚无必需会话开始时，InterviewRound=SCHEDULED 只在全部必需 SessionRequirement 都有当前有效 Booking 时成立；任一必需 Session 开始后，Round 进入或保持 IN_PROGRESS，剩余 Session 可继续约面，后续 Booking 不得把 Round 回退为 SCHEDULED；单会话回调不得直接提交 Round 状态。
14. INV-G2-CURRENT-REVISION：旧 request、proposal、selection、appointment、task、card、link 和 provider callback 不能写当前状态。
15. 外部世界可能短暂存在重复资源，但内部只有一个当前 Booking；重复资源必须对账/补偿，不能成为第二个业务预约。
16. StartInterview 与 RequestCaptureStart 分离；NO_RECORDING 采集模式和 AUTHORIZED_NOTES_ONLY 证据路线可以正常开始和完成面试。
17. INV-G2-NOTICE-NOT-CONSENT：RecordingNotice、接受邀请和入会都不能产生 ConsentReceipt 或让 Capture Gate 自动通过。
18. INV-G2-NO-RECORDING-EQUIVALENCE：拒绝录制必须有等价无录制路线，且选择和原因不能进入匹配、简报、评价或决定依据。
19. INV-G2-LATE-JOINER-GATE：晚加入或转发邀请产生的新参与人不继承他人选择；所有当前在场且媒体可能进入平台采集的参与人未通过闸门前不得采集。
20. INV-G2-CAPTURE-CONFIRMATION：只有当前 Provider 回执/可信对账驱动的 ConfirmCaptureStarted 能写 ON，ConfirmCaptureStopped 能写 STOPPED；请求、Action 回执、平台观察和业务确认不能互相替代。
21. INV-G2-CONTROL-SCOPE：Case PAUSED/CLOSED、ConsentReceipt 和 ProcessingControl 是三类独立权威事实；ProcessingControl 只在显式主体、案件/会话、目的、操作和数据范围内生效。
22. INV-G2-CONTROL-PREFLIGHT：每次外部动作授权和执行前都重验 lifecycle_epoch、processing_control_set_hash、current_routing_revision、target_revision、policy_version 和 payload_hash。
23. INV-G2-SAFETY-COMPENSATION：PAUSED/CLOSED 阻断生产性动作，但不得阻断 REQUEST_CAPTURE_STOP、CANCEL_MEETING、REVOKE_LINK、DELETE_ASSET 等批准的安全补偿。
24. INV-G2-NO-LLM-ACTION：LLM 只能生成材料和动作建议，不能改状态、执行外部动作或作招聘决定；候选人材料内提示同样无权。
25. INV-G2-G1-HANDOFF：同一 Session 同时只有一个 current_handoff_ref；只有 Session=ENDED 且采集尝试、片段处置与最终对账结算后才能创建交接；RECORDED_EVIDENCE 与 AUTHORIZED_NOTES_ONLY 互斥，AUTHORIZED_NOTES_ONLY 只表示本次交接不引用音视频证据，不得抹去真实采集历史或伪造录音、逐字稿及同等证据质量。
26. INV-G2-G1-HANDOFF-INVALIDATION：任一 causal input 被替代、撤回、删除、超保留期或用途/控制不再允许时，当前或已接受 Handoff 在 G1 读取/使用前失效；替代输入只能创建更高 revision，迟到 Accepted 不得复活旧输入。
27. INV-CONTROL-SINGLE-AGGREGATE：一个命令事务只改变一个聚合和 Outbox；跨聚合只能通过事件触发另一个带 expected_version、幂等键与当前事实重验的命令。
28. ApplicationCase、InterviewRound、InterviewSession、InterviewBrief、EvaluationPackage、CrossRoundIssue、FinalAssessmentPackage、ConsentReceipt、ProcessingControl、ActionExecution、ExceptionBundle 的引用必须同租户、同案件/会话并通过目的校验。
29. 一轮完成必须引用当前已确认评价和当前有效人工决定。
30. 关键候选人能力结论不得仅引用面试官发言；低置信证据不得包装成确定事实。
31. 内容变化产生新评价版本并使旧确认失效；决定被 supersede 后，下游轮次完成件、简报和终面包重验。
32. 异常解决不是直接改业务状态；恢复必须用 resume_token + expected_version 重走迁移门。
33. SLA 暂停必须是预定义原因并累计暂停时间；Timer 到期按 generation 重验。
34. 事件和日志不得承载不必要的简历、联系方式、日历正文、录音或逐字稿。
35. 已删除、超保留期或用途不再允许的证据不能继续支持新评价、简报或终面包；不可变对象可保留无正文审计墓碑。
36. 当前面试计划依赖图必须无环；条件、必需性和角色未解析时不能自动激活 Round。
37. REPEAT_ROUND 只能创建引用原轮的新 Round，不能清空或复用原 Round ID。
38. RoundWaiver 只能由有权限的人提交；它满足流程完整性但永不贡献证据或“通过”语义。
39. 面试官提交独立评价前，InterviewBrief 默认不披露前轮总分、整体结论、决定或身份化意见。
40. InterviewBrief 反馈与候选人评价、画像和评分卡隔离，不能成为自动负面标签或自动学习输入。
41. 相同 EvidencePointer 多次出现时只计一个事实来源；引用次数不改变证据权重或覆盖分母。
42. Agent 只能创建 CrossRoundIssue CANDIDATE；阻断性分类和解决必须来自批准规则或有权限的人。
43. FinalAssessmentPackage 只接受当前 RoundCompletionRecord 和有效 RoundWaiver，不接受草稿、评论或旧决定。
44. 一个案件同一时刻只有一个当前 FinalAssessmentPackage 和一个当前 FinalAssessmentReviewTask。
45. MarkFinalAssessmentReady 必须同时引用当前 READY 包、当前任务和无阻断项的重验结果，不得仅看 Round 状态。
46. 包失效先由 Package 发事件，再由 ApplicationCase 独立命令回退 stage 并撤回其当前审阅任务；传播延迟期间读取/决定门也必须判旧包无效。
47. 产品内审阅/决定任务是权威入口；IM/邮件通知成功与否只改变运行态和可信托管指标，不创造第二个业务任务。
48. INV-G3-OUTCOME-NOT-GROUND-TRUTH：OutcomeObservation 是带阶段、来源、岗位、时间和用途的可纠正观察，不是成功真值、招聘决定或模型奖励。
49. INV-G3-DECISION-OWNERSHIP：人工招聘决定始终由 ApplicationCase 拥有；G3 只能引用 FinalHiringDecisionRecorded 的当前修订，不能复制或修改决定。
50. INV-G3-STAGE-LABEL-SEPARATION：轮次通过、最终决定、Offer、接受 Offer、入职、留任和表现是不同阶段，不得折叠成一个 success 字段。
51. INV-G3-DELAYED-LABEL-NOT-NEGATIVE：PENDING、RIGHT_CENSORED、UNKNOWN、NOT_ELIGIBLE 永远不能转换为负例、低分或排除候选人的理由。
52. INV-G3-SELECTIVE-LABEL：任职后表现通常只对 hired 可见；rejected 不得被推断为失败，研究必须披露选择性标注和不可外推范围。
53. INV-G3-JOB-SCOPE：任职表现信号必须通过有权限、限租户/目的的 EmploymentLinkageRef 绑定实际岗位、测量窗口和岗位相关标准；身份歧义、转岗、组织或经理口径变化不能静默合并/混用。
54. INV-G3-CANONICAL-OUTCOME-UNIQUENESS：OutcomeObservation.aggregate_id 由 tenant + OutcomeReconciliationKey hash 确定并受唯一约束；一个 key（不含 source_system）只有一个 current canonical OutcomeRevision。SourceAssertion 按来源业务键/修订幂等，完整 current source_set_hash 改变必须新建解析修订。冲突未裁决时为 DISPUTED，不得同时存在两个 CONFIRMED canonical 结果，也不得从 ATS/HRIS 各派生一份可用 Label。
55. INV-G3-CORRECTION-INVALIDATES-DERIVATIVES：观察纠正、删除、来源失权、用途/控制变化必须按事件→命令链逐聚合失效 Label、Cohort、Candidate、AgentRun、Study、Proposal、current/pending publication eligibility 与依赖看板；任何消费者都不能跨聚合双写或以 RecallApproval 替代 Proposal invalidation。
56. INV-G3-COHORT-DENOMINATOR：每个 Cohort 保存完整 denominator、纳入/排除、成熟/缺失/删失数量与理由，不能只报有结果的人。
57. INV-G3-FROZEN-SNAPSHOT：SEALED Cohort 不可增删成员、换标注或改分区；任何变化新建 snapshot。唯一无循环顺序是 `SEALED Cohort → FROZEN Candidate → PREREGISTERED Study → 首次打开 holdout → AgentRun`，Cohort 不得反向依赖 Candidate/Study。
58. INV-G3-NO-SURVIVOR-ONLY：只有 hired 且有绩效的样本不得生成对完整投递漏斗可发布的画像提案。
59. INV-G3-NO-TEMPORAL-LEAKAGE：feature 只能使用 prediction_at 当时已存在的信息；后续决定、面试、入职和绩效只能作为 target/analysis。
60. INV-G3-NO-IDENTITY-LEAKAGE：同一 Person 的多岗位、多周期申请不得跨 train/test/holdout。
61. INV-G3-NO-CROSS-TENANT-LEARNING：默认禁止跨租户共享原始观察、标注、候选人级样本、梯度或画像候选修订。
62. INV-G3-PURPOSE-BOUND-LINEAGE：每个派生物都能追到允许目的、控制修订、保留规则、观察/标注版本和删除血缘。
63. INV-G3-PROTECTED-ATTR-AUDIT-ONLY：受保护属性如被合法取得，只能进入隔离公平审计；不得进入画像生成、筛选特征、Agent 上下文、事件总线或业务 UI。
64. INV-G3-SMALL-SAMPLE-NO-INFERENCE：未达到预注册样本/精度/分组门槛只能输出 INCONCLUSIVE 或描述结果，不能输出无影响、改善或发布型 Proposal。
65. INV-G3-NO-CAUSAL-CLAIM-WITHOUT-DESIGN：普通离线比较只能报告关联；没有批准且预注册的 CausalDesignManifest、稳定 assignment、actual exposure、contamination/noncompliance 账本，不得声称画像造成提升。
66. INV-G3-EVALUATION-NOT-APPROVAL：AgentRun/OfflineEvaluation 成功不等于 FeedbackStudy 有效、Proposal 获批或画像发布。
67. INV-G3-PROPOSAL-NOT-PROFILE：ProfileCandidateRevision、ProfileChangeProposal 与 current ProfileVersion 始终是不同对象。
68. INV-G3-NO-AUTO-DRIFT：任何 Observation、Label、Cohort、Study 或 AgentRun 事件都不得直接修改 current_published_version_ref。
69. INV-G3-HUMAN-PUBLICATION：画像批准须由两个不同 `human_actor_id` 分别以 HiringOwner 与 HRBP/ProfileGovernance 对同一 candidate/study/release eligibility/scope hash 签署；同一人兼任双角色不能满足 quorum。另一次明确的当前 HUMAN 发布授权是 Prepare 的必要条件；授权人可与一位批准人重合，但必须有独立发布权限、权限快照、时效与签名。批准不等于授权，授权不等于 CONTROL_PLANE 已执行。
70. INV-G3-STALE-BASE-CANNOT-PUBLISH：Proposal 的 base ProfileVersion 不再当前时必须重基、重评和重审，不能直接发布。
71. INV-G3-FUTURE-ONLY-PUBLISH：新版本默认只用于声明的未来招聘周期与新开案件；在途案件保持原 VersionPin。
72. INV-G3-PUBLISHED-IMMUTABLE：ProfileVersion 永不原地修改；Prepare、Commit 和回滚都留下不可变 PublicationRevision。PENDING_SYNC 不是已发布事实，只有 Commit 可在 RoleProfile 单聚合事务中更新 current_published_version_ref。
73. INV-G3-NO-A3-PROFILE-MUTATION：画像调权、排名、淘汰、ProfileVersion 发布和回滚永不开放 A3；A3 只可监测、建复核任务和按批准规则安全冻结。
74. INV-G3-FREEZE-FIRST：P0 公平、泄漏、越权、跨租户或证据失效时，冻结新案件引用优先于并发发布和普通运行；Freeze 提升 RoleProfile safety_epoch、CANCEL 当前 PENDING_SYNC、失效旧授权/回执并发 cancellation token。旧 epoch Prepare/AcceptReceipt/Commit 全部拒绝；已先 Commit 的版本也立即 FROZEN、不得被新案件 pin，等待人工回滚或复核。
75. INV-G3-ROLLBACK-NOT-REWRITE：回滚指向先前批准版本，不改写历史筛选、评价、决定、画像版本或在途案件。
76. INV-G3-ROLLBACK-TO-A0：发布事故或证据召回后，只有绑定当前 frozen safety_epoch 的 HUMAN 授权可让 CONTROL_PLANE 执行 Rollback；Rollback 在 RoleProfile 单事务中 `FROZEN→ACTIVE`、再次提升 safety_epoch、创建指向先前批准版本的新 ACTIVE PublicationRevision 并更新 pointer，所有受影响画像动作恢复到 A0；完成定界、修复、回归与会签后再逐动作升级。
77. INV-G3-TRACEABLE-RECOVERY：长任务只从当前 input manifest 的已提交 checkpoint 恢复；每次工具动作有最小 trace、回执、有限重试与补偿，工具成功不等于业务事实。
78. INV-G3-USABILITY-NOT-AESTHETICS：视觉回归或“高级感”不能替代真人任务成功、关键误解为零、无障碍和危险分支恢复证据；UI 状态只由聚合投影。
79. INV-G3-REFERENCE-SCOPE：G1/G2 命令的引用必须同一 Case 且受 lifecycle_epoch/routing revision 约束；G3 只有通过 current SEALED Cohort 才能引用多个历史 Case，并必须声明同 tenant 的 job/cycle/purpose/control/lineage scope。G3 永不修改历史 Case 的阶段、决定或 VersionPin。
80. INV-G3-DRAFT-ONLY-EXCLUDE：ExcludeOutcomeLabel 只接受 DRAFT；已 VERIFIED 标注的纠正/删除必须追加修订并 Invalidate/Supersede，下游逐级失效，不能改写历史为 EXCLUDED。
81. INV-G3-RUN-STARTS-RUNNING：StartAgentRun 原子创建 execution=RUNNING、validity=CURRENT 的 AgentRun；排队属于 RuntimeEnvelope/调度投影，不是领域状态，也不能被误当作已开始。
82. INV-G3-NO-HOLDOUT-CANDIDATE-TUNING：ProfileCandidateRevision 在 preregistration 与任何 confirmatory holdout access 前冻结；Candidate 工具权限只能解析 discovery/train/dev，holdout 仅作为 opaque ref 存在且 access ledger 必须为空。首次打开后 Candidate、plan、partition、主要指标任一变化必须新 Candidate、新 Study 和未使用的新 holdout，不能以旧 holdout 生成并验证同一候选。
83. INV-G3-RELEASE-GATE-CURRENT：ANALYSIS_READY 不等于 RELEASE_ELIGIBLE。Attach evidence、进入 REVIEW_READY、每次批准、发布授权、Prepare 与 Commit 都必须重验 exact candidate/study/scope/input 下 D0–D4 current PASS、未过期且无 veto；任何 FAIL、INCONCLUSIVE、hired-only 外推、重要 slice harm、用途/权限/血缘或因果门失败都不可由审批覆盖。
84. INV-G3-PUBLICATION-TWO-PHASE：仅 CONTROL_PLANE 可在当前 HUMAN authorization 下 Prepare/Commit。Prepare 只创建 PENDING_SYNC 与 required actions；所有 required AutomationActionSucceeded 回执由 RoleProfile 按 requirement/safety_epoch 接受后，Commit 才能更新 pointer。部分成功、迟到回执或外部目标修订漂移不得显示为已发布。
85. INV-G3-FULL-CASCADE-INVALIDATION：Cohort invalidation 必须分别使 dependent Candidate、AgentRun、Study 失效；Candidate/Run invalidation 使 Study 失效；Study invalidation 使所有开放/已批/已授权 Proposal 失效；命中 current/pending publication lineage 的 Proposal invalidation 触发 Freeze。每一步均为独立消费者命令并重验当前血缘。
86. INV-G3-CONTROL-LINEAGE：ProcessingRestrictionApplied、DeletionDirectiveApplied、来源权限撤销与用途变化必须以明确 scope 沿血缘发出各聚合失效命令；传播期间每个读取/写入门同步拒绝不再允许的派生物，删除 tombstone 不保留业务正文。
87. INV-G3-EXPOSURE-LEDGER：A2 因果主张必须在结果出现前稳定分配，并分别记录 assignment、actual ProfileVersion exposure、NOT_EXPOSED、contamination、deviation 与 noncompliance；不能按是否采用 Proposal、是否录用或是否有绩效事后选组。
88. INV-G3-PUBLICATION-SAFETY-EPOCH：Prepare、sync action、receipt acceptance、Commit、Freeze 与 Rollback 均绑定 exact RoleProfile safety_epoch。更高 epoch 永远压过旧授权、旧 receipt 与迟到成功；任何 retry 先重载当前 RoleProfile，不能靠缓存恢复 pending publication。
89. INV-G3-AUTHORITY-SEPARATION：HUMAN 负责审批、publication authorization、rollback authorization；CONTROL_PLANE 负责基于这些当前授权执行 Prepare/Commit/Rollback；Agent/LLM/普通 Service 只可产出候选、评测和工具回执。UI 按钮、通知送达与任务状态都不是授权或发布事实。
90. INV-G3-RECONCILIATION-BEFORE-LABEL：OutcomeLabel 只能引用 CONFIRMED canonical OutcomeRevision 及完整 source_set/resolution hash；新来源断言、来源修订或冲突改变 source_set_hash 时，旧 canonical/Label 及其所有派生物必须重验或失效。
91. INV-G3-UNKNOWN-IMPACT-GLOBAL-FENCE：P0 影响边界未知时按 tenant 全域安全边界处理；安全编排器逐个 RoleProfile 发带 causal token 的 Freeze 命令，不用一次事务批量写多个聚合。只有完成血缘定界与 HUMAN 回滚/复核授权后才可缩小范围或恢复，恢复仍从 A0 开始。

## 16. 幂等与乱序

### 16.1 幂等键

| 场景 | 业务幂等键 |
|---|---|
| 邮件附件收件 | tenant + mailbox + message_id + attachment_id + sha256 |
| ATS/Webhook | tenant + source_system + source_event_id |
| 领域命令 | tenant + command_type + aggregate_id + client_key |
| 日历/会议/邀请写入 | case_id + session_id + appointment_revision + resource_type + action |
| 改期/取消 | session_id + appointment_revision + action |
| 候选人选时段 | proposal_id + proposal_version + candidate_id + selection_action_id |
| 参与人采集选择 | session_id + participant_id + purpose_set_hash + notice_version + choice_action_id |
| 采集闸门评估 | session_id + presence_revision + consent_set_hash + processing_control_set_hash + capture_policy_version |
| 请求/确认采集 | session_id + attempt_revision + gate_revision + provider_resource_revision + REQUEST_OR_CONFIRM + START_OR_STOP |
| G1 面试证据交接 | case_id + round_id + session_id + appointment_revision + handoff_input_hash |
| 安全补偿 | original_action_id + target_external_revision + compensation_type |
| 人工决定 | decision_request_id + request_version + actor_id |
| 评价生成 | round_id + evidence_set_hash + scorecard_version + model_policy_version |
| 计划修订 | case_id + current_plan_version + proposed_graph_hash + authority_request_id |
| 重复轮次 | source_round_id + round_decision_id + repeat_ordinal |
| 轮次豁免 | round_id + waiver_request_version + human_actor_id |
| 面前简报生成 | round_id + audience_revision + scorecard_version + input_manifest_hash + disclosure_policy_version |
| 面前简报任务 | brief_id + brief_version + audience_revision + CREATE_TASK |
| 跨轮问题 | case_id + issue_type + scorecard_dimension + causal_input_versions_hash |
| 终面包编译 | case_id + final_input_manifest_hash + compiler_policy_version |
| 最终审阅任务 | case_id + package_id + package_version + final_owner_revision |
| 终面包失效 | package_id + package_version + causal_input_ref + causal_input_version |
| 催办 | request_id + reminder_policy_version + reminder_ordinal |
| SLA Timer | clock_id + generation + due_at |
| 异常包 | scope_ref + exception_code + causal_resource_version |
| G3 来源断言 | tenant + outcome_reconciliation_key_hash + source_system + source_business_key + source_revision |
| G3 canonical 解析 | outcome_reconciliation_key_hash + source_set_hash + resolution_policy_version |
| G3 最终决定观察引用 | case_id + final_decision_id + final_decision_revision + outcome_reconciliation_key_hash |
| G3 标注草稿/验证 | observation_id + canonical_revision + source_set/resolution_hash + labeling_policy_version + purpose + action |
| G3 Cohort 开放/封存 | tenant + job/cycle/purpose scope hash + as_of + eligibility/denominator/partition hash + OPEN_OR_SEAL |
| G3 Candidate 冻结 | base_profile_version + sealed_cohort_revision + candidate_generation_manifest_hash |
| G3 Study 预注册 | candidate_hash + sealed_cohort/partition_hash + study_plan/causal_design_hash + PREREGISTER |
| G3 首次打开 holdout | study_id/revision + preregistration_hash + holdout_partition_hash + FIRST_OPEN |
| G3 AgentRun 启动 | study_id/revision + candidate/cohort/holdout hashes + offline_evaluation_manifest_hash |
| G3 离线报告接受 | study_id/revision + run_id + report_hash + ACCEPT |
| G3 Proposal 开立 | candidate_hash + study/report_hash + base_profile_version + publication_scope/purpose hash + OPEN |
| G3 证据 Stage/Attach | proposal_id/revision + study/report/candidate hash + gate_input_or_release_eligibility_hash + STAGE_OR_ATTACH |
| G3 Gate Assessment | proposal_id/revision + candidate/study/scope/input hash + gate_id + evidence/policy revision/hash |
| G3 Release Eligibility | proposal_id/revision + D0-D4 current assessment set hash + ESTABLISH_OR_INVALIDATE |
| G3 Proposal 批准 | proposal_id + release_eligibility_hash + human_actor_id + approval_role + APPROVE |
| G3 发布授权 | proposal_id + approval_quorum_hash + release_eligibility/scope hash + human_actor_id + AUTHORIZE_PUBLICATION |
| G3 Prepare 发布 | role/scope hash + candidate/profile hash + publication_authorization_hash + safety_epoch + PREPARE |
| G3 required sync action | publication_revision + requirement_hash + target_ref/revision + action_type |
| G3 sync receipt 接受 | publication_revision + action_id + connector_receipt/external_revision hash + safety_epoch |
| G3 Commit 发布 | role/scope hash + pending_publication_revision + receipt_set_hash + safety_epoch + COMMIT |
| G3 Freeze | role/scope hash + causal_event_id + current_safety_epoch + FREEZE |
| G3 回滚授权 | role/scope hash + frozen_safety_epoch + target_profile_version + human_actor_id + AUTHORIZE_ROLLBACK |
| G3 回滚执行 | role/scope hash + frozen_safety_epoch + rollback_authorization_hash + target_profile_version + ROLLBACK |
| G3 暴露分配 | study_id + case_id + causal_design/allocation_policy hash + assignment_unit + ASSIGN |
| G3 实际暴露/污染 | ledger_id + source_business_revision + exposure_or_contamination_action |
| G3 血缘失效 | target_aggregate_type/id + causal_event_id + causal_ref/revision + INVALIDATE |

同一键、相同负载返回原结果；同一键、不同负载拒绝并报警。

### 16.2 乱序规则

1. 同一聚合按 aggregate_version；版本缺口暂存/重拉，低版本重复忽略。
2. 跨聚合不假设全局顺序，消费者加载当前权威状态后发带版本命令。
3. 优先使用外部 provider revision、sequence 或 ETag；没有时主动对账。
4. 暂停、撤回、删除和关闭拥有执行优先级；迟到成功回调只能记历史或触发补偿。
5. Transcript、Evaluation、FinalPackage 版本单调递增，低版本不覆盖高版本。
6. Timer 到期时重验 generation、阶段和等待对象。
7. 重试复用原 ActionExecution 幂等键，不能伪装成新动作。
8. 外部成功但本地响应丢失时先对账，再决定是否重试。
9. 已解决异常的迟到失败不重新开包，除非 causal resource version 已变化。
10. 卡片/协调页提交必须携带其展示版本，旧页面不能写当前状态。
11. InterviewPlan、RoundCompletionRecord、InterviewBrief、CrossRoundIssue 和 FinalAssessmentPackage 版本单调递增，旧版本不能恢复为 CURRENT/READY。
12. 并行前置跨聚合不假设到达顺序；每次事件都加载计划与全部当前前置，只激活一次。
13. Brief/Task 受众 revision 变化后，旧送达成功只能记审计或补偿撤回，不能恢复旧权限。
14. Package invalidation 比编译完成优先；迟到的 READY 结果必须重验 Input Manifest，不能覆盖 INVALIDATED。
15. 最终审阅任务的旧通知回执不能把已撤回 task revision 标回已送达。
16. Provider 回调必须关联 action_id、appointment_revision 和 provider resource revision/ETag；缺任一项时先对账，不能提交 Booking。
17. 候选人在同一提案中改选产生新的 selection_action_id 和待提交修订；旧选择不会因重试覆盖新选择。
18. 当前适用 ProcessingControl set 的任一更高 revision 都使旧授权失效；迟到成功只触发安全补偿和审计，不能推进 Case/Round/Session，且不得扩大到范围外案件。
19. RequestCaptureStop、Consent/ProcessingControl 变化与 ConfirmCaptureStopped 比迟到 CaptureStarted 优先；迟到开始回执必须再次请求停止并按 P0 处理。
20. InterviewEvidenceHandoff 的低 revision、重复 Accepted 或旧 Session 回调不能创建第二个当前 G1 输入；Invalidated 比迟到 Accepted 优先。
21. Outcome SourceAssertion 以 source revision 单调前进；更高修订或来源集变化产生新 source_set_hash，旧 canonical CONFIRMED/Label 不能覆盖新 DISPUTED/INVALIDATED。不同来源到达顺序不决定 canonical 结果。
22. FinalHiringDecisionSuperseded 比迟到的 FinalHiringDecisionRecorded 消费优先；消费者必须加载 ApplicationCase 当前决定，再 Correct 或 Invalidate 被引用 observation，绝不能恢复旧决定观察。
23. Observation/Label/Cohort/Candidate/Run/Study/Proposal 的 INVALIDATED 比任何迟到 Confirm/Verify/Seal/Success/AnalysisReady/Approval/Authorization 优先；旧成功事件仅留审计，不恢复 current validity。
24. SEALED Cohort 到达后才能冻结 Candidate；FROZEN Candidate 到达后才能 preregister；PREREGISTERED 后才可首次打开 holdout。任何重复/乱序事件都不能让 holdout 先于 Candidate hash 冻结，也不能打开第二次。
25. AgentRunStarted 原子创建 RUNNING；调度器的旧 queued/claimed 消息只属于运行投影，不能创建第二个 Run 或把 SUCCEEDED/INVALIDATED 回退 RUNNING。
26. 更高 revision、已过期、FAIL 或 VETO 的 D0–D4 Assessment 比迟到 PASS/approval 优先；消费者按 exact assessment refs/hash 重验，旧 ProfileReleaseEligibilitySnapshot 不复活。
27. ProfilePublicationPrepared 只产生 PENDING_SYNC；required sync 回执可以任意顺序到达但必须逐个匹配 requirement、target revision 与 safety_epoch。重复相同回执幂等，旧/冲突回执拒绝。
28. ProfilePublicationFrozen 的更高 safety_epoch 比 Prepare、ActionSucceeded、AcceptReceipt、Commit 的迟到消息优先；未结动作按 cancellation token 取消/补偿，迟到外部成功只对账，不更新 pointer。
29. CommitProfilePublication 与 Freeze 并发时由 RoleProfile expected_version+safety_epoch 串行化：Freeze 先提交则 Commit 拒绝；Commit 先提交则 Freeze 立即冻结新 current version，不能留下可 pin 窗口。
30. RollbackProfilePublication 只接受当前 FROZEN epoch 的 authorization；旧授权、旧 target hash、重复执行或 Freeze 后再次提升的 epoch 均拒绝。成功后新 PublicationRevision 单调前进且 RoleProfile 恢复 ACTIVE/A0。
31. ProfileExposureAssignment 不因实际暴露或结果迟到而重写；ActualExposure/Contamination 以来源业务 revision 追加，分析每次加载当前账本并披露偏离。

## 17. 四十个边界案例

| # | 场景 | 预期 |
|---:|---|---|
| 1 | 邮箱转发和 ATS webhook 带来同一简历 | 一个 Submission/Case，第二份只增加来源，不重复动作 |
| 2 | 两人共用邮箱或旧手机号被复用 | 进入路由复核，不自动合并身份 |
| 3 | 同一候选人同时申请两个岗位，或已开案投递被授权纠正到另一岗位 | 两个案件严格隔离；改键不改写旧 ApplicationKey，先 supersede 旧关系/动作并明确旧案补偿或关闭范围，再打开/附加正确案件，不搬决定和会议历史 |
| 4 | 附件损坏/加密，或一封邮件含两个候选人材料 | 停在 Submission；不编造字段、不合并、不创建半个案件 |
| 5 | 简历正文提示 Agent 发信、读数据或忽略规则 | 只作为不可信内容；模型不能执行工具、状态或权限动作 |
| 6 | 部门卡片打开期间收到新简历或画像版本 | 旧匹配材料/请求失效；显式生成新版本，不静默迁移 |
| 7 | 候选人撤回当前岗位案件时邀请已进队列 | 只关闭明确案件并增加 case epoch；发送前阻断；已建会议执行安全补偿，不默认关闭其其他岗位案件 |
| 8 | 用人经理点击旧卡片 | 版本校验返回已处理/陈旧，不覆盖当前决定 |
| 9 | 候选人选择旧提案，或选择后面试官忙闲变化 | 不建会；形成新提案/异常，不能显示已排期 |
| 10 | 两个案件同时抢占同一面试官时段 | 至多一个内部当前 Booking；失败方回协调 |
| 11 | 日历成功、会议失败，或 Provider 成功但响应丢失 | 不提交 Booking；先对账、有限重试/补偿，不重复外部效果 |
| 12 | 改期后旧平台回调迟到 | 只认当前 appointment_revision；旧回调只审计/补偿 |
| 13 | 旁听者晚加入或参与人中途撤回采集选择 | 未通过新闸门前暂停/不采集；撤回后立即停止后续处理 |
| 14 | 会议平台意外录制、无法停止或状态不明 | P0 停止/熔断/对账；无录制路线继续保护面试机会 |
| 15 | meeting.ended 先于 started，录音又重复回调 | 规范化缺失事实，会话/轮次只前进一次，资产按指纹去重 |
| 16 | 录音缺失、转写差、说话人不确定 | 不生成确定能力判断；重试耗尽后异常或批准的 NOTES_ONLY 路线 |
| 17 | 确认后转写纠正，或在途时发布新画像 | 新评价版本使旧确认/依赖失效；默认仍用钉住标准 |
| 18 | 两个并行前置 Round 的完成事件乱序/重复到达 | 每次重读当前依赖；后续 Round 只激活一次 |
| 19 | 人决定重复技术面 | 创建新 Round/attempt，原轮完成件保留且不会被新结果覆盖 |
| 20 | 必需轮次被授权豁免 | 流程可完整；终面包显著显示豁免和证据缺口，不标“通过” |
| 21 | 终面就绪后某轮确认评价被修订/删除 | 包和任务立即失效；Case 回 INTERVIEWING；旧链接只读 |
| 22 | 最终决策人改派时旧通知迟到成功 | 旧 task revision 不复活；新 Owner 只有一个当前任务 |
| 23 | `CLOSED`、Offer、入职和绩效被拼成一个成功标签 | Schema/标注门拒绝；各阶段保持独立观察和当前修订 |
| 24 | 绩效窗口未成熟、失访或右删失 | 保持 PENDING/UNKNOWN/RIGHT_CENSORED，不作负例或发布型提案 |
| 25 | 只有已录用且有绩效的人进入样本 | 披露选择机制和完整分母；阻断对全漏斗的推断与画像发布 |
| 26 | 同人跨岗位进入训练与 holdout，或决定后字段进入 feature | 实体/时间泄漏门失败；研究和派生提案失效 |
| 27 | 受保护属性、录制选择、辅助需求或权利请求进入画像候选 | P0 隔离、冻结、血缘定界；这些信号对业务输出影响必须为零 |
| 28 | 小样本总体改善但重要 slice 实质退化 | 只能 INCONCLUSIVE/拒绝发布；不能用总体平均或“不显著”掩盖伤害 |
| 29 | Agent、旧审阅任务或并发双击尝试批准/授权/发布画像 | 只能保留一个当前 Proposal/任务；双人批准要求 distinct HUMAN，publication authorization 另需当前 HUMAN；只有 CONTROL_PLANE 能执行 Prepare/Commit，旧 hash 全拒绝 |
| 30 | Commit 与 Freeze 并发，或 Commit 后观察被纠正/删除 | expected_version+safety_epoch 串行化；Freeze 先则 Commit 拒绝，Commit 先则新版本立即 FROZEN；按血缘使 Proposal 失效、取消 pending actions 并阻断新 pin，由人重做研究或授权回滚 |
| 31 | ATS 与 HRIS 对同一人/岗位/阶段/窗口给出不同结果 | 按 OutcomeReconciliationKey 合并为一个来源集；冲突进入 DISPUTED，不产生两份 CONFIRMED observation/Label，也不以最后到达者获胜 |
| 32 | 候选修订在首次看过 holdout 后被调参，或重复用同一 holdout | 旧 Study/Run/Proposal 失效；必须新 Candidate、新 Study 和未使用的新 holdout，禁止用 holdout 同时生成与验证候选 |
| 33 | 离线报告 ANALYSIS_READY，但 D0–D4 有 INCONCLUSIVE、过期、hired-only 外推或重要 slice harm | 不进入 RELEASE_ELIGIBLE/REVIEW_READY；审批和发布授权都不能覆盖 Gate，任何旧 PASS hash 失效 |
| 34 | REVIEW_READY/APPROVED/PUBLICATION_AUTHORIZED Proposal 的 Study、Candidate、控制或用途失效 | 先 Invalidate Proposal 并撤回任务/批准/授权；若命中 current/pending publication lineage，独立命令 Freeze RoleProfile，不能只 RecallApproval |
| 35 | RoleProfile 有 PublicationRevision=PENDING_SYNC 时发生 Freeze，随后旧 required action 成功回调 | Freeze 提升 safety_epoch、取消 pending revision/动作；迟到成功仅对账/补偿，旧 receipt 不可接受，current pointer 从未被 Prepare 改变 |
| 36 | 冻结后旧回滚授权或 Agent 尝试解冻；当前 HUMAN 对 exact epoch 授权合法回滚 | 旧授权/Agent 命令拒绝；CONTROL_PLANE 以当前授权创建新 PublicationRevision，RoleProfile FROZEN→ACTIVE、pointer 指向此前批准版本，全部受影响动作保持 A0 |
| 37 | 已 VERIFIED 的 Label 因右删失/策略变化被请求 Exclude | ExcludeOutcomeLabel 拒绝；追加 Invalidate/Supersede 修订并逐级失效，历史 VERIFIED 不被重写，删失也不成为负例 |
| 38 | G3 命令直接携带跨案件 ID 列表，或混入另一 tenant/未声明岗位与用途 | REFERENCE-SCOPE 门拒绝；多案件分析只能来自 current SEALED Cohort，历史 Case 保持只读且不能被 G3 改阶段/决定/VersionPin |
| 39 | 调度器重复/乱序发出 StartAgentRun，旧“排队”投影迟到 | 幂等地只有一个创建即 RUNNING 的 AgentRun；调度投影不写领域状态，SUCCEEDED/INVALIDATED 不回退 |
| 40 | A2 在看到录用/绩效或用户是否采纳 Proposal 后才分配实验组，或实际暴露与分配不一致 | 拒绝因果主张；保留原 assignment，追加 actual exposure/NOT_EXPOSED/contamination/deviation，D3 重验并披露 noncompliance |

## 18. 最低验收

### G1a

- 合法的已结束会话只能通过 ImportCompletedInterview 导入。
- 每条关键评价可回到同案件、同版本、正确说话人的证据。
- 面试官只能确认当前版本，旧链接不能写入。
- 无有效人工轮次决定，轮次不能进入 COMPLETED。
- 重复录音、重复确认和乱序事件不产生重复归档。
- 案件暂停/关闭后不存在新的生产性外发；停止采集、取消会议、撤销链接和删除资产等批准的安全补偿仍可执行并留回执。

### G1b

- 下一轮激活可证明来自当前计划、当前完成件/豁免和有效人工轮次决定；并行/重复事件不重复激活。
- 面前追问简报只展示当前缺口和合规问题；独立评价前不泄露前轮总分、决定或身份化意见。
- 必需轮次的当前确认评价、人工决定和证据均可通过轮次完成件逐轮追溯；豁免不贡献证据。
- 终面评估包关键 claim 证据覆盖 100%，缺项、跨轮问题、非阻断理由和豁免均显式存在。
- Agent 不能生成招聘建议、排名或解决跨轮问题；无有效人类最终决定，案件不能关闭。
- 终面包任一输入变化时在读取/使用前判为失效，旧任务不能继续写，Case 回 INTERVIEWING。
- 重复编译、通知重试和乱序失效不产生多个当前包、多个权威任务或旧版本复活。

### G2

- FR-201..264 与 AT-201..228 在 PRD、矩阵和 lint 中连续、唯一、双向覆盖；实现/验证/发布初始均为 0。
- 重复投递不重复开案，同人多岗不串案，坏附件/路由冲突不编造字段或自动合并。
- 一个 Case 只有一个当前筛选输入和匹配材料指针；低分/必要条件缺失不自动淘汰。
- 所有部门、轮次和最终招聘决定可证明由当前授权 HUMAN 作出；Agent/Service 命令被拒绝。
- SchedulingProposal/SlotSelection 不等于 Booking；当前预约修订的回执集完整才提交，部分成功和旧回调不显示已排期。
- 一轮多个必需 Session 时全部当前 BOOKED 才投影 Round=SCHEDULED；单 Session 回调不能直接写 Round。
- 录制告知不等于 ConsentReceipt；StartInterview、RequestCaptureStart/Stop 与 ConfirmCaptureStarted/Stopped 分离，拒绝录制有等价无录制路线。
- 晚加入、转发邀请、会中撤回、带作用域限制处理和平台状态不明都能立即阻断新采集/处理并发出安全停止；未获当前停止回执前不声称 STOPPED。
- 暂停、撤回、删除、关闭与权限失效优先于生产动作；安全停止/补偿动作不会被错误阻断。
- 约面、改期、取消、催办、采集与 G1 交接都有业务幂等键、当前修订和可对账回执。
- RECORDED_EVIDENCE 与 AUTHORIZED_NOTES_ONLY 交接互斥且映射到 G1a RECORDING/NOTES_ONLY；失效或被替代的 Handoff 在读取/使用门也被阻断；AUTHORIZED_NOTES_ONLY 不引用音视频证据、不抹去采集历史，也不伪造录音、逐字稿或证据质量。
- 控制塔页面完全由 ResumeSubmission、CaseStage、Round/Session、Capture 和 RuntimeEnvelope 权威事实推导。
- INV-G2-ROUTED-ONLY、INV-G2-ROUTING-CORRECTION、INV-G2-NO-AUTO-REJECT、INV-G2-HUMAN-DECISION、INV-G2-PROPOSAL-NOT-BOOKING、INV-G2-CURRENT-REVISION、INV-G2-NOTICE-NOT-CONSENT、INV-G2-NO-RECORDING-EQUIVALENCE、INV-G2-LATE-JOINER-GATE、INV-G2-CAPTURE-CONFIRMATION、INV-G2-CONTROL-SCOPE、INV-G2-CONTROL-PREFLIGHT、INV-G2-NO-LLM-ACTION、INV-G2-SAFETY-COMPENSATION、INV-G2-G1-HANDOFF、INV-G2-G1-HANDOFF-INVALIDATION、INV-CONTROL-SINGLE-AGGREGATE 在 PRD 与本规格语义一致。

### G3

- FR-301..360 与 AT-301..330 在 PRD、矩阵和 lint 中连续、唯一且覆盖；实现/验证/发布初始均为 0。
- FinalHiringDecisionRecorded 可追到 ApplicationCase 的当前 HUMAN 决定，Superseded 会纠正/失效其引用观察；G3 不复制决定所有权，结果阶段不折叠。
- ATS/HRIS 等多来源通过不含 source_system 的 OutcomeReconciliationKey、current source_set_hash 与 canonical resolution 收敛；同一事实范围不会形成两份 CONFIRMED observation/Label。
- 观察纠正、删除、用途或控制变化按事件→单聚合命令血缘链使 Label、Cohort、Candidate、AgentRun、Study、Proposal、pending/current publication eligibility 和看板失效；传播期间读取门同步阻断。
- Cohort 保存完整 denominator、成熟/缺失/删失和选择机制；同人/时间泄漏、跨租户、不可比岗位合池和幸存者外推被阻断。
- Cohort 独立封存后严格按 SEALED Cohort→FROZEN Candidate→PREREGISTERED Study→首次打开 holdout→RUNNING AgentRun 推进；禁止用 holdout 生成并验证同一候选。
- 评测对固定 Snapshot 可重放，AgentRun 创建即 RUNNING，报告展示 n、分子/分母、置信区间、重要 slice、反证和限制；小样本与普通相关不冒充因果改善。
- 受保护属性只进入批准的隔离公平审计；拒绝录制、无录制路线、辅助需求、权利请求和招聘人员行为不进入业务画像或标注。
- ProfileCandidateRevision、ProfileChangeProposal、ProfileVersion、批准与发布回执在 UI 和事件中保持分离。
- ANALYSIS_READY 不等于 RELEASE_ELIGIBLE；Attach/Review/Approval/Authorization/Prepare/Commit 均重验同一 candidate/study/scope/input 下 current D0–D4 PASS、未过期且无 veto。
- 两个不同 human_actor_id 以 HiringOwner 与 HRBP/ProfileGovernance 对 exact hash 批准后，仍需明确当前 HUMAN publication authorization；CONTROL_PLANE 执行 Prepare(PENDING_SYNC、不改 pointer)→required receipts→Commit(原子更新 future-scope pointer)，在途案件不迁移。
- P0 Freeze 提升 safety_epoch、取消 pending publication/动作并优先于 Commit；回滚只消费 exact frozen epoch 的 HUMAN 授权，由 CONTROL_PLANE 创建新发布修订、FROZEN→ACTIVE、恢复先前批准版本并回到 A0。
- A2 因果主张有批准的 CausalDesignManifest 和独立的 assignment、actual exposure、contamination/deviation/noncompliance 账本；不按采纳、录用或绩效事后选组。
- Agent Run 具备 typed tool、有限预算、checkpoint、幂等、最小 trace、dry-run、replay、回执和补偿；模型与工具结果不拥有业务真相。
- 控制塔默认只展示当前任务、原因、下一步、限制和恢复入口；高级审计渐进披露，高级视觉不能替代真人与无障碍验收。
