# LSQ 交互语义检查与覆盖场景（2026-11-06）

## 1. 起因与范围

用户要求：以 Scala 为依据继续做**交互语义**检查，确定**全面覆盖场景**，然后**回归**。

上一轮已经建立了三向对账（规格/Scala/生成端口）与单 kind × 单结果域矩阵。这一轮补的是
**跨模块交互**：两个模块各自"正确"，但条件交错出现的时间窗口不属于任何单个格子。

范围：LSQ、DefaultConfig、`public-a0c2a26cb`、seed 1。

## 2. 交互语义清单（新增合同）

[interaction-semantics.md](../../../design/contracts/interaction-semantics.md) 按 8 条边界（B1–B8）逐条写：
发起、消费、握手、背压/撤销、身份传播、完成条件、窗口。要点：

| 边界 | 关键语义 | 覆盖 |
|---|---|---|
| B1 LsqWrapper ↔ LQ/SQ | `canAccept = lq && sq`；load 的 `sqIdx` 在入口绑定物理槽 | partial |
| B2 VSQ ↔ PSQ | 三拍传播 `rob→VSQ→[2拍]→PSQ`；4 条指针不变量 | partial |
| B3 DeqModule ↔ EnterSbufferQueue | cross16B 要两端口 ready；credit 由**类型**决定 | partial |
| B4 DeqModule ↔ UnalignQueue | 第二页在**第一页写出**时释放 | **fail**（见 §3.1） |
| B5 PSQ ↔ ForwardModule | 逐字节 mask/data；hazard 只来自 UQ | covered |
| B6 LoadQueue ↔ 子模块 | RAR release/ldWbPtr、RAW 地址就绪、Replay 银行选择 | covered |
| B7 UncacheEntry ↔ Uncache | Load 读 `nderr/error`，Store 读未驱动的 `denied/corrupt` | Load covered / Store fail |
| B8 Wrapper 单总线仲裁 | `selectLq` 按 robIdx；NC outstanding 时留在 idle | covered |

## 3. 两个探针：都是真实红，都有合法对照

新增 `tests/lsq_wrapper/test_interaction_windows.py`，只读公开引脚。

### 3.1 `IWL-UQ-SECOND-PAGE`（上游 #6822 同根因）

`NewStoreQueue.scala:1299`：

```scala
io.fromUnalignQueue.ready := headrdataPtr === io.fromUnalignQueue.bits.sqIdx && writeSbufferWire.head.fire
```

释放条件是"**第一页**写出到 Sbuffer 的那一拍"。`ForwardModule` 的页 hazard 只来自
`unalignQueue.forwardEntries`（`:1632`）；UQ 一旦释放，第二页就不再有任何前递可见性，
而它的片段此刻还停在 `EnterSbufferQueue`。

| 相位 | 含义 | 结果 |
|---|---|---|
| `uq_held`（对照） | 第二页仍在 UQ | **3/3 PASS**：正确拦截 |
| `uq_released`（反例） | 第一页已进 Sbuffer、第二页仍在 FIFO | **3/3 FAIL**：`blocked=False`、`forwarded_ok=False` |

探针同时断言 `second_fragment_still_pending=True`，证明窗口真实存在而不是"存已经落地"。

后果：年轻 Load 查询第二页时既不报 hazard、也拿不到前递字节，会读到旧内存。
上游 #6822（open PR）的修复正是把它改成 `headDeqPtr === sqIdx && io.sqDeqCnt.orR`，
并给 PSQ 加 `fwdHold` 保持 `forwardValid`。

### 3.2 `IWL-NC-CROSS16B`：**已撤回**（我的假阳性）

初版结论是"NC store 跨 16B 时请求 mask `0xf0` 只覆盖 4/8 字节"。**该结论错误，现已撤回。**

复核 `NewStoreUnit.scala:632-634`：

```scala
val afUnalignMMIO = isMMIO && !align
val am = !align && isScalar && isNC && !pmpInaccessible
val hasException = in.hasException.get || af || am
```

**NC 标量 store 只要非对齐就置 `storeAddrMisaligned`**；而 8 字节 store 跨 16B 必然非对齐
（offset 12 + 8 > 16）。`hasExceptionSet → ctrlEntries(i).hasException`（`:1823-1848`），
`uncacheCanHandle` 又要求 `!hasException`，所以该组合**不会发出 uncache 请求**。
`NewStoreQueue.scala:1448` 的那条 `XSError` 是上游已保证的防御断言。

错在哪：我按 `hasException=0` 驱动了一个非对齐 NC store，等于喂非法激励；DUT 用非法的
8 字节 mask 响应了它，我却把响应当成缺陷。这正是我自己在 `legal-stimulus` 里反对的做法。

修正后的探针 `test_uncached_store_respects_upstream_misalign_exception`：

| 场景 | `hasException` | 期望 | 实际 |
|---|---|---|---|
| `nc_aligned`（offset 8） | 0 | 发请求且 8 字节全覆盖 | **PASS**（mask `0xff`） |
| `nc_misaligned_with_upstream_exception`（offset 12） | 1 | 不发请求 | **PASS**（无请求） |

结论：LSQ 行为正确，**此条不是缺陷**。`function_points.INTERACTION_WINDOWS` 中该条已从
`fail` 改为 `pass`，`note` 保留撤回记录。

## 4. 覆盖场景扩充

