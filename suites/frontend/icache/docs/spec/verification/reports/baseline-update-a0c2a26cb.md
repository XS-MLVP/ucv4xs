# ICache 新基线适配与回归（public-a0c2a26cb）

本轮把 ICache 工程从 `public-893e1580b` 的旧结论推进到默认基线
`public-a0c2a26cb`（XiangShan `a0c2a26cbe3c862175174bad03a1a23c406315ed`，
DefaultConfig），完成构建、11 个 DUT 冒烟、两次完整回归、上游差分复核、事务边界
迁移和覆盖复核。**不改 RTL，不把旧基线结果重标为新基线结论。**

结论边界：ICache / DefaultConfig / `public-a0c2a26cb` / seed 1 与 seed 2（分别标注）。
本机结果目录不随 Git 发布；机器记录见
[`docs/history/icache-baseline-a0c2a26cb-20261107.json`](../../../../../../../docs/history/icache-baseline-a0c2a26cb-20261107.json)。

## 1. 构建与基线身份

| 项 | 值 |
|---|---|
| 基线 | `public-a0c2a26cb` = `a0c2a26cbe3c862175174bad03a1a23c406315ed` |
| 基线清单 | `baselines/public-a0c2a26cb.json`，sha256 `f7108f95…67f91` |
| 设计/配置 | DefaultConfig，`generation=soc`，`closure=module-dependencies` |
| 源码缓存键 | `f3ac6022d07c5c05d28869ac811f91038f9103677796dd6f051bd1981408be9b` |
| 整芯片生成缓存键 | `d7c6bc4d17651fc1bd92ac39c469410a6bb91215f46c1efcfaf1ec66a72e972d` |
| prepare | `ucv prepare icache --require-unified-baseline` → 11/11 `PREPARED` |
| build | `ucv build icache --require-unified-baseline --jobs 12` → 11/11 `BUILT + SMOKE PASS` |
| 工具锁 | toffee `f571500…`、picker `4dd442c…`、xcomm `2e4a4a9…`（1.1.1，native ABI 3，coverage protocol 5）、verilator 5.052 |

逐 DUT 的 RTL 闭包与 native 产物集合哈希（`rtl_set_sha256` / `native_set_sha256`，
按文件名+内容规约）记录在机器记录中；11 个 DUT 的 `source.json` 与 `build.json` 全部
指向同一 `public-a0c2a26cb` 缓存身份，冒烟均为 `PASS`。source 清单中的
`ICacheWayLookup.sv` 与旧基线**字节相同**（sha256 `6433fed2…b08ce9`）；MSHR、
MissUnit、PrefetchPipe 和整块 ICache 的 RTL 因上游 #6691 变化，见 §2。

## 2. a0c2a26 相对 893e1580b 的 ICache 差分与合同复核

基线区间内 ICache 只有 1 个提交：`4b9f938b7 feat(frontend): enhanced iprefetch
part 1 (#6691)`。它同时改动 FTQ（新增 `PrefetchQueue`/`PrefetchQueuePtr`，
`Ftq`/`Bundles`/`FtqParameters`/`IfuRedirectReceiver`）、`Frontend`、`XSCore`
和 ICache 的六个 Scala 文件。

