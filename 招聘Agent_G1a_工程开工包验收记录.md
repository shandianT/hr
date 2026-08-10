# 招聘 Agent G1a 工程开工包验收记录

> 验收时间：2026-08-10 15:50（Asia/Singapore）  
> 验收对象：产品工程规格、机器契约、需求追踪与看板同步  
> 结论：**结构验收通过；完整 JSON Schema 2020-12 语义验证待实现仓库 CI。真实实现与发布仍为 No-go。**
> 2026-08-10 17:57：G2 v0.2 语义终审后已重跑 G1a lint，并刷新组合文档指纹；19 命令/24 事件机器契约本身未扩展。

## 1. 验收范围

本次只检查：

- JSON 文件语法、本地 `$ref`、命令/事件枚举与 payload 分支一一覆盖。
- command/event payload 是否为关闭对象，避免未知字段静默穿透。
- 控制/事件契约中的聚合枚举、错误码和事件内容最小化约束。
- PRD 的 FR-001..032、AT-001..015 是否在追踪矩阵完整且不重复。
- 追踪矩阵引用的 Backlog ID 是否存在、主要 Markdown 本地链接是否可打开。
- 推进看板与 Gate 0 是否仍明确标注真实数据、A0/A1 和外部写入 No-go。

本次不检查：代码实现、数据库事务、并发行为、连接器回执、模型质量、真实数据合法性、用户采用、A0/A1 或生产 SLO。

## 2. 可重复命令

```bash
jq empty contracts/recruiting-agent-g1a-control.schema.json
jq empty contracts/recruiting-agent-g1a-event.schema.json
python3 contracts/lint_contracts.py
```

## 3. 结果

| 检查 | 结果 | 数量 / 说明 |
|---|---|---|
| 两份 JSON 语法 | PASS | `jq empty` 均退出 0 |
| Control 本地 `$ref` | PASS | 145 个解析成功 |
| Event 本地 `$ref` | PASS | 161 个解析成功 |
| Command enum ↔ payload branch | PASS | 19/19，一一对应且 payload 关闭 |
| Event enum ↔ payload branch | PASS | 24/24，一一对应且 payload 关闭 |
| AggregateType 跨契约一致 | PASS | 7 个一致 |
| 错误码唯一 | PASS | 28 个，无重复 |
| 事件原始内容禁用键 | PASS | 7 类禁用键未出现 |
| PRD ↔ 矩阵 FR | PASS | 32/32，顺序完整 |
| PRD ↔ 矩阵 AT | PASS | 15/15，顺序完整 |
| 矩阵 Backlog 引用 | PASS | 23 个被引用故事均在工程包存在 |
| 本地 Markdown 链接 | PASS | 39 个，全部存在 |
| No-go 声明 | PASS | 推进看板与 Gate 0 均保留 |

## 4. 文件指纹

| 文件 | SHA-256 |
|---|---|
| `招聘Agent_G1a_工程开工包.md` | `1d982bde4952dc2fdd00b7a2f4ff3272665a71e0dd090d7ff0a74c0731061079` |
| `contracts/recruiting-agent-g1a-control.schema.json` | `6c0a6c2ba59473eaba62e49aef447a8fc70b87367f72eb6c3c1ab176ca60ee52` |
| `contracts/recruiting-agent-g1a-event.schema.json` | `2c5cd1bcab087721bc2073ee1bbdb7e1bd65394a63b56dcb1c0e8a21b64716d4` |
| `contracts/README.md` | `417bf169ab1b0b7e72b1ba848bda09bbb40ed38e9f5b0eef6d44bbb4326d068a` |
| `contracts/lint_contracts.py` | `04e3463921fd7177c29ad9798f36e2216be6159d6773f5eaad739795bcbc359d` |
| `招聘Agent_G1a_需求追踪矩阵.md` | `f29f73db247231225263f78b9045dea6abdaf35599ef2c813faf96df3236282a` |
| `招聘Agent_领域与事件规格.md` | `47b282ed9c34b702a512eef7ffaaa6c3b6cd33a649aa642733062e5c0a69e9da` |
| `招聘Agent推进看板.md` | `9ee7b0f584e7e624340880e596864bd674cdd1fd1bd6c02df18ce1d241d06e8d` |
| `招聘Agent_Gate0执行包.md` | `1620c4f4fb2b9da0881ae15be0f560a08840431a8fe54bf2dd15a260d6b3abea` |

这些指纹只用于确认本次审阅对象；文件后续修改后必须重新运行检查并更新记录。

## 5. 已知验证缺口

系统 Python、Codex bundled Python 和 Node 全局模块均未提供 Draft 2020-12 validator。本轮没有联网安装依赖，也没有把 `jq` 或自编 lint 冒充完整 Schema 语义验证。

实现仓库的 G1A-001/G1A-060 必须补：

1. 锁定版本的标准 JSON Schema 2020-12 validator。
2. 19 类命令与 24 类事件各至少一个合法 fixture、一个缺字段/多字段反例。
3. 决定字段、错误 actor、同键异载、旧 version/epoch、暂停/撤回/删除竞态行为测试。
4. CI 生成不可变测试报告并回填 `EV-FR*`、`EV-AT*` 和横向证据槽。

因此，本次验收可把产物标为“工程规格 v0.1 / SPEC”，不能标为 `IMPLEMENTED`、`VERIFIED` 或 `RELEASED`。
