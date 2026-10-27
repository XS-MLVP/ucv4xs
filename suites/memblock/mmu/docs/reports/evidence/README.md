# Evidence retention

The original first-pass run directories were pruned after their metrics were
written into the reports. Historical compact audits remain in the per-cycle
directories; full final runs are retained under `results/`.

Final committed runs (phase 1 + phase 2):

- `tlbfa-full-06`, `wrapper-full-06`, `tlb-gpa-tests-06`, `tlbn-tests-13`
- `l2mq-03`, `l2pf-05`, `ptwrepeater-06`, `ptwfilter-final-16`
- `hptw-final-02`, `ptw-final-06`, `pmp-final-04`
- `bitmapcache-final-06`, `bitmap-final-07`, `ptwcache-final-02`
- `llptw-final-04`, `l2tlb-final-12`, `l2tlbwrapper-final-05`

Phase-2 closures/residuals and compact evidence are in
`cycle-phase2-20261025/`; phase-2 report is
`docs/reports/final-delivery-phase2-20261025.md`. No waveforms or per-cycle
dumps are retained.
