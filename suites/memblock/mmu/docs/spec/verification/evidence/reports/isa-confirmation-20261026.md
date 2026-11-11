# ISA 对照确认（2026-10-26）

## 依据与边界

对照 RISC-V Ratified Specifications Library 固定版本 v20260120：Supervisor
1.13、Hypervisor 1.0、Machine 1.13。版本链接、具体章节及本地 Fence.scala
编码源 SHA-256 见 `evidence/soundness-20261025/isa-sources.json`。官方正文已通过
服务端网页读取；客户端取网页超时，因此没有保存或虚构正文 SHA-256。

这是行为对照，不意味着该 RTL 声明实现规范的所有可选扩展，也不是 CPU/CSR
退役级 ISA 测试。Picker 公开 TLB/MMU 端口与 ISA 操作数之间还必须核对转换层。

## 规范结论及误报处理

| 项 | ISA 要求 | 本工程判定 |
|---|---|---|
| SFENCE.VMA 全范围 | §11.1.2.1：指令操作数 rs1=x0、rs2=x0 覆盖全部地址/ASID。x0 指寄存器身份，不是其值为零。 | 本地 `Fence.scala` 输出 rs1/rs2 为 `imm` 中寄存器编号等于零，故 bundle 1/1 才是全范围。原 0/0、addr=0 对非零 VPN 要求失效没有依据；撤回缺陷归因。 |
| SFENCE 地址单位 | 非 x0 的 rs1 提供映射内虚拟字节地址，非 VPN。 | 目标 VPN 转为 `vpn << 12`；目标页 PTE 改写后必须不再采用旧翻译。 |
| SFENCE 精细范围 | 同章明确允许 over-fence，甚至实现成全刷新。 | “未目标页必须仍 hit”“非目标 ASID/VMID必须保留”只能检查实现优化，不是 ISA 正确性要求。失败须区分额外 miss 与错误旧翻译。 |
| satp 写入 | §11.1.1.11、§11.1.2.1：写 satp 不隐含排序/失效；可采用规则允许的旧/新映射。另外，在 satp 有效时已开始、此后 satp 不再有效的翻译，未匹配 fence 时不要求完成或终止。 | 必须区分旧在途翻译、切换后新请求及 inactive 条件；既不能将所有 timeout 统一豁免，也不能声称所有 no-fence 翻译都必须完成。旧 responder timeout 不能证明任一种归因；当前 liveness 仍未确认。 |
| 1GiB/2MiB 大页对齐 | §11.1.3.2 step 5、§11.1.4：非最低层 leaf 的低 PPN 段必须为零，否则原始访问类型 page fault。Sv39 1GiB 要求 PPN[17:0]=0，2MiB 要求 PPN[8:0]=0。 | 修正 PageMemory level=2 真正生成 root leaf 后，旧 wrapper PMP 正例 PPN=0x3000 非法，硬件 PF 正确。正例用 0x80000；新增原值负例断言 PF=1、AF=0。 |
| HFENCE.GVMA | §14.1.3.2：rs1 是 GPA 右移 2 位；rs2 是 VMID；允许更广刷新。 | 不得通用套用 SFENCE 的 VA/VPN 地址换算。现有 VMID/all 例不能证明 GPA 定点失效。 |
| Guest fault/GPA | §14.1.2.8、§14.1.5：htval 可为零或故障 GPA 右移 2 位；隐式 VS 页表读取故障对应 PTE 的 GPA。 | UT 检查的是内部原始 gpaddr，不是已编码 htval。端口 replay PASS 不能证明 CSR/异常退役编码；fake-PTE level3 内部编码也不能由 ISA 单独判错。 |
| PMP/PMA | Machine §2.1.7：PMP 作用于走表访问；平台可有更粗 grain，NA4 可不可选；PMA 属性由平台定义。 | TOR/read/cacheable 等测试有意义，但固定 PMA 初值来自该 SoC 配置，不能宣称为 ISA 通用值。原 live DUT 采期望为自指 oracle，已移除。导出配置寄存器不是完整 CSR WARL/读回验收。 |
| A/D 位 | Supervisor §11.1.3.1/3.2：行为依赖 Svade 或硬件 A/D 更新方案；不能脱离配置要求所有 A=0/D=0 一律 fault。 | 现有断言约束此 RTL 配置，未宣称穷尽全部扩展与原子更新/并发语义。 |
| 并发与替换 | ISA 不指定 LLPTW slot 数、memory read 合并次数、PLRU 次序、最低空闲拍数。 | 这些需要真实 fire、响应完整性和局部接口契约。原 LLPTW/Bitmap/shared-leaf 停顿由验证漏采导致；撤回 RTL 根因。两次请求可合并读取，不能硬要求两次访存。 |

## 保留的未确认项

这里 satp 的 active 按有效特权级 S/U 判定，不等同于“刚写了 satp”、
“更换页表根”或“切换 Bare”。上表在途翻译例外必须满足规范所说的 active→inactive
条件，不能直接套用于所有 satp 切换或切换后新请求。

- fake-PTE 缓存 level 与后续 guest fault/GPA 的架构可见影响，需退役级/CSR 对照，
  现有 level0 用例只刻画当前实现。
- no-fence 情况的 liveness、HFENCE.GVMA 定点 GPA 路径、A/D 原子更新/并发、
  完整 privilege/异常优先级交叉覆盖没有由本轮 PASS 自动证明。
  特别是 no-fence 需先划分 satp 有效性和请求时间点，不能跳过 §11.1.1.11
  对旧在途翻译的完成/终止例外。
- 标准 ISA 不定义这里自有 Bitmap 检查接口，也不能替它补造架构依据。
- 结构/数据极性残余继续保留；缺少 direct-way selector 不是不可达证明。
- MBIST/DFT 不在功能 UT 范围；整颗 MMU/SoC 未签核。

## 证据

官方规范固定页面：
- `https://docs.riscv.org/reference/isa/v20260120/priv/supervisor.html`
- `https://docs.riscv.org/reference/isa/v20260120/priv/hypervisor.html`
- `https://docs.riscv.org/reference/isa/v20260120/priv/machine.html`

本地对照：两份 `src/main/scala/xiangshan/backend/fu/Fence.scala`；
`tests/l2/soundness_helpers.py`、`test_isa_misaligned_1g_leaf_is_page_fault`；
`soundness-isa-controls-01` 为 16 PASS，包含两个大页负例、修正 PMP 正例与
13 个 checker/model 自检；这不是最终 DUT 总数。