| 变化 | 对验证的影响 | 判定 |
|---|---|---|
| 删除 ICache 顶层 `io.softPrefetchReq[3]` 和 `softPrefetchValid` 合并逻辑 | 软预取不再由 ICache 选择/合并；FTQ 的 `PrefetchQueue` 以普通 `toPrefetch` 项投递，`source=Sw` | 适配：`ICachePorts` 删除该端口；`soft_prefetch()` 改走 FTQ 预取通道 |
| `PrefetchReqBundle.isSoftPrefetch: Bool` → `PrefetchSource{0=Fdip,1=Sw}` | 端口字段改名/改宽；"是否进入取指流"由 `source.inStream` 表达 | 适配：PrefetchPipe/ICache 绑定与模型改为 `source`；驱动两端口都写 `source` |
| `PrefetchReqBundle.fromSoftPrefetch` 删除，`vSetIdx` 由 FTQ 队列项地址生成 | 旧 `ICACHE-012` 的 stale `vSetIdx` 缺陷源头消失 | **上游修复**：改为普通正向用例（2026-11-08 收口，见 §9.1） |
| `ICacheImp` 的 `req(0)` 替换 + `ready && !softPrefetchValid` 删除 | 旧 `ICACHE-030` 的"合并未接受请求"刺激不再可构造 | **上游修复（接口退役）**：改写为 FTQ `PrefetchQueue` 接口迁移合同，nodeid 保留（2026-11-08 收口，见 §9.2） |
| `ICacheMshr(edge, isFetch, ID)` → `ICacheMshr(edge, id)`，`isFetch` 由 id 派生 | 子模块接口变化；`invalid` 输入改名 `finish` | 适配：`MshrPorts.finish`，语义仍是"完成脉冲释放条目" |
| `ICacheMissUnit` 的 prefetch 仲裁改到 fetch 臂之后，`responseLatency` 直方图迁入 | 端口/层次不变，内部仲裁顺序变化；不影响外部合同 | 无适配（由既有 MissUnit 用例覆盖） |
| `ICache` 的 TileLink `sourceId` 上界改为 `NumAllMshr` | 与 MissUnit 的 14 个 MSHR 一致（0..13） | 无适配（既有 MSHR 来源断言仍成立） |
| `ICachePrefetchPipe` 用 `source.inStream` 替换 `!isSoftPrefetch`；新增 `req(1)` 的 inStream 断言 | 预取写 waylookup、flush 豁免、S1 状态推进的合同不变，但谓词换了名字 | 适配：`PREFETCHPIPE-006/012` 用 `source=Sw` 重述；断言"Sw 不写 waylookup"仍成立 |
| 软预取端口从 ICache 移到 FTQ | `ICACHE-029` 的"每个 LDU 端口"义务转到 FTQ 队列；ICache 侧只剩一个 Sw 预取通道 | 适配：保留 nodeid，测试改为固定"ICache 不再暴露 per-LDU 引脚 + 队列项取指正确" |

`WAYLOOKUP-020` 的 RTL 未变（整文件字节相同），仍是真实缺陷，保持 strict XFAIL。
FTQ 新增队列的 DUT 不在本工程范围内；本轮不把 FTQ 队列的行为写成 ICache 结论。

## 3. 完整回归与逐 nodeid 对账

| 运行 | 目录（本机，忽略） | seed / workers | source（前后） | 节点 | 判定 |
|---|---|---|---:|---|---|
| 旧权威 | `results/ucv-collaboration-checkpoint-icache-full-20261102` | 2 / 2 | `b48dc54b…` | 570 | 567 PASS / 3 XFAIL |
| 上一轮 seed 1 | `results/ucv-icache-a0c2a26cb-final4-seed1-20261107` | 1 / 8 | `0476d335…`（前后一致） | 571 | 568 PASS / 2 XFAIL / 1 XPASS |
| 上一轮 seed 2 | `results/ucv-icache-a0c2a26cb-final4-seed2-20261107` | 2 / 8 | `0476d335…`（前后一致） | 571 | 568 PASS / 2 XFAIL / 1 XPASS |
| **收口 seed 1** | `results/ucv-icache-close2-seed1-20261108` | 1 / 8 | `094d3388…`（前后一致） | 573 | **572 PASS / 1 XFAIL**，exit 0 |
| **收口 seed 2** | `results/ucv-icache-close2-seed2-20261108` | 2 / 8 | `094d3388…`（前后一致） | 573 | **572 PASS / 1 XFAIL**，exit 0 |

573 = 原 571 个硬件节点 + 2 个 `scoreboard/` selftest（ICACHE-012 红/绿对照，见 §8），
selftest 不计硬件功能点；`feature-points` 仍为 142/142。

