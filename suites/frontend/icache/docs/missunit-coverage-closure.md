# ICacheMissUnit 功能验证与覆盖率闭环

运行：`results/xreactor-mu-8`（`xreactor run --workers 1 -- tests/missunit/testcase tests/framework/test_repository_layout.py`）

| 指标 | 值 |
|---|---|
| 用例 | 29 passed（missunit 28 + 目录契约 1） |
| 功能点 | 11/11 PASS（`ICACHE-MISSUNIT-001` … `011`） |
| 语句覆盖 | 487 / 487 = **100%** |
| 行覆盖（含 picker 包装） | 1002 / 1035 = 96.81% |
| 行覆盖（不含 picker 包装） | 905 / 919 = 98.48% |
| 分母 | 未剔除；picker 生成的 `MissUnitDut.v` 包装仅在行统计中说明，与全仓库口径一致 |

## 功能点与判定

| ID | 功能点 | 判定依据 |
|---|---|---|
| 001 | 两池独立容量（4 fetch / 10 prefetch） | 填满 fetch 池后 prefetch 池仍可分配，反之亦然；两池索引不相交 |
| 002 | 重复请求抑制 | 同 block+set 重复请求 ready 但不占第二条；同 block 不同 set 视为不同 miss；满池时重复请求仍被 hit 路径接收 |
| 003 | fetch 优先占用内存通道 | prefetch 先到、fetch 后到，issue 顺序仍为 fetch 在前；前一次 prefetch grant 不改变该优先级 |
| 004 | prefetch 按到达顺序服务 | 4 条 prefetch 的 issue 顺序等于分配顺序，且等于优先级 FIFO 的索引顺序 |
| 005 | issue 时请求 victim way | victim 请求的 vSetIdx 等于该 MSHR 的 set；回填响应的 waymask 等于 replacer 给出的 way |
| 006 | 回填完成发布响应并写阵列 | 最后一个 beat 后下一拍发布 block/set/waymask，同时 metaWrite/dataWrite 有效；响应后条目释放 |
| 007 | corrupt/denied 不写阵列 | 仍向流水线报告 corrupt/denied（供取指触发 access fault），但 metaWrite/dataWrite 均为 0 |
| 008 | flush 只清 prefetch | flush 后 fetch 条目仍在并可继续 issue；已发出的 prefetch 事务不丢失，完成后静默释放 |
| 009 | fence.i 清两池 | 未发出的条目全部失效；已发出的条目保留到回填完成，完成时不发布响应、不写阵列 |
| 010 | WFI 安全性 | 仅当没有已发出的 MSHR 时 wfiSafe=1；wfiReq 有效期间不发出新的 acquire |
| 011 | 每个 MSHR 槽位可独立工作 | 4+10 个槽位全部占用并逐一 issue/回填，响应各自匹配；prefetch 优先级 FIFO 完成一次 10 项回卷 |

## 缺口倒推过程

| 轮次 | 语句覆盖 | 倒推出的功能点 / 修正 |
|---|---|---|
| 1 | — | 初版 10 功能点，20 用例 |
| 2 | 96.0%（各 ICacheMshr 28/29） | 倒推出 **011**：只有 fetch MSHR 0 和 prefetch MSHR 0..6 被使用过，槽位 1–3 与 7–13 的 `way` 捕获语句从未执行 |
| 3 | **100%** | 新增"填满两池并逐一回填"用例后，全部 14 个槽位的语句均被覆盖 |

### 倒推暴露的参考模型缺陷（非 RTL 缺陷）

1. **way 是索引不是 one-hot**：`victim.resp.way` 是 2-bit way 索引，`waymask = UIntToOH(way)`。
   初版把 replacer 返回值当作 one-hot mask，导致 `waymask` 全错。
2. **xcomm 电平驱动的两拍提交**：Python 写出的电平在下一沿提交、再下一沿被 DUT 采样。
   初版按"写后一拍即生效"计算，导致 acquire 被连续消费、grant beat 数错位。
   现在 agent 以"offered source 发生变化"作为接受事件，以"第 `beats` 个沿后撤销 valid"
   保证恰好 `beats` 个 beat 被采样。
3. **flush/fence.i 后的响应被抑制**：RTL 的 `io.info.valid` 带有 `!flush && !fencei` 寄存位，
   被重定向的已发出事务完成时不会发布响应。模型最初仍期望响应，按文档语义（fence.i 后
   取到的行可能已过期，不得进入流水线/阵列）修正为"静默完成并释放"。
4. **denied ⇒ corrupt**：TileLink 规范要求 denied 时同时置 corrupt；测试内存对端据此
   产生 beat，RTL 的 `writeSramValid` 才与规范一致。

## 剩余 33 行（已闭环）

全部为声明行，无行为缺口：

| 类别 | 行数 | 证据 |
|---|---|---|
| `ICacheMshr_1..13.sv` 的端口声明行 | 13 | 各文件仅剩 1 行，均为 `input ... io_lookUps_1_req_bits_*` 端口声明；对应 29/29 语句已全部覆盖 |
| `FIFOReg.sv` 的 `reg [3:0] regFiles_*` 声明 | 1 | 67/67 语句覆盖；FIFO 经过 10 项回卷（`test_every_mshr_slot_owns_and_completes_its_transaction`） |
| `MissUnitDut.v`（picker 包装）的端口声明 | 19 | picker 生成的测试台不属于 DUT 逻辑，全仓库统一排除；其 43/43 条语句已覆盖 |

## 复现

```bash
cd /home/xyl/kmh-v3-test/icache-verify-kunminghu-v3
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 1 --output results/xreactor-mu-8 -- tests/missunit/testcase
python3 tools/coverage_gaps.py results/xreactor-mu-8 --dut missunit
```
