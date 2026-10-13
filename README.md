# What public debt statistics establish about interest-rate exposure

Code, data and paper for sharp, exactly certified bounds on the increase in debt interest
that is consistent with specified debt statistics and a declared refinancing model,
illustrated with UK (12 October 2026) and US (30 September 2026) records.

**Evidence boundary:** All 105 UK gilt rows have been matched against an independently downloaded official
DMO export, including ISIN, type, maturity and amounts; bill timing remains reconstructed. The code's
`consolidated` and `consolidated_bank` labels denote synthetic IPP-funded runoff and
banknote-allocation scenarios, not validated fiscal accounting. APF purchase proceeds
are not its loan balance. The OBR comparison is unbridged and validates nothing.
Certificates establish optima for encoded models, not those accounting assumptions.

- `paper/main.pdf` — the paper.
- `src/ddb/` — the method: `pa.py` (exact piecewise-affine functions), `lp.py` (breakpoint
  linear programmes, exact rational certification of the solver's basis, primal witness
  check, coupled programme for worst-case value of disclosure), `model.py` (ledger, scenario
  kernels, disclosure statistics), `closed_forms.py` (classical bounds used as cross-checks),
  `uk.py`, `us.py`, `data_uk.py` (data and disclosure sets), `truth_direct.py` (an
  independent computation of instrument-level values), `experiments.py`.
- `src/ddb/specs.py` — every linear programme is built from a JSON specification, so stored
  certificates can be re-checked against an independently rebuilt programme.
- `scripts/run_experiments.py` (all bounds, with certificates), `run_perimeter.py`,
  `run_inflation_terms.py`, `run_revision_extensions.py`, `verify_certificates.py` (re-checks
  4,540 original and 36 recursive-annual endpoint certificates without invoking the solver,
  and links their exact values to results), `make_figures.py`, `make_tables.py`.
- `tests/` — property tests against closed forms on random portfolios, exact identification,
  invariance to grid refinement, attainment on the daily grid, coverage on the UK data, and
  data-integrity checks.
- `data/raw/` — redistributable source files; `data/PROVENANCE.md` documents origin and checks. BoE and OBR originals are excluded; see `data/EXTERNAL_INPUTS.md`.
- `results/` — every bound with its exact rational value (`*_exact` fields), feasibility of the
  actual ledger, and coverage status; `results/certificates/` holds the extremal portfolios and
  exact dual multipliers.
- `REVIEW_RESPONSE.md` and `CITATION_AUDIT.md` — review disposition and bounded source comparison. Private prompts and third-party review text are not redistributed.

For offline exact certificate replay, run `python scripts/verify_certificates.py --frozen` with Python>=3.12. Only the standard library is needed. It checks all 4,576 endpoints against shipped exact model snapshots and result values. This does not reproduce source acquisition or validate the fiscal model.

For source-based regeneration, obtain the hash-matched external inputs described in `data/EXTERNAL_INPUTS.md`, then run `sh run_all.sh`. The source-based builder is compared exactly with the frozen models. Source websites can update files; the runner fails rather than silently substitute a new vintage. The package version `1.1.0rc1` is the PEP440 spelling of release `1.1.0-candidate`.

Author: Anonymous. AI-assisted analysis and review are not human peer review.
The second evaluator checks original instrument-level values with separate parsers but
shares the modelling conventions. New recursive kernels have independent scalar-recurrence
tests. Original `iai` means first-pass financing, not recursive continuous-time financing.
See `paper/accounting_revision.tex`, `results/disclosure_vectors.json`, and the review response.
