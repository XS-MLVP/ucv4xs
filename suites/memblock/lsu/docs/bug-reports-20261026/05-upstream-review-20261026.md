# 上游核查：另外确认6个固定版本RTL Bug

**结论：上游核查确认6个此前未被本套UT覆盖的RTL问题，合计已确认RTL Bug为7个。** 全部绑定固定提交 `893e1580b705d81f113c30c7a05734e09a08050e`；没有把上游“已修复”当作固定版本已修复，也没有修改RTL。

上游快照：`kunminghu-v3` HEAD `f85a1f71da8c1522035744c71e2cb266bfed1a7d`，查询时间 2026-10-26。检索了 LoadUnit/StoreUnit/NewLoadUnit/NewStoreUnit/StdExeUnit 的 Issue/PR、相关文件提交历史，并对照固定提交 Scala 与生成 RTL。

## 1. 新增确认的6个Bug

| 编号 | 上游依据 | 模块 | 本工程复现 | 预期→实际 | 是否RTL Bug |
|---|---|---|---|---|---|
| `LSU-STORE-TVAL-001` | #6742，修复PR于2026-10-23合入，晚于固定提交 | StoreUnitS1 / NewStoreUnit | 原生DUT，普通FAIL | 故障tval应为TLB掩码后 `0xff00000080200048`，实际回写 `0xab00000080200048` | **是** |
| `LSU-CBO-NC-AF-001` | #6060，仍open | StoreUnitS2 / NewStoreUnit | 原生DUT，普通FAIL | PBMT=NC的CBO不应报Store AF，实际 `exceptionVec_7=1` | **是** |
| `LSU-S3-KILL-WB-001` | #6154，仍open | LoadUnitS3 | 原生DUT，普通FAIL | redirect kill后 `ldout/intRF/lqWrite=(0,0,0)`，实际 `(1,1,1)` | **是** |
| `LSU-MATCHINV-CAUSE-001` | #5810，仍open | LoadUnitS3 | 原生DUT，普通FAIL | matchInvalid回写应清replay cause，实际 `need_rep=1, cause_4=1` | **是** |
| `LSU-PREFETCH-W-INTENT-001` | #6158，仍open | LoadUnitS0 | 原生DUT，普通FAIL | `prefetch.w`应发 `M_PFW=3`，实际发 `M_PFR=2` | **是** |
| `LSU-STD-PERF-001` | #6653，仍open | StdExeUnit | 固定源码静态检查，普通FAIL | `STD_out_of_range_issue`应统计越界发射，实际条件取反，统计空闲/合法周期 | **是（仅性能）** |

加上此前确认的 `LSU-HWPF-MISS-001`，**总数为7个独立RTL根因**。同一根因的多个上游编号、重复测试和不同种子不重复计数。

## 2. 每个Bug的要点

### LSU-STORE-TVAL-001：Store故障tval未使用指针掩码后的地址

固定源码 `NewStoreUnit.scala:473-474` 只把TLB返回的 `paddr/gpaddr` 写入stage data，没有写入 `fullva`；`:823` 又用 `sxData.fullva` 产生 `exceptionInfo.vaddr`。因此带指针掩码的Store/CBO store page fault会把原始tagged pointer写入 `mtval/stval`。

复现：issue一个有效Store，`stin.vaddr=0xab00000080200048`，TLB返回 `fullva=0xff00000080200048` 且 `excp_0_pf_st=1`；等待写回后检查 `io_exceptionInfo_bits_vaddr`。实际是输入tagged值，不是TLB掩码值。可导致异常软件观察到错误地址；没有声称整核异常处理一定失败。

上游 #6741 是同一根因的Issue，#6742 是修复PR；两者合并为一个Bug。

### LSU-CBO-NC-AF-001：PBMT=NC的CBO被误报Store Access Fault

固定源码 `NewStoreUnit.scala:618-628`：

```scala
val isNC = tlbHit && tlbAccessible && Pbmt.isNC(pbmt)
val isUncache = isNC || isMMIO
val afCboUncache = isCbo && isUncache
val af = ... || afCboUncache || ...
```

CBO的目标页为PBMT=NC时，`isCbo && isUncache` 成立，于是设置storeAccessFault。RISC-V/Spike语义要求CBO继续执行，而不是因PBMT=NC产生访问异常。

复现：CBO store（`fuOpType[0]=1`），TLB `pbmt=1`（NC），等待写回；`stout.exceptionVec_7` 实际为1、预期0。影响CBO在NC内存上的架构行为；修复方向是把NC从CBO的不可缓存访问异常条件中排除，而不是修改测试预期。

### LSU-S3-KILL-WB-001：redirect kill的S3 Load仍驱动写回

固定源码 `NewLoadUnit.scala:1516`、`:1529`、`:1557` 的scalar `ldoutValid`、`ldout.toRob.valid`、`lqWriteValid` 没有 `!kill`；`:909` 的 `kill = io.kill || robIdx.needFlush(redirect)` 只用于另一部分逻辑。向量路径则包含kill门控，scalar与vector不一致。

复现：S3 beat的ROB index=30，redirect target=5（年轻于redirect）；观察 `io_ldout_toRob_valid`、`io_ldout_toIntRf_valid`、`io_lqWrite_valid`。三者实际 `(1,1,1)`，预期 `(0,0,0)`。这是错误路径数据进入RF写总线/LQ的架构副作用；上游报告还给出RF侧信道场景，本报告只确认公开端口行为，不独立证明物理侧信道。

### LSU-MATCHINV-CAUSE-001：matchInvalid回写仍携带replay cause

