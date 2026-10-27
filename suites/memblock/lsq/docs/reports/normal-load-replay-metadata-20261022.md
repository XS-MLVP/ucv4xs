# 正常标量Load：Replay原UID元数据与活跃依赖身份

当前状态：**formal02三层定向、完整九build after、完整专项审计及幂等终点复核
均已完成；已接入47补例/58源检查/38-DUT索引。整体ACTIVE_NOT_ACCEPTED。**
固定开源893e1580b原样RTL/Chisel，使用真实Picker DUT与X Reactor原完整参考，
默认无逐拍JSON、波形或完整新源码副本，性能缓存关闭。

## 请求到证据

| 要求 | 证据 |
|---|---|
| 先定义人类可读功能点 | `docs/contracts/normal-load-replay-metadata.md`，identity/scalar/address/cache/translation/hold/finish，先于新实现。 |
| 实际层次逐层验证 | Replay叶子→真实LoadQueue→真实LsqWrapper，不替换父级下级模块，三层完整fixture及参考保持。 |
| 独立刺激及功能检查 | `lsqverify/normal_replay_metadata.py`只使用公开输出选择原slot和原bank，外部UID/依赖身份台账不读DUT/model私有状态。 |
| 用例 | `tests/replay/test_normal_metadata.py`、`tests/load_queue/test_normal_replay_metadata.py`、`tests/lsq_wrapper/test_normal_replay_metadata.py`；独立小探测在`tests/normal_replay_probe/test_probe.py`。 |
| 三类覆盖集合、源码和失败保持 | `tools/audit_normal_replay_metadata_v1.py`，定向三对fresh before/after，完整旧1750节点与12新节点，独立dat分母，不OR。 |
| 完整范围与真实终态 | `results/normal-replay-metadata-contributor-regression-01/normal-replay-metadata-contributor-evidence-v1.json`，1762节点/9build，1750旧结果和196份失败全文精确保持。 |
| 受影响索引及原件保护 | `tools/audit_normal_replay_post_round_v1.py`，只重建新证据和四份受影响索引，旧版本按SHA归档，不重跑DUT或历史全链。 |
| 剩余缺口与精确源边界 | `tools/audit_normal_replay_remaining_v1.py`，九build三类缺口集合均为统一原分类库存子集；三层fullva高位252点硬连零，仍留分母。 |
| 上游来源与限制 | 原因/S3/VA/fullva14段固定源证据、FTQ4段更正、5位ID存储零扩展源证明；不声称上游native分配器或全核验证。 |

## 1. 每条原UID做了什么

四种路径分别为真实接口refill、L2 hint、fast TLB hint、slow TLB hint。每条Load
先绑定当前依赖ID与另一个不同地址/VPN的活跃decoy ID，容量域16、仅两外部
依赖同时活跃。先回应decoy，原Load必须持续阻塞；再回应匹配ID，按源码规定
N/N+1/N+2边沿出现原Replay UID，而非只观察“以后终于valid”。

首次父级S3是C_DM/C_TM单原因、update0且准确revoke，不能释放LQ。正确唤醒后
背压3拍，全部已定义payload及同slot稳定；实际Replay握手与原bank LDU的S0同拍，
接S1翻译、S2 RAR/RAW、S3原slot反馈cause0/update1，直到真实LQ释放才计完成。
叶子只声明反馈释放Replay，不借父级VLQ检查。Wrapper SQ实际为空，真实Forward
无字节命中且无错误；首次TLB miss用S1Kill，不期待被kill路径产生valid。

每层四路径，每路径8轮×120顺序完成UID=960；每轮公开slot集合0..119。是全部
slot的顺序生命周期/复用，不声称同拍满池，也不假设120个未执行Load驻留IQ。
操作为合法LB/LBU/LH/LHU/LW/LWU/LD，size/mask/自然对齐/PA页内偏移/lastBeat
一致；无中途reset、取消捷径或非法全宽opcode。

首次Sv48负地址fullva64为canonical，保存的VA50在LRQ公开fullva只作零扩展。
两者逐字段区分；不能用第一次64位值要求一个不存在的LRQ64位存储。Cache返回
数据值、上游native TLB/Cache/ROB/Frontend及分配器选择ID的历史不在该DUT范围，
因此不声称这些实现已验收。

## 2. 实际校准与诚实修正

1. probe01三层四路径12/12 PASS，原192个小探测UID全部本地完成；formal01三层
   15→19、12→16、9→13节点PASS。各层四路径共3840原UID，真实功能/覆盖结果
   保留，但正常Frontend投影不能据这些PASS自动成立。
2. 更深入固定源核对发现：FetchBlockSize=64B，FTQ offset是非压缩指令的**结束
   半字**。新helper原先沿用了16B块/起始offset假设。三个01派生报告已显式标记
   `UNIT_INTERFACE_FTQ_START_OFFSET_UNPROVEN_FRONTEND`，按旧SHA归档；原dat/JUnit
   和所有比较检查不改。
