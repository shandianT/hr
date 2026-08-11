# 招聘 Agent G1a 合成控制面实现计划

版本：v0.1
日期：2026-08-11
状态：实现完成，待线上 CI 证据

## 1. Goal

在不连接真实邮箱、日历、会议、模型、消息平台或候选人数据的前提下，交付一条可本地运行、可重复验证、带持久化和审计事实的 G1a 纵切：

> 已结束会话 → 受控导入 → 合成证据/逐字稿 → 合成评价草稿 → 人工确认 → 独立人工轮次决定 → 不可变归档

退出标准不是“页面能演示”，而是控制面接口、事务事实与行为测试足以把本切片实际覆盖的需求从 `SPEC` 提升为 `IMPLEMENTED`。真实数据、真人采用、真实连接器、A0/A1 和生产发布继续保持 No-go。

## 2. Approach

### 2.1 采用的 Module 与 Interface

第一版只有一个对调用方和测试公开的深 Module：`RecruitingCaseControl`。

```text
submit(CommandEnvelope) -> CommandResult
read(ProjectionRequest) -> CaseProjection
```

Interface 包含命令顺序、幂等、版本、生命周期 epoch、权限、控制态、引用与授权失败语义。聚合存储、状态迁移、事件、Inbox/Outbox、审计和投影都隐藏在 Implementation 内。业务行为通过两个公开入口验证；仅故障注入、损坏状态防御和合成前置的测试直接操作私有 SQLite。

### 2.2 技术路线

采用 Python 3.9+ 标准库和 SQLite：

- 当前仓库已有 Python 规格检查与 GitHub runner，不增加依赖安装或供应链面。
- SQLite 以 `:memory:` 跑行为测试，以本地文件跑可恢复演练；同一事务可证明 aggregate、command result、event 与 outbox 的原子性。
- SQLite 属于 Module 内部的 local-substitutable 实现，不把 repository 暴露成第二条写路径。
- 后续生产存储迁移到 Postgres 时，保持 `submit/read` Interface 不变；只有出现测试和生产两个真实 Adapter 时才固定存储 seam。

这一选择用于建立可执行控制内核，不代表生产部署、云区域、Web 框架或真实连接器已经选型。

### 2.3 本轮支持范围

完整走通以下核心命令：

1. `RegisterCompletedSessionFact`
2. `ImportCompletedInterview`
3. `RegisterEvidenceArtifact`
4. `RecordTranscriptOutcome`
5. `RecordEvaluationDraftGenerated`
6. `PublishEvaluationForReview`
7. `SubmitEvaluationReview`
8. `ReachConfirmationQuorum`
9. `RecordRoundDecision`
10. `PauseScope` / `ResumeScope`
11. `RequestExternalAction`
12. `RecordExternalActionResult`

其中 `PauseScope` 第一切片只实现 Case 作用域；tenant/requisition 暂不伪装成可用。运行实现共覆盖 13 类命令，同时实现通用命令门、重复/旧消息吸收、不可变事件、Outbox 记录与按权限只读案件投影。ExceptionBundle 仍未实现。其余 G1a 命令继续保留在 Schema 中，但在本轮运行实现中显式返回 `INVALID_TRANSITION / command.not_implemented_in_synthetic_slice`，不得伪装成已支持。

### 2.4 合成 Provider

- 合成证据和评价都作为固定 fixture 输入，不调用 LLM。
- `decision_fields_present` 必须为 `false`，`tool_execution_count` 必须为 `0`。
- 恶意逐字稿中的指令只作为内容；运行时没有工具调用入口。
- 外部效果只写 Outbox/ActionExecution mock，不发送任何消息。

## 3. File-level Steps

### 3.1 Red：先固化行为

1. 新建 `runtime/tests/test_g1a_walking_skeleton.py`
   - 证明完整正常链最终为 `COMPLETED`，归档钉住会话、证据、评价和人工决定版本。
   - 证明评价确认后仍是 `AWAITING_OUTCOME`，不会自动形成轮次决定。
2. 新建 `runtime/tests/test_command_gates.py`
   - 同键同负载返回 `REPLAYED`，同键异负载拒绝。
   - 旧 aggregate version、旧 lifecycle epoch、暂停状态和非 HUMAN 决定均拒绝。
   - 缺同意、关键 claim 无证据、评价含决定字段或工具执行均拒绝。
3. 新建 `runtime/tests/test_atomic_facts.py`
   - 一个成功命令同时留下 aggregate、command result、event；失败命令三者都不变。
   - 重放不产生第二个事件或 Outbox 业务效果。
4. 新建 `runtime/tests/test_runner_recovery.py`
   - 命令已提交但 checkpoint 未保存时，Runner 重启通过同幂等键得到 `REPLAYED` 并继续。
   - 验证命令已提交 / checkpoint 未保存窗口的幂等恢复；暂停后的排队动作被抑制。Connector lease、probe 和 reconciliation 尚未实现。