同源码两次完整回归的逐节点判定完全相同。对账（上一轮 571 → 收口 573，硬件节点
571 个一一对应）：

- **删除 0**；571 个硬件节点全部保留（新增的 2 个是 selftest，不是硬件点）。
- **判定变化 2**（收口轮，见 §9）：
  `test_software_prefetch_warms_the_requested_line` `XPASS → PASS`（去掉 strict 标记，
  缺陷已由上游 #6691 修复）；`test_pending_soft_prefetch_does_not_process_an_unaccepted_ftq_issue`
  `XFAIL → PASS`（改写为 FTQ `PrefetchQueue` 接口迁移合同，见 §9.2）。
- **判定不变 569**：其余全部 PASS / XFAIL 原样保留。

三个标记的最终处置（2026-11-08）：

| 功能点 | 节点 | 最终状态 | 依据 |
|---|---|---|---|
| `ICACHE-012` | `test_software_prefetch_warms_the_requested_line` | **PASS**（普通正向用例） | 上游 `4b9f938b7`（#6691）删除 stale `vSetIdx` 寄存器与顶层合并；红/绿对照保留在 `tests/icache/scoreboard/test_hint_install_control.py` |
| `ICACHE-030` | `test_pending_soft_prefetch_does_not_process_an_unaccepted_ftq_issue` | **PASS**（接口迁移合同） | 承接方为 FTQ `PrefetchQueue`；ICache 侧义务改写为"未完成握手的预取 issue 不得触达内存"，nodeid 保留 |
| `WAYLOOKUP-020` | `test_flush_in_the_write_cycle_discards_the_entry_and_its_exception` | **XFAIL（strict，真实缺陷）** | `ICacheWayLookup.sv` 与旧基线字节相同；缺陷文档 `docs/bugs/open/waylookup-flush-cancelled-write-exception.md` |

收口回归为 **572 PASS / 1 XFAIL，exit 0**；唯一非 PASS 是仍有真实 RTL 缺陷的
`WAYLOOKUP-020`。原失败记录（旧基线的 3 个 XFAIL、`ICACHE-030` 的合并缺陷、两次
XPASS）继续保留在本文件 §2/§3、`docs/spec/verification/error-review.md` §1.1–§1.4 与历史机器记录中，
未重标。

## 4. 事务边界迁移（其余 9 个 DUT）

迁移前静态审计：ICache 工程 `owner infrastructure/private-helper` **329** 处
（icache 80、prefetchpipe 94、waylookup 41、dataarray 31、missunit 23、metaarray 20、
mshr 17、replacer 17、mainpipe 6）。本轮把这 9 个 DUT 的功能用例迁移到 agent 的
公开事务 API：

- **时钟/输入**：`tick()`、`set_csr_pf`、`set_pmp`、`set_miss_ready`、
  `set_meta_ready`、`set_flush`、`set_bpu_flush`、`set_wfi`、`set_acquire_ready`、
  `set_redirect_flush`、`set_fencei`。
- **碰撞场景事务**：`complete_while_flushing()`（MSHR finish×fence.i 同拍）、
  `refill_while_flushing()`（MetaArray 回填×flushAll）、`issue_read()`/
  `begin_write()`/`finish_write()`（DataArray 读与写竞争）、
  `begin_ecc_injection(fencei_delay=…)`（ECC 注入×整行清扫）。
- **有类型观测/期望**：`expect/commit_expectation/is_resident/resident_way/
  expected_victim/record_hint_fill`、`memory_idle()`、`next_write_slot()`/
  `next_read_slot()`/`resident_count()`、`slot1_code()`、`miss_request_block()`/
  `miss_request_vset()`、`published_leaves()` 支撑的 `has_published_port()`。
- **几何信息**：`set_count`/`way_count`/`bank_count`/`fetch_mshr_count`/
  `prefetch_mshr_count`/`depth` 由 DUT 合同提供，测试不再读 `agent.model`。