固定源码 `NewLoadUnit.scala:1561`：

```scala
val lqWriteCause = Mux(useS4HeadReplay, s4HeadReplayCause, cause)
```

没有 `matchInvalid` 优先清零。matchInvalid是终结性poisoned-load路径，应只触发rollback/flush，不应在LQ中建立replay entry；两者同时存在会让正确性依赖后续redirect清理。

复现：S3 beat `matchInvalid=1, cause_4=1, causeOrR=1`；`rollback_valid=1`，但 `lqWrite.rep_info_need_rep=1`、`cause_4=1`。预期 `need_rep=0` 且所有cause为0。

### LSU-PREFETCH-W-INTENT-001：prefetch.w丢失写意图

固定源码 `NewLoadUnit.scala:424`：

```scala
io.dcacheReq.bits.cmd := Mux(isPrefetch, MemoryOpConstants.M_PFR, MemoryOpConstants.M_XRD)
```

所有prefetch都发 `M_PFR`（读意图），没有 `M_PFW`。`prefetch.w` 仍应保留写意图，供TLB/PMP/PMA/DCache权限与副作用检查使用；只读页上的prefetch.w不应被当作读prefetch放行。

复现：LoadUnitS0输入 `fuOpType=0x05`（该提交的prefetch.w编码，ldType=0010、bit0为uopPrefetch），`dcacheReq.valid=1`，实际 `dcacheReq.cmd=2`（M_PFR），预期 `3`（M_PFW）。这是TLB/DCache请求语义缺陷；没有把实际DCache侧效应当作本UT已验证。

### LSU-STD-PERF-001：StdExeUnit越界发射计数器条件取反

固定源码 `StdExeUnit.scala:87`：

```scala
XSPerfAccumulate("STD_out_of_range_issue", !(io.in.valid && s0IllegalIssue))
```

它统计的是“没有越界发射”的所有周期，包括idle；正确条件应去掉取反。上游 #6653 明确为性能计数器修复，不影响功能。该DUT没有把此计数器作为公开端口，因此本工程保留**源码契约普通FAIL**，不伪装成动态DUT观测；不能用功能覆盖100%掩盖。

## 3. 上游问题中不计为Bug或不在范围的项

| 上游项 | 结论 | 原因 |
|---|---|---|
| #6525 | **不是Bug** | 维护者关闭并说明：kill路径Load的训练地址仍应纳入预取器训练；这是性能设计选择，不是功能错误 |
| #6002 | **固定版本不存在该路径** | 固定提交的 `StLdNukeMatchType` 只有Normal/CacheLine，没有Issue中的OctaWord；不能把旧版本逻辑当作本版本反例 |
| #6229 / #6704 | **不计入本套UT Bug** | 根因和修复位于 `NewStoreQueue`/StoreQueue转发；该队列属于本目标明确排除的外部LSQ边界。不是“已证明无Bug” |
| #6678 | **未确认，不冒充已排除** | 上游open且源码相关，但本工程尚未建立独立复现；不计数，也不宣称不存在 |
| #6652 | **不在19 DUT范围** | 根因在Backend/VecIssueQueue的向量STD发射窗口，不是NewStoreUnit端口内的检查 |
| #6267 | **未确认** | PMA缺失导致的全核StoreUnit死锁依赖未在本DUT暴露的uncache/StoreQueue路径；没有本地复现 |
| #6153 | **固定版本前已修复** | 上游PR已合入，固定提交包含修复；没有本地复现 |
| #6741 | **与#6742同根因** | 不重复计数 |

## 4. 执行结果与证据

新回归 `results/upstream-review-regression-02`：

```text
589 items: 582 PASS / 7 FAIL / 0 SKIP / 0 ERROR
19 native builds, coverage_complete=true
```

7个FAIL正好对应7个已确认RTL根因（其中StdExe为源码级检查）。

注意：初次上游回归`upstream-review-regression-01`把prefetch.w写成0x0B，仍得到`cmd=2/预期3`；最终`-02`改用该提交准确的`0x05`编码，结论不变，证据以`-02`为准。新增测试没有用xfail/skip/waiver，也没有改RTL或放宽参考。功能覆盖率数值仍由原548个普通bin+39个cross报告；新增规范/上游检查是**额外测试**，不偷偷并入旧功能bin分母。

证据：

- `review/upstream_check_20261026_01/audit.json`：上游快照、Issue状态、6个新增Bug、排除项、源码/RTL哈希、7个失败节点。
- `review/upstream_check_20261026_01/` 下 `issues-*.json`、`pr-*.json`、`pr-files-*.json`、`commits-*.json`：原始API响应及请求索引。
- `results/upstream-review-regression-02/junit.xml`、`console.log`、`manifest.json`：逐节点失败与运行provenance。
- `tests/upstream_spec/test_upstream_confirmed.py`：5个原生DUT公开端口反例。
- `tests/upstream_spec/test_upstream_static.py`：StdExe性能计数器源码契约反例。

## 5. 边界

- 上游检索是2026-10-26的快照，不是持续监控；之后的新Issue/PR可能改变状态。
- 6个新增Bug的5个有原生DUT动态证据，1个只有固定源码证据（StdExe计数器未导出）；没有把静态证据夸大为动态仿真。
- #6678、#6267等未复现项保留为“未确认”，不加入Bug总数，也不表示已排除。
- 本报告只覆盖三个模块族独立UT范围，不覆盖NewStoreQueue、DCache、LSQ整体或整核；因此不能据此宣称所有上游问题都在本工程复现。
