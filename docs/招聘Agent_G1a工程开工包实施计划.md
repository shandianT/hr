# 招聘 Agent G1a 工程开工包实施计划

> 状态：执行中  
> 日期：2026-08-10  
> 范围：把已通过合成场景验证的控制塔逻辑，转成研发可领取、可校验、可追踪的 G1a 开工包；不代表真实数据或生产发布获准。

## Goal

为“已结束的单轮面试 → 证据处理 → 评估草稿 → 面试官确认 → 人类轮次决定 → 归档”建立唯一、确定性的控制面契约，并把产品需求拆成有依赖、有验收、有证据位的工程 Backlog。最终交付应让后端、前端、AI/数据、QA、集成和隐私角色可以在不重新解释状态语义的情况下领取工作。

## Approach

1. 以 `ApplicationCase`、`InterviewRound`、`InterviewSession`、`EvidencePackage`、`Evaluation`、`RoundDecision` 为统一语言。
2. 对控制面做三种接口设计：最小通用命令入口、扩展型能力接口、默认路径工作流接口；按接口深度、改动局部性、seam 位置和误用风险选择最终方案。
3. 把最终接口写成技术栈无关的 Markdown 规范，并用 JSON Schema 2020-12 固化命令、结果、事件、动作执行和异常包的机器边界。
4. 以 G1a PRD 的 FR/AT 为基线拆 Backlog；每项同时绑定验收测试和证据 ID，避免“功能完成但无法过门”。
5. 只更新文档、契约和看板，不接入真实邮箱、日历、会议、消息或候选人数据，不执行外部写操作。

## File-level Steps

1. 新建 `招聘Agent_G1a_工程开工包.md`
   - 记录三案对照与推荐接口。
   - 定义深模块、真实 seam、依赖分类、命令处理顺序、错误语义、读模型和部署切片。
   - 提供按 Epic 排序的工程 Backlog、RACI、DoR/DoD 和首两周领取清单。
2. 新建 `contracts/recruiting-agent-g1a-control.schema.json`
   - 定义 `CommandEnvelope`、各 G1a command payload、`CommandResult`、错误码和关键领域标识。
   - 固化幂等、乐观并发、lifecycle epoch、actor 与 policy snapshot 字段。
3. 新建 `contracts/recruiting-agent-g1a-event.schema.json`
   - 定义 `DomainEventEnvelope`、关键事件 payload、`ActionExecution`、`ExceptionBundle` 与证据引用。
   - 区分领域事实和外部副作用执行结果。
4. 新建 `contracts/README.md`
   - 说明契约范围、版本规则、兼容性、验证方法与禁止事项。
5. 新建 `招聘Agent_G1a_需求追踪矩阵.md`
   - 将 PRD 的全部 FR/AT 映射到模块、命令/事件、Backlog、测试层和证据位。
6. 更新 `招聘Agent推进看板.md` 与 `招聘Agent_Gate0执行包.md`
   - 只登记“工程契约/计划证据已形成”；保持真实数据、A0/A1 与外部写入 No-go。
7. 新建 `contracts/lint_contracts.py` 与 `招聘Agent_G1a_工程开工包验收记录.md`
   - 用标准库重复检查本地 `$ref`、命令/事件分支覆盖、FR/AT 覆盖、Backlog 引用和 Markdown 链接。
   - 明确区分结构 lint 与完整 JSON Schema 2020-12 validator，记录剩余验证缺口和文件哈希。

## Risks / Unknowns

- 当前没有代码仓库、技术栈、CI、数据库、身份系统或连接器沙箱证据；契约只能做到技术栈无关，不能虚构工程完成度。
- 目标岗位、客户租户、法务基础、数据地图、保留期限和跨境路径尚未冻结；这些仍是 Gate 0 输入门。
- 转写/评估供应商、对象存储和会议源尚未选型；只定义 port 责任，不绑定厂商。
- 多轮汇总属于 G1b；收件箱、画像筛选、部门推送、约面与催办属于 G2。把它们提前塞进 G1a 会破坏可验收边界。
- 子 Agent 协作运行时本轮出现授权刷新失败；接口对照由主 Agent 按相同约束本地完成并显式记录降级，不影响文件一致性验证。

## Validation

- 所有 JSON 文件通过 `jq empty`。
- 若本机有 Python `jsonschema`，用正例/反例 fixture 验证 command/event Schema；否则至少检查 `$ref` 可解析和关键枚举一致。
- `rg` 核对 PRD 的 FR/AT 数量全部进入追踪矩阵，没有孤儿需求。
- 对照领域规格检查：案件六阶段不被轮次状态覆盖；确认不等于决定；暂停与案件阶段正交；同意撤回和候选人退出不会被重放消息逆转。
- 检查所有新增 Markdown 本地链接存在，并核对看板仍明确标注生产 No-go。
- 记录验证命令、结果、时间和文件 SHA-256；失败项必须回到对应文件修正后再登记证据。
