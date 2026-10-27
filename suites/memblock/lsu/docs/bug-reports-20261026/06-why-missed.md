# 为什么没检查到：验证盲区复盘

**结论：7个已确认RTL Bug中，4个的组合已被旧测试实际到达（HWPF、Store tval、S3 kill、matchInvalid），但旧模型给出了同样错误的预期；CBO的CBO/NC两条边分别到达而组合未到达；prefetch.w的写变体未枚举且模型同源；StdExe性能计数器则根本没有可观测端口。** 因此主要根因不是随机测试数量不足，而是**参考模型同源、检查点选错、功能组合缺失、覆盖bin只记录“采样过”**。除StdExe外，其余6个即使只增加断言、仍以旧模型为oracle，也会继续通过。

本复盘绑定固定提交 `893e1580b705d81f113c30c7a05734e09a08050e`，分析对象是上游核查前的 `tests/`、`lsuverify/` 与 `docs/gaps/`，不是事后新测试。

## 1. 先看总表

| Bug | 激励是否到达相关逻辑 | 旧检查器是否检查出错的可观察量 | 旧期望值来源 | 相关功能bin | 主要漏检类型 |
|---|---|---|---|---|---|
| `LSU-HWPF-MISS-001` | 是，性能测试驱动了硬件预取miss | 检查了perf3，但期望0 | 直接复制RTL的互斥条件 | `perf.four_counters` | 同源预期+错误归类为结构死逻辑 |
| `LSU-STORE-TVAL-001` | 是，写回测试同时给了输入VA和TLB fullva | 检查了exceptionInfo.vaddr，但期望输入VA | 模型从S1输入转抄fullva | `e2e.writeback_payload`、`e2e.exception_info_sideband` | 同源预期；测试注释把RTL行为写成合同 |
| `LSU-CBO-NC-AF-001` | CBO和NC分别到达，**组合未到达** | CBO测试不看异常；MMIO测试只看写回 | 模型把`CBO && uncache`统一判AF | `exc.cbo_uncache_faults`只采样IO | 组合缺失+一个代表样本被当成整个等价类 |
| `LSU-S3-KILL-WB-001` | 是，redirect kill测试到达 | 只看pipeOut，未看ldout/intRF/lqWrite | 模型写ldout时没有kill门控 | `kill.current_redirect` | 断言范围不足+同源预期 |
| `LSU-MATCHINV-CAUSE-001` | 是，matchInvalid测试到达 | 只看rollback/pipeOut，未看LQ cause | 模型未让matchInvalid压过replay cause | `rollback.match_invalid` | 断言范围不足+同源预期 |
| `LSU-PREFETCH-W-INTENT-001` | 否，只测了prefetch.i/r | 未检查dcache cmd | 模型只按instrType[2]产生M_PFR | `lane.scalar_prefetch_i/r` | 激励缺失+同源预期+S0无可观察pftCoh |
| `LSU-STD-PERF-001` | 否，计数器没有导出端口 | 无检查 | 无模型 | 无 | 可观测性/范围缺口 |

**关键结论：即使把旧测试的断言数量加倍，只要仍拿旧模型当oracle，6个RTL Bug仍会通过。** HWPF、Store tval、CBO NC、S3 kill、matchInvalid的模型主动期望错误值；prefetch.w的模型也只可能产生`M_PFR`；StdExe计数器没有模型。唯一能靠“多加断言”发现的是StdExe，但它没有端口。

## 2. 同源预期：最深的根因

### 2.1 Store故障tval：测试把错误值写成了合同

固定常量：

```python
VADDR = 0x1000
FULLVA = 0x4000
```

`good_tlb()`默认`fullva=FULLVA=0x4000`，而`stin()`默认`vaddr=VADDR=0x1000`。写回测试却断言：

```python
# exceptionInfo.vaddr is the store's own full virtual address (src+imm),
# not the TLB response's fullva (that one only feeds the unaligned tail).
assert int(nsu.exc["vaddr"].value) == VADDR
```

