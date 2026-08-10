# 招聘 Agent G3 PRD：结果回流与画像治理

版本：v0.1
日期：2026-08-10
状态：Gate 0 评审稿
产品边界：批准来源断言 → canonical 结果解析 → 标注成熟/资格裁决 → 分析队列与分区封存 → 仅用 discovery/train/dev 生成并冻结画像候选 → 预注册 confirmatory Study → 首次打开 untouched holdout 并评测 → D0–D4 Release Eligibility → 双人人审 → 单独发布授权 → CONTROL_PLANE 两阶段未来周期发布 → 暴露监控、冻结与人工回滚
发布结论：真实任职后数据、A0/A1/A2 运行、画像发布、跨岗位扩展与工程发布仍为 No-go

相关材料：

- [产品落地总方案](./招聘Agent产品落地总方案.md)
- [领域语言](./CONTEXT.md)
- [领域与事件规格](./招聘Agent_领域与事件规格.md)
- [ADR-0009：结果观察不是真值](./docs/adr/0009-outcomes-do-not-auto-train-role-profiles.md)
- [Hermes 式 Agent 与 UI 设计原则](./docs/招聘Agent_Hermes式Agent与UI设计原则.md)
- [Gate 0 执行包](./招聘Agent_Gate0执行包.md)

## 1. 要解决的问题

G1/G2 已定义从简历进入到终面评估就绪的可信中段，但“招聘结果回流画像”如果简单实现为“统计历史通过者关键词并自动调权”，会把旧流程中的选择偏差、面试官偏好、岗位差异和数据缺失自我强化：只有被旧画像选中的人更可能被录用，只有被录用的人更可能产生任职后结果，再用这些结果证明旧画像正确。

G3 要解决的不是如何更快自动学习，而是如何在不把历史决定冒充真值的前提下，安全地产生可审、可拒绝、可回滚的画像改进建议：

1. Offer、接受 Offer、入职、留任和绩效发生在不同阶段，不能压成一个“招聘成功”。
2. 未成熟、失访、缺失和右删失不是失败；历史 reject/offer/hire 是流程或选择事实，不是候选人能力真值。
3. 任职后表现通常只对 hired 可见，不能直接推断被拒绝者，也不能只用幸存者样本评价完整筛选策略。
4. 名称、学校、口音、邮编、空窗等可能成为代理变量；禁止字段本身不足以保证公平。
5. 评测报告、画像提案、批准和发布是不同事实；模型或工具成功不能直接改变当前画像。
6. 同一结果可能有多个来源断言，但只能由有权限的规则与 Steward 确认一个当前 canonical revision；不能自动投票、取最新或取高置信来源。
7. 结果更正、删除、用途变化或安全事件必须能级联失效候选、运行、研究、发布资格、提案、批准和待发布修订；已生效画像进入 Freeze。

本期要证明：

> 批准来源事件可以自动启动结果归一化、成熟等待、固定队列评测和画像提案准备；正常链不要求 HR 点击“开始”。Agent 负责收集、校验、评测、解释和监控，人只处理结果冲突、画像审阅、发布和回滚等不可替代判断。任何历史结果都不能直接调权、排名、淘汰或改变在途案件。

## 2. 成功定义

G3 成功必须同时满足：

- 每项结果观察保存各来源不可变 SourceAssertion，并绑定租户、案件/主体、岗位、招聘周期、当时使用的画像/流程、结果阶段、来源权限、有效/观察/接收时间；一个 reconciliation key 只有一个经授权确认的当前 canonical revision。
- 当前 ApplicationCase 最终招聘决定只通过 `FinalHiringDecisionRecorded` 被引用，G3 不复制、修改或重新解释其所有权。
- Labeling Policy 明确成熟窗口、资格、缺失/删失、禁止信号和用途；PENDING、UNKNOWN、RIGHT_CENSORED、NOT_ELIGIBLE 不转成负例。
- Analysis Cohort Snapshot 保存完整 denominator、纳排理由、as_of、成熟/缺失/删失、选择机制、岗位/时间/人分区、discovery/train/dev/confirmatory-holdout 分区和血缘。
- SEALED Cohort 后只用 discovery/train/dev 生成并冻结 Profile Candidate Revision；candidate hash 冻结后才可预注册 confirmatory Study，首次运行才打开 untouched holdout。同一 holdout 不得用于生成/调参后再充当确认性评测。
- 报告披露分子、分母、n、置信区间、重要 slice、反证和限制；无当前获批 CausalDesignManifest 时只允许关联表述。
- D0–D4 当前 Gate Assessment 全部 PASS、未过期且无 veto 才形成 ProfileReleaseEligibilitySnapshot；任何人类批准都不能覆盖 FAIL、INCONCLUSIVE、EXPIRED 或 VETO。
- Proposal 不等于 ProfileVersion。Hiring Owner 与 HRBP / Profile Governance Owner 两个不同 HUMAN 对同一 candidate/study/release-eligibility/scope hash 批准后，仍须另有当前 HUMAN 发布授权。
- CONTROL_PLANE 先创建 PENDING_SYNC 发布修订且不改 current pointer；只有关键下游同步回执完整且所有门仍当前，才原子提交 ProfileVersion/PublicationRevision 并更新 future-scope pointer。
- 新画像不静默迁移在途案件；P0 时 Freeze 提升 safety_epoch 并优先于 Prepare/Commit。FROZEN 只能经 HUMAN 授权的人工回滚恢复 ACTIVE，且放权回到 A0。
- 每次 Agent Run 都可回答正在做什么、为何触发、读取哪个版本、工具返回什么、等待谁、如何恢复；不暴露思维链或不必要个人信息。
- 候选人的录制选择、无录制路线、辅助需求、拒绝自动化、申诉和权利请求对结果标注、画像和业务评价影响为零。

北极星子指标：**可信画像改进闭环率**。
定义：在声明范围内，从当前有效 canonical 结果观察开始，经标签成熟、SEALED Cohort、候选冻结、确认性评测、Release Eligibility 和必要人审，到“研究有依据地 INCONCLUSIVE/提案被拒绝或失效”或“经双批准、独立授权和两阶段 Commit 后未来周期版本受控生效，并完成暴露监控/回滚准备”的治理闭环数 ÷ 所有进入 G3 范围且已到成熟窗口的结果观察批次；要求无跨租户/用途/公平/删除事件、无自动画像变更、无计划外 HR 搬运和全链血缘完整。

