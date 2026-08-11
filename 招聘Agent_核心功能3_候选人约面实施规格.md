# 招聘 Agent 核心功能 3：候选人约面 bounded 实施规格

> 版本：v0.1
> 日期：2026-08-11
> 状态：实施输入；当前已有精确合成实现，证据边界以同名验收记录为准
> 证据目标：`IMPLEMENTED / SYNTHETIC_ONLY` 的精确子集
> 发布结论：不改变 Gate 0 No-go，不改变 G2 需求追踪矩阵的 `SPEC` 状态

## 1. 目标

用完全合成的数据和连接器，证明一条可执行但不夸大的候选人约面纵切：

> 当前可约面的一个必需面试会话 → 候选人协调请求 → 当前时段提案 → 候选人选时 → 选后重验 → 不可变预约修订 → 日历、会议、邀请三类资源写入与对账 → 唯一当前面试预定

完成标准不是“候选人点了一个时间”，而是同一当前预约修订要求的三类资源写入都取得版本匹配的有效回执，随后由拥有该事实的 `InterviewSession` 提交唯一 `InterviewBooking`。

本规格只收窄现有 [G2 PRD](./招聘Agent_G2_收件筛选约面_PRD.md)、[领域与事件规格](./招聘Agent_领域与事件规格.md) 和 [G2 需求追踪矩阵](./招聘Agent_G2_需求追踪矩阵.md) 的实现切片，不新增 FR、AT、领域阶段或招聘决定。

## 2. 权威依据与冲突规则

本实施规格必须服从以下权威输入：

1. [CONTEXT](./CONTEXT.md)：`候选人协调请求`、`时段提案`、`预约修订`、`面试预定`、`录制告知`、`采集选择凭证`等标准业务语言。
2. [ADR-0007：时段提案和候选人选择不等于面试预定](./docs/adr/0007-scheduling-proposal-is-not-a-booking.md)。
3. [ADR-0008：录制告知不等于采集授权](./docs/adr/0008-recording-notice-is-not-consent.md)。
4. G2 PRD 的 `FR-237..249` 与 `AT-214..227`。
5. 领域规格的 `INV-G2-PROPOSAL-NOT-BOOKING`、`INV-G2-CURRENT-REVISION`、`INV-G2-NOTICE-NOT-CONSENT`、`INV-G2-CONTROL-PREFLIGHT`、`INV-G2-SAFETY-COMPENSATION` 和 `INV-CONTROL-SINGLE-AGGREGATE`。

若本文件与上述权威输入冲突，以上述输入为准；修正本文件，不能借本文件静默改变权威语义。

本文件中的场景序号仅用于本纵切的测试组织，不是新的 FR 或 AT 编号。

## 3. Bounded 起点与终点

### 3.1 起点：fixture-only 当前会话

合成 fixture 直接建立以下当前事实：

- `ApplicationCase.stage=INTERVIEWING`，具有当前 `lifecycle_epoch` 与 `current_routing_revision`。
- 一个当前 `InterviewRound.state=READY_TO_SCHEDULE`。
- 该轮只有一个必需 `InterviewSession`：
  - `lifecycle_state=PLANNED`
  - `scheduling_state=NOT_STARTED`
  - 当前 Session、Round、Case、岗位需求和招聘周期引用同租户、同案件且版本一致。
- 当前 Interview Plan、参与人角色、面试时长、时区、允许时间窗、动作策略和处理控制快照均由 fixture 钉住。
- 候选人、面试官、忙闲、外部资源和所有回执均为虚构固定数据。

`READY_TO_SCHEDULE` 是 `InterviewRound` 状态，不是 `InterviewSession` 的状态。本文件所说“当前可约面的 Session”，精确含义是“属于当前 `READY_TO_SCHEDULE` Round、且自身仍为 `PLANNED / NOT_STARTED` 的一个必需 InterviewSession”。

### 3.2 本切片明确不证明的前置 seam

fixture 起点不消费核心功能 2 的真实运行输出，因此不证明：

- Hiring Owner 提交 `INVITE` 后钉住 Interview Plan；
- `DepartmentDecisionRecorded(INVITE)` 到 `InterviewPlanPinned` 的事件消费；
- Interview Plan 物化 Round/Session；
- `ActivateRound` 及 `InterviewRoundActivated`；
- `InterviewRoundActivated → OpenCandidateCoordinationRequest` 的跨聚合编排；
- 核心功能 2 与核心功能 3 共用持久化、Outbox、身份和生命周期后可无缝恢复。

产品 Demo 可以把前序显示为“负责人已决定进入面试”，但验收记录必须标注该前序为 fixture，不得声称 `INVITE → Plan → Round → Session` seam 已实现。

### 3.3 终点：唯一 Interview Booking

成功终点必须同时成立：