5. 在 `runtime/recruiting_control/scenario.py` 集中定义完全合成的命令、actor 与 artifact 引用，每次运行重建固定 fixture。

先运行测试并记录预期失败，确认失败源于实现尚不存在，而不是测试语法或 fixture 错误。

### 3.2 Green：实现最小深 Module

6. 新建 `runtime/recruiting_control/__init__.py`
   - 只导出 `RecruitingCaseControl` 和稳定结果/查询类型。
7. 新建 `runtime/recruiting_control/control.py`
   - 实现 `submit/read`。
   - 固定 Schema 子集门 → authority/scope → 幂等 → version → Case epoch → 控制态 → 引用/授权 → 单聚合提交顺序。
8. 第一切片暂将私有 SQLite storage、domain handler 和 projection 收敛在该深 Module 内，不向调用方暴露 repository。在增加第二存储 Adapter 或扩展下一个运行切片前，再拆出 `_storage.py` / `_domain.py` / `_projection.py`，避免无证据的提前抽象。
9. 新建 `runtime/recruiting_control/runner.py`
    - 公开 `start/tick/read_run`，只向 `RecruitingCaseControl.submit` 提交命令。
    - 保存 `run_epoch + workflow_version + step_id + input_manifest_hash` checkpoint；不能直接改聚合或构造 HUMAN 命令。
10. 新建 `runtime/run_synthetic_g1a.py`
    - 以固定 fixture 运行正常链并输出机器可读摘要；不启动网络监听、不访问外部账户。

### 3.3 Refactor：证据、文档与 CI

11. 新建 `runtime/README.md`
    - 说明运行方法、支持命令、明确未支持范围和 No-go。
12. 更新 `.github/workflows/spec-lint.yml`
    - 在现有规格检查后运行标准库行为测试和合成链。
13. 新建 `招聘Agent_G1a合成控制面验收记录.md`
    - 记录 commit、CI、测试映射、证明/不证明和 SHA-256。
14. 更新 `招聘Agent_G1a_需求追踪矩阵.md`、`招聘Agent推进看板.md`、`招聘Agent_Gate0执行包.md`
    - 只把有行为证据直接覆盖的条目升级为 `IMPLEMENTED`。
    - 模型质量、真人可用、真实集成、删除血缘、A0/A1 与发布继续为 0。

## 4. Risks / Unknowns

- 当前没有实名技术负责人或生产技术栈签核；本实现不能替代架构评审。
- SQLite 只证明本地事务语义，不证明多节点 Postgres、消息总线或生产容灾。
- 仓库内零依赖验证器仅覆盖当前两份 Schema 实际使用的关键字子集；不能替代通用 JSON Schema 2020-12 validator，19 命令 / 24 事件的完整正反 fixture 仍是后续证据门。
- 合成转写/评价只能验证控制逻辑，不能证明转写准确率、证据质量、偏见、成本或候选人体验。
- 已有单文件可点击产品形态 Demo，但它仍是独立合成原型，尚未连接运行内核，也没有真人可用性证据。
- ExceptionBundle 尚未实现；真实 Provider 重试耗尽、迟到成功、对账和补偿需要后续切片。

## 5. Validation

每次提交至少执行：

```bash
python3 -m unittest discover -s runtime/tests -v
python3 runtime/run_synthetic_g1a.py
python3 contracts/lint_contracts.py
python3 contracts/lint_g1b_spec.py
python3 contracts/lint_g2_spec.py
python3 contracts/lint_g3_spec.py
git diff --check
```

必须得到的行为证据：

- 正常链唯一完成，归档不可变。
- 评价确认与人工决定明确分离。
- 同键同负载重放无第二效果；同键异负载拒绝。
- version/epoch 过期拒绝，暂停优先阻断。
- `SERVICE`、`SYSTEM`、Agent/模型产物均不能提交有效人工决定。
- 缺授权、无证据关键结论、决定字段和工具执行都不能进入审阅。
- 失败命令不留下半个状态、孤儿事件或外发意图。

## 6. 后续顺序

1. 冻结首个产品形态 Demo，用它确认全链路信息层级、必要人工决策点和 Agent Activity Rail。
2. 按核心功能逐一实现：简历收件 / 解析 / 去重 / 路由 → 部门决策 → 约面 → 面前简报 → 会后证据 / 评估 → `FINAL_ASSESSMENT_READY`。
3. 同时补 G1a 完整 Schema fixture、Privacy/Delete、ActionExecutor 故障注入、ExceptionBundle 和真实身份网关。
4. 真实邮箱、日历、会议和消息外发必须逐动作通过 Gate；G3 等合法完整分母和 E-019..E-026 证据后再投入发布工程。
