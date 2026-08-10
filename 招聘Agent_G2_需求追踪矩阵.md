# 招聘 Agent G2 需求追踪矩阵

> 版本：v0.1  
> 日期：2026-08-10  
> 基线：[G2 从收件到可信面试交接 PRD](./招聘Agent_G2_收件筛选约面_PRD.md)  
> 口径：SPEC 只表示产品模块、命令/事件、目标测试与证据槽已对应；当前没有实现、真实账号、真人验收或发布证据。

## 1. 状态规则

| 状态 | 含义 |
|---|---|
| UNMAPPED | 尚未绑定产品模块、命令/事件或测试 |
| SPEC | 产品行为、负面场景和目标证据槽齐全 |
| IMPLEMENTED | 实现与契约/行为测试通过，尚未完成人真验证 |
| VERIFIED | 目标环境、真人流程、故障/权利演练和 Owner 验收齐全 |
| RELEASED | 对应动作通过离线/A0/A1/A2/A3 放权与回滚门 |

证据 ID 是未来实现仓库、CI 和试点产生的占位符，不是现有证据。

## 2. FR-201..264

| ID | 产品要求（压缩表述） | 产品模块 / 关键命令或事件 | 目标测试 | 证据槽 | 当前 |
|---|---|---|---|---|---|
| FR-201 | 只接入批准来源并保存来源/目的 | 投递收件箱 / RegisterResumeSubmission | G2-INTAKE-201：非白名单来源隔离 | EV-G2-FR201 | SPEC |
| FR-202 | 来源/消息/附件/内容幂等与关联 | ResumeSubmission / ResumeSubmissionReceived | G2-INTAKE-202：重复消息与同键异载 | EV-G2-FR202 | SPEC |
| FR-203 | 附件安全与完整性先于解析 | Attachment Gate | G2-INTAKE-203：坏文件/恶意/加密矩阵 | EV-G2-FR203 | SPEC |
| FR-204 | 原件与结构化简历不可变版本化 | Structured Resume / RecordStructuredResumeVersion | G2-INTAKE-204：重解析/纠正不覆盖 | EV-G2-FR204 | SPEC |
| FR-205 | 多附件逐件分类，不混候选人 | Submission Splitter | G2-INTAKE-205：一信多人/材料歧义 | EV-G2-FR205 | SPEC |
| FR-206 | 转发/重复附件/ATS 回调不重复开案 | Intake Dedup / ResumeSubmissionAttachedToCase | G2-INTAKE-206：十次重放一个效果 | EV-G2-FR206 | SPEC |
| FR-207 | 材料内提示不触发工具/状态/权限 | Untrusted Content Boundary | G2-INTAKE-207：简历 prompt injection 红队 | EV-G2-FR207 | SPEC |
| FR-208 | 解析失败/非申请有依据、SLA 和恢复 | Intake Exception / ExceptionBundle | G2-INTAKE-208：失败不丢弃/不无限重试 | EV-G2-FR208 | SPEC |
| FR-209 | 字段保存 locator、版本和置信信号 | Structured Resume / field manifest | G2-ROUTE-209：逐字段来源与低置信 | EV-G2-FR209 | SPEC |
| FR-210 | 敏感/保护/代理字段与匹配隔离 | Field Policy Gate | G2-ROUTE-210：字段访问与用途例外 | EV-G2-FR210 | SPEC |
| FR-211 | 联系方式/姓名只作身份信号 | Identity Resolver | G2-ROUTE-211：共享邮箱/复用手机号 | EV-G2-FR211 | SPEC |
| FR-212 | 身份合并拆分须人权责与审计 | Identity Correction / routing supersede | G2-ROUTE-212：冲突不自动合并 | EV-G2-FR212 | SPEC |
| FR-213 | 岗位与招聘周期唯一且可处理 | Application Routing | G2-ROUTE-213：关闭/未知/多候选岗位 | EV-G2-FR213 | SPEC |
| FR-214 | 自动路由要求唯一且无冲突 | ResolveApplicationRouting | G2-ROUTE-214：分数不等于路由事实 | EV-G2-FR214 | SPEC |
| FR-215 | 任一不唯一不得开半个案件 | Routing Review / ReviewRequired | G2-ROUTE-215：缺人/岗位/周期阻断 | EV-G2-FR215 | SPEC |
| FR-216 | 开案要求完整键、version/epoch/幂等 | OpenOrAttachApplicationCase | G2-ROUTE-216：ROUTED-only 命令门 | EV-G2-FR216 | SPEC |
| FR-217 | 同键附加；改键纠正先失效旧关系/动作且不搬历史 | SupersedeApplicationRouting / SupersedeSubmissionCaseLink | G2-ROUTE-217：已开案改键纠正与补偿范围 | EV-G2-FR217 | SPEC |
| FR-218 | 同人多岗/周期案件严格隔离 | ApplicationCase / DataScope | G2-ROUTE-218：跨案引用与外发隔离 | EV-G2-FR218 | SPEC |
| FR-219 | 筛选前有当前简历和批准画像 | Screening Gate / PinScreeningInput | G2-MATCH-219：输入缺失不生成空分 | EV-G2-FR219 | SPEC |
| FR-220 | 筛选输入清单钉住全部版本 | ScreeningInputManifest | G2-MATCH-220：重放与输入变化 | EV-G2-FR220 | SPEC |
| FR-221 | 每个标准区分支持/反证/未知/不适用 | Match Assessment | G2-MATCH-221：四态完整性 | EV-G2-FR221 | SPEC |
| FR-222 | 必要条件/低分不能自动淘汰 | Match Gate / NO-AUTO-REJECT | G2-MATCH-222：score→state 全拒绝 | EV-G2-FR222 | SPEC |
| FR-223 | 关键匹配 claim 可定位到证据 | Evidence Validator | G2-MATCH-223：无 locator/反证阻断 | EV-G2-FR223 | SPEC |
| FR-224 | 不用常识补写候选人未知事实 | Claim Validator | G2-MATCH-224：未知保持未知 | EV-G2-FR224 | SPEC |
| FR-225 | 禁用/代理/注入污染阻断结论 | Fairness Policy Gate | G2-MATCH-225：代理变量红队 | EV-G2-FR225 | SPEC |
| FR-226 | 发布门校验维度/证据/版本/禁止字段 | PublishMatchAssessment | G2-MATCH-226：逐门缺失矩阵 | EV-G2-FR226 | SPEC |
| FR-227 | 匹配材料不可变且 Case 只有一个当前指针 | MatchAssessment / InvalidateCurrentMatchAssessment | G2-MATCH-227：重跑原子失效旧任务 | EV-G2-FR227 | SPEC |
| FR-228 | result band 不作排名/决定/外发标签 | Match Schema + Publish Gate | G2-MATCH-228：排名/决定字段三层阻断 | EV-G2-FR228 | SPEC |
| FR-229 | 原子钉住当前材料、迁移阶段并创建一个权威任务 | OpenDepartmentDecisionRequest | G2-DEPT-229：无“有阶段无任务”窗口 | EV-G2-FR229 | SPEC |
| FR-230 | 决策卡展示证据/未知/版本而非人格分 | Department Review UI | G2-DEPT-230：字段/证据 UI 快照 | EV-G2-FR230 | SPEC |
| FR-231 | 外部通知最小，产品任务权威 | Notification + ActionExecution | G2-DEPT-231：安全深链/错误收件人 | EV-G2-FR231 | SPEC |
| FR-232 | INVITE/HOLD/REJECT 只由授权 HUMAN 提交 | RecordDepartmentDecision | G2-DEPT-232：Agent/Service/越权 actor 拒绝 | EV-G2-FR232 | SPEC |
| FR-233 | INVITE/REJECT 迁移与拒信外发分离 | ApplicationCase / DecisionRecord | G2-DEPT-233：决定与沟通独立回执 | EV-G2-FR233 | SPEC |
| FR-234 | HOLD→ON_HOLD 新修订，revisit 后只恢复 OPEN 人审 | RecordDepartmentDecision / ResumeDepartmentDecisionRequest | G2-DEPT-234：HOLD 停催办/到期单一恢复 | EV-G2-FR234 | SPEC |
| FR-235 | 材料失效原子回 SCREENING；旧卡/权限不能写当前 | InvalidateCurrentMatchAssessment / Currentness Gate | G2-DEPT-235：失效与旧卡双击竞态 | EV-G2-FR235 | SPEC |
| FR-236 | 催办有静默时段、ordinal、上限和升级 | Reminder Orchestrator | G2-DEPT-236：阶段变化/耗尽/幂等 | EV-G2-FR236 | SPEC |
| FR-237 | 只有当前已激活轮次/会话可约面 | Scheduling Gate / OpenCoordination | G2-SCHED-237：无 INVITE/未激活阻断 | EV-G2-FR237 | SPEC |
| FR-238 | 日历只读授权忙闲，不泄露正文 | Availability Port | G2-SCHED-238：字段最小化/授权撤销 | EV-G2-FR238 | SPEC |
| FR-239 | 时段提案有约束/快照/版本/有效期 | SchedulingProposal | G2-SCHED-239：过期/输入变化失效 | EV-G2-FR239 | SPEC |
| FR-240 | 协调入口限时/案件/用途/修订 | Coordination Token Gate | G2-SCHED-240：错人/重放/旧链接 | EV-G2-FR240 | SPEC |
| FR-241 | 选时携带当前版本和唯一 action | RecordCandidateSlotSelection | G2-SCHED-241：同提案合法改选 | EV-G2-FR241 | SPEC |
| FR-242 | 预约修订前重读忙闲/参与人/控制 | ProposeAppointmentRevision | G2-SCHED-242：选后冲突与控制竞态 | EV-G2-FR242 | SPEC |
| FR-243 | 提案/选择非预定，回执齐才 Booking | CommitBooking / BookingReceiptSet | G2-SCHED-243：部分成功不 SCHEDULED | EV-G2-FR243 | SPEC |
| FR-244 | 所有预约外部写走 ActionExecution | ActionExecution + ConnectorPort | G2-SCHED-244：丢响应/重放/同键异载 | EV-G2-FR244 | SPEC |
| FR-245 | 邀请字段完整，资源写回执与送达分离 | Invitation Writer | G2-SCHED-245：内容/回执分类 | EV-G2-FR245 | SPEC |
| FR-246 | 改期新修订；新提交前旧预定有效 | RequestReschedule / CommitBooking | G2-SCHED-246：改期失败/旧回调 | EV-G2-FR246 | SPEC |
| FR-247 | 控制态阻断生产动作并允许安全补偿 | CommitBookingCancellation | G2-SCHED-247：关闭后取消/撤链 | EV-G2-FR247 | SPEC |
| FR-248 | 改期/提案/替人尝试有限，耗尽异常 | Scheduling Exception | G2-SCHED-248：上限与决策包 | EV-G2-FR248 | SPEC |
| FR-249 | 录制告知内容完整且版本化 | Recording Notice | G2-CAPTURE-249：文案字段/送达版本 | EV-G2-FR249 | SPEC |
| FR-250 | 选择按参与人/会话/目的/告知取得 | Consent Receipt | G2-CAPTURE-250：跨人/会话/目的复用拒绝 | EV-G2-FR250 | SPEC |
| FR-251 | 选择凭证保存全字段并幂等 | RecordParticipantRecordingChoice | G2-CAPTURE-251：同载重放/同键异载 | EV-G2-FR251 | SPEC |
| FR-252 | 拒绝录制有等价无录制路线且非评价信号 | No-recording Route | G2-CAPTURE-252：数据血缘与体验等价 | EV-G2-FR252 | SPEC |
| FR-253 | 全部在场且媒体可能进入采集的参与人过门 | Capture Gate / Presence | G2-CAPTURE-253：晚加入与媒体入口组合矩阵 | EV-G2-FR253 | SPEC |
| FR-254 | 面试、闸门、采集请求和平台确认分离 | StartInterview / RequestCaptureStart / ConfirmCaptureStarted | G2-CAPTURE-254：旧快照/迟到开始确认 | EV-G2-FR254 | SPEC |
| FR-255 | 晚加入/转发不继承选择 | Presence + CaptureGateEvaluated | G2-CAPTURE-255：晚加入暂停采集 | EV-G2-FR255 | SPEC |
| FR-256 | 撤回/作用域控制立即隔离并请求停止，确认后才 STOPPED | RequestCaptureStop + ProcessingControl | G2-CAPTURE-256：会中撤回/范围/停止确认 | EV-G2-FR256 | SPEC |
| FR-257 | 请求、平台观察、确认持续对账 | Capture Reconciler / MarkCaptureStateMismatch | G2-CAPTURE-257：意外录制/无法确认停止 P0 | EV-G2-FR257 | SPEC |
| FR-258 | Session 结束且采集/片段/最终对账结算后才有一个当前不可变交接；双路线互斥且 capture history 诚实 | Create/InvalidateInterviewEvidenceHandoff | G2-HANDOFF-258：未结算硬拒绝/资产 checksum/授权笔记/采集历史/失效 | EV-G2-FR258 | SPEC |
| FR-259 | LLM 不写状态或调用外部工具 | Deterministic Control Plane | G2-CONTROL-259：模型/简历注入零效果 | EV-G2-FR259 | SPEC |
| FR-260 | A0–A3 按动作授权，决定永久人审 | Action Policy | G2-CONTROL-260：动作等级不扩散 | EV-G2-FR260 | SPEC |
| FR-261 | 控制事实优先并钉住 control set、路由和目标修订 | Processing Control + Preflight | G2-CONTROL-261：Pause/Delete/Route/Close 竞态 | EV-G2-FR261 | SPEC |
| FR-262 | 重试/频控/预算/对账有限，耗尽异常 | Runtime + ExceptionBundle | G2-CONTROL-262：重试预算与单一异常 | EV-G2-FR262 | SPEC |
| FR-263 | 全链路权限、作用域控制、审计、最小化和删除传播 | Privacy/Audit Orchestrator | G2-CONTROL-263：主体/案件/目的/操作/血缘 | EV-G2-FR263 | SPEC |
| FR-264 | G1 交接幂等可失效；单命令单聚合；页面只投影 | Handoff invalidation + Cross-aggregate seam | G2-HANDOFF-264：旧交接/迟到 Accepted/跨聚合写 | EV-G2-FR264 | SPEC |

