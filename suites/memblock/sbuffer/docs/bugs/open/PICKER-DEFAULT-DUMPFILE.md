# PICKER-DEFAULT-DUMPFILE：Picker 默认 dump 已在旧基线验证隔离，当前基线未复验

状态：**历史验证问题已按 fixed 处置并有通过证据；当前默认基线未重新运行，保留
open/unverified**。Picker `-w` 在生成的 top 中注入无条件 `$dumpfile/$dumpvars`；即使运行时不调用
`SetWaveform` 也会产生默认 fst。该问题不是设计退役，也不应因为历史“已缓解”就在当前
基线标记 closed。

## 原问题

生成 harness 的默认 dump 可能在正常运行中写出波形文件，导致“未请求波形”的交付仍包含
波形或 I/O 副作用。历史 [manifest/known-issues.json](../../../manifest/known-issues.json) 将其分类为 `tool_boundary`，
状态为 `mitigated`；进一步核对运行入口和报告后，旧基线已经用临时 cwd 与 trace policy
实际验证了隔离效果。

## 独立预期与历史处置

- 编译保留 trace 能力，供显式诊断使用；正常运行不调用 `SetWaveform`，不提供运行时
  波形开关。
- pytest 进程在临时 cwd 中运行，Picker 默认 fst 只落在临时目录并删除；运行入口再清理
  项目内可能的遗留波形。
- trace policy 必须检查证据目录：存在波形、逐周期 JSONL 或 `*trace*.json` 时失败。
- 旧基线 `sbuffer-top-contract-03` 的 `trace-policy.json` 记录 `status=PASS`；这证明的是
  “正常回归不把默认 dump 留在证据树”，不是“已经实测零 dump I/O”。默认 dump 的生成
  仍是 Picker 行为。

## 当前状态

当前默认基线为 `public-a0c2a26cb`，本工程尚未在该基线重新执行构建和回归，也没有新的
`trace-policy.json`。因此历史修复结论不能自动迁移；本记录保留在 `open/`，当前版本
标记为 `unverified`。重新运行并确认 trace policy PASS 后，再把当前版本改为 closed。

## 证据

- [顶层 UT 报告](../../spec/verification/evidence/sbuffer-top-20261024.md)
- [运行入口](../../../tools/run.py)：临时 cwd、遗留波形清理和 trace policy
- [pytest 隔离夹具](../../../tests/conftest.py)：进程级临时 cwd
- 历史运行 `results/sbuffer-top-contract-03/trace-policy.json`（`status=PASS`，运行产物不随 Git 发布）
- [历史问题台账](../../../manifest/known-issues.json) 的同名条目

```ucv-bug
{
  "id": "PICKER-DEFAULT-DUMPFILE",
  "title": "Picker 默认 dump 已在旧基线验证隔离，当前基线未复验",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/sbuffer/docs/spec/verification/evidence/sbuffer-top-20261024.md",
        "suites/memblock/sbuffer/tools/run.py",
        "suites/memblock/sbuffer/tests/conftest.py",
        "results/sbuffer-top-contract-03/trace-policy.json"
      ],
      "note": "历史基线已修复验证：临时 cwd + trace policy PASS；保留原 mitigated 证据边界"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/sbuffer/README.md"
      ],
      "note": "当前默认基线未重新构建/回归或生成 trace-policy.json，不能沿用历史 closed"
    }
  ]
}
```
