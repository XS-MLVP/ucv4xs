# ForwardModule阶段报告：字节来源、完整依赖与分阶段转发

## 状态

**已完成本轮功能/覆盖迭代和公开历史审计，但受3项真实缺陷阻止验收，NOT_PASS。** 完整冻结回归184例165通过/19失败、64/64 reached、61/64 checked，本体DA253/253。17个真实生产者域失败与2个仅接口孔洞mask失败分列；不能以行满或通过用例数替代验收。独立推进VirtualStoreQueue，保留本模块全部普通失败。

真实目标为开源893e1580b的单文件ForwardModule，64 SQ槽、3查询lane、2跨页输入；原样build/实例化走钟PASS见`results/builds/20261018T081233332925Z-forward_module/report.json`。实际695输入/129输出，**无reset/ready/s1Resp/perf端口**。工具与RTL未修改；本轮重新核验53份原始RTL SHA一致，开源工作树干净。

## 已实际完成的验证

[用例前合同](../contracts/forward-module.md)先定义15类微架构行为，包含88fb444c574a52c1e33f682f5ab6770204cb923f（#6693）的VA别名旧值历史回归；只读核对该提交，不把其修复记录当本UT通过。

已实现领域事务/695输入适配、独立公开端口解码、逐拍参考与被动观察、本地fixture及62种可读语义情形。参考按标量SQ顺序、字节范围和查询UID建模，不读DUT内部寄存器。区分S1保存的data/mask/选择与S2实时PA/MDP输入；无reset启动用公开无效查询排空。

另外增加**独立PA字节来源安全性质**：稳定bank下，每个被当作安全转发的有效字节必须来自最年轻的较老、有效、物理范围/byteMask覆盖该字节的store。此检查不复用详细时序模型的VA重叠域，避免参考与RTL共同漏掉别名。

| 运行 | 用例结果 | 本体DA | 语义checked |
|---|---:|---:|---:|
| `forward-initial-01` | 10 PASS/3 FAIL | 250/253，98.81% | 13/62 |
| `forward-expanded-01` | 31 PASS/3 FAIL | 253/253，100% | 24/62 |
| `forward-expanded-02` | 165 PASS/19 FAIL | 253/253，100% | 61/64 |

首轮3条未覆盖行为4675/6736/8797，均为查询lane的回绕低年龄段选择树；原始needs_review清单保留，`initial-audit.json`逐项映射到已有年龄/优先选择情形。补deq60、SQ112/slot48、load114的低年龄段及全部64槽×3lane真实数据检查后命中，未排除可达行。

## FWD-ALIAS-001：跨word别名遗漏年轻物理覆盖

三lane各自独立复现，普通同word的历史#6693回归仍通过：

| 对象 | SQ顺序 | VA | PA范围 | 原数据 |
|---|---:|---:|---:|---:|
| 老store A | 0 | `0x10010` | `0xabc010..0xabc013` | `0x11111111` |
| 年轻store B | 1 | `0x2000c` | `0xabc00c..0xabc013` | `0x2222222222222222` |
| load | 2 | `0x10010` | `0xabc010..0xabc013` | 应取B尾部`0x22222222`，或必须要求重放/等待 |

实际S2：**valid=1、mask=0xf、data=0x11111111**，forwardInvalid/matchInvalid/addrInvalid/dataInvalid全0。两个store地址和数据均有效；B合法跨16B但不跨页，page offset一致，无kill、MDP或额外取消。`NewStoreQueue.scala:1931-1949`允许此size/VA/PA高位与offset-free mask=0xff组合，不是虚构位拼接。

源码462～476的“next16B”需要VA tag相同；487～511以该VA匹配决定load相对store范围是否加16，再将这个重叠集合用于606～625的PA CAM范围。B经不同VA，未进入VA相对的跨段重叠集合；它真实的下一PA段命中随后被排除，漏掉了更新的物理字节。这里只定位固定版本结构和公开失败，不作完整形式化证明。

`tools/audit_forward_initial.py`不导入参考模型，单独从公开输入SQ/VA/PA高位/size/mask/data与S2输出重建这3个反例，保存UID相位、journal及SHA到`results/forward-initial-01/initial-audit.json`；核验159份源码快照和产物/build SHA。不是完整Forward仲裁/活性审计。

15个对照（3lane×年轻/地址无效/无字节重叠/相同VA/不同PA页）全部通过；没有改RTL、降低安全性质、xfail或跳过失败。expanded-01的161份启动文件在结束时全部SHA一致。