## 3. AT-201..228

| ID | 场景 / 关键断言 | 主要覆盖 FR | 自动化层 | 证据槽 | 当前 |
|---|---|---|---|---|---|
| AT-201 | 邮件转发+ATS 同份申请重复到达，只有一个业务效果/案件 | FR-201、FR-202、FR-206、FR-216、FR-217 | intake/idempotency | EV-G2-AT201 | SPEC |
| AT-202 | 共享邮箱/复用手机号或路由候选歧义，不自动合并/开案 | FR-211、FR-212、FR-213、FR-214、FR-215 | identity/routing | EV-G2-AT202 | SPEC |
| AT-203 | 同人两岗及已开案改键纠正：旧关系先失效，不改键/搬历史 | FR-216、FR-217、FR-218、FR-261 | routing correction/data isolation | EV-G2-AT203 | SPEC |
| AT-204 | 坏附件/多候选人材料/低质解析停在 Submission | FR-203、FR-205、FR-208、FR-209 | file/parser fault | EV-G2-AT204 | SPEC |
| AT-205 | 简历提示注入不能触发工具/状态/外发/取数 | FR-207、FR-225、FR-259 | prompt/security red-team | EV-G2-AT205 | SPEC |
| AT-206 | 简历/画像变化使指针/任务原子失效回 SCREENING，再原子开新任务 | FR-204、FR-217、FR-219、FR-220、FR-227、FR-229、FR-235 | version/aggregate transaction | EV-G2-AT206 | SPEC |
| AT-207 | 低匹配/证据不足仍由人审，不自动关闭或拒信 | FR-221、FR-222、FR-223、FR-224、FR-226、FR-228、FR-230、FR-232、FR-233 | match/decision safety | EV-G2-AT207 | SPEC |
| AT-208 | 敏感/代理变量进入匹配时阻断和分层复核 | FR-210、FR-225、FR-226、FR-263 | fairness/privacy red-team | EV-G2-AT208 | SPEC |
| AT-209 | Agent/Service 提交 INVITE/HOLD/REJECT 被拒绝 | FR-232、FR-233、FR-234、FR-260 | authority/API | EV-G2-AT209 | SPEC |
| AT-210 | 双击/旧卡不重复决定；INVITE/REJECT 关闭请求，HOLD 生成 ON_HOLD revision | FR-227、FR-229、FR-230、FR-231、FR-234、FR-235 | auth/request lifecycle | EV-G2-AT210 | SPEC |
| AT-211 | 决定/ON_HOLD/暂停/静默后的催办被抑制，HOLD 到期只恢复一个 OPEN revision | FR-234、FR-236、FR-261、FR-262 | timer/request race | EV-G2-AT211 | SPEC |
| AT-212 | Owner 缺失或重试耗尽只形成一个异常包 | FR-229、FR-231、FR-236、FR-248、FR-262 | retry/exception | EV-G2-AT212 | SPEC |
| AT-213 | 错误或跨租户收件人在外发前 P0 阻断 | FR-231、FR-244、FR-245、FR-263 | recipient/security | EV-G2-AT213 | SPEC |
| AT-214 | 多 Session 同轮：首场开始令 Round 进入 IN_PROGRESS，剩余会话继续约面且不回退 | FR-237、FR-238、FR-239、FR-240、FR-241、FR-242、FR-243、FR-244、FR-245 | multi-session scheduling/start E2E | EV-G2-AT214 | SPEC |
| AT-215 | 过期提案或忙闲变化不建会，重新提案 | FR-239、FR-241、FR-242、FR-243 | scheduling/currentness | EV-G2-AT215 | SPEC |
| AT-216 | 并发抢同一时段至多一个当前 Booking | FR-242、FR-243、FR-244 | concurrency/provider mock | EV-G2-AT216 | SPEC |
| AT-217 | Provider 成功但响应丢失/重复回调，不重复会议邀请 | FR-243、FR-244、FR-245、FR-246 | connector fault injection | EV-G2-AT217 | SPEC |
| AT-218 | 改期后旧回调迟到，只认当前修订并补偿 | FR-246、FR-247、FR-261 | revision/race | EV-G2-AT218 | SPEC |
| AT-219 | 候选人撤回/Case 关闭时队列动作阻断并补偿 | FR-244、FR-247、FR-261、FR-262 | control/compensation | EV-G2-AT219 | SPEC |
| AT-220 | 日历失权/Provider 故障不伪造忙闲或 Booking | FR-238、FR-242、FR-243、FR-248、FR-262 | connector outage | EV-G2-AT220 | SPEC |
| AT-221 | 告知但无 ConsentReceipt：RequestCaptureStart 拒绝，面试无录制继续 | FR-249、FR-250、FR-251、FR-253、FR-254 | consent/request gate | EV-G2-AT221 | SPEC |
| AT-222 | 任一媒体可入平台参与人拒绝：NO_RECORDING，可形成授权笔记路线且非评价信号 | FR-249、FR-250、FR-252、FR-253、FR-258 | no-recording E2E | EV-G2-AT222 | SPEC |
| AT-223 | 晚加入先 RequestCaptureStop；当前回执后才 STOPPED/重新过门 | FR-250、FR-253、FR-254、FR-255、FR-257 | presence/capture confirmation race | EV-G2-AT223 | SPEC |
| AT-224 | 会中撤回按 session/purpose 隔离、请求停止；未确认时保持 P0 | FR-251、FR-254、FR-256、FR-257、FR-261、FR-263 | scoped privacy/fault injection | EV-G2-AT224 | SPEC |
| AT-225 | 参与人/目的/告知/会话/control set/version 不匹配时闸门拒绝 | FR-249、FR-250、FR-251、FR-253、FR-254、FR-261 | consent/control property | EV-G2-AT225 | SPEC |
| AT-226 | 控制竞态范围正确；Session/采集未结算不能建 Handoff；失效后迟到 Confirm/Accepted 不复活 | FR-244、FR-247、FR-256、FR-258、FR-261、FR-262、FR-263、FR-264 | concurrency/control/handoff settlement/invalidation | EV-G2-AT226 | SPEC |
| AT-227 | 协调链接错人/重放/旧 revision 不改时段或选择 | FR-240、FR-241、FR-250、FR-251 | auth/token security | EV-G2-AT227 | SPEC |
| AT-228 | 两条 evidence_route 参数化正常链：含从未采集/撤回后仅笔记历史，零 HR 点火、零 Agent 决定、唯一预定/交接 | FR-201、FR-209、FR-213、FR-216、FR-219、FR-220、FR-226、FR-229、FR-232、FR-233、FR-237、FR-239、FR-243、FR-245、FR-249、FR-252、FR-253、FR-258、FR-259、FR-260、FR-264 | synthetic dual-route and capture-history E2E | EV-G2-AT228 | SPEC |

