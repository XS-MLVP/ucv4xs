```ucv-bug
{
  "id": "R-13",
  "title": "FrontendTrigger 忽略 tdata2 高 14 位，导致 EQ/GE 误命中与 LT 漏命中",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "tests/frontend_trigger/test_frontend_trigger.py::test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc",
        "tests/frontend_trigger/test_frontend_trigger.py::test_tdata2_above_the_address_space_is_greater_for_less_than",
        "docs/spec/verification/evidence/upstream-review-20261029.md"
      ],
      "note": "两条常驻反例为真实 FAIL；未修改 RTL/CSR，未登记 XFAIL。"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "tests/frontend_trigger/test_frontend_trigger.py::test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc",
        "tests/frontend_trigger/test_frontend_trigger.py::test_tdata2_above_the_address_space_is_greater_for_less_than",
        "docs/spec/verification/exit-criteria.md"
      ],
      "note": "2026-11-08 只读复核：FrontendTrigger.sv 与旧基线逐字节相同，本地上游最新状态也未修复；R-13 仍 blocking/open。"
    }
  ]
}
```

# FrontendTrigger 忽略 tdata2 高 14 位（R-13）

## 2026-11-08 收口（只读核查，未修改 RTL/CSR）

**根因（固定基线逐行核对，`public-a0c2a26cb`）**：

| 位置 | 事实 |
|---|---|
| `backend/fu/NewCSR/DebugLevel.scala:301-303` | `Tdata2Bundle.ALL = RW(63, 0)`，没有 WARL 高位只读 0 的约束 |
| `frontend/ifu/FrontendTrigger.scala:71-78` | 把 `tdataVec(j).tdata2`（64 位）与 36 个 `Pc` 一起送入 `TriggerCmpConsecutive` |
| `backend/fu/util/Trigger.scala:255-300` | `highPos = log2Up(36)+1 = 6`；只取 `lowTdata = tdata(5,0)` 与 `highTdata = tdata(VAddrBits-1,6)`，即 **`tdata2[63:50]` 完全不参与**；EQ/GE/LT 都建立在“PC 的高位只可能等于 `highPC` 或 `highPC+1`”这一连续取指假设上 |
| `backend/fu/util/Trigger.scala:239-248` | `TriggerCmp`（单点比较）同样只取 `data(VAddrBits-1,0)` / `tdata(VAddrBits-1,0)`；本配置走 Consecutive 版本 |

该连续取指优化本身对 in-range 值是等价的（PC 每拍最多前进 2 字节），失效点是
“把 64 位 `tdata2` 截成 50 位”这一步：截断发生在进入比较器之前，任何高位进位
证明都无法覆盖。

**影响面（同一次运行实测，`results/ifu-a0c2a26cb-closeout-seed1-20261108`）**：

| 模式 | 输入 | 期望 | 实测 |
|---|---|---|---|
| EQ | `tdata2 = 2^50 + (base+0x14)`，`base=0x5000` | 36 lane 全 `NONE` | lane 10 = `DEBUG`（`[10]: expected 15, actual 1`） |
| LT | `tdata2 = 2^50`，`base=0x6000` | 36 lane 全命中 | 36 lane 全 `NONE`（`[0..35]: expected 1, actual 15`） |
| GE | `tdata2 = 2^50 + (base+0x14)`，`base=0x5000` | 36 lane 全 `NONE` | lane 10..35 全部 `DEBUG`（一次性探针 `results/ifu-r13-ge-probe-20261108`，实测 `[10..35]: expected 15, actual 1`） |

GE 探针是一次性测量，**未纳入常驻用例**：它与 EQ 同根因，常驻会重复计数同一缺陷。
常驻反例仍只有 EQ/LT 两条。

**上游只读检索（2026-11-08）**：本地镜像
`.cache/sources/f3ac6022…` 的 `origin/kunminghu-v3` = `2145ba1c9`（2026-11-03），
比固定基线 `a0c2a26cb` 前进 10 个提交；`git log --all -- FrontendTrigger.scala`,
`-- Trigger.scala`, `-- NewCSR/DebugLevel.scala` 均无基线之后的提交；
`git diff --stat a0c2a26cb..origin/kunminghu-v3 --` 这三处与 `frontend/ifu` 为空。
10 个提交只触及 decode/rob/bpu/storequeue/lsqueue/memblock/loadunit/XSCache。
最近一次相关提交 `db3923fe0`（2025-03-07，`fix(Trigger): fix comparison between
consecutive pc and tdada2 (#4346)`）已是基线的祖先，正是当前截断实现。
**结论：固定基线与本地已知上游最新状态都没有修复 R-13**；检索只覆盖本地镜像，
未访问网络、未提交 issue/PR。

**候选修复方向（文档记录，未实施、未提交上游）**：

1. **全 64 位比较**：`TriggerCmp`/`TriggerCmpConsecutive` 把 PC 零扩展到 64 位后与完整
   `tdata2` 比较。`TriggerCmpConsecutive` 的“只比较 `highPC`/`highPC+1`”优化必须重新
   证明：当 `tdata2[63:50]` 可任意时，候选高位数不止两个，最直接的做法是退化为逐 lane
   全宽比较（36 个 64 位比较器，时序需评估）。
2. **CSR 高位 WARL 只读 0**：`Tdata2Bundle` 增加写掩码，使 `tdata2[63:50]` 读回恒 0，
   并在合同中声明“仅实现低 50 位 PC 匹配”。比较器可保持不变，但必须同时约束软件
   写入后的读回值，不能只改比较侧；且需要 CSR 侧“写高位读回 0”的用例（不在本 DUT
   边界内）。