该指标不优化“批准率”“画像版本数”或“招聘通过率”。安全红线事件必须为 0；业务提升阈值和重要 slice 实质伤害界值必须在基线后预注册，不能在本规格中拍数字。

## 3. 范围

### 3.1 本期包含

- 一个租户、1–2 个试点岗位/岗位族、一个明确招聘周期与一个批准结果来源生态。
- Final Hiring Decision、Offer、Offer Acceptance 等招聘/雇佣前阶段的独立结果观察与纠正。
- 任职后表现信号只作为额外批准子范围：独立目的、数据地图、字段白名单、窗口、访问、保留和公平审计。
- Outcome SourceAssertion、canonical Observation/Label 生命周期、成熟/缺失/删失表达、来源冲突人审。
- 完整分母、选择机制、人员/时间分区、岗位隔离和不可变 Analysis Cohort Snapshot。
- SEALED Cohort 后仅用 discovery/train/dev 生成并冻结 Profile Candidate Revision，再预注册 Feedback Study、首次打开 untouched confirmatory holdout、执行可重放离线运行并输出质量/公平/关联边界报告。
- Profile Change Proposal、当前 D0–D4 Release Eligibility、修改/拒绝/失效、单一权威审阅任务和两个不同 HUMAN 批准。
- 独立 HUMAN Publication Authorization、CONTROL_PLANE Prepare/关键同步/Commit、仅未来周期指针、ProfileExposureLedger、Freeze、人工回滚和 A0 恢复。
- Hermes-style deterministic harness：typed tool、有限计划/预算、checkpoint、幂等、dry-run、replay、回执、补偿和异常包。
- 画像治理工作台、Version Diff、风险带、渐进披露审计和七角色真人/无障碍验收计划。

### 3.2 本期不包含

- 从 `CLOSED`、沉默、超时、退出、拒绝或录用直接推断候选人能力/未来表现。
- 每周自动重算关键词、画像权重、门槛、排名、淘汰或招聘决定。
- 跨租户共享原始观察、标注、候选人级样本、梯度或画像候选修订。
- 未证明可比的跨岗位合池、全公司通用“人才质量分”或人格/潜力推断。
- 将受保护属性或其推断放入业务画像、匹配、Prompt、Agent Memory、事件总线或业务 UI。
- 将拒绝录制、无录制、撤回、辅助需求、权利请求、申诉、回复速度或 HR override 用作 feature/label/weight/纳排条件。
- 自动授权发布、自动解冻或自动回滚 ProfileVersion；发布授权/回滚授权永不开放 A3，CONTROL_PLANE 只能执行已授权且所有门当前的确定性命令。
- 使用 confirmatory holdout 生成、挑选或调整 candidate，再用同一 holdout 声称独立验证。
- 因已有 ATS/HRIS API 就默认处理任职后数据；真实数据与任职后用途在 E-019 前均 No-go。

### 3.3 合格入口与合法出口

合格入口同时满足：来源与访问权限批准，结果阶段 Taxonomy 明确，岗位/周期/主体或案件唯一，当前用途/控制/保留允许，来源修订可对账。不能唯一绑定、冲突、未成熟或失权的观察停在对应状态或形成一个 Exception Bundle，不强行标注。

合法出口只有三类：

1. 数据不足、Gate FAIL/INCONCLUSIVE/EXPIRED/VETO、风险过高或假设不成立，Study 有依据地结束为描述性 INCONCLUSIVE 且不打开发布型审阅任务，或 Proposal 被 REJECTED/INVALIDATED；单纯停在 EVALUATION_PENDING 不是已闭环。
2. 当前 RELEASE_ELIGIBLE Proposal 经两个不同 HUMAN 批准和单独 HUMAN Publication Authorization 后，由 CONTROL_PLANE Prepare；关键同步回执齐全且重验通过后 Commit，为未来周期原子更新 current pointer。
3. 风险、纠正或删除导致 safety_epoch 提升和 Freeze；PENDING_SYNC 修订被取消，ACTIVE 版本停止新 pin。随后只能由 HUMAN 授权回滚到此前批准且仍允许的版本，使 FROZEN→ACTIVE 并回到 A0；历史不被改写。

## 4. 用户与权限

| 角色 | 可以做 | 不能做 |
|---|---|---|
| Hiring Owner | 审阅岗位含义、证据与 Diff；对当前 RELEASE_ELIGIBLE 提案批准、要求修改或拒绝 | 单方绕过 HRBP、Release Gate 或发布授权；迁移在途案件 |
| HRBP / Profile Governance Owner | 与 Hiring Owner 作为另一 HUMAN 批准；确认未来适用周期和回滚目标 | 把历史录用结果定义成能力真值；无研究直接改画像；把共同批准冒充发布授权 |
| Publication Authorizer | 在双批准完成后，以单独 HUMAN 命令授权精确 proposal/eligibility/scope/effective_at/rollback target | 预授权、授权旧版本、替 CONTROL_PLANE 提交 pointer；由 Agent/Service 代签 |
| Outcome Data Steward | 管来源映射、阶段口径、canonical revision、成熟规则、纠正和冲突裁决 | 发布画像、修改招聘决定、解释候选人优劣、参与画像批准 quorum |
| AI / Data Analyst | 审查 Cohort 分区，冻结 candidate 生成清单，预注册评测、检查泄漏、执行固定协议、解释不确定性 | 看过 holdout 后调参仍称独立评测；批准、授权发布、回滚 |
| Privacy / Fairness Owner | 独立记录 D0–D4 中相应 Gate Assessment，管用途、字段隔离、重要 slice、公平门和 veto | 修改招聘决定或业务画像内容；被 Hiring Owner/HRBP 覆盖 FAIL/VETO |
| 招聘运营 | 处理来源/Owner/关键同步异常，监督 SLA、回执和异常包 | 手工改标签、搬状态、批准/授权发布、绕过 current pointer |
| Agent 智能引擎 | 归一化/标注草稿，仅用 discovery/train/dev 形成候选，执行已预注册评测并整理说明 | 确认 canonical 真值、改分母/指标、反复打开 holdout、作招聘决定、批准/授权发布/回滚 |
| CONTROL_PLANE | 在 HUMAN 授权、ProfileReleaseEligibilitySnapshot、safety_epoch 和关键回执均当前时执行 Prepare/Commit/Rollback | 伪造批准或授权；回执未齐更新 pointer；把模型/工具输出直接变成当前画像 |
| 候选人 / 数据主体 | 行使查阅、更正、限制、删除及其他适用权利 | 其选择和权利行为不得被学习链解释为负面信号 |

