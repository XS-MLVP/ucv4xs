# 对独立审核发现的二次裁决

## 结论

**没有确认真实 RTL bug。上轮把若干覆盖不足与检查器缺口统一列成 P1，容易被理解成已确认
硬件缺陷，表述过重，应以本报告的逐项分类为准。**

本轮确认：两条正式用例存在可复现的假通过路径；另有接口检查缺口。
这属于测试软件的问题，不是证明硬件已经发生错误。优先级、kill、CMO 的新增区分性检查
在未改动的现有 DUT 上全部通过。

不修改/重编译 RTL，不改正式用例或参考模型。新增测试和观测插件只在
`review/recheck_20261024/`。保留上轮报告及证据，以便看清结论如何修订。

## 1. 判定标准

1. RTL bug 需要合法输入和环境响应下，公开输出违反已确认合同的实例。
2. 检查器 bug 可以由用例承诺的事务没有完成、但用例仍通过来证明；必须与真实 DUT 错误
   分开报告。边界故障模拟不等于 mutant RTL，也不等于真实 DUT 失败。
3. 单纯改变参考期望、随意调用 helper 或让一个扰动存活，只能证明场景/检查存在盲区；
   不能自动提升为硬件 bug。
4. 不能只因为接口是 Decoupled，就擅自要求 Irrevocable 式的全部保持约束。

## 2. 对上轮 R1–R7 逐项裁决

| 原编号 | 本轮裁决 | 是否确认 RTL bug |
|---|---|---|
| R1：入队被拒绝后用例仍可通过 | **确认测试用例存在空跑路径**；不是按实际 fire 记账本身错误 | 否 |
| R2：排空超时正常返回 | **确认完成性检查缺陷**，正式用例可在 8 行未完成时通过 | 否 |
| R3：非法 accept / ID 复用 | **撤回“已证明实际运行 bug”的暗示**；旧 helper 反例不足以证明合法调用链可达，保留监视/并发覆盖缺口 | 否 |
| R4：优先级和 kill | **原用例缺少区分性场景**；新增真实竞争与实际 mismatch 检查均 PASS | 否 |
| R5：CMO 分类 | **原用例只检查空信号，未检查退出后续行为**；新增续接检查 PASS | 否 |
| R6：地址低位 | **确认对齐检查缺口**；下游物理地址合同确要求 block-aligned，现有 DUT 对齐正确 | 否 |
| R7：运行时波形策略 | **证据/合规问题，不是 RTL 功能 bug**；未测量默认运行时的文件 I/O，不能把代码推断说成实测违反 | 否 |

### R1：完整正式用例的空跑反例

测试：`tests/sbuffer/test_sbuffer.py::test_timeout_writeout_all_lanes`。

边界适配器模拟“ready 卡低且不接受任何请求”：检查器读到 ready=0，适配器同时抑制送入
未改动 DUT 的 valid，保持这个故障模型的无接受行为。它不是在正常 DUT 上复现了 ready 卡低。

观测结果：

- offered = 4，accepted = 0，accept helper 调用 = 0；
- 模型为空，原用例直接跳过 `while env.model.lines`；
- **正式用例 PASS**。

因此可以确认该用例不保证真的验证了四笔 store 的超时写出。
`env.py:148-161` 按实际 ready 维护模型是合理的；缺陷是默认路径不重试或断言预期接受数，
而该用例最后也不核对事务数。不能把这种缺口解释成当前 RTL 在丢 store。

### R2：完整正式用例的未完成反例

测试：`tests/sbuffer/test_sbuffer.py::test_each_lane_merge_and_forward`。

只在检查器观察边界隐藏 outgoing req_valid，模拟 DUT 不再发写出请求。
真实未改动 DUT 的 req_valid 仍为 1；报告中明确记录 raw 值，避免冒充真实硬件漏发。

观测结果：

- 72 笔输入被接受，转发检查完成；
- 排空 helper 预算耗尽后正常返回；
- 用例退出时模型仍有 **8 行**，raw sbempty=0，没有接受任何 DCache 写出；
- **正式用例仍 PASS**。

阳性对照：同样隐藏 req_valid，但运行 `test_timeout_writeout_all_lanes`，
`wait_req()` 在 40 周期后抛出 TimeoutError，**该用例 FAIL**。
因此结论应精确限定为 `drain_requests()` 及缺少收尾检查的调用方，而不是声称整个测试台
都没有 watchdog。

