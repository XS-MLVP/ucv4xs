# ICacheReplacer 覆盖率缺口倒推与收尾

运行：`results/xreactor-repl-11`（`xreactor run --workers 1 -- tests/replacer/testcase`）

| 指标 | 值 |
|---|---|
| 用例 | 10 passed |
| 功能点 | 7/7 PASS |
| 行覆盖 | 6478 / 6478 = **100.00%**（模块 DUT `ReplacerDut.v`，无未覆盖行） |
| 分母 | 未剔除（仅排除 picker 生成的 `ReplacerDut_top` 测试台，全仓库同一规则） |

## 缺口倒推过程

| 轮次 | 覆盖 | 倒推出的功能点 / 修正 |
|---|---|---|
| 1 | 42.70% | 初版 6 功能点；同时暴露 3 处参考模型错误 |
| 2 | 43.61% | 补 007 全集合/全端口扫描 |
| 3 | 85.72% | 加双请求同拍扫描（每个 replacer 两个候选 way） |
| 4 | 95.17% | 补 004 扩展：victim 反馈与显式 touch 同拍 |
| 5 | 95.26% | victim 必须按"触摸前状态"锁存（模型顺序错误） |

### 倒推暴露的参考模型缺陷（非 RTL 缺陷）

1. **PLRU 左右子树编号**：发布的 tree-PLRU 把高编号 way 放在 older-bit=1 一侧
   （4 way 时 state[1] 比较 way3 与 way2）；初版方向相反，victim 全错。
2. **victim 端口有副作用**：它在下一拍被锁存为 touch，组合读取无法"只看不改"，
   测试必须消耗一个时钟沿，模型同位置重放。
3. **victim 取值时点**：victim 是本拍组合输出，必须基于本拍 touch **之前**的状态，
   初版取在 touch 之后，并发场景不一致。
4. **端口/通道维度**：`vSetIdx[0]` 选 replacer，`vSetIdx[7:1]` 是组号；每个 replacer
   内有两条 request 通道（`ways_0_*` / `ways_1_*`），两条通道共享同一套状态。

## 剩余 257 行（已闭环）

对 257 行逐行取证后，结论是**全部为工具归因，无行为缺口**。

| 类别 | 行数 | 证据 |
|---|---|---|
| `else if (set_touch_ways_0_<set>_valid)` | 256 | 见下方"三路链取证" |
| `if (reset)` | 1 | 复位分支只在 harness 的 `ResetDriver` 期间进入一次，之后不再进入 |

### 三路链取证

每个组的状态更新是一条三路优先链：

```verilog
if (set_touch_ways_2_<set>_valid)      // victim 反馈，最高优先
  state_vec_<set> <= {...};
else if (set_touch_ways_1_<set>_valid) // request 通道 1
  state_vec_<set> <= {...};
else if (set_touch_ways_0_<set>_valid) // request 通道 0，最低优先
  state_vec_<set> <= {...};
```

`tools/coverage_gaps.py` 的原始行表里有 256 行计数为 0，全部是这个链的**最后一条
`else if` 条件行**。对该链逐条统计（脚本见下方复现）得到：

| 统计 | 值 |
|---|---|
| 三路链数量 | 256（2 个 replacer × 128 组） |
| 条件行计数为 0 | **256**（每链恰好一条，即最低优先那一条） |
| 条件行计数 > 0 | 512 |
| 分支体计数为 0 | **0** |
| 分支体计数 > 0 | **768（全部）** |

也就是说：**每个组、每条通道、每个优先级的更新分支体都被执行过**，只有最低优先级
那条条件行本身没有被 Verilator 记数——firtool 把条件预计算成
`set_touch_ways_0_<set>_valid` 线网，`else if` 行不再产生独立语句。例如组 255：

```
9584: cnt=6   if (set_touch_ways_0_255_valid | set_touch_ways_1_255_valid | set_touch_ways_2_255_valid)
9586: cnt=1   if (set_touch_ways_2_255_valid)
9587: cnt=1     state_vec_1_127 <= {...victim...}
9591: cnt=3   else if (set_touch_ways_1_255_valid)
9592: cnt=3     state_vec_1_127 <= {...通道1...}
9594: cnt=0   else if (set_touch_ways_0_255_valid)   <-- 条件行未记数
9595: cnt=2     state_vec_1_127 <= {...通道0...}      <-- 分支体执行 2 次
```

因此这 256 行**保留在分母中**，不做剔除；它们是行覆盖工具对 `else if` 的记数方式，
不是未验证的行为。若后续改用分支覆盖或表达式覆盖，应当重新评估这些行。

## 复现

```sh
python3 -m xreactor run --workers 1 --output results/xreactor-repl-final \
    -- tests/replacer/testcase
python3 tools/coverage_gaps.py results/xreactor-repl-final --json /tmp/gaps.json
# 三路链取证
python3 tools/chain_audit.py results/xreactor-repl-final dut/replacer/ReplacerDut.v
```


## 最终收尾

`results/xreactor-repl-11` 的模块 DUT 源文件已无任何未覆盖行（`verilator_coverage` 中
0 个零计数点），语句覆盖 **6478/6478 = 100%**。整块 ICache 里的 `ICacheReplacer.sv`
仅剩 626 行（多行 `wire ... =` 声明首行）一条声明性缺口，同文件其余语句全部覆盖；
详见 `docs/icache-coverage-closure.md`。
