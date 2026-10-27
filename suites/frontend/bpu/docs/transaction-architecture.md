# Transaction architecture

The direct/async checking semantics and extension points are specified in
[Scoreboard design](scoreboard-design.md). The implementation now lives in
xreactor; this repository supplies BPU-specific bindings, monitors,
request/response dataclasses, and agent facades.

Since 2026-10-10 implementations are organized by DUT and role; see
[repository layout](repository-layout.md) for current source locations.

There is no common `Interface` base class. `PortBinding` and `PulseBinding`
only group bound signals with their clock. XReactor's `SignalDriver` owns the
driven leaves; the project's `ClockedWriteDriver`, `AsyncSingleCycleDriver`, and
`PulseDriver` implement distinct launch policies and accept scalar signals as
well as Bundles. `AsyncSingleCycleDriver` submits without waiting and launches
one request per cycle; `ClockedWriteDriver` writes a persistent level and is not a
handshake protocol. XReactor's protocol-neutral `AsyncDriver` template covers
non-blocking submissions, regardless of input duration. It can allow different
transfers' input stages to overlap via `max_active`.
The rise-write cycle convention stays inside the BPU bindings and drivers.
The BPU `AsyncSingleCycleDriver` is only a `PortBinding` adapter for XReactor's
single-cycle scheduler; it contains no independent submission loop.
MicroBTB uses that same scheduler for fast training: the agent's
`train_contiguous()` queues successive valid cycles and waits internally for
the final DUT acceptance, while tests observe only the transfer handles and
architectural prediction result.
Its resolve input is a separate static `PulseBinding` and a second instance of
the same asynchronous single-cycle driver. `UbtbBatchTraining` carries up to
eight `UbtbBranchFeedback` slots, with FTQ's at-most-one valid misprediction
validated before driving. `train_resolve(..., fast_train=...)` submits both
sources before awaiting either and checks their event ticks coincide; source
arbitration is therefore tested on one beat, not two sequential calls. The
prediction monitor retains RAS action as well as target, position and type.
These transactions preserve the existing MicroBTB byte-address convention;
they do not reuse ITTAGE's halfword-address codec.

ITTAGE full-region replacement uses a small domain-specific expected generator,
`IttageRegionModel`, with heap-order PLRU nodes rather than the RTL's packed
state. Only qualifying non-PC-region allocation writes update it, including
existing-region reuse; prediction reads do not touch replacement state. The
reference chooses the pointer before DUT readback. Old victim entries keep
their offset and decode through the replacement region, while unrelated
residents retain their prediction metadata. Callable comparisons run through
the existing asynchronous Scoreboard and propagate contextual pytest exceptions.
This reference does not claim to inherit a core ReferenceModel base: that base
is not currently supplied by XReactor.

The verification layer follows UVM's responsibility boundaries without
copying its phase and factory machinery into Python.

| UVM concept | This environment |
|---|---|
| sequence item | immutable request dataclass plus its `XTransfer` handle |
| sequencer request stream | XReactor `AsyncSingleCycleDriver.submit()` |
| driver `get_next_item/item_done` | XReactor submission scheduling and `PENDING -> PROCESSING` transition |
| monitor analysis transaction | immutable `CycleMonitor` or `ReadyValidMonitor` snapshot |
| analysis port | accepted and observed transaction streams |
| reference model / scoreboard input | completed or observed `XTransfer` |
| UVM run phase / objection | pytest fixture plus `Execution` lifetime |

`XTransfer` is a task-like handle, not a single event.  A submitted request is
`PENDING`, becomes `PROCESSING` when the DUT accepts it, and becomes
`COMPLETED` when the output monitor supplies its response.  Acceptance and
completion retain their separate `XEvent` objects.  Cancellation and failure
are terminal states, which allows redirects and flushes to retire in-flight
predictor work explicitly.

`XTransfer` is intentionally not the name for every event in the environment.
An `XEvent` is one timestamped occurrence. A monitor observation is a passive
transaction. An `XTransfer` exists only when submitted work needs a lifecycle
and a result. Ready/valid training therefore completes at its acceptance
event, while integrated-BPU prediction and metadata remain independent monitor
streams; inventing request/response pairing for those ports would encode a
relationship that the RTL protocol does not provide.

