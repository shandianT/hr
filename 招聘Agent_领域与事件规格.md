# 招聘 Agent 领域与事件规格

版本：v0.3  
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

## 1. 建模结论

1. 申请案件的业务键是“租户 × 候选人 × 岗位需求 × 招聘周期”，不是邮件、手机号或会议。
2. 人或岗位尚未唯一解析的邮件先属于简历投递，不能创建缺少业务键的“半个案件”。
3. 案件顶层阶段只回答“招聘走到哪一大段”；约面、排期、面试和确认由当前轮次子状态表达。
4. 业务阶段、运行状态和暂停状态彼此正交；异常不是一个招聘阶段。
5. 面试轮次是一项目标明确的评价阶段；面试会话是一次实际会面。改期和技术重试通常不创建新轮次。
6. 评价材料和招聘决定是两个对象；模型只能产生前者的草稿。
7. 已确认评价、决定、画像、评分卡和流程版本不可原地覆盖。
8. G1 导入已结束面试必须使用受控命令，不能由后台任意跳状态。

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
| ResumeSubmission | G2 | 保存来源投递、附件引用、内容指纹、解析和路由候选 | 同一来源附件只接受一次；未唯一路由前不得开案 |
| ApplicationCase | G1/G2 | 保存 ApplicationKey、案件阶段、版本钉住、轮次计划和关闭事实 | 唯一有权改变案件顶层阶段 |
| MatchAssessment | G2 | 保存当前简历/画像版本下的逐项证据和匹配材料 | 低分不能直接产生淘汰 |
| InterviewRound | G1/G2 | 管理一轮评价目标、会话、评分卡、确认策略和人工决定 | 唯一有权判断该轮是否完成 |
| InterviewSession | G1/G2 | 管理一次实际会面、预约修订、参与人、采集路线和产物 | 一个预约修订只有一个有效外部会议 |
| InterviewBrief | G1b/G2 | 保存下一轮证据缺口、建议问题、披露策略、受众与反馈版本 | 每个 Round/受众修订只有一个当前可分发版本；输入变化即失效 |
| EvaluationPackage | G1/G2 | 保存证据集合、逐维评价草稿、人工修改和确认 | 确认只对同一评价版本有效 |
| CrossRoundIssue | G1b/G2 | 保存跨轮问题候选、双方依据、严重度、阻断性和解决记录 | 同一 causal input/问题键只有一个活动问题；Agent 不拥有最终分类权 |
| FinalAssessmentPackage | G1b/G2 | 钉住各轮评价/决定版本，保存缺项、冲突和总体摘要 | 输入失效时必须立即失效 |
| DecisionRecord | G1/G2 | 保存部门、轮次或最终人类决定及权限快照 | 决定不可变；纠正用 supersede |
| ActionExecution | G1/G2 | 保存外部动作授权、幂等键、尝试和连接器回执 | 保障业务效果只发生一次 |
| ExceptionBundle | G1/G2 | 保存事实、风险、尝试、选项、责任人、时限和恢复凭证 | 同一原因/资源版本只有一个活动异常 |

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

## 6. 简历投递与开案

### 6.1 ResumeSubmission 路由状态

| 状态 | 含义 |
|---|---|
| RECEIVED | 来源消息/附件已去重接收 |
| PARSING | 正在提取可用于身份与岗位路由的信号 |
| ROUTING_REVIEW_REQUIRED | 人、岗位或批次存在缺失/冲突 |
| ROUTED | 已唯一解析到候选人、岗位需求和招聘周期 |
| REJECTED_AS_NON_APPLICATION | 经规则/人工确认不是有效申请 |

只有 ROUTED 才能执行 OpenApplicationCase。一个投递可作为同一案件的新来源附加，但不能因转发或 ATS 重复回调创建两个案件。

### 6.2 OpenApplicationCase 门

- ApplicationKey 四部分全部确定。
- 同租户不存在同一有效 ApplicationKey。
- 来源投递没有归属到冲突案件。
- 候选人和岗位均处于允许处理范围。
- 命令包含 expected_version 和幂等键。

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

1. suspension=PAUSED 时一律显示 PAUSED，并硬阻断写动作。
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
4. 当前 lifecycle_epoch 与命令一致。
5. 案件未关闭、未删除；外部写动作还要求未暂停。
6. 当前动作符合 ActionPolicySnapshot 和 A0–A3 等级。
7. 所有引用对象同租户、同案件，且版本仍有效。
8. 录制、转写或新用途处理的合法依据/同意仍有效。
9. 红色决定的 actor_type 必须为 HUMAN 且权限匹配。
10. 本地事务只写单一聚合与 Outbox；跨聚合通过事件推进。

