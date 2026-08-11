# 招聘 Agent 核心功能 2：画像匹配与部门决定合成 Demo 验收记录

日期：2026-08-11

状态：`IMPLEMENTED / SYNTHETIC_ONLY` 精确子集；`VERIFIED / RELEASED` 均未达到

范围：`ApplicationCase.RECEIVED` → 钉住筛选输入 → 四态证据匹配 → 发布校验 → 唯一权威部门任务 → 合成通知/有限催办 → 当前授权 `HUMAN` 提交 `INVITE / HOLD / REJECT`

## 1. 本次可验收产物

- [核心功能 2 可点击 Demo](./prototype/招聘Agent_核心功能2_画像匹配与部门决定Demo.html)：八个完全虚构的场景，展示正常链、低证据、禁用信号、版本变化、HOLD、SLA 耗尽、错误收件人与决定越权。
- [合成 screening 运行实现](./runtime/recruiting_screening/)：`RecruitingG2Control` 复用核心功能 1 的 `submit(command_envelope)` / `read(projection_request)` 深模块接口和同一权威 `ApplicationCase` 行。
- [行为测试](./runtime/tests/test_screening_walking_skeleton.py)：34 条简历筛选与部门决定行为测试。
- [合成验收 runner](./runtime/run_synthetic_screening.py)：从核心功能 1 的 `NORMAL` Case 继续执行正常 HUMAN INVITE、低/未知证据人审、污染发布阻断、决定后排队催办阻断、SLA 耗尽和跨租户收件人阻断。
- [Demo 行为检查](./prototype/check_screening_demo.mjs)：执行独立状态机、八场景及安全文案检查。

## 2. 当前实现命令

本切片只实现以下九类受控命令：

1. `PinScreeningInput`
2. `PublishMatchAssessment`
3. `OpenDepartmentDecisionRequest`
4. `QueueDepartmentDelivery`
5. `ExecuteSyntheticDelivery`
6. `AdvanceReminderOrdinal`
7. `RecordDepartmentDecision`
8. `ResumeDepartmentDecisionRequest`
9. `InvalidateCurrentMatchAssessment`

`QueueDepartmentDelivery` 与 `ExecuteSyntheticDelivery` 只建立合成 `ActionExecution` 和合成回执，不会连接邮件或 IM；`RecordDepartmentDecision` 也不隐式发送候选人拒信。

## 3. 当前实现能够证明什么

- 合成正常链复用核心功能 1 产生的唯一 `ApplicationCase.RECEIVED`，不重建第二个 Case。
- `PinScreeningInput` 精确钉住当前结构化简历、ACTIVE 已发布画像版本/发布修订/安全纪元、允许字段及服务端当前策略/生成器版本；旧简历、旧/非 ACTIVE 画像、旧策略或保护字段不能被钉住。
- `MatchAssessment` 按画像维度区分 `SUPPORT / COUNTER_EVIDENCE / UNKNOWN / NOT_APPLICABLE`，关键支持/反证必须保留 locator；低匹配或未知仍会形成人审材料，自动淘汰和候选人拒信计数均为 0。
- 发布门阻断缺失必需维度、伪造/缺失的证据 locator/hash，以及中英文保护字段、明显代理变量、中英文提示注入、决定和排名字段；被阻断的材料不会建立部门任务或外部动作。
- 一个 Case 只有一个当前 `ScreeningInputManifest`、一个当前匹配材料指针和一个权威 `DepartmentDecisionRequest`；产品内任务是唯一决定入口，合成通知不是第二个任务。
- 决定必须同时匹配当前 Case 版本/lifecycle epoch、request revision/SLA generation、材料引用、Owner 与 authority revision；`SERVICE`/`AGENT`、旧卡、旧 Owner/权限、双击或跨修订复用 decision ID 不会产生第二个决定。
- `INVITE` 将 Case 推进到 `INTERVIEWING`；`REJECT` 将 Case 关闭，但不发送拒信；`HOLD` 保持 `AWAITING_DEPARTMENT_DECISION`、停止催办并建立新 `ON_HOLD` revision，到期只生成新 `OPEN` revision/generation，不替人决定。
- 简历/画像等因果输入变化时，当前材料指针、部门请求及旧待执行动作一起失效，Case 回到 `SCREENING`；旧材料或旧卡无法写当前状态。
- 同一 ApplicationKey 收到新的结构化简历并附加到当前 Case 时，现有筛选输入和负责人任务会一并失效，必须基于新材料重做筛选；刷新 Case 版本不能让旧卡复活。
- Case 只允许钉住当前结构化简历；重新打开的部门任务使用单调新身份，旧简历、旧 request 或旧排队动作都不能在新材料下复活。
- `SCREENING_WORKFLOW`、`MATCH_GENERATOR` 和 `DELIVERY_WORKER` 只读取当前案件中各自工作所需的最小视图；合成自动化路径不借用 HUMAN 全租户投影。
- 合成 SLA 催办重验静默时段、request revision、generation 和 ordinal，最多两次；耗尽后只建立一个当前异常包，不把沉默解释为决定。人工决定会关闭当前任务并结算该超时异常。决定生效后才到达的排队催办会被阻断且不产生送达效果。
- 合成送达的临时失败允许在当前 request 仍有效时进行一次有版本的有限重试；第二次成功只形成一个送达回执，不会重复部门任务。
- 催办 ordinal 只有在上一条合成提醒已有送达回执后才能继续；`0` 与布尔值 `False` 不能制造两个初始通知。重试耗尽会形成一个可见的动作异常包。
- 错误或跨租户部门收件人在 `ActionExecution` 建立前就被阻断；合成 runner 明确输出 `real_external_effect_count=0`。
- Demo 默认只展示“简历与岗位 → 筛选卡 → 用人负责人决定”三步；版本、Agent Activity、SLA 和安全回执渐进披露。独立状态机仍保留四态证据、唯一权威任务、HUMAN 决定、HOLD 恢复、版本失效、SLA 耗尽和错误收件人安全边界。