所有权限同时受租户、岗位、招聘周期、主体/案件、结果阶段、字段、目的、处理操作、保留期、发布范围和时间约束。两个批准记录来自不同 HUMAN；Publication Authorization 与 Approval 是独立事实。Prepare/Commit/Rollback 由 CONTROL_PLANE 执行，但必须引用当前 HUMAN 授权。批准规则可自动触发安全 Freeze，不能自动解冻。

## 5. 产品与 Agent 结构

~~~mermaid
flowchart LR
    S["权威结果来源"] --> O["结果观察与纠正"]
    O --> L["标签资格与成熟"]
    L --> C["完整分母队列快照"]
    C --> D["train/dev 生成并冻结候选"]
    D --> R["预注册 confirmatory Study"]
    R --> H["首次打开 untouched holdout · 可重放评测"]
    H --> E["ANALYSIS_READY 报告"]
    E --> P["Proposal EVALUATION_PENDING · D0–D4"]
    P --> G["RELEASE_ELIGIBLE → REVIEW_READY"]
    G --> A["两个不同 HUMAN 批准"]
    A --> U["单独 HUMAN 发布授权"]
    U --> Q["CONTROL_PLANE Prepare · 关键同步"]
    Q --> V["Commit · 原子更新 future pointer"]
    V --> M["Exposure Ledger · Freeze · 人工回滚"]
    X["用途 · 权利 · 公平 · 租户控制"] -.每步重验.-> O
    X -.每步重验.-> H
    X -.每步重验.-> V
~~~

| 产品模块 | 核心产物 | 默认体验 |
|---|---|---|
| 结果对账箱 | 当前 Outcome Observation、冲突、成熟时间、纠正血缘 | 正常自动归一化；只把冲突/失权变成人审任务 |
| 队列健康台 | denominator、纳排、成熟/缺失/删失、选择机制、分区 | 先显示是否可研究，不先显示“提升多少” |
| 评测运行台 | CandidateGenerationManifest、Study Plan、holdout access receipt、Agent Activity Rail、checkpoint、报告与限制 | 安静运行；明确候选先冻结、holdout 首次打开和不可重复调参 |
| 画像审阅台 | `vN → candidate` Diff、Release Eligibility、支持/反证/未知、风险、适用范围 | 一页一个当前决定；修改、拒绝、批准及失效后果清楚，细节渐进披露 |
| 发布与回滚台 | 双批准、独立发布授权、PENDING_SYNC、关键回执、current pointer、safety_epoch、上一安全版本 | 批准、授权、Prepare、同步、Commit、Freeze 和 Rollback 保持分离 |
| 审计与权利台 | purpose/control lineage、读取/动作、删除/纠正回执 | 最小引用与哈希，不复制简历/逐字稿/保护属性 |

## 6. 端到端主流程

| 步骤 | Agent / 控制面动作 | 人类动作 | 权威产物 |
|---:|---|---|---|
| 1 | 接收批准来源的不可变 SourceAssertion，按 key/revision 幂等归一化 | 仅处理无法唯一绑定或来源冲突 | Outcome Observation PROVISIONAL/DISPUTED + SourceAssertions |
| 2 | 汇集多源断言，引用 ApplicationCase 当前 HUMAN 决定并重验用途/控制 | Steward 按当前 resolution policy 确认、纠正或保持争议 | 唯一 current canonical Outcome Revision |
| 3 | 按当前 Labeling Policy 计算资格与 maturity | 仅处理规则未覆盖的争议 | Outcome Label DRAFT/VERIFIED/EXCLUDED |
| 4 | 到成熟窗口自动唤醒；PENDING/UNKNOWN/CENSORED 不作负例 | 无 | 当前 Label maturity |
| 5 | 以完整 denominator 建立纳排、选择机制、person/time/job 和 discovery/train/dev/confirmatory-holdout 分区 | Analyst 审查范围与分区，不接触 holdout 内容 | Cohort DRAFT |
| 6 | 质量、泄漏、用途和分区门通过后封存；holdout 保持未打开 | 无 | SEALED AnalysisCohortSnapshot |
| 7 | 只读 discovery/train/dev 形成相对 base ProfileVersion 的 Diff，保存 CandidateGenerationManifest 并冻结 hash | Analyst 只审生成清单与禁用信号 | FROZEN ProfileCandidateRevision |
| 8 | 以已冻结 candidate、SEALED Cohort 预注册假设、指标、slice、样本/精度、停止规则和 claim type | Analyst 提交确认性研究；CAUSAL 另需批准设计 | FeedbackStudy PREREGISTERED |
| 9 | 校验 holdout 从未用于候选生成/调参，首次打开并记录 access receipt；按固定协议启动 Agent Run | 无；异常才接管 | RUNNING Study + AgentRun/checkpoints/receipts |
| 10 | 输出 label health、指标、CI、slice、反证、限制和因果边界 | Analyst/Privacy/Fairness 审查表述与风险 | FeedbackStudy ANALYSIS_READY |
| 11 | 创建 Proposal、绑定不可变 candidate/report/base/scope，冻结 gate evaluation input hash | 无 | Proposal EVALUATION_PENDING |
| 12 | 独立 Owner 对 D0–D4 记录有 current/expiry 的 Gate Assessment；全 PASS 后生成 Eligibility，再重验并形成唯一审阅 artifact/task | FAIL/VETO 只能修复后重评，不能被业务批准覆盖 | RELEASE_ELIGIBLE→REVIEW_READY，或 INVALIDATED |
| 13 | 维护唯一产品内任务；修改使 eligibility/批准失效并回到新 candidate/new Study，拒绝关闭当前提案 | Hiring Owner 与 HRBP 两个不同 HUMAN 分别决定 | Approval records / APPROVED、REJECTED 或 EVALUATION_PENDING |
| 14 | 双批准后再请求精确 publication authorization | 有 Publication Authority 的当前 HUMAN 单独授权 scope/effective_at/rollback target | Proposal PUBLICATION_AUTHORIZED |
| 15 | CONTROL_PLANE 重验 eligibility/base/safety_epoch，Prepare PENDING_SYNC；收齐关键同步回执后 Commit 并原子更新 pointer | 普通同步异常由招聘运营处理，不能手工搬 pointer | PublicationRevision PENDING_SYNC→ACTIVE + receipts |
| 16 | 按稳定 assignment 记录实际未来 exposure；异常按预注册规则提升 safety_epoch 并 Freeze | 有权限 HUMAN 决定是否回滚；CONTROL_PLANE 只执行授权 | ExposureLedger / FROZEN，或 Rollback 后 ACTIVE+A0 |