## 12. 关键迁移门

| 命令 | 迁移/结果 | 额外条件 |
|---|---|---|
| StartScreening | Case RECEIVED→SCREENING | 简历版本可读；画像可钉住；禁用字段隔离 |
| PublishMatchAssessment | SCREENING→AWAITING_DEPARTMENT_DECISION | 版本一致；必填维度完成；结论有原文证据；无自动淘汰 |
| RecordDepartmentDecision(INVITE) | →INTERVIEWING | 有权限的人；引用当前匹配材料；面试流程可钉住 |
| RecordDepartmentDecision(REJECT) | →CLOSED | 只能人工；拒绝信是独立外发动作 |
| AmendInterviewPlan | Case 仍 INTERVIEWING；生成新计划版本与影响清单 | 只能有权限的人；图无环；受影响 Round/Brief/Package/Task 失效 |
| ActivateRound | PLANNED→READY_TO_SCHEDULE | 当前计划适用；所有前置轮次完成件/豁免有效；人类决定允许继续；评分卡已钉住 |
| CreateRepeatRound | 新建 Round，原 Round 不变 | 来源决定为 HUMAN 的 REPEAT_ROUND；新 ID、来源关系、序号和幂等键唯一 |
| RecordRoundWaiver | PLANNED/READY_TO_SCHEDULE→WAIVED | 只能有权限的人；范围、原因、依据和权限快照齐全；不生成能力证据 |
| CommitBooking | SCHEDULING→SCHEDULED | 当前预约修订写入成功；邀请回执；会议引用唯一 |
| StartInterview | SCHEDULED→IN_PROGRESS | 当前会话；录制参与人同意有效，否则无录制路线 |
| ImportCompletedInterview | PLANNED/READY_TO_SCHEDULE→EVIDENCE_PROCESSING | 满足 G1a 受控导入门 |
| FinishInterview | IN_PROGRESS→EVIDENCE_PROCESSING | 必需会话结束；采集事实与同意一致 |
| PublishEvaluationForReview | EVIDENCE_PROCESSING→AWAITING_CONFIRMATION | 证据集合/评分卡一致；关键结论证据覆盖 100% |
| ReachConfirmationQuorum | AWAITING_CONFIRMATION→AWAITING_OUTCOME | 必需 Reviewer 对同一评价版本确认；无未处理修改请求 |
| RecordRoundDecision | AWAITING_OUTCOME→COMPLETED | 人工决定；引用当前已确认评价 |
| PublishInterviewBrief | Brief DRAFT/BLOCKED→CURRENT | 当前 Round/受众/评分卡/Input Manifest；分阶段披露和问题策略通过 |
| RecordInterviewBriefFeedback | Brief 版本不变；追加隔离反馈 | 当前指定面试官；接受/编辑/忽略/报告问题；不得改候选人评价或画像 |
| ClassifyCrossRoundIssue | Issue CANDIDATE→CLASSIFIED | 批准规则或有权限的人；确定类型、严重度、阻断性和 Owner |
| ResolveCrossRoundIssue | Issue CLASSIFIED→RESOLVED | 有权限的人；补证/范围澄清/信息不足/非阻断记录齐全 |
| CompileFinalAssessmentPackage | Package 无当前版本/BLOCKED/INVALIDATED→READY 或 BLOCKED | FinalInputManifest 当前；仅完成件/有效豁免；证据/决定字段/问题门通过 |
| InvalidateFinalAssessmentPackage | Package READY→INVALIDATED；Case FINAL_ASSESSMENT_READY→INTERVIEWING | 任一 causal input 失效；同事务或后续命令撤回/标旧当前审阅任务 |
| CreateFinalAssessmentReviewTask | 创建唯一当前权威任务 | Package READY；最终决策人权限有效；task revision 与 package version 绑定 |
| MarkFinalAssessmentReady | INTERVIEWING→FINAL_ASSESSMENT_READY | 必需轮次 COMPLETED/WAIVED；Package READY 且读取前重验；当前审阅任务已创建；无未处理 P0/P1 |
| RecordFinalDecision | FINAL_ASSESSMENT_READY→CLOSED | 有权限的人；引用当前终面评估包 |
| RecordCandidateWithdrawal | 任一非 CLOSED→CLOSED | 来源可证明；同事务写取消令牌 |
| ReopenApplicationCase | CLOSED→上一个合法阶段 | 仅纠错；增加 lifecycle_epoch；所有旧外发无效 |

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
| ResumeSubmissionParsed | 解析落库 | resume_version、parser_version、structured_ref、quality、identity_signal_refs | 身份/岗位路由 |
| ApplicationRoutingResolved | 人、岗位、周期唯一 | person_id、requisition_id、cycle_id、method、confidence | 案件中心 |
| ApplicationRoutingReviewRequired | 路由冲突/缺失 | reason_code、candidate_refs、due_at | 异常中心 |
| ApplicationCaseOpened | 开案成功 | case_id、application_key、submission_ids | 案件编排器 |
| ScreeningStarted | 筛选门通过 | resume_version、profile_version、policy_version | 匹配引擎 |
| MatchAssessmentReady | 匹配材料校验通过 | assessment_id、version、result_band、evidence_coverage | 部门卡片、案件中心 |
| MatchAssessmentInvalidated | 输入版本失效 | reason、replacement_input_refs | 卡片撤销、案件中心 |
| DepartmentDecisionRequested | 当前匹配卡进入人审 | request_id、allowed_decisions、reviewers、due_at | 协作卡、SLA |
| DepartmentDecisionRecorded | 有权限人提交 | decision_id、decision_type、human_actor、basis_ref、revisit_at | 案件中心、面试流程 |

