# 招聘 Agent G1a 合成控制面与产品 Demo 验收记录

版本：v0.1<br>
日期：2026-08-11<br>
状态：`IMPLEMENTED / SYNTHETIC_ONLY`<br>
发布判定：`NO-GO FOR REAL DATA / EXTERNAL ACTIONS`

## 1. 权威版本与线上证据

| 项 | 值 |
|---|---|
| Git commit | [`ab8cf205e297357fb8ee8555ebe3a3316f17b82e`](https://github.com/shandianT/hr/commit/ab8cf205e297357fb8ee8555ebe3a3316f17b82e) |
| Git tree | `1bb4c523c3646377c0696f028820821c5257169b` |
| GitHub Actions | [`spec-lint` run 31452559339](https://github.com/shandianT/hr/actions/runs/31452559339) · PASS |
| Demo SHA-256 | `06c5740896ae0bb8770890543b931a2bc13d9fc223e97d9d26e5a41f8b516470` |
| Runtime manifest SHA-256 | `c03e0c93ad3db52f2017a0b761d1077c59a6c8afce0f82f42ebcdb88c65c3ae5` |
| 合成归档 hash | `b45671cfc8e883f5ff57bc7e8708b923b25bab6c2a8c387ea8c9cb69395ab2e4` |

Runtime manifest 的复算口径为：对 `runtime/` 下除 `__pycache__` 外的文件按路径排序，逐文件计算 SHA-256，再对完整清单计算 SHA-256。

## 2. 本次交付

### E-031：可点击产品形态 Demo

- 默认 B「候选人旅程」，可无刷新切换 A「控制室」与 C「运营工作台」，案件进度与分支不丢失。
- 一个合成候选人从简历收件走到终面评估包；前两轮快速回放，终面完整演示。
- Agent 自动步骤无需 HR 启动；部门筛选决定和面试评估确认保留为 HUMAN 闸门。
- 「暂缓并说明」和「要求修改」会保留状态、原因、修订版本和恢复检查点。
- 录制同意缺失、日历冲突、部门超时都显示所选安全路线、checkpoint、retry 与新活动记录。部门超时升级后仍回到 Hiring Owner 决策，不会被恢复动作绕过。
- 终面评估包有可打开正文，包含三轮结论、证据引用、能力评分、风险、未解问题、人工确认和控制记录；明确不是录用/淘汰决定。

### E-032：G1a 合成控制内核

- 公开业务接口只有 `submit(CommandEnvelope)` 与 `read(ProjectionRequest)`，自动 Runner 只能提交 `SERVICE` 命令。
- 13 类命令在本地 SQLite 事务中执行，覆盖已结束会话导入、证据/逐字稿、评估草稿、人工确认、独立人工轮次决定、不可变归档、Case 暂停/恢复与合成外部动作回执。
- 权限、tenant/case/lifecycle epoch、幂等、aggregate version、当前评估、暂停令牌和敏感引用边界有公开行为测试。
- 证据和逐字稿离开 `EVIDENCE_PROCESSING` 后不能迟到混入旧评估；重复/低版本逐字稿被吸收或拒绝。
- 归档 hash 钉住 session、artifact checksum/版本、transcript/版本、evaluation、confirmation、decision record 与 lifecycle epoch。
- GitHub runner 执行 40 个 runtime 行为测试、4 套规格一致性检查、合成正常链与 Demo 静态交互检查，全部通过。

## 3. 独立终审

- Runtime 终审先后找到并回归锁定：跨案件引用、暂停令牌世代、非当前评估、最大长度 command ID、逐字稿重复/版本、归档钉住与确认后迟到证据。最终结论为本精确合成子集无剩余 P0/P1。
- Demo 终审检查主线、两类人工退回、三个异常、A/B/C 同状态切换、三轮证据包、桌面与 390px 移动重排；终审发现的人工闸门绕过和版本号矛盾已在当前 commit 修复并复验。

## 4. 这些证据能证明什么

1. 第一个产品形态已可直接打开、可点击、可讲完端到端承诺，并且能看到「终面评估摆上桌」的实际产物形态。
2. G1a 最短面后闭环已不只是文档；合成控制内核中有持久状态、事务事实、事件、Outbox、幂等、版本、人工权限闸门和可重放的固定场景。
3. 这一精确子集可以记为 `IMPLEMENTED / SYNTHETIC_ONLY`，但仍不是 `VERIFIED` 或 `RELEASED`。

## 5. 这些证据不能证明什么

- 不证明真实邮箱、简历、日历、会议、消息、ATS、对象存储、身份网关或模型供应商已接入。
- 不证明 JSON Schema 2020-12 全兼容、多节点 Postgres/消息总线、生产容灾、connector probe/reconciliation、重试策略或 ExceptionBundle 已完成。
- 不证明转写/简历解析/匹配/评估质量、偏见、成本、法务合规、删除血缘、真人可用性、商业价值或生产稳定性。
- 不证明简历收件→解析→去重→路由→部门→约面→会前→会后→终面包→结果回流的完整生产系统已完成。
- 不解除 Gate 0：真实个人信息、录音、A0/A1 与外部发送/写入继续 No-go。

## 6. 下一开发切片

按用户确认的顺序，下一版只向前扩一段：

> 招聘邮箱附件（合成） → 附件安全门 → 结构化简历 → 重复/身份冲突 → 人×岗位×批次路由 → 候选人案件页。

该版仍使用合成附件，但会把 Demo 中的「简历收件」从文案升级为实际可上传、可查看解析、可演示去重/冲突/路由的核心功能。
