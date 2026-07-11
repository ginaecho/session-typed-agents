# samples/ — committed data samples (≤200 records per file)

Small, reviewable slices of the full builds. Full datasets are NOT
committed (multi-MB); they are reproducible with the exact commands in
`docs/reference/reports/seam/W3_data_builders.md`.

| file | schema | producer |
|---|---|---|
| `d1_dataset.jsonl` | DatasetRecord | `d1_expand.py` |
| `d2_backtranslate.jsonl` | DatasetRecord (intent non-null) | `d2_backtranslate.py` |
| `d3_repair.jsonl` | RepairRecord | `d3_repair.py` |
| `calibration_candidates.jsonl` | calibration candidate (validator-passing mutants; judge-calibration material, NOT repair data) | `d3_repair.py` |
| `d1_saturation.json` | uniques-vs-candidates curve + run stats | `d1_expand.py` |
| `d3_yields.json` | per-operator repair yield table + run stats | `d3_repair.py` |
| `sig_verify_report.json` | signature-vs-E5-checker agreement | `signature.py --verify` |
| `splits/` | family split registry + strat table + leakage-check output | `splitter.py` / `leakage_check.py` |

Records in the sample files carry their final `split` assignment (the
splitter ran over the FULL builds; these are the first N records of each).
