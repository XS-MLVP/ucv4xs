# 模块身份、观察与增量维护

模块树使用根 `ucv.json` 的 `modules` 路径（本仓库为 [`docs/modules.json`](../modules.json)）。
它保存模块身份、管理父级、版本观察及变更依据；功能要求和完成条件继续在工程规格中维护。
当前树采用 2026-11-17 确认的草案层次，首次分配的 ID 已持久保存。源码移动、改名和人员变化
不重新计算 ID；模块族可以关联多个 **各自独立初始化的 DUT testbench**。

## 命令

从仓库根执行，均不加载 native、不运行仿真，也不写线上表：

| 命令 | 行为 |
|---|---|
| `ucv modules list [--json]` | 显示模块树与当前 DUT 关联；JSON 返回完整身份记录 |
| `ucv modules check` | 校验 ID、父级无环、继任关系、资料引用和全部 DUT 的 module_id/top/基线观察 |
| `ucv modules adopt INPUT [--catalog PATH] [--output FILE]` | 首次采用规范化目录，完整对账已有 DUT；拒绝覆盖已采用的目录 |
| `ucv modules diff INPUT [--decisions FILE] [--output FILE]` | 只读计算变化、候选匹配与 `plan_sha256` |
| `ucv modules apply INPUT [--decisions FILE] --expect HASH [--output FILE]` | 核对 diff 身份后原子更新目录文件并读回；保留旧观察及人工字段 |
| `ucv init SUITE --group GROUP --dut DUT --top TOP --export-name CLASS --module-id ID` | 给指定身份新增独立 DUT 的 testbench、规格、测试根与失败占位 smoke |

`adopt/diff/apply/check` 返回 JSON；`--output` 保存新报告文件，已有文件不会被覆盖。
`diff` 的 `READY` 返回 0，`NEEDS_REVIEW` 返回 1；格式、映射或过期 diff 错误返回 2。
`check` 的 PASS 仅表示结构与映射一致。`apply` 只更新模块目录，工程配方和 workspace 的
技术绑定在确认合同承接后分别维护。`init` 在配置模块目录时要求现有 ID、本版观察和 top 一致；
未配置模块目录的独立工作空间仍兼容不带 `--module-id` 的初始化。

## 一次更新的步骤

1. 保存目标基线的完整清单及来源证据。由来源核查产生下述观察 JSON；旧观察不能改个基线名
   就当作新观测。`complete` 指该 scope 的来源检查完整，不表示枚举了所有硬件类型或验证完成。
2. 保留已确认对象的 `module_id`。无法确认的新生成名只提供本次 `key`；工具将同名、历史别名、
   同路径、交集 top 列为匹配线索，**不会自动选择候选或重绑**。
3. 运行 diff；明确已有 ID 的延续、新 ID 的分配及内联/拆分/合并/退役依据，再填写 decisions。
4. 对带 decisions 的最终 diff 审查前后名称、父级、基线、源码和变体。把该次 `plan_sha256`
   原样传给 apply；记录、人工字段、观察或 decisions 任何一个变化，旧摘要都会被拒绝。
5. 运行 `modules check` 和 `info`，更新相关规格及必要的 DUT 绑定，再按影响范围适配与复验。

```sh
./scripts/ucv modules diff results/<review>/observations.json \
  --decisions results/<review>/decisions.json --output results/<review>/diff.json
./scripts/ucv modules apply results/<review>/observations.json \
  --decisions results/<review>/decisions.json --expect <plan_sha256> \
  --output results/<review>/receipt.json
./scripts/ucv modules check
```

本轮未观测到的旧 ID 仍留在树中，追加 `unobserved`，旧源码/top 留在旧观察中。部分输入不能
声称 `absent`；即使完整生成未出现，也不能自动退役。公开/internal 使用独立 scope，观察一侧
不会把另一侧标为缺失。管理父级和实际父实例分别保存；父级变更由明确的输入提出，不因扫描到
新使用位置自动搬迁主记录。旧 top 缺失的历史记录仍可关联旧 DUT。

## 观察输入 schema 1

下面是格式示例，尖括号须替换。每次输入只描述一个 scope、一个完整命名基线。

```json
{
  "schema": 1,
  "scope": "public",
  "baseline": "<baseline-name>",
  "baseline_sha256": "<canonical-baseline-sha256>",
  "coverage": "complete",
  "evidence": {
    "scan-new": {"reference": "results/<review>/evidence.json", "sha256": "<file-sha256>"}
  },
  "modules": [
    {
      "key": "scan-root",
      "module_id": "M-existing-id",
      "name": "LogicalModule",
      "parent_key": null,
      "availability": "present",
      "source": {"path": "src/LogicalModule.scala", "line": 12},
      "rtl_tops": ["GeneratedModule"],
      "references": ["suites/<group>/<suite>/docs/spec/design/README.md"]
    }
  ]
}
```