`function_points.py` 新增 `INTERACTION_WINDOWS`（5 条）并进门禁：

- `validate()` 检查每条有 boundary/scala/window/status/evidence；
  `pass`/`fail` 必须有 `note` 且证据文件存在；`gap` 必须有 `missing` + `next`。
- `tests/meta/test_function_points.py` 增加 3 项：窗口必须声明、必须出现在合同文档里、
  `fail` 必须有探针文件。当前 **14 项全 PASS**。

矩阵状态：48 格仍为 **23 pass / 2 fail / 4 gap / 19 na**；交互窗口另计
**2 fail / 2 gap / 1 pass**。

## 5. 回归

### 5.1 先定向

| 运行 | 选择 | 计数 | 说明 |
|---|---|---:|---|
| `/tmp/opencode/lsq-iwl-uq-20261106` | 首版 UQ 探针 | 3 PASS / 3 FAIL | `uq_held` 控制通过，`uq_released` 因激励不足被显式拒绝（"head never presented"），不算结论 |
| `/tmp/opencode/lsq-iwl-uq2-20261106` | 补 ROB head 后 | 3 / 3 | 同上，激励修正 |
| `/tmp/opencode/lsq-iwl-3-20261106` | 加窗口真实性证据 + NC 探针 | **4 PASS / 4 FAIL** | 两个对照 PASS、两个反例 FAIL，失败原因与预期一致 |
| `/tmp/opencode/lsq-iwl-2-20261106` | NC 探针首版 | 4 / 4 | 首版用裸 packet 驱动，探针自身报"no uncached request"，作废 |

### 5.2 完整回归

**权威结果以修正假阳性后的 v2 为准。**

| 运行 | 用例 | PASS | FAIL | 状态 |
|---|---:|---:|---:|---|
| 上一轮权威 `full-a0c2a26cb-v3` | 2575 | 2356 | 219 | 对照基线 |
| `lsq-full-20261106`（v1） | 2600 | 2368 | 232 | **作废**：含已被撤回的 NC 假阳性 1 条 FAIL |
| `lsq-full-20261106-v2`（**权威**） | **2600** | **2369** | **231** | 修正探针后重跑 |

v2：seed 1、32 workers、新目录；运行前后 `source_sha256` 均为
`8ede0b3b657b88a20fe20d0ecadc88932df0702b7417983dc4b53589fd563cc7`。

逐 nodeid 对账（**删除 0 条**）：

```
新增节点 25 = 14 meta + 8 交互窗口 + 3 uncached-store-fault
           其中 PASS 20 / FAIL 5
PASS→FAIL    7   （上轮 mixed_owners 同源期望修复的后续，非本轮造成）
FAIL→PASS    0
算术核对：2356 + 20 - 7 = 2369 PASS；219 + 7 + 5 = 231 FAIL；2575 + 25 = 2600
```

v1→v2 的唯一差异就是撤回的那两个节点：

| 节点 | v1 | v2 |
|---|---|---|
| `test_nc_store_must_not_silently_drop_...[aligned-control]` | PASS | 已删除（改名） |
| `test_nc_store_must_not_silently_drop_...[cross16B]` | **FAIL** | 已删除（改名） |
| `test_uncached_store_respects_upstream_misalign_exception[nc_aligned]` | — | PASS |
| `test_uncached_store_respects_upstream_misalign_exception[nc_misaligned_with_upstream_exception]` | — | PASS |

**FAIL 分类（231 条，可加和核对）**

| 类别 | 数量 | 说明 |
|---|---:|---|
| 上一轮就已 FAIL（判定未变） | 219 | 与上一轮 FAIL 总数相等，逐 nodeid 无变化 |
| 上一轮 PASS→本轮 FAIL | 7 | `io_store × fault` 同根因，由上一轮同源期望修复引入 |
| 本轮新增探针 FAIL | 5 | `IWL-UQ-SECOND-PAGE` ×3、`test_uncache_store_fault` ×2 |
| **合计** | **231** | 219 + 7 + 5 |

按目录分布（仅统计那 219 条）：`lsq_wrapper` 86、`deq` 28、`forward` 19、`store_queue` 18、
`psq` 17、`fail_review` 13、`load_queue` 9、`load_uncache` 8、`rar` 7、`normal_mixed` 6、
`sq_endpoint` 6、`vsq` 2。

## 6. 结论边界与剩余

- 本轮**只新增 1 条真实红**：`IWL-UQ-SECOND-PAGE`（3 lane，与上游 #6822 同根因）。
- `IWL-NC-CROSS16B` **已撤回**：初版探针漏了上游 `NewStoreUnit.scala:633` 的
  `am = !align && isScalar && isNC`，喂了非法激励；修正后 LSQ 正确拒绝，不是缺陷。
  这次错误已写进报告与合同，作为"判缺保护前先确认上游是否已排除该组合"的教训。
- `IWL-VSQ-RETIRE`（#6597）、`IWL-CREDIT-TYPE`（`GAP-PSQ-CREDIT`）仍是 `gap`，
  前者需要真实分段向量 store 的 flow 拆分 + 后续 AMO，后者需要模型按类型算 credit。
- 三向对账的 315 项"待分诊"仍未逐项判定（上一轮已声明）。
- 结论只覆盖 LSQ、DefaultConfig、`public-a0c2a26cb`、seed 1。
