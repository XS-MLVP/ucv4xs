# DCache 用例可信度复核（按 KMH-v3 假阴性经验，2026-10-26）

> 依据：[跨模块假阴性总结](../../../../../docs/lessons/false-negatives-20261026.md) 与
> [防复发手册](../../../../../skills/rtl-verification-soundness/SKILL.md)（P01–P12）。
>
> 本文只做“已有用例是否真的检查了它声称的东西”的复核，并给出成对证据。
> 结论绑定 `results/soundness-recheck-03`（210 passed + 3 xfailed / 219.28 s）、
> RTL 哈希 59/59 一致、seed 1。

---

## 1. 一页结论

上一轮我交付的是“覆盖率 98.2%、功能组 100%”。按经验文档复核后，**覆盖率本身没有错，
但有 11 处用例并没有检查它名字/注释所声称的语义**。这些是验证缺口，不是 RTL 缺陷；
修正后用例数 209 → 210（新增一个），通过数 210，RTL 行为结论不变。

| 类别（对应经验） | 发现 | 性质 |
|---|---|---|
| P09 死检查 | 3 个用例有断言但断言与名字无关（MSHR 耗尽、release 槽位、mask 矩阵） | 确认验证问题 |
| P09/P03 陈旧值 | `test_three_lanes_same_line` 的“三 lane 并发”可以用陈旧响应通过 | 确认验证问题 |
| P03 过严 + 假合同 | 128-bit 比较 + 注释“mask 只影响 LSU 消费”，与 RTL 相反 | 确认验证问题 |
| P10 无观察点 | 6 个功能性输出从不被读（含 AMO 复位的 word_idx/amo_cmp/req_coh） | 确认验证问题 |
| P08 静默超时 | 4 个 driver 超时返回 0/None 而不失败 | 确认验证问题 |
| P06 区分性 | 8/8 成对注错实验通过（注错必须 FAIL，未注错必须 PASS） | 新增门禁 |
| P11 XFAIL | 3 个 xfail 解遮罩后都精确失败在同一条数据断言上 | 复核通过 |
| P04/P05 | 预取标记清除原来靠覆盖率推断；现在由 `meta_prefetch` 端口直接断言 | 增强 |

**新发现的两个真实契约细节**（之前写错，现在由端口固定）：

1. 预取标记清除后的值是 `L1_HW_PREFETCH_CLEAR = 1`，**不是 0**；`isDemand(v) = v <= 1`。
2. 执行清除的那一次命中仍观察到旧值；且清除被 CounterFilter 的 4 拍窗口抑制——
   同一 line 连续访问不会重复清除。

---

## 2. 三个新门禁（不靠记忆，靠工具）

| 门禁 | 入口 | 判据 | 当前结果 |
|---|---|---|---|
| 收集/定义审计（P09） | `tools/audit_test_soundness.py` | 定义数 vs 收集数、重名、注释中的 def、恒真断言、`except: pass`、无断言用例是否在允许清单内 | 187 定义 → 212 收集（25 个是 wrapper 复用 DCache 用例），0 重名，0 恒真，17 个委托断言且全部登记 |
| 输出观察审计（P10） | `tools/audit_output_fields.py` + `dcacheverify/common/pin_trace.py` | 运行时记录 bench 到底读了哪些 pin，与 RTL output 端口求差 | 产出 `manifest/output-field-audit.json`；剩余未读端口按桶给出理由 |
| 检查器灵敏度（P03/P06） | `tools/selfcheck_checkers.py` + `tools/mutation_lib.py` | 每个 DUT 一组“注错必须 FAIL / 不注错必须 PASS” | **8/8 sensitive**，产出 `manifest/checker-selfcheck.json` |

第三项是本轮最关键的证据：它回答的不是“用例跑过没有”，而是“**把 oracle 故意改错，用例
会不会红**”。8 组覆盖 7 个 DUT（BDA / CounterFilter / DTA / MissQueue / LoadPipe /
MainPipe / DCache×2）。

---

## 3. 逐项发现与修正

### 3.1 P09：三个“有断言但没检查名字所说内容”的用例

**F1 `test_mshr_full_yields_unhandled_miss`**
注释写“三条 lane 必须都报 unhandled”“store 必须走 replay”，实际两条都没有 assert，
只是采样了覆盖率。若三条 lane 全部 `handled=1`，或用 store 拿到 hit，用例照样绿。

修正：断言三条 lane 的 `miss==1 && handled==0 && nack_any==1`；断言 store 的
`replay==1 && hit==0 && replay_id==11`。

**F2 `test_release_slots_one_to_three`**
整个用例没有任何断言。MSHR 槽位不释放也照样通过。

