# 覆盖摘要

基线 `public-a0c2a26cb` / DefaultConfig；seed 1 与 seed 2 的完整集合均为
83 PASS。覆盖数字来自 `results/ibuffer-seed1-final5/coverage.json` 与
`results/ibuffer-seed2-final5/coverage.json`（Picker `*_top.sv` 已排除）。

## 逐 DUT

| DUT | line | branch | toggle bin | 曾变化位 |
|---|---|---|---|---|
| `vtype_gen` | 163/163 (100%) | 104/106 (98.11%) | 1226/1596 (76.82%) | 613/798 (76.82%) |
| `ibuffer` | 4177/4209 (99.24%) | 666/726 (91.74%) | 18524/20252 (91.47%) | 9304/10126 (91.88%) |

seed 2：`vtype_gen` branch 104/106、toggle 1224/1596；`ibuffer` branch 667/726、
toggle 18522/20252。差异来自随机激励，不是判定变化。

## 逐文件

| DUT / 文件 | line | branch | toggle |
|---|---|---|---|
| `vtype_gen` / `VSetFuncUnit.sv` | 6/6 | 5/6 | 190/506 |
| `vtype_gen` / `VTypeGenDut.v` | 157/157 | 99/100 | 1036/1090 |
| `ibuffer` / `IBufferDut.v` | 4014/4046 | 562/620 | 17333/18656 |
| `ibuffer` / `VTypeGen.sv` | 157/157 | 99/100 | 1020/1090 |
| `ibuffer` / `VSetFuncUnit.sv` | 6/6 | 5/6 | 171/506 |

## 缺口归因

- 未覆盖行：`ibuffer` 32 行，全部是 `DontCare` 的 vtype 字段降级为 0。
- 未覆盖分支：`VSetFuncUnit` 固定输入（2）、初始化 reset-else（2）、
  `exceptionMask` 高位（30）、旁路异常槽 1..7（7）、指针预回绕 lane 0..3（4）、
  无效项 vtype 清零（15）、随机相关异常 mux（1，seed 2 已命中）。
- 未覆盖 toggle：VSetFuncUnit 固定输入、IFU padding lane、`exceptionMask` 高位、
  少量随机深度未双向跳变的 payload/状态位。

全部为结构不可达、合法 IFU 域外、工具 don't-care 或随机深度，不阻塞本层结论。
详见 [覆盖率闭环](coverage-loop.md)。
