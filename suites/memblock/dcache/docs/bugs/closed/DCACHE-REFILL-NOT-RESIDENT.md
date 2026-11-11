# DCACHE-REFILL-NOT-RESIDENT：冷 load refill 后不命中（原 RTL 指控不成立，当前基线未复验）

状态：**已关闭（仅撤回历史 RTL 误报，`invalid`）**。原“冷 load refill 后不命中”由
未等待 SRAM 清扫、GrantData size 误用 5、未在 S2 采样响应三项验证环境问题共同造成；
修正环境后，`public-893e1580b` 的冷 miss → AcquireBlock → 2×GrantData → 重放命中
路径通过。当前默认基线 `public-a0c2a26cb` 仍为 `unverified`：本工程尚未在该基线
prepare/build/run，关闭旧误报不代表新基线同域行为通过，也不能因为新基线未跑而把旧
RTL 指控重新当成 open。

## 原问题与原 RTL 指控

历史阶段观察到：DCache 顶层冷 load 产生 miss 并完成 refill 后，对同一行的重放 load
仍不命中。本记录的旧版本把该现象列为 RTL 问题，并推断原因涉及 tag/meta SRAM、
GrantData 形态、load 响应采样以及 refill 安装/重放时序。该 RTL 归因已被原始证据撤回：
三项直接原因都在验证环境侧，修正后同一路径通过。

历史边界：原路径曾记录为失败/阻塞，但本仓库未保留独立的原始 FAIL 运行收据；
[DCache 顶层 2026-10-24 报告](../../spec/verification/evidence/dcache-top-20261024.md)
保留了归因、修正方式和修正后的 PASS 记录。本记录不补造缺失的运行证据。

| 边界 | 当前保留的记录 |
|---|---|
| 历史原判定 | 冷 miss → refill → 重放不命中（历史 FAIL/阻塞）；独立原始 run 收据未在本仓库保留 |
| 误报修正 | 三项原因均为验证环境；修正后 `dc-final-05` 15 PASS，原 RTL 指控撤回 |
| 当前默认基线 | `public-a0c2a26cb` 为 `unverified`；本工程未在该基线 prepare/build/run |
| 关闭范围 | 只关闭 `public-893e1580b` 的原 RTL 误报（`invalid`），不证明新基线同域行为通过 |

## 三项验证环境原因

1. **未等待 tag/meta SRAM 清扫**：复位释放后 tag/meta SRAM 需要 256 拍逐 set 清扫，
   清扫完成前 MainPipe 的 tag/meta ready 为低。旧用例在清扫完成前发起事务；当前用例
   统一等待 300 拍。
2. **GrantData size 误用 5（单 beat）**：`size=5` 时 `r_beats1=0`，MissEntry 把第一个
   beat 当成整行完成，后续无法形成完整行。冷 refill 必须使用 `size=6` 并等待
   2×GrantData。
3. **未在 S2 采样 load 响应**：旧检查在错误的流水阶段读取响应，导致已完成的 refill
   被误判为不命中；修正为在 S2 采样后，数据与重放命中均可观察。

以上均为 driver/monitor/用例前置条件问题，不是 DCache RTL 缺陷。

## 独立预期

冷 load 产生 miss 后，DCache 在对应 L2 通道发出 `AcquireBlock`（opcode 6、size 6、
64B 对齐地址），L2 用两个 `GrantData` beat 回应；refill 完成后对同一行重放 load 应
命中，返回数据与 refill beat 拼接一致。该期望不依赖“先写后读”或恰好同窗口的旧值，
也不依赖 DUT 输出反推期望。

## 修正与历史证据

- [DCache 顶层 UT 报告（2026-10-24）](../../spec/verification/evidence/dcache-top-20261024.md)
  第 3 节明确记录：此前“refill 不命中”的阻塞由未等清扫、GrantData size=5、未在 S2
  采样三点共同造成，修正后冷 miss→refill→hit 全链路通过；`results/dc-final-05`
  记录 15 PASS。
- [DCache 顶层 UT 报告（2026-10-25）](../../spec/verification/evidence/dcache-top-20261025.md)
  在 25 PASS + 1 XFAIL 的复核中只确认 `MQ-STORE-MERGE-DATA-PENDING` 为 RTL 缺陷，
  其余曾怀疑问题均已澄清为非缺陷。
- [P0 收口报告](../../spec/verification/evidence/p0-closure-20261026.md) 只把
  `MQ-STORE-MERGE-DATA-PENDING` 列为确认 RTL 缺陷；本项不在其中。
- [manifest/known-issues.json](../../../manifest/known-issues.json) 同名条目为
  `reviewed_not_bug` / `closed_resolved`，记录的是验证环境根因和修正，不是“已修复的
  RTL bug”。

## 当前范围与复验义务

- 当前根默认基线为 `public-a0c2a26cb`；本工程尚未在该基线执行 prepare/build/run，
  因此该基线结论是 `unverified`，不是重新打开的 RTL 缺陷。
- 复验时应重新执行当前节点
  [test_cold_miss_refill_then_hit](../../../tests/dcache/test_dcache.py)::test_cold_miss_refill_then_hit
  （若当前测试组织改变，保留旧新 nodeid 关联），并记录源码、RTL、构建、随机种子和
  运行收据；未选择、SKIP、XFAIL 或缺失证据都不能作为通过证据。
- 历史 PASS 只属于 `public-893e1580b`；不得据此推断其他 L2 响应形态、错误路径、
  Uncache 行为或当前默认基线已通过。

```ucv-bug
{
  "id": "DCACHE-REFILL-NOT-RESIDENT",
  "title": "冷 load refill 后不命中（原 RTL 指控不成立，当前基线未复验）",
  "kind": "verification",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "closed",
      "evidence": [
        "suites/memblock/dcache/docs/spec/verification/evidence/dcache-top-20261024.md",
        "suites/memblock/dcache/docs/spec/verification/evidence/dcache-top-20261025.md",
        "suites/memblock/dcache/tests/dcache/test_dcache.py::test_cold_miss_refill_then_hit"
      ],
      "note": "原阻塞由未等 SRAM 清扫、GrantData size=5、未在 S2 采样三项验证环境问题造成；修正后 dc-final-05 记录 15 PASS，原 RTL 指控撤回"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "unverified",
      "evidence": [
        "suites/memblock/dcache/README.md"
      ],
      "note": "当前默认基线尚未重新 prepare/build/run；停止把未复跑当作旧 RTL 指控复活，复验义务继续保留"
    }
  ],
  "resolution": {
    "reason": "invalid",
    "evidence": [
      "suites/memblock/dcache/docs/spec/verification/evidence/dcache-top-20261024.md",
      "suites/memblock/dcache/docs/spec/verification/evidence/dcache-top-20261025.md",
      "suites/memblock/dcache/docs/spec/verification/evidence/p0-closure-20261026.md",
      "suites/memblock/dcache/manifest/known-issues.json"
    ],
    "note": "关闭的是历史 RTL 误报归因：三项原因均为验证环境修正，修正后同一路径通过；当前默认基线仍为 unverified"
  }
}
```
