from .types import FtqPtr, Inputs, Outputs, Query, Redirect, RobPtr, Rollback, SqPtr, Store, Training


class Ports:
    def __init__(self, dut, spec):
        self.dut, self.spec = dut, spec
        query_names = ("req_valid", "req_bits_robIdx_flag", "req_bits_robIdx_value", "req_bits_robIdx_isFormer",
                       "req_bits_sqIdx_first_flag", "req_bits_sqIdx_second_flag", "req_bits_sqIdx_value", "req_bits_paddr",
                       "req_bits_mask", "req_bits_dataValid", "req_bits_isRVC", "req_bits_ftqPtr_flag", "req_bits_ftqPtr_value",
                       "req_bits_ftqOffset", "req_bits_debugInfo_runahead_checkpoint_id", "revokeLastCycle", "revokeLastLastCycle")
        self.query = tuple(tuple(getattr(dut, f"io_query_{lane}_{key}") for key in query_names) for lane in range(spec["query_width"]))
        self.ready = tuple(getattr(dut, f"io_query_{lane}_req_ready") for lane in range(spec["query_width"]))
        store_names = ("valid", "bits_uop_robIdx_flag", "bits_uop_robIdx_value", "bits_uop_robIdx_isFormer", "bits_paddr",
                       "bits_mask", "bits_wlineflag", "bits_tlbMiss", "bits_uop_ftqPtr_flag", "bits_uop_ftqPtr_value", "bits_uop_ftqOffset", "bits_uop_isRVC")
        self.stores = tuple(tuple(getattr(dut, f"io_storeIn_{lane}_{key}") for key in store_names) for lane in range(spec["store_width"]))
        self.redirect = tuple(getattr(dut, "io_redirect_" + key) for key in
                              ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer", "bits_level"))
        self.head = tuple(getattr(dut, "io_stAddrReadySqPtr_" + key) for key in ("first_flag", "second_flag", "value"))
        rollback_names = ("valid", "bits_robIdx_flag", "bits_robIdx_value", "bits_robIdx_isFormer", "bits_ftqIdx_flag", "bits_ftqIdx_value",
                          "bits_ftqOffset", "bits_isRVC", "bits_debug_runahead_checkpoint_id", "bits_stFtqIdx_flag", "bits_stFtqIdx_value", "bits_stFtqOffset", "bits_stIsRVC")
        self.rollbacks = tuple(tuple(getattr(dut, f"io_rollback_{lane}_{key}") for key in rollback_names) for lane in range(spec["store_width"]))
        train_names = ("valid", "bits_ftqIdx_value", "bits_ftqOffset", "bits_isRVC", "bits_stFtqIdx_value", "bits_stFtqOffset", "bits_stIsRVC")
        self.train = tuple(getattr(dut, "io_mdpTrain_" + key) for key in train_names)

    @property
    def driven(self):
        return (self.dut.reset, *self.head, *self.redirect, *(s for lane in self.query for s in lane), *(s for lane in self.stores for s in lane))

    def sample(self, event):
        queries, one, two = [], [], []
        for lane in self.query:
            valid, rf, rv, former, first, second, sq, address, mask, data, rvc, ff, fv, fo, checkpoint, r1, r2 = (s.U() for s in lane)
            queries.append(Query(bool(valid), RobPtr(bool(rf), rv, bool(former)), SqPtr(bool(first), bool(second), sq), address, mask,
                                 bool(data), bool(rvc), FtqPtr(bool(ff), fv), fo, checkpoint))
            one.append(bool(r1))
            two.append(bool(r2))
        stores = []
        for lane in self.stores:
            valid, flag, value, former, address, mask, line, miss, ff, fv, fo, rvc = (s.U() for s in lane)
            stores.append(Store(bool(valid), RobPtr(bool(flag), value, bool(former)), address, mask, bool(line), bool(miss), bool(ff), fv, fo, bool(rvc)))
        valid, flag, value, former, level = (s.U() for s in self.redirect)
        first, second, value_sq = (s.U() for s in self.head)
        inp = Inputs(tuple(queries), tuple(stores), tuple(one), tuple(two), SqPtr(bool(first), bool(second), value_sq),
                     Redirect(bool(valid), RobPtr(bool(flag), value, bool(former)), bool(level)), bool(self.dut.reset.U()))
        rollbacks = []
        for lane in self.rollbacks:
            valid, flag, value, former, ff, fv, fo, rvc, checkpoint, sff, sfv, sfo, srvc = (s.U() for s in lane)
            rollbacks.append(Rollback(bool(valid), RobPtr(bool(flag), value, bool(former)), FtqPtr(bool(ff), fv), fo, bool(rvc), checkpoint, bool(sff), sfv, sfo, bool(srvc)))
        valid, fv, fo, rvc, sfv, sfo, srvc = (s.U() for s in self.train)
        out = Outputs(tuple(bool(s.U()) for s in self.ready), bool(self.dut.io_lqFull.U()), tuple(rollbacks),
                      Training(bool(valid), fv, fo, bool(rvc), sfv, sfo, bool(srvc)), self.dut.io_perf_0_value.U(), self.dut.io_perf_1_value.U())
        return inp, out