- `InterviewSession.scheduling_state=BOOKED`。
- Session 恰有一个 `current_booking_ref`。
- 当前 `InterviewBooking` 钉住一个不可变 `AppointmentRevision`。
- 当前 `BookingReceiptSet` 恰好包含下列三种、且各一份有效资源写入回执：
  - `CALENDAR_EVENT / WRITE`
  - `MEETING_RESOURCE / WRITE`
  - `INVITATION / WRITE`
- 三份回执都绑定同一 `case_id + session_id + appointment_revision`，并具有当前 `action_id`、Provider resource id、resource revision/ETag、receipt ref 与 payload hash。
- 只产生一次 `InterviewBookingCommitted` 业务事实；重复命令或回调不得产生第二个 Booking。
- `real_external_effect_count=0`，所有外部资源均来自合成 Adapter。

对于这个单必需 Session fixture，页面可以把该 Session 显示为“面试安排已确认”。本切片不写 `InterviewRound` 聚合，不以单 Session 回调直接提交 Round 状态，因此不证明 `AT-214` 的多 Session Round 投影；若展示 Round 排期，只能标为只读派生展示，不得作为第二份权威状态。

## 4. 范围与非目标

### 4.1 本期包含

- 一个 Case、一个 Round、一个必需 Session 的合成正常链。
- 版本化 `CandidateCoordinationRequest`、安全入口和候选人时区。
- 授权范围内的合成忙闲读取，不包含日历事件正文。
- 带约束、忙闲快照、版本和有效期的 `SchedulingProposal`。
- 候选人选择、选后重验和不可变 `AppointmentRevision`。
- 日历、会议和邀请三种合成资源写入的 `ActionExecution`、回执、重试、对账和有限异常。
- 唯一当前 `InterviewBooking`。
- 一次改期：新 Booking 提交前旧 Booking 保持当前；新 Booking 成功后再补偿旧资源。
- 候选人撤回、Case 暂停/关闭后的生产动作阻断与允许的安全补偿。
- 邀请中包含当前 `RecordingNotice` 版本；有真实合成送达证明时可记录 `RecordingNoticeDelivered`。
- 候选人移动优先的三步产品体验和运营侧回执详情。

### 4.2 本期不包含

- `INVITE → Interview Plan → Round → Session` 物化 seam。
- 多 Round、多必需 Session、替换面试官或跨组织调度。
- 真实邮箱、日历、会议、IM、候选人账号或 Provider callback。
- 真实联系人、真实邀请、真实会议、真实录制或真实个人信息。
- 候选人身份提供方、生产 IAM、跨租户授权或生产安全链接签发。
- `ConsentReceipt` 的创建、撤回、代理选择或法律效力判断。
- `CaptureGate`、录制开始/停止、面试开始、面试证据交接和 G1 输入。
- 法务批准的录制告知文本、保留删除、供应商或跨境结论。
- `AT-214` 多 Session 全链和 `AT-222..226` 采集/交接链。
- 候选人“全部时段不可用”、可访问性需求和人工协助请求的命令闭环。
- 生产数据库、分布式锁、多节点 worker、真实 Exactly-once 或灾难恢复。

### 4.3 既有 FR/AT 的精确映射

下表只说明这个 bounded 切片计划覆盖或明确排除哪些现有条目，不改变权威矩阵状态：

| 既有条目 | 本切片处理 | 证据边界 |
|---|---|---|
| FR-237 | 实现 fixture Round/Session 上的 `OpenCandidateCoordinationRequest` | 不证明 HUMAN INVITE、Plan/轮次物化或首轮激活 seam |
| FR-238 | 实现合成 Availability Adapter、最小忙闲/时区/资源快照和授权撤销 | 不证明真实日历授权、字段最小化配置或 Provider 权限 |
| FR-239 | 实现带约束、忙闲引用、版本和有效期的 Scheduling Proposal | 只证明合成 currentness |
| FR-240 | 实现限时、限案件、限用途、限 request revision 的合成 token 门 | 不证明生产身份提供方、链接签发或账号找回 |
| FR-241 | 实现当前 Proposal 上的候选人 SlotSelection 与唯一 action id | 选择只形成意图，不形成 Booking |
| FR-242 | 实现 Appointment Revision 前的参与人、资源、忙闲、Case 控制态和策略重验 | 输入均为合成 fixture |
| FR-243 | 实现三类 current WRITE 回执齐全后才 `CommitBooking` | 不证明真实外部资源 Exactly-once |
| FR-244 | 实现合成 ActionExecution、业务幂等、执行前重验、响应丢失对账和补偿 | shared G1a machine Schema 尚未扩展，生产 Connector 未证明 |
| FR-245 | 实现邀请写入负载的发送主体、时间/时区、会议入口、改期入口和 Recording Notice version；写入、送达、已读分离 | 不证明真实投递或告知实际送达 |
| FR-246 | 实现一次改期、新 Appointment Revision、旧 Booking 保留和新成功后补偿 | 不证明复杂多次/跨组织改期策略 |
| FR-247 | 实现撤回、PAUSED/CLOSED 下生产动作阻断和白名单安全补偿 | 只证明 bounded Case 作用域和合成资源 |
| FR-248 | 实现有限 proposal/改期/重试预算和单一 current Exception Bundle | 具体生产阈值、Owner 和升级链未冻结 |
| FR-249 | 实现结构完整、版本化的合成 Recording Notice 引用与独立送达凭证 | 文案未经隐私法务批准，不产生 ConsentReceipt |

