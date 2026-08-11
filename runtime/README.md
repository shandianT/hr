# 招聘 Agent 合成控制面运行实现

状态：`IMPLEMENTED / SYNTHETIC_ONLY` 候选；尚未形成目标环境验证或发布证据。

本目录目前包含三条边界明确的可执行纵切：核心功能 1 负责 Case 出现前的收件与开案，核心功能 2 复用同一 Case 执行画像匹配和部门决定，G1a 负责面后证据到轮次归档。

## 核心功能 1：简历收件到自动开案

独立 Module `recruiting_intake` 负责 Case 出现之前的流程：

> 批准来源 → 附件门 → 结构化简历版本 → 去重与身份信号 → 唯一岗位/周期路由 → 自动开案或附加来源

它与 G1a 后半程控制面使用相同的公共形状：

```python
intake.submit(command_envelope) -> command_result
intake.read(projection_request) -> intake_projection
```

当前实现四类命令：

- `RegisterResumeSubmission`
- `RecordStructuredResumeVersion`
- `ResolveApplicationRouting`
- `OpenOrAttachApplicationCase`

已锁定的合成行为包括：

- 批准来源与来源修订门；来源事件、附件、内容 + 申请意图和命令幂等各自防重。
- 正常路径零 HR 启动，只有当前 `ROUTED` 修订可以创建 `ApplicationCase.RECEIVED`。
- 邮箱与 ATS 的同一申请重复到达只附加来源血缘，不产生第二案件业务效果。
- 邮箱、手机号、姓名和内容哈希只作身份信号；共享信号停在 `ROUTING_REVIEW_REQUIRED`，仅当前 `HIRING_OWNER` 可从已展示候选项提交判断。
- 同一候选人申请不同岗位形成两个隔离 ApplicationKey，不因内容相同而合并。
- 加密、损坏、不支持、恶意或扫描未知附件，以及低质量解析，都不会编造结构化字段或开案；异常预算有限。
- 简历内提示注入只保存为不可信正文发现，工具调用和外部动作始终为 0。
- 不可信解析结果先经过 closed-schema 校验；普通字段只允许当前白名单并保留 locator 与置信信号，保护字段进入隔离区，未知字段进入脱敏 quarantine。
- 开案或附加来源命令必须直接指向当前 ApplicationKey 对应的 Case 聚合，并钉住 Routing Revision、Case version 与 lifecycle epoch；同键异载和越权人工候选项明确拒绝。
- 当前读写授权是精确的合成 fixture grant，用来证明门的行为形状，不冒充生产身份网关。

该切片仍不接真实邮箱、ATS、文件扫描或模型，也没有实现多附件拆人、已开案改键纠正、删除传播、生产身份网关或并发多节点验证。因此它只支持当前行为子集的 `IMPLEMENTED / SYNTHETIC_ONLY`，不能把整个 FR-201..218 或 AT-201..205 升为已完成。

## 核心功能 2：画像匹配与部门决定

`recruiting_screening` 在核心功能 1 建立的同一权威 `ApplicationCase.RECEIVED` 上继续：

> 钉住结构化简历/已发布画像/允许字段/策略 → 四态证据匹配 → 发布门 → 唯一权威部门任务 → 合成通知与有限催办 → 授权 HUMAN 决定

公共接口仍只有：

```python
screening.submit(command_envelope) -> command_result
screening.read(projection_request) -> screening_projection
```

当前实现九类命令：

- `PinScreeningInput`
- `PublishMatchAssessment`
- `OpenDepartmentDecisionRequest`
- `QueueDepartmentDelivery`
- `ExecuteSyntheticDelivery`
- `AdvanceReminderOrdinal`
- `RecordDepartmentDecision`
- `ResumeDepartmentDecisionRequest`
- `InvalidateCurrentMatchAssessment`

已锁定的精确合成行为包括：

