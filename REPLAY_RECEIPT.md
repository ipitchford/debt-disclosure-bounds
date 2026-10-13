# Replay routes and executed evidence

## Source-based internal replay, 13 October 2026

The revised source workspace completed `sh run_all.sh`: 21 tests passed; all six computational source hashes matched; the 105 official DMO gilt rows matched by identity, type, maturity and amount; accounting checks passed; all result families were regenerated. The 2,598 exact model snapshots matched their source-built problems. All 4,576 endpoint certificates verified and linked to the result files under both normal and optimized Python. Six semantic mutations were rejected in both modes and the valid control was accepted. Figures, tables and the 19-page manuscript were rebuilt.

The final presentation revision changes synthetic-perimeter labels and table layout only. It changes neither the model specifications nor any certified endpoint. Source replay is internal and used retained source files; it is not independent reproduction or validation of institutional modelling assumptions.

## Public offline replay

With Python 3.12 or later and no third-party packages, run:

```
python scripts/verify_certificates.py --frozen
python scripts/verify_accounting.py
python scripts/negative_controls.py
```

Repeat with `PYTHONOPTIMIZE=1`. The checker verifies all 4,576 endpoints against shipped exact model snapshots, checks inventory completeness, and links exact values to results. It never invokes a numerical solver. This checks the encoded finite programmes, not source acquisition, the continuous-to-finite theorem, or the fiscal assumptions.

## Full regeneration

Obtain the six hash-matched computational inputs described in `data/EXTERNAL_INPUTS.md`, then run `sh run_all.sh` in a disposable extraction. BoE and OBR raw workbooks are deliberately not redistributed. `uv.lock` pins the numerical environment; Tectonic builds the manuscript. A changed upstream vintage fails rather than silently replacing the historical source.

Fresh frozen-archive replay, manifest/AI-index checks and PDF text inspection are retained in the publication's external gate receipt, bound to the archive SHA-256. They are not claimed by an unexecuted command in this document.

The accounting check establishes the reported cash and balance-sheet identities, the GBP 1 million loan roll-forward discrepancy at published precision, and the interval [5.314355,5.315365] billion per percentage-point-year under frozen-February assumptions. This is a source-precision envelope, not a confidence interval, forecast, October balance or multiyear response.