Drivers and monitors remain independent. A driver publishes accepted
transfers and may launch one submitted item per cycle without waiting for an older
response. A passive `CycleMonitor` uses xreactor's persistent `@on`
subscription and synchronous `capture` callback. xreactor `Scoreboard` joins
those streams by acceptance cycle plus the declared pipeline latency and calls
the same `check()` used by direct mode. The subscription is armed only while
transfers are outstanding, because a permanent clock subscription would itself
keep an event-driven simulation advancing.

MicroBTB exercises a one-cycle response pipeline; MainBTB exercises a
three-cycle response pipeline. Their tests submit four adjacent requests
without awaiting between submissions and assert distinct acceptance and
completion events.

The same pattern is used by AheadBTB, TAGE, SC, ITTAGE, and MicroTAGE with
their declared pipeline latencies. RAS and MicroRAS use pulse/cycle drivers and
event-correlated monitor snapshots. The integrated BPU uses a project-level
`BpuTrainingDriver` on XReactor's `AsyncDriver` and
`drive_ready_valid(..., bits=...)` for FTQ training, plus `ReadyValidMonitor`
for prediction and metadata. The generic handshake helper commits Rise-written
payload and valid before sampling combinational ready, then withdraws valid
immediately after acceptance. Protocol edges and picker write modes stay inside components;
pytest scenarios contain no explicit edge waits or direct signal writes.

MicroRAS neutral-correction tests use ordinary `UrasCycle` transactions and
event-correlated `CycleMonitor` results, with direct architectural assertions.
They distinguish S2's delayed-redirect recovery from S3's direct main-RAS path;
the driver does not invent a uniform bubble for both stages. Functional bins
are sampled only after complete target/validity checks and cancellation checks.
Project evidence hooks write verdicts and the raw-file manifest only for actual
pytest execution. Collection-only sessions retain the previous formal evidence,
including when collection fails; they cannot be interpreted as a zero-test run.

TAGE and MicroTAGE also separate the earlier position input from the later
base-result input. Their agents drive the two phases through disjoint
`AsyncSingleCycleDriver` bindings, timed from the accepted transfer, and
observe all four prediction slots. The original slot-zero scalar fields remain
available for serial tests; vector tests use `predict_branches()` and the
returned per-slot metadata without driving pipeline IO directly.
TAGE feedback checks use a separate input contract. `observe_training()` owns a
temporary passive `CycleMonitor` subscription over the complete feedback Bundle.
`train_checked()` freezes semantic expectations before driving, then compares the
actual beat count, sparse resolved-slot placement, MainBTB counter, branch identity
and genuine captured metadata with the same core Scoreboard in direct mode.
The expected representation does not call the driver's encoder: a resolved slot
is not the flattened predicted MainBTB/metadata index. Inactive and unmatched
resolved branches must not consume predicted entries. Missing, extra or corrupted
beats raise contextual pytest-native failures. Output state is checked separately
by the existing asynchronous prediction Scoreboard; submission and drain APIs hide
task scheduling. No new Interface, domain-specific matcher base or BundleDriver
class is needed, and all edge/VPI details stay outside architectural testcases.

MainBTB's `observe_counter_activity()` temporarily owns two passive `@on`
subscriptions: public FTQ feedback and a static read-only Bundle covering the
counter queue ports and occupancy of all four physical banks. The installed
legacy pulse training source is synchronous and does not publish `XTransfer`
acceptance; `train_during_predictions_checked()` therefore compares its monitored
inputs and aligned queue/writeback traces in direct Scoreboard mode, without
pretending to bind it as an asynchronous driver. Independently frozen semantic
input and counter expectations precede driving. The prediction stream still uses
the existing asynchronous driver/monitor Scoreboard and its submit/drain API.
Same-bank sentinel reads retain two distinct counter requests, whereas an
opposite-bank control bypasses the flow queue. Both target ways, both directions
and low/high set contexts are checked; forward/reverse overlapping readback
preserves the opposite-way residents and both read sentinels. This bounded model
does not claim overflow handling or entry-write-buffer verification. Observation
scopes reject nesting and close both subscriptions even after startup/body errors;
missing or ambiguous memory-direct bindings fail explicitly, never skip the test.

