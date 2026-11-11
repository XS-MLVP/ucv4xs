# MMU Verification Spec

状态：验证侧当前索引。2026-11-11 已完成本轮已审查适配范围的独立验收，**不等于整体 MMU/ISA 认证**。

## 1. 范围与基线

- 17 个真实 RTL DUT：`tlbfa`、`wrapper`、`tlb`、`tlbn`、`l2mq`、`l2pf`、`ptwrepeater`、`ptwfilter`、`hptw`、`ptw`、`pmp`、`bitmap`、`bitmapcache`、`ptwcache`、`llptw`、`l2tlb`、`l2tlbwrapper`。本轮收集 433 项，相对起点新增 15 纯自检和 1 PTW 权限功能负例。
- 当前配置 `public-a0c2a26cb` / DefaultConfig：16 个受影响 DUT 当前构建/冒烟及身份通过，统一选跑 **421 PASS**，`hardware_verdict=INCOMPLETE`；PMP 12 项未选。最后 loader 小修补另定向 **21 PASS**、根种子 **83 PASS**，没有最后再跑一轮全 421 项，也不累加重叠选择。
- 历史固定源码：`XiangShan kunminghu-v3 @ 893e1580b705d81f113c30c7a05734e09a08050e`，历史 RTL 哈希见 [`manifest/*-rtl.sha256`](../../../manifest)。2026-10-26 可信度复核 **408 PASS（395 functional + 13 self-test），0 FAIL/XFAIL/SKIP**，索引 [final-runs.json](evidence/reports/evidence/soundness-20261025/final-runs.json) 保留日期与范围；不用于替代当前结果。

## 2. 功能点与检查

功能点文档在 [functional-points/](functional-points)：

| 文件 | 覆盖 |
|---|---|
| [functional-points-tlbfa.md](functional-points/functional-points-tlbfa.md) | TLBFA 48-way 存储、命中/回填/sfence/权限/极性 |
| [functional-points-wrapper.md](functional-points/functional-points-wrapper.md) | TlbStorageWrapper 存储/替换/初始化 |
| [functional-points-tlb.md](functional-points/functional-points-tlb.md) | TLB ITLB、PTW/GPA 重放、异常与 sfence |
| [functional-points-tlbn.md](functional-points/functional-points-tlbn.md) | TLBNonBlock 多端口 DTLB、每 way sfence、need_gpa |
| [functional-points-l2-leaves.md](functional-points/functional-points-l2-leaves.md) | MissQueue、Prefetch、PTWFilter/Repeater、PMP |
| [functional-points-l2-midblocks.md](functional-points/functional-points-l2-midblocks.md) | PTW、HPTW、LLPTW、Bitmap、BitmapCache |
| [functional-points-ptwcache.md](functional-points/functional-points-ptwcache.md) | PtwCache L0/L1/L2/L3/SP、flush、bitmap、RAM 回读 |
| [functional-points-l2tlb.md](functional-points/functional-points-l2tlb.md) | L2TLB 顶层组合、PMA/PMP、sfence、异常 |
| [functional-points-l2tlbwrapper.md](functional-points/functional-points-l2tlbwrapper.md) | L2TLBWrapper 组合、perf trace、outstanding |

功能点/覆盖数字只属于对应 run；`sampled bins 100%` 不是语义闭合。逐 DUT 最终指标见 [工程 README](../../../README.md) 和可信度复核报告。

## 3. 证据与残余

- 2026-10-25 可信度复核：[verification-soundness-20261025.md](evidence/reports/verification-soundness-20261025.md)。5 个旧 XFAIL 被判为验证侧问题；旧 RTL 根因结论撤回。
- ISA 对照：[isa-confirmation-20261026.md](evidence/reports/isa-confirmation-20261026.md)。
- 最终运行/残余/源码差异：[final-runs.json](evidence/reports/evidence/soundness-20261025/final-runs.json)、[final-residuals.json](evidence/reports/evidence/soundness-20261025/final-residuals.json)、[source-drift-review.json](evidence/reports/evidence/soundness-20261025/source-drift-review.json)。
- 未被归为正式 bug 的覆盖/结构/已接受项统一在 [residuals.md](residuals.md)，保留 `manifest/known-issues.json` 的稳定 ID。
- 当前问题目录为 **8 open / 9 closed**。本轮局部回归未审计问题的完整关闭条件，不升级其 `unverified` 状态；旧 closed 版本和 resolution 历史保留。9 个 closed 中 8 个是旧基线误报/归因撤回，1 个是独立 DUT 结构缺口关闭，均不由本轮 PASS 自动认证。

## 4. 完成条件

一个 DUT/组合只有同时满足以下条件才可声明验收：

1. 对应功能点有合同/ISA/协议依据，且有独立预期和公开端口观察；
2. 合法对照存在，真实失败不被 xfail/skip/waiver 消除；
3. 行/branch/toggle 分母与残余逐项分类，不把声明 bin 采样当作语义闭合；
4. 父块使用真实子块，叶子与组合结论分开；
5. 当前基线构建/运行并保留种子、RTL/build/source 哈希和 run manifest；本轮 16 DUT 证据在 `results/transaction-adapters-20261110/mmu/`，PMP 与未证明义务仍单列。

**当前验收边界**：旧 17 DUT soundness run 只属于其历史基线；本轮当前 16 DUT 的适配与批准权限修复通过，不关闭 fake-PTE、条件化 no-fence、HFENCE.GVMA、A/D/privilege 交叉和残余功能序列，不声称整颗 MMU/SoC 或 ISA 签核。

## 5. 事务适配层

2026-11-10 的事务边界修复把功能用例中的引脚/信号/owner 内部访问收回到各 DUT 的 env：

