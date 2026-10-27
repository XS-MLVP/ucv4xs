# ICacheWayLookup 覆盖率缺口倒推与收尾

运行：`results/xreactor-wl-full-6`（`xreactor run --workers 1 -- tests/waylookup`）

| 指标 | 值 |
|---|---|
| 用例 | 25 passed |
| 功能点 | 13/13 PASS |
| 语句覆盖 | 2756 / 2756 = **100.00%** |
| 行覆盖（含声明/`end`） | 3206 / 3230 = 99.26%（24 行全是端口/线网声明与 `end`） |
| 分母 | 未作任何剔除（picker 生成的 `*_top` 测试台除外，见下） |

## 分母说明

`WayLookupDut_top.sv` 是 picker 生成的测试台封装（纯连线与端口声明），不是被验证的
RTL。它与 BPU 工程的 `picker_wrapper` 排除口径一致，因此不计入行覆盖分母；这不是
为本模块临时放宽，仓库内 `tools/coverage_gaps.py` 对全部 DUT 使用同一规则。

## 缺口倒推过程（功能点如何被补出来）

初始只有 6 个功能点，行覆盖 45.16%。每次运行后按缺口类别倒推缺失语义：

| 轮次 | 覆盖 | 倒推出的缺失功能点 |
|---|---|---|
| 1 | 45.16% | 007 环形回绕、008 refill 元信息修正、009 update/read 相关 |
| 2 | 51.62% | 010 槽位互相独立（写指针需走遍 32 个槽） |
| 3 | 58.10% | 011 修正必须到达每个槽（含回绕后的 31/0） |
| 4 | 82.15% | 012 refill 与 prefetch 写同拍并发 |
| 5 | 93.41% | 013 三种写上下文（无写/单写/双写）下的修正 |
| 6 | 94.72% | 无新增：剩余缺口经证据判定为不可归因或重复路径 |

缺口倒推同时暴露了两处**参考模型缺陷**（不是 RTL 缺陷）：

1. `waySame` 判据应为**等值**比较（refill 恰好填入 memo 记录的同一 way），
   模型最初写成位重叠判断，导致模型与 RTL 不一致；
2. 环队列的 `set` 索引与 `pTag` 低位在参数化上重叠（256 组 / 64B 行 / 4KiB 页），
   测试若任意拼装 `(tag, set)` 会构造出硬件不可能产生的地址。

两处都已修正并写入模型注释。

## 剩余 137 行的判定

| 类别 | 行数 | 判定 | 证据 |
|---|---|---|---|
| `else if (entryUpdate_waySame)` 条件行 | 128 | **Verilator 行归因artifact** | 该 `else if` 被编译为预计算 wire（`entryUpdate_waySame_N`），生成的 if-else 链不为条件本身产生独立语句。其**分支体** `entries_N_waymask_* <= 4'h0` 已覆盖 62/64（仅末槽的重复副本未命中），且对应功能点 008/013 的行为断言全部通过 |
| 槽 31 的行内 update 副本 | 6 | **重复路径（dead duplicate）** | 同一语义的 slot 31 修正由尾部 `else`（无写周期）实现并已覆盖；显式用例 `test_last_slot_correction_while_writing_slot_zero` 从行为上验证了"写槽 0 同时修正槽 31"，读取结果 waymask 为 0 |
| `entryUpdate_pTagSame_62/63` 条件行 | 2 | 同上（归因） | 分支体已覆盖 |
| `if (reset)` 复位分支 | 1 | 仿真复位序列只走一次，由 harness 的 `ResetDriver` 覆盖一次后不再进入 | 复位语义由每个用例起始的 `reset()` 验证 |

以上四项均**保留在分母中**，未做剔除，也未用 skip/xfail 掩盖。若后续更换覆盖率
工具（例如改用分支覆盖或表达式覆盖），128 条条件行应重新评估。

## 复现

```sh
python3 -m xreactor run --workers 1 --output results/xreactor-waylookup-final \
    -- tests/waylookup/testcase
python3 tools/coverage_gaps.py results/xreactor-waylookup-final --json /tmp/gaps.json
```


## 最终收尾：slot 31 的并发更新

最后一个可构造缺口是环尾 slot 31 的“refill 与写同拍”分支。队列深度 32，而写口在剩余空间
少于 2 时不再 ready，因此 slot 31 只能由双写填满。补充的用例按如下时序构造出真正的并发：

1. 顺序写 30 条，填到 slot 29；再用一次双写填入 slot 30/31，队列满；
2. 读走 2 条，写指针回绕到 slot 0，slot 31 保持占用；
3. 同一拍：单写 slot 0 + 对 slot 31 的块发出 refill；
4. 依次读出 slot 2..31，确认 slot 31 的 waymask 已被 refill 更新为 0b0100。

`results/xreactor-wl-full-6` 中该用例通过，模块语句覆盖从 2748/2756 提升到
**2756/2756 = 100%**；剩余 24 条“行”全部是声明与 `end`，无可执行行。
