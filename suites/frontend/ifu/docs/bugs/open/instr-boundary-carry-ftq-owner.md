```ucv-bug
{
  "id": "R-14",
  "title": "InstrBoundary carry 误标跨块，导致完成指令的 FTQ 归属错误",
  "kind": "rtl",
  "versions": [
    {
      "baseline": "public-893e1580b",
      "status": "open",
      "evidence": [
        "tests/instr_boundary/test_instr_boundary.py::test_carried_upper_half_cannot_acquire_block_one_ownership",
        "tests/ifu/test_ifu_fetch.py::test_recovered_half_instruction_keeps_its_completing_ftq_block",
        "docs/spec/verification/transaction-adapters.md"
      ],
      "note": "端口合同域真实偏差；真实 FTQ 生产可达性经后续复核撤回，原 FAIL 保留。"
    },
    {
      "baseline": "public-a0c2a26cb",
      "status": "open",
      "evidence": [
        "tests/instr_boundary/test_instr_boundary.py::test_carried_upper_half_cannot_acquire_block_one_ownership",
        "tests/ifu/test_ifu_fetch.py::test_recovered_half_instruction_keeps_its_completing_ftq_block",
        "docs/spec/verification/exit-criteria.md"
      ],
      "note": "2026-11-08 只读复核：InstrBoundary.sv 与旧基线逐字节相同，三条反例逐值复现；R-14 仍 blocking/open。"
    }
  ]
}
```

# InstrBoundary carry误标跨块，导致FTQ归属错误（R-14，2026-11-01）

## 2026-11-08 收口（只读复核，未修改 RTL）

**根因（固定基线逐行核对）**：

| 位置 | 事实 |
|---|---|
| `frontend/ifu/InstrBoundary.scala:84-92` | `crossBlockFallThrough` 只检查 `fetchBlock(1).valid && !fetchBlock(0).takenCfiOffset.valid && i === takenCfiOffset.bits && !blockSel(i) && blockSel(i+1)`。**没有检查 `boundary(i)`（该槽是否真的是本窗口的指令起始）** |
| `frontend/ifu/InstrBoundary.scala:114` | `isCrossBlockInstr := crossBlockFallThrough && !maybeRvc(i)`；carry 首槽的 `maybeRvc(0)` 来自上半字低两位，低两位为 11 时即为 0，于是 `cross[0]=1` |
| `frontend/ifu/Ifu.scala:334-339` | carry 重建只覆盖 `pc`、`data`、`isPrevEndHalfRvi`、`endOffset`，**不覆盖 `isCrossBlockInstr`** |
| `frontend/ifu/Ifu.scala:540` | `ftqPtr := Mux(s2_blockSel(i) \|\| s2_isCrossBlockInstr(i), fetchBlock(1).ftqIdx, fetchBlock(0).ftqIdx)` → 错误的 cross 位直接把完成槽的 FTQ 身份换成块 1 |
| `frontend/ifu/Ifu.scala:559-561` | 同一 `select` 参与 `isLastInFtqEntry` 计算，错误归属会同时影响 FTQ 末项标记 |

正确的合同是：carry 首槽完成的是上一个窗口的指令，它不是本窗口的新起始，
因此即使它恰好落在块 0 的最后一槽，也不构成“跨到块 1”。

**最小复现（固定基线，端口域）**：

- leaf：`tests/instr_boundary/test_instr_boundary.py::test_carried_upper_half_cannot_acquire_block_one_ownership[upper-half-low11]`
  场景 `size0=1, taken=0, block1=1, carry=1, total_end=3`；上半字 `0x13`（低两位 11）
  时 DUT `is_cross_block[0]=1`，期望 0。同参数上半字 `0x10`（低两位 00）为 PASS 对照。
- 批量：同一文件的 600 个随机窗口在 `(137, 254, 406, 477, 529)` 五个样本上失败，
  差异一律是 `is_cross_block[0]: expected 0, actual 1`。
- 顶层：`tests/ifu/test_ifu_fetch.py::test_recovered_half_instruction_keeps_its_completing_ftq_block[upper-half-low11]`
  在 invalid-taken 恢复窗口上得到 `ftq[0][1]: expected 32, actual 33`（块 1 身份）。

