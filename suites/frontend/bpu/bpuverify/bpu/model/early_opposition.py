"""Source identities for an opposed-direction loop, never DUT observations."""
from dataclasses import dataclass

from bpuverify.bpu.model.main_sources import source_entries
from bpuverify.bpu.model.path_history import path_contribution
from bpuverify.utage.model.semantic import Entry,HISTORIES,Context,INDEX_FOLDS,TAG_FOLDS,ALT_FOLDS

PC=0x40000000
# An odd later CFI contributes bit 4 to the path hash. The configured
# five-bit short history can therefore distinguish it from conditional 2.
CONDITIONAL,FALLBACK=2,5


@dataclass(frozen=True,slots=True)
class Provider:
    table: int
    index: int
    tag: int
    position: int
    counter: int
    base: bool

    @property
    def key(self):return self.table,self.index


def provider(sources,token):
    saved=sources.short_snapshot(token);frame=saved.prediction.frame
    values=saved.prediction.values()
    if frame is None:return None
    for way in range(4):
        if (values.get(f'{way}.valid') and values.get(f'{way}.hit')
                and values.get(f'{way}.position')==CONDITIONAL):
            table=values[f'{way}.provider'];entry=frame.read.entries[table]
            return Provider(table,frame.read.indices[table],entry.tag,entry.position,
                entry.counter,bool(values[f'{way}.base']))
    return None


def ahead_owner(sources,token):
    saved=sources.snapshot(token);frame=saved.frame
    if not saved.enabled or frame is None or not frame.valid:return None
    for way,(entry,hit,counter) in enumerate(zip(frame.read.entries,frame.hits,frame.counters,strict=True)):
        if hit and entry.position==CONDITIONAL and entry.kind==1:
            return (frame.read.bank,frame.read.row,way),counter
    return None


def resident(sources,key):
    table,index=key;version=sources.short.updates[table].newest(index)
    return sources.short.memory[table].get(index,Entry()) if version is None else version.entry


def main_counter(token):
    return next(entry.counter for row in source_entries(token.lookup) for entry in row
        if entry.hit and entry.position==CONDITIONAL and entry.kind==1)


def is_opposed(sources,token,*,taken=False):
    source=provider(sources,token)
    return source is not None and (source.counter>=4)==taken and source.base!=taken


def stable_negative(sources,token):
    value=provider(sources,token)
    if value is None or value.counter!=0 or value.base:return False
    frame=sources.short_snapshot(token).prediction.frame
    expected=Context.from_recent(loop_history(token.pc,FALLBACK))
    # Repeated fallback edges have a well-defined short-history fixed point.
    # An older in-flight read can already say counter0 while its tag owner has
    # since changed. Do not protect that transient alias as the steady key.
    return (steady_history(token,FALLBACK)
        and all(frame.context.folds[index]==expected.folds[index] for index in (*INDEX_FOLDS,*TAG_FOLDS,*ALT_FOLDS))
        and resident(sources,value.key)==Entry(True,value.tag,value.position,value.counter))


def loop_history(pc,position):
    width=max(HISTORIES);edge=path_contribution((pc//16)*16+position,pc);word=0
    for shift in range(0,width,2):word^=edge<<shift
    return word% (1<<width)


def steady_history(token,position):return token.history.history% (1<<max(HISTORIES))==loop_history(token.pc,position)