| 既有 AT | 本切片状态 | 说明 |
|---|---|---|
| AT-214 | 不覆盖 | fixture 只有一个必需 Session，不证明多 Session Round 投影或开始后不回退 |
| AT-215 | 计划覆盖 | Proposal 过期、选后忙闲变化不建会 |
| AT-216 | 计划覆盖，合成限定 | 两 Case 共享同一原子合成 Provider，至多一个 Booking |
| AT-217 | 计划覆盖，合成限定 | 部分成功、响应丢失和十次重复回调不重复资源/Booking |
| AT-218 | 计划覆盖，合成限定 | 改期后旧 callback 只审计/补偿，不复活 |
| AT-219 | 计划覆盖，合成限定 | 撤回/CLOSED 阻断生产动作并允许安全补偿 |
| AT-220 | 计划覆盖，合成限定 | 日历失权/Provider 故障不伪造忙闲或 Booking |
| AT-221 | 只覆盖负面边界 | Notice 存在但 ConsentReceipt 缺失时不产生采集动作；不实现 Capture Gate |
| AT-222 | 不覆盖 | 无录制证据路线属于后续采集/交接切片 |
| AT-223 | 不覆盖 | 晚加入停止/重验属于后续采集切片 |
| AT-224 | 不覆盖 | 会中撤回与停止确认属于后续采集切片 |
| AT-225 | 不覆盖 | Consent/Control 属性组合属于后续采集切片 |
| AT-226 | 不覆盖 | Handoff 结算/失效与复杂控制竞态属于后续切片 |
| AT-227 | 计划覆盖，合成限定 | 错人、重放和旧 request revision 不改变当前选择 |

## 5. 产品形态

### 5.1 候选人默认三步

1. **选择时间**
   - 显示岗位、轮次概述、预计时长、参与人角色、候选人时区、提案有效期和 2–4 个可选时段。
   - 一个主要动作：“选择这个时间”。
2. **正在确认安排**
   - 候选人已提交选择，但控制面正在重验忙闲并写入日历、会议和邀请。
   - 此时禁止使用“已预约”“已排期”“会议已创建”等完成词。
3. **面试安排已确认**
   - 只在 `InterviewBookingCommitted` 后显示日期、时区、会议入口、邀请状态和改期入口。
   - 显示“录制告知已提供/已送达/尚未确认送达”和“采集选择尚未完成”中的真实状态，不显示“已同意录制”。

过期提案、选后冲突和改期失败都在当前步骤内给出下一有效动作，不让候选人理解内部错误码。

### 5.2 运营侧渐进披露

默认只显示：

- 当前在等谁；
- 当前是“待选择 / 正在确认 / 已确认 / 改期中 / 需要协助”；
- 下一次检查时间和最晚升级时间；
- 当前唯一主要动作。

二级“运行详情”才显示：

- Candidate Coordination Request revision；
- Scheduling Proposal id/version/expiry；
- SlotSelection action；
- 当前和待提交 Appointment Revision；
- 日历、会议、邀请三类 ActionExecution 和回执；
- BookingReceiptSet hash；
- 对账、重试、补偿、陈旧回调和 Exception Bundle；
- Recording Notice version、送达证明与 `ConsentReceipt` 是否存在。

## 6. Module、Interface 与 seam

### 6.1 深 Module

核心功能 3 的业务状态读写使用一个对调用方和行为测试一致的 Module Interface：

```python
scheduling.submit(command_envelope) -> command_result
scheduling.read(projection_request) -> scheduling_projection
```

调用方不能通过 repository、页面字段或 Connector callback 直接改变 Session、Booking、ActionExecution 或回执状态。合成 fixture 的建立/查询 helper 只用于测试装配，不属于业务状态读写 API，也不能在 Case 建立后绕过命令改变招聘事实。

Implementation 内部负责：

- 聚合版本、生命周期、幂等和当前修订；
- 候选人入口 token 门；
- 合成忙闲 Adapter；
- 三类资源 ActionExecution；
- 回执接受、重试、对账和补偿；
- BookingReceiptSet 计算；
- 当前 Booking 提交；
- 最小化投影与审计。