- 请求/翻译：`issue(...)` 接收有类型请求（`BmReq`、`CacheReq`、`LlpReq`、`Req`、`WalkRequest` 等），按真实 ready 接受，返回或记录实际 fire 身份；不把 `send` 调用本身当作已接受。单次 offer（`offer_request`、`offer_second_request`、`send_request`、`send`）在驱动 payload、组合 settle 之后、边沿之前采样 `valid && ready`，返回值就是本拍真实 fire；不得用后一拍 ready 电平推断接受。多端口 `issue_ports` 在写任何端口之前完成类型、索引、重复端口、数量与字段宽度校验，部分输入非法时不留下半驱动状态。
- 回填/响应：`refill_word`、`refill_l0`、`refill_super`、`refill_entries`、`ptw_respond`、`ptw_respond_observed`、`queue_hptw_response` 等保持同一时钟沿的回填/响应语义；响应由 `*_snapshot()` 返回独立副本，测试不读取活引脚或活 model。
- 失效/上下文：`pulse_sfence`、`begin_sfence`/`end_sfence`、`pulse_csr_change`、`flush` 保持请求有效电平的拍数和撤销顺序；sfence 与同拍 refill 仍在一个沿上服务。
- 观察：`response_snapshot`、`output_snapshot`、`wakeup_snapshot`、`llptw_snapshot`、`csr_snapshot`、`ptw_request`、`port_idle_status` 只在合同采样点读取公开输出并构造独立副本；调用者修改返回值不改变 env 历史账本。`collect_responses` 按真实完成点计数：response port 0 只有 `valid && ready` 才算一次完成，计数后仍推进该次消费沿；response port 1 在当前生成 DUT 上没有 ready 输入，是 valid-only 通道，按 valid 采样。重复响应不做去重，调用方保留原身份断言。`count`、`max_cycles`、`port` 在驱动/推进时钟前拒绝非法值。
- 独立 oracle：`expected_response`、`expected_ppn`、`hit_ways`、`way_valid`、`stored_level`、`storage_invalid_way_count` 只返回期望值或标量查询，不返回活 model/ports。`ptw_respond` 返回的 way 是独立替换模型对本次 refill 的分配收据；TLB 的 48-way 覆盖场景据此维护自身 refill 账本生成 hit 地址，不再读取 live storage entries。
- 结构压力：`structural_input_sweep` 只由 env 在带 `structural_stress` 标记或明确标注为接口压力段的用例收尾调用，排除时钟/复位/握手/上下文；不是功能事务 API，也不计功能 credit。

`ucv check mmu` 的结构通过只说明接线；采样、所有权、独立 oracle 与正负对照仍需按 [checker 与运行时](../../../../../../skills/execution/checker-and-runtime.md) 复核。首次适配交付的 416 PASS 属于本检出现有 `public-893e1580b` 缓存 DUT（`dut/` 符号链接）的适配复验；当前配置的 `public-a0c2a26cb` 构建与身份由主 agent 单独核验（`independent-current-native-identity.json`），两类结果不混用。实际命令与精确边界放在 `results/transaction-adapters-20261110/mmu/`，不把旧 893e 的 408 PASS 当作本配置结果。

### 5.1 当前基线的隐式页表 MXR 合同

当前 `public-a0c2a26cb` 的 PTW/LLPTW 生成接口裁剪 `io_csr_priv_mxr`，源码的隐式 G-stage 页表读只要求
`R=1`。独立 RISC-V privileged v20260120 规定 VS 页表访问按 implicit load 检查、MXR 只作用于 explicit
access，因此旧 `test_stage2_first_perm_mxr_pass` 的 MXR 正例期望已按用户授权纠正；PTW 增加对应隐式读
错误场景，合法 readable 控制复用既有用例。合同、源码位置、端口差分和证据边界见
[implicit-gstage-mxr-contract.md](../design/contracts/implicit-gstage-mxr-contract.md) 与
`results/transaction-adapters-20261110/mmu/baseline-and-port-diff.json`。该 oracle 差异单独登记，**不**
属于原事务迁移的 nodeid/激励零差分结论。

MXR 的绑定依据是本 DUT loader 返回的生成 artifact `signals.json` 与实际 handle 的双向一致，不是
Python 属性存在性：schema 声明而 handle 缺失、或 handle 多出而 schema 未声明，都明确失败；无 schema、
不可解析或未知版本不得泛化为裁剪。loader 默认仍是历史二元 `(cls, argv)`，仅显式
`with_schema=True` 返回 schema，并要求 schema 来自实际绑定模块的 artifact 目录；同进程缓存 alias
跨目录复用时 fail-closed 要求隔离进程。功能用例只读 `mxr_input_capability`/`has_mxr_input` 这一只读
能力，不读取 live CSR 字典或 pin；裁剪路径由自检验证 `set_csr(mxr=...)` 的 fail-closed 合同。详见合同 §4。

当前 421 项和最后 21 项选择的源码/构建身份均由主 agent 独立核验。最后实现下旧 893e
定向仍 **5 PASS / 2 FAIL**，两个失败恰为 PTW 隐式 `R=0,X=1` 和原 LLPTW `mxr_pass`
修正节点，其余合法控制通过。schema/handle 不一致及模块缓存导致的 class/schema 跨产物
分离均明确拒绝；默认 loader 二元 API 与逐调用 seed 保持兼容，带 schema 是显式入口。
详细过程、真实失败与证明边界在 `results/transaction-adapters-20261110/mmu/independent-final-review.md`，
机器收据 `independent-acceptance.json`；不把静态清零等同于硬件正确。
