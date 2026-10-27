# TlbStorageWrapper 功能点

> 本文为既有功能点清单，不代表 sampled bins 或旧 PASS 已证明所有语义。
> 当前 checker/归因限制与误报修正见 `reports/verification-soundness-20261025.md`。


`TlbStorageWrapper` 是 L1 TLB 的存储封装：内部保留真实 `TLBFA` 48-way 叶子，负责
把对外读请求/回填/失效透传到叶子，并用 tree-PLRU 选择回填 way。它不是新的条目语义
模型；条目命中、PPN、权限和 sfence 语义仍由真实 `TLBFA` 执行。

## 1. 复位与初始状态

| ID | 功能点 | 关键行为 |
|---|---|---|
| WRAP-RESET-01 | 复位使真实 TLBFA 的 48 个 way 全部无效，并把 PLRU 状态归零 | 复位后任何查找都 miss；下一次回填从 PLRU 初始状态选择 way |
| WRAP-RESET-02 | 复位可发生在已有有效条目时；不保留旧翻译或旧替换历史 | 旧 VPN miss，后续回填从 way 0 序列重新开始 |

## 2. 替换

| ID | 功能点 | 关键行为 |
|---|---|---|
| WRAP-REPLACE-01 | 回填 victim 由纯 tree-PLRU 状态选择，不按 way 编号顺序填充 | 初始状态 victim 序列为 0、32、16、40、…；连续回填会重复覆盖部分 way |
| WRAP-REPLACE-02 | 读命中更新 PLRU；下一次回填选择更新后的 victim | 命中一个有效 way 后，victim 序列与未命中时不同 |
| WRAP-REPLACE-03 | 回填只覆盖一个 way；victim 的旧翻译消失，新翻译出现 | 其余有效翻译保持不变；不存在一次回填写多个 way |
| WRAP-REPLACE-04 | 无需“先填无效 way”的特权；PLRU 可以在仍有 invalid way 时重复选择已有 way | 前 60 次回填只覆盖 46 个不同 way，way 15/31 仍需后续回填才被选中 |
| WRAP-REPLACE-05 | PLRU 状态由真实 TLBFA 的 touch_ways 驱动，包括命中 touch 和回填 touch | wrapper 不另造 way 统计 |

## 3. 回填与查找

| ID | 功能点 | 关键行为 |
|---|---|---|
| WRAP-REFILL-01 | 新回填的翻译在下一拍可见 | 回填后紧接的查找命中并返回正确 PPN/权限 |
| WRAP-REFILL-02 | 回填与查找同拍时，新 way 不参与当拍命中 | 当拍查找 miss，下一拍命中 |
| WRAP-REFILL-03 | 回填 way 的旧内容由新 PTW 响应完整替换 | 旧 tag/PPN/权限不再可见 |
| WRAP-LOOKUP-01 | 读请求与命中结果原样透传真实 TLBFA | noS2/onlyStage1/onlyStage2/allStage 四类上下文都可命中 |
| WRAP-LOOKUP-02 | 未命中不产生有效翻译，也不更新 PLRU | 后续回填的 victim 序列没有因 miss 改变 |
| WRAP-LOOKUP-03 | 响应仍保持一拍延迟；撤销请求后响应有效拍结束 | 与叶子相同的流水节拍 |

## 4. 失效

| ID | 功能点 | 关键行为 |
|---|---|---|
| WRAP-FENCE-01 | sfence/hfence 原样透传真实 TLBFA | 普通全地址、地址指定、hfence.vvma/gvma 的目标清除和非目标保留与叶子一致 |
| WRAP-FENCE-02 | 失效不重置 PLRU 状态 | 失效后的下一次回填仍沿当前替换历史选择 victim |
| WRAP-FENCE-03 | 对无匹配条目的失效仍走完逐 way 条件求值，不改变有效翻译 | 不会误清无关 way |

## 5. 组合边界

| ID | 功能点 | 关键行为 |
|---|---|---|
| WRAP-COMBO-01 | wrapper 内部必须是真实 TLBFA，不用 Python 叶子替代 | 对读/回填/失效的响应与叶子模型逐项一致 |
| WRAP-COMBO-02 | wrapper 自身的 RTL 只有透传和 PLRU 两部分 | 不从子块结果推导 wrapper 的替换行为；替换序列单独验证 |

## 6. 覆盖与证据

功能覆盖 5 组（replace/lookup/fence/reset/timing）全部 100%；DUT 行 3431/3431、
toggle 18798/18798、branch 1019/1022。未取到的 3 个分支是时间零 initial 块和
TLBFA 的 allStage fake-PTE 死分支，逐项见 `manifest/known-issues.json` 与
`docs/reports/wrapper-20261024.md`。