迁移后 **329 → 6**；剩余 6 处全部在 `ICACHE-030` 的**不可达**测试体（测试先
`pytest.xfail` 再引用旧 `softPrefetch` 刺激）。收口轮把该测试体改写为 FTQ 接口
迁移合同并改用公开 API（`soft_prefetch` / `present_prefetch_issue` /
`ftq_pref_ready` / `drop_fetch` / `tick`），**6 → 0**；ICache 行的静态事务边界
由 `needs-adapter` 变为 `no-static-leak-found`。

迁移同时把三处"只断言参考模型、可空转"的检查改为 RTL 可观测断言：

- MissUnit：`model.entries[source].valid/issued` → 发布合同 `wfi_safe()`；
- WayLookup：填队列循环由 `model.write_ready()` 改为 RTL `write.ready`，异常停顿
  断言也落在 RTL 电平上；
- MSHR：way 捕获只通过 `info.way` 断言，不再读 `model.state`。

边界：569 个原节点在同源码下判定不变；没有改 RTL、没有删除/放宽检查。收口轮
ICache 行已无 pin/signal/owner 债务；**全仓** `--require-transaction-boundary` 仍
exit 1，原因是其他工程既有债务（BPU 24、LSQ 121、MMU 53、DCache 2+87、LSU 140、
VAGQ 179+9+32），本轮按约束未改动它们，因此不声称全仓事务闭合。

## 5. 覆盖复核（line / branch / toggle）

工具：`tools/coverage_breakdown.py`（原生点，三类分开统计）与
`tools/coverage_ledger.py`（整块未覆盖点与字节相同子模块 DUT 对账）。口径不变：
只排除 picker 生成的 `*_top` 测试台封装，不剔除 payload/存储/分母。

运行：`results/ucv-icache-a0c2a26cb-final4-seed1-20261107/icache`（seed 1）。

| DUT | line | branch | toggle |
|---|---|---|---|
| waylookup | 227/227 = 100% | 667/796 = 83.79% | 10283/10382 = 99.05% |
| replacer | 515/515 = 100% | 3845/4102 = 93.73% | 3238/3248 = 99.69% |
| mshr | 2/2 = 100% | 7/8 = 87.50% | 654/666 = 98.20% |
| databank | 7/7 = 100% | 44/46 = 95.65% | 6641/6822 = 97.35% |
| metabank | 10/10 = 100% | 301/304 = 99.01% | 12415/12672 = 97.97% |
| metaarray | 19/19 = 100% | 591/602 = 98.17% | 25843/26786 = 96.48% |
| dataarray | 32/32 = 100% | 322/334 = 96.41% | 50266/52852 = 95.11% |
| missunit | 33/33 = 100% | 282/298 = 94.63% | 16229/16770 = 96.77% |
| mainpipe | 5/5 = 100% | 155/156 = 99.36% | 13941/14240 = 97.90% |
| prefetchpipe | 3/3 = 100% | 140/142 = 98.59% | 5554/5758 = 96.46% |
| **icache（整块）** | 788/854 = 92.27% | 5514/6480 = 85.09% | 91200/139880 = 65.20% |

整块未覆盖 ledger（seed 1）：

| 类 | line | branch | toggle |
|---|---:|---:|---:|
| 未覆盖 | 66 | 966 | 48680 |
| 由字节相同子模块 DUT 覆盖 | 64 | 530 | 35470 |
| 开放 | 2 | 436 | 13210 |

逐类归因：

1. **line 66 = 64 + 2**：64 条是 `ICacheWayLookup.sv` 逐槽 `elsif` 行点，与
   `waylookup` 单模块 DUT 字节相同且已被其 100% 行覆盖；2 条是
   `ICacheCtrlUnit.sv` 159/161 的死代码（注入写分支与 `deq_bits_read` 互斥）。
