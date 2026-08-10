# 招聘 Agent G1b 需求追踪矩阵

> 版本：v0.1  
> 日期：2026-08-10  
> 基线：[G1b 多轮串联与终面评估包 PRD](./招聘Agent_G1b_终面评估包_PRD.md)  
> 口径：`SPEC` 只表示产品模块、命令/事件、目标测试与证据槽已对应；当前没有实现或真人验收证据。

## 1. 状态规则

| 状态 | 含义 |
|---|---|
| `UNMAPPED` | 尚未绑定产品模块、命令/事件或测试 |
| `SPEC` | 产品行为、负面场景和目标证据槽齐全 |
| `IMPLEMENTED` | 实现与契约/行为测试通过，尚未完成人真验证 |
| `VERIFIED` | 目标环境、真人流程、故障/权利演练和 Owner 验收齐全 |
| `RELEASED` | 对应动作通过离线/A0/A1/A2 放权与回滚门 |

证据 ID 是未来实现仓库和试点产生的占位符，不是现有证据。

## 2. FR-101..140

| ID | 产品要求（压缩表述） | 产品模块 / 关键命令或事件 | 目标测试 | 证据槽 | 当前 |
|---|---|---|---|---|---|
| FR-101 | 钉住不可变面试计划版本 | 多轮编排器 / `InterviewPlanPinned` | `G1B-PLAN-001`：模板更新不改变在途计划 | `EV-G1B-FR101` | SPEC |
| FR-102 | 必需/可选/条件显式且图无环 | 计划校验器 / `AmendInterviewPlan` | `G1B-PLAN-002`：环、悬空条件均拒绝 | `EV-G1B-FR102` | SPEC |
| FR-103 | 当前完成件/豁免 + 人类决定后才激活 | 多轮编排器 / `ActivateRound` | `G1B-ACTIVATE-001`：分数/Agent 不能替代决定 | `EV-G1B-FR103` | SPEC |
| FR-104 | 重复轮次新建 Round，不覆盖 | 多轮编排器 / `CreateRepeatRound` | `G1B-REPEAT-001`：来源、ordinal、历史均保留 | `EV-G1B-FR104` | SPEC |
| FR-105 | 计划修订新版本并失效下游 | 影响分析器 / `InterviewPlanAmended` | `G1B-PLAN-003`：只失效受影响 Brief/Package/Task | `EV-G1B-FR105` | SPEC |
| FR-106 | 激活/豁免/重复/迁移走统一命令门 | 控制面 / 通用 Command Gate | `G1B-CONTROL-001`：UI/模型直写全部拒绝 | `EV-G1B-FR106` | SPEC |
| FR-107 | 只有当前 Round/指定面试官能形成和读取简报 | 面前简报 / `PublishInterviewBrief` | `G1B-BRIEF-001`：取消/改派/旧 Round 阻断 | `EV-G1B-FR107` | SPEC |
| FR-108 | 简报只用当前允许输入 | Brief Input Compiler | `G1B-BRIEF-002`：旧/删/过期/跨目的输入拒绝 | `EV-G1B-FR108` | SPEC |
| FR-109 | 独立评价前不披露前轮总分/决定/身份化意见 | Disclosure Gate / `InterviewBriefValidationFailed` | `G1B-DISCLOSE-001`：Schema/策略/发布三层红队 | `EV-G1B-FR109` | SPEC |
| FR-110 | 每条问题有维度/缺口/理由/版本 | Question Provenance Validator | `G1B-BRIEF-003`：无目的/无来源问题阻断 | `EV-G1B-FR110` | SPEC |
| FR-111 | 禁用特征、代理、诱导、敏感问题阻断 | Brief Policy Validator | `G1B-BRIEF-004`：敏感与预设结论语料红队 | `EV-G1B-FR111` | SPEC |
| FR-112 | Brief 钉住 Round/受众/评分卡/输入并可失效 | InterviewBrief / `InterviewBriefInvalidated` | `G1B-BRIEF-005`：任一修订使旧链接只读 | `EV-G1B-FR112` | SPEC |
| FR-113 | 产品任务权威，外部通知最小且幂等 | Brief Task + ActionExecution | `G1B-BRIEF-006`：重试不重复任务/错误收件人 P0 | `EV-G1B-FR113` | SPEC |
| FR-114 | 简报反馈与候选人评价/画像隔离 | Feedback Store / `InterviewBriefFeedbackRecorded` | `G1B-FEEDBACK-001`：反馈不能写评价或画像 | `EV-G1B-FR114` | SPEC |
| FR-115 | 每个完成 Round 有当前轮次完成件 | Round / `InterviewRoundCompleted` | `G1B-COMPLETE-001`：评价/决定/证据缺一不可 | `EV-G1B-FR115` | SPEC |
| FR-116 | 包只接受当前完成件，排除草稿/评论/旧决定 | Final Input Validator | `G1B-INPUT-001`：非当前输入全集拒绝 | `EV-G1B-FR116` | SPEC |
| FR-117 | 豁免只由人提交、版本化且无能力证据 | Waiver / `RecordRoundWaiver` | `G1B-WAIVER-001`：Agent/越权/无理由均拒绝 | `EV-G1B-FR117` | SPEC |
| FR-118 | 相同 EvidencePointer 去重并显示复用 | Evidence Manifest Compiler | `G1B-DEDUP-001`：多轮多 claim 只计一来源 | `EV-G1B-FR118` | SPEC |
| FR-119 | 按维度保留支持/反证/语境/不足 | Final Package Compiler | `G1B-SYNTH-001`：不平均差异、不补写不足 | `EV-G1B-FR119` | SPEC |
| FR-120 | 每条关键汇总 claim 可回源 | Package Evidence Validator | `G1B-EVIDENCE-001`：无 Round/Evaluation/Atom 引用阻断 | `EV-G1B-FR120` | SPEC |
| FR-121 | 计划/画像/评分卡/输入版本兼容 | Version Compatibility Gate | `G1B-VERSION-001`：模板更新不静默迁移 | `EV-G1B-FR121` | SPEC |
| FR-122 | 包无决定/排名/单一总体分 | Package Schema + Publish Gate | `G1B-DECISION-001`：Prompt/Schema/发布三层拒绝 | `EV-G1B-FR122` | SPEC |
| FR-123 | 包 ID/版本/Input Manifest/hash/编译版本不可变 | FinalAssessmentPackage | `G1B-PACKAGE-001`：重编译新版本、旧版不覆盖 | `EV-G1B-FR123` | SPEC |
| FR-124 | 同输入并发只形成一个当前包 | Package Idempotency / `CompileFinalAssessmentPackage` | `G1B-PACKAGE-002`：并发/同键异载 | `EV-G1B-FR124` | SPEC |
| FR-125 | 缺项按 Round/确认/决定/证据/维度/版本分类 | Gap Detector | `G1B-GAP-001`：每类缺项独立阻断/呈现 | `EV-G1B-FR125` | SPEC |
| FR-126 | Agent 只提问题候选并引用双方依据 | CrossRoundIssue / `CrossRoundIssueDetected` | `G1B-ISSUE-001`：Agent 不能选择真伪或改分 | `EV-G1B-FR126` | SPEC |
| FR-127 | 严重度/阻断性由批准规则或人确定 | Issue Classifier / `ClassifyCrossRoundIssue` | `G1B-ISSUE-002`：未分类/P0/P1 阻断 | `EV-G1B-FR127` | SPEC |
| FR-128 | 非阻断问题有责任/理由且持续披露 | Issue Center | `G1B-ISSUE-003`：默认折叠/缺理由均失败 | `EV-G1B-FR128` | SPEC |
| FR-129 | 豁免显式影响证据覆盖/信息不足 | Package Completeness View | `G1B-WAIVER-002`：流程完整≠证据完整 | `EV-G1B-FR129` | SPEC |
| FR-130 | 问题只能通过解决记录关闭，输入变更重验 | `ResolveCrossRoundIssue` / Superseded | `G1B-ISSUE-004`：删除卡片/改摘要不能关闭 | `EV-G1B-FR130` | SPEC |
| FR-131 | 当前 READY 包 + 当前任务 + Owner + 无阻断才可就绪 | Readiness Gate / `MarkFinalAssessmentReady` | `G1B-READY-001`：逐前置缺失矩阵 | `EV-G1B-FR131` | SPEC |
| FR-132 | 就绪不关闭、不决策、不通知候选人 | ApplicationCase / decision separation | `G1B-READY-002`：Case 停在 FINAL_ASSESSMENT_READY | `EV-G1B-FR132` | SPEC |
| FR-133 | 最终任务绑定唯一当前包/展示版本且不预选 | Final Review Task | `G1B-TASK-001`：旧展示版本不能写 | `EV-G1B-FR133` | SPEC |
| FR-134 | 通知失败开异常，不重复权威任务 | ActionExecutor + ExceptionBundle | `G1B-TASK-002`：丢响应/重试耗尽/对账 | `EV-G1B-FR134` | SPEC |
| FR-135 | 输入变化在读取/使用前判包失效 | Package Validity Gate | `G1B-INVALIDATE-001`：每类 causal input 竞态 | `EV-G1B-FR135` | SPEC |
| FR-136 | 失效撤回任务、Case 回 INTERVIEWING、旧包只读 | `InvalidateFinalAssessmentPackage` | `G1B-INVALIDATE-002`：三对象一致变更 | `EV-G1B-FR136` | SPEC |
| FR-137 | 重复/乱序不重复包/任务或复活旧版 | Control + revisions/epoch | `G1B-RACE-001`：事件排列组合/迟到回执 | `EV-G1B-FR137` | SPEC |
| FR-138 | 纠正用 supersede + 重编译，不原地编辑 | Package History | `G1B-CORRECT-001`：旧 hash/差异/新依据保留 | `EV-G1B-FR138` | SPEC |
| FR-139 | 全链路访问与变更审计 | Audit Timeline | `G1B-AUDIT-001`：还原任一决策时点可见材料 | `EV-G1B-FR139` | SPEC |
| FR-140 | 最小必要、分阶段披露、权限、保留与删除 | Privacy Orchestrator | `G1B-PRIVACY-001`：血缘删除/字段访问/回执 | `EV-G1B-FR140` | SPEC |