3. 只改本轮新helper为每16条一个64B块，结束半字1/3/.../31，witness保存并审计
   FTQ flag/value/end-offset。用内存重建旧helper并恢复整个旧验证库聚合SHA证明
   sole diff；不额外存完整源码。probe02再次12/12 PASS，原192UID及FTQ投影检查
   全部通过。正式02在新目录完整验证，不用小probe替代960UID路径。
4. 正常程序源投影补强不改冻结旧RAW helper/actor/model或旧测试。此前RAW报告中
   16B/offset0,2,4,6也仅是保留FTQ身份的LSQ接口声明，**不是本次已证明的64B
   Frontend轨迹**；其原功能结果不受影响，但不提升为完整上游可达性证据。

## 3. 5位ID存储与4位输入的真实边界

每DUT两族ID存储各120项×5位，实际公开ID输入只有4位。可复现源审计逐项核对
每族120个reset写0和360个clocked `{1'h0,4bit_input}`写入，合法低4位每族960
方向点是动态目标；高位每族240方向点是本配置post-reset零扩展边界。

三层所有分母与高位未命中保留，动态增益记0，不驱动16..31，不笼统把全部
未复位payload都归为初始化。其他opcode/vector/hyper/异常域继续保留；独立
Replay exception有效写后恒0证明也不替代公开S3异常功能。

### formal02实际定向结果（不是完整回归增益）

| 真实DUT | PASS节点前→后 | toggle命中前→后 /总数 | 新branch | 新raw line |
|---|---:|---:|---:|---:|
| LoadQueueReplay | 15→19 | 22701→60641 /79904 | 837 | 1004 |
| LoadQueue | 12→16 | 49997→97334 /204148 | 2075 | 1040 |
| LsqWrapper | 9→13 | 112388→146649 /322010 | 902 | 40 |

每层3840个原UID、四路径×8轮全120公开slot，三层共11520原UID完成，均有
错活跃ID负例、精确首次valid边沿、3拍完整metadata保持和实际消费/反馈。
两父级均等待实际LQ释放，叶子不借父级结论。每层已知写入目标：VA12000、
普通标量opcode位1/2/4共720、合法MSHR低4位960、TLB低4位960方向点全部命中；
其余opcode与每族第5位仍在分母。三对before/after的source/build/三类点全集相同，
旧节点结果、public stream和旧native hit保持。LCOV闭包行另列JSON，rawline点
不是原始源码行。所有上述定向分子不回填完整回归或统一regression15。

## 4. 完整贡献范围，不重复完成的基线

原八build1569节点作为已完成真实基线，不重跑。新增Replay上下文不能只跑
主目录：完整贡献者实为181=统一回归179（含48外目录endpoint）+两个既有
全宽metadata/全池checkpoint PASS。实际181节点177 PASS/4原FAIL，所有179旧
结果与stream精确保持。第一次审计按预估180断言exit1，原失败日志SHA保留，
只修正审计集合后续审成功，**181节点DUT没有重跑**。

完整新选择为原八build FULL_PATHS + `tests/replay` + 两个原Replay endpoint文件，
1750个旧节点+12新节点，实际1762节点，**1566 PASS/196 FAIL、0 ERROR/SKIP**。
196失败是原八build192加新增纳入的4个**既有**Replay失败，不是新例失败。
JUnit/manifest、全部原贡献者及失败全文已核对；完整与三层定向都是独立真实
运行，不合并dat、不回填统一38-DUT。

### 实际完整增益与原集合保持

| 真实DUT | 独立完整基线 | 完整toggle命中前→后 /总数 | 新toggle | 新branch/raw line |
|---|---|---:|---:|---:|
| LoadQueueReplay | 181节点Replay完整旧贡献者 | 71645→73467 /79904 | 1822 | 0/0 |
| LoadQueue | 八build1569节点中的完整LQ贡献者 | 149506→160872 /204148 | 11366 | 0/0 |
| LsqWrapper | 八build1569节点中的完整Wrapper贡献者 | 282950→289897 /322010 | 6947 | 0/0 |

这些是native独立build上下文中的原样非Picker点，不能按唯一源代码去重口径
相加，也不是上文定向子集中的37940/47337/34261增益。六个未新增测试的build
原dat字节SHA全等；九个build全部line/toggle/branch点全集保持，旧hit无丢失。
LCOV闭包行亦无新增：LQ50513/50520、Wrapper59595/59602、LQU3169/3175，原20行
边界仍保留；native rawline点全命中不等于这些源码闭包行已消失。

原1750个节点的结果及196份失败全文SHA精确相同：
`7762ca928cf073b58cfd3ae9e4b217f3fbee70332fea7481686e33a43de54cc0`。
三层12份完整witness与formal02逐字段全等；每层3840UID的已知写入、精确唤醒、
背压与实际释放均重新独立审计。Wrapper原2403份public/check/actor stream全等；
原162库文件、198测试文件及pytest/manifest/README聚合保持，只明确排除本轮
新增helper/4个test计算旧集合，不混淆新全source与旧全source。

