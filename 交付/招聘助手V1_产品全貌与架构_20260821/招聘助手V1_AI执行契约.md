---
document_type: agent_execution_contract
product: 招聘助手 V1
version: 1.0
status: approved
updated_at: 2026-08-21
work_packages:
  - SCREENING_AND_JD_ASSETS
  - UI_LAYER
  - BOSS_AUTOMATION_SPIKE
---

# 招聘助手 V1：AI 执行契约

## 0. 执行声明

这是给 Codex、Claude Code 或其他编码 Agent 使用的执行契约，不是自由发挥的参考建议。

启动任务时必须提供：

- WORK_PACKAGE：SCREENING_AND_JD_ASSETS、UI_LAYER、BOSS_AUTOMATION_SPIKE 三选一；
- WORKSPACE_ROOT：该 Agent 独立工作的目录；
- BASELINE：开始工作的提交、版本或文件快照；
- AVAILABLE_INPUTS：已经提供的接口样例、测试账号或数据；
- STOP_CONDITIONS：权限、外部写入、真实数据或不可逆操作的停止条件。

如果 WORK_PACKAGE 未指定，停止修改，只返回三个可选工作包。不要自行同时承担多个工作包。

### 0.1 当前负责人绑定

| WORK_PACKAGE | 负责人 | 责任边界 |
|---|---|---|
| SCREENING_AND_JD_ASSETS | 项目负责人（本文发起人） | 简历自动化筛选评估、JD 画像资产和筛选结果接口 |
| UI_LAYER | 新源 | HR 工作台 UI 层建设 |
| BOSS_AUTOMATION_SPIKE | 周玮 | BOSS 自动打招呼、简历信息抓取和进入飞书的可行性测试 |

飞书招聘 API 的只读接入、权限申请和 CandidateSnapshot 标准化尚未指定负责人。任何 Agent 都不得默认接管；联调前由项目负责人补充责任人或另立工作包。

## 1. 必读材料与优先级

执行前按顺序读取：

1. 本文件：技术执行范围、接口和完成条件；
2. 招聘助手V1_产品全貌与分工_人类版.md：业务目标和协作解释；
3. diagrams/招聘助手V1_总架构流程图.mmd：流程和边界的可编辑图源；
4. WORKSPACE_ROOT 中的真实代码、配置、测试和版本状态。

优先级规则：

- 当前代码和配置决定“现在真实存在什么”；
- 人类版决定业务目标；
- 本执行契约决定 AI 如何实现和验收；
- 架构图只帮助理解，不覆盖文字约束。

如果材料互相矛盾，停止冲突部分的实现，在 RETURN_REPORT.md 中列出冲突、影响和需要确认的决定。不要自行选择更方便的一版。

## 2. 全局目标

交付一个一期只做简历筛选的内部 HR 工作台：

~~~text
飞书招聘新投递
→ 只读同步
→ 简历解析与去重
→ AI 提取原文证据
→ 服务端固定规则评分
→ HR_REVIEW_REQUIRED
→ HR 人工确认或纠错
~~~

BOSS 路径是独立可行性 Spike，不是正式 V1 的生产依赖。

## 3. 不变量

每个工作包都必须维持以下不变量：

1. 飞书招聘是正式主链路唯一的人才档案源。
2. 官网投递直接进入飞书招聘，不经过邮箱。
3. 招聘助手只读飞书招聘；V1 不写回、不推进招聘阶段。
4. BOSS 实验数据如需进入主链路，必须先形成飞书招聘中的可追溯记录。
5. AI 只提取事实、原文证据、缺失项和冲突；最终分数由版本化固定规则计算。
6. 筛选成功只能进入 HR_REVIEW_REQUIRED，不能产生通过、淘汰、约面或阶段推进决定。
7. HR 确认或纠错必须记录操作者、时间、输入版本、修改内容和原因。
8. 真实租户、真实模型和真实候选人路径没有验证证据时，状态必须写“未验证”。
9. 凭证、令牌和候选人敏感数据不得写入代码、日志、样例、截图或交付包。
10. 保留用户已有改动；只修改 WORKSPACE_ROOT 和当前工作包授权的文件。

