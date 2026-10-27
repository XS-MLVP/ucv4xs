# 其他 case 的同源漏报复核（2026-10-22）

## 1. 目的与方法

问题起因：`#6229` 之所以长期没被发现，是因为**参考模型和 RTL 用了同一个“跨度=完整覆盖”的判断**。模型和 RTL 同时错，相等比较仍然通过。

本轮把“同源”当作系统性风险，逐个检查所有模型的判断点：

1. 找“模型判断与 RTL 判断形状相同”的位置（同源点）；
2. 区分**规范性性质**（必须成立，错了就是 RTL bug）和**策略/实现选择**（顺序、仲裁、流水窗口，不影响架构正确性）；
3. 对规范性同源点，写只读公开引脚、不依赖预测器的性质 oracle；
4. oracle 必须通过三项灵敏度门禁：bug 现场失败、干净对照通过、注入一个违约后再次失败；
5. 能够本地复现的，直接给出普通 FAIL 证据；不能的，明确标为“未复现风险”，不冒充已确认 bug。

不修改 RTL、旧参考、旧测试或历史 JUnit。

## 2. 本轮新确认：`#6634` 不只是“选错 owner”

### 2.1 同源点

- RTL `LoadQueueUncache.scala:236-239`：`io.exception.valid := RegNext(writeback)`，**任何 writeback 都产生候选**，正常完成也一样；
- RTL `LoadQueueUncache.scala:467-470`：`ParallelPriorityMux(entries.map(...))`，**按物理 entry 顺序**选第一个；
- 参考 `uncache_entry/model.py:96-100`：任何消费都构造 `FaultReport(True, ...)`；
- 参考 `load_uncache/model.py:165`：`next((out.exception for out in outs if out.exception.valid), None)`，同样按物理顺序。

参考没有读 RTL 寄存器，但复制了 RTL 的“候选产生条件”和“仲裁顺序”，所以这类错误永远不会以模型失配的形式出现。

### 2.2 独立性质探针

`tests/fail_review/test_uncache_exception_property.py`，只驱动公开引脚：

- 分配两个 NC load：A=ROB10（slot0），B=ROB11（slot1）；
- 分别完成总线请求、SID 绑定、响应；可分别注入 `nderr`；
- **同一拍**用两个 bypass lane 消费两个 owner；
- 收集窗口内全部 `io_exceptionInfo_*`，同时记录两个 lane 的 s1/s2 响应，证明两者真的被消费；
- 性质：每个被消费的真实总线错误都必须以自己的 ROB/VA 被报告；正常完成（exceptionVec 全 0）不得替代真实故障。

### 2.3 结果（`results/uncache-exception-property-05/`）

| 场景 | 结果 | 实际观察 |
|---|---|---|
| 单个真实错误（对照） | **PASS** | ROB10、VA 0x10000、loadAccessFault=1 |
| 正常完成 + 真实错误，同拍消费 | **FAIL** | 只报 ROB10（正常，`laf=0`），ROB11 的真实错误完全没有报告 |
| 两个真实错误，同拍消费 | **FAIL** | 只报 ROB10，ROB11 的错误被丢弃 |

两个 lane 的 s1/s2 响应都存在，说明**不是“第二个没被消费”**，而是消费了却没有向上报告。

### 2.4 父级后果

`ExceptionInfoGen.scala:140-143` 先过滤 `p.hasException`（`exceptionVec.orR`），再按 ROB/uopIdx 选最老。因此：

- 正常完成的零向量候选本身会被父级过滤，**不是**一个独立的 trap；
- 但它会赢得 LQU 内部的 `ParallelPriorityMux`，使同拍的真实故障根本到不了 `ExceptionInfoGen`；
- 同拍两个真实错误时，LQU 只输出一个 `io.exceptionInfo`，另一个已在 `ncOut.fire` 时释放，**故障被静默丢弃**。

这不是“错误地点（mtval）不对”这么轻：**真实总线错误可能完全不产生 trap**。

### 2.5 可达性边界

- 两个 NC 可以在 uncache outstanding 下同时存在；
- LDU 有 3 个 bypass lane，同一拍消费两个 owner 是模块接口允许的；
- 但本轮没有证明完整 Backend 在该拍一定同时提交两条 NC 错误，因此结论限定在“支持的模块接口内可复现”；不扩大为整核 ISA 必现。

## 3. 其他同源点逐项裁定