## 3. AT-101..118

| ID | 场景 / 关键断言 | 主要覆盖 FR | 自动化层 | 证据槽 | 当前 |
|---|---|---|---|---|---|
| AT-101 | 两轮正常链到终面就绪但无最终决定 | 103,115–124,131–133 | state/API + synthetic E2E | `EV-G1B-AT101` | SPEC |
| AT-102 | 有确认无人工决定，不激活下一轮 | 103,106 | state/API | `EV-G1B-AT102` | SPEC |
| AT-103 | REPEAT_ROUND 新建 Round，原轮不变 | 104,106 | domain/API | `EV-G1B-AT103` | SPEC |
| AT-104 | 并行 ALL 前置乱序完成只激活一次 | 102,103,124,137 | concurrency/property | `EV-G1B-AT104` | SPEC |
| AT-105 | 简报不泄露前轮总分/决定/身份化意见 | 108–110 | disclosure/red-team | `EV-G1B-AT105` | SPEC |
| AT-106 | 敏感/诱导问题被阻断并留异常 | 110,111 | policy/red-team | `EV-G1B-AT106` | SPEC |
| AT-107 | 面试官改派使旧简报失效 | 107,112,113 | auth/race | `EV-G1B-AT107` | SPEC |
| AT-108 | 同证据多轮复用不虚增覆盖 | 118,119 | compiler/property | `EV-G1B-AT108` | SPEC |
| AT-109 | 必需轮次缺失阻断编译 | 115,116,125,131 | completeness/API | `EV-G1B-AT109` | SPEC |
| AT-110 | 人工豁免满足流程但显式保留证据缺口 | 117,125,129 | domain/UI snapshot | `EV-G1B-AT110` | SPEC |
| AT-111 | 未处理 P1 跨轮问题阻断就绪 | 126,127,131 | issue/API | `EV-G1B-AT111` | SPEC |
| AT-112 | 非阻断语境差异持续披露 | 126–130 | issue/UI snapshot | `EV-G1B-AT112` | SPEC |
| AT-113 | HIRE/排名输出被三层阻断 | 122 | schema/red-team | `EV-G1B-AT113` | SPEC |
| AT-114 | 轮次评价修订使包/任务失效并回退 Case | 105,135,136,138 | cross-aggregate/race | `EV-G1B-AT114` | SPEC |
| AT-115 | 旧包链接只读且不能支持新决定 | 133,135,136 | security/API | `EV-G1B-AT115` | SPEC |
| AT-116 | 编译/通知重复乱序仍只有一个当前包/任务/效果 | 124,133,134,137 | concurrency/connector mock | `EV-G1B-AT116` | SPEC |
| AT-117 | 删除传播使包失效并形成回执 | 135,136,139,140 | privacy/integration | `EV-G1B-AT117` | SPEC |
| AT-118 | 产品任务成功、外部通知失败：材料可就绪但不计可信托管 | 131,134,139 | fault injection/SLO | `EV-G1B-AT118` | SPEC |

