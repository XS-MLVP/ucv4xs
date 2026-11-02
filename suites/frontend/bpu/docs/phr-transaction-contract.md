# BPU 内部 PHR 的当前事务观察合同

适用基线：`public-893e1580b`、完整香山 DefaultConfig、真实 `Bpu` 实例闭包。本文描述当前
迁移实现，不据历史 MinimalConfig 的 PASS/覆盖数字认证当前环境；运行证据另行登记。

## 物理值、逻辑身份和观察限制

| 内容 | 当前真实合同 | 实现 |
|---|---|---|
| PHR 环 | 532 个物理 bit，每次 taken 右移读指针两格 | `models/configuration.py`，独立 `bpu/model/phr/model.py` |
| 指针 | 10-bit 容器中的合法值 `0..531`；实际端口/trace没有flag | ports将真实`phrPtr_value`映射为逻辑`phrPtr.value`，不绑定/补造flag |
| 低位快照 | 13位，taken哈希总宽15位 | 模型从复位维护物理cell、pending旁路和恢复低位 |
| fold | 33种折叠 × 四组寄存快照 | 独立多项式折叠，不读实际寄存器修正期望 |
| 公开 BPU prediction | startPc/taken/endPosition/S2、S3 override | target明确为`None`；不把内部target说成公开输出 |
| 公开 metadata | resolve/redirect及RAS提交字段，PHR只保留value/low | perf echo明确为`None`，不从golden或内部诊断补回 |
| 环境 UID/epoch | 在真实PHR S1输入接受事件建立，逐fire/flush推进 | `bpu/checker/phr/association.py`；不是硬件tag或已DCE的flag |

公开源码依据：`history/phr/Phr.scala::getPhr/getRedirectPhr`只用`ptr.value`定位物理环；
`Helpers.scala::pathHash/getUpdatePtrs`定义哈希与两格移动；`Bundles.scala::PhrPtr`虽然有
Scala层flag，但当前完整生成结果没有消费它。旧纯模型的完整flag算术测试仍保留；实际
checker显式选择`BpuPhrReference(pointer_flags=False)`，不是按测试路径暗中切模型。

## 独立性边界

这是**给定真实PHR输入流后的历史状态/恢复检查**，不是完整BPU选择器oracle。输入中的
S1、S2、S3 target来自BPU父模块到PHR的真实边界，用来计算PHR应有的结果；这些值本身
不能因此算作BPU预测target的独立正确性证据。完整BPU的选择正确性仍须由自主预测模型
及真正消费者检查，不借用本合同绕过被裁公开字段。

同一RisingEdge同步冻结父/子边界、全部物理cell、pending、fold寄存器、公开预测/metadata。
先和独立模型比较物理状态及PHR快照，再登记接受身份。关联器保存已检查S1输入的UID与
快照，按S2/S3真实fire和flush优先级推进；不按返回PC、payload或“当前地址”反推身份。
同PC、同metadata的两笔输入也必须保留两个不同UID。

## 完成与取消

- offered、同拍flush抑制、生效accepted、S3公开完成和reset/override取消分开计账。
- 退出前由场景显式停止新预测接受并drain；不自动reset、发redirect或补响应清债。
- 正常收尾要求两级lease与pending UID为空，并满足accepted=emitted+cancelled及
  offered=accepted+suppressed。已比较的自发输出不要求测试逐条消费，但不能漏比较。
- monitor关闭只释放订阅，不算完成。吞掉比较错误后，粘滞checker错误仍阻止正常收尾。
- reset取消保留具体UID、epoch、tick和原因；新输入不复用旧UID。
- reset调用到真实复位沿之间，较老输入可以已经正常完成。分别保留完成和取消的UID
  终态收据，不能把调用前一张pending快照中的全部身份重标为取消；终态集合必须无重叠
  且完整覆盖所有生效输入。

## 当前场景与控制

`phr_recovery.py`按532格构造两个完整的偶数指针环，每步各执行NT/T恢复，分别走flowing
与backpressured节奏。覆盖中的`lap`是输入程序的圈次，不是硬件flag；奇数指针没有从
这组两格移动程序得到信用。原旧52格/flag覆盖不能改名当作当前完整覆盖。

`tests/framework/test_phr_value_only_contract.py`检查完整物理指针域、真实逻辑映射、拒绝
额外flag/错误位宽/方向、同payload不同UID、错误S3快照、reset取消及未收尾。它们是
Python模型/采样检查链自检，不是RTL mutation或硬件功能PASS。真实回归继续使用原
`tests/bpu/testcase/test_phr.py`及handoff用例，保留实际失败和仍未迁移的其他BPU义务。
