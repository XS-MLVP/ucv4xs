"""Declared normal traffic that turns over DefaultConfig retained entry keys.

No SRAM/way observation selects these inputs. Distinct rows in the same bank
start with identical replacement age; each allocates physical way three.
SPDX-License-Identifier: MPL-2.0
"""
from suites.frontend.bpu.models.configuration import MAIN_RETAINED
from suites.frontend.bpu.mbtb.transaction.types import MbtbBatchTraining, MbtbBranchFeedback


async def preceding_displacers(agent, neighbor_pc, position, target, kind):
    """The caller's neighbor is the final one of four new retained keys."""
    for ordinal in range(1, MAIN_RETAINED):
        pc = neighbor_pc + 128 * ordinal
        source = await agent.predict(pc)
        if any(entry.valid for entry in source.entries):
            raise AssertionError('declared retained-key pressure must use a new row')
        await agent.train_batch(MbtbBatchTraining(pc, source.meta_entries, (
            MbtbBranchFeedback(target + 0x200 * ordinal, 1, position, kind, mispredict=1),)))
