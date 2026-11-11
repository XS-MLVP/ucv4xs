"""One algebraic discriminator, not an address or physical-bank sweep."""
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import Program as VersionProgram
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import PC
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import POSITION
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import NEIGHBOR
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import PROFILES
from suites.frontend.bpu.testbenches.utage.model.read_lifetime import RELATIONS

MATCH_PC,MATCH_HISTORY=PC+0x550,0xea
RULES=('normally-learned-distinct-prestate','distinct-read-and-match-contexts',
    'complete-original-feedback','actual-read-effect-relation','original-read-not-rebound',
    'declared-response-version','fresh-new-version-consumers','own-context-stays-cold',
    'all-other-protection-and-neighbor-preserved','immutable-originals')


class Program(VersionProgram):
    def state(self):
        return dict(super().state(),match_pc=MATCH_PC,match_history=MATCH_HISTORY,
            own_context_response=(0,None,None,None),read_and_match_ancestors_are_distinct=True)