### 14.2 面试、证据与评价

| 事件 | 触发 | 必要业务字段 | 主要消费者 |
|---|---|---|---|
| InterviewPlanPinned | 案件进入面试时锁定计划 | plan_id/version、graph_hash、required/optional/conditional steps、authority_ref | 轮次编排、审计 |
| InterviewPlanAmended | 有权限的人批准新版本 | old/new version、change_manifest_ref、affected_round_refs、authority_ref | 轮次、简报、终面包失效器 |
| InterviewRoundActivated | 前置轮次满足 | round_id、plan_step_id、sequence、scorecard_version | 约面编排器 |
| InterviewRoundRepeated | 人工决定要求重复一轮 | new_round_id、source_round_id、decision_id、reason、attempt_ordinal | 轮次编排、控制塔 |
| RoundWaiverRecorded | 有权限的人豁免适用轮次 | waiver_id/version、round_id、scope、reason、human_actor、authority_snapshot、evidence_impact | 完整性、终面包 |
| RoundWaiverSuperseded | 豁免被纠正/计划变化 | waiver_id/version、reason、replacement_ref | 完整性、终面包失效器 |
| SchedulingRequested | 进入 SCHEDULING | constraints、interviewer_rules、candidate_timezone、due_at | 协调页、日历 |
| CandidateSlotSelected | 候选人选当前提案 | proposal_id/version、slot、candidate_actor | 日历服务 |
| InterviewSessionBooked | 日历/会议写入成功 | session_id、schedule_revision、event_ref、meeting_ref、slot、receipt | 轮次、通知 |
| InterviewSessionRescheduled | 新修订生效 | old/new revision、resource refs、slot、reason | 轮次、通知、对账 |
| ParticipantConsentRecorded | 隐私上下文记录选择 | participant_id、purposes、decision、notice_version、receipt_ref | 采集闸门 |
| ParticipantConsentWithdrawn | 撤回目的 | participant_id、purposes、effective_at | 采集停止、删除、异常 |
| InterviewSessionStarted | 当前会话开始 | schedule_revision、participant_snapshot_ref、capture_gate_result | 轮次、采集 |
| InterviewSessionEnded | 当前会话结束 | ended_at、outcome、observed_start_missing | 轮次、证据管线 |
| CompletedInterviewImported | G1a 受控导入门通过 | round_id、session_id、from/to round state、scorecard_version、source_artifact_sha256 | 轮次、证据管线；不得伪造排期/进行中事实 |
| RecordingAssetAvailable | 录音/笔记完整入库 | artifact_id/type/version、checksum、consent_snapshot_ref、retention_class | 转写/证据 |
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

### 14.3 动作、异常与控制