两条路径都要保持 in-range EQ/GE/LT、128 字节进位扫描与逐 trigger 副本扫描不变，修复后
两条常驻 FAIL 必须转 PASS。

**证据边界**：本次只读复核未修改任何 RTL/Scala/生成产物；R-13 仍为
`blocking=true, acceptance=open`，不得写成硬件通过。

**2026-11-07 新基线复验（`public-a0c2a26cb`）**：`FrontendTrigger.sv` 与旧基线
`893e1580b` **逐字节相同**（sha256 `6de38b9e…`），上游 63 个提交未触及该模块与
`Trigger.scala`。完整 seed1 与 seed2 定向中两条反例原样 FAIL：EQ 在
`tdata2=2^50+pc` 时 lane 10 命中（期望无动作），LT 在 `tdata2=2^50` 时 36 lane 全不命中。
判定、根因与修复方向均不变，R-13 仍是 blocking + open。

**2026-11-01适配复验**：已迁入严格不可变事务/独占Driver/沿前后双采样，完整64位输入
和独立比较不变；两条反例仍为FAIL，现可在第一笔配置更新沿后立即检出。最终完整IFU
为387 PASS/5 FAIL/1 UNCERTAIN（其中另3 FAIL是新R-14），native seed2定向同样保留这
两条FAIL。下文历史收据不改写，最新证据见[活动事务合同](../../spec/verification/transaction-adapters.md)。

## 现象

`tdata2` 由 CSR 以 `Tdata2Bundle.ALL = RW(63,0)` 暴露为 64 位可写字段，但
`FrontendTrigger` 的 PC 比较只使用 `tdata[VAddrBits-1:0]`（50 位）：

- `src/main/scala/xiangshan/frontend/ifu/FrontendTrigger.scala:72` 把
  `tdataVec(j).tdata2` 原样送入比较；
- `src/main/scala/xiangshan/backend/fu/util/Trigger.scala:241-249`
  （`TriggerCmp`）与 `:255` 起（`TriggerCmpConsecutive`）都只取
  `data(VAddrBits-1,0)` / `tdata(VAddrBits-1,0)`。

因此高位被写入、能读回，却不参与匹配。

## 复现（当前 FAIL）

```
tests/frontend_trigger/test_frontend_trigger.py::
  test_tdata2_above_the_address_space_cannot_equal_a_fetch_pc
  test_tdata2_above_the_address_space_is_greater_for_less_than
```

- 取指窗口 `base=0x5000`，`tdata2 = 2^50 + (base+0x14)`，match=EQ：DUT 在 lane 10
  输出 `ACTION_DEBUG`（1）；全宽语义应无任何 lane 命中。
- 取指窗口 `base=0x6000`，`tdata2 = 2^50`，match=LT：DUT 36 个 lane 全部
  `ACTION_NONE`（15）；全宽语义应为 36 个 lane 全部命中。
- 对照：`tdata2` 落在 50 位地址空间内时，同一比较器与模型一致（含 128 字节进位扫描
  与逐 trigger 副本扫描）。

## 依据

- `Tdata2Bundle.ALL = RW(63,0)`（`backend/fu/NewCSR/DebugLevel.scala:301`）没有把高位
  定义为 WARL 只读 0，软件可写入并读回全部 64 位。
- PC 是 50 位地址，比较时应零扩展；`2^50 + pc` 不等于 `pc`，且任何实现 PC 都小于
  `2^50`。
- 参考模型原先把 `tdata2` 也掩码到 50 位，属于照抄 RTL 实现；本轮已改为全 64 位比较，
  并保留 in-range 随机配置作为对照。

## 影响

只影响软件把 `tdata2` 写成 ≥ 2^50 的配置：

- EQ/GE 会在真实 PC 上误命中，产生本不该有的 breakpoint/debug 进入；
- LT 会漏掉本应命中的地址；
- 触发链（chain）会因此把“误命中/漏命中”传播到相邻 trigger。

## 修复方向（二选一，需设计确认）

1. **按 64 位比较**：PC 零扩展到 64 位，`TriggerCmp` / `TriggerCmpConsecutive` 使用
   完整 `tdata2`。改动集中在 `Trigger.scala`，但 `TriggerCmpConsecutive` 的
   “只比较两个可能高位”优化需要重新证明（高位进位不止 1 个候选）。
2. **把 CSR 高位做成 WARL 只读 0**：`Tdata2Bundle` 增加写掩码，`tdata2[63:50]` 读回
   恒 0，并在合同/文档中声明“仅实现低 50 位”。这保留当前比较器，但必须同时保证
   软件写入后读回值也截断，不能只改比较侧。

任一方向修复后，两条 FAIL 必须转 PASS，并且原有 in-range 用例与随机序列保持通过；
若选方向 2，还需新增“写高位后读回为 0”的 CSR 侧用例（不在本 DUT 边界内，交由
CSR/Debug 工程承接）。

## 证据与边界

- 运行：`results/20261029T143647Z-219b7036`（`ifu: FAIL`，143 PASS / 2 FAIL）。
- 功能点：`IFU-TR-002`（硬件 54/55）。
- 该缺陷是**协议/合同不一致**（CSR 暴露宽度 vs 比较宽度），不是“任意输入都能触发的
  算术错误”；只有当软件写入 ≥ 2^50 的值时可见。
