"""Complete branch versions, not independent target/type signal assignments."""
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Entry
from suites.frontend.bpu.testbenches.mbtb.model.semantic import Target
from suites.frontend.bpu.testbenches.mbtb.model.semantic import coordinate
from suites.frontend.bpu.testbenches.mbtb.model.semantic import tag
from suites.frontend.bpu.testbenches.bpu.model.main_service import PCS
from suites.frontend.bpu.testbenches.bpu.model.main_service import PEER_POSITION
from suites.frontend.bpu.testbenches.bpu.model.main_service import entry_payload

PC=PCS[0]
POSITION=PEER_POSITION
# Ordinary target, next-region target, then previous-region clean reactivation.
# These are three versions of ONE indirect branch, not physical coordinates.
TARGETS=(PC+0x400,PC+(1<<20)+0x600,PC-(1<<20)+0x900)


def effect(target):
    return entry_payload(coordinate(PC)[2],Entry(tag(PC),POSITION,3,0,Target.encode(PC,target)))


def direction():
    return dict(row=coordinate(PC)[2],mask=4,values={'2':2})