| 事件 | 触发 | 必要业务字段 | 主要消费者 |
|---|---|---|---|
| AutomationActionRequested | 编排器提出动作 | action_id/type、target_ref、business_revision、payload_hash、risk、policy | 动作控制面 |
| AutomationActionAuthorized | 策略/人批准 | authorization_type、approver、policy_version、limits | 连接器 |
| AutomationActionSucceeded | 外部回执落库 | attempt_no、connector_receipt、external_resource_ref | 聚合、控制塔 |
| AutomationActionFailed | 一次尝试失败 | error_code、retryable、next_retry_at、connector_state | 重试、异常 |
| AutomationActionCancelled | 控制事实使动作失效 | reason、cancellation_token、cancelled_at | 连接器 |
| ExceptionBundleOpened | 需要人判断或重试耗尽 | exception_id、scope、code/severity、facts、options、owner、due_at、resume_token | 控制塔 |
| ExceptionBundleResolved | 人提交方案 | resolution_id、selected_option、resolver、supplied_refs、resume_token | 原编排器 |
| CasePaused | 人/策略/权利请求暂停 | reason、actor、cancellation_token | 所有执行器 |
| CaseResumed | 恢复门通过 | actor、reason、new_resume_token | 案件编排器 |
| SlaDeadlineBreached | 当前 generation 到期 | clock_id/type、target_ref、generation、due_at、owner | 催办、异常 |

## 15. 跨对象不变量

1. 同租户活动 ApplicationKey 唯一；重复投递只增加来源。
2. 一个简历投递未唯一路由前不能同时归属多个互斥案件。
3. ApplicationCase、InterviewRound、InterviewSession、InterviewBrief、EvaluationPackage、CrossRoundIssue、FinalAssessmentPackage、DecisionRecord、ActionExecution、ExceptionBundle 必须同租户、同案件。
4. 画像在筛选时、流程在进入面试时、评分卡在轮次激活时钉住。
5. DepartmentDecision、RoundDecision、FinalDecision 的 Actor 必须是有权限的人。
6. 低匹配分不能关闭案件、发拒信或阻止人工查看。
7. 一轮完成必须引用当前已确认评价和当前有效人工决定。
8. 一个会话只有一个当前 AppointmentRevision；旧回调不能覆盖新修订。
9. 晚加入参与人未完成同意前不得被录制；不能只看初始名单。
10. 关键候选人能力结论不得仅引用面试官发言。
11. 低置信证据不得包装成确定事实。
12. 内容变化产生新评价版本并使旧确认失效。
13. 终面评估包钉住各必需轮次版本；任一输入被替代，包立即失效。
14. 案件暂停、关闭、撤回或删除后，外部写动作执行前必须重读控制状态。
15. 异常解决不是直接改状态；恢复必须用 resume_token + expected_version 重走迁移门。
16. SLA 暂停必须是预定义原因并累计暂停时间。
17. 事件和日志不得承载不必要的个人信息正文。
18. 已删除或超保留期的证据不能继续支持新评价。
19. 决定被 supersede 后，所有依赖的下游轮次和终面包必须重新校验。
20. 当前面试计划依赖图必须无环；条件、必需性和角色未解析时不能自动激活 Round。
21. REPEAT_ROUND 只能创建引用原轮的新 Round，不能清空或复用原 Round ID。
22. RoundWaiver 只能由有权限的人提交；它满足流程完整性但永不贡献证据或“通过”语义。
23. 面试官提交独立评价前，InterviewBrief 默认不披露前轮总分、整体结论、决定或身份化意见。
24. InterviewBrief 反馈与候选人评价、画像和评分卡隔离，不能成为自动负面标签或自动学习输入。
25. 相同 EvidencePointer 多次出现时只计一个事实来源；引用次数不改变证据权重或覆盖分母。
26. Agent 只能创建 CrossRoundIssue CANDIDATE；阻断性分类和解决必须来自批准规则或有权限的人。
27. FinalAssessmentPackage 只接受当前 RoundCompletionRecord 和有效 RoundWaiver，不接受草稿、评论或旧决定。
28. 一个案件同一时刻只有一个当前 FinalAssessmentPackage 和一个当前 FinalAssessmentReviewTask。
29. MarkFinalAssessmentReady 必须同时引用当前 READY 包、当前任务和无阻断项的重验结果，不得仅看 Round 状态。
30. 包失效时旧任务不可继续写，Case 在最终决定前回 INTERVIEWING；旧包仅作历史审计。
31. 产品内审阅任务是权威入口；IM/邮件通知成功与否只改变运行态和可信托管指标，不创造第二个业务任务。