MainBTB's `observe_entry_activity()` applies the same arrangement to the
separate entry WriteBuffer: a temporary public-input subscription and a static
read-only Bundle covering requests and SRAM writebacks for all four banks and
both ways. `train_entry_during_predictions_checked()` shares the input-checking
path, but uses an independent entry payload/timing reference and its own direct
Scoreboard. Two same-key indirect rewrites coalesce to the latest payload under
same-bank read blocking; opposite-bank reads allow both payloads to drain in
order, including a drain concurrent with the second request. Fit/Overflow/
Underflow transitions check carry encoding and the reconstructed full target.
The asynchronous prediction Scoreboard checks full resident and metadata state,
including unchanged counters and neighbors. Common resident preparation uses
normal allocations and genuine metadata, not forced SRAM state. Entry and
counter observation scopes reject cross-nesting and close both subscriptions
on all failure paths. That coalescing reference is bounded to two same-key
counter-2 hits; it does not claim overflow, cross-row migration, flush or stale-way
behavior.

The separate `mbtb_entry_keys_model` describes two distinct-set indirect hits,
not two temporal versions of one key. Both buffered payloads must survive read
blocking and drain in submission order. Each target belongs to its own PC even
when feedback order is reversed, and carry is derived relative to that PC.
Equal targets do not make distinct keys eligible for coalescing. State prediction
changes only the two targeted entries, preserving all counters, metadata and
neighbors; full native request/writeback expectations precede driving. It uses
the same static Bundle, passive `@on` monitors, direct input/activity Scoreboard
and asynchronous prediction Scoreboard, without another driver or matcher base.
Shared normal resident preparation optionally spaces tags to expose wrong-key
pairing while leaving earlier scenarios unchanged. This is a two-hit, two-key
reference, not a full WriteBuffer/FTQ, capacity-overflow, flush or stale-way model.

`mbtb_shadow_model` separates another pair of identities: captured-cold feedback
selects a request victim through an independent two-way LRU state machine, while
an existing entry shadow retains its own physical writeback owner. A normal
correct-taken touch and two adjacent rewrites exercise clean-first and
pending-second crossings. The same static Bundle and passive monitors check
every request/writeback; per-request read status belongs to that request port,
not to global dirty occupancy. Carry/timing payloads reuse the proven two-rewrite
contract; no observed DUT replacement state advances the LRU model. Shared
`resident_vectors`/`allocate_pair` prepare genuine states and capture metadata
without test-level IO or forced SRAM contents.

This bounded shadow reference currently commits only to initially counter-2
residents. An isolated ordered module diagnostic exposes a distinct-tag
conditional neighbor reset from 3 to 2 even though entry payload/owner/timing
are correct: entry routing follows the retained shadow owner, but counter reset
still follows the requested cold-feedback victim. That is not hidden by the
weak-counter PASS or turned into an automatic XFAIL. Full FTQ epoch/redirect
qualification still needs an independent audit. Likewise, one-hot training
wayMask does not prove the whole entry buffer is one-hot: a concurrent flush
can activate another write port. Neither non-weak counter safety nor complete
flush/row-priority behavior is claimed by this reference.

`observe_entry_shadow()` adds a separately scoped passive `@on` monitor over
the static entry-shadow Bundle: four physical banks, two retained owners and
two buffer depths, including validity, dirty state and every entry field.
It neither drives native state nor supplies expected ownership. The depth-one
scenario fills two distinct-set keys under real same-bank read pressure, proves
the second key occupies depth one, and checks both fill and retarget input /
request / writeback timing through the existing direct Scoreboards. Clean-first
and pending-second request orderings cross the owner; opposite-bank reads are
the flow control. The independent `mbtb_depth_model` keeps entry ownership and
request-way counter initialization separate, including an unmatched empty
way's counter 0 to 2 transition. Both complete public profiles are checked in
forward and reverse asynchronous batches with exact cadence and latency.
This is a bounded standalone two-way/two-depth contract, not a full allocator,
arbitrary saturated-neighbor, FTQ epoch/redirect, overflow or multi-hit model.

`train_during_multi_hit_cleanup()` owns the S2 resume timing inside an active
deferred-cleanup scope. The dirty control leaves cached clears running. The
clean control sends one clear pulse, pauses S2 and lets it drain, then resumes
cleanup while the existing PulseDriver launches normal training. Tests do not
handle edges, signal writes, tasks or gather. A separate scope-active flag
prevents accidental nesting after S2 has resumed; interrupted clear pulses
restore the deferred gate. After a fresh lookup replaces cached multi-hit,
`retire_multi_hit_cleanup()` lets pending writebacks finish before readback.