修正：断言 `refill_info` 存在且 mask 全 1；释放后新请求的 `source == miss_id`
（槽位 0..N-1 仍占用，只有 N 释放了才会拿到 N）。

**F3 `test_mask_class_matrix`**
36 组 `(wmask, dup_valid)` 只写不读，等于没验证掩码语义。

修正：每组写完立即 `read_port`，由模型比对整窗。

### 3.2 P09/P03：`test_three_lanes_same_line` 可以用陈旧响应通过

它记录了 `spawned` 但从未断言；数据比对读的是响应寄存器，而响应寄存器保存的是
**上一次事务**。如果某条 lane 从未 fire，它保留的是同一条 line 的旧值 → 断言成立。

修正：
1. 先在三条 lane 上各读一次**另一条 line**作为陈旧标记，并断言标记已锁存；
2. 断言 `spawned == [True, True, True]`；
3. 只比对被掩码覆盖的 8 字节（见 3.3）。

### 3.3 P03：128-bit 全窗比较 + 一条与 RTL 相反的注释

RTL 事实：`io.banked_data_read.bits.bankMask = byteMaskToBankMask(vaddr, mask)`，
数据阵列**只刷新被选中的 bank**，其余 bank 保留上一次锁存值；响应是 16B 对齐窗口，
被刷新的字节保持窗口内原始偏移。

原代码：
- `test_load_mask_shapes` 注释写“响应总是返回整窗新鲜，mask 只影响 LSU 消费”——与 RTL 相反；
- 多个用例把 128 bit 整体与 `line[0:16]` 比较。它们能过，是因为**上一次读恰好是同一窗口**，
  属于“偶然正确”，一旦前面插一次别的访问就变红（我在三 lane 用例里就遇到了）。

修正：新增 `window_bytes(response, addr, nbytes=8)` 与 `line_bytes()`，只比对被覆盖的
字节；`test_load_mask_shapes` 改为“先锁存另一条 line，再按 mask 比对被覆盖字节”，
并把真实契约写进功能点 `DC-FP-002`。

### 3.4 P10：6 个功能性输出从未被读

用运行时 pin trace 对比 RTL output 端口（`manifest/output-field-audit.json`）：

| DUT | 输出数 | 被读 | 从未被读 |
|---|---:|---:|---:|
| DuplicatedTagArray / CtrlUnit / MissReadyGen / CounterFilter / MissTrack / BankedDataArray | 19/74/63/3/6/94 | 全 | **0** |
| ProbeQueue / WritebackQueue | 12 / 28 | 7 / 23 | 5 / 5（全是 perf） |
| LoadPipe | 83 | 27 | 56 |
| MainPipe | 902 | 133 | 769 |
| MissQueue | 290 | 81 | 209 |
| DCache / DCacheWrapper | 412 / 412 | 82 / 139 | 330 / 273 |

真正**功能性**且未读的项已修：

- MainPipe `miss_req` 的 `vaddrAlias` / `vaddrSet` / `word_idx` / `amo_cmp` / `req_coh`
  ——AMO miss 要靠它们复位到正确的字与比较值。原来只查了 `addr/amo_data/amo_mask/cmd`。
  修正：`test_amo_miss_request_and_replay` 改用 `word_idx=2, amo_cmp=0x1234, vaddr=0x4A40`，
  断言五个字段（alias/set 用独立的 `dcache_alias` / `dcache_index` 计算）。
- DCache `io_mshr_store_empty`——store miss 期间必须为 0、refill 完成后为 1。
  修正：`test_store_miss_with_refill` 三处断言。
- DCache `io_lsu_load_*_resp_bits_meta_prefetch`——直接观测预取标记。
  修正：预取用例断言“首次命中=2（STRIDE）、清除后下一次命中=1（CLEAR）”。
- MissQueue `io_full`——16 项占满必须为 1、第 17 笔必须 `ready=0`。
  修正：新增 `test_mshr_full_flag_tracks_free_entries`。
- DCache `io_lsu_load_*_s2_mq_nack`——`handled=0` 时必须出现过 nack。
  修正：`load_once` 在流水里对 nack 求或，MSHR 用例断言。

剩余未读端口全部登记在 `manifest/output-field-audit.json` 的 `needs_decision` 与桶计数里，
理由见第 6 节。

### 3.5 P08：四个 driver 超时静默返回

| helper | 原行为 | 现行为 |
|---|---|---|
| `DcacheEnv.wait_store_hit` | 超时返回全 0 dict（与“响应为 0”不可区分） | 抛 `AssertionError`，带 offered id/ready |
| `DcacheEnv.wait_atomic_response` | 返回 `None` | 抛错（`optional=True` 才返回 None） |
| `DcacheEnv.wait_wakeup` | 返回 `False`；无该端口时返回 `True` | 无端口即报错；超时抛错 |
| `DcacheEnv.complete_cmo` | 返回 `None` | 抛错（`optional=True` 才返回 None） |
| `MissQueueEnv.refill` | 不看 D ready | 每拍检查 D ready，未就绪即报错 |