| 位置 | 模型判断 | 是否同源 | 性质类型 | 裁定 |
|---|---|---|---|---|
| `forward/model.py:78` 候选重叠 | `vaddr%16 + length` 跨度 | 是，与 RTL `s1OverlapMask` 同形 | 规范性（B1） | 已确认为 `FWD-ALIAS-001`，不新增 |
| `forward/model.py:100` 完整覆盖 | 跨度覆盖 = full | 是，与 `s2FullOverlap` 同形 | 规范性 | 已确认为 `#6229/#6312`，本轮之前已本地复现 |
| `forward/model.py:110-111` 已退休目标 | 先排除 retired | 否，独立正确 | 规范性 | 能发现 `#6714`；此前缺跨代激励，不是同源 |
| `uncache_entry/model.py:96-100` 候选产生 | 消费即 `valid=True` | 是 | 规范性 | **本轮确认 `#6634`** |
| `load_uncache/model.py:165` 异常选择 | 第一个 entry | 是 | 规范性 | **同上** |
| `age/model.py` 选择 | 按入队顺序扫描 | 否，使用规格顺序 | 规范性 | 无需修改 |
| `raw/model.py` 冲突/最老 | ROB 时间线解码 | 否，显式独立 | 规范性 | 无需修改 |
| `rar/model.py` release 捕获 | 当前/前拍 | 否，按规格 | 规范性 | 已暴露 `RAR-REL-001` |
| `replay/model.py:142-145` 选择 | head/near 内 `min(slot)` | **是**，与 RTL `PriorityEncoderOH` 同形 | 策略 | 不改判：replay 顺序不改变架构结果；仅“head 优先”策略可能被掩盖，属于活性/性能风险，不是已确认功能 bug |
| `replay/model.py:169-171` refill 窗口 | 对齐 2 拍、非对齐 3 拍 | 是（实现窗口） | 实现相关 | 无外部规格可判错，保留为“实现定义风险” |
| `deq/model.py:59` 可写条件 | 与 `toSbufferValid` 同形 | 是 | 实现条件 + 字节规范性 | 已有独立字节/生命周期账本（`audit_deq_lifecycle`）覆盖，并已发现 B7-B10；本轮未发现新增 |
| `psq/model.py:111` full | `virtual_count > 128` | 是 | 规格边界 | 已用 Dispatch 合法性核对（128 合法），非 bug |
| `load_uncache/model.py:104-123` 仲裁 | MMIO 取最高、组内 RR | 是 | 策略/接口 | 多 MMIO 同时有效已被判为接口域；公平性未证明，保留风险 |
| `lsq_wrapper/model.py:55-63` 总线仲裁 | ROB 较老者优先 | 否，独立规格比较 | 策略 | 不影响正确性，保留风险 |
| `freelist/model.py:59` bank 选择 | `min(bank)` | 是 | 策略 | 已有 `priority_over_age` 自检及 23/23 语义，非 bug |
| `vlq/model.py` 指针 | 规格算术 | 否 | 规范性 | 无需修改 |
| `vsq/model.py` 计数 | 规格计数器 | 否 | 规范性 | 无需修改 |

## 4. 结论与计数更新

- **新增本地确认的 RTL 功能 bug：1 个**（`#6634`，此前只有源码/上游确认）。
- 之前 11 个根因不变；5 组线索中仍是 **4 个 RTL 功能 bug + 1 个配置问题**。
- 因此当前计数：
  - RTL 功能 bug 总数 **15**；
  - 其中本地 DUT 已复现 **14**（11 + `#6229` + `#6714` + `#6634`）；
  - 仅源码/上游确认、本轮未重跑 **1**（`#6704`）；
  - 另有 **1 个配置合法性问题**（`#6688/#6697`）。
- `#6634` 的错误描述应升级：不只是“多候选按物理槽序选错 owner”，还包括“同拍多个真实错误只报一个、正常完成可抢占真实故障，导致真实 trap 丢失”。

## 5. 证据

```text
tests/fail_review/test_uncache_exception_property.py
results/uncache-exception-property-05/pytest.xml
results/uncache-exception-property-05/execution/manifest.json
results/uncache-exception-property-05/relationship-v1.json
```

该运行 3 节点：**1 PASS / 2 FAIL**；无逐拍 JSON、无波形。失败为真实功能失败，保留为普通 FAIL。