## 7. 体验与 UI

G3 只增加一个按角色授权可见的“画像治理”入口，首屏默认只有三类卡片：**待你决定**、**Agent 正在处理**、**发布与风险**。不展示神经网络动画、机器人头像、无休止“思考中”或大面积 AI 仪表盘。

### 7.1 单屏画像审阅

1. 顶部：`当前 v4 → 候选 v5`、Proposal 状态、Release Eligibility、当前责任人、截止和唯一主要动作。
2. 主区：逐维 Diff、业务理由、支持证据、反证与未知。
3. 风险带：分母/成熟率、置信区间、重要 slice、用途/删除/代理红队状态。
4. 右侧：未来适用周期、在途案件不迁移、两个批准槽、独立发布授权、上一安全版本和回滚预览。
5. 折叠层：分析样本与覆盖范围、预注册协议、血缘、Agent trace、工具回执与审计字段；`Cohort` 等内部对象名只在授权审计抽屉出现。

提案人审动作只有“批准提案 / 要求修改 / 拒绝”，不预选，也不把“批准”做成诱导性默认。首位批准人明确看到“仍需另一位 HUMAN 批准，尚不会发布”；双批准完成仍只显示“已批准，待发布授权”。要求修改会撤回当前 eligibility、任务、批准和授权，并要求新 candidate/new Study；拒绝关闭当前提案。发布授权是后续独立任务，清楚展示 future scope、effective_at、关键同步集和 rollback target。普通业务用户不看事件名、哈希或内部枚举，这些只在审计抽屉出现。

### 7.2 Agent Activity Rail

Activity Rail 只投影 AgentRun：当前在做什么、为什么触发、读取的版本化输入、已完成/等待步骤、holdout 是否尚未打开、下一次唤醒或截止、暂停/恢复入口、失败后的自动恢复或 Owner。Proposal 和 Publication 使用独立状态条，禁止把“分析完成”显示成“已批准/已发布”。不得显示模型思维链、Prompt、密钥、完整个人材料或保护属性。

| 状态族 | 普通用户文案 | 不得冒充 |
|---|---|---|
| AgentRun | 尚未开始仅是调度投影；领域 Run 创建即分析中，随后可等待工具、等待人工、暂停、完成、失败/取消或输入失效 | Proposal 获批或画像生效 |
| Proposal | 评测中、待 Release Gate、可审阅、待另一位批准、双人已批准、待发布授权、要求修改、已拒绝、已失效 | ProfileVersion 或 current pointer |
| Publication | 待同步、同步不完整、已生效、已暂停新案件使用、已回滚并仅做后台验证 | AgentRun 成功或仅收到外部请求；`A0` 只在授权审计抽屉出现 |

### 7.3 高级而克制的视觉

视觉沿用 [Hermes 式 Agent 与 UI 设计原则](./docs/招聘Agent_Hermes式Agent与UI设计原则.md)：温暖浅灰画布、白色表面、石墨文字、克制钴蓝进行态、深青绿核验态、琥珀风险和深红阻断；状态同时用文字/图标表达。动效只解释状态变化，支持 reduced motion；键盘、读屏、焦点、200% 缩放、非颜色状态、长文本、时区与语言进入发布门。

## 8. 数据、评测与因果边界

- `ProfileVersion → 面试/录用选择 → 是否能观察任职后表现`；只看 hired 会在选择节点上产生偏差。
- Offer 接受还受薪资、市场、地点影响；表现还受经理、团队、资源与 onboarding 影响，均不是画像准确度的纯标签。
- 数据必须按 Person 与时间切分；同人多岗位/周期不能跨 train/test/holdout，prediction_at 后字段不能进入 feature。
- SEALED Cohort 先固定分区；Profile Candidate Revision 只能从 discovery/train/dev 生成并冻结。冻结 candidate hash 后才能预注册假设、主指标、重要 slice、最小样本/精度、实质伤害边界、多重比较和停止规则，随后才可首次打开 untouched confirmatory holdout。
- 同一 holdout 一旦用于选择、解释、调整或生成 candidate，就不能再证明该 candidate；必须冻结新 candidate，并使用未触碰的新 holdout 与新 Study。
- 普通离线比较只能写“关联”；因果主张需当前获批 CausalDesignManifest，包含预注册随机或充分准实验、稳定分配、overlap、干扰审查和停止规则。
- 不允许按“是否采用 Proposal”自选分组后称 A/B；A2 必须用 ProfileExposureLedger 分开保存 assignment、actual exposure、noncompliance、contamination 和完整 denominator。
- 保护属性仅在合法、隔离、公平审计域用于发现伤害；不能回流业务画像、模型特征、Agent Context 或事件总线。

## 9. 功能需求

### 9.1 结果观察 FR-301..309

| ID | 需求 | 验收要点 |
|---|---|---|
| FR-301 | 只接入批准结果来源，将每个来源载荷保存为不可变 SourceAssertion，记录 source/event/revision、authority、taxonomy 和 purpose | 非批准来源隔离；来源事件可对账、可去重；SourceAssertion 不直接成为 canonical 事实 |
| FR-302 | 轮次结果、最终决定、Offer、接受 Offer、入职、留任和表现分别记录 | 不存在通用 `case_success`；阶段 Taxonomy 版本可审计 |
| FR-303 | 招聘决定类观察只引用 ApplicationCase 的当前 HUMAN 决定事件 | 保存 actor/authority/package/basis 版本；G3 不复制决定所有权 |
| FR-304 | 不得从 CLOSED、沉默、超时、退出、缺失或无结果推断业务结果 | 关闭原因和结果阶段分离；未知保持未知 |
| FR-305 | 同 reconciliation key/revision/载荷幂等；纠正和撤销只追加不可变修订并维护唯一 current canonical pointer | 同键异载进入冲突；历史不可覆盖；旧修订不可因迟到回调复活 |
| FR-306 | 每项观察绑定 tenant、subject/case、requisition、cycle、受控 employee/assignment linkage 及实际暴露的 profile/model/process 版本 | linkage 有权限/目的/修订；身份歧义不自动合并；保存 exposure history |
| FR-307 | 多来源断言按当前 resolution policy 对账；不能唯一解析或发生冲突时进入有权限的 Steward 裁决 | 只有授权确认可产生 current canonical revision；不按多数、置信分或最新到达自动选真相 |
| FR-308 | 显式表达 PROVISIONAL/CONFIRMED/CORRECTED/INVALIDATED 与 PENDING/UNKNOWN/RIGHT_CENSORED/NOT_ELIGIBLE | 生命周期和成熟度正交；前端不乐观显示成功/失败 |
| FR-309 | canonical 观察纠正、删除、来源失权、最终决定 supersede 或用途变化按血缘完整失效 | Label/Cohort/Candidate/Run/Study/ReleaseEligibility/Proposal/ReviewTask/Approval/PublicationAuthorization/Dashboard 均召回；PENDING_SYNC 取消，已 ACTIVE 发布触发 Freeze |