### 6.2 Adapter seams

| Seam | 最小 Interface | 合成 Adapter 行为 | 不允许 |
|---|---|---|---|
| Availability | 读取声明主体/时间窗的忙闲、时区和资源可用性，返回 `AvailabilitySnapshotRef` | 固定时区/忙闲；支持过期、授权撤销和选后冲突 | 返回事件标题、正文、参会人私密详情 |
| Coordination Identity | 校验限时、限案件、限用途、限请求 revision 的入口 | 当前 token 成功；错人、重放、过期、旧 revision 拒绝 | 仅靠前端隐藏或可猜 ID |
| Booking Resource | 按 `resource_type + operation` 执行当前动作，返回资源 revision/ETag 与 receipt ref | 成功、失败、响应丢失、重复和迟到回调可注入 | 由模型或页面直接调用 |
| Reconciliation | 按 action、appointment revision 和外部 resource revision 查询真实合成状态 | 响应丢失时先查询再决定重试 | 把超时当失败后直接重复创建 |

本期资源枚举固定为：

- `resource_type`: `CALENDAR_EVENT / MEETING_RESOURCE / INVITATION`
- `operation`: `WRITE / CANCEL`

这只是该 bounded Implementation 的 ActionExecution 分类，不新增产品 FR/AT，也不宣称现有 G1a shared machine Schema 已支持这些值。

### 6.3 Observe → Execute → Reconcile → Commit

一次预约提交遵循：

1. **Observe**：加载当前 Case/Round/Session、Proposal、Selection、参与人、忙闲、ProcessingControl set、策略和外部资源事实。
2. **Authorize**：`ProposeAppointmentRevision` 通过当前性、权限、预算和冲突门。
3. **Execute**：为同一 Appointment Revision 分别建立三类 `ActionExecution`，Worker 在执行点再次重验。
4. **Reconcile**：每个 Provider 结果先归属当前 action/revision/resource；响应丢失先查询，不盲目重试。
5. **Commit**：拥有预约事实的 `InterviewSession` 加载完整当前回执集后执行 `CommitBooking`。

`AutomationActionSucceeded` 只证明一项资源动作成功，不能单独形成 `InterviewBooking`。

### 6.4 单聚合不变量

每条命令事务只改变一个聚合及其 Outbox：

- 协调、Proposal、Selection、Appointment Revision 和 Booking 命令只写 `InterviewSession`。
- 每项外部动作命令只写自己的 `ActionExecution`。
- ActionExecution 成功事件由编排器消费；编排器重新加载当前 Session 和完整回执集，再向 `InterviewSession` 提交带 expected version 与幂等键的 `CommitBooking`。
- 安全取消的每个外部资源同样各自使用一个 ActionExecution，不跨聚合双写。

## 7. 最小领域对象

| 对象 | 归属 | 本切片最小字段/不变量 |
|---|---|---|
| CandidateCoordinationRequest | InterviewSession | request id/revision、status、candidate timezone、constraint ref、token policy、due/expiry；只有一个当前 OPEN 请求 |
| SchedulingConstraintSnapshot | 值对象 | participants/roles、timezones、duration、windows、policy version |
| AvailabilitySnapshotRef | 值对象 | provider、subject refs、observed/expiry、snapshot hash；不含日历正文 |
| SchedulingProposal | InterviewSession | proposal id/version、constraint/availability refs、slot refs、expires_at、CURRENT/SUPERSEDED |
| SlotSelection | InterviewSession | proposal id/version、candidate actor、selection action id、slot ref、recorded_at；只表达预约意图 |
| AppointmentRevision | InterviewSession | revision、slot、participants、resource requirements、previous booking ref、status；不可变 |
| BookingRequirementsSnapshot | 值对象 | 当前 revision 所需 `CALENDAR_EVENT / MEETING_RESOURCE / INVITATION` 三类 WRITE、policy version |
| ActionExecution | 独立聚合 | action id、case/session/revision、resource type、operation、payload hash、policy/control snapshot、attempts、state |
| ExternalResourceRevision | 值对象 | provider、resource type/id、revision_or_etag、observed_at |
| BookingReceiptSet | 值对象 | appointment revision、三类 current action refs、external revisions、receipt hash |
| InterviewBooking | InterviewSession | booking id/revision、appointment revision、receipt set hash、current resource refs、committed_at、CURRENT/CANCELLED/INVALIDATED |
| RecordingNotice | 隐私/告知引用 | notice version、purposes、处理方式、数据类型、接收方、保留/权利和无录制路线 |
| RecordingNotice Delivery Receipt | 受控引用 | participant/session/purpose/notice version/channel/receipt/observed_at；不产生 ConsentReceipt |
| ProcessingControlSetSnapshot | 值对象 | control refs/revisions、case/session/purpose/operation/data categories、snapshot hash |
| ExceptionBundle | 独立聚合或 bounded runtime record | causal resource version、事实、尝试、风险、选项、Owner、截止与恢复条件；同因果键一个当前包 |