2. **branch 436 开放**：257 条 Replacer 优先级 mux 最终 `else`、129 条 WayLookup
   同类 `else`、8 条取指 MSHR 2/3 仲裁臂、3 条 CtrlUnit 等待臂、其余 39 个文件
   各有 1 条 `initial` 复位 `else`/声明臂。前四类与旧基线的归因一致，本轮未新增
   开放点。
3. **本轮闭合 1 条**：`ICacheCtrlUnit.sv:204`（注入请求阶段 `metaRead.req.ready=0`
   的等待臂），由新用例 `test_ecc_injection_waits_for_the_arrays_across_a_flush`
   在 fence.i 整行清扫期间发起注入覆盖。整块 branch 开放点 437 → 436。
4. **仍开放**：CtrlUnit 184/209（写阶段数组忙）与 234（注入启动/保持臂）。184/209
   需要"控制单元进入写状态时数组写就绪为低"；本配置下数组写就绪只在逐行清扫时
   为低，而清扫同时使目标行失效，注入实际以 NotFound 终止，因此未能在该状态呈现。
   这是当前刺激可达性的缺口，不是从分母剔除；没有用"不可达"改写为已闭环。
5. **toggle**：开放 13210 条中约 12.6k 是 payload/存储位（宽地址/数据总线、每个
   MSHR 实例一份副本、SRAM 宏），与旧分析同一性质；control 位剩余约 300 条集中在
   FTQ 属性、BPU s2/s3 flush 组合、第二读槽 bankSel 高位和 CtrlUnit 的寄存器映射
   输入位，未补新用例。

**seed 效应必须分开看**：旧权威运行是 seed 2。同 seed 2 下整块 branch 为
5258/6480（新）对 5265/6488（旧，点集因 RTL 变化不同）；seed 1 的 5514/6480 多出的
256 条是随机用例在 Replacer 第二 touch 端口上的刺激差异。因此"branch 覆盖大幅提高"
不能归因于新基线或本轮迁移；本轮可归因的覆盖变化只有 CtrlUnit:204 一条。

## 6. 变更文件

工程代码（未改 RTL）：

- `suites/frontend/icache/mshr/{bundle/ports.py,agent/main.py,model/mshr.py}`：
  `invalid → finish`（上游改名），新增 `tick/set_wfi/set_acquire_ready/
  complete_while_flushing`。
- `suites/frontend/icache/prefetchpipe/{bundle/ports.py,agent/main.py,model/prefetchpipe.py,transaction/types.py}`：
  `source` 枚举替换 `isSoftPrefetch`；新增 `tick/set_meta_ready/set_miss_ready/
  set_csr_pf/set_pmp/set_flush/set_bpu_flush/present_miss_response/
  clear_miss_response/miss_request_{block,vset}`。
- `suites/frontend/icache/icache/{bundle/ports.py,agent/main.py,case/definitions.py}`：
  删除 `softPrefetchReq` 绑定；软预取改走 FTQ 通道；新增 §4 的公开 API、
  `begin_ecc_injection`、`published_leaves` 支撑的端口查询。
- `suites/frontend/icache/{replacer,waylookup,missunit,metaarray,dataarray,mainpipe}/…`：
  新增几何/状态查询与碰撞事务 API；Replacer 的端口/组译码发布在
  `replacer/transaction/types.py`，MissUnit 的 MSHR 几何发布在
  `missunit/transaction/types.py`。
- `suites/frontend/icache/ports/bindings.py`：`published_leaves()`。
- 测试：`tests/{icache,prefetchpipe,waylookup,missunit,mshr,replacer,metaarray,dataarray,mainpipe}/…`
  迁移到公开 API；新增 ECC×flush 用例；`ICACHE-029` 按新接口重述（nodeid 保留）；
  其余功能点与断言不放宽。

文档与记录：

- 本文件、[`docs/history/icache-baseline-a0c2a26cb-20261107.json`](../../../../../../../docs/history/icache-baseline-a0c2a26cb-20261107.json)、
  `docs/status.md` 的 ICache 段、`README.md`、`docs/spec/verification/error-review.md` 与
  `docs/spec/verification/coverage/icache-coverage-closure.md` 的本轮追加。

