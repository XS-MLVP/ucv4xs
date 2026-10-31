# 验证环境完整性：四个会“静默变绿”的错误假设（IFU，2026-10-29）

> 路径迁移说明（2026-10-31）：本文记录中的 *verify/common 为当时源码路径；当前实现已迁入 suites.<group>.<suite> 工程根。历史判定、命令与哈希不据此重标；当前映射见仓库 docs/lessons/suite-namespace-refactor-20261031.md。


本案例按 [归因与证据](../../skills/review/triage-and-evidence.md) 记录。案例 1/2 为
`confirmed-verification`（环境或检查链错误）；案例 3 是**需求定义错误**：验证对象被
端口宽度截窄，最终表现为 `out-of-domain` 的交接面限制；案例 4 是**模型复制实现**：
reference model 把 tdata2 也截成 50 位，掩盖了真实 RTL 偏差（`confirmed-rtl`）。

## 案例 1：复位后 Picker/Verilator 仍施加寄存器随机化

- **原假设**：显式拉高 `reset` 若干拍并释放后，FSM 与数据寄存器已是确定值。
- **反证**：`IfuUncacheUnit` 复位后 `io_req_ready=0`，捕获地址是随机值
  `46432847171544`；三次重跑一致，说明不是竞争而是初始值来源固定。
- **定位**：生成 RTL 的 `ENABLE_INITIAL_REG_` 块在时刻 0 之后仍按 `$random` 写入
  寄存器；仅靠 RTL 复位不足以覆盖这一点。
- **修正**：构造 DUT 时附加 `+verilator+rand+reset+0`，并在 `reset()` 中把所有输入
  先置 0 再拉复位，避免复位释放沿误接受请求。
- **成对对照**：修前该 DUT 11 个用例全部失败；修后全部通过，且同一 harness 的
  `read_pruned` 仍会拒绝把存在的端口当常量。
- **边界**：这是仿真器初始化行为，不代表芯片复位有问题；其他工程若只靠 RTL 复位，
  同样可能出现“首拍随机”。

## 案例 2：删除的端口被“默认 0”掩盖

- **原假设**：`read_optional(name, 0)` 这种写法只是方便读取，缺端口即视为 0。
- **反证**：先用该方法读了 `io_resp_rawInstrVec_31_isCrossBlockInstr`（端口不存在），
  测试仍“通过”；但若真实原因是接线错误或端口改名，同样会静默通过。
- **定位**：firtool 会删除可证明为常量的端口。缺端口本身不是错误，但“默认 0”把
  两种完全不同的情况合并了：常量被删除 vs. 绑定写错。
- **修正**：
  1. harness 只提供 `read_pruned(name, constant)` / `set_pruned(name=constant)`；
     若端口实际存在则**抛错**，避免用“pruned”名义跳过真实端口；
  2. 每次声明都记录 `(name, constant)` 与命中次数，供审计；
  3. 三个删除端口各用模型级证明其常量性：
     - InstrBoundary slot31 cross：对每个 split 与起始槽扫描，最后一槽恒 0；
     - PredChecker lane34 cross：shift=3 时 lane34 只对应压缩 index 31，且 lane33
       在同一扫描中可以跨块（证明功能活着，零是特定于 index 31）；
     - IFU lane35：入队掩码 bit35 恒 0、指令字恒 0，故 `predTaken` 叶被删除。
- **成对对照**：`test_pruned_ports.py` 既验证“真实端口不能声明为 pruned”，也验证
  三个常量声明与模型一致；负对照证明若把任一字段的期望改错，检查会失败。
- **边界**：模型扫描证明的是“在已建模的合法输入域内恒 0”，不是对所有可能
  Chisel 参数组合的证明；换配置后需重跑。

## 案例 3：把端口宽度当成需求，内部宽于端口的部分从未进入功能点

- **原假设**：“重定向携带被归咎取指块的起始 PC”就是需求；端口
  `toFtq.wbRedirect.pc` 是 50 位，所以功能点按 50 位写、比较按 50 位做。
