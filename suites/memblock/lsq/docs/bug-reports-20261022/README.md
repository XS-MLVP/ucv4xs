# LSQ bug汇报包：先看现象，再看代码

本文件夹把最初确认的 **11个独立RTL根因** 分别写成11份报告。面向第一次接触LSQ验证的读者，每份都解释：模块本来要做什么、怎样触发、实际错在哪里、有何后果，以及哪些结论还没有验证。

> 2026-10-22补充：后续对5组GitHub线索做了关系核验，另外确认 **4个独立RTL功能bug** 和 **1个配置合法性问题**。因此当前RTL功能bug总数为 **15**，不是11；详见[14号关系报告](14-relationship-11-vs-5.md)。本文件下面的11份报告不重复展开这4个新增根因。

## 1. 版本和结论边界

| 项目 | 本汇报包采用的口径 |
|---|---|
| 源码 | 公开仓库 `OpenXiangShan/XiangShan`，不使用内部仓库 |
| 分支 / 固定提交 | `kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e` |
| bug数量 | 最初11个独立根因；经5组GitHub线索关系核验后为 **15个RTL功能bug**（+4），另有1个配置合法性问题 |
| 修复状态 | 这些RTL问题均未在本工程完成“修复＋针对性复测通过”闭环 |
| 对外提交 | 本轮只整理本地报告，没有新建GitHub Issue或提交PR |
| 本轮执行 | 复核源码和已有失败证据；补跑2组关系探针（2类×3 lane，共6节点，均按预期FAIL）；没有修改RTL或旧检查器 |
| 证明范围 | 支持的模块接口内存在逻辑错误；不把模块UT直接冒充整核ISA失败证明 |

11个根因对应原两次回归去重后的221个RTL问题失败节点；另有10个独立补充探针失败，仍归入同一批根因。另7个失败节点已经确认为验证侧问题，见[误报总结](12-false-positive-review.md)，**不在这11个bug之内**。

2026-10-22查询上游时，涉及这11项的5个Scala文件与固定提交逐字节相同。该查询快照是 `e516245046234ba958fd69cf95241e77278a1c43`，不是对未来分支状态的承诺。历史Issue关闭、历史PR合并，均不自动代表当前反例已经修复。

## 2. 每个bug一个文件

可以先读“最容易观察”的01、07、08，再读涉及事务所有权的其余报告。

| 文件 | 独立根因 | 一句话说明 | 原回归失败节点数 |
|---|---|---|---:|
| [01：写回错误丢失](01-DEQ-WB-001.md) | `DEQ-WB-001` | 下游还没接收，RTL就把错误标志清掉了 | 50 |
| [02：CBO.zero漏写](02-DEQ-ZERO-001.md) | `DEQ-ZERO-001` | 把老Store的传输误当成自己的清零完成 | 15 |
| [03：SQ提前释放](03-DEQ-FINISH-ORDER-001.md) | `DEQ-FINISH-ORDER-001` | 年轻项完成，却把未完成的老项释放了 | 20 |
| [04：SID复用污染](04-LQU-SID-001.md) | `LQU-SID-001` | 新请求复用编号后，返回结果覆盖了旧Load | 29 |
| [05：串行总线误解锁](05-LSQ-BUS-OWNERSHIP-001.md) | `LSQ-BUS-OWNERSHIP-001` | 旧NC的响应错误地解锁了另一笔IO事务 | 6 |
| [06：无效输入清strict](06-LRQ-STRICT-001.md) | `LRQ-STRICT-001` | 没有有效请求的入口也能改变活动Load的等待条件 | 11 |
| [07：前递mask折回](07-FWD-RANGE-001.md) | `FWD-RANGE-001` | 循环旋转把没有写过的地址也标成可前递 | 28 |
| [08：PA别名漏检查](08-FWD-ALIAS-001.md) | `FWD-ALIAS-001` | 两个VA指向同一PA，却漏掉较新的Store | 12 |
| [09：split尾段wline污染](09-DEQ-SPLIT-WLINE-001.md) | `DEQ-SPLIT-WLINE-001` | 普通Store尾段错误携带相邻CBO.zero的整行写标志 | 16 |
| [10：依赖SQ身份错误](10-FWD-SQID-001.md) | `FWD-SQID-001` | 槽号对了，槽号对应的是哪一代Store却错了 | 15 |
| [11：RAR release错拍](11-RAR-REL-001.md) | `RAR-REL-001` | 地址延迟一拍，有效位却延迟了两拍 | 19 |
| **合计** | **11个根因** | 同一根因的种子、lane和父子层重复失败不重复计bug | **221** |