收口轮（2026-11-08）新增/修改：

- `icache/agent/main.py`：新增 `present_prefetch_issue()`（只驱动预取通道、
  不等握手），供 ICACHE-030 合同使用。
- `tests/icache/testcase/test_prefetch_wfi_ecc.py`：ICACHE-012 去掉 strict 标记；
  ICACHE-030 改写为接口迁移合同。
- `tests/icache/scoreboard/test_hint_install_control.py`（新）：ICACHE-012 红/绿
  对照 selftest（2 项）。
- `docs/bugs/open/waylookup-flush-cancelled-write-exception.md`（新）：WAYLOOKUP-020
  最小复现、RTL 根因、影响评估。
- `verification_plan.json`：ICACHE-012/030 描述同步为最终合同。
- [`docs/history/icache-close-open-items-20261108.json`](../../../../../../../docs/history/icache-close-open-items-20261108.json)（新）：
  收口轮机器记录。

## 7. 残余与尚未验证

收口后的明确状态：

- `ICACHE-012` 为正向用例（上游 #6691 已修），`ICACHE-030` 为 FTQ 接口迁移合同
  （承接方 `PrefetchQueue`），`WAYLOOKUP-020` 保持 strict XFAIL（真实缺陷）。
- ICache 行事务审计 0 处 owner/pin/signal 债务；全仓门禁因其他工程债务仍 exit 1，
  未声称全仓闭合。
- CtrlUnit 184/209 已给出源码级守卫证明（读/写 ready 同源，见 §9.4）；234 是
  `initial` 块的 reset `else`。三者保留为开放点，不从分母剔除。
- toggle 13210 条已分为 payload 10286、control 262、other 2654、storage 8；未用
  非法激励刷翻转。
- FTQ 新增 `PrefetchQueue` 的入队仲裁、容量和 source 语义不属于本工程；本轮只按
  FTQ 已发布接口适配，没有验证 FTQ 侧行为。
- 覆盖结论绑定 seed 1/seed 2、`public-a0c2a26cb`、DefaultConfig 和本机工具锁；
  换 seed 或工具版本需要重测，不能直接外推。
- 本轮未 push；本机 `results/` 不随 Git 发布。

## 8. ICACHE-012 模型补全的针对性红/绿对照

`ICACHE-012` 的 XPASS 必须是"有区分度"的结果，而不是断言空转。最初用临时对照
（运行后删除）验证：

- **绿对照**：预取 0xB000（set `0xC0`），把"提示行安装到自身地址命名的组"记录进
  参考模型，再发需求取指 → 无 acquire，PASS。
- **红对照**：同样的预取，但把提示行记录到旧缺陷的 stale 组 `0`，再发需求取指 →
  模型预测 block 704 需要回填，而 DUT 命中；断言失败（`model expected refills for
  [704], observed [(704, 4)]`）。

因此 XPASS 反映的是"RTL 命中、模型按正确组预测"，不是两边一起放行。

收口轮把这两条对照固化为 `tests/icache/scoreboard/test_hint_install_control.py`
（`selftest`，纯模型，不占硬件点、不改 RTL）：

- `test_green_control_hint_in_its_own_set_is_resident`：安装到自身组后命中；
- `test_red_control_hint_in_the_stale_set_is_not_resident`：安装到 stale 组 0 后，
  在自身组查询必须为 miss。

这样即使将来重新引入 stale 组行为，正向用例与对照会同时给出可审计的失败。

## 9. 收口轮（2026-11-08）

本轮只动验证侧：测试、agent/绑定、文档。未改 RTL/Scala/生成产物/基线/工具锁，
未向上游提交任何内容，未 push。

### 9.1 ICACHE-012：转正向用例

- 删除 `@pytest.mark.xfail(strict=True, ...)`，保留 `@pytest.mark.feature` 和全部
  断言；nodeid 不变。
