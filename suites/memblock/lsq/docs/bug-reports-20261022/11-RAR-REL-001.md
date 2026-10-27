# RAR-REL-001：release的地址和有效位没有处在同一个周期

**结论：已确认的RTL bug；未完成修复复测。** 固定提交`893e1580b705d81f113c30c7a05734e09a08050e`。19个原失败节点及2个独立补充探针失败归于同一根因。

## 1. 用一句话理解

RAR要记住“刚刚发生过哪条缓存行的release”。代码想保存上一拍的事件，却把地址保存一拍、有效位保存两拍。结果该抓住的上一拍冲突漏掉，已经过期的事件又可能被多算一拍。

这像监控录像的图像与时间戳错开了：图像是这一时刻，标记却来自另一时刻。

## 2. RAR在这里做什么

RAR检查Load与Load之间的顺序。年轻Load可能先得到数据；如果随后发现较老Load需要与它维持顺序，而相应缓存行在关键窗口发生过release，就不能无条件保留年轻Load的旧结果。

为覆盖Load分配附近的窗口，源码使用当前release和上一拍release。这里的`release2Cycle`是变量名，不应仅凭名字推断它“本来就该延迟两拍”；代码注释要求的是**延迟一拍**。

## 3. 有问题的Scala实现

文件：[LoadQueueRAR.scala](../../../../XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueRAR.scala)，**130–137行**：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueRAR.scala:130-137 -->
```scala
  // Real-allocation: load_s2
  // PAddr write needs 2 cycles, release signal should delay 1 cycle so that
  // load enqueue can catch release.
  val release1Cycle = io.release
  // val release2Cycle = RegNext(io.release)
  // val release2Cycle_dup_lsu = RegNext(io.release)
  val release2Cycle = RegEnable(io.release, io.release.valid)
  release2Cycle.valid := RegNext(io.release.valid)
```

**181–189行**用它判断新分配项是否经历过release：

<!-- source: XiangShan/src/main/scala/xiangshan/mem/lsqueue/LoadQueueRAR.scala:181-189 -->
```scala
      //  NC is uncachable and will not be explicitly released.
      //  So NC requests are not allowed to have RAR
      released(enqIndex) := enq.bits.nc || (
        enq.bits.dataValid &&
        (release2Cycle.valid &&
        enq.bits.paddr(PAddrBits-1, DCacheLineOffset) === release2Cycle.bits.paddr(PAddrBits-1, DCacheLineOffset) ||
        release1Cycle.valid &&
        enq.bits.paddr(PAddrBits-1, DCacheLineOffset) === release1Cycle.bits.paddr(PAddrBits-1, DCacheLineOffset))
      )
```

## 4. 为什么是两级valid，不是给valid补一个门控

`RegEnable(io.release, ...)`已经创建了一个包含`valid`字段的寄存器。下一行对`release2Cycle.valid`赋值，是给这个寄存器的输入端接线；右边的`RegNext`又创建了**另一个**寄存器。

生成的真实SV在`rtl/load_queue_rar/LoadQueueRAR.sv:11865–11868`明确是：

```systemverilog
release2Cycle_valid <= release2Cycle_valid_REG;
if (io_release_valid) release2Cycle_bits_paddr <= io_release_bits_paddr;
release2Cycle_valid_REG <= io_release_valid;
```

因此地址只保存一次，valid却走了两次寄存。不是参考模型随意规定了一个与RTL无关的时序。

## 5. 怎样激励

必须使用**孤立一个周期的release脉冲**，连续高电平会掩盖这个错拍：

1. 令`io.release.valid=1`仅一拍，地址为`0x18007`，之后置0。
2. 下一拍正常分配一个年轻、已经获得数据的缓存Load：`ROB=2、LQ=2、PA=0x18000、dataValid=1、nc=0`；保持LQ头较老，不提前回收。
3. 再用更老的Load（`ROB=1`）查询同一条缓存行，检查有效RAR响应的`nuke`。
4. 对照分别把年轻Load放到release同拍、隔两拍、隔三拍，并测试`dataValid=0`。

`0x18007`与`0x18000`属于同一条64B缓存行，不要求地址逐字节完全相同。

| release距年轻Load分配的距离 | 正确`nuke`（dataValid=1） | 原RTL表现 |
|---|---:|---:|
| 同拍 | 1 | 1 |
| 前一拍 | **1** | **0，漏报** |
| 前两拍且没有其它相关事件 | **0** | **1，过期事件被算入** |
| 更早 | 0 | 对照为0 |

两个异常方向来自同一个valid错拍，不重复计两个bug。

## 6. 后果与边界

- **已经观察到**：上一拍release应触发的有效RAR冲突被漏报；过期窗口则额外nuke。
- **正确性风险**：应撤销的年轻Load结果没有被要求撤销，失去该条顺序保护。
- **额外重放的性质**：过期nuke主要表现为不必要回滚/性能问题，不能单独把它说成已经证明ISA数据损坏。
- 本报告没有重新运行整核一致性litmus，不把UT结果夸大为完整内存模型验证。

修复应确保地址与valid代表同一个上一拍事件，例如分开定义组合Bundle与寄存字段；还必须复测孤立脉冲、连续脉冲和不同缓存行交错。

## 7. 复现和证据

- [test_release_boundaries.py](../../tests/rar/test_release_boundaries.py)，`test_isolated_release_age_is_exactly_current_or_previous[True-1-0]`。
- 首次失败：有效`response.nuke` **实际False，预期True**。
- 独立探针：[test_public_contracts.py](../../tests/fail_review/test_public_contracts.py)，`test_RAR_release_association_has_the_declared_age_window[True-1-load_queue_rar]`以及距离2的对照失败。
- [裁定JSON](../../results/fail-source-adjudication-01/all-fail-verdicts-v1.json)中查`RAR-REL-001`。

## 8. GitHub：功能PR中出现了覆盖这个代码点的改法

[PR #5507](https://github.com/OpenXiangShan/XiangShan/pull/5507)是“把RAR release源从L1改到L2”的未合并功能PR。其补丁把原来的寄存Bundle改成`Wire`，分别寄存地址和valid，从代码结构上消除了这个双寄存valid写法。

但PR正文没有把它作为“valid错拍bug”明确说明，也没有本地针对本反例的复测记录。因此准确说法是**已有相关未合并改动覆盖此代码点**，不是“该bug已有明确Issue并已修复”。历史`paddrModule`写延迟修复也不是此valid双寄存根因。
