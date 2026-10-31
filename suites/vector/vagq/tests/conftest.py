pytest_plugins = ("ucv.pytest_selftest",)

from suites.vector.vagq.fixtures import (
    addrgen_dut, arbiter_dut, manager_dut, manager_env, maskgen_dut, native_registration,
    ordered_env, entrytable_env, pipeline3_env, pipeline_env, split_env, storedata_env,
    merge_env, vagq_env,
)
