# 招聘 Agent 领域与事件规格

版本：v0.5  
日期：2026-08-10  
状态：Gate 0 评审稿  
适用范围：G1a 面后单轮闭环、G1b 多轮终面包、G2 从收件到有限托管

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

## 2. 分阶段领域范围

| 阶段 | 必须具备 | 本阶段不要求 |
|---|---|---|
| G1a | 申请案件、面试轮次、已结束会话导入、录音/转写、证据评价、面试官确认、人工轮次决定、轮次归档 | 邮件自动建案、约面、多轮终面包 |
| G1b | 多轮计划、轮次依赖、各轮评价串联、缺项/冲突、终面评估包 | 简历筛选与日历生产自动化 |
| G2 | 简历投递、身份/岗位路由、匹配评价、部门决策、候选人协调、日历、同意、催办与动作级 A0–A3 | 画像自动改权重、跨岗位自动学习 |

完整目标不变：G1a/G1b 建立可信材料引擎，G2 扩大无人推动的流程半径。

## 3. 上下文边界

| 上下文 | 拥有的数据与决定 | 案件域如何使用 |
|---|---|---|
| 人员身份 | 候选人身份、合并/拆分、联系方式权属 | 只引用 CandidatePerson ID 和必要快照 |
| 岗位与标准 | 岗位需求、招聘周期、画像、评分卡、面试流程 | 在案件/轮次开始时钉住不可变版本 |
| 招聘案件 | 申请阶段、轮次、评价、决定、动作和异常 | 本规格的核心 |
| 隐私与权利 | 告知、同意、撤回、限制、删除和保留例外 | 在处理时读取有效凭证/控制事实 |
| 证据资产 | 简历、录音、逐字稿、屏幕材料 | 案件域保存受控引用、版本和哈希 |
| 连接器 | 邮箱、IM、日历、会议、ATS 的外部资源 | 通过动作执行与回执交互 |

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
| HandoffInputManifest | case/round/session/appointment refs、capture_mode、evidence_route、consent/control refs、capture history/segment/final reconciliation refs、asset_or_notes refs、input_hash |
| ExternalResourceRevision | provider、resource_type、resource_id、revision_or_etag、observed_at |
| ActionCategory | PRODUCTION / SAFETY_COMPENSATION；决定 PAUSED/CLOSED 后是否仍允许执行 |

关键实体归属：

- ResumeSubmission 内：StructuredResumeVersion、RoutingResolution。
- ApplicationCase 内：ScreeningInputManifest、CurrentMatchAssessmentRef、DepartmentDecisionRequest、FinalAssessmentReviewTask、部门/最终 DecisionRecord。
- InterviewRound 内：SessionRequirement、轮次 DecisionRecord、RoundCompletionRecord。
- InterviewSession 内：CandidateCoordinationRequest、SchedulingProposal、SlotSelection、AppointmentRevision、InterviewBooking、ParticipantPresence、CaptureGateEvaluation、InterviewEvidenceHandoff 和 current_handoff_ref。
- 隐私上下文：ConsentReceipt 与 ProcessingControl 分别拥有参与人选择和带作用域的禁止性控制；InterviewSession 只保存当前引用快照。
- ActionExecution 内：ActionAttempt、ConnectorReceipt、CompensationLink。

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

API 不接受“直接写页面状态”。所有显示状态由业务事实推导。

## 11. 通用命令门

每条改变状态或外部世界的命令依次校验：

1. 租户、部门、岗位和字段级权限。
2. expected_aggregate_version 乐观锁。
3. 同一幂等键未被不同负载使用。
4. 当前 lifecycle_epoch、processing_control_set_hash、current_routing_revision 和 target_business_revision 与命令一致；控制引用的主体、案件/会话、目的、操作和数据范围必须覆盖本动作。
5. 生产性动作要求案件未关闭、未删除、未暂停；SAFETY_COMPENSATION 只允许白名单停止/撤销/删除动作，并校验其补偿来源。
6. 当前动作符合 ActionPolicySnapshot 和 A0–A3 等级。
7. 所有引用对象同租户、同案件，且版本仍有效。
8. 录制、转写或新用途处理的告知、参与人选择、处理目的和 Capture Gate 仍有效。
9. 红色决定的 actor_type 必须为 HUMAN 且权限匹配。
10. 本地事务只写单一聚合与 Outbox；跨聚合通过事件推进。

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
| PinScreeningInput | Case RECEIVED/SCREENING→SCREENING | 当前简历可读；画像可钉住；允许字段/策略明确；旧材料/任务按影响失效 |
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
| RecordFinalDecision | FINAL_ASSESSMENT_READY→CLOSED | 有权限的人；引用当前终面评估包 |
| RecordCandidateWithdrawal | 任一非 CLOSED→CLOSED | 来源可证明；同事务写取消令牌 |
| ReopenApplicationCase | CLOSED→上一个合法阶段 | 仅纠错；增加 lifecycle_epoch；所有旧外发无效 |

### 12.1 跨聚合 seam

INV-CONTROL-SINGLE-AGGREGATE：下表每个命令事务只改变“唯一目标聚合”并写 Outbox；消费者必须重新加载全部当前事实，再用 expected_version 与幂等键提交下一条命令。

| 源命令 | 唯一目标聚合 | 发出事件 | 消费命令 | 唯一目标聚合 |
|---|---|---|---|---|
| StartInterview | InterviewSession | InterviewSessionStarted | MarkInterviewRoundInProgress | InterviewRound |
| CreateInterviewEvidenceHandoff | InterviewSession | InterviewEvidenceHandoffCreated | AcceptInterviewEvidenceHandoff | InterviewRound |
| InvalidateInterviewEvidenceHandoff | InterviewSession | InterviewEvidenceHandoffInvalidated | InvalidateRoundEvidenceInput | InterviewRound |
| InvalidateFinalAssessmentPackage | FinalAssessmentPackage | FinalAssessmentPackageInvalidated | RecallFinalAssessmentReadiness | ApplicationCase |

## 13. 事件信封

所有领域事件包含：

| 字段 | 含义 |
|---|---|
| event_id / event_type / schema_version | 事件身份与结构版本 |
| tenant_id | 租户边界 |
| aggregate_type / aggregate_id / aggregate_version | 权威聚合及版本 |
| case_id | 有申请案件时必填 |
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

## 17. 二十二个边界案例

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
