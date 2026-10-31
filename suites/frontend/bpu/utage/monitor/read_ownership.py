"""Bounded passive snapshots and actual public feedback receipts."""
from suites.frontend.bpu.utage.monitor.source_ownership import SourceOwnershipMonitor
from suites.frontend.bpu.utage.model.semantic import indices, tag


class ReadOwnershipMonitor(SourceOwnershipMonitor):
    def __init__(self, agent, checks):
        super().__init__(agent)
        self.checks = checks

    def observe(self, observation):
        super().observe(observation)
        self.checks.observe(self.records[-1])

    def diagnostic(self):
        """Render only on failure: bounded identities, not full cycle replay."""
        context = []
        for row in tuple(self.records)[-8:]:
            inputs = row.inputs
            meta = row.prediction.meta
            selected = tuple(i for i, hit in enumerate(row.shadow['hits']) if hit)
            cells = tuple(dict(slot=i, **cell) for i, cell in enumerate(row.shadow['cells'])
                          if i in selected or i == 0)
            context.append(dict(tick=row.tick,
                read=None if inputs is None else indices(inputs.read_pc, inputs.read_context),
                match_tag=None if inputs is None else tag(inputs.pc, inputs.context, 0),
                feedback_valid=row.shadow['public']['valid'], selected=selected, cells=cells,
                shadow_response=row.shadow['response'], return_indices=tuple(meta['readIndex']),
                return_source=meta['abtbResult'][0], hit=row.prediction.hit, taken=row.prediction.taken))
        return tuple(context)
