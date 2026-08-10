# 招聘 Agent G3 产品规格实施计划

版本：v0.1
日期：2026-08-10
状态：产品规格完成记录；不是工程实施状态

## 1. 目标

把总方案中“招聘结果回流画像”从两句方向补成可评审、可拆解、可机械检查的产品规格，并切断“历史结果 → 自动调权”的自我强化反馈环。

## 2. 已完成的规格工作

1. 补齐结果观察、标注、任职后信号、分析队列、研究、候选修订、发布与回滚的统一语言。
2. 通过 ADR-0009 冻结“观察不是真值、画像只能经受控研究与人工发布改变”。
3. 在领域规格中新增 G3 聚合、状态、值对象、单聚合命令、事件、跨聚合 seam 和失效链。
4. 修复 `RecordFinalDecision` 无权威事件的问题，新增 `FinalHiringDecisionRecorded / Superseded`，G3 只引用 ApplicationCase 的 HUMAN 决定。
5. 形成 FR-301..360、AT-301..330、横向 Gate 和追踪矩阵；初始均为 SPEC，IMPLEMENTED/VERIFIED/RELEASED 为 0。
6. 冻结 Hermes-style Agent harness 与高级简洁 UI 原则：模型建议、确定性授权、工具执行、回执对账、业务提交分离。
7. 增加静态 lint、验收记录与仓库 CI 入口。

## 3. 关键产品取舍

| 取舍 | 当前决定 |
|---|---|
| 自动学习速度 vs 可审治理 | 选择来源断言/当前解析→标签→Cohort→仅 train/dev 生成并冻结候选→预注册确认性 Study→当前发布资格→Proposal→双人批准→单独授权→两阶段发布 |
| 历史通过率 vs 完整分母 | 必须披露选择机制、成熟/缺失/删失；幸存者样本不外推 |
| 一键发布 vs 事实分离 | 审阅可在一个页面完成，但批准、发布授权、准备版本、关键同步回执、权威指针提交仍是可辨认事实 |
| 多岗位合池 vs 可比性 | 默认岗位隔离；无可比性证据不合池；跨租户候选人级学习禁止 |
| 高级 UI vs 可理解 | Quiet by default、One primary action、渐进披露；真人误解即 No-go |
| 自主恢复 vs 高风险控制 | Run 可 checkpoint/replay；画像发布/回滚无 A3，P0 可规则冻结 |

## 4. 工程与证据依赖

规格完成后仍需按顺序取得：

1. E-019 数据地图/PIPIA、结果来源与任职后目的批准。
2. E-020 Outcome Taxonomy、来源/纠正/成熟/冲突行为契约与演练。
3. E-021 完整 denominator 的冻结 Cohort 与 label-health 报告。
4. E-022/E-023 固定 holdout、统计/公平/代理/选择偏差与因果边界审查。
5. E-024/E-025 领域/连接器/血缘/冻结回滚红队与 Agent harness 故障恢复。
6. E-026 用人负责人（Hiring Owner）、HRBP/画像治理负责人（Profile Governance）、发布授权人（Publication Authorizer）、结果数据管理员（Data Steward）、隐私/公平负责人（Privacy/Fairness）、AI/数据分析师（Analyst）和招聘运营七类 HUMAN 的真人任务、关键误解、无障碍和视觉验收；未取得记录前不得声称真人可用。
7. E-027..E-030 A0 → A1 → A2、未来周期试验与发布/回滚会签。

## 5. 当前边界

当前只可声称“G3 产品规格静态一致”。不得声称真实数据可用、Agent harness 已实现、采用 Hermes Agent runtime、画像改进有效、公平、真人可用、A0/A1/A2 已运行或画像已发布。总体仍为 No-go。