## 4. Agent 执行步骤

### Step 1：确认工作包

读取 WORK_PACKAGE，只加载该工作包的步骤、输入和完成条件。

完成条件：工作包恰好为三个允许值之一；否则不修改文件。

### Step 2：检查当前状态

检查：

- 工作区文件与 Git 状态；
- 已存在的功能、接口、测试和样例；
- 用户未提交改动；
- 所需输入是否齐全；
- 外部系统和真实数据边界。

完成条件：列出“已经存在、需要新增、明确不改、当前缺失”的清单。

### Step 3：锁定当前任务

只选择一个可以独立验收的代表性路径。不要为了完整感增加聊天 Agent、微服务、Kafka、Redis、向量数据库、通用工作流平台或第二套 ATS。

完成条件：目标路径有明确输入、输出、文件范围和验证方式。

### Step 4：实现

按照所选工作包的实施顺序执行。接口样例优先于内部表结构；跨工作包只能通过本契约定义的结构协作。

完成条件：代表性路径在授权范围内可运行，异常路径不会伪装成功。

### Step 5：验证

运行与改动范围相匹配的测试，并检查用户可见路径。源码测试、Mock、合成数据和真实外部验证必须分别报告。

完成条件：每个工作包的验收项都有命令输出、页面证据、结构校验或明确的未验证说明。

### Step 6：交接

在 WORKSPACE_ROOT 生成 RETURN_REPORT.md，使用第 12 节模板。

完成条件：下一位协作者不阅读聊天记录，也能知道做了什么、如何验证、还缺什么和不能宣称什么。

## 5. 工作包：简历自动化筛选评估与 JD 画像资产

**负责人：项目负责人（本文发起人）**

### 5.1 Objective

把约定格式的飞书 CandidateSnapshot 转换成有原文依据、等待 HR 复核的筛选结果，并维护可版本化复用的 JD 画像资产。

### 5.2 Inputs

- 飞书 API 接入方提供的 CandidateSnapshot；
- 试点岗位 ID 或选择规则；
- 至少一个 JD 画像及其版本；
- 企业模型调用方式和数据处理边界；
- 新源确认的列表、详情、原文和复核字段；
- 合成 CandidateSnapshot 与授权真实投递测试窗口。

缺少真实租户输入时，先实现合成契约路径，并把真实端到端路径标记为未验证。

### 5.3 Owned capabilities

- JD 画像的结构、版本、变更记录和试点资产；
- PDF、DOCX、TXT 解析、内容哈希和原文定位；
- EvidencePackage 生成和格式校验；
- 版本化 JD 画像与确定性评分；
- 状态机、异常队列和审计；
- ReviewCandidate 和 HRReviewCommand 内部 API。

### 5.4 Out of scope

- HR 页面和视觉实现；
- BOSS 登录、沟通或简历爬取；
- 飞书招聘 API 鉴权、读取和 CandidateSnapshot 标准化，除非项目负责人另行书面指定；
- 自动淘汰、约面、外联、飞书写回和阶段推进；
- 把模型输出直接当作最终分数；
- 以本地测试代替真实租户验证。

### 5.5 Implementation order

1. 固定 CandidateSnapshot、ReviewCandidate、HRReviewCommand 样例；
2. 固定 JD 画像 schema、版本规则和试点画像资产；
3. 用合成 CandidateSnapshot 实现筛选输入路径；
4. 实现内容哈希、岗位内去重和幂等；
5. 实现文件解析及原文位置索引；
6. 实现 EvidencePackage 结构校验；
7. 实现版本化固定规则评分；
8. 实现状态机、异常和审计；
9. 实现供 UI_LAYER 使用的列表、详情、原文和复核接口；
10. 在飞书接入方提供数据后执行真实代表性端到端验证。

### 5.6 Completion criteria

