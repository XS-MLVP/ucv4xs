# `StdExeUnit`：store 数据单元

## 1. 职责

`StdExeUnit` 把 store 数据写进 SQ，并把 AMO 的数据送给 `AtomicsUnit`、把普通
store 的完成写回 ROB/RS。标量 STD 与向量 STD 在这里仲裁。

## 2. 语义（除反馈寄存器外全组合）

```
legalIssue      = sqIdx.withInPhysicalQueue(sqDeqPtr)      // [deq, deq+64)
isAMO           = fuType[18]
in.ready        = !vstdIn.valid                           // 向量优先，标量被反压
out.toRob.valid = in.valid && !vstdIn.valid && !isAMO && legalIssue
atomicData      = in.valid && !vstdIn.valid && isAMO
sqData.valid    = out.toRob.valid || vstdIn.valid
sqData.bits     = vstdIn.valid ? vstdIn
                              : {fuOpType, {64'h0, src0}, sqIdx}
feedBack.valid  = RegNext(in.valid)
feedBack.hit    = RegEnable(legalIssue || isAMO, in.valid)
```

**关键点：`out.toRob.valid` 要求 `legalIssue`（SQ 窗口内），不是"非非法"**。
源码写的是 `!(in.valid && s0IllegalIssue)`，与 `in.valid` 相与后等价于
`in.valid && !s0IllegalIssue`，即必须合法。

## 3. 各路径

| 情形 | `toRob` | `atomicData` | `sqData` |
|---|---|---|---|
| 合法标量 store | 1 | 0 | 1（低 64 位 = `src_0`，高 64 位 = 0） |
| 非法标量 store（窗口外） | 0 | 0 | 0 |
| 标量 AMO | 0 | 1 | 0 |
| 向量 STD（`vstdIn.valid`） | 0 | 0 | 1（完整 128 位载荷） |

向量 STD 优先：`in.ready=0`，标量输入即使有效也不写回、不发 atomic。

## 4. 无 reset 与反馈寄存器

生成的 DUT **没有 reset 端口**。`feedBack.valid`/`hit` 是 `RegNext`/`RegEnable`，
上电值由 Verilator 随机初始化决定，因此第一个比较周期不比较反馈；`hit` 在
`valid=0` 时保持旧值（`RegEnable`），只在 valid=1 时比较。

## 5. 依据

- `XiangShan/src/main/scala/xiangshan/mem/pipeline/StdExeUnit.scala:44-88`
- `soc-split/rtl/StdExeUnit.sv`（本 DUT）