`mbtb_cleanup_model` predicts both complete public profiles and the exact
training/clear payloads plus all four before/after shadow slots independently
of the encoder. Passive entry and shadow `@on` monitors pair inputs with
pre-edge and next-cycle state. Direct Scoreboards check the feedback beat,
one genuine simultaneous write at four ticks after acceptance, dirty/clean
state, depth zero/one and other-bank isolation. Asynchronous prediction
Scoreboards then compare both profiles in forward/reverse batches. This
bounded nonzero-key module contract excludes the jointly zero tag/position
defect; complete FTQ reachability and full functional correctness are not
implied by native line coverage.

`python3 -m bpuverify.mbtb_branch_audit` checks the exact generated hierarchy
constants behind eight unhit branch arms: flush mask bit zero is always zero,
so seven enabled port-zero payload muxes cannot choose the clear arm; the
counter queue RAM read enable is tied high. Exhaustive Boolean cases and four
in-memory source mutations validate the premises without modifying RTL or
subtracting raw coverage denominators. This is a MiniConfig structural proof,
not a proof for arbitrary configurations or integrated FTQ safety.

Cleanup/zero-key diagnostics remain outside normal pytest collection. Run
`python3 tests/mbtb/diagnostics/run_flush_key_probe.py` to preserve all four
formal reports and redirect both DUT raw data and functional destinations to
a fresh isolated directory. Its static monitors prove real simultaneous
training / flush write valids and both shadow depths. Across all physical
banks, tag-zero/position-zero cleanup requests the upper way but can route the
zero payload through a retained lower-way owner; those are ordinary contextual
Scoreboard failures, not registered XFAILs or integrated FTQ reachability proof.
After a fresh lookup replaces cached multi-hit state, the helper retires queued
writebacks before checking the other set. Otherwise a pending update may still
be starved by repeated cleanup and a first SRAM read can be stale without data
loss. Only successful post-retirement comparisons count as diagnostic PASS;
none of these raw files or observations receives formal coverage credit.

`mbtb_replacement_model` owns the shared `MbtbTwoWayLru` policy and a bounded
`MbtbReplacementState` indexed by alignment bank and halfword PC[9:4]. Entry
SRAM set PC[10:5] and internal bank PC[4] are a different identity: changing
PC[10] changes the SRAM set but shares replacement state. The reference is
advanced by intended normal allocations and taken single-hit feedback, never
by observing a DUT victim. Not-taken feedback and prediction reads do not
touch it. `mbtb_shadow_model` reuses the exact same policy class.

The indexed replacement scenario prepares four contexts without an intervening
reset: a target, its set+32 alias, an adjacent independent index, and the other
alignment bank. Fresh normal metadata drives all allocations; independent
victims and payloads are checked before full unchanged snapshots are adopted.
Conditional residents ensure feedback can qualify through the backend resolve
path: correct taken feedback saturates 2 to 3 and touches LRU, actual not-taken
is a misprediction that decrements 2 to 1 without touching LRU, and a new
allocation resets its selected counter to 2. A correct direct backend resolve
is filtered by FTQ, so it is not used as this scenario's normal touch stimulus.
Every replacement then compares all complete profiles through the existing
asynchronous prediction Scoreboard, including opposite ways and inactive fields.
Forward/reverse submission batches assert acceptance cadence and completion
latency; tests contain no edge waits or explicit coroutine gather. This is
normal two-way MiniConfig allocation/feedback coverage, not a general shadow,
flush, overflow or integrated-FTQ reference.

`observe_prediction_state()` adds optional read-only TAGE state to that same
paired prediction observation. Its lazy `TagePredictionStateMonitor` supplies a
static Bundle of hit masks, each table's per-way taken/useful values and the
selected alternate counter. While the scope is active, the existing `@on`
capture samples this Bundle together with public prediction; no later VPI read,
second competing monitor task or new association mechanism is introduced.
The scope drains before switching bindings, restores the basic decoder on both
success and failure, and treats missing or ambiguous VPI capability as an error.
Raw hit masks retain simultaneous-way hits rather than silently choosing one
without exposing the ambiguity. `TagePairModel` independently predicts a
prepared table2/table3 pair and both alternate-confidence selector buckets;
observed counters never initialize or update it. Physical ways are frozen at
the earlier real allocations. This is not a complete allocation, hashing,
useful-aging, stale-metadata or program/FTQ reference.

