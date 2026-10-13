# Assurance boundaries
- **Author claim:** sharp bounds and disclosure comparisons for the stated linear ledger model; exact annual discrete-financing extension; global feasible-set identification criterion.
- **Written argument:** paper/main.tex and included revision sections contain proofs. A finite certificate does not prove the modelling assumptions or every universal theorem.
- **Computation:** results/certificates contains rational primal/dual witnesses. scripts/verify_certificates.py reconstructs each encoded problem, checks feasibility and matching objectives, and links records to results. Rational exactness concerns encoded values, including binary floating-point source conversions, not recovered source precision.
- **Source verification:** scripts/verify_official_gilts.py compares 105 gilt records with a separately retrieved official export. This is producer-coordinated source checking, not unaffiliated reproduction. Bill maturity timing remains reconstructed.
- **Accounting:** scripts/verify_accounting.py checks reported February accounts and a conditional rounding envelope. October loan and IPP observations are distinct quantities, not interchangeable funding bases. No measured five-year residual path is claimed.
- **Review:** supplied major-revision review prompted the changes recorded in REVIEW_RESPONSE.md. Targeted internal follow-up checked the accounting interpretation. Neither is represented as journal peer review.
- **Novelty:** application and inspectable disclosure architecture, not invention of general moment bounds, linear programming or accounting identities. Bounded searches do not prove priority.
- **Formal verification / empirical validation / human review:** not established by this release.
See REPLAY_RECEIPT.md for the replay boundary and AI_INDEX.md for claim-to-evidence navigation.