- **反证**：内部 PC 是 51 位 `GuardedPc`（bit50 为溢出/guard 位），而基线
  `FrontendRedirect.pc` 声明为 `UInt(VAddrBits.W)`；消费者
  `IfuRedirectReceiver` 直接 `redirect.bits.pc := wbRedirect.bits.pc`，随后用
  `GuardedPcInit` 重装，截断没有任何加宽环节。构造 guard=1 的取指
  （`GuardedPc = 0x7FF_FFFF_FFFF_FE`）后，DUT 输出
  `0x3FF_FFFF_FFFF_FE`，同拍 51 位 `target` 仍正确。
- **定位**：不是激励没到、也不是比较器没比，而是功能点的语义取自端口，而不是取自
  消费者需要重建的 `GuardedPc`。100% 行覆盖必然包含这条截断赋值，覆盖率与随机化
  都发现不了“少了一位”。
- **修正**：新增 [观察点精度方法](../../skills/design/observation-precision.md)：
  系统扫描“内部宽 / 端口窄 + 消费者赋值”，筛选阶段默认保留所有正确性未建立的字段，
  关闭必须有消费者合同或结构证明；探针固定断言端口宽度，边界变化时强制重开。
- **成对对照**：guard=1 探针证明截断存在；同一探针在端口加宽后应失败（宽度断言），
  防止静默沿用旧 PASS。该限制登记为 `IFU-ENV-005` / R-08，不计入硬件通过率。
- **边界**：本层端口无法表达正确值，所以不能据此判 IFU 行为违规；系统层后果与
  上游后续修复只作佐证，方法的关闭依据仍是消费者合同与端口宽度事实。

## 案例 4：reference model 复制了 RTL 的截断

- **原假设**：`tdata2` 是地址，地址只有 50 位，所以模型也把两边都掩码到 50 位比较；
  随机 `tdata2` 是 64 位，但命中概率极低，测试一直“通过”。
- **反证**：CSR 侧 `Tdata2Bundle.ALL = RW(63,0)`，高 14 位可写可读回；构造
  `tdata2 = 2^50 + pc`（EQ）时 DUT 在 `pc` 命中，构造 `tdata2 = 2^50`（LT）时
  所有 lane 都不命中。全宽语义应为 EQ 不命中、LT 全命中。
- **定位**：`TriggerCmpConsecutive` 与 `TriggerCmp` 都只用 `tdata[VAddrBits-1:0]`；
  模型 `compare()` 也用了 `tdata2 & PC_MASK`，所以 oracle 与 RTL 同错，负对照和随机
  测试都无法发现。
- **修正**：模型改为 PC 零扩展、`tdata2` 全 64 位比较；随机域收缩到机器可生成地址，
  另立两条“超出地址空间”定向用例，当前均 FAIL（R-13）。
- **成对对照**：同一模型在 in-range 配置下继续通过；错误算法/负对照仍然有效。

## 可迁移做法

1. 新 DUT 接入时先问：哪些端口不存在？逐个写“为什么可以是常量”的模型级证明，
   不要用默认值接口。
2. 复位 harness 统一关随机化并清输入；把这一条写进工程约定而不是各用例。
3. 每个模块至少一条负对照：同一观测 + 故意错的期望必须失败。否则“全绿”只证明
   代码跑过。
4. 交接面宽度/单位用 schema 断言固定（本仓库 IFU：PC 为 `[50:1]`、GPA 为字节），
   避免模型与 DUT 单位漂移后仍“通过”。
5. 初步筛选默认留下“正确性未建立”的字段，不用“端口就这么多位”关闭；留下项写清
   关闭条件、承接方和影响，按 [观察点精度](../../skills/design/observation-precision.md)
   维护清单。
6. 写 oracle 时先问“生产者能给出的最宽值是什么”，再决定比较宽度；模型里出现
   `& MASK` 时要说明这是规范约束还是抄了 RTL。两边同时截断会让负对照也失效。

## 相关位置

- harness：`suites/frontend/ifu/ifuverify/common/dut.py`
- 门禁：`suites/frontend/ifu/tests/framework/`
- 模型扫描证明：`tests/framework/test_pruned_ports.py`
- 交接面限制：`suites/frontend/ifu/docs/upstream-review-20261029.md`