- 一个固定 CandidateSnapshot 可生成 ReviewCandidate；
- 至少一个试点 JD 画像有版本、字段定义和验收样例；
- 同一岗位和同一简历重复同步不生成重复筛选任务；
- PDF、DOCX、TXT 代表性文件能够解析或进入明确异常；
- 每个计分维度都有原文证据或明确缺失；
- 模型格式无效、证据不足、画像缺失时不继续评分；
- 同一输入、画像版本和规则版本产生一致评分；
- 成功状态为 HR_REVIEW_REQUIRED；
- 至少一个授权真实投递到筛选结果的路径已验证，或者明确记录未验证原因。

## 6. 工作包：HR 产品 UI 层

**负责人：新源**

### 6.1 Objective

交付一个清晰、可信、可完成任务的 HR 工作台 UI，让 HR 无需配置技术参数，即可完成“今日复核 → 候选人详情 → 原文证据 → 确认或纠错 → 提交回执”。

### 6.2 Inputs

- ReviewCandidate 固定样例；
- 列表、详情、原文和 HRReviewCommand API；
- 状态、推荐等级、维度证据、缺失和异常定义；
- 管理员与 HR 的身份边界；
- 合成候选人和脱敏页面数据。

### 6.3 Required UI deliverables

| 界面 | 必须回答的问题 | 必须操作 |
|---|---|---|
| 今日复核首页 | 今天有多少人需要处理，先看谁 | 查看队列、进入候选人 |
| 候选人列表 | 每个人的岗位、推荐等级、状态和更新时间是什么 | 搜索、筛选、排序、打开详情 |
| 候选人详情 | 为什么得到这个结果，缺什么，有什么冲突 | 展开维度、查看证据、定位原文 |
| 确认纠错 | HR 是否同意，改了什么，为什么改 | 确认、修改、填写原因、提交 |
| 管理员连接状态 | 飞书、模型和试点岗位是否可用 | 查看状态和处理指引 |

每个界面必须设计并可演示以下适用状态：

- 正常；
- 加载中；
- 空数据；
- 权限不足；
- 简历解析失败；
- 模型处理失败；
- revision 版本冲突；
- 提交中、提交成功和提交失败。

必须交付：

- 可运行或可点击 UI；
- 页面地图和组件清单；
- 固定脱敏演示数据；
- 关键页面截图或短录屏；
- UI 自动化或代表性用户路径测试；
- `UI_DECISIONS.md`；
- `RETURN_REPORT.md`。

### 6.4 Controlled creative space

新源拥有以下设计决定权，无需逐个组件请求批准：

- 页面布局、导航、视觉主题、字体、颜色、间距和密度；
- 卡片、表格、抽屉、分栏或其他组件形式；
- 信息层级、证据呈现、原文对照和数据可视化方式；
- 微交互、动效、快捷操作、提示文案和桌面端适配；
- 不改变主流程的辅助视图和体验优化提案。

先提交一版页面地图和视觉方向供项目负责人做一次边界评审；确认后，新源可在约束内自主完成细节。不要把每个视觉决定变成审批点。

所有重要取舍写入 `UI_DECISIONS.md`，至少记录：问题、选择、理由、影响页面和是否触及接口。触及接口或业务流程的想法只放入“提案”区，获得确认前不作为既定实现。

### 6.5 Hard constraints

- UI 只消费 ReviewCandidate，只通过 HRReviewCommand 提交人工结果；
- 页面展示服务端给出的分数、推荐等级、证据和状态；
- HR 与管理员界面分离，HR 页面不出现凭证、Scope、CLI 或模型参数；
- 每个结论都能看到证据或明确的“无证据/无法定位”；
- 自动淘汰、约面、外联、阶段推进和写回不是 V1 页面动作；
- 固定演示数据明确标注“本地合成”，不能伪装成真实飞书数据；
- 列表、详情、原文和提交使用同一 candidate_id 与 revision；
- UI 内不实现评分、模型调用、BOSS 自动化、飞书鉴权或服务端状态机。

### 6.6 Implementation order

