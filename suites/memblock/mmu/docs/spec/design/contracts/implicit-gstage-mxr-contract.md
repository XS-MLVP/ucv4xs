# 隐式 VS 页表 G-stage 读取与 MXR 合同

状态：当前基线 `public-a0c2a26cb` 的事务/接口适配合同。ISA 期望来自独立固定的 RISC-V
privileged 文档，不由 RTL 输出反推。用户已明确授权扩展当前适配并纠正因此产生的旧期望。

## 1. 范围

本文件只约束 PTW、LLPTW 在 allStage 路径上经 HPTW 完成的**隐式** G-stage
页表读取（VS 页表读取），以及当前生成 DUT 裁剪 `io_csr_priv_mxr` 后的 env/API 行为。
onlyStage2 不是 VS 页表读取，不在本文件新增语义范围；TLB 对显式 load 的 MXR、VS-stage MXR
（`vsstatus.MXR`）、PMP/PMA 或其余 MMU 语义也不重新定义。

## 2. 架构要求

固定 ISA 版本：RISC-V privileged `v20260120`。主 agent 已独立下载并保存原文与哈希，收据为
`results/transaction-adapters-20261110/mmu/isa-sources/receipt.json`（`hypervisor.html/.txt`、
`priv-preface.html/.txt`）；本文件不复制原始哈希，避免与历史报告混用。

规范依据：

1. **Hypervisor §14.1.5.1 Guest Physical Address Translation**：G-stage 翻译中，所有内存访问
   （包括访问 VS 页表数据结构的访问）按 U 模式用户级访问处理；为支持 VS-stage 翻译而进行的
   页表访问，其权限按 **implicit load or store** 检查，而不是按原始访问类型检查。
2. **Hypervisor §14.1.3.1**：MXR 使 execute-only 页对 **explicit loads** 可读；HS-level MXR
   作用于显式访问的两级翻译，不放宽隐式页表读取。
3. **Privileged Preface（Preface to Version 20241017）**：“Clarified that MXR affects only
   explicit memory accesses.”

因此：VS 页表层级的隐式 G-stage 读取必须满足 G-stage `R=1`。`X=1` 即使配合 `MXR=1` 也不满足。
这条规则的答案是“拒绝”，不是用 DUT 的 HPTW 响应或旧 expected 反推。

上游 `OpenXiangShan/XiangShan` 提交 `c9c7b37067ade19e03f9e22db37862f8e61a441b`
（`fix(RVH): ignore MXR for implicit G-stage reads (#6099)`）删除 PTW/LLPTW 中
`mxr && x` 的回落；该提交只用于确认旧期望对应已知上游缺陷，规范依据仍是上面的独立 ISA 原文。

## 3. 基线与接口差分

`results/transaction-adapters-20261110/mmu/baseline-and-port-diff.json` 保存逐字段证据：

| 项 | `public-893e1580b`（旧） | `public-a0c2a26cb`（当前） |
|---|---|---|
| `PageTableWalker.scala` | 首/VS 页表 HPTW 响应允许 `R=0 && mxr && X=1` | 两处都只要求 `h_resp.entry.perm.r` |
| 生成 DUT `io_csr_priv_mxr` | 存在 | 已裁剪；priv 输入仅 `io_csr_priv_virt_changed` |
| `signals.json` 叶计数（含 clock/reset） | PTW 400 / LLPTW 160 | PTW 399 / LLPTW 159（差异仅 `io_csr_priv_mxr`） |
| 显式访问 MXR | TLB 使用 `csr.priv.mxr` | 当前 `TLB.scala` 仍使用，属显式 load 路径，不在本文件范围 |

端口口径只按生成 artifact 的 `signals.json` schema 叶计数（含 clock/reset）；生成 Python 中的合成
XData 别名（例如 ppn 虚拟别名）不是 physical port，不计入端口数。
源码只用于定位“谁实现/是否消费”：当前 PTW/LLPTW 不消费 MXR；生成 schema 决定是否声明该字段，
信号只决定其能否驱动/观测。当前源码位置：`PageTableWalker.scala:436-441`（PTW）与 `1168-1173`（LLPTW）。