- 筛选输入钉住当前简历、ACTIVE 画像发布修订/安全纪元、允许字段和服务端当前策略/生成器；旧版本、非 ACTIVE 画像、旧策略与保护字段钉住被拒绝。
- `MatchAssessment` 按维度保留 `SUPPORT / COUNTER_EVIDENCE / UNKNOWN / NOT_APPLICABLE` 和证据 locator；低匹配或未知仍建立人审任务，不自动淘汰或发拒信。
- 发布门阻断缺维度、伪造/缺失 locator/hash、中英文保护或明显代理字段、中英文提示注入、决定与排名字段；畸形嵌套输入返回结构化拒绝，不抛出运行时异常。
- Case 同时只有一个当前筛选清单、匹配材料指针和权威 `DepartmentDecisionRequest`；合成通知是 `ActionExecution`，不是第二个决定任务。
- `RecordDepartmentDecision` 只接受当前授权 `HIRING_OWNER` HUMAN、当前 request/material/Owner/authority/lifecycle；Service、Agent、旧卡、旧 Owner 或双击不产生第二决定。
- `INVITE` 推进到 `INTERVIEWING`；`REJECT` 关闭 Case 但不隐式发拒信；`HOLD` 停催并产生新 `ON_HOLD` revision，到期只恢复新 `OPEN` revision/generation，不替人决定。
- 材料因果输入变化会在同一 Case 事务撤销当前指针/请求并使旧动作失效，Case 回到 `SCREENING`。
- 新结构化简历附加到同一 Case 时会同时失效当前筛选输入与负责人任务；Case 只允许钉住当前结构化简历，旧简历、旧卡或旧排队动作都不能在新请求下复活。
- `SCREENING_WORKFLOW`、`MATCH_GENERATOR` 与 `DELIVERY_WORKER` 只读取当前案件和各自用途所需的最小视图；自动化场景不借用 HUMAN 的全租户投影来构造 Service 命令。
- 催办重验静默时段、request revision、generation 与 ordinal，最多两次；上一条合成提醒没有送达回执时不能继续授权下一 ordinal 或上报。耗尽后只建一个异常包，决定后迟到催办被阻断。临时送达失败可在当前 request 下有限重试并以动作版本结算，耗尽后形成动作级异常包。
- 错误/跨租户收件人在 action 建立前被拒绝；所有通知/催办回执都是合成数据，`real_external_effect_count=0`。

34 条专项行为测试已本地通过；当前全 runtime 快照为 105 / 105 通过。该切片仍不证明真实匹配模型、IM/邮件、IAM、独立持久化的 Owner/错误收件人异常接管、分布式 worker/并发、拒信、日历约面、真人或法务已可用。它只支持精确行为子集的 `IMPLEMENTED / SYNTHETIC_ONLY`；G2 需求追踪矩阵继续保持 `SPEC`。

## G1a：面试证据到轮次归档

本目录还把 G1a 的第一条工程纵切变成可执行行为：

> 已结束会话 → 受控导入 → 证据/逐字稿 → 评价草稿 → 人工确认 → 独立人工轮次决定 → 不可变归档

实现只使用完全虚构的固定数据、Python 标准库和本地 SQLite。它不会启动网络监听，不读取真实账号、凭据或个人信息，也不会连接邮箱、日历、会议、消息、ATS、对象存储或模型供应商。

## Module 与 Interface

业务调用方和行为测试只通过同一个深 Module：

```python
control.submit(command_envelope) -> command_result
control.read(projection_request) -> case_projection
```

聚合存储、命令结果、领域事件、Outbox、版本和状态迁移都隐藏在 Implementation 内。状态不能通过 repository、setter 或页面字段绕过 `submit` 写入。

自动 Runner 是独立 Module：

```python
runner.start(workflow_version, automatic_commands) -> run_id
runner.tick(run_id, max_steps=1) -> run_projection
runner.read_run(run_id) -> run_projection
runner.resume(run_id) -> run_projection
```

Runner 只能提交自动化 `SERVICE` 命令。任何带 `HUMAN` actor 的确认或招聘决定都会在运行前被拒绝。`resume` 只会在已授权人先恢复 Case 后，以新 `run_epoch` 和新幂等上下文重试原阻塞步骤。

## 当前实现命令

运行行为覆盖 13 类命令：

- `RegisterCompletedSessionFact`
- `ImportCompletedInterview`
- `RegisterEvidenceArtifact`
- `RecordTranscriptOutcome`
- `RecordEvaluationDraftGenerated`
- `PublishEvaluationForReview`
- `SubmitEvaluationReview`
- `ReachConfirmationQuorum`
- `RecordRoundDecision`
- `PauseScope`
- `ResumeScope`
- `RequestExternalAction`
- `RecordExternalActionResult`

