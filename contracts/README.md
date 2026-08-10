# 招聘 Agent G1a 契约

本目录把 [G1a MVP PRD](../招聘Agent_G1_MVP_PRD.md) 和 [领域与事件规格](../招聘Agent_领域与事件规格.md) 中最容易被工程实现“解释走样”的边界固化成可机器校验的 JSON Schema。它是工程开工输入，不是生产接口已实现的证明。

## 文件

- `recruiting-agent-g1a-control.schema.json`：命令信封、19 类 G1a 命令、统一结果和错误码。
- `recruiting-agent-g1a-event.schema.json`：事件信封、24 类领域事件、`ActionExecution` 和 `ExceptionBundle`。

两份 Schema 均使用 JSON Schema 2020-12，当前契约版本为 `1.0.0`。

## 唯一写路径

对产品 UI、工作流 Worker、模型流水线和连接器而言，外部模块只有两个入口：

```text
submit(CommandEnvelope) -> CommandResult
read(ProjectionRequest) -> CaseProjection
```

`read` 是无副作用查询；它的页面文案由 `ApplicationCase.stage + InterviewRound.state + RuntimeEnvelope` 推导，不接受“写页面状态”。SDK 可以提供 `importCompletedInterview()`、`confirmEvaluation()` 等强类型便捷函数，但它们必须只构造 `CommandEnvelope`，不得形成第二条写路径。

## 处理顺序

控制面对每个命令按固定顺序执行：

1. 校验 Schema、已认证主体、租户/部门/岗位/字段权限。
2. 对幂等键计算规范化 payload hash：同键同负载返回首次结果；同键异负载返回 `IDEMPOTENCY_KEY_REUSED` 并报警。
3. 校验 `expected_aggregate_version` 和 `lifecycle_epoch`。
4. 重读关闭、撤回、删除、三级暂停与熔断状态。
5. 从服务端加载当前 `ActionPolicySnapshot`；客户端无权选择策略版本或自治等级。
6. 校验所有引用对象同租户、同案件且版本有效；处理媒体前重验授权。
7. 执行单一聚合迁移；在同一数据库事务写聚合、命令结果、领域事件和 Outbox。
8. 事务提交后由 Worker 执行外部动作；执行前再次重读控制状态并按业务幂等键对账。

跨聚合不做分布式事务。事件消费者加载目标聚合当前状态后，再提交带版本的新命令。`ImportCompletedInterview` 的受控顺序是：先在 `InterviewSession` 记录已结束事实，再在 `InterviewRound` 导入；任一步重放都返回原结果，不伪造 `SCHEDULED` 或 `IN_PROGRESS`。

## 结果语义

| status | 含义 | 调用方行为 |
|---|---|---|
| `APPLIED` | 本地事务已提交；可能已经产生待执行 Outbox，但不代表第三方副作用已成功 | 读取事件/动作 ID，等待投影或动作结果 |
| `REPLAYED` | 同幂等键、同规范负载，返回首次命令的结果 | 当成功处理；不得再造新任务 |
| `REJECTED` | 命令没有改变权威状态 | 按结构化错误决定刷新、修复或打开异常包 |
| `IGNORED_STALE` | 外部事实修订低于当前版本，安全记录后忽略 | 停止重试；必要时对账 |

`APPLIED` 绝不等于“邮件已发送”“模型已完成”或“轮次已决定”。外部效果只由 `AutomationActionSucceeded` 和连接器回执证明；轮次完成只由当前确认评价 + 有权限的人类决定 + `InterviewRoundCompleted` 共同证明。

## 信任边界

- `actor_context` 必须由认证网关注入。浏览器字段、模型输出和第三方 webhook 里的 actor 信息都不可信。
- 模型只返回受限草稿 artifact；`decision_fields_present` 必须为 `false`，`tool_execution_count` 必须为 `0`。
- `ReachConfirmationQuorum`、`RequestExternalAction` 只允许内部工作流服务身份提交；UI 不能用它们跳过审阅或策略门。
- `RecordRoundDecision` 只接受 `HUMAN` actor 且要校验权限快照；评分或推荐永远不能自动转换为该命令。
- 事件总线只放 ID、版本、哈希和受控摘要，不放简历全文、候选人联系方式、录音或完整逐字稿。

## 兼容性规则

- 同一 major 版本只能新增可选字段、新事件类型或新错误码；不得改变已有字段语义。
- 新增必填字段、删除/重命名字段、收窄既有枚举或改变幂等语义必须升 major。
- 消费者必须忽略自己不订阅的事件类型，但不能忽略已订阅事件中的未知 major 版本。
- 生产者先双写兼容事件、再迁移消费者、最后停写旧版本；禁止直接覆盖历史事件。
- 内容修订产生新 artifact/evaluation version；Schema 版本不是业务内容版本。

## G1a 边界

本契约只开放单轮面后证据闭环。`FinalAssessmentPackageReady`、简历收件/解析/筛选、部门决定、约面/改期/取消和候选人沟通命令不在本版本中。它们分别属于 G1b/G2；后续可以在同一信封中增加命令类型，但必须重新完成威胁建模、契约测试和动作级放权。

## 验证

语法检查：

```bash
jq empty contracts/recruiting-agent-g1a-control.schema.json
jq empty contracts/recruiting-agent-g1a-event.schema.json
python3 contracts/lint_contracts.py
```

`lint_contracts.py` 只用标准库检查本地 `$ref`、命令/事件分支覆盖、FR/AT 覆盖、Backlog 引用、链接和 No-go 声明；它**不是** JSON Schema 2020-12 的完整实现。完整正反 fixture 仍必须在实现仓库 CI 中使用标准 validator 运行。

实现仓库必须增加：

- 每类命令至少一个合法 fixture、一个缺字段 fixture、一个越权/非法迁移行为测试。
- 同幂等键同负载、同键异负载、并发版本冲突、旧 epoch、暂停后队列执行五类控制面契约测试。
- 所有事件 fixture 的 Schema 验证和内容最小化扫描。
- 连接器成功但响应丢失、迟到成功、重复回调和取消竞态的对账测试。

当前验证结果和 SHA-256 在 [工程开工包](../招聘Agent_G1a_工程开工包.md) 中登记。