## 4. 横向发布门

| 套件 | 断言 | 证据槽 |
|---|---|---|
| `G1B-X-AUTHORITY` | Agent/Service 无法提交豁免、问题最终分类或招聘决定 | `EV-G1B-X01` |
| `G1B-X-DISCLOSURE` | 所有简报字段在独立评价前符合 staged disclosure；例外有目的/权限/审计 | `EV-G1B-X02` |
| `G1B-X-CURRENTNESS` | Brief/Completion/Issue/Package/Task 每个 read/write 都重验当前 version/epoch | `EV-G1B-X03` |
| `G1B-X-ATOMICITY` | 每个单聚合事务的 state/result/event/outbox 原子；跨聚合失效最终收敛且读取前安全 | `EV-G1B-X04` |
| `G1B-X-NO-DECISION` | Prompt 注入、结构绕过、Service actor、旧页面均无法生成有效招聘决定或建议字段 | `EV-G1B-X05` |
| `G1B-X-MINIMIZATION` | 事件/日志不复制简报正文、完整评价、逐字稿或联系方式 | `EV-G1B-X06` |
| `G1B-X-ROLLBACK` | 能按动作撤回 Brief/Task、降级通知、保留包历史且不破坏 G1a 完成件 | `EV-G1B-X07` |

## 5. 覆盖快照

| 项 | 基线 | 已映射 | 已实现 | 已验证 | 已发布 |
|---|---:|---:|---:|---:|---:|
| FR | 40 | 40 | 0 | 0 | 0 |
| AT | 18 | 18 | 0 | 0 | 0 |

现有控制塔原型的“两轮正常链”只能作为 AT-101 的部分合成逻辑证据，不能证明其余 17 个 G1b 场景，更不能将任何条目标记为 `IMPLEMENTED` 或 `VERIFIED`。

