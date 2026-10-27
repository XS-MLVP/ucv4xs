# ICacheMainPipe / ICachePrefetchPipe 功能验证与覆盖率闭环

运行：`results/xreactor-mp-24`（MainPipe）、`results/xreactor-pf-15`（PrefetchPipe）

| DUT | 功能点 | 用例 | 语句覆盖 | 行覆盖（含 picker 包装） |
|---|---|---|---|---|
| ICacheMainPipe | 12/12 PASS | 19 | 432 / 432 = **100.00%** | 755 / 813 = 92.87%（余下 58 行是声明/`end`） |
| ICachePrefetchPipe | 11/11 PASS | 17 | 295 / 295 = **100.00%** | 442 / 477 = 92.66%（余下 35 行是声明/`end`） |

分母未剔除；两个 DUT 被 firtool 平坦化成单个 `*Dut.v`，因此统计文件就是 DUT 本身，不是测试台包装。

## ICacheMainPipe 功能点

| ID | 功能点 | 判定依据 |
|---|---|---|
| 001 | 命中路径 | waymask 命中的行从数据阵列取数，一拍返回 IFU，并对该 set/way 触发一次 replacer touch |
| 002 | 缺失请求与回填完成 | 空 waymask 的行发出一次 miss 请求（块地址 + set），流水线保持到回填到达后返回回填数据；跨行取指的第二行单独请求 |
| 003 | ITLB 异常 | 异常上报 IFU、不请求 miss、转发 guest physical address |
| 004 | PMP access fault | 上报 access fault，不发 miss |
| 005 | MMIO / uncacheable | 不发 miss，`pmpMmio` 置位 |
| 006 | corrupt / denied 回填 | 仍完成取指，但分别上报 hardware error / access fault，不当作有效数据 |
| 007 | 双取指有效性 | 第二取指仅在有效、waylookup 有效、无数据 bank 冲突（同 way 不同 set）且非 MMIO/异常时为真；两路结果在同一响应返回 |
| 008 | flush | 杀死在途取指，不产生 IFU 响应与 miss；之后可正常服务新请求 |
| 009 | maybeRvcMap 对齐与范围 | 跨行取指的两行 RVC map 拼接、移位并对实际取指范围做 mask；taken 偏移与 size 正确 |
| 010 | ECC 上报 | ECC 开启时数据/元数据校验失败置 `toIfu.corrupt` 并在一拍后上报 BEU |
| 011 | 第二取指跨行/缺失/回填异常 | 第二取指自身跨行、两行分别缺失、回填 corrupt 只影响请求 1 的异常 |
| 012 | 全 bank ECC | 全行取指选中 8 个 bank；两路取指的任意 bank 校验失败都能置 corrupt |

## ICachePrefetchPipe 功能点

| ID | 功能点 | 判定依据 |
|---|---|---|
| 001 | 元数据命中写 waylookup | 写回每行的 set 索引、waymask、RVC map、ECC code 与共享 pTag |
| 002 | 元数据缺失发 miss | 无命中的读端口发出块地址 + set；跨行预取读/请求两行 |
| 003 | ITLB miss | 停在 s1、`pendingItlbMiss` 保持、持续重发翻译请求，完成后才写 waylookup |
| 004 | 元数据重发 | 翻译完成时元数据未 ready 则重发元数据读，接受后才完成 |
| 005 | csrPfEnable | 关闭时仍写 waylookup（保持主流水元数据一致），但不发 miss |
| 006 | 软预取 | 不写 waylookup、不发 miss |
| 007 | 异常 / MMIO | 异常与 MMIO 写入 waylookup 条目并抑制 miss |
| 008 | flush | 置 `itlbFlushPipe`、阻止被杀的写，之后可正常服务 |
| 009 | 双预取 case | SameLine/Overlap/Interleave 选择两个元数据读地址并广播到两个取指块；两路 waylookup 都写 |
| 010 | 回填更新 stage-1 元数据 | 同块回填更新 waymask；同 way 不同 tag 的回填清除陈旧命中 |
| 011 | miss 反压 | miss 单元不 ready 时请求停在请求级不丢失，接受后完成 |

## 缺口倒推过程

| 轮次 | MainPipe 语句覆盖 | 倒推出的功能点 |
|---|---|---|
| 1 | 93.75% | 初版 10 功能点，ECC 只覆盖请求 0 的 bank 0–3 |
| 2 | 99.31% | 补 011（请求 1 跨行/缺失/回填异常）与 012（全 bank ECC） |
| 3 | **100.00%** | 012 补“请求 1 全行 8 个 bank 的 ECC”情形：显式给出每个 bank 的奇校验字，bank 1/5/6 的 `bankCorrupt_1_*` 才第一次置 1 |