## 8. 最小命令与命令门

### 8.1 业务命令

| 命令 | 唯一目标 | 成功结果 | 关键门 |
|---|---|---|---|
| OpenCandidateCoordinationRequest | InterviewSession | `NOT_STARTED → COORDINATING` | fixture Round 当前可约面；Session/constraints/token policy/current control 当前 |
| PublishSchedulingProposal | InterviewSession | `COORDINATING → PROPOSAL_OPEN` | 忙闲/约束快照当前；版本和有效期齐全 |
| RecordCandidateSlotSelection | InterviewSession | 追加 SlotSelection，仍非 Booking | 当前 request/proposal/version/token/candidate actor/selection action |
| ProposeAppointmentRevision | InterviewSession | `PROPOSAL_OPEN → BOOKING_PENDING` 或 `BOOKED → RESCHEDULING` | 重新读取忙闲、参与人、资源、Case 控制态和策略；冲突时禁止外部写 |
| CommitBooking | InterviewSession | 当前 Appointment Revision 形成唯一 InterviewBooking | 三类 current WRITE 回执齐全且同 revision；expected version/幂等/控制快照当前 |
| RequestReschedule | InterviewSession | `BOOKED → RESCHEDULING`，生成新意图 | 新 revision；旧 Booking 继续 current；次数/窗口未耗尽 |
| CommitBookingCancellation | InterviewSession | 旧 Booking 取消或回协调 | 当前取消回执齐全；安全补偿可越过 PAUSED/CLOSED 普通写门 |
| RecordRecordingNoticeDelivery | InterviewSession | 只追加当前 notice delivery ref；Notice 文本仍由隐私/告知上下文拥有 | participant/session/purpose/notice version/channel/receipt 当前；不产生 ConsentReceipt |

### 8.2 通用动作命令

外部动作沿用通用语义：

- `RequestExternalAction`：由确定性 Workflow Service 为一个资源动作建立 `ActionExecution`。
- `RecordExternalActionResult`：仅合成 Connector Service 可提交成功、失败、取消或待对账结果。

当前 shared G1a Schema 尚未包含本切片资源枚举；在 shared Schema 扩展前，只能在 `recruiting_scheduling` Module 内实现同形、封闭的合成命令并在验收记录中明确该 seam 未统一。

### 8.3 所有写命令的共同门

1. tenant、case、round、session 与用途同一且有权限。
2. expected aggregate version、lifecycle epoch、current routing revision 当前。
3. 当前 request/proposal/selection/appointment/action/booking revision 与命令一致。
4. 同一幂等键同载重放；同键异载拒绝并记录安全事件。
5. 当前 `processing_control_set_hash`、ActionPolicy、payload hash 与执行点一致。
6. `PAUSED/CLOSED/撤回/删除/权限撤销` 阻断生产性 WRITE，不阻断白名单安全 CANCEL。
7. Agent、模型、页面和候选人材料不能直接提交外部动作结果或 Booking。
8. 回调缺少 action id、appointment revision 或 external revision/ETag 时先对账，不能提交 Booking。

## 9. 最小事件

| 事件 | 必要字段 | 本切片用途 |
|---|---|---|
| CandidateCoordinationRequestOpened | request id/revision、constraints ref、timezone、token policy、due_at | 打开候选人页与 SLA |
| CandidateCoordinationRequestExpired | request id/revision、reason、replacement ref | 旧入口只读/拒绝 |
| SchedulingProposalPublished | proposal id/version、constraint/availability refs、slot refs、expires_at | 展示当前可选时段 |
| SchedulingProposalSuperseded | proposal id/version、reason、replacement ref | 过期、忙闲或参与人变化 |
| CandidateSlotSelectionRecorded | proposal id/version、selection action id、slot ref、candidate actor | 形成选择意图，非 Booking |
| AppointmentRevisionProposed | session、appointment revision、slot/participant/resource requirement refs、previous booking ref | 创建三类资源动作 |
| AppointmentRevisionAborted | appointment revision、reason、partial resource/compensation refs | 回到新提案或异常 |
| AutomationActionRequested | action/resource/operation/revision/payload/policy refs | 合成 Worker 执行 |
| AutomationActionSucceeded | action、attempt、receipt、external resource revision | 回执编排；不单独提交 Booking |
| AutomationActionFailed | action、attempt、error、retryable | 有限重试、对账或异常 |
| AutomationActionCancelled | action、resource revision、cancellation token | 安全补偿审计 |
| InterviewBookingCommitted | session、appointment revision、BookingReceiptSet hash、三类 resource refs | 唯一 Booking 业务事实 |
| InterviewBookingInvalidated | booking/revision、reason、replacement revision | 防止旧 Booking 复活 |
| InterviewBookingCancelled | booking/revision、cancellation receipts、reason | 取消完成 |
| RecordingNoticeDelivered | session、participant、purposes、notice version、channel、receipt ref | 只证明告知送达，不证明选择 |