### 9.2 结果标注与分析队列 FR-310..320

| ID | 需求 | 验收要点 |
|---|---|---|
| FR-310 | Outcome Label 只能按版本化 LabelingPolicyPin 派生 | 目的、定义、成熟/删失、排除和版本齐全；不是真值 |
| FR-311 | 历史 reject/offer/hire 是流程或选择事实，不是能力/任职成功标签 | 规则与 UI 均禁止“录用=好、拒绝=差”的映射 |
| FR-312 | Post-hire Performance Signal 只进入额外批准的目的、字段、岗位和测量窗口 | 无数据地图/PIPIA/权限时只允许合成数据 |
| FR-313 | 学习字段白名单显式化，禁用受保护属性及代理推断 | 新字段默认不可用；字段变更使 Snapshot/Study 重验 |
| FR-314 | 录制/无录制/撤回、辅助需求、拒绝自动化、申诉、权利请求和 HR 行为不得作为 feature/label/weight/纳排 | 隔离测试证明对业务输出影响为零 |
| FR-315 | 未成熟、缺失、迟到、失访和删失保持 PENDING/UNKNOWN/RIGHT_CENSORED | 不进入负例；到期按当前策略自动重验 |
| FR-316 | Cohort 披露完整 denominator、选择机制和缺失机制 | 只有 hired+有绩效者时明确选择性标注，不外推全漏斗 |
| FR-317 | AnalysisCohortSnapshot 钉住输入、as_of、标签策略、纳排、成熟/缺失/删失、discovery/train/dev/confirmatory-holdout 分区、访问状态与哈希 | SEALED 后不可改；holdout 内容保持未打开；变化只建新 revision |
| FR-318 | 按 Person 与时间切分，阻断决策后字段和同人跨岗 train/test 泄漏 | FeatureAvailability/Partition Manifest 可机械检查 |
| FR-319 | 默认按 tenant、岗位/岗位族、周期、地区/语言、流程与时间窗隔离 | 跨岗合池须可比性证据；跨租户候选人级学习禁止 |
| FR-320 | 受保护属性只在批准的隔离公平审计域使用 | 不进入画像候选、匹配、Prompt、Agent Context、事件或业务 UI |

### 9.3 离线评测与候选修订 FR-321..331

| ID | 需求 | 验收要点 |
|---|---|---|
| FR-321 | Offline Evaluation 只能在 SEALED Cohort、FROZEN candidate 和 PREREGISTERED Study 当前时启动；首次打开 confirmatory holdout 并记录 access receipt | AgentRun.kind=OFFLINE_EVALUATION 对固定输入可重放、幂等；代码/模型/Prompt/评估器、seed、环境和回执可定位 |
| FR-322 | candidate hash 冻结且 holdout 未打开后，才预注册假设、主指标、重要 slice、门槛、多重比较、停止规则和 claim type | 打开 holdout 后改变 candidate、口径或协议必须新建 Candidate/Study/holdout，不能继续称独立评测 |
| FR-323 | 关联与因果在 Schema、报告和 UI 中分离；CAUSAL 必须引用当前批准的 CausalDesignManifest | 无批准随机/充分准实验、稳定 assignment、overlap、干扰与 exposure 设计时禁止“导致、提升、改善”等因果主张 |
| FR-324 | 小样本、宽区间、高缺失、低标签可靠性、选择性标签或 small cell 只允许描述/抑制展示 | 输出 INCONCLUSIVE，适用的 D1/D2/D3 不 PASS，不形成 RELEASE_ELIGIBLE；人类批准不能覆盖 |
| FR-325 | FROZEN candidate 只在从未参与候选生成、选择或调参的 untouched confirmatory holdout 上与 current ProfileVersion 比较 | baseline/candidate、数据分区和评测程序版本固定；同一 holdout 生成并验证 candidate 硬阻断 |
| FR-326 | 总体改善不能掩盖预注册重要 slice 的实质恶化 | 任一伤害界值越线即不放行；不以“不显著”冒充安全 |
| FR-327 | Offline Evaluation Report 展示来源覆盖、成熟/冲突/纠正/缺失/删失、分子/分母/n/CI、支持、反证和限制 | 未知不填 0；历史口径不静默改变 |
| FR-328 | Profile Candidate Revision 基于一个 current base ProfileVersion 与 SEALED Cohort，只用 discovery/train/dev 形成并在预注册前冻结不可变 ProfileDelta | CandidateGenerationManifest、逐维差异、锚点、证据规则、禁用信号和 content hash 齐全；任何变化生成新 Candidate/Study |
| FR-329 | Profile Change Proposal 引用 FROZEN candidate、当前 ANALYSIS_READY Study、风险、适用范围、Release Gate、发布和回滚计划 | Proposal 明确不等于 CandidateRevision、ProfileVersion 或 current pointer；支持 EVALUATION_PENDING→RELEASE_ELIGIBLE→REVIEW_READY→APPROVED→PUBLICATION_AUTHORIZED，以及 REJECTED/INVALIDATED |
| FR-330 | base、canonical Observation、Label、Cohort、Candidate、Run、Study、Gate、用途、权限或权利状态变化使全部下游当前性失效 | 同步读取门阻断报告、Proposal、任务、批准、授权和 pending publish；已 ACTIVE 发布触发 safety Freeze，不只依赖异步事件 |
| FR-331 | Agent 可生成候选解释、仅用 discovery/train/dev 形成 Candidate，并执行已预注册评测，但不能确认 canonical、改分母/分区/指标、反复打开 holdout、批准、授权发布、发布或回滚 | 模型输出只进入草稿/候选聚合命令；无外部或业务直接写权限 |

### 9.4 审阅与发布 FR-332..342