1. 检查现有页面、组件、路由和样式，保留可复用资产；
2. 输出页面地图、组件清单和一版视觉方向，完成一次边界评审；
3. 使用固定 ReviewCandidate 样例打通今日复核、列表和详情；
4. 实现维度证据、缺失、冲突和原文定位；
5. 实现 HRReviewCommand 确认纠错、版本冲突、幂等反馈和提交回执；
6. 实现管理员连接状态并隔离 HR 身份；
7. 补齐所有适用的加载、空数据和异常状态；
8. 接入 SCREENING_AND_JD_ASSETS 的真实接口；
9. 完成代表性用户路径测试、截图或录屏、UI_DECISIONS.md 和 RETURN_REPORT.md。

### 6.7 Completion criteria

- HR 可以完成“今日复核 → 详情 → 原文证据 → 确认或纠错 → 提交回执”；
- 5 个必需界面及其适用状态都有可运行页面、测试或视觉证据；
- 原文证据能够定位，无法定位时有明确说明；
- 确认和纠错携带操作者、原因、revision 和 idempotency_key；
- 重复提交不会产生重复反馈，过期 revision 有明确提示；
- HR 与管理员角色边界在界面和测试中成立；
- 常用桌面宽度下关键内容没有遮挡、截断或横向溢出；
- 页面没有重新计算评分，也没有出现“AI 已决定”或 V1 外动作；
- UI_DECISIONS.md 区分“已实现决定”和“待确认提案”；
- RETURN_REPORT.md 列出页面、状态、验证证据、未验证项和接口变更提案。

## 7. 工作包：BOSS 自动打招呼与简历信息抓取 Spike

**负责人：周玮**

### 7.1 Objective

回答一个问题：在授权测试范围内，BOSS 自动打招呼、简历信息识别与抓取、下载并进入飞书招聘的路径是否可行？

### 7.2 Nature

本工作包是时间盒 Spike。目标是购买信息，不是交付生产代码。

所有代码、目录、页面和报告必须标注 SPIKE_ONLY。实验代码不得直接合入 SCREENING_AND_JD_ASSETS 或 UI_LAYER。

### 7.3 Inputs

- 授权测试账号；
- 测试岗位和允许操作范围；
- 少量授权或脱敏候选人样例；
- 预先约定的时间盒；
- 停止条件；
- 飞书测试环境或人工上传配合。

任一关键输入缺失时，不尝试规避权限或安全限制；记录为前置条件不足。

### 7.4 Questions

- B-01：登录态能否在授权测试环境中稳定保持？
- B-02：能否稳定检索岗位或候选人并自动打招呼、进入沟通路径？
- B-03：能否识别候选人简历是否可获取？
- B-04：能否获取并下载完整简历文件？
- B-05：下载的简历能否上传飞书并形成可读取记录？
- B-06：验证码、风控、频率、授权、稳定性和维护成本是否允许正式化？

### 7.5 Execution order

1. 记录授权账号、范围、样例、时间盒和停止条件；
2. 测试登录、会话保持、验证码和风控；
3. 测试检索、自动打招呼与必要的沟通路径；
4. 测试简历可获取状态识别；
5. 测试完整简历获取和下载；
6. 在授权范围内测试上传飞书；
7. 对 B-01 至 B-06 逐项记录证据；
8. 到达时间盒立即停止，输出结论。

### 7.6 Conclusion enum

- FEASIBLE：代表性路径可重复完成，正式化风险明确；
- CONDITIONALLY_FEASIBLE：依赖人工、验证码、特定账号、低频或其他条件；
- NOT_FEASIBLE：当前条件下不能作为可靠路径。

三种结论都可以完成 Spike。一次成功不等于 FEASIBLE，必须有代表性重复证据和限制说明。

### 7.7 Deliverables

- BossSpikeReport；
- 自动打招呼和简历信息抓取的测试记录；
- 最短可复现步骤；
- 截图、日志或脱敏样例证据索引；
- SPIKE_ONLY 原型及运行说明；
- 风险与停止条件；
- 正式化需要重新实现的功能清单；
- 推荐下一步：停止、补充条件或另立正式开发工作包。