事件信封只携带稳定 ID、版本、哈希和受控摘要，不复制候选人联系方式、日历正文或告知全文。

## 10. Case-bound 读模型

### 10.1 Service view：`SCHEDULING_CASE_CONTEXT`

自动化命令构造只能使用精确 Case-bound view：

```json
{
  "tenant_id": "tenant-synthetic",
  "application_case_id": "case-synthetic-1",
  "interview_session_id": "session-synthetic-1",
  "view": "SCHEDULING_CASE_CONTEXT",
  "actor_context": {
    "actor_type": "SERVICE",
    "actor_id": "scheduling-workflow",
    "role": "SCHEDULING_WORKFLOW"
  }
}
```

该 view 只返回：

- Case id/stage/version/lifecycle epoch/current routing revision；
- Round id/version/state 与当前必需 Session 引用；
- Session id/version/lifecycle/scheduling state；
- 当前 constraints、availability、request、proposal、selection；
- 当前/待提交 Appointment Revision 与 current Booking ref；
- 当前 ActionExecution/receipt refs 的最小状态；
- 当前 ProcessingControl set、ActionPolicy、等待对象、下一检查和最晚升级。

明确不返回：

- 完整简历、人岗匹配材料或部门评价；
- 日历事件标题/正文；
- 候选人和面试官不必要联系方式；
- token secret、完整 Provider payload、告知全文或内部安全策略。

Service 自动化不得借用 HUMAN 的全租户投影构造命令。

### 10.2 Candidate view：`CANDIDATE_COORDINATION_VIEW`

候选人只经当前安全 token 读取自己的 request revision、岗位/轮次概述、时长、参与人角色、时区、当前 Proposal、选时/一次改期入口，以及 Recording Notice/选择状态。它不能读取内部匹配、负责人决定依据、他人日历正文、内部 ActionExecution 或其他候选人。“全部不可用”、可访问性需求和人工协助若出现在本期 Demo，只能标成未接通的体验占位，不计入 `IMPLEMENTED`。

### 10.3 Operations view：`BOOKING_RECONCILIATION_VIEW`

仅招聘运营/受控 Service 可读取当前 Appointment Revision、三类资源动作、回执、外部 revision、对账状态、重试预算、补偿和异常；默认隐藏 Provider payload 与候选人正文。

## 11. 状态与当前性规则

### 11.1 正常链

```text
InterviewSession.scheduling_state
NOT_STARTED
  -> COORDINATING
  -> PROPOSAL_OPEN
  -> BOOKING_PENDING
  -> BOOKED
```

- `RecordCandidateSlotSelection` 只追加选择意图，Session 在 `ProposeAppointmentRevision` 成功前仍保持 `PROPOSAL_OPEN`。
- 单个资源成功仍保持 `BOOKING_PENDING`。
- 只有 `CommitBooking` 可写 `BOOKED`。

### 11.2 改期链

```text
BOOKED
  -> RESCHEDULING  # old current Booking + new pending Appointment Revision
  -> BOOKED        # new Booking committed, then old resources compensated
```

- 新修订失败或放弃时，旧 Booking 继续 current。
- 新 Booking 提交成功后，旧资源进入取消/撤链；旧 Provider 回调只审计或补偿。
- 任何时候内部至多一个 current Booking。

### 11.3 回执有效性

一份回执只有同时满足下列条件才可进入 BookingReceiptSet：

- ActionExecution 已被当前 Connector 结果确认 `SUCCEEDED`；
- action id、case、session、appointment revision、resource type、operation、payload hash 全部匹配；
- external resource id 与 revision/ETag 齐全；
- policy、lifecycle epoch、routing revision、processing control set 仍当前；
- 同一 required resource type 没有冲突 current receipt；
- 回执未被取消、失效、替代或标记待对账。

## 12. 十二个合成验收场景