| ID | 需求 | 验收要点 |
|---|---|---|
| FR-332 | 每个 Proposal 同时只有一个当前产品内权威审阅任务；修改、拒绝、失效或 artifact hash 变化撤回旧任务 | 通知/邮件只深链；旧 task revision 只读且不能批准/授权 |
| FR-333 | 审阅首屏展示 Diff、建议原因、分母/成熟度、反证、公平、D0–D4 current/expiry、未来范围和回滚目标 | 业务用户 30 秒内理解现在要决定什么、门是否当前、自己的动作会不会发布 |
| FR-334 | 统计细节、血缘、Run trace 和原始引用渐进披露且最小化 | 默认不暴露完整候选人材料、保护属性或思维链 |
| FR-335 | Proposal 人审动作仅“批准提案 / 要求修改 / 拒绝” | 不预选、不诱导；要求修改撤回任务/eligibility/批准/授权并回到 EVALUATION_PENDING，新差异必须新 Candidate/Study；拒绝进入 REJECTED |
| FR-336 | D0–D4 Gate Assessment 绑定当前 proposal/candidate/study/scope/input hash、独立 Owner、evidence/policy、verdict、evaluated_at 和 expires_at | 全 PASS、未过期且无 veto 才生成不可变 ProfileReleaseEligibilitySnapshot；FAIL/INCONCLUSIVE/EXPIRED/VETO 不能被 Hiring Owner、HRBP 或双人批准覆盖 |
| FR-337 | 只有两个不同 HUMAN 主体分别以 Hiring Owner 与 HRBP/Profile Governance Owner 对同一 candidate/study/release-eligibility/scope hash 批准 | 同一人兼签、Agent/Service、旧页面、旧通知、旧 eligibility 和同键异载命令拒绝；批准不等于发布授权 |
| FR-338 | 双批准后必须由具备 Publication Authority 的当前 HUMAN 另行执行 AuthorizeProfilePublication | 授权绑定精确 proposal/eligibility/scope/effective_at/rollback target；审批、授权、Prepare、同步、Commit 在 UI/审计中互不冒充 |
| FR-339 | CONTROL_PLANE 的 PrepareProfilePublication 在重验当前授权、ProfileReleaseEligibilitySnapshot、base/current 和 safety_epoch 后创建不可变 ProfileVersion 与 PublicationRevision=PENDING_SYNC | Prepare 不更新 current pointer、不让新 Case pin；历史不覆盖，可定位 proposal/study/approval/authorization |
| FR-340 | CONTROL_PLANE 只在 required critical sync receipt set 完整且所有门仍当前时 CommitProfilePublication | PENDING_SYNC→ACTIVE 并原子更新唯一 current_published_version_ref；expected_version/idempotency 收敛，Freeze/新 epoch 优先 |
| FR-341 | 新画像只作用声明的未来招聘周期和新案件 | 在途 Case 保持 pin；迁移需单独逐案影响清单和人审，不在 G3 默认路径 |
| FR-342 | AcceptProfilePublicationSyncReceipt 只接受当前授权发布的关键回执；缺失/失败/未知保持 PENDING_SYNC | 显示未变的 current pointer、各下游 required/optional 回执、原因、有限重试和恢复点；关键同步未齐绝不显示生效 |

### 9.5 监控、冻结与回滚 FR-343..349

| ID | 需求 | 验收要点 |
|---|---|---|
| FR-343 | 画像分析可逐项 A0/A1/A2；画像生效修改、排名、淘汰、发布和回滚永不开放 A3 | A3 只允许监测、建复核任务和按批准规则安全 Freeze |
| FR-344 | A2 监控按批准的 CausalDesignManifest/assignment policy 建立 ProfileExposureLedger，分开记录 assignment、actual exposure、NOT_EXPOSED、contamination、noncompliance 和完整分母 | 不按是否自愿采用 Proposal 分组；同一 Study/Case 分配稳定、偏离不覆盖历史 |
| FR-345 | 真值误用、保护属性、跨租户、用途/删除违规、关键公平退化或影响未知时 Freeze 优先 | Freeze 提升 safety_epoch、取消旧 epoch PENDING_SYNC 并停止新 Case pinning；影响边界未知时以同一 causal token 对 tenant 内每个 RoleProfile 分别发 Freeze，不能跨聚合批量写；迟到 Prepare/Sync/Commit 拒绝 |
| FR-346 | Freeze 不得阻断删除、限制、更正、停止使用和其他安全补偿 | SAFETY_COMPENSATION 继续执行并留回执 |
| FR-347 | FROZEN 只可由具备权限的 HUMAN 授权回滚到此前已批准且当前仍允许的版本 | AuthorizeProfileRollback 绑定影响范围、目标版本、当前 safety_epoch、当前安全复核和 A0 恢复计划；Agent/Service 不得授权 |
| FR-348 | CONTROL_PLANE 消费绑定当前 frozen safety_epoch 的 HUMAN 授权执行 RollbackProfilePublication，原子创建新 PublicationRevision、更新安全 pointer 并使 FROZEN→ACTIVE | 不改写历史观察、决定、画像、评价或在途案件；相关 Study/Proposal/批准/授权按血缘失效，所有受影响画像动作回到 A0 |
| FR-349 | P0 修复、定界、删除/补偿、回归、会签和人工回滚后，恢复 ACTIVE 也只把相关放权降到 A0 | 不能直接恢复事故前 A1/A2/A3；重新取证后逐动作升级 |

### 9.6 Hermes-style harness、体验与治理 FR-350..360