这不是“没给掩码场景”，而是**输入VA与TLB fullva本来就不同，测试却选择相信输入VA**。参考模型同样在`lsuverify/store_s1/env.py:281`写：

```python
"fullva": pipe_in["fullva"],
```

而TLB返回的`fullva`只用于尾段`tail_fullva`。RTL `NewStoreUnit.scala:473-474`也只把`paddr/gpaddr`写回stage data，`:823`再用`sxData.fullva`产生tval。三者形成闭环：RTL错、模型同错、测试把同错写成注释。

### 2.2 CBO+NC：一个IO样本被推广成“所有uncache都报AF”

模型`lsuverify/store_s2/env.py:115-120`：

```python
is_uncache = is_nc or is_mmio
af = ... or bool(is_cbo and is_uncache) or ...
```

测试只驱动了CBO+IO：

```python
got = run(s2, 1, beat(instr_type=1, is_cbo=1, pbmt=PBMT_IO), "cbo io")
assert got["out_bits"]["uop_exceptionVec_7"] == 1
s2.coverage.sample_case("exc.cbo_uncache_faults")
```

bin名是`cbo_uncache_faults`，语义上覆盖NC和IO两类，但只采样了IO。NC路径在`memtype.nc_from_pbmt_one`和`nc_misaligned_*`里测过，却从未与`is_cbo=1`同时出现。RTL和模型都把`CBO && is_uncache`当成一个整体，于是“IO要报AF”被错误推广到“NC也要报AF”。这是**等价类划分错误**，不是单纯漏一条随机用例。

### 2.3 S3 kill：测试只证明“流水停了”，没证明“没有副作用”

测试`test_redirect_kills_the_beat`只断言：

```python
assert got["pipeOut_valid"] == 0
assert got["detail"]["kill"] == 1
```

而同一拍还有`io_ldout_toRob_valid`、`io_ldout_toIntRf_valid`、`io_lqWrite_valid`。模型在`lsuverify/load_s3/env.py:481-495`计算`ldout_valid`、`int_rf_valid`、`lq_write_valid`时都没有`kill`项，所以即使测试把这些输出和模型比较，也会得到`(1,1,1)`并判为正确。上游#6154的核心正是“kill了但写回仍在”，旧测试与旧模型刚好都停在“pipeOut停了”。

### 2.4 matchInvalid：测试只证明rollback，没证明replay状态被清除

测试只断言：

```python
assert got["rollback_valid"] == 1
assert got["rollback"]["level"] == 1
assert got["pipeOut_bits"]["matchInvalid"] == 1
assert got["pipeOut_bits"]["headAlwaysWriteback"] == 1
```

没有检查`lqWrite.rep_info_need_rep`和13个`rep_info_cause_*`。模型`lsuverify/load_s3/env.py:514`仍按普通cause优先级选择：

```python
cause_src = concat if use_head_replay else pipe
```

没有`matchInvalid`清零分支。上游#5810要求matchInvalid是终结路径，不能在LQ/LRQ建立replay entry；旧测试只验证了“rollback发生了”，没有验证“同时不能有replay”。

### 2.5 prefetch.w：只枚举了i/r，且模型没有写意图

LoadUnitS0测试只覆盖：

- `fu=0x01`：prefetch.i
- `fu=0x03`：prefetch.r

从未使用`fu=0x05`（该提交的prefetch.w）。模型`lsuverify/load_s0/env.py:350,414`：

```python
prefetch = (bits["accessType_instrType"] >> 2) & 1
"dcacheReq_cmd": (prefetch << 1) & 0x1F,
```

只要`instrType[2]=1`就产生`M_PFR=2`，完全不看`pftCoh`。同时S0生成RTL只导出`accessType_instrType`和`accessType_pftType`，没有`pftCoh`；唯一能观察写意图的点是`dcacheReq.bits.cmd`，但旧测试从未检查prefetch的cmd。因此这是**激励缺失+观察点缺失+模型同源**三重问题。

### 2.6 HWPF：已知矛盾，但被归类为“结构死逻辑”

