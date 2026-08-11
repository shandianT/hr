# 招聘 Agent G3 产品规格验收记录

> 验收时间：2026-08-11（Asia/Singapore）
> 验收对象：G3 领域语言、ADR、PRD、领域/事件、需求追踪、Hermes 式 Agent/UI 基线、组合看板与 Gate 证据边界
> 发布结论：**No-go 保持不变；当前只允许合成/匿名化规格与沙箱准备。**

权威输入 SHA-256：7584224b7fc34e1571ebdab2d4380f651550357eabd1b5c3b2a2d10fd0b06390

## 1. 权威输入

- [G3 PRD](./招聘Agent_G3_结果回流与画像治理_PRD.md)
- [G3 需求追踪矩阵](./招聘Agent_G3_需求追踪矩阵.md)
- [领域语言](./CONTEXT.md)
- [领域与事件规格](./招聘Agent_领域与事件规格.md)
- [ADR-0009](./docs/adr/0009-outcomes-do-not-auto-train-role-profiles.md)
- [Hermes 式 Agent 与 UI 设计原则](./docs/招聘Agent_Hermes式Agent与UI设计原则.md)
- [产品落地总方案](./招聘Agent产品落地总方案.md)
- [推进看板](./招聘Agent推进看板.md)
- [Gate 0 执行包](./招聘Agent_Gate0执行包.md)
- [仓库说明](./README.md)
- [G3 规格 lint](./contracts/lint_g3_spec.py)

组合 SHA-256 按相对路径排序，将“相对路径 + NUL + 文件内容 + NUL”依次输入 SHA-256；本验收记录不参与哈希，避免自引用。

## 2. 验收方法

1. 检查 FR-301..360、AT-301..330 在 PRD/矩阵连续、唯一，60 条 FR 均有 AT 覆盖。
2. 检查矩阵六列、SPEC 状态、目标测试和证据槽；IMPLEMENTED/VERIFIED/RELEASED 必须为 0。
3. 检查十个 G3 领域词、ADR-0009、十一项必需聚合行、单聚合命令、事件与最终决定/发布/失效 seam。
4. 检查结果阶段、成熟/删失、完整 denominator、选择偏差、泄漏、用途、保护属性、公平与因果边界。
5. 检查 Proposal、双人 Approval、独立 HUMAN Publication Authorization、CONTROL_PLANE Prepare/Commit、ProfileVersion 与 Publication Receipt 分离，以及 future-only、无 A3、Freeze 优先与回到 A0。
6. 检查 Hermes-style harness 与 UI 的 typed tool、checkpoint、trace/replay、回执/补偿、Quiet by default、One primary action 和渐进披露。
7. 检查本地链接、README/总方案/看板/Gate No-go 与 E-018 证据边界。

## 3. 结果

| 检查 | 预期 | 结果 | 证据 |
|---|---|---|---|
| FR 连续与双向覆盖 | 60/60 | PASS（60） | contracts/lint_g3_spec.py |
| AT 连续与双向覆盖 | 30/30 | PASS（30） | contracts/lint_g3_spec.py |
| FR→AT 覆盖 | 60 条无孤儿 | PASS（60） | G3 需求追踪矩阵 |
| 领域词汇 | 10 个 G3 词 | PASS（10） | CONTEXT.md |
| ADR | 0001..0009 连续；0009 accepted | PASS（9） | docs/adr |
| G3 聚合/命令/事件 | 为权威表格行且事件不重复 | PASS（11 个必需聚合行、52 命令、53 事件） | 领域与事件规格 |
| ApplicationCase 与决定 seam | 六阶段；HUMAN 决定由 Case 拥有，G3 只引用 | PASS | 领域与事件规格 |
| 稳定不变量 | 44 个 ID 在 PRD/领域完全一致且唯一 | PASS（44） | PRD + 领域规格 |
| 证据状态 | SPEC=60/30/9，IMPLEMENTED/VERIFIED/RELEASED=0 | PASS | G3 需求追踪矩阵 |
| Agent / UI 边界 | 模型建议、双人批准、独立 HUMAN 发布授权、控制面 Prepare/Commit、回执/恢复及高级简洁体验分离 | PASS（产品规格） | Hermes 式 Agent/UI 原则 |
| 组合计划与 Gate | 总方案、看板、README、E-018、No-go 同步 | PASS | 组合文档 |
| 本地链接 | 仓库内相对链接可解析 | PASS（80） | lint 输出 |

