"""Real valid untracked decisions interleave four independently learned owners."""
from bpuverify.bpu.checker.tage.interleaved import InterleavedLearningChecker
from bpuverify.bpu.env.tage_interleaved import interleaved_program
from bpuverify.bpu.model.tage.interleaved import RESOLVED,UNTRACKED,discovery_outcomes


async def check_interleaved_learning(agent,coverage):
    checker = InterleavedLearningChecker(coverage)
    async with interleaved_program(agent,checker) as program:
        await program.establish_owners()
        before = await program.oppose_bases()
        checker.arm_learning(before)
        await program.resolve(before,tuple((position,False,False) for position in RESOLVED))
        learned = await program.query()
        checker.consume_learning(learned,await program.env.corrections(learned))
        for position in UNTRACKED:
            source = await program.query()
            checker.arm_discovery(source,position)
            await program.resolve(source,discovery_outcomes(position))
            discovered = await program.query((position,))
            checker.consume_discovery(discovered,position,await program.env.corrections(discovered))
        checker.finish()