`lsuverify/load_s2/env.py:701-703`直接复制：

```python
self.perf[3] = [int(valid and is_hw_prefetch and not kill and cause[6]), ...]
```

`docs/gaps/load_s2.json`的`LS2-PERF3-CONSTANT-ZERO`甚至写出了`isHwPrefetch`与`troubleMaker`互斥，却把`defect_claim`设为`false`，测试`test_four_performance_counters`也断言`perf3==0`。也就是说，验证过程已经发现了“这个计数器永远为0”，但把“实现上不可能”误当成“规范上应该为0”。这是**错误分类**，不是没看到代码。

### 2.7 StdExe计数器：没有端口，也没有模型

`lsuverify/std_exe_unit/env.py:86-111`只收集`in/out/toRob/atomicData/sqData/feedBack`，没有`io_perf_*`；测试与功能覆盖里也没有`STD_out_of_range_issue`。该计数器不在StdExeUnit的功能接口上，旧UT只验证功能行为，因此完全没有观察点。上游#6653是代码审查发现的；本工程只能在固定源码上补静态契约检查。

## 3. 覆盖为什么显示100%却没发现

### 3.1 “reached”被当成了“checked”

功能覆盖bin由测试显式调用`sample_case()`达标。例如：

- `kill.current_redirect`只要求测试进入kill拍；
- `rollback.match_invalid`只要求进入matchInvalid拍；
- `exc.cbo_uncache_faults`只要求进入某个CBO uncache拍；
- `e2e.exception_info_sideband`只要求exceptionInfo有效。

但bin的达标条件**不要求断言该bin的区分性输出**。测试可以一边`sample_case("kill.current_redirect")`，一边只检查`pipeOut_valid`，于是“kill已到达”被记录，但`ldout/intRF/lqWrite`没被检查。最终548/548普通bin、39/39交叉bin全绿，仍不能推出“每个bin的语义都被独立检查”。

### 3.2 组合空间没有定义

21个covergroup中只有`store_arbiter.payload`有交叉bin（39个），其余20个组的bin是扁平的`case`枚举。以下关键组合没有对应bin：

- CBO × PBMT=NC；
- redirect kill × 写回/RF/LQ副作用；
- matchInvalid × 非零replay cause；
- prefetch.w × DCache cmd；
- 指针掩码后地址 ≠ 输入地址 × Store异常；
- 性能计数器的功能事件。

功能覆盖100%只说明“声明的bin都被采样”，不说明“未声明的组合不存在”。这正是CBO+NC和matchInvalid+cause逃逸的结构性原因。

### 3.3 行/分支/toggle覆盖对“错误表达式”不敏感

这些Bug所在的代码路径都被执行过：

- Store S1写回和exceptionInfo路径；
- Store S2 CBO/uncache异常路径；
- Load S3 ldout/lqWrite路径；
- matchInvalid priority chain；
- prefetch请求和perf3寄存器。

错误发生在“表达式写错”或“少了一个门控”，不是“某行没执行”。行覆盖100%、分支覆盖两侧都走到，也无法发现`M_PFR`应为`M_PFW`、`ldoutValid`少了`!kill`、`lqWriteCause`少了matchInvalid清零。toggle只证明位变化过，不证明变化条件正确。

## 4. 流程层面的原因

### 4.1 参考模型从RTL反推，而不是从规范建立

旧模型的组织方式是“读RTL表达式，再用Python写一遍，然后比较”。这能发现实现与模型不一致，但不能发现“RTL和模型共同误解规范”。本次6个新增Bug中，5个的模型直接复制了错误条件；prefetch.w的模型也天然产生`M_PFR`。**同源模型对实现等价性有效，对架构正确性无效。**

### 4.2 失败 triage 可能把RTL Bug“修”成通过

历史上有多次失败通过调整模型相位、驱动键或预期来消除。缺少当时的逐节点日志，不能逐项判定哪些是验证错误、哪些是RTL错误。但当前代码留下了明显痕迹：

- “TLB fullva只给unaligned tail”的注释；
- “MMIO需要异常才写回”的测试；
- `perf3`被标成结构死计数器。