补充材料：

- [12：误报及验证工具错误为什么发生](12-false-positive-review.md)。
- [13：GitHub额外问题与本套UT为什么没有检出](13-github-missed-bugs.md)。这些是外部报告的复核线索。
- [14：11个bug与5组GitHub线索的关系](14-relationship-11-vs-5.md)。关系核验结果是：**4组为独立RTL功能bug，1组为配置合法性问题**；不是5个默认配置功能bug。按“固定源码＋上游复现”口径，RTL功能bug总数为 **15**；其中 `#6229`、`#6634`、`#6714` 已由本地DUT直接复现，`#6704` 尚未本地重跑。
- [同源漏报复核](../reports/same-source-audit-20261022.md)。对全部模型的同源判断点逐个裁定；新增确认 `#6634` 的“同拍多错误只报一个、正常完成可抢占真实故障”后果，并列出仍保留的策略/实现风险。

## 3. 阅读前只需要知道这些词

| 术语 | 简单解释 |
|---|---|
| Load / Store | 从内存读数据 / 向内存写数据的操作 |
| 老 / 年轻 | 在程序顺序中更早 / 更晚；不等于哪个先执行完 |
| LSQ / SQ / LQ | 访存队列 / Store队列 / Load队列 |
| Sbuffer | 暂存已获写出许可的Store数据，之后再送往缓存 |
| FIFO | 先进入先出去的缓冲队列 |
| 前递（forward） | 较早的Store尚未写入缓存时，直接把数据交给后面的Load |
| VA / PA | 程序使用的虚拟地址 / 地址翻译后的物理地址 |
| mask | 每一位对应一个字节；位为1表示该字节有效，不代表整个数据总线都有效 |
| valid / ready / fire | 有数据 / 能接收 / 本拍真的交接；`fire = valid && ready` |
| 背压 | 接收方暂时`ready=0`，发送方必须保留还没有交接的事务 |
| WB / ROB | 写回完成结果 / 保持程序提交顺序的重排序缓冲 |
| CBO.zero | 按缓存行清零的操作；不能只“报告完成”而没有自己的清零副作用 |
| NC / IO | 非缓存内存访问 / 需要串行约束的设备类访问；两者不能混作同一种事务 |
| replay / nuke | 重新执行Load / 检出顺序冲突后要求丢弃并重做相关执行结果 |
| owner / UID | 某个请求的真实身份 / 验证环境给原始事务分配的唯一标识 |

Scala/Chisel的两个常见陷阱：`when(...).otherwise(...)` 的 `otherwise` 也会执行赋值；对一个已是寄存器的Bundle字段赋值，并不会把该字段自动变成组合线。报告06和11分别解释这两种情况。

## 4. 怎样追到源码、测试和原始失败

每份报告的Scala代码均为固定提交中的**原文摘录**，保留原有拼写和注释，不是修复代码。旁边给出文件与行号；HTML注释中的`source`标记用于机械核对摘录。

共同证据入口：

- [最终全量源码裁定报告](../reports/all-fail-source-verdicts-20261022.md)。
- [全部根因、源码片段和逐节点证据JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)：查`roots[bug编号]`及`failed_nodes`。
- [238行失败节点CSV](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.csv)：区分原回归和补充探针，不跨运行合并通过率。
- [有界失败窗口索引](../../results/fail-source-adjudication-01/captures-index-v1.json)：包含gzip路径和原字节SHA，无需复制完整波形。
- [上游5文件逐字节对比](../../results/github-duplicate-check-20261022/fixed-versus-upstream-source-v1.json)。

报告中的“激励”是已有测试的接口级操作说明，不是未经验证的整核汇编。已具备本工程原生DUT、Picker和xreactor环境时，可在 `memblock-hash/lsq/` 运行对应nodeid，例如：

```sh
python3 -B tools/run_summary.py --name bug-report-wb-new-run --workers 1 -- 'tests/deq/test_cbo_fault_consumption.py::test_delayed_writeback_fire_consumes_original_cache_error[False-True]'
```

运行名必须换成尚不存在的名字。当前未修复RTL下，该用例预期仍会FAIL；运行命令不是“已经修复”的证明。本轮没有执行此命令，不默认开启完整trace、波形或源码副本。
