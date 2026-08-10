# 招聘 Agent G1b 产品规格验收记录

> 验收时间：2026-08-10 16:05（Asia/Singapore）  
> 验收对象：G1b 领域语言、关键 ADR、PRD、领域规格、需求追踪和组合看板  
> 结论：**文档结构与领域一致性验收通过；工程、真人、模型、合规和发布验证尚未开始。**
> 2026-08-10 18:04 登记规格 CI 证据后已重跑回归并更新当前文件指纹。

## 1. 本次验收证明什么

- PRD 的 FR-101..140 与 AT-101..118 连续、无重复，并在追踪矩阵一一出现。
- G1b 的八个关键业务词已进入权威 `CONTEXT.md`，不是 PRD 私有术语。
- 终面包不可变编译、面前简报分阶段披露已形成 accepted ADR。
- 领域规格包含 InterviewBrief、CrossRoundIssue、FinalAssessmentPackage 及对应命令、事件、状态门和失效规则。
- ApplicationCase 仍严格只有六个顶层阶段；终面评估就绪与最终招聘决定保持分离。
- 组合看板和 Gate 0 已登记 G1b 规格，同时继续明确真实数据、A0/A1 和外部写入 No-go。
- 现有控制塔原型的正常两轮链被限定为 AT-101 的部分合成逻辑证据，没有外推到其他 17 个场景。

## 2. 本次验收不证明什么

- 不证明任何 FR 已实现，也没有 G1b 命令/API/事件 Schema、数据库或 CI。
- 不证明多轮依赖、重复轮次、豁免、问题分类、包失效、旧链接或通知故障在运行时正确。
- 不证明面前简报能降低重复提问或锚定偏差，也没有面试官/最终决策人实际使用记录。
- 不证明模型问题质量、汇总准确率、公平性、隐私合法性或真实样本路径。
- 不证明 A0/A1/A2、可信托管完成率、时效、成本或商业价值。

## 3. 可重复命令

```bash
python3 contracts/lint_g1b_spec.py
```

## 4. 最终结果

| 检查 | 结果 | 数量 / 说明 |
|---|---|---|
| PRD ↔ 矩阵 FR | PASS | 40/40 |
| PRD ↔ 矩阵 AT | PASS | 18/18 |
| G1b 权威领域词 | PASS | 8 个 |
| ADR 编号与状态 | PASS | 0001..0008 连续；G1b 的 0005/0006 accepted |
| G1b 聚合 | PASS | 3 个核心新增/强化聚合 |
| G1b 命令 | PASS | 11 个关键命令存在于领域规格 |
| G1b 事件 | PASS | 13 个关键事件存在于领域规格 |
| ApplicationCase 阶段 | PASS | 仍为 6 个且顺序一致 |
| 就绪与人类最终决定分离 | PASS | 4 项文本/命令不变量 |
| 原型证据边界 | PASS | 正常两轮链存在；17 个场景未被冒充验证 |
| 本地 Markdown 链接 | PASS | 42 个，全部位于仓库内且存在 |
| No-go 声明 | PASS | PRD、推进看板、Gate 0 三处保留 |
| 组合计划同步 | PASS | 总方案、看板、Gate 0 均登记 G1b |

## 5. 文件指纹

| 文件 | SHA-256 |
|---|---|
| `CONTEXT.md` | `926659c27dd9149956dedf3782aa491a111208e0810e70fde2d68696d438018f` |
| `docs/adr/0005-final-assessment-package-is-an-immutable-compilation.md` | `fe0f8f83371f41467d7215293c958bdecca10c86257b35ce2e7918fe267a0561` |
| `docs/adr/0006-interview-brief-uses-staged-disclosure.md` | `c74253ba22d597ca64d741ad9e1581ea39fd7b42ccec48c70138dfc0381c84ad` |
| `招聘Agent_G1b_终面评估包_PRD.md` | `715dabe13d70005464bb8628c22e5c466eb3da4625ac1ff94d93b42baa68e294` |
| `招聘Agent_领域与事件规格.md` | `47b282ed9c34b702a512eef7ffaaa6c3b6cd33a649aa642733062e5c0a69e9da` |
| `招聘Agent_G1b_需求追踪矩阵.md` | `cd20ea22e7ad1ace791cd3667a5d5344c3cffb95856415604bc5d61f747cb1a8` |
| `招聘Agent产品落地总方案.md` | `cdc37768a6cdc22d18b5c58dd3ed84234df30cdc83145a66e1e5ddfe7a0c7e2d` |
| `招聘Agent推进看板.md` | `6afbaa72b0ba8c6f4de4f6a860c498d22d4ae455284d9eb24a59fe277cc4a30c` |
| `招聘Agent_Gate0执行包.md` | `f8fb76a985ec6fe877f60350d497cf883bdb8f04aedd0ac6fe115a1f8e0cb869` |
| `contracts/lint_g1b_spec.py` | `f3a2e79f81b3e8892dc42751c65c63ba08b36cb9d805f7aaf030b1dc7ffa8d1d` |
| `docs/招聘Agent_G1b产品规格实施计划.md` | `5a389b6ad2df700932784826aef7ecfff1932c27ad98a25694f54ebfd1344478` |

这些 hash 固定本次评审对象；后续修改需要重跑 lint 并更新记录。

## 6. 下一证据门

1. 形成 G1b 命令/事件 Schema、工程 Backlog 与技术评审记录。
2. 扩展合成逻辑原型，至少覆盖并行依赖、重复轮次、豁免、阻断/非阻断问题、包失效、旧链接和通知失败。
3. 由招聘运营、面试官、最终招聘决策人和隐私/公平 Owner 评审分阶段披露字段与异常处置。
4. 在合法样本上建立简报问题质量、汇总证据准确、问题漏报、锚定/披露和成本基线。

在这些证据出现前，G1b 只能标为 `SPEC`，不能标为 `IMPLEMENTED`、`VERIFIED` 或 `RELEASED`。