## 4. 适配决策

### 4.1 绑定依据与失配规则

可选字段只有 MXR 一项，登记依据不是 Python 属性是否存在，而是**本 DUT loader 返回的生成
artifact 自带 `signals.json`** 与**实际绑定 handle** 的一致结果：

- loader 的默认 API 仍是历史二元 `(cls, argv)`，`native_seed` 逐调用解析；只有 fixture 显式
  `with_schema=True` 才把 schema 交给 env。env 不读取仓库全局配置，也不按 baseline 名称选择分支，
  因此旧 native 目录仍按其自带的 pin 绑定。
- `with_schema=True` 返回的 schema 必须来自本次实际绑定的模块：校验 `module.__file__` 的 artifact
  目录等于请求目录，schema 路径由实际模块目录得到。若同进程内 `_load_package` 缓存 alias 复用了
  其他目录的模块，则明确 `RuntimeError`，要求隔离进程；不卸载缓存、不改 `sys.modules`、不静默换
  baseline。默认二元路径不触发该 schema 校验。
- schema 与 handle 都声明 MXR：绑定真实 pin 到 `csr["mxr"]`，并给出可驱动能力。
- schema 声明 MXR 但 handle 没有：明确绑定失败（`RuntimeError`），不登记为裁剪。
- schema 未声明 MXR 但 handle 多出该属性：明确绑定失配（`RuntimeError`），不据 handle 反推
  baseline。
- schema 缺失、不可解析、为空或没有叶 pin：明确失败；不能把“未知版本”泛化为裁剪。
- 裁剪只对 MXR 生效。其他缺失 pin 仍由直接 schema 属性访问失败（`AttributeError`），
  不进入可选注册，也不存在通用 pin 代理。

### 4.2 公开能力

`PtwEnv`/`LlptwEnv` 暴露两个只读能力接口，不返回 CSR 字典、schema 或 live pin：

- `mxr_input_capability`：每次返回新的不可变 `MxrInputCapability(driveable, reason)`；
  裁剪时 `driveable=False` 且 `reason` 为具名合同说明。
- `has_mxr_input`：上述 `driveable` 的标量便捷视图。

功能用例只据该能力决定是否调用 `set_csr(mxr=1)`；裁剪路径读取能力状态并验证
`set_csr(mxr=...)` 的 fail-closed `ValueError`，不读取 `env.csr`。真实绑定自检可以检查
`env.csr`，因为它是自检而非功能场景。旧的 893e 有真实 pin 时，两个隐式读用例仍驱动
`mxr=1`，旧 RTL 的 `mxr && x` 回落会让它们真实 FAIL；这是旧缺陷，不为单 DUT 增加
baseline override。

### 4.3 oracle 修正

LLPTW 旧节点 `test_stage2_first_perm_mxr_pass` 保留原 nodeid（历史命名），期望从“MXR+X
允许 execute-only 页表”改为“R=0,X=1 的首个 G-stage 页表读被拒绝
（gpf=1/first_s2_fault=1/无 PTE 内存读）”；同一节点保留 R=1 的合法 readable 控制。
PTW 侧新增 allStage 隐式读的对应错误场景，合法 readable 控制复用
`test_normal_all_stage_identity_hptw`。这是用户批准的当前适配扩展，单独登记在
`results/transaction-adapters-20261110/mmu/baseline-and-port-diff.json` 与
`mxr-oracle-change.json`，不混入原事务迁移的零差分结论。

## 5. 未覆盖范围

- 不证明显式 load 的 MXR、`vsstatus.MXR`、SUM、HLVX 或 PMP/PMA 集成语义。
- 不证明 HPTW 自身对 G-stage 页表 PTE 的读取（HPTW DUT 缺 MXR 输入，且其 G-stage walk
  规则不在本层合同内）；本文件只约束 PTW/LLPTW 对 HPTW 响应的权限判定。
- 不改变 `ptw-completion-contract.md`（893e）的历史身份；该合同不能冒充 a0c2。
