# 招聘 Agent 核心功能 3：候选人约面合成 Demo 验收记录

日期：2026-08-11

状态：`IMPLEMENTED / SYNTHETIC_ONLY` 精确子集；`VERIFIED / RELEASED` 均未达到

范围：fixture-only 当前可约面 Session → 候选人协调请求 → 当前时段提案 → 候选人选时 → 选后重验 → 日历/会议/邀请三类合成写入与对账 → 唯一当前 Booking

## 1. 本次可验收产物

- [候选人约面 Demo](./prototype/招聘Agent_核心功能3_候选人约面Demo.html)：默认三步“选择时间 → 正在确认 → 面试已安排”，十二个危险场景渐进披露。
- [bounded 实施规格](./招聘Agent_核心功能3_候选人约面实施规格.md)：冻结起点、终点、公共接口、既有 FR/AT 映射和证据边界。
- [合成 scheduling 实现](./runtime/recruiting_scheduling/)：业务状态读写 seam 为 `submit(command_envelope)` 与 case-bound `read(projection_request)`；合成 fixture helper 只用于测试装配，不属于业务 API。
- [行为测试](./runtime/tests/test_scheduling_walking_skeleton.py)：12 条公开 seam 行为测试。
- [合成验收 runner](./runtime/run_synthetic_scheduling.py)：正常 Booking、响应丢失先对账、告知不产生同意和零真实外部效果。
- [Demo 行为检查](./prototype/check_scheduling_demo.mjs)：独立状态机、十二危险场景、渐进披露、XSS 和移动布局断言。

## 2. 当前实现命令

本切片实现以下受控命令：

1. `OpenCandidateCoordinationRequest`
2. `PublishSchedulingProposal`
3. `RecordCandidateSlotSelection`
4. `ProposeAppointmentRevision`
5. `QueueSchedulingAction`
6. `ExecuteSchedulingAction`
7. `ReconcileSchedulingAction`
8. `RecordSchedulingProviderObservation`
9. `CommitBooking`
10. `SupersedeAppointmentRevision`
11. `PauseScope`
12. `QueueSchedulingCompensation`
13. `RecordRecordingNoticeDelivery`

所有 Provider 都是带合成 capability 的固定 Adapter；没有真实网络、日历、会议、邀请或录制动作。

## 3. 当前实现能够证明什么

- 起点明确是 fixture-only 的当前 `READY_TO_SCHEDULE` Round 与一个 `PLANNED / NOT_STARTED` 必需 Session；不会冒充核心功能 2 的 `INVITE → InterviewPlan → Round → Session` seam 已实现。
- 当前协调入口绑定 Case、Session、用途、request revision、credential revision 和有效期；错人、跨租户、旧 revision 或重放不能改变当前选择。
- `SchedulingProposal` 钉住当前约束、时区、参与人角色、忙闲快照和有效期；过期提案不能记录选择。
- 候选人选时只形成 `SlotSelection` 意图，投影明确保持“未预定”；选后忙闲变化会阻断 Appointment 和三类资源写入。
- 同一当前 Appointment Revision 必须分别取得日历、会议和邀请写入三类回执；任一缺失时不能 `CommitBooking`，齐全后只产生一个当前 Booking。
- Provider 已成功但响应丢失时，Action 先进入 outcome unknown，再通过合成对账接受已有资源；不会盲目创建第二份资源。
- 重复 callback、迟到 callback 和旧 Appointment Revision 只保留为审计/补偿事实，不能覆盖或复活当前 Booking。
- Case 暂停优先于生产写入和 Booking Commit；精确白名单的安全取消仍可执行。两个 Case 争用同一合成日历时段时最多一个成功占位。
- 服务身份只能读取指定 Case、Session 与用途的最小视图；资源效果计数按 Case 隔离，不泄露其他案件活动。
- 参与人引用使用精确白名单字段；额外邮箱等字段不会被持久化或投影。命令中的当前引用和版本使用封闭类型，布尔值不能冒充整数版本。
- Invitation write、邀请实际送达/已读、Recording Notice delivery 和 ConsentReceipt 严格分开。当前 runner 只有一条合成告知送达事实，`consent_receipt_count=0`。
- Adapter 必须提供合成 capability，任意 Connector 不能被注入后仍得到 `synthetic_only=true`。runner 的 `real_external_effect_count=0` 是受控边界，不是无条件硬编码宣传。
- 产品 Demo 默认只让候选人理解本人必须做的一件事；选择后显示“现在还不是已预定”，三项回执齐全后才显示“面试已安排”。录制选择默认未选，选择“不录制”不影响预约。

