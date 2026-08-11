# 招聘 Agent 产品与控制规格

本仓库承载“简历进入收件源到终面评估包就绪”的招聘 Agent 产品规格、状态与事件契约、控制塔原型和推进证据。

目标不是把单点 AI 功能拼在一起，而是把招聘中段作为一个可托管、可暂停、可审计、可人工接管的案件流程交给 Agent。除候选人、用人部门、面试官等必要输入与明确的人类决策闸门外，流程不依赖 HR 手动发起。

## 当前真实状态

- 产品与控制规格：G1a、G1b 已有规格验收；G2 的 64 FR/28 AT 已通过结构一致性验收；G3 的 60 FR/30 AT 已形成多源结果对账、冻结候选与确认性评测、D0–D4 发布资格、双人批准、独立授权、两阶段未来发布与回滚的产品规格；G2/G3 工程/验证/发布仍为 0。
- 产品 Demo：[新产品形态 Demo](./prototype/招聘Agent_产品形态Demo_v1.html) 已可点击跑完合成主线；另有三个低理解成本的独立切片，分别展示[简历收件](./prototype/招聘Agent_核心功能1_简历收件Demo.html)、[简历筛选与部门决定](./prototype/招聘Agent_核心功能2_画像匹配与部门决定Demo.html)和[候选人约面](./prototype/招聘Agent_核心功能3_候选人约面Demo.html)。尚无真人任务或真实集成证据。
- 运行实现：收件、筛选/部门决定、候选人约面和 G1a 面后归档已有边界明确的本地合成纵切，当前 117 个行为测试与固定 runner 可重复运行，精确状态为 `IMPLEMENTED / SYNTHETIC_ONLY` 子集；G2 矩阵不因此升级。
- 当前 CI：[`spec-lint` run 31463159475](https://github.com/shandianT/hr/actions/runs/31463159475) 已在 Core3 实现 commit `5c1e979` 通过，覆盖四套规格检查、117 条 runtime 行为测试、四个合成 runner 和四个 Demo 检查。
- 真实集成、真实数据、模型质量、真人使用与生产发布：尚无完成证据。
- 发布结论：**No-go**。当前仅允许合成/匿名化数据、沙箱验证和治理准备，不得连接真实邮箱、日历、会议或对候选人执行外部写操作。

## 产品分段

| 分段 | 范围 | 当前产物 |
|---|---|---|
| G1a | 单轮面试后：证据、纪要、评估、确认、人工轮次决策、归档 | PRD、工程开工包、契约、追踪矩阵、合成控制内核与 40 个行为测试 |
| G1b | 多轮串联：追问清单、轮次依赖、终面评估包、失效与重编译 | PRD、追踪矩阵、规格验收记录 |
| G2 | 简历接入至可信面试交接：解析、路由、匹配、部门决定、约面、采集闸门、G1 交接 | PRD、领域规格、追踪矩阵；收件、筛选/部门决定、候选人约面各有精确合成子集，但矩阵实现/验证/发布仍为 0 |
| G3 | 结果回流与画像治理：多源对账、标注成熟、固定 Cohort、预研究冻结候选、确认性评测、发布资格、双人批准、授权与两阶段未来发布、冻结/回滚 | PRD、ADR-0009、领域规格、追踪矩阵与静态验收；IMPLEMENTED/VERIFIED/RELEASED=0，真实数据与画像发布 No-go |

## 关键入口

- [产品落地总方案](./招聘Agent产品落地总方案.md)
- [推进看板](./招聘Agent推进看板.md)
- [Gate 0 执行包](./招聘Agent_Gate0执行包.md)
- [领域与事件规格](./招聘Agent_领域与事件规格.md)
- [领域语言](./CONTEXT.md)
- [G2 收件筛选约面 PRD](./招聘Agent_G2_收件筛选约面_PRD.md)
- [G2 需求追踪矩阵](./招聘Agent_G2_需求追踪矩阵.md)
- [G2 产品规格验收记录](./招聘Agent_G2_产品规格验收记录.md)
- [G3 结果回流与画像治理 PRD](./招聘Agent_G3_结果回流与画像治理_PRD.md)
- [G3 需求追踪矩阵](./招聘Agent_G3_需求追踪矩阵.md)
- [G3 产品规格验收记录](./招聘Agent_G3_产品规格验收记录.md)
- [Hermes 式 Agent 与 UI 设计原则](./docs/招聘Agent_Hermes式Agent与UI设计原则.md)
- [可点击产品形态 Demo](./prototype/招聘Agent_产品形态Demo_v1.html)
- [核心功能 2：简历筛选与部门决定 Demo](./prototype/招聘Agent_核心功能2_画像匹配与部门决定Demo.html)
- [核心功能 3：候选人约面 Demo](./prototype/招聘Agent_核心功能3_候选人约面Demo.html)
- [合成控制面运行说明](./runtime/README.md)
- [核心功能 3 验收记录](./招聘Agent_核心功能3_候选人约面合成Demo验收记录.md)
- [G1a 合成控制面与产品 Demo 验收记录](./招聘Agent_G1a合成控制面与产品Demo验收记录.md)
- [新原型设计任务书](./交付/Claude原型设计任务书.md)
- [控制塔逻辑原型](./招聘Agent控制塔_逻辑原型.html)
- [架构决策记录](./docs/adr/)
- [机器可校验契约](./contracts/)

## 不可突破的产品边界

1. LLM 不直接写状态、不直接调用外部系统、不作录用或淘汰决定。
2. 低匹配分数只能形成证据或提示，不能自动拒绝候选人。
3. 会议邀请中的录制告知不等于有效同意；不同意录制必须有等价的无录制路线。
4. 所有外部动作必须可重试、幂等、留回执，并在执行前重新核对撤回、暂停、删除和版本状态。
5. `FINAL_ASSESSMENT_READY` 只表示终面评估材料满足就绪条件，不表示录用、淘汰或案件关闭。
6. 结果观察、历史招聘决定和任职后表现都不是通用人才真值；不得直接训练或自动改变岗位画像。
7. 画像候选修订必须在确认性 holdout 打开前冻结；研究、发布资格、提案、双人批准、发布授权、关键同步与权威指针提交必须分离。新版本只作用未来周期，画像发布/回滚永不开放 A3。

## 本地校验

```bash
python3 contracts/lint_contracts.py
python3 contracts/lint_g1b_spec.py
python3 contracts/lint_g2_spec.py
python3 contracts/lint_g3_spec.py
python3 -m unittest discover -s runtime/tests -v
python3 runtime/run_synthetic_g1a.py
python3 runtime/run_synthetic_intake.py
python3 runtime/run_synthetic_screening.py
python3 runtime/run_synthetic_scheduling.py
node prototype/check_demo.mjs
node prototype/check_intake_demo.mjs
node prototype/check_screening_demo.mjs
node prototype/check_scheduling_demo.mjs
```

规格检查只证明文档/契约一致；runtime 测试只证明当前合成子集的行为。它们都不能替代真实集成验收、模型评测、安全评估、合规审查、真人任务或真实业务成效。