- `baseline_sha256` 是 `ucv.common.digest(Project(...).baseline(name))`，涵盖完整清单，
  不等于文件字节哈希或 `ucv info` 中不含 name 的 `baseline_fingerprint`。
- `coverage` 为 `complete / partial / documentation`。`availability` 为
  `present / absent / unobserved / documented`；documentation 只能提供后两种。
- `key` 只在本次输入中唯一；`module_id` 是可选的、已经确认的持久 ID；未知 ID 也须经 decisions 处理。
  `parent_key` 必填，指向本次输入的另一 key 或 null；父级身份未解决时禁止写入。
- `source` 可为 null；`rtl_tops` 为唯一名称列表。可选 `instances`、`actual_parent_edges`
  保存实际使用位置，`placement`、`grouping` 说明管理归属及模块族边界。
- `references` 只追加资料入口。观察中不允许提供 tracking、lifecycle 或任意人工字段。
- evidence 的键是保留哈希的证据标识；同键内容不同会报错。工具核对基线身份并保留来源哈希，
  不自动获取远端证据、认证证据内容或完成源码/RTL 语义分析。来源真实性须在观察生成时核验。

## 决策输入

```json
{
  "matches": {
    "scan-renamed": {"module_id": "M-existing-id", "reason": "源码移动与接口对照确认角色延续，见本次证据"}
  },
  "add": {
    "scan-new-child": {"module_id": "M-new-persistent-id", "reason": "新独立设计对象，已确认范围"}
  },
  "transitions": [
    {"module_id": "M-old-id", "kind": "inlined", "successors": ["M-existing-id"],
     "reason": "旧要求的逐条承接已在对应规格记录，功能复验仍待执行"}
  ]
}
```

这三个集合均可省略。matches 只能引用已有 ID；add 首次必须分配尚未使用的 ID（一次分配、以后沿用）。
创建时保存输入指纹，完全相同的创建操作可重放为无变化；修改绑定后的 add 不能借此复用旧 ID。
每个观察只能绑定一个 ID，一个 ID 每次只能接受一条观察；多变体放在同一观察的 rtl_tops 中。
transition 的 kind 为 `inlined / split / merged / replaced / retired / active`。
前四种必须有非空 successors，retired 和恢复 active 的 successors 为空。所有承接关系保留
生效基线、原因与本次证据；继任关系不能自指、成环或跨 scope。已退役/被替代对象再次出现为 present
时，必须显式恢复 active。active 表示仍在管理，**不表示验证通过**。

## 持久记录与首次采用

目录包含 `schema: 1`、`evidence` 和 `modules`。每条模块记录包含：

| 字段 | 职责 |
|---|---|
| `module_id / scope / name / parent_id` | 持久身份与当前管理树；名称、父级可变化 |
| `aliases` | 改名前的历史名称，更新时保留 |
| `lifecycle / history` | 管理生命周期及有原因/证据/基线的变化；旧 ID 不删除或复用 |
| `observations` | 按更新顺序追加的版本绑定，最后一条为本次观察；旧版本原样保留 |
| `references` | 规格/资料入口；详细进展仍维护在其所属正文 |
| `tracking` | 可选人工关联信息，例如外部 recordId、任务链接；工具增量更新原样保留 |

首次 adopt 输入为 `{"catalog": <完整目录>, "dut_modules": {"suite": {"dut": "module_id"}}}`。
必须逐项覆盖所有已登记 DUT，基线和 top 要与模块观察相符；采用后 `workspace.json` 的
`duts.<key>.module_id` 是当前 DUT 到模块的关联，目录不重复存一份当前 DUT 清单。

`ucv modules list` 从同一份记录和 workspace 生成树。按模块族组织管理、按 DUT 初始化实现是
两个独立选择：两个 DUT 可拥有相同 module_id，却各有 `testbenches/<dut>/env.py`、tests、smoke
及选跑入口。schema2 要求每个 DUT 的 testbench 独占；实际复用按职责提取到 shared，
其余资源字段见[工作空间参考](workspace.md#workspacejson)。

判断模块是否延续、是否值得拆分及如何承接合同，见
[模块身份与生命周期方法](../../skills/pending/module-identity-and-lifecycle.md)。