### R3：为什么收窄旧反例的结论

旧脚本直接构造 ReqSnap 并在 req_valid=0 时调用 `accept()`，没有经过实际 `wait_req()`。
这显示 helper 缺少防御检查，但尚未证明这种调用在正式用例和合法 DUT 行为中会出现。

重复 ID 的脚本同样只验证一个局部 helper，未验证完整响应链会不会在后续被其它断言发现。
没有维护 outstanding ID 表仍是监视器/并发用例缺口，不能据此确认硬件重用了 ID，
也不能宣称这个脚本已经给出了全用例的假通过反例。

源接口为 `DCacheToSbufferIO.req = Decoupled(...)`
（`DCacheWrapper.scala:725-727`），不是 Irrevocable；应按具体合同规定检查，
不能凭通用总线经验追加所有 stall 稳定性要求。外部 Chisel 文档访问本轮超时，
本报告不宣称完成了在线规范复核。

## 3. 在未改动 DUT 上补做的区分性检查

新增文件：`review/recheck_20261024/test_directed_recheck.py`。

| 定向检查 | 显式期望与实际结果 |
|---|---|
| 同字节 active/inflight 竞争 | 旧值 0x11、新值 0x22，mask 分别为 0xF/0x3；三路转发均得到 `[0x22,0x22,0x11,0x11]`，PASS |
| kill + 实际标签不一致 | 同一虚标签、错误物理标签，不 kill 时 invalid=1，kill 后 invalid=0，PASS |
| CMO 完成后 SQ 仍非空的普通事务 | sbempty=1、flush.empty=0；结束 CMO 源后普通 store 不残留在 drain-all 路径，PASS |
| 完整写出行地址 | 非零 lane 的 store 写出时 addr/vaddr 均为预期行基址，PASS |

这些用例还包含独立字面值/常量断言，不以 DUT 返回数据作为期望。
沿用模型只作现有事务记账；真正的数据竞争结果另按上述明确的新旧数据检查。

故意错误的对照：

- 把期望的优先级反过来，新增竞争用例失败：实际 byte0=0x22，错误期望=0x11。
- 把 CMO 输入分类强制普通 flush，新增续接用例失败，出现残留 drain-all 写出。
- 把请求快照地址 bit0 置 1，新增完整地址检查失败。

对照失败验证的是新增用例的区分力，仍不是未改动 RTL 的自然失败。
CMO 续接的“不应立即写出”仅针对固定配置的高 timeout、单行低占用且没有 flush/replay
条件，是微架构路径检查，不是声称 ISA 普遍禁止提前写出。

## 4. R6 的接口合同补证

`cache/dcache/mainpipe/MainPipe.scala:52-53` 明确注释物理 addr：
`must be aligned to block`；`:85-100` 从 store 请求直接传入该地址。

`Sbuffer.scala:263-264,703-704` 生成物理/虚拟行基址。
因此仅比较 `addr >> 6` 确实遗漏了对齐值检查；但新增定向检查已证明当前被测场景的
真实输出对齐正确，不能用人为破坏后的地址声称原 RTL 输出了错误地址。

## 5. 重跑证据和保留限制

- 原正式用例 31 个 + 新增定向用例 4 个：**35 PASS**。
- 八组实验的退出码均符合预期，命令见 `review/recheck_20261024/runs.json`。
- 空跑反例：`reject_all_timeout_case.json/.log`。
- 未完成反例：`missing_writeout_merge_case.json/.log`。
- watchdog 对照：`missing_writeout_watchdog_control.json/.log`。
- 正常 35 例：`combined_baseline_35.json/.log`。
- 本轮复用同一个现有顶层共享库；没有建立新的 DUT 构建，没有使用 VPI/internal-cfg。
- 通过上轮审计插件请求 PauseWaveformDump，不以暂停状态返回值证明“零初始化 I/O”。
- 未更新原生覆盖率；旧覆盖率只代表旧运行，不与本轮 35 PASS 混报为同一轮覆盖结果。

**最终可对用户陈述：没有证实 RTL bug；确有两条正式用例的假通过路径及若干检查/覆盖缺口。
“尚未验证充分”和“硬件真的有错”是两个不同结论。**
