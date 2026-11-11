# lsq_wrapper

<!-- ucv:module:start -->

由 `ucv docs --write` 更新；基线与执行状态通过 `ucv info/run/report` 查询。

| DUT 键 | RTL top | Python 导出名 |
|---|---|---|
| `lsq_wrapper` | `LsqWrapper` | `LsqWrapperDut` |

## 工作入口

- 设计规格：[docs/spec/design/contracts/lsq-wrapper.md](../../docs/spec/design/contracts/lsq-wrapper.md) · [docs/spec/design/README.md](../../docs/spec/design/README.md)
- 验证合同与计划：[docs/spec/verification/README.md](../../docs/spec/verification/README.md) · [docs/spec/verification/plan.md](../../docs/spec/verification/plan.md) · [testbenches/lsq_wrapper/coverage/function_points.py](coverage/function_points.py)
- 公开环境：[testbenches/lsq_wrapper/env/__init__.py](env/__init__.py)
- 用例与自检：[testbenches/lsq_wrapper/tests](tests) · [testbenches/lsq_wrapper/tests/test_bus.py](tests/test_bus.py) · [testbenches/lsq_wrapper/tests/test_bus_ownership.py](tests/test_bus_ownership.py) · [testbenches/lsq_wrapper/tests/test_cancel_capacity.py](tests/test_cancel_capacity.py) · [testbenches/lsq_wrapper/tests/test_cause_lifetimes.py](tests/test_cause_lifetimes.py) · [testbenches/lsq_wrapper/tests/test_checkpoint_pool.py](tests/test_checkpoint_pool.py) · [testbenches/lsq_wrapper/tests/test_forward_memory.py](tests/test_forward_memory.py) · [testbenches/lsq_wrapper/tests/test_initial.py](tests/test_initial.py) · [testbenches/lsq_wrapper/tests/test_interaction_windows.py](tests/test_interaction_windows.py) · [testbenches/lsq_wrapper/tests/test_joint_capacity.py](tests/test_joint_capacity.py) · [testbenches/lsq_wrapper/tests/test_ldu_joint_serial.py](tests/test_ldu_joint_serial.py) · [testbenches/lsq_wrapper/tests/test_ldu_mixed.py](tests/test_ldu_mixed.py) · [testbenches/lsq_wrapper/tests/test_ldu_rar_capacity.py](tests/test_ldu_rar_capacity.py) · [testbenches/lsq_wrapper/tests/test_ldu_rar_routing.py](tests/test_ldu_rar_routing.py) · [testbenches/lsq_wrapper/tests/test_ldu_s3_mixed.py](tests/test_ldu_s3_mixed.py) · [testbenches/lsq_wrapper/tests/test_ldu_s3_rar.py](tests/test_ldu_s3_rar.py) · [testbenches/lsq_wrapper/tests/test_ldu_s4_epochs.py](tests/test_ldu_s4_epochs.py) · [testbenches/lsq_wrapper/tests/test_ldu_s4_errors.py](tests/test_ldu_s4_errors.py) · [testbenches/lsq_wrapper/tests/test_ldu_s4_mixed.py](tests/test_ldu_s4_mixed.py) · [testbenches/lsq_wrapper/tests/test_ldu_s4_plain.py](tests/test_ldu_s4_plain.py) · [testbenches/lsq_wrapper/tests/test_ldu_s4_precise.py](tests/test_ldu_s4_precise.py) · [testbenches/lsq_wrapper/tests/test_ldu_s4_precise_epochs.py](tests/test_ldu_s4_precise_epochs.py) · [testbenches/lsq_wrapper/tests/test_mixed_bus.py](tests/test_mixed_bus.py) · [testbenches/lsq_wrapper/tests/test_normal_cbo_mixed.py](tests/test_normal_cbo_mixed.py) · [testbenches/lsq_wrapper/tests/test_normal_cbo_paths.py](tests/test_normal_cbo_paths.py) · [testbenches/lsq_wrapper/tests/test_normal_replay_metadata.py](tests/test_normal_replay_metadata.py) · [testbenches/lsq_wrapper/tests/test_nuke_memory.py](tests/test_nuke_memory.py) · [testbenches/lsq_wrapper/tests/test_nuke_population.py](tests/test_nuke_population.py) · [testbenches/lsq_wrapper/tests/test_pending_reset.py](tests/test_pending_reset.py) · [testbenches/lsq_wrapper/tests/test_prefix_byte_windows.py](tests/test_prefix_byte_windows.py) · [testbenches/lsq_wrapper/tests/test_raw_checkpoint_owners.py](tests/test_raw_checkpoint_owners.py) · [testbenches/lsq_wrapper/tests/test_release_windows.py](tests/test_release_windows.py) · [testbenches/lsq_wrapper/tests/test_remaining_paths.py](tests/test_remaining_paths.py) · [testbenches/lsq_wrapper/tests/test_replay_gaps.py](tests/test_replay_gaps.py) · [testbenches/lsq_wrapper/tests/test_replay_population.py](tests/test_replay_population.py) · [testbenches/lsq_wrapper/tests/test_response_payload_pool.py](tests/test_response_payload_pool.py) · [testbenches/lsq_wrapper/tests/test_retire_known_width.py](tests/test_retire_known_width.py) · [testbenches/lsq_wrapper/tests/test_scalar_reservation_pool.py](tests/test_scalar_reservation_pool.py) · [testbenches/lsq_wrapper/tests/test_seeded_mixed.py](tests/test_seeded_mixed.py) · [testbenches/lsq_wrapper/tests/test_serialized_cbo.py](tests/test_serialized_cbo.py) · [testbenches/lsq_wrapper/tests/test_serialized_mixed.py](tests/test_serialized_mixed.py) · [testbenches/lsq_wrapper/tests/test_shared_recovery.py](tests/test_shared_recovery.py) · [testbenches/lsq_wrapper/tests/test_sid_data.py](tests/test_sid_data.py) · [testbenches/lsq_wrapper/tests/test_special_memory.py](tests/test_special_memory.py) · [testbenches/lsq_wrapper/tests/test_sq_age_endpoint.py](tests/test_sq_age_endpoint.py) · [testbenches/lsq_wrapper/tests/test_sq_smf_endpoint.py](tests/test_sq_smf_endpoint.py) · [testbenches/lsq_wrapper/tests/test_store_population.py](tests/test_store_population.py) · [testbenches/lsq_wrapper/tests/test_store_span.py](tests/test_store_span.py) · [testbenches/lsq_wrapper/tests/test_store_strict_lifetimes.py](tests/test_store_strict_lifetimes.py) · [testbenches/lsq_wrapper/tests/test_uncache_population.py](tests/test_uncache_population.py) · [testbenches/lsq_wrapper/tests/test_uncache_recovery.py](tests/test_uncache_recovery.py) · [testbenches/lsq_wrapper/tests/test_uncache_store_fault.py](tests/test_uncache_store_fault.py) · [testbenches/lsq_wrapper/tests/test_uq_page_pairs.py](tests/test_uq_page_pairs.py)
- 实现职责：[testbenches/lsq_wrapper/transactions.py](transactions.py) · [testbenches/lsq_wrapper/model.py](model.py) · [testbenches/lsq_wrapper/checker](checker) · [testbenches/lsq_wrapper/coverage](coverage)
- 问题：[docs/bugs/README.md](../../docs/bugs/README.md)

## 从仓库根操作

```sh
./scripts/ucv info lsq --dut lsq_wrapper
./scripts/ucv run lsq --dut lsq_wrapper --collect-only --workers 1
./scripts/ucv run lsq --dut lsq_wrapper --workers 1
./scripts/ucv report
```

源码、RTL 获取和构建命令见 `ucv info`；运行前完成对应构建。

<!-- ucv:module:end -->