### 7.8 Completion criteria

- B-01 至 B-06 每项都有 PASS、FAIL 或 BLOCKED 及证据；
- 输出三选一结论；
- 到达时间盒后停止实验；
- 不宣称生产稳定；
- 不直接写招聘助手数据库；
- 自动或人工路径获得的简历都先进入飞书招聘；
- Spike 代码没有合入正式 V1。

## 8. 共享接口

以下结构定义跨工作包语义。实现语言可以变化，字段含义不能静默变化。变更前先更新样例和 schema_version，再通知消费者。

### 8.1 CandidateSnapshot：飞书接入方 → SCREENING_AND_JD_ASSETS

~~~json
{
  "schema_version": "1.0",
  "tenant_id": "tenant-ref",
  "source_system": "feishu_hire",
  "original_channel": "website_or_uploaded_or_unknown",
  "job": {
    "id": "job-id",
    "title": "job-title"
  },
  "application": {
    "id": "application-id",
    "updated_at": "2026-08-21T00:00:00Z"
  },
  "talent": {
    "id": "talent-id"
  },
  "resume": {
    "attachment_id": "attachment-id",
    "filename": "resume.pdf",
    "mime_type": "application/pdf",
    "content_sha256": "sha256",
    "acquired_at": "2026-08-21T00:00:00Z"
  }
}
~~~

Required：schema_version、tenant_id、source_system、job.id、application.id、talent.id、resume.attachment_id、resume.content_sha256、application.updated_at。

### 8.2 ReviewCandidate：SCREENING_AND_JD_ASSETS → UI_LAYER

~~~json
{
  "schema_version": "1.0",
  "candidate_id": "candidate-id",
  "revision": 1,
  "status": "HR_REVIEW_REQUIRED",
  "job_id": "job-id",
  "profile_version": "profile-v1",
  "rule_version": "rule-v1",
  "total_score": 78,
  "recommendation": "MEDIUM_MATCH",
  "dimensions": [],
  "missing_fields": [],
  "conflicts": [],
  "resume_pointer": {
    "attachment_id": "attachment-id"
  }
}
~~~

每个 dimensions 项必须包含维度名、分值、事实、原文片段、位置或无法定位原因。

### 8.3 HRReviewCommand：UI_LAYER → SCREENING_AND_JD_ASSETS

~~~json
{
  "schema_version": "1.0",
  "candidate_id": "candidate-id",
  "revision": 1,
  "action": "CONFIRM_OR_CORRECT",
  "corrections": [],
  "reason": "human-readable reason",
  "operator_id": "hr-user-id",
  "idempotency_key": "unique-key"
}
~~~

服务端必须校验 revision、operator_id 和 idempotency_key。

### 8.4 BossSpikeReport：周玮 → 项目负责人

~~~json
{
  "schema_version": "1.0",
  "question": "BOSS resume acquisition to Feishu feasibility",
  "timebox": "declared-before-start",
  "tests": [
    {
      "id": "B-01",
      "status": "PASS_OR_FAIL_OR_BLOCKED",
      "evidence": []
    }
  ],
  "conclusion": "FEASIBLE_OR_CONDITIONALLY_FEASIBLE_OR_NOT_FEASIBLE",
  "conditions": [],
  "risks": [],
  "recommended_next_step": "STOP_OR_MORE_SPIKE_OR_FORMAL_PROJECT"
}
~~~

## 9. 正式状态机

Allowed transitions：

~~~text
DISCOVERED → SYNCING
SYNCING → PARSING | EXCEPTION
PARSING → SCREENING | EXCEPTION
SCREENING → HR_REVIEW_REQUIRED | EXCEPTION
HR_REVIEW_REQUIRED → HR_REVIEWED
EXCEPTION → 原失败步骤（仅在安全重试后）
~~~

Forbidden projections：

- SCREENING → REJECTED；
- SCREENING → INTERVIEW；
- SCREENING → OFFER；
- HR_REVIEW_REQUIRED 被描述为招聘决定。

## 10. 验证矩阵