## 已证明

- G3 已从“结果回流画像”方向收敛为来源断言/当前解析、标注成熟、完整分母 Cohort、仅用 train/dev 生成并冻结候选、预注册后首次打开确认性 holdout、当前 D0–D4 发布资格、双人批准、独立发布授权、关键同步后提交未来周期指针、监控/Freeze/人工回滚的可审链路。
- ApplicationCase 的最终 HUMAN 决定新增权威事件 seam；G3 只引用，不建立第二份招聘决定真相。
- 结果阶段、生命周期与成熟度被分离；未成熟、未知、删失和不适用不会被自动转成负例。
- 选择性标注、幸存者偏差、时间/身份泄漏、跨岗位可比性、跨租户、用途、保护/代理变量和普通相关的因果越界已进入 FR/AT 与稳定不变量。
- Profile Candidate Revision、Study、Release Eligibility、Proposal、双人批准、发布授权、ProfileVersion、PENDING_SYNC、关键同步回执、current pointer 与回滚保持分离；画像发布/回滚无 A3，新版本默认只作用未来周期。
- Hermes-style harness 与 UI 设计原则已成为跨阶段产品基线：模型不是状态机，Run 可观察/暂停/恢复/对账；双人批准后另有发布授权人 HUMAN 任务，批准、授权、控制面发布准备、发布记录创建、同步和当前生效互不冒充；普通用户只看当前任务、原因、下一步与恢复入口。
- E-018 只登记静态产品规格；E-019..E-030 保持空白，防止用文档冒充数据、实验、工程、真人或发布证据。

## 未证明

- **真实结果数据合法**：未有结果/任职后数据地图、PIPIA、来源权限、Purpose、字段/保留/删除和供应商方案批准。
- **统计有效性**：未形成真实完整分母 Cohort、成熟/删失基线、固定 holdout、置信区间、稳定性或前瞻 exposure 证据。
- **公平**：未有合法隔离保护属性、代理变量红队、重要 slice 实质伤害边界或公平 Owner 会签。
- **工程实现**：没有 G3 聚合、数据库、队列、AgentRun、连接器、血缘失效、ProfileVersion 发布或行为测试代码。
- **Hermes runtime**：只借鉴公开设计原则；没有决定、集成、部署或验证 Hermes Agent 作为生产运行时。
- **真人采用**：没有用人负责人（Hiring Owner）、HRBP / 画像治理负责人（Profile Governance）、发布授权人（Publication Authorizer）、结果数据管理员（Data Steward）、隐私 / 公平负责人（Privacy/Fairness）、AI / 数据分析师（Analyst）和招聘运营七类 HUMAN 的任务成功、关键误解、无障碍或采用证据。
- **A0/A1/A2**：没有真实观察影子、Proposal 建议、双人批准、独立 HUMAN 发布授权、CONTROL_PLANE Prepare/Commit、未来周期受控发布或停止条件证据；A3 画像变更永久禁止。
- **画像发布**：没有任何 ProfileVersion 对真实新案件生效，也没有真实 Freeze/回滚/下游同步回执。
- **发布**：没有 Gate Go、生产 SLO、事件响应、长期监控或商业效果。

因此，本记录只允许声称“G3 产品规格静态一致”。不得声称数据可用、画像有效、公平、Agent harness 已实现、采用 Hermes runtime、真实用户已接受、A0/A1/A2 已通过、画像已发布或产品可以发布。