- 依据：上游 `4b9f938b7`（#6691）删除了 `softPrefetch_vSetIdx_0` 的 stale 寄存器
  读取和 ICache 顶层选择；FTQ `PrefetchQueue.fromPrefetchQueueEntry` 用队列项
  自身地址生成 `vSetIdx`。
- 红/绿对照从临时探针固化为
  `tests/icache/scoreboard/test_hint_install_control.py`（见 §8）。
- 运行：`results/ucv-icache-close2-seed1-20261108`、
  `...-seed2-20261108`，两种 seed 均 PASS。

### 9.2 ICACHE-030：接口迁移合同（选 (b)）

- 承接方确认：`Ftq.scala` 把 `io.softPrefetch` 入 `PrefetchQueue`，
  `PrefetchQueue.scala` 是多入单出队列，`ICacheImp` 直接
  `prefetcher.io.fromFtq <> io.fromFtq.toPrefetch`。
- 旧"合并未接受请求"刺激不再可构造；保留 nodeid
  `test_pending_soft_prefetch_does_not_process_an_unaccepted_ftq_issue`，改写为
  ICache 侧仍成立的合同：**FTQ 预取通道未完成握手时，其任何 block 不得触达内存**。
- 刺激合法：用 ITLB miss 把预取管道占住，再在 `fromFtq.toPrefetch` 上保持
  `valid=1` 而 `ready=0` 24 拍（合法背压），断言这 24 拍内 0 次 acquire、且
  `ready` 始终为 0；随后释放并排空。
- 事务审计：该测试体原 6 处 owner 访问（`soft_driver`×2、`_pref_payload`×1、
  `ftq_pref_driver`×2、`ports`×1）全部改为公开 API，**6 → 0**。
- 原缺陷记录保留：`docs/spec/verification/error-review.md` §1.2、本文件 §2、旧机器记录。

### 9.3 WAYLOOKUP-020：真实缺陷文档

- 保持 strict XFAIL，未转正、未改 RTL。
- 新增缺陷文档
  `docs/bugs/open/waylookup-flush-cancelled-write-exception.md`：最小复现
  (`test_flush_in_the_write_cycle_discards_the_entry_and_its_exception`)、
  RTL 根因（`_GEN_83` 未与 `io_flush` 相与，`write.ready` 被
  `exceptionEntry_valid` 压住）、影响评估（空队列拒写；整块 ICache 中因
  `~s1_flush` 门控不可达）和证据。
- 缺陷修复决定交回用户；本轮没有上游 issue/PR/patch。

### 9.4 CtrlUnit 184/209/234 与源码级守卫

尝试过的合法组合：

1. **注入 × fence.i 整行清扫**：`test_ecc_injection_waits_for_the_arrays_across_a_flush`
   在注入的读/写相位附近多个 offset 拉 fence.i。闭合了
   `ICacheCtrlUnit.sv:204`（读等待臂），但 184/209 仍为 0。
2. **注入 × 复位后 SRAM 清扫**：临时探针在 `reset(sweep=8)` 后立即注入并保持到
   状态终止。读等待臂 (`204 else`) 计数 114，184/209 仍为 0。

源码级守卫（`public-a0c2a26cb` 的 `SRAMTemplate.sv` 与 `ICacheCtrlUnit.sv`）：

- `io_read_req_ready_0 = ~_resetState & ~io_w_req_valid`（SRAMTemplate:100）
- `io_w_req_ready = ~_resetState`（SRAMTemplate:185）
- `_resetState` 只在 `reset` 时置 1（:103），128 行清扫完后清零（:108），之后不再置位。
- CtrlUnit 只有在状态 2 且读握手完成后才进入写状态（`iState <= 3/4`）；
  写状态 3/4 的 `_GEN_4` 就是对应数组的 `write.ready`。