## 16. 幂等与乱序

### 16.1 幂等键

| 场景 | 业务幂等键 |
|---|---|
| 邮件附件收件 | tenant + mailbox + message_id + attachment_id + sha256 |
| ATS/Webhook | tenant + source_system + source_event_id |
| 领域命令 | tenant + command_type + aggregate_id + client_key |
| 日历建会 | case_id + session_id + schedule_revision + BOOK |
| 改期/取消 | session_id + schedule_revision + action |
| 候选人选时段 | proposal_id + proposal_version + candidate_id |
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

## 17. 十五个边界案例

| # | 场景 | 预期 |
|---:|---|---|
| 1 | 邮箱转发和 ATS webhook 带来同一简历 | 一个 Submission/Case，第二份只增加来源，不重复动作 |
| 2 | 两人共用邮箱或旧手机号被复用 | 进入路由复核，不自动合并身份 |
| 3 | 同一候选人同时申请两个岗位 | 两个隔离案件，各自钉住画像/流程/评价 |
| 4 | 候选人撤回时邀请已进队列 | 关闭+取消令牌；发送前阻断；已建会议补偿取消 |
| 5 | 用人经理点击旧卡片 | 版本校验返回已处理，不覆盖当前决定 |
| 6 | 改期后旧平台回调迟到 | 只认当前 schedule_revision，旧回调只审计/对账 |
| 7 | 旁听者晚加入或候选人中途撤回同意 | 未同意前不录制；撤回后立即停止后续采集 |
| 8 | meeting.ended 先于 started，录音又重复回调 | 规范化缺失事实，轮次只前进一次，录音按指纹去重 |
| 9 | 录音缺失、转写差、说话人不确定 | 不生成确定能力判断；重试耗尽后异常/人工笔记 |
| 10 | 确认后转写纠正，或在途时发布新画像 | 新评价版本使旧确认/依赖失效；默认仍用钉住标准 |
| 11 | 两个并行前置 Round 的完成事件乱序/重复到达 | 每次重读当前依赖；后续 Round 只激活一次 |
| 12 | 人决定重复技术面 | 创建新 Round/attempt，原轮完成件保留且不会被新结果覆盖 |
| 13 | 必需轮次被授权豁免 | 流程可完整；终面包显著显示豁免和证据缺口，不标“通过” |
| 14 | 终面就绪后某轮确认评价被修订/删除 | 包和任务立即失效；Case 回 INTERVIEWING；旧链接只读 |
| 15 | 最终决策人改派时旧通知迟到成功 | 旧 task revision 不复活；新 Owner 只有一个当前任务 |

## 18. 最低验收

### G1a

- 合法的已结束会话只能通过 ImportCompletedInterview 导入。
- 每条关键评价可回到同案件、同版本、正确说话人的证据。
- 面试官只能确认当前版本，旧链接不能写入。
- 无有效人工轮次决定，轮次不能进入 COMPLETED。
- 重复录音、重复确认和乱序事件不产生重复归档。
- 案件暂停/关闭后不存在新的外发动作。

### G1b

- 下一轮激活可证明来自当前计划、当前完成件/豁免和有效人工轮次决定；并行/重复事件不重复激活。
- 面前追问简报只展示当前缺口和合规问题；独立评价前不泄露前轮总分、决定或身份化意见。
- 必需轮次的当前确认评价、人工决定和证据均可通过轮次完成件逐轮追溯；豁免不贡献证据。
- 终面评估包关键 claim 证据覆盖 100%，缺项、跨轮问题、非阻断理由和豁免均显式存在。
- Agent 不能生成招聘建议、排名或解决跨轮问题；无有效人类最终决定，案件不能关闭。
- 终面包任一输入变化时在读取/使用前判为失效，旧任务不能继续写，Case 回 INTERVIEWING。
- 重复编译、通知重试和乱序失效不产生多个当前包、多个权威任务或旧版本复活。

### G2

- 重复投递不重复开案，同人多岗不串案，路由冲突不自动合并。
- 约面、改期、取消和催办都有业务幂等键和外部回执。
- 撤回、拒绝录制、晚加入者和权限失效均有停止与恢复路径。
- 所有管理决定可证明由授权人作出。
- 控制塔页面完全由 CaseStage、RoundState 和 RuntimeEnvelope 推导。
