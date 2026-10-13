# AI index: debt-disclosure bounds
## Identity and reading order
Version1.1.0-candidate; Anonymous; DOI10.5281/zenodo.23337976.
Start with [STATUS](STATUS.md), [ASSURANCE](ASSURANCE.md), [manuscript source](paper/main.tex), [claims](CLAIMS.json), then the relevant implementation and evidence below.
## Exact target
For the specified debt ledger and rate/refinancing conventions, minimise and maximise a linear interest-cost functional over portfolios matching disclosed moments. The target is a model-conditional identified set, not actual fiscal exposure without an accounting bridge.
## Claims and dependencies
1. Piecewise-affine moment/kernels reduce to finite programmes: manuscript breakpoint lemma; [piecewise affine arithmetic](src/ddb/pa.py), [ledger/kernel](src/ddb/model.py), [LP and checker](src/ddb/lp.py). Requires the stated support/grid and endpoint conventions.
2. Identification is constancy over the **entire** feasible set, equivalently objective orthogonality to span(P−P): manuscript identification revision. Actual single-point support is not disclosed support.
3. Disclosure value uses a vector of linear measurements, not an unqualified single statistic: [specifications](src/ddb/specs.py), [vector inventory](results/disclosure_vectors.json). Conditional means with unknown denominators require accompanying amounts; unequal vector sizes are not equal-cost comparisons.
4. Certified endpoints: [checker](scripts/verify_certificates.py), [certificate directory](results/certificates), corresponding JSON results. Match specification keys, primal/dual equality and results links before quoting a table.
5. Exact **discrete** annual recursive financing: [accounting/financing revision](paper/accounting_revision.tex), [extension runner](scripts/run_revision_extensions.py), [results](results/recursive_annual.json). Not continuous exponential financing.
6. Historical accounting and conditional residual envelope: [empirical revision](paper/empirical_revision.tex), [accounting checker](scripts/verify_accounting.py). February fixed-balance derivative does not establish October or multi-year paths.
## Data and replay
[Data provenance](data/PROVENANCE.md), [source rights](LICENSES.md), [replay](REPLAY_RECEIPT.md), [full runner](run_all.sh), [environment specification](pyproject.toml), [locked dependencies](uv.lock).
Original BoE raw resources require external retrieval; do not interpret missing nonredistributable input as an invitation to fabricate data. Use documented source hashes and fail on mismatch.
## Falsification and limits
[Negative controls](scripts/negative_controls.py) and [tests](tests/test_core.py) check selected encoding failures. Numerical replay validates encoded programmes, not completeness of institutional accounts. Gross and synthetic perimeters and gilt-yield/common-rate scenarios must not be conflated. Annual sufficiency does not imply arbitrary subannual sufficiency.
## Review, prior art and reuse
[Review response](REVIEW_RESPONSE.md), [citation and prior-art audit](CITATION_AUDIT.md), [sources](SOURCES.md). Classical moment/LP sources are antecedents, not evidence for new fiscal facts. Read [licence map](LICENSES.md) before redistribution. No global novelty, REF four-star rating, formal verification or unaffiliated reproduction claim.