| 范围 | 必须验证 | 不能替代什么 |
|---|---|---|
| 合成契约 | 四个共享结构可校验、可消费 | 不能证明真实飞书可用 |
| 单元测试 | 去重、规则评分、状态、幂等、版本冲突 | 不能证明页面路径可用 |
| UI 路径 | 列表 → 详情 → 原文 → 确认/纠错 | 不能证明真实模型或飞书可用 |
| 真实飞书 | 指定岗位、投递、人才、附件读取 | 不能用 Token 存在代替读取成功 |
| 企业模型 | 授权样例产生合规 EvidencePackage | 不能用 Mock 代替真实调用 |
| BOSS Spike | B-01 至 B-06 的证据和三选一结论 | 不能证明生产稳定 |

## 11. AI Native 兼容约束

当前模块需要能够在未来被 Agent 当作工具调用，但 V1 不建设通用 Agent 平台。

每个正式工具必须具备：

- 明确输入和结构化输出；
- 幂等键或可重复执行语义；
- 超时、失败和重试状态；
- 数据来源和版本；
- 审计事件；
- 人工确认点。

未来 Agent 可以编排同步、解析、证据和评分工具，但必须保留飞书事实源、确定性规则和 HR 人工闸门。

BOSS 能力只有在 BOSS_AUTOMATION_SPIKE 结论通过、另立正式工作包并完成生产验收后，才能注册为 Agent 工具。

## 12. RETURN_REPORT.md 模板

~~~markdown
# Return Report

## Assignment
- WORK_PACKAGE:
- WORKSPACE_ROOT:
- BASELINE:

## Delivered
- 文件或功能：
- 对应完成条件：

## Changed contracts
- schema_version:
- 兼容性影响：

## Validation evidence
- 命令：
- 结果：
- 页面路径：
- 外部系统证据：

## Not verified
- 未验证项：
- 原因：

## Risks and limits
- 风险：
- 不得宣称：

## Handoff
- 下一位需要接收什么：
- 如何复现：
- 剩余工作：
~~~

## 13. 推荐启动提示词

### 启动简历筛选与 JD 画像工作包

~~~text
读取 招聘助手V1_AI执行契约.md 并执行 WORK_PACKAGE=SCREENING_AND_JD_ASSETS。
WORKSPACE_ROOT=<路径>，BASELINE=<提交或版本>。
你负责简历自动化筛选评估和 JD 画像资产。先检查现状，再实现代表性筛选路径并按契约验证。飞书 API 接入不在本工作包内，使用约定的 CandidateSnapshot。完成后生成 RETURN_REPORT.md。
~~~

### 启动新源的 UI 工作包

~~~text
读取 招聘助手V1_AI执行契约.md 并执行 WORK_PACKAGE=UI_LAYER。
WORKSPACE_ROOT=<路径>，BASELINE=<提交或版本>。
负责人是新源。只完成 UI 层：先检查现有界面，输出页面地图和一版视觉方向，再使用固定 ReviewCandidate 打通“今日复核 → 详情 → 原文证据 → 确认或纠错 → 提交回执”。你可以自主决定布局、视觉、组件和微交互，但必须保持 ReviewCandidate、HRReviewCommand、角色权限和 HR 人工决策边界。接口或流程改变只写入 UI_DECISIONS.md 的提案区。完成后提交页面证据、测试、UI_DECISIONS.md 和 RETURN_REPORT.md。
~~~

### 启动周玮的 BOSS 自动化测试工作包

~~~text
读取 招聘助手V1_AI执行契约.md 并执行 WORK_PACKAGE=BOSS_AUTOMATION_SPIKE。
WORKSPACE_ROOT=<路径>，BASELINE=<提交或版本>，TIMEBOX=<时间盒>。
负责人是周玮。这是 SPIKE_ONLY，只测试自动打招呼、简历信息抓取和进入飞书，并回答 B-01 至 B-06。不要修改正式 V1 代码，不要绕过授权或风控边界。到达时间盒停止并生成 BossSpikeReport 与 RETURN_REPORT.md。
~~~