**影响**：完成槽的 `ftqPtr` 与 `isLastInFtqEntry` 归属错误 ⇒ 后端/FTQ 把这条指令
记到错误的 FTQ 项，训练与恢复身份错位；指令字、PC、endOffset 本身正确，所以只靠
指令流比较发现不了。生产可达性仍按 2026-11-01 复核结论处理：短 non-taken 窗口不满足
真实 fall-through 长度要求，严格生产者对照通过，因此保留为**端口合同 FAIL**，
不宣称已证明生产可达。

**上游只读检索（2026-11-08）**：本地镜像 `origin/kunminghu-v3` = `2145ba1c9`，
比基线 `a0c2a26cb` 前进 10 个提交；`git log --all -- InstrBoundary.scala` 无基线之后
的提交，`git diff --stat a0c2a26cb..origin/kunminghu-v3 -- src/main/scala/xiangshan/frontend/ifu`
为空。**固定基线与本地已知上游最新状态都没有修复 R-14**；未访问网络、未提交上游。

**关闭条件**（未变）：只让本窗口真正的起始指令产生 cross 标记，并复核 carry 重建后的
FTQ/redirect 归属；修复后 leaf 成对、原 600 随机与顶层恢复反例必须全部转 PASS，
正常上半字对照不得回归。

**2026-11-07 新基线复验（`public-a0c2a26cb`）**：`InstrBoundary.sv` 与旧基线
`893e1580b` **逐字节相同**（sha256 `cc9ed7cb…`），上游 63 个提交未触及该模块。
完整 seed1 中三条反例逐值复现：原 600 随机窗口仍是同一组
`(137, 254, 406, 477, 529)` 且差异均为 `is_cross_block[0]: expected 0, actual 1`；
leaf 成对反例与顶层恢复反例分别保持 `cross[0]=1`（期望 0）与
`ftq[0][1]: expected 32, actual 33`。判定、根因、生产可达性撤回结论均不变，
R-14 仍是 blocking + open。

## 基线与判定

`public-893e1580b` / DefaultConfig，来自完整香山RTL的现有InstrBoundary与Ifu原生闭包。
没有修改RTL、重建native、登记XFAIL或把错误改为期望。该问题是**端口合同域**中的
硬件偏差，同时暴露旧参考模型与激励的验证缺口；现保留原FAIL。**后续生产者审计撤回
此前“真实FTQ可达”的过强结论**，见下节；不能将该FAIL自动当成生产缺陷。全仓活动适配
目标尚未完成，原运行的日期/数据/判定不重标。

## 后续生产者复核：原可达性论证不充分

公开基线`Bpu.scala:325-329,367`在没有taken时选择`FallThroughPredictor`；其64-95行
要求取到`min(align32(start)+64,nextPage)`，不只是小于该长度。
`FtqFetchReq.size=(endPosition+1)-startVAddr[4:1]`，双fetch还须同页及总size不超过32。
原顶层序列的首请求第二块size1/non-taken和恢复请求第一块size1/non-taken只检查了
上界，未满足完整fall-through长度。先前在下方写“最终序列受约束”不能证明生产可达。

实际native成对诊断`results/ucv-goal-ifu-top-uncache-ledger-20261101/producer-carry-diagnostic.json`
将首窗口改为size1/17、taken1/0，恢复窗口size1/3、taken1/1；两种高半字的FTQ归属均为
`(0,32)`，恢复时均产生正确notCfiTaken跳转至0x1040。当前生产agent上的等价合法控制
`test_real_ftq_extent_and_taken_carry_completion_keep_block_zero_identity`也完整检查这些
事件。它们是收紧论证后的正常控制，不是删掉旧反例或修改旧输入让FAIL变绿。

这次控制还发现独立模型对carry硬编码`pred_taken=0/branch_type=NONE`，遗漏完成槽的
预测与完整ISA属性。现按完整保存字解码，并在块0仅有carry且taken时把预测归给carry；
旧错误期望在相同实际snapshot上必须失败。该修正不放行R-14的错误FTQ，也未改变原
600样本或原顶层端口反例。尚未证明同一偏差符合完整生产历史；剩余处置须区分端口
鲁棒性合同修复和生产可达性论证。

## 合同和独立答案

一条32位指令的低半字可能在前次fetch末尾，高半字在当前fetch首槽。首槽不是当前
窗口的新指令起始，它完成的是先前指令，不能因为恰好处于当前块0末尾就声称它又跨到
块1。若该首槽由当前块0提供，高半字完成后的完整指令应使用块0的FTQ身份。