`observe_writes()` owns a separate bounded passive `TageWriteActivityMonitor`
over all four banks and both highest-table ways. Its static read-only Bundle
captures active/inactive ports in one event, including set/tag, entry counter,
valid and actual outcome. `train_with_writes_checked()` first verifies the
complete genuine sparse input independently, then compares frozen write
expectations through the core Scoreboard in direct mode. A hit plus allocation
must produce one snapshot with two writes, not two successful serial snapshots;
no-op/qualification cases require one or zero writes. The accepted feedback to
buffer-input write latency is four cycles (t1, t2, t3 and registered table request).
The independent `expected_tage_mixed_writes()` covers only the prepared
highest-table family and zero folded history. Full metadata/state readback uses
the existing asynchronous prediction Scoreboard, with callbacks frozen before
submission and both forward/reverse overlapping batches. Prepare the family
once per context/way; subsequent cases restore its victim and counter through
normal checked transactions, rather than repeating the aging sweep or writing
internal state. Saturated counter/useful holds intentionally suppress a write
and are not evidence of parallel activity. Missing/ambiguous native capability,
nested observation and lifecycle errors fail explicitly; scopes close on both
body and startup failures. No new driver/matcher/interface abstraction is added,
and this does not establish all shadow slots, adjacent feedback equivalence,
the complete allocator or program FTQ scheduling.

`train_batches_with_writes_checked()` extends that same comparison path to a
feedback burst. It freezes independently normalized inputs and write expectations
before driving, rejects empty bursts, checks adjacent acceptance or fully separated
input cadence, and pairs each write snapshot with its accepted feedback for latency.

`observe_shadows()` adds a separate bounded, passive `TageShadowMonitor`. A static
Bundle captures every highest-table bank, owner and depth together with drain
valid/ready in the same `@on` event. Native discovery and binding remain in the
monitor, not testcases. Missing/ambiguous VPI capability, nested scopes and startup
or cleanup failures are explicit; all exits release the scope's active flag.
`tage_shadow_model.advance_tage_shadow()` independently advances a qualified
starting snapshot: drain first, then write; lookup by set/tag can retain a different
owner from the request port, and counters saturate from retained state rather than
copying the stale request counter. It supports one write per cycle and rejects
unsupported full-row-miss/PLRU outcomes instead of guessing them.

`train_batches_with_read_pressure()` is a domain operation composed from the
existing synchronous feedback driver and asynchronous prediction Scoreboard. It
validates every feedback beat before any submission, rejects foreign-bank or
SRAM-reread-dependent feedback, keeps a normal same-bank prediction stream active
while provider-only feedback fills pending depths, then drains both streams and
quiesces owned controls. Tests see completed prediction transfers, not edges or
coroutine gathering. Failure and cancellation still quiesce both lookup drivers.

The standalone `tests/tage/diagnostics/retained_owner_probe.py` uses these operations
to separate captured physical-way identity from retained counter ownership. Real
metadata is captured before normal tag migration; taken base prediction prevents
useful updates, isolating this requirement without claiming the known useful
misassociation is fixed. Independently frozen inputs, all write ports, every shadow
cycle and forward/reverse complete profiles are checked. This upper-saturation,
zero-history diagnostic is not a complete allocator, lower-saturation, useful-aging
or FTQ model, and its raw output is never added to a formal manifest automatically.
Its shared `check_case()` is also called by the registered BPU-TAGE-034 pytest
matrix; only that explicit pytest path samples the 192 functional bins after
the checks and can contribute to a later full formal refresh.
Prediction callbacks use the pure `Scoreboard.compare()` operation, not a nested
direct `check()`: the outer asynchronous Scoreboard owns transfer identity,
accepted/observed events, failure statistics and exception formatting. This keeps
field-level differences together with sequence/request/timing context. A mutated
neighbor profile exposed this distinction; positive and negative regression tests
now protect it, alongside eight hardware negative controls.