| 轮次 | PrefetchPipe 语句覆盖 | 倒推出的功能点 |
|---|---|---|
| 1 | 96.27% | 初版 9 功能点，未覆盖回填与 stage-1 合并、miss 反压 |
| 2 | 98.31% | 补 010（回填更新元数据）与 011（miss 反压） |
| 3 | **100.00%** | 010 补“跨行两端口都命中且 meta 校验位为 1”情形；011 补“s2 被占用时第二个请求进入 EnterS2 再释放”情形 |

### 倒推暴露的参考模型缺陷（非 RTL 缺陷）

1. **PrunedAddr 的位宽语义**：FTQ 的 `vAddr.addr` 与 IFU 的 `startVAddr/pAddr/gpAddr` 都是
   `PrunedAddr`，端口上携带的是 `address >> 1`；初版按完整地址驱动/比较，miss 请求块地址出现
   `+0x10/+0x20` 的偏移。agent 现在统一在驱动侧右移、读回侧左移。
2. **set 索引不是块内偏移**：`get_idx(addr) = addr[untagBits-1:blockOffBits]`（默认
   `addr[13:6]`），初版误用 `addr[5:0]`，导致 vSetIdx 全错。
3. **waylookup 的 pTag 是页号**：`pTag = blkPAddr >> 6`，`missResp.blkPAddr` 用它重建匹配；
   模型与内存对端必须用同一页号。
4. **非跨行取指的第二行无元数据**：`s1_sramValid(1)` 只在 double-line 时置位，第二行的
   waymask/RVC map 为 0；初版期望两行都有效。
5. **PrefetchPipe 的第二读端口**同样只在 double-line 时采样，非跨行时为 0。
6. **同拍 fetch+prefetch 的缺失判定**：PrefetchPipe 的异常/MMIO 来自 ITLB 响应，寄存器化后
   在 s2 才使用；模型的 miss 列表按读端口而非取指块生成。
7. **xcomm 电平两拍提交**：请求只在一个采样沿有效；agent 先写请求、等一个沿、立即撤销，
   避免同一请求被 decoupled 输入重复接受。回填和 miss 响应按"观测到事件"推进，不写死拍数。

## 剩余行（第三轮后为 0 条可执行行）

### MainPipe

`results/xreactor-mp-24`：19 passed，语句 **432/432**。此前的 `bankCorrupt_1_1/_1_5/_1_6`
不是“声明归因差异”——它们是请求 1 的 bank 1、5、6 **从未真正置 1**：旧用例只让部分 bank
出现奇校验，`^data != code` 在这三个 bank 恒为 0，Verilator 不会把恒 0 的连续赋值记为命中。
新增的全行 ECC 用例给请求 1 的每个 bank 显式提供奇校验字，8 个 bank 的 corrupt 位全部翻转，
缺口消失。余下 58 条“行”全部是端口/线网声明与 `end`。

### PrefetchPipe

`results/xreactor-pf-15`：17 passed，语句 **295/295**。四个 `metaCodes` 行不是声明归因：
旧用例的 meta 校验位恒为 0、且只测单行取指，第二读端口的 `s1_metaInfo_1_metaCodes` 从未
取到 1。新增用例用跨行取指（两端口都命中）并把 meta `code` 在 1/0 之间切换，四个表达式
全部覆盖。`s1_state == EnterS2 & s2_ready` 一行由新增的两请求反压用例覆盖：第一个请求占住
被 miss 反压的 s2，第二个请求写入 waylookup 后进入 EnterS2，释放 miss 后回到 Idle 并发出
自己的 miss。余下 35 条“行”全部是声明与 `end`。

## 复现

```bash
cd /home/xyl/kmh-v3-test/icache-verify-kunminghu-v3
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 1 --output results/xreactor-mp-24 -- tests/mainpipe
PYTHONPATH=/usr/local/share/picker/python:$PWD:$PWD/dependencies/xreactor/src \
  python3 -m xreactor run --workers 1 --output results/xreactor-pf-15 -- tests/prefetchpipe
python3 tools/coverage_gaps.py results/xreactor-mp-24 --dut mainpipe
python3 tools/coverage_gaps.py results/xreactor-pf-15 --dut prefetchpipe
```