真实ICache为每个半字按`low2 != 11`产生maybeRvcMap；上半字的数据并不受opcode低2位
规则约束，因此该位可为0或1。不能只产生“真实起始”压缩格点来替代原始半字map。

### 实际消费者与有效域

- `Helpers.compact` 用独立的validOH选择有效槽，无效槽metadata不进入后级。
- `Ifu.scala` 重建carry时，把PC、data及endOffset覆盖（endOffset=0），因此leaf的
  carry首槽endOffset不作架构原值约束；**isCrossBlockInstr并未被覆盖**。
- `Ifu.scala` 的IBuffer FTQ指针、last标记与重定向训练身份用
  `blockSel || isCrossBlockInstr` 选择当前fetch块。错误的carry cross会真实影响身份，
  不是可忽略的无效数据。

因此比较器只对无效槽metadata和carry首槽endOffset作合同限定，valid/endMask/首尾半
指令标记总比较；包括carry cross在内的其他有效metadata仍必须受检。掩码来自独立
参考格点，不能用DUT的valid把错误隐藏。

## 最小成对复现

共同前提：`carry=1`、块0大小1、块1有效、块0fall-through、taken_offset=0。原始高
半字为0x10时maybeRvcMap[0]=1，DUT cross[0]=0；高半字0x13时该位为0，DUT cross[0]=1。
正确答案两者均为0：首槽不是新起始。

原顶层端口历史（不手填内部寄存器，但**不是生产可达证明**）如下：

1. 从PC0x103c取一条RVI，预测taken错误地截在其低半字，触发正常invalidTaken恢复。
   此次两个请求各只有一槽（0x103c低半、0x103e投机高半），只满足最大size上界，
   不满足non-taken完整fall-through长度。
2. 检查首拍未入队、redirect目标为0x103e；等待重定向完成。
3. 从0x103e续取高半字，当前块0只有此一槽（FTQ `(0,32)`），块1从0x1040开始
   （FTQ `(0,33)`），数据与原始map逐半字一致。
   块1由一条C指令加预测taken的合法条件分支组成，size=3；不把对齐开始的fall-through
   块伪造为任意短块，但块0仍是任意短fall-through。早期及此版诊断都不能单独证明
   生产可达性；原正常/失败功能例继续以端口压力保留，而不是重标其历史判定。

| 指令 | 高半字 | 合法raw map首位 | 完整字/PC/endOffset | carry FTQ |
|---|---:|---:|---|---|
| `addi x5,x0,1` | 0x10 | 1 | 正确 | `(0,32)`，端口域正常对照PASS |
| `addi x5,x6,1` | 0x13 | 0 | 同样正确 | **错误`(0,33)`**，应为`(0,32)` |

## 根因与旧漏检

InstrBoundary的crossBlockFallThrough没有检查boundary/start，只检查当前槽是块0
末尾及下一槽属于块1，随后使用`!maybeRvc(i)`。carry高半字low2=11时恰好满足，产生
错误cross。旧模型也用`!is_rvc`而没有start条件，在carry+size1时与RTL同错。

原600随机窗口的第137/254/406/477/529项已包含该组合，原PASS是假阴性；现批次仍
完整驱动并检查600项，汇总五项相同偏差后明确FAIL，不在首个反例就放弃剩余样本。
另有独立leaf定向、实际native顶层端口恢复反例，正常高半字对照分别保留；不据这些
端口输入宣称已证明完整FTQ生产可达。

## 验证代码与关闭条件

- `model/boundary.py::predict` 从指令格点要求cross属于真实起始，不从RTL读出期望。
- `tests/instr_boundary/test_instr_boundary.py`：原600样本、raw map和carry成对对照。
- `tests/ifu/test_ifu_fetch.py::test_recovered_half_instruction_keeps_its_completing_ftq_block`：
  正常历史与FTQ错误归属复现。
- `tests/framework/test_boundary_agent.py`：保留旧错误模型的区分性控制；有效载荷不能被
  无效槽/carry endOffset限定一并豁免。

建议只让本窗口真正的起始指令产生cross-block标记，并复核后级carry归属。修复设计后，
leaf、原600样本及顶层反例必须转PASS，正常对照不能回归；R-14经真实回归再关闭。
构建冒烟、manifest完整性、功能判定与覆盖闭环分别报告。
