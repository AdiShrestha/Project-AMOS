# Project AMOS / BPFeat research foundation

Start with [plan.md](plan.md). It contains the legacy audit, mathematical corrections, the research protocol to develop, factory v3.3 integration work, and ordered contracts for future Architect and Implementor sessions.

**Status: corrected engine foundation; no admitted research results; not submission ready.** Historical scores, plots, models and PASS reports are not evidence for this version. The active engine does not yet implement a publication cache or an independent query stream.

```sh
cmake -S . -B build/debug -DCMAKE_BUILD_TYPE=Debug
cmake --build build/debug -j 2
ctest --test-dir build/debug --output-on-failure
python3 factory/run_self_tests.py
```

The engine documentation is [source/README.md](source/README.md). It requires an explicit model and unlabeled event CSV; there is no fallback predictor or bundled research dataset. The test fixtures are solely for correctness checks.

The supplied software factory v3.3.0 is preserved in history; the active documented integrity repair is `3.3.1-amos.1` under `factory/`. Its existing binary-classification profile does not validate streaming publication, query coverage, latency, load generation or the intended inference unit. Keep `project/research_plan.json` unfrozen until the adapter and scientific protocol pass the gates in the plan. The unrelated v2.6 forensic example in `docs/FORENSIC_AUDIT.md` belongs to the supplied factory, not AMOS; AMOS evidence is under `docs/audit/legacy/`.

Local raw candidates are preserved under `data/quarantine/raw/` and excluded from Git. Their manifests record local hashes, not provider authenticity or redistribution permission. Re-download instructions and terms must be established before data admission. Old repository history and its code snapshot are preserved by legacy tags; the new folder is the working checkout.

The existing root license is retained. Artifact sharing and dataset licenses still require explicit review; see the plan.

The migrated-tree re-audit found and repaired additional numeric, diagnostic and factory-integrity defects. Read [the repair report](docs/audit/reaudit_2026_10_01/report.md) and [the critical review of the supplied research assessment](docs/research/deep_research_review.md). Native Debug/Release/ASan+UBSan/ThreadSanitizer checks, 27 bound Python tests and 307 factory tests passed within their stated software scope; none admits research evidence. Older audit manifests describe their original snapshots.