| # | 既有需求/场景映射 | Given / When | Then 与必须保留的证据 |
|---:|---|---|---|
| 1 | FR-237；不宣称 AT-214 全量 | fixture 有一个当前 `READY_TO_SCHEDULE` Round 和一个 `PLANNED / NOT_STARTED` 必需 Session；自动编排打开协调 | 恰有一个 current Candidate Coordination Request；Case 保持 INTERVIEWING；明确记录 fixture 起点，未消费 INVITE seam |
| 2 | FR-240；AT-227 | 当前、错人、重放、过期和旧 revision token 分别访问/提交 | 只有当前正确 token 可读写；其余结构化拒绝且 request/proposal/selection/version 不变 |
| 3 | FR-238/239；AT-215 | Proposal 已过期、忙闲授权撤销或 constraint/availability hash 已变化 | 旧 Proposal 被拒绝/标记 SUPERSEDED；不产生 Selection、Appointment Revision 或外部动作；可发布新 Proposal |
| 4 | FR-241/242/243；AT-215 | 候选人选择当前时段，随后忙闲重验发现冲突 | Selection 被保留为历史意图；不形成 Booking、不执行三类 WRITE；生成新 Proposal 或单一异常 |
| 5 | FR-241/243；ADR-0007 | 候选人选择当前时段但尚未提出/提交 Appointment Revision | 页面只显示“正在确认”；`current_booking_ref` 为空、`InterviewBookingCommitted=0`、资源写入业务效果为 0 |
| 6 | FR-242..245 | 当前 Appointment Revision 的 calendar、meeting、invitation WRITE 依次成功并获得 current 回执 | 前两项成功仍为 BOOKING_PENDING；第三项后只由 CommitBooking 形成一个 InterviewBooking 和一个 BookingReceiptSet；重复 Commit 幂等 |
| 7 | FR-243/244/248；AT-217/220 | 日历成功但会议失败、邀请缺回执、权限撤销或 Provider 故障 | 不显示 BOOKED/SCHEDULED；保留每项真实状态；有限重试/对账/补偿，耗尽后只有一个 current Exception Bundle |
| 8 | FR-243..245；AT-217 | Provider 成功但响应丢失，随后相同回调重复十次 | 先对账，不重复创建资源；每类一个业务效果、一个 current receipt，最终至多一个 Booking |
| 9 | FR-242..244；AT-216 | 两个 Case 通过同一个共享合成 Provider 并发抢同一面试官时段 | Provider 条件写/CAS 至多允许一个当前资源与一个 Booking；失败方回新 Proposal，不双占；单 Case 顺序测试不能替代此证据 |
| 10 | FR-246/248；AT-218 | 已有 Booking，候选人发起一次改期；新 Appointment Revision 部分失败或放弃 | Session 为 RESCHEDULING 时旧 Booking 继续 current；失败不让会话看似无安排；重试耗尽进入异常而非无限循环 |
| 11 | FR-246/247；AT-218/219 | 新 Booking 成功后旧 revision 回调迟到；或候选人撤回/Case 关闭时旧资源仍存在 | current pointer 只指新 Booking；旧回调只审计/补偿且不能复活；生产 WRITE 被阻断，允许的 CANCEL/REVOKE 安全补偿继续 |
| 12 | FR-245/249；ADR-0008；AT-221 | 邀请含当前 Recording Notice version，且有或没有独立送达证明，但没有 ConsentReceipt | Booking 可按资源回执成立；只有真实送达证明才记 RecordingNoticeDelivered；`ConsentReceipt=0`、capture action count=0，页面显示“已告知/送达待确认/尚未选择”而非“已同意” |

`AT-214` 的多 Session Round 和 `AT-222..226` 的采集/交接控制不因上述任一测试通过而获得实现状态。

## 13. P0 / P1 边界

### 13.1 P0：立即阻断并冻结受影响动作

- Scheduling Proposal、SlotSelection 或单一回执被显示为已预定。
- 缺任一 current required receipt、receipt revision 不匹配或 payload hash 冲突仍形成 Booking。
- 同一 Session 同时出现两个 current Booking，或两个 Case 双占同一 Provider 时段。
- 旧 request/proposal/appointment/action/link/callback 写入当前状态或复活旧 Booking。
- 错租户、错 Case、错候选人、错参与人或错误邀请收件人产生任何外部效果。
- 候选人撤回、Case PAUSED/CLOSED、权限撤销或处理控制生效后生产 WRITE 继续执行。
- 安全 CANCEL/REVOKE 被普通 PAUSED/CLOSED 门错误阻断。
- invitation WRITE、邀请接受、告知送达或入会被解释为 ConsentReceipt。
- 合成测试产生真实外部效果、读取真实账号或个人信息。

### 13.2 P1：保持事实诚实，有限恢复或形成异常包

- Proposal 过期、选后忙闲变化、没有共同时间。
- 日历权限撤销、Provider 暂时故障、资源部分成功或送达状态未知。
- 时区、DST、长文本、本地化或可访问性导致候选人可能误选。
- 改期次数/时间窗耗尽、候选人全部不可用或请求人工协助。
- 外部重复资源已存在但内部 current Booking 仍唯一；需对账和补偿。
- 邀请资源已写入但送达/已读未确认；Booking 与通知异常必须分开显示。

P1 不能通过乐观显示、无限重试或静默停滞降级成“看起来成功”。有限预算耗尽后交付一个可决策 Exception Bundle。

## 14. 实施顺序