- 因此"进入写状态时写就绪为低"要求 `_resetState=1`；但同一信号也把读就绪拉低，
  读握手无法完成，FSM 到不了写状态；若在窗口内重新 reset，CtrlUnit 自身也被复位到
  `iState=0`。结论：**184/209 在本配置结构不可达**，不是缺用例。
- **234** 是 `initial` 块里的 `if (reset)`，其 `else` 在时刻 0 不可达，属于
  initial-reset else，不是写等待臂。

### 9.5 branch 436 的四类结论

| 类别 | 条数 | 结论 |
|---|---:|---|
| Replacer 优先级 mux 最终 `else` | 257 | 外层 OR 已保证至少一个 valid，构造不可达；第二 touch 端口的随机刺激差异只影响已覆盖臂，见 §9.6 |
| WayLookup 同类 mux `else` | 129 | 同上；`updated = pTagSame \| waySame` 约束下最终 else 矛盾 |
| 取指 MSHR 2/3 仲裁臂 | 8 | 一个取指 issue 最多两行且 main pipe miss 前阻塞，取指 MSHR 只占 0/1 |
| CtrlUnit 写等待臂 | 2 | 184/209，源码守卫证明不可达（§9.4） |
| `initial` 块 reset `else` | 40 | 时刻 0 reset 恒为 1；含 CtrlUnit:234 与 `ICacheDut.v:839` 包装寄存器 |

合计 257+129+8+2+40 = **436**，与 ledger 一致。没有把可执行缺口改写成"不可达"。

### 9.6 toggle 13210 的分类

| 类 | 条数 | 说明 |
|---|---:|---|
| payload | 10286 | 宽地址/数据总线、每个 MSHR 实例一份副本、SRAM 宏数据位；结构化测试不会翻遍每一位 |
| other | 2654 | 分类器未命中的信号名（属性/控制混合），未从分母剔除 |
| control | 262 | FTQ 属性（`hasSatpFlush`、`req_1_taken`、`bankSel_1` 高位）、BPU s2/s3 组合、第二读槽 bankSel、CtrlUnit 寄存器映射输入位等 |
| storage | 8 | SRAM 宏内部位 |

没有用非法激励刷翻转；control 位的剩余项按"某个合法输入组合尚未驱动"登记，不当作
不可达。

### 9.7 双 seed 与同 seed 对比

| 对比 | branch | 说明 |
|---|---|---|
| 收口 seed 1 | 5514/6480 | 随机用例在 Replacer 第二 touch 端口多触发的刺激 |
| 收口 seed 2 | 5258/6480 | 与上一轮 seed 2 相同 |
| 上一轮 seed 2 | 5258/6480 | 点集因 RTL 变化与旧基线不同 |
| 旧基线 seed 2 | 5265/6488 | 旧点集 |

seed 1 与 seed 2 的差异逐点检查仍全部是 `ICacheReplacer.sv` 的 256 条第二 touch
端口臂（外加 `MainPipeDut.v` 1 条）；因此 **seed 1 的 256 条增量是随机刺激差异，
不是基线或收口收益**。收口轮本身没有改变覆盖分子分母（除 §9.4 的 204 已在上一轮
闭合）。

### 9.8 收口命令与结果

```sh
.venv/bin/ucv run icache --workers 8 --seed 1 --require-unified-baseline \
  --output results/ucv-icache-close2-seed1-20261108
.venv/bin/ucv run icache --workers 8 --seed 2 --require-unified-baseline \
  --output results/ucv-icache-close2-seed2-20261108
.venv/bin/python suites/frontend/icache/tools/coverage_breakdown.py \
  results/ucv-icache-close2-seed1-20261108/icache
.venv/bin/python suites/frontend/icache/tools/coverage_ledger.py \
  results/ucv-icache-close2-seed1-20261108/icache
```

结果：572 PASS / 1 XFAIL，源码 `094d3388…` 前后一致，nodeid 571 个硬件节点一一
对应（另加 2 个 selftest）；feature-points 142/142。