现有调用方本来就都断言了 `is not None`，所以这是“防御性收口”，不改变通过/失败结论。

### 3.6 P06：区分性（把优先级反过来，用例会不会红）

已有用例里本来就有强区分性对照，本轮确认并记录：

- **BDA 读-读冲突**：同一测试先用 `lqidx 3 vs 9` 得到冲突向量 `[0,1]`，再用
  `lqidx 9 vs 3` 要求 `[1,0]`——优先级反了必然失败。
- **MissTrack 事件**：同 line 时 install 赢；不同 line 时轮到 alloc 赢（并断言 install
  丢失）——两种顺序都被固定。
- **WritebackQueue**：`param=0..3` 时 opcode 恒为 6，ProbeAck 恒为 4——参数不能影响 opcode。
- **MissQueue**：同块合并接受、alias 不同拒绝、首 beat 后拒绝——三个方向都有。

### 3.7 P04/P05：期望来源

| 期望 | 来源 | 是否独立 |
|---|---|---|
| index / set / alias | `DCacheWrapper.scala` 的 `addr_to_dcache_set`、`get_alias` 公式，在 Python 里独立实现 | 是（非 RTL 观察） |
| refill 行数据 | 两拍 GrantData 的字节拼接 + store 掩码字节 | 是 |
| 预取标记编码 | `L1PrefetchInterface.scala` 的常量表（0/1/2/3/4/5） | 是 |
| AMO 旧值 | refill beat 的 16B 窗口 | 是 |
| CMO 响应编码 | CMO opcode → A 通道 opcode 映射表 | 是 |
| 握手/时序 | 只能由 RTL 观察（`handled` 只在 S2、A 后隔一拍发 D） | **实现刻画**，已在文档标注 |

最后一行是明确的限制：时序假设来自实现观察，不能当作规范证明。

---

## 4. 成对证据

### 4.1 检查器灵敏度：注错必须 FAIL（8/8）

| 注错 | 类型 | 基线 | 注错后 |
|---|---|---|---|
| BDA 读窗首 bank 翻位 | readback fault | PASS | **FAIL** |
| CounterFilter query 取反 | expected mutation | PASS | **FAIL** |
| DTA tag 字翻位 | readback fault | PASS | **FAIL** |
| MissQueue refill 拼接翻位 | expected mutation | PASS | **FAIL** |
| LoadPipe index oracle 偏移 | expected mutation | PASS | **FAIL** |
| MainPipe alias oracle 偏移 | expected mutation | PASS | **FAIL** |
| DCache load data 翻位 | readback fault | PASS | **FAIL** |
| DCache store hit_id 翻位 | readback fault | PASS→**原先仍 PASS** | **FAIL**（已补断言） |

最后一行是本轮唯一由注错实验直接抓出的缺口：DCache 顶层 6 处 store 响应都没有断言
`hit_id`，LSU 按 id 退休 store，id 错了会退错指令。

### 4.2 XFAIL 解遮罩（P11）

`pytest --runxfail -k 'merge_data or carries_its_bytes'`：

| 用例 | 失败位置 | 实际值 | 期望 |
|---|---|---|---|
| `test_two_partial_stores_same_missing_line_merge_data`（dcache） | 数据断言 | `0x00AA` | `0xBBAA` |
| 同名回放（wrapper） | 数据断言 | `0x00AA` | `0xBBAA` |
| `test_second_store_merge_carries_its_bytes`（miss_queue） | 数据断言 | `0x01AA` | `0xBBAA` |

三条都精确失败在同一条数据断言，不是 setup/超时/其它断言——确认 xfail 没有被宽泛使用。

### 4.3 收集审计

```
files=15 defined=187 collected=212
duplicates=[] defined_but_not_collected=[] collected_but_not_defined=[]
tautology_true=0 or_true=0 if_false=0 except_pass=0
tests_without_assert=17 (allowlisted 17)
```

187 与 212 的差是 wrapper 用 importlib 复用 25 个 DCache 用例（同一份断言跑两个 DUT），
已在审计脚本里写明，不是漏收集。

---

## 5. 用例与覆盖率变化

| 项 | 复核前（`full-regression-15`） | 复核后（`soundness-recheck-03`） |
|---|---:|---:|
| 用例 | 209 passed + 3 xfailed | **210 passed + 3 xfailed** |
| 功能组 | 61 / 100% | 61 / 100% |
| 子模块行 | 8059/8309 = 96.99% | 8059/8309 = 96.99% |
| DCache | 50260/51179 = 98.20% | 50262/51179 = 98.21% |
| DCacheWrapper | 50453/51265 = 98.42% | 50455/51265 = 98.42% |
| MissQueue 分支 | 967/1334 | 967/1334 |