`train_batches_with_writes_checked()` still exposes transactions, not task gathering or edges. The bounded
`tage_overlap_model` distinguishes adjacent old-SRAM reads from separated current
reads: a cold misprediction forces `t0_needRead`, so captured metadata must not be
mistaken for the counter used by separated training. Two adjacent decrements must
forward and saturate the resident counter even when both request the same value;
after a drained first write, a fresh SRAM reread may suppress a saturated write.
The scenario freezes its six-neighbor baseline once and verifies restoration
against it too. This is not general adjacent/sequential useful-update equivalence,
all shadow slots, or a complete FTQ reference.

Secondary S2 base-driving tasks share transfer failures with the prediction
Scoreboard. Agent shutdown cancels unfinished secondary tasks and consumes only
the identical already-owned first failure after Scoreboard cleanup; independent
errors still propagate. Normal drive/drain paths still raise failures. This
avoids reporting one asynchronous mismatch again as a pytest teardown error,
and cleanup tests plus negative controls verify that tasks are reclaimed.

SC uses XReactor's three-stage driver for S0/S1/S2 and accepts a four-slot
MainBTB/TAGE bundle at S2. Its monitor pairs the entire combinational
direction/use vector with the following cycle's registered metadata, while
retaining scalar slot-zero aliases for existing serial tests.
SC training uses a separate pulse driver and a full resolved-branch vector.
`ScBatchTraining` keeps the resolved slot, predicted MainBTB slot, outcome,
and qualification together; the agent converts that transaction into the
banked MBTB metadata and padded feedback Bundle. Serial `ScTraining` delegates
to the same path with resolved/predicted slot zero.

SC threshold state checking is a separate domain contract, not a replacement
for the prediction pipeline scoreboard. `ScThresholdModel` consumes genuine
feedback metadata before driving, independently computes eligibility and the
net contribution of branches hashing to each way, then rejects an entire
out-of-range candidate rather than clipping it to the custom boundary. The
expected vector never uses a DUT threshold observation to seed its state.
`ScThresholdMonitor` binds the native read-only VPI handles into a static Bundle
and inherits `CycleMonitor`'s `@on` capture. `ScAgent.check_thresholds()` arms a
bounded subscription for one immutable snapshot and closes it immediately,
so observation does not introduce a permanent clock-advancing task.

```python
update = reference.apply(feedback)
await agent.train_batch(feedback)
await agent.check_thresholds(update.after, request=feedback)
```

This uses the same core Scoreboard comparison in direct mode, with request,
driven-feedback and observed event ticks, full-state differences and pytest-native
exceptions. For adjacent feedback, the model consumes all beats with
`apply_many()`, the agent sends them with `train_batches()`, and one drained
snapshot checks the final vector; the independent feedback monitor verifies
the actual beat count and cadence. Missing picker VPI capability is an explicit
error with a rebuild hint, never a skipped test. No edge wait, raw signal write,
VPI path discovery or `asyncio.gather()` appears in these scenario APIs.
The current four-way MinimalConfig limits and picker GuardedPc address units
are explicit in the SC scenarios; they do not claim full-program FTQ trace
reachability or an independent signed table-counter reference.

The integrated BPU uses a ready/valid training driver. Its binding contains
the entire FTQ branch vector, and `BpuBatchTraining` encodes a whole accepted
beat with explicit invalid slots. `BpuTraining` remains the scalar
convenience transaction and delegates to the same vector encoder.

Pipeline callers submit all requests and drain the batch:

```python
for pc, expected in vectors:
    agent.submit_predict(pc, expected=expected)

await agent.drain_predictions()
```

This is the Python equivalent of a UVM sequencer feeding the driver while a
monitor and scoreboard progress independently. Tests do not expose
`asyncio.gather()`. Awaiting `agent.predict()` in the submission loop is valid
for a serial scenario, but deliberately removes pipeline concurrency.

The built-in association modes are FIFO, fixed latency, and request/response
key. A special protocol can override the pure `associate()` hook without
changing expected generation or comparison. Redirect support cancels affected
`PENDING` and `PROCESSING` transfers rather than silently dropping results.

Pytest is organized by DUT under `tests/<dut>/`. Each suite declares its own
fixture in `conftest.py`, keeps scenario data and reusable assertions in
`definitions.py`, and leaves test modules focused on execution and verdicts.
`tests/support/` contains only cross-DUT fixture construction and repository
paths.