native贡献Replay181→185、LQ257→261、Wrapper801→805；Forward186、PSQ70、
SQ90、VSQ50、LQU73、UQ42均保持。运行实际耗时4620.324289632961秒，默认load
调度24workers、缓存关闭；新范围和资源条件不同，不据此声称与旧整轮同比加速。

`remaining-gap-selection-v1.json`逐build核验：当前三类缺点均是原统一分类库存的
子集，没有新缺点被偷偷遗漏分类。当前toggle余量Replay6437、LQ43276、
Wrapper32113、LQU12169、SQ6290、PSQ3300、Forward2380、VSQ823、UQ72。
其中Replay源本身分别4970/10531/5022；正常标量VA、opcode位1/2/4和合法4位
MSHR/TLB已知写入方向均闭合，但其他cause/NC/向量/Hyper/依赖类型仍需语义补例。
源中三路`fullva={14'h0,VA50}`精确赋值另证高位252方向点硬连0；它不是初始化
随机性，也没有修改分母或计动态增益。

## 5. 审计入口及剩余范围

- 原命令保存在各运行`command.json`；fresh目录禁止覆盖旧运行。
- 定向/完整：`python3 -B tools/audit_normal_replay_metadata_v1.py --full`。
- 独立Replay基线续审：同脚本`--replay-baseline-only`，不会运行DUT。
- 当前索引接入：`python3 -B tools/audit_post_regression_v1.py lsq-progress-regression-15 --normal-replay-index-only`。
  已加范围保护：旧44报告入口在47报告接入后会明确exit2而不改索引，避免倒退。
- 终点复核：`python3 -B tools/audit_normal_replay_post_round_v1.py --capture`后运行
  同脚本不带参数；重新审三对定向、新完整九build与受影响索引，核对指纹及归档
  幂等，不重跑任何DUT，不冒称历史完整审计全链再次运行。
- 整体仍须保留SID、strict、disabled、混合排空、头许可、release-wait、取消、
  FP/vector/hyper/跨页/异常、完整核容量资源历史、全38-DUT新统一回归及最终存储
  审计。本轮合法标量域补例不删除其中任何一项，不以绿色子集作整体验收。
- Python验证代码自身仍未采集line/branch代码覆盖率，toggle不适用于Python。
  上文所有三类指标均为真实RTL，不能用来冒充测试代码覆盖率。

### 实际索引与幂等终点

- 首轮新完整证据/索引审计真实exit0，69.603775秒；新公开入口实测exit0，
  87.525896秒。旧`--raw-owners-index-only`入口在当前图上明确exit2，实测四索引
  字节未变，不把这个有意范围拒绝误报为DUT失败或审计隐瞒。
- capture后重新执行三对formal02定向审计、完整九build、剩余库存/fullva常量边界、
  VSQ条件局部引理及四受影响索引，真实exit0，189.589431秒。
- **61份关键报告SHA幂等、933份原件/日志SHA保持、无重复归档、0次DUT重跑**。
  报告为`results/lsq-progress-regression-15/normal-replay-round-post-audit-v1.json`，
  实际log/耗时receipt也原样保留。四索引旧字节按SHA归档，其余39份旧报告保持。
- 当前索引47个独立定向证据、58份源检查、38-DUT矩阵；最新9build1762节点，
  统一38-DUT仍2330节点2103PASS/227FAIL，不回填新分子或跨上下文OR覆盖。
  “旧命中保持”门禁PASS只是覆盖证据一致，未消除任何原功能FAIL；包括
  `OPEN_HEAD_PRECOMMIT_FLUSHSELF_BOUNDARY`仍required=true/waived=false。
- 下一补例仅有`remaining-gap-selection-v1.json`选点，尚未写下一合同/测试或
  启动下一DUT运行；原source域、严禁skip/xfail/放宽检查等要求持续有效。

### 等待完整运行期间的下一边界筛查

`results/normal-replay-original-contributors-01/next-vsq-release-wait-local-lemma-v1.json`
记录VSQ release自等待的**条件性局部引理**：在明确假设活动项连续、ROB/物理
释放资格均为前缀、无覆盖/别名时，当前头已退休意味着前一拍延迟退休数为0；
进入release的边沿已清除该头，头指针本拍不动，所以下一拍立即离开release。
这解释了为何仅增加长退休前缀并不必然击中release自等待，避免重复已完成的
release→walk用例来刷同一方向。

独立枚举8181个局部状态组合，固定Chisel4段及三DUT状态写入源码已核验；但它
只有16项lookahead的局部抽象，**不是128项实际VSQ的完整可达性证明**。128项
所有allocated写入/优先级、环绕复用、ROB former关系、0flow/vector快照、取消及
dispatch覆盖等五类归纳义务尚未闭合。因此三条release-wait仍是原
`existing_feature_missing_case`，未豁免、未删分母、动态增益0；已证明的state3
边界也不因此重开或混为一谈。
