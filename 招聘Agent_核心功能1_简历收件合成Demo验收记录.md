# 招聘 Agent 核心功能 1：简历收件合成 Demo 验收记录

日期：2026-08-11

状态：`IMPLEMENTED / SYNTHETIC_ONLY` 精确子集；`VERIFIED / RELEASED` 均未达到

范围：合成来源事件与合成附件 → 结构化简历版本 → 重复/身份与路由门 → 自动开案或附加来源

## 1. 本次可验收产物

- [核心功能 1 可点击 Demo](./prototype/招聘Agent_核心功能1_简历收件Demo.html)：六个完全虚构的样例，可演示正常开案、邮箱与 ATS 重复来源、身份冲突、岗位/招聘周期冲突、附件阻断和简历提示注入；不提供真实文件上传入口。
- [合成 intake 运行实现](./runtime/recruiting_intake/)：独立 `recruiting_intake` Module，通过 `submit(command_envelope)` 和 `read(projection_request)` 暴露受控行为。
- [行为测试](./runtime/tests/test_intake_walking_skeleton.py)：31 条 intake 行为测试。
- [合成正常链](./runtime/run_synthetic_intake.py)：输出一个当前 Submission、一个 ApplicationCase、两个来源引用、一个开案业务效果，外部动作和工具执行均为 0。

## 2. 当前实现命令

本切片只实现以下四类命令：

1. `RegisterResumeSubmission`
2. `RecordStructuredResumeVersion`
3. `ResolveApplicationRouting`
4. `OpenOrAttachApplicationCase`

四类命令之外的附件拆分、路由改键纠正、删除传播及完整 G2 命令/事件目录不属于本次实现。

## 3. 当前实现能够证明什么

- 批准来源、来源修订、来源事件、附件、内容 + 申请意图和命令幂等在合成行为中受门控。
- 合成正常链无需 HR 启动；只有当前 `ROUTED` 路由修订可以创建 `ApplicationCase.RECEIVED`。
- 邮箱与 ATS 对同一合成申请重复到达时保留两个来源引用，但只产生一个当前 Submission、一个 Case 和一个开案业务效果。
- 邮箱、手机号、姓名和内容哈希只作身份信号；共享身份信号停在 `ROUTING_REVIEW_REQUIRED`，仅持有当前合成权限的 `HIRING_OWNER` 可从已展示候选项提交判断。
- 同一候选人申请不同岗位形成隔离的 ApplicationKey，不因简历内容相同而合并。
- 加密、损坏、不支持、恶意或扫描未知的合成附件，以及低质量解析，不会编造结构化字段或开案；低质量解析只有两次尝试预算。
- 简历中的提示注入只作为不可信正文发现保存；工具调用和外部动作均为 0。
- 结构化普通字段保存 locator 与置信信号，受保护字段进入隔离区；开案必须引用当前 Routing Revision。
- Demo 可将上述正常链和安全停止点直接展示为产品形态，并能在必要人工判断后继续自动推进。

上述结论只允许把这组精确、合成、可执行行为记为 `IMPLEMENTED / SYNTHETIC_ONLY`。G2 需求追踪矩阵继续保持 `SPEC`，本记录不把完整 `FR-201..218`、`AT-201..205` 或其他 G2 条目升级为已实现。

## 4. 当前验证快照

2026-08-11 在本地工作区复跑：

| 检查 | 当前结果 | 证据边界 |
|---|---:|---|
| `python3 -m unittest runtime.tests.test_intake_walking_skeleton -v` | 31 / 31 通过 | 只覆盖 `recruiting_intake` 当前行为子集 |
| `python3 -m unittest discover -s runtime/tests -v` | 71 / 71 通过 | 当前全 runtime 快照：既有 G1a 40 条 + intake 31 条 |
| `node prototype/check_intake_demo.mjs` | PASS | 证明 Demo 脚本、关键文案和选定交互分支可执行，不代替真人可用性测试 |
| `python3 runtime/run_synthetic_intake.py` | PASS | `CASE_OPENED`、`DUPLICATE_ATTACHED`、一个开案效果、零工具/外部动作 |

这些是当前本地快照；在相同提交的线上 CI 完成前，不表述为 GitHub runner 证据。

## 5. 当前不能证明什么

- 不证明真实招聘邮箱、真实 ATS、真实账号或连接器已经接入。
- 不证明真实文件扫描、恶意文件检测、加密附件处理或供应商回执已经可用；当前附件门是合成规则与 fixture。
- 不证明真实简历解析模型、身份模型、人岗匹配模型的准确率、偏差、成本或稳定性。
- 不证明生产身份网关、实名权限、租户边界、数据保护影响评估、删除血缘或真实审计已经完成。
- 不证明一封邮件包含多位候选人/多附件时的逐件分类与拆分已经实现。
- 不证明已开案路由的改键纠正、旧关系 supersede、旧案处置和补偿闭环已经实现。
- 不证明多节点并发、生产数据库、队列、故障恢复或 Exactly-once 外部效果。
- 不证明完整 `FR-201..218`、`AT-201..205`、整个 G2、完整端到端招聘 Agent 或任何真实发布门已完成。
- 不证明真人任务成功、无障碍、候选人权利体验、法务合规、商业价值或生产效果。

## 6. Gate 结论

Gate 0 保持 **No-go**：真实个人信息、真实邮箱/ATS、真实 A0/A1 和任何外部发送或写入均未放行。下一步只有在补齐精确契约、线上 CI、独立代码/产品复核和相应试点前置条件后，才能讨论扩大实现或动作放权。