这些不是中性的遗漏，而是**把观察到的RTL行为写成了合同**。一旦这样做，后续再多样本、再高覆盖都只会强化错误预期。

### 4.3 没有架构级golden/difftest

上游这些问题多由NEMU/Spike全核difftest或特权规范审查发现：tval的指针掩码、CBO在PBMT=NC上的异常、kill后的RF写、prefetch.w的写意图，都是架构/特权语义。旧UT只有模块内参考模型，没有独立ISA/特权规范oracle，也没有全核difftest。模块UT能验证握手和内部时序，但无法自动判断“这个异常该不该报”“这个地址该不该掩码”。

### 4.4 上游问题没有进入回归语料

旧测试的用例清单来自模块功能和RTL阅读，没有把上游Issue/PR作为回归来源。于是：

- #6742已在固定提交后修复，但固定版本没有对应测试；
- #6060、#6154、#5810、#6158、#6653仍open，也没有进入用例；
- #6525这种维护者解释为设计选择的项，也没有被记录为“非Bug”。

没有“上游问题→本地最小复现→普通FAIL”的闭环，漏检就无法被系统性发现。

### 4.5 范围划分把性能计数器排除了

StdExeUnit的UT只把`toRob/sqData/atomicData/feedBack`当功能接口，性能计数器没有导出也没有覆盖。性能Bug不影响功能，但它仍是固定RTL的缺陷；需要在合同中明确“性能计数器也要检查”，或者至少做源码契约检查。否则“功能100%”会掩盖这一类问题。

## 5. 各类问题需要什么检查才能发现

| 漏检类型 | 需要补充的检查 | 本次是否已补 |
|---|---|---|
| 同源预期 | 规范/上游固定的预期表；每个expected标注来源，禁止从RTL反推架构字段 | 部分：6个上游反例已加入，但未全量重构 |
| 断言范围不足 | 对每个操作检查全部架构副作用，不只检查主握手 | 部分：新增kill/matchInvalid/tval反例 |
| 组合缺失 | 功能点×属性/模式的交叉覆盖，而不是扁平case | 未完成：仅新增针对性反例 |
| 编码枚举缺失 | 从decoder枚举全部Zicbop/异常/PBMT编码 | 部分：prefetch.w已补 |
| 无可观测端口 | 导出perf计数器或做固定源码契约检查 | StdExe已补静态检查；其余未做 |
| 覆盖bin只采样不检查 | 每个bin记录reached/checked，checked必须有区分性断言 | 未完成 |
| 架构语义 | 独立golden/全核difftest，或规范推导的expected | 未完成，超出当前UT范围 |

## 6. 已做的修正与仍未解决的部分

已做：

- 新增`tests/upstream_spec/test_upstream_confirmed.py`：5个原生DUT公开端口反例；
- 新增`tests/upstream_spec/test_upstream_static.py`：StdExe计数器源码契约反例；
- 回归`results/upstream-review-regression-02`：589项，**582 PASS / 7 FAIL**，7个FAIL对应7个RTL根因；
- 上游审计`review/upstream_check_20261026_01/audit.json`记录Issue状态、补丁、排除项和源码/RTL哈希。

仍未解决：

- 没有把所有功能bin重构成“规范预期+独立reached/checked”；
- 没有建立全量CBO×PBMT、kill×副作用、matchInvalid×cause、prefetch类×cmd的交叉覆盖；
- 没有全核difftest或独立ISA golden；
- #6678、#6267等未复现项仍是“未确认”，不能当作已排除；
- 历史17次失败缺少逐节点证据，无法完整复盘当时的triage。

## 7. 一句话总结

**这次漏检不是因为测试跑得少，而是因为测试在几个关键点上“问错了问题”：模型复述RTL、bin只记录到达、断言只看主输出、组合空间没有定义、架构语义没有独立oracle。** 要避免下一批同类Bug，必须先把预期来源从“RTL行为”改成“规范/上游可验证语义”，再谈覆盖率和随机强度。
