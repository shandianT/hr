# 招聘 Agent G1a 需求追踪矩阵

> 版本：v0.2<br>
> 日期：2026-08-11<br>
> 基线：[G1a MVP PRD](./招聘Agent_G1_MVP_PRD.md)  
> 口径：`SPEC` 只表示需求已映射到接口、Backlog 和目标测试；没有实现与运行证据时不得标 `DONE`。

## 1. 状态与证据规则

| 状态 | 必要证据 |
|---|---|
| `UNMAPPED` | 尚未绑定工程故事或测试 |
| `SPEC` | 模块、命令/事件、Backlog、测试设计齐全 |
| `IMPLEMENTED` | 代码合并、契约/行为测试通过，但尚未完成业务放行 |
| `VERIFIED` | 目标环境运行证据、负面/竞态测试和 Owner 验收齐全 |
| `RELEASED` | 对应动作通过离线/A0/A1 的发布门并有回滚演练 |

证据 ID 默认为待实现槽位。只有 `EV-FR019`、`EV-FR022` 和 `EV-AT009` 已绑定到 [commit `ab8cf20`](https://github.com/shandianT/hr/commit/ab8cf205e297357fb8ee8555ebe3a3316f17b82e)、[CI run 31452559339](https://github.com/shandianT/hr/actions/runs/31452559339) 与完整行为测试。`SYNTHETIC_ONLY` 是证据范围限定，不是高于 `IMPLEMENTED` 的生命周期状态。

## 2. FR-001..032

| ID | 产品要求（压缩表述） | Module / Interface | Backlog | 目标测试与证据槽 | 当前 |
|---|---|---|---|---|---|
| FR-001 | 外部事件 + 资源 + 租户幂等 | Control / `RegisterEvidenceArtifact` | G1A-011,021 | `CT-IDEM-001`：同回调 10 次仅一任务；`EV-FR001` | SPEC |
| FR-002 | 媒体唯一绑定 Case/Round/Session | Session / `ImportCompletedInterview` | G1A-020,021 | `BT-BIND-001/002`：无匹配/多匹配均开异常；`EV-FR002` | SPEC |
| FR-003 | 所有需授权参与人处理前重验 | Privacy Gate / import、artifact、worker preflight | G1A-022 | `ST-CONSENT-001..003`：缺失/撤回/旧 notice；`EV-FR003` | SPEC |
| FR-004 | 人工上传 provenance 且不绕绑定/授权 | Session / `RegisterEvidenceArtifact` | G1A-021,022 | `BT-UPLOAD-001`：缺上传人/目的/绑定/授权拒绝；`EV-FR004` | SPEC |
| FR-005 | 撤回/关闭/暂停/删除阻断旧任务 | Control / every write + executor preflight | G1A-014,022,052 | `CT-CONTROL-001`：排队后变控制态仍阻断；`EV-FR005` | SPEC |
| FR-006 | 逐字稿含媒体版本、时间戳、说话人 | Evidence / `RecordTranscriptOutcome` | G1A-024,026 | `BT-TRANSCRIPT-001`：每证据可定位片段；`EV-FR006` | SPEC |
| FR-007 | 保存转写/说话人质量信号并降级 | Evidence / transcript outcome | G1A-024,025 | `BT-QC-001`：阈值下转人工或只出纪要；`EV-FR007` | SPEC |
| FR-008 | 证据保留原文引用、来源、范围、版本 | EvidencePointer | G1A-026 | `BT-EVIDENCE-001`：重跑生成新版本不覆盖；`EV-FR008` | SPEC |
| FR-009 | 低置信说话人不强制映射 | Evidence Validator | G1A-025,033 | `BT-SPEAKER-001`：关键错配阻断发布；`EV-FR009` | SPEC |
| FR-010 | 媒体/逐字稿/评价分级授权 | AuthZ + Artifact Store / `read` | G1A-002,004,023,041 | `ST-ABAC-001`：评价权限不能下载媒体；`EV-FR010` | SPEC |
| FR-011 | 使用案件锁定画像与评分卡 | VersionPin / evaluation commands | G1A-030 | `BT-PIN-001`：新版本不影响在途；`EV-FR011` | SPEC |
| FR-012 | 每条关键评价至少一条证据 | Evaluation Validator | G1A-033 | `BT-CLAIM-001`：零证据关键 claim 阻断；`EV-FR012` | SPEC |
| FR-013 | 区分事实/判断/存疑/信息不足 | Evaluation Claim Schema | G1A-032 | `CT-EVAL-001`：四类结构互斥且信息不足非负面；`EV-FR013` | SPEC |
| FR-014 | 检测禁用特征与代理变量 | Compliance Validator | G1A-034 | `RT-PROXY-001`：直接字段与代理变量均阻断；`EV-FR014` | SPEC |
| FR-015 | Agent 结构无决定字段 | Model Port + Schema | G1A-031,032 | `CT-EVAL-002`：决定字段/schema/publish 三层拒绝；`EV-FR015` | SPEC |
| FR-016 | 安全失败不可静默删后发布 | Validator + ExceptionBundle | G1A-015,033,034 | `BT-VALIDATE-001`：失败保留原因并开包；`EV-FR016` | SPEC |
| FR-017 | 每会话唯一确认责任人 | Review Policy | G1A-040,043 | `BT-OWNER-001`：多人评论不产生多生效版；`EV-FR017` | SPEC |
| FR-018 | 修改生成新版本/diff/作者/原因 | Evaluation / `ReviseEvaluation` | G1A-042 | `BT-REVISION-001`：历史不可覆盖；`EV-FR018` | SPEC |
| FR-019 | 评价确认与轮次决定独立 | Round / review + decision commands | G1A-043,044 | `test_completed_session_reaches_immutable_round_archive_only_after_human_decision` + HUMAN/SERVICE 权限负例；`EV-FR019` / E-032 | IMPLEMENTED |
| FR-020 | 并发确认使用版本校验 | Control + Evaluation | G1A-012,042 | `CT-VERSION-001`：后提交返回冲突；`EV-FR020` | SPEC |
| FR-021 | 未确认不得完成，豁免可审计 | Round completion gate | G1A-043,045 | `BT-ARCHIVE-001`：缺确认拒绝；豁免需 actor/reason/time；`EV-FR021` | SPEC |
| FR-022 | 归档钉住确认版/决定版/证据版 | Round / `RecordRoundDecision` | G1A-045 | 正常链 + archive hash 版本变化 + 确认后迟到证据拒绝测试；`EV-FR022` / E-032 | IMPLEMENTED |
| FR-023 | 策略化提醒、静默、上限、升级、幂等 | ActionExecutor / `RequestReminder` | G1A-016,050 | `CT-REMINDER-001`：同 ordinal 仅一外发；`EV-FR023` | SPEC |
| FR-024 | 异常包含事实/风险/尝试/选项/建议/Owner/期限 | ExceptionBundle | G1A-015 | `CT-EXCEPTION-001`：Schema + HR 可恢复演练；`EV-FR024` | SPEC |
| FR-025 | 每任务定义重试/不可重试/人工恢复 | Worker + ActionExecutor | G1A-015,016,024,031 | `BT-RECOVERY-001`：授权缺失不按模型失败重试；`EV-FR025` | SPEC |
| FR-026 | 案件/岗位/租户三级暂停熔断 | Control / `PauseScope` | G1A-014,016 | `CT-PAUSE-001..003`：未执行动作失效；`EV-FR026` | SPEC |
| FR-027 | 接管范围与恢复点可审计，不重复外发 | Control / resolve + resume | G1A-015,051 | `BT-TAKEOVER-001`：从 checkpoint 恢复；`EV-FR027` | SPEC |
| FR-028 | 读/生成/改/确认/发/导出/删全审计 | Audit + Projection | G1A-004,053 | `ST-AUDIT-001`：案件/人员时间线完整性；`EV-FR028` | SPEC |
| FR-029 | 保存模型/Prompt/评分卡/策略/模板版本 | VersionPin + Event Envelope | G1A-030,031,053 | `BT-REPRO-001`：任一报告可解释输入版本；`EV-FR029` | SPEC |
| FR-030 | 撤回/删除传播到全血缘并回执 | Privacy Orchestrator | G1A-022,052 | `ST-DELETE-001`：媒体→逐字稿→证据→副本；`EV-FR030` | SPEC |
| FR-031 | 删除中停止生成/提醒/分发 | Control + Executor preflight | G1A-014,052 | `CT-DELETE-001`：队列执行前重验；`EV-FR031` | SPEC |
| FR-032 | 默认不训练/不跨目的分析 | Data Controls + Provider Port | G1A-004,023,031 | `ST-PURPOSE-001`：供应商配置/日志/审计证明；`EV-FR032` | SPEC |

## 3. AT-001..015

| ID | 场景 / 关键断言 | 覆盖故事 | 自动化层 | 目标证据槽 | 当前 |
|---|---|---|---|---|---|
| AT-001 | 合格会话只创建一个处理任务并产可溯源草稿 | G1A-020..035 | API component + fake providers | `EV-AT001` | SPEC |
| AT-002 | 相同回调 10 次仅一个媒体/草稿 | G1A-011,021 | concurrency/component | `EV-AT002` | SPEC |
| AT-003 | 授权缺失：不转写/不评价，开 CONSENT_MISSING | G1A-022 | security/component | `EV-AT003` | SPEC |
| AT-004 | 转写前撤回：停止且无新派生数据 | G1A-014,022,052 | race/component | `EV-AT004` | SPEC |
| AT-005 | 关键说话人低置信：不发布，转人工映射 | G1A-025,033 | quality/component | `EV-AT005` | SPEC |
| AT-006 | 无证据负面结论被阻断并记录失败 | G1A-033 | validator/red-team | `EV-AT006` | SPEC |
| AT-007 | 婚育/健康无关信息不进评价并触发复核 | G1A-034 | compliance/red-team | `EV-AT007` | SPEC |
| AT-008 | 两人编辑同版，后者冲突且不覆盖 | G1A-012,042 | concurrency/API | `EV-AT008` | SPEC |
| AT-009 | 确认评价不自动推进，仍待人类决定 | G1A-043,044 | state-machine/API | `test_completed_session_reaches_immutable_round_archive_only_after_human_decision` + 决定权限负例；`EV-AT009` / E-032 | IMPLEMENTED |
| AT-010 | 当前轮归档，但不生成终面包/全案就绪事件 | G1A-045 | event assertion/API | `EV-AT010` | SPEC |
| AT-011 | 暂停后队列提醒在执行点被阻断 | G1A-014,016,050 | race/connector mock | `EV-AT011` | SPEC |
| AT-012 | 模型超时重试耗尽：异常/接管，不重复媒体 | G1A-015,021,031,051 | fault injection | `EV-AT012` | SPEC |
| AT-013 | 删除传播、停止生成并形成回执 | G1A-052 | lineage/integration | `EV-AT013` | SPEC |
| AT-014 | 新评分卡发布后旧案仍用钉住版本 | G1A-030 | version/component | `EV-AT014` | SPEC |
| AT-015 | 逐字稿恶意提示仅作内容，零工具/指令改变 | G1A-031,032 | prompt-injection red-team | `EV-AT015` | SPEC |

## 4. 横向安全与竞态套件

PRD 的单个 FR/AT 之外，以下必须作为发布门复用到所有命令：

| 套件 | 断言 | 证据槽 |
|---|---|---|
| `CT-COMMAND-GATE` | 权限 → 幂等 → version → epoch → 控制态 → policy → 引用 → consent → human-decision gate 顺序稳定 | `EV-X-001` |
| `CT-IDEMPOTENCY-RACE` | 两个节点同键并发，只有一个事务提交；同键异载报警 | `EV-X-002` |
| `CT-OUTBOX-ATOMICITY` | 进程在事务任一点崩溃，不出现有状态无事件或有动作无状态 | `EV-X-003` |
| `CT-LATE-SUCCESS` | 外部成功但响应丢失先对账；关闭/撤回后的迟到成功只补偿 | `EV-X-004` |
| `CT-LIFECYCLE` | CLOSED 重开增加 epoch；旧命令、旧卡片、旧 action 永久失效 | `EV-X-005` |
| `ST-MINIMIZATION` | 事件/日志/指标无简历全文、联系方式、录音或完整逐字稿 | `EV-X-006` |
| `RT-HUMAN-DECISION` | Prompt、模型输出、内部服务和 UI 篡改均不能生成有效 RoundDecision | `EV-X-007` |

## 5. 覆盖快照

| 项 | 基线 | 已映射 | 已实现 | 已验证 | 已发布 |
|---|---:|---:|---:|---:|---:|
| FR | 32 | 32 | 2 | 0 | 0 |
| AT | 15 | 15 | 1 | 0 | 0 |

当前成果是把“32 项功能 + 15 个验收”变成可领取、可测试、可挂证据的工作图，并用合成运行证据完整实现 FR 2 项、AT 1 项。剩余 FR 30 项、AT 14 项仍为 `SPEC`；全部 `VERIFIED/RELEASED` 仍为 0。**40 个测试通过不等于 40 项需求已实现。**