## 4. 横向发布门

| 套件 | 断言 | 证据槽 |
|---|---|---|
| G2-X-AUTHORITY | Agent/Service 无法提交部门/轮次/最终招聘决定或绕过动作策略 | EV-G2-X01 |
| G2-X-IDENTITY-ISOLATION | 重复投递、身份纠正、同人多岗/周期和跨案读取/外发保持隔离 | EV-G2-X02 |
| G2-X-NO-AUTO-REJECT | 低分、必要条件、超时、模型字段和规则均不能自动关闭或发拒信 | EV-G2-X03 |
| G2-X-RECIPIENT-SAFETY | 产品任务、候选人协调、部门卡片和邀请均重验当前受众/权限/深链 | EV-G2-X04 |
| G2-X-BOOKING-EXACTLY-ONCE | 内部只有一个当前 Booking；部分成功/丢响应/迟到回调可对账补偿 | EV-G2-X05 |
| G2-X-CONSENT-CAPTURE | 告知≠选择；晚加入、拒绝、撤回、无录制和平台状态均受运行闸门控制 | EV-G2-X06 |
| G2-X-CONTROL-RACE | lifecycle/control/target/policy/payload 每次重验，生产动作与安全补偿正确分类 | EV-G2-X07 |
| G2-X-MINIMIZATION-ROLLBACK | 日志/事件最小化，字段/目的/保留/删除传播和按动作回滚可证明 | EV-G2-X08 |

## 5. 覆盖快照

| 项 | 基线 | 已映射 | 已实现 | 已验证 | 已发布 |
|---|---:|---:|---:|---:|---:|
| FR | 64 | 64 | 0 | 0 | 0 |
| AT | 28 | 28 | 0 | 0 | 0 |

当前 PRD、领域规格和矩阵只能支持 SPEC 状态。文档 lint、合成原型或 GitHub 提交都不能把任何条目标记为 IMPLEMENTED、VERIFIED 或 RELEASED。