`PauseScope` / `ResumeScope` 目前只实现 `APPLICATION_CASE`，没有冒充 tenant/requisition 作用域已经可用。其余 G1a Schema 命令返回明确拒绝，不能据此标为已实现。

## 已锁定行为

- 命令先通过仓库内同版 Control Schema 子集验证，再依次重验当前权限、租户/案件/对象绑定、幂等、version、Case epoch 和暂停态。
- 同租户同幂等键、同规范负载和同当前 actor 返回 `REPLAYED`，不产生第二事件或动作；同键异载或异 actor 拒绝。
- 既有子聚合必须属于同一 Case，且其 lifecycle epoch 必须与当前 ApplicationCase 一致。
- 案件暂停时，排队命令和迟到成功回执在执行点被阻断；待执行 Outbox 转为 `SUPPRESSED` 并留下事件，恢复后也不会自动复活。
- 用于命令闸门的同意、录制对象引用 + hash、评分卡、画像、验证、评审策略和 evidence-set hash 都精确绑定 `tenant + case + lifecycle_epoch`。
- 证据 artifact 与逐字稿只能在关联轮次仍为 `EVIDENCE_PROCESSING` 时写入；评估确认后的迟到证据明确拒绝，不会被静默混入旧评估。
- 同一逐字稿的版本必须单调递增；重复或更低版本不产生第二个事实。
- 同一轮可保留多个草稿，但仅 Round 当前钉住的 `evaluation_id + version` 可被确认或达到 quorum。
- 关键结论证据覆盖不足不能形成评价草稿。
- 评价确认只把 Round 带到 `AWAITING_OUTCOME`；只有当前权限快照中授权的 `RECRUITER` HUMAN 可以提交 `RecordRoundDecision`。
- 归档钉住会话版本、artifact 版本与 checksum、逐字稿 ID/版本、评价聚合版本、确认记录、决定记录版本和生命周期 epoch；任一钉住输入变化都会改变 archive hash，完成后第二决定被拒绝。
- aggregate、command result、domain event 与 Outbox 在一个 SQLite 事务提交。
- 领域事件以完整 envelope 落库，且落库前通过同版 Event Schema 子集验证；event/action ID 以 tenant 复合键隔离。
- `read` 要求当前 authority snapshot，按角色隐藏恢复令牌、证据内容引用和完整审计 envelope。
- Runner 在“命令已提交、checkpoint 未保存”的崩溃窗中重启后得到 `REPLAYED` 并继续，不重复业务事实。
- 已抑制动作的取消回执使用该动作被抑制时钉住的 cancellation token，不会被后续暂停周期覆盖。

## 运行

从仓库根目录执行：

```bash
python3 -m unittest discover -s runtime/tests -v
python3 runtime/run_synthetic_intake.py
python3 runtime/run_synthetic_screening.py
python3 runtime/run_synthetic_g1a.py
```

行为测试不会访问网络。合成脚本输出机器可读 JSON 摘要；输出中的 `archive_hash` 只证明同一固定输入下的确定性归档，不证明报告质量或真实招聘效果。

## 现在仍不证明

- 零依赖验证器只实现了两份 Schema 已使用的关键字子集，不是通用 JSON Schema 2020-12 实现；19 命令/24 事件的完整正反 fixture 仍是后续门。
- SQLite 只证明本地事务，不证明多节点 Postgres、消息总线、锁竞争、容灾或生产恢复。
- 当前读写权限只是合成 authority fixture，没有真实身份网关；也没有真实连接器、模型、媒体、删除血缘或 ExceptionBundle 创建命令。
- `RecordExternalActionResult` 当前由测试中的合成 Connector 身份提交；尚无 lease、probe/reconciliation 或真实外部效果。
- 已有独立的合成产品形态 Demo，但尚未与本运行内核打通；没有真人任务、无障碍、模型质量、法务批准、A0/A1 或生产发布证据。

因此，本目录即使全部测试通过，也只能支持对应子集的 `IMPLEMENTED / SYNTHETIC_ONLY` 结论，不能支持 `VERIFIED`、`RELEASED` 或解除 Gate 0 No-go。