上述结论只允许把这组精确、合成、可执行行为记为 `IMPLEMENTED / SYNTHETIC_ONLY`。G2 需求追踪矩阵继续保持 `SPEC`，本记录不把完整 `FR-237..249`、`AT-214..227`、整个 G2 或端到端 Agent 升级为已实现。

## 4. 当前验证快照

2026-08-11 在本地工作区复跑：

| 检查 | 当前结果 | 证据边界 |
|---|---:|---|
| `python3 -m unittest runtime.tests.test_scheduling_walking_skeleton -v` | 12 / 12 通过 | 只覆盖 `recruiting_scheduling` 当前公开行为子集 |
| `python3 -m unittest discover -s runtime/tests -v` | 117 / 117 通过 | 当前全 runtime 本地快照：既有 105 条 + scheduling 12 条 |
| `python3 runtime/run_synthetic_scheduling.py` | PASS | selection 非 Booking、三回执后唯一 Booking、响应丢失先对账、Notice 不产生 Consent、真实外部效果 0 |
| `node prototype/check_scheduling_demo.mjs` | PASS | 十二危险场景、独立状态机、XSS/移动断言；不代替真人可用性 |
| 本地浏览器复验 | PASS | 桌面端已实际点击正常链、不录制路线与改期保护；390px 无横向溢出，仍不代替真人任务、读屏或视觉定稿 |

这些是当前本地快照；在相同提交的线上 CI 完成前，不表述为 GitHub runner 证据。

## 5. 当前不能证明什么

- 不证明核心功能 2 的 HUMAN `INVITE` 已真实物化 Interview Plan、Round、Session 或自动打开候选人协调请求；当前起点来自固定 fixture。
- 不证明真实 Google/Outlook/飞书日历、会议平台、邮箱/IM 邀请、候选人身份、链接签发或联系人系统已接入。
- 不证明邀请实际送达、已读或候选人收到 Recording Notice；写入回执和合成 Notice delivery 都不是真实送达证据。
- 不证明任何有效 ConsentReceipt、录制授权、Capture Gate、录制开始/停止、无录制证据路线或法务批准。
- 不证明生产数据库、分布式 Outbox/worker、Provider lease、真实 Exactly-once、多节点竞争、灾难恢复或生产安全补偿。
- 不证明复杂多轮、多 Session、跨组织调度、替换面试官、候选人全部时段不可用、辅助需求或人工协助闭环。
- 不证明 Demo 与 Python 内核已线上打通；两者分别是产品状态机和合成行为内核。
- 不证明候选人/招聘运营真人任务成功、完整键盘/读屏/200% 缩放无障碍、隐私法务批准、真实 A0/A1 或发布效果。

## 6. 下一步

1. 先把核心功能 2 的当前 `INVITE` 事实到 Interview Plan/Round/Session 物化 seam 做成同一合成纵切。
2. 再在批准的沙箱接入一个日历 Provider，先做只读忙闲与最小化字段审计，再放行单一写入动作。
3. 补真实候选人协调身份、邀请实际送达/失败对账和“全部时段不可用/人工协助”路线。
4. 录制告知、ConsentReceipt 和 Capture Gate 保持独立切片，法务/隐私未批准前不接真实录制。

## 7. Gate 结论

Gate 0 保持 **No-go**：真实个人信息、真实日历/会议/邀请、真实候选人身份、录制同意和任何外部写操作均未放行。本记录只证明核心功能 3 的一个精确合成行为子集，不改变 G2 矩阵 `SPEC` 状态或任何现有 Gate 结论。