上述结论只允许把这组精确、合成、可执行行为记为 `IMPLEMENTED / SYNTHETIC_ONLY`。G2 需求追踪矩阵继续保持 `SPEC`，本记录不把完整 `FR-219..236`、`AT-205..213`、`AT-228` 或其他 G2 条目升级为已实现。

## 4. 当前验证快照

2026-08-11 在本地工作区复跑：

| 检查 | 当前结果 | 证据边界 |
|---|---:|---|
| `python3 -m unittest runtime.tests.test_screening_walking_skeleton -v` | 34 / 34 通过 | 只覆盖 `recruiting_screening` 当前行为子集 |
| `python3 -m unittest discover -s runtime/tests -v` | 105 / 105 通过 | 当前全 runtime 本地快照：既有 71 条 + screening 34 条 |
| `python3 runtime/run_synthetic_screening.py` | PASS | 正常 HUMAN INVITE、低/未知证据人审、发布/催办/收件人安全分支；`synthetic_only=true`、真实外部效果为 0 |
| `node prototype/check_screening_demo.mjs` | PASS | 八场景状态机与关键交互断言可执行；不代替真人可用性测试 |
| 本地浏览器手动复验 | PASS | 桌面端已实际点击正常 `INVITE`、HOLD 停催/到期恢复未选择任务和“不推进但不发候选人沟通”；1280×720 与 390×844 首屏、三步名称、18px 单选框、无横向溢出及抽屉焦点隔离已用真实浏览器复验，但尚未纳入 CI，也不代替真人任务、读屏或视觉定稿 |

这些是当前本地快照；在相同提交的线上 CI 完成前，不表述为 GitHub runner 证据。

## 5. 当前不能证明什么

- 不证明真实简历解析、画像匹配模型的准确率、公平性、成本、稳定性或可解释质量。
- 不证明真实邮箱、ATS、IM/邮件卡片、深链、送达回执、超时升级或收件人管理已可用。
- 不证明 Owner 缺失或错误收件人已通过独立持久化 ExceptionBundle 接管；当前切片只证明外发前结构化阻断。重试耗尽目前只有合成动作级异常包，不冒充生产运维接管。
- 不证明生产 IAM、实名 Owner/权限变更、租户边界、保护字段存储或真实审计已完成；当前权限是精确合成 fixture grant。
- 不证明生产数据库、分布式 worker/Outbox、多节点锁竞争、真实 Timer/静默时段、容灾、重启恢复或 Exactly-once 外部效果。
- 不证明 REJECT 之后的候选人拒信生成、审批、发送或回执；当前实现明确保持候选人拒信为 0。
- 不证明读面试官日历、候选人选时、建会、发会议邀请、改期/取消、录制告知或无录制路线。
- 不证明 Demo 与 Python 内核已线上打通；Demo 是独立的合成产品状态机。
- 不证明用人负责人、HR 或候选人真人任务成功、键盘/读屏/200% 缩放等无障碍、法务/隐私/公平审批、真实 A0/A1 或商业效果。
- 不证明完整 `FR-219..236`、`AT-205..213`、`AT-228`、整个 G2、完整端到端招聘 Agent 或任何真实发布门已完成。

## 6. 下一个工程切片

1. 先把核心功能 2 的任务卡、合成通知和内核统一为可以通过安全深链验证的同一 request revision。
2. 用批准的匿名/合成金标评测四态证据、locator、未知与代理变量阻断，不直接接入真实简历。
3. 在沙箱里接入一个部门通知通道，补送达/失败/撤回对账、收件人变更、Timer 与并发 worker 故障注入，继续保持决定仅 HUMAN。
4. 当部门 HUMAN `INVITE` 成为已验证事实后，再进入核心功能 3：候选人协调与日历约面。

## 7. Gate 结论

Gate 0 保持 **No-go**：真实个人信息、真实模型、真实邮箱/IM/IAM、真实 A0/A1 和任何外部发送或写入均未放行。本记录只证明核心功能 2 的一个精确合成行为子集，不改变 G2 矩阵 `SPEC` 状态或任何现有 Gate 结论。