| ID | 需求 | 验收要点 |
|---|---|---|
| FR-350 | 批准来源事件自动启动 SourceAssertion→canonical/成熟→Cohort→candidate/Study→提案准备 | 正常链无需 HR 点火；canonical 冲突、数据不足或 Gate 阻断时等待或只生成一个当前异常包 |
| FR-351 | Activity Rail 分别投影调度、AgentRun、ProfileChangeProposal 和 RoleProfile/Publication 正交状态族 | “尚未开始”只属于调度投影；AgentRun 创建即 RUNNING，随后可待工具/待人/暂停/完成/失败/取消/失效；批准、授权、PENDING_SYNC、ACTIVE、FROZEN、ROLLED_BACK 绝不归入 AgentRun |
| FR-352 | 用户可见当前工作、触发原因、输入版本、holdout access 状态、下一步、Owner/唤醒条件和恢复点 | 正常安静折叠；异常在两步内暂停/接管；不会暴露思维链或保护属性 |
| FR-353 | 模型只产草稿；写入经 typed tool、最小权限、确定性策略门和有限预算 | 模型/材料内指令不能改变状态、工具或权限 |
| FR-354 | 每个 Run 保存 Observe→Plan→Propose→Authorize→Execute→Reconcile→Commit 的最小 trace、checkpoint、回执、重试和补偿 | 不展示思维链；输入变化使旧 resume_token 失效 |
| FR-355 | 陈旧、失败、未知、部分成功、Gate 过期、待另一批准、待授权和等待关键回执诚实显示 | 不用乐观绿色；工具/Agent 成功不冒充提案获批，Prepare 不冒充 pointer 生效 |
| FR-356 | 正常审阅在同一页面完成，每位责任人每个职责只需一次明确决定 | 一个中性主 CTA；批准提案与发布授权是不同任务，高级细节不阻塞主任务 |
| FR-357 | 视觉使用克制企业层级、Version Diff、留白和语义状态 | 不做 AI 炫技面板、玻璃拟态堆叠或 ATS Excel 墙 |
| FR-358 | 键盘、读屏、焦点、200% 缩放/重排、非颜色状态、reduced motion、时区和语言可用 | 适用 WCAG 2.2 AA 目标；危险动作可理解可恢复 |
| FR-359 | ingest/canonical/read/candidate/run/gate/review/approval/authorization/prepare/sync/commit/freeze/rollback/exposure 全链审计 | 每个动作可回答为何、actor/authority、输入版本、safety_epoch、工具/关键回执、pointer 前后与补偿 |
| FR-360 | 每次 ingest/canonical/read/candidate/run/gate/approval/authorization/prepare/sync/commit/rollback 前重验 purpose、ProcessingControl、保留/删除、供应商不训练、租户和 job scope | 冻结时仍允许权利与安全补偿；越界为 P0，失效不能等待异步传播后才阻断 |

## 10. 验收场景

| ID | 前置 / 触发 | 预期 |
|---|---|---|
| AT-301 | 系统尝试把轮次通过、最终决定、Offer、入职和绩效合成 success，或把单一 SourceAssertion 直接当 canonical | Schema/解析门拒绝；各阶段观察与修订独立，多源断言不自动成为真值 |
| AT-302 | 绩效未到成熟窗口、迟到或右删失 | 保持 PENDING/UNKNOWN/RIGHT_CENSORED，不作负例或进入发布型 Proposal |
| AT-303 | FinalDecision 被 supersede，或 canonical Observation 在 Candidate/Run/REVIEW_READY/APPROVED/PUBLICATION_AUTHORIZED/PENDING_SYNC/ACTIVE 任一阶段被纠正、删除或用途失权 | Label、Snapshot、Candidate、Run、Study、ReleaseEligibility、Proposal、Task、Approval、Authorization、Dashboard 全级联失效；PENDING_SYNC 取消，ACTIVE 触发 Freeze，读取门同步阻断 |
| AT-304 | ATS、HRIS 与人工 SourceAssertion 或 candidate↔employee linkage 冲突，迟到回调继续到达 | 进入 Steward 人审；不自动合并、不投票、不按最新/最高置信覆盖；只有授权解析产生唯一 current canonical revision，旧 revision 不复活 |
| AT-305 | 数据只有 hired + 有绩效者 | 披露完整 denominator/选择机制和未观察标签；D1 不 PASS，若仍作因果主张则 D3 也失败；阻断对全漏斗推断、ReleaseEligibility 和画像发布 |
| AT-306 | 历史 recruiter reject/offer/hire 被提交为能力真值 | 硬拒绝；只保留流程/选择事实引用 |
| AT-307 | 决策后面试/绩效字段被放入 prediction_at 前特征 | 时间泄漏检查失败；Run/Study 不可用 |
| AT-308 | 同一 Person 跨岗位/周期进入 train 与 test/holdout | 实体泄漏检查失败并重建 Partition Manifest |
| AT-309 | 两个不可比岗位直接合池 | 无 comparability evidence 时阻断；默认按岗位隔离 |
| AT-310 | 混入另一租户观察、标注、样本、梯度或候选修订 | P0 Freeze 提升 safety_epoch、取消 pending publish、定界与处置；无跨租户业务效果 |
| AT-311 | 受保护属性进入业务画像、匹配、Prompt、Agent Context 或提案 | P0；隔离、冻结、血缘处置，发布门失败 |
| AT-312 | 姓名、口音、学校、邮编等代理替换后输出显著变化 | D2 Gate FAIL/VETO，Proposal 不得 RELEASE_ELIGIBLE；即使两人批准也不能发布，并复核字段/机制 |
| AT-313 | 录制选择、无录制、撤回、采集历史被尝试作为 feature/label/纳排 | 硬阻断；相关选择对画像和结果输出影响为零 |
| AT-314 | 辅助需求、拒绝自动化、申诉、权利请求或 HR override 被尝试作为信号 | 硬阻断并审计；不改变评价、标注或抽样 |
| AT-315 | 删除命中 cache/benchmark/Snapshot/Candidate/Run/Study/Gate/Proposal/Approval/Authorization/pending publish/导出 | 全血缘停止使用、失效、Freeze/补偿和回执；只留无正文墓碑，checkpoint 不得恢复已删内容 |
| AT-316 | 目的变化、供应商训练用途或跨目的读取 | ingest/read/run/publish 门拒绝；不得以既有接口绕过 |
| AT-317 | 小样本、宽 CI、高缺失或选择性标签看似改善，且两位业务审批人仍点击批准 | 只生成描述性 INCONCLUSIVE；适用的 D1/D2/D3 非 PASS，不生成/维持 ReleaseEligibility，批准写入和发布授权均拒绝 |
| AT-318 | candidate 曾读取 confirmatory holdout、在同一 holdout 上调参后再验证，或反复偷看多 slice 只报告最好结果 | CandidateGenerationManifest/holdout access receipt/预注册门失败；必须冻结新 Candidate、创建新 Study 并换 untouched holdout，旧 Study 不可发布使用 |
| AT-319 | 仅已录用绩效被用来声称新画像改善全体候选人，或没有当前 CausalDesignManifest、稳定 assignment、actual exposure/contamination 全分母却作因果主张 | 因选择性标签和因果越界拒绝；只能写关联，不能形成因果 ReleaseEligibility |
| AT-320 | 总体指标改善但重要 slice 实质恶化，或任一 D0–D4 assessment 过期/FAIL/VETO 后两位 HUMAN 仍批准 | ReleaseEligibility 失效且发布硬阻断；“统计不显著”和双人同意都不能覆盖伤害/当前性门 |
| AT-321 | REVIEW_READY/RELEASE_ELIGIBLE Proposal 被要求修改或拒绝；同时 Agent/Service、同一人兼签、双击、旧任务尝试批准/授权 | 修改回 EVALUATION_PENDING 并撤回 task/eligibility/approval/authorization，新差异需新 Candidate/Study；拒绝进入 REJECTED；只有两个不同 current HUMAN 可批准，批准不产生 Publication Authorization/ProfileVersion |
| AT-322 | D0–D4 当前全 PASS，两个不同 HUMAN 已批准，当前 HUMAN 单独授权发布；CONTROL_PLANE Prepare 后关键同步回执先缺失、后齐全，且存在在途案件 | 缺回执时保持 PENDING_SYNC 且 pointer 不变；回执齐且重验通过后 Commit 原子更新 future pointer；旧案保持原 pin，并写稳定 assignment/actual exposure 账本 |
| AT-323 | Freeze 与 Prepare/Sync/Commit 并发、版本刚 Commit 后发现风险，或 P0 影响边界未知 | Freeze 提升 safety_epoch 并胜出：旧 epoch pending 取消、迟到命令拒绝、ACTIVE 版本不得新 pin；影响未知时逐 RoleProfile 施加 tenant 全域安全边界，完成定界与 HUMAN 回滚/复核前不缩小范围 |
| AT-324 | FROZEN 状态下有权限 HUMAN 以当前 frozen safety_epoch 授权回滚到上个批准且仍允许版本 | CONTROL_PLANE 原子创建新 PublicationRevision、更新 future pointer 并使 FROZEN→ACTIVE；历史/在途不改写，依赖研究/提案/批准/授权失效，所有受影响画像动作只回 A0 |
| AT-325 | approval、publication authorization、input manifest、trace、policy、safety_epoch、required sync receipt 或 recovery token 任一缺失/过期 | Prepare/Commit/写动作执行前拒绝；pointer 不变，不能只凭模型、工具或可选下游“成功”提交业务事实 |
| AT-326 | 批准来源自动启动正常链后，工具超时、部分成功、重放或乱序 | 无需 HR 点火；从当前 checkpoint 和权威状态恢复，只有一个业务效果，可对账/补偿，Agent/Proposal/Publication 状态不混写 |
| AT-327 | 系统 FROZEN 时收到删除、限制或结果纠正 | 安全补偿继续；普通 Freeze 不阻断权利履行和血缘失效 |
| AT-328 | Hiring Owner、HRBP、Publication Authorizer、Data Steward、Privacy/Fairness、Analyst、招聘运营完成各自关键任务 | 越权 CTA 不可见/不可写；不把 SourceAssertion 当 canonical、分析完成当提案获批、双批准当发布授权、PENDING_SYNC 当已生效或回滚当恢复原放权；关键误解为 0 |
| AT-329 | 键盘、读屏、200% 缩放、非颜色状态、长文本、时区/语言走通 | 主任务、风险、暂停、拒绝和恢复均可完成 |
| AT-330 | 视觉回归“漂亮”，但真人误解版本/后果或找不到恢复入口 | 发布仍失败；高级审美不能替代任务正确与可恢复 |