覆盖率几乎不变（+2 行），说明这一轮的价值不在“跑更多代码”，而在**把已跑过的代码
真的检查起来**。四个被改动最多的 DUT 另外用 seed=2 复跑：
`tests/dcache tests/miss_queue tests/main_pipe tests/banked_data_array` =
**112 passed + 2 xfailed**，新断言不依赖种子。

---

## 6. 仍未验证（如实列出）

### 6.1 从未被读的输出（按桶）

| 桶 | 数量（DCache / MissQueue / MainPipe / LoadPipe） | 为什么可以暂不检查 | 边界 |
|---|---:|---|---|
| perf_counter | 42 / 5 / 6 / 7 | 性能计数不影响功能正确性 | 未做 perf 语义验证 |
| store_load_forwarding | 219 / 108 / – / – | Sbuffer↔LoadPipe 联合范围，需 Sbuffer DUT 或 MemBlock | **未验证** |
| speculative_fabric | 33 / 33 / – / – | 文档标注的范围外 | **未验证** |
| status_mirror（`io_status_dup_*`） | – / – / 648 / – | 每 set 状态的广播副本，由同一状态源推导 | 未逐一比对 |
| data_array_bundling | – / – / 97 / – | 由 BankedDataArray UT 覆盖 | 父块边界未重复检查 |
| child_block_write_req | – / – / 5 / 12 | 请求发往子块，效果在子块 UT / DCache 层检查 | LoadPipe 边界未检查 |
| replacement_hint | 2 / – / 5 / 3 | 替换提示，效果由替换/eviction 用例检查 | 未逐字段比对 |
| ld_ld_violation_hint | 2 / – / – / – | 给 LSU 的 ld-ld 违例提示，不是 cache 正确性契约 | **未验证** |
| misstrack_sideband | – / 48 / – / – | MissTrack UT 直接驱动这些输入并比对 | 连接层未验证 |
| loadpipe_misstrack_link | – / 6 / – / 13 | 同上 | 连接层未验证 |
| tl_sideband | 10 / – / – / – | user/echo 字段不被本地 L2 模型消费 | 未验证 |
| cache_ctrl_slave | 6 / – / – / – | 由 wrapper UT 的 WFP-002 覆盖 | 顶层未重复 |
| debug_bore | 4 / – / – / – | 调试通道 | 未验证 |
| perf/WFI/l1Miss | `io_l1Miss`、`io_wfi_wfiSafe` | 状态/握手，不是本 DUT 功能契约 | 未验证 |

### 6.2 其它限制

- **LoadPipe 的 ECC / 伪错误注入输出**（`io_error_*`、`io_pseudo_*_done`）在 LoadPipe UT
  里从未被读：ECC 注入未建模。DCache 层的错误用例走的是 denied/corrupt refill，属于
  另一条路径，不能替代。
- **`CtrlUnitEnv.wait_tag_valid` 是死 helper**（无调用者），不影响任何结论，但属于
  代码卫生问题。
- **时序假设**（`handled` 只在 S2、A 后隔一拍发 D、CounterFilter 4 拍窗口）来自实现
  观察，不是规范；已在功能点文档标注为实现刻画。
- 本轮没有修改任何 RTL；`MQ-STORE-MERGE-DATA-PENDING` 仍是唯一确认缺陷。

---

## 7. 复现

```sh
cd /home/xyl/kmh-v3-test/memblock-hash/dcache

# 1) 收集/定义/恒真断言审计（硬失败即非 0 退出）
python3 tools/audit_test_soundness.py

# 2) 运行全量并记录 pin 观察轨迹
DCACHE_PIN_TRACE=/tmp/pins.json \
  /home/xyl/xreactor/output/toffee-migration/venv/bin/python -m pytest tests -q

# 3) 输出端口观察审计
python3 tools/audit_output_fields.py --pin-trace /tmp/pins.json

# 4) 检查器灵敏度（注错必须 FAIL）
python3 tools/selfcheck_checkers.py

# 5) XFAIL 解遮罩复核
PYTHONPATH=/usr/local/share/picker/python:$PWD \
  /home/xyl/xreactor/output/toffee-migration/venv/bin/python -m pytest tests -q --runxfail \
  -k 'merge_data or carries_its_bytes'
```

产物：`manifest/test-soundness.json`、`manifest/output-field-audit.json`、
`manifest/checker-selfcheck.json`、`results/soundness-recheck-03/`。