## 补全剩余功能与两个新反例

后续已实施全部访问长度（Q编码4～7）、16偏移/mask、最年轻缺数据不回退、strict/精确MDP/退休/窗口、S1 kill和背靠背、CBO、两个跨页UQ的正反关系及四圈年龄、S1快照/S2 live变化。分组调试运行不替代完整冻结回归：

| 运行 | 实际结果 | 边界与用途 |
|---|---:|---|
| `forward-semantic-directed-01` | 114 PASS/6 FAIL，5 deselected | 定向分区，新跨代依赖身份失败 |
| `forward-bytes-random-01` | 3 PASS/2 FAIL，120 deselected | 全尺寸/偏移扫描通过；原孔洞mask随机仅为接口压力 |
| `forward-range-mask-01` | 2 PASS/10 FAIL，123 deselected | 真实连续PSQ mask下2随机+6最小定向失败；2接口mask压力仍失败；2对齐store随机完整排空通过 |

**FWD-SQID-001**：物理窗口deq=SQ60、upper=SQ124，slot48实际代表SQ112且地址有效/数据缺失；load SQ128/129时三个lane都返回`dataInvalid.valid=1`和SQ176（first1/second0/value48），应为SQ112（first0/second1/value48）。SQ124/127同类对照通过。load仍在虚拟SQ年龄域内，不能为了通过把查询收窄到64项物理窗口。源码550～554用load generation恢复低年龄段身份，裁剪窗口时该假设不成立。

**FWD-RANGE-001**：单个store在PA`0xabc00c..0xabc013`写8B，真实生产者连续mask=`0xff`。分别读`0xabc000`和`0xabc010`的word对齐16B load，三lane实际都给出mask=`0xf00f`、所有重放/依赖标志为0；实际可写字节只允许mask=`0xf000`和`0x000f`。多余位没有物理producer，不能用旋转后的参考mask证明安全。两组真实PSQ mask随机同样失败，对齐store的两组完整随机通过不是未对齐用例的替代品。新增15个必要条件对照保留完整原失败。

上述两项分别为既有依赖身份与字节范围功能中遗漏的情形，功能分母62→64，旧快照不修改；不是为了行覆盖添位，也不删减分母。任意孔洞mask压力明确单列UNIT-INTERFACE，最小反例不依赖这种输入。未修改目标RTL、加入xfail/skip或更改严格预期。

## 完整冻结回归与审计

完整回归`forward-expanded-02`包含全部184例，无-k缩减、deselect或skip；15个range必要条件对照均通过，原全部失败仍为普通FAIL。64/64 reached、61/64 checked，未通过的严格语义恰为`FWD-VAPA.alias_cross_word`、`FWD-WAIT.clipped_identity`、`FWD-BYTE.range_mask`。163份启动文件结束SHA与冻结副本一致，全部产物/build SHA已审计；53份原始RTL SHA再次一致，开源XiangShan工作树干净。

`tools/audit_forward_trace.py`不导入参考模型或读取DUT内部寄存器，审计5599条连续公开记录：3196次接受=278次kill+2906个实际有效响应+12个失败时尚在途查询。有效响应中2881个所在边沿完成严格检查，25个位于失败边沿（含同拍其他lane）不计成功；165个PASS用例均最终排空。全192个load lane×64 store slot具有成功见证，13773次安全字节检查、3条kill后新UID完成证明。每个checked语义proof的UID必须已经通过公开响应检查；proof样本的计数/first/last tick与xreactor provenance逐项相符。失败分类为ALIAS3、SQID6、RANGE10（其中2个接口边界）。见`results/forward-expanded-02/trace-audit.json`。

完整审计的`live_bank_observations`仅统计post-edge，故为0；定向变化发生在pre-edge，不能误解为没有live检查。原审计文件不改写，另由`tools/audit_forward_live.py`从实际前后公开bank/输出验证6条pre-edge见证：3lane的MDP ready解除等待，以及3lane的PA/边界变化触发matchInvalid而旧data仍保持S1快照，随后新UID获得新data。见`live-audit.json`；结束源一致性见`end-source-check.json`。

其余功能补例已实际执行，剩余严格验收与未对齐随机的完整排空受上述RTL失败阻止，不能宣布Forward通过。任务保持局部blocked而不是整体unmet；接下来独立推进VSQ。

真实VSQ/Deq/PSQ/StoreQueue、LoadQueue和LsqWrapper组合都保留完整范围。