## 11. 稳定不变量

以下语义 ID 必须与领域规格中的全部 `INV-G3-*` 完全一致且唯一；它们共同构成 FR/AT、Release Gate 和 UI 状态投影的稳定边界：

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

## 12. 证据门与放权

每个 D0–D4 Gate Assessment 都绑定 exact proposal/candidate/study/scope/input hash、独立 Owner、evidence/policy version、verdict、evaluated_at 与 expires_at。只有全 PASS、未过期且无 veto 才能生成当前 `ProfileReleaseEligibilitySnapshot`；Attach evidence、进入 REVIEW_READY、每次批准、Publication Authorization、Prepare 和 Commit 都同步重验。任何 HUMAN quorum 都不能覆盖 FAIL、INCONCLUSIVE、EXPIRED、VETO、hired-only 外推、重要 slice harm、用途/权限/血缘或因果门失败。

| 门 | 必需证据 | 失败结果 |
|---|---|---|
| D0 数据与标签健康 | 数据地图/PIPIA、来源权限、Taxonomy、canonical resolution、成熟/删失、纠正/删除契约和 label health | 仅合成或描述；无 ReleaseEligibility |
| D1 Cohort、泄漏与外推 | 完整 denominator、选择性标注/缺失机制、prediction_at、tenant/job/time/person 隔离、冻结分区与访问清单 | 不得外推或统计推断；无 ReleaseEligibility |
| D2 指标、公平与代理风险 | train/dev CandidateGenerationManifest、冻结 candidate、untouched holdout access receipt、n/CI、重要 slice、代理红队、漂移、稳定性与成本 | 只允许 INCONCLUSIVE/描述；无 ReleaseEligibility |
| D3 Claim 与因果设计 | claim type、选择机制限制；若主张因果则有当前获批 CausalDesignManifest、稳定 assignment 与 exposure ledger 设计 | 只允许描述性关联复盘；无因果 ReleaseEligibility |
| D4 用途、安全与恢复 | 用途/权限/血缘、跨租户、删除/纠正/full cascade、two-phase publication、safety_epoch、freeze/rollback、trace/replay/故障注入 | No-go；必要时 Freeze |
| A0 影子 | 真实数据另行批准；Proposal 对业务不可见、零案件影响；完整 exposure/trace | 保持 A0 |
| A1 建议 | 授权人可见并能评价证据/局限；采纳/编辑/拒绝原因隔离记录 | 不得发布画像 |
| A2 受控发布 | 当前 ReleaseEligibility、两个不同 HUMAN 批准、独立 HUMAN 发布授权、two-phase publication、未来周期、稳定 assignment/actual exposure、成熟标签、停止条件、回滚演练 | Freeze 并通过 HUMAN rollback 回 A0 |
| A3 | 只允许自动监测、建复核任务和批准规则安全 Freeze | 画像调权、排名、淘汰、发布、回滚与招聘决定永久禁止 |

## 13. 当前结论

本 PRD、领域模型、需求追踪与 lint 完成后，只能登记“G3 产品规格一致”。它不证明结果数据合法、标签无偏、画像候选有效、Hermes runtime 已采用、Agent harness 已实现、真人会正确使用、任何 A0/A1/A2 已运行或画像可发布。

当前保持 No-go。下一证据必须从数据地图/目的批准、Outcome Taxonomy、纠正与成熟演练、完整 Cohort 和离线评测开始；在 E-019 之前不得接入真实任职后个人数据，在 E-029 之前不得让新画像影响真实未来案件。