1. 建立 `recruiting_scheduling` Module、SQLite 合成聚合表、命令结果、事件和 Outbox；先只支持 fixture 起点。
2. 按公开 `submit/read` seam 逐场景做红→绿纵切：先让当前一个场景失败，只实现足够使其通过的 Candidate Coordination Request、Proposal 或 Selection 行为，再进入下一个场景；不一次性写完十二个想象测试。
3. 实现 Appointment Revision 与 `SCHEDULING_CASE_CONTEXT`，锁住 proposal/selection 非 Booking。
4. 实现三个合成 Booking Resource Adapter 和各自 ActionExecution；加入丢响应、重复、迟到、权限撤销和部分成功故障注入。
5. 实现 BookingReceiptSet validator 和 `CommitBooking`；任何不完整/陈旧回执均拒绝。
6. 实现共享合成 Provider 的原子 slot reservation，覆盖两 Case 并发。
7. 实现一次改期、旧 Booking 保留、新成功后补偿和迟到旧回调抑制。
8. 实现 Recording Notice 版本/送达凭证投影，并断言全链不创建 ConsentReceipt 或 capture action。
9. 打通移动优先 Demo 与运行内核，默认三步、运行详情折叠、状态词与领域事实一致。
10. 形成独立验收记录，逐项列出已证明/未证明，G2 权威矩阵继续保持 `SPEC`。

## 15. 验证与证据槽

### 15.1 自动行为证据

实施完成后至少保存：

- 十二个专项场景的测试名、运行命令、通过数和 commit SHA；
- 每个场景的 command result、aggregate version、domain event、ActionExecution、receipt 和 Booking 数量断言；
- `real_external_effect_count=0`；
- 同键同载重放/同键异载拒绝；
- 两 Case 共享 Provider 的并发结果；
- 十次重复/迟到 callback 的 effect count；
- notice delivery count、ConsentReceipt count 和 capture action count 分离断言；
- 全 runtime 回归与 GitHub runner 链接。

“脚本能打开”“页面文字存在”或静态 token checker 不能替代上述运行行为证据。

### 15.2 产品体验证据

最低需要记录：

- 桌面与候选人移动宽度的正常链；
- 选时后、回执不全时绝不显示已预约；
- Proposal 过期、选后冲突、改期失败和送达未知的恢复文案；
- Notice 已提供/已送达/尚未选择三种状态不混淆；
- 键盘焦点、200% 缩放、非颜色状态和长时区文本的静态/工具检查结果。

真人任务、读屏和法律理解测试未发生时，只能写“未验证”，不能由截图替代。

### 15.3 允许声称

只有行为测试、Demo checker、回归和验收记录全部通过后，才允许声称：

> 核心功能 3 的一个精确合成子集已实现：从 fixture-only 当前可约面 Session 开始，候选人可选择版本化时段，控制面在选后重验并以三类当前合成资源写回执提交唯一 InterviewBooking；Proposal/Selection 不等于 Booking，Recording Notice 不等于 ConsentReceipt。状态为 `IMPLEMENTED / SYNTHETIC_ONLY`。

### 15.4 明确不证明

即使全部合成测试通过，仍不证明：

- `INVITE → Plan → Round → Session` 物化 seam；
- 真实日历、会议、邀请或 Provider 回调可用；
- 生产 IAM、候选人身份、跨租户/跨案件访问正确；
- 生产数据库、多节点并发、Exactly-once、容灾或恢复；
- 真实邀请送达、真人能理解/完成、无障碍和时区/DST 正确；
- Recording Notice 文案合法、已获得 ConsentReceipt 或可以录制；
- 多 Session Round 已正确投影为 SCHEDULED；
- G2 `FR-237..249` 或 `AT-214..227` 已整体实现；
- 任一 A0/A1/A2/A3、Gate 0 Go、发布或真实招聘托管效果。

## 16. 完成定义

本 bounded 切片只有在以下全部有当前可检查证据时，才算完成：

- 业务状态读写 Interface 只有 `submit/read`；fixture setup helper 不属于业务 API。自动化使用 Case-bound view，不借用 HUMAN 全量投影。
- 十二个合成验收场景逐一通过，且测试真正覆盖状态、回执和副作用数量。
- 任一 Proposal、Selection、部分回执或迟到回调都不能产生或复活 Booking。
- 三类 current resource WRITE receipt 齐全才提交唯一 InterviewBooking。
- 改期失败保留旧 Booking；新 Booking 成功后才补偿旧资源。
- Notice、delivery receipt、ConsentReceipt 和 capture action 四类事实在 Schema、状态、UI 和测试中分离。
- 所有外部数据/效果为合成，真实外部效果为 0。
- 独立验收记录准确列出 fixture-only 起点、已证明与未证明；G2 权威矩阵、No-go 和发布结论不变。
