# Source inputs and redistribution boundary

The public package omits the original Bank of England spreadsheets/HTML and the supplied OBR spreadsheet. Their hashes remain in INPUTS.sha256 as provenance, not as a claim of redistribution permission. The Bank's general legal page does not extend its Database OGL permission automatically to these operational resources: https://www.bankofengland.co.uk/legal . No BoE endorsement is implied. OBR spreadsheet redistribution rights were not established during this bounded check, so the original is also excluded.

`python scripts/fetch_external_inputs.py` retrieves only the BoE APF maturity table used by the numerical builders. It accepts it only if its SHA-256 matches the recorded vintage. It neither bypasses access restrictions nor overwrites different existing bytes. A changed current workbook cannot reproduce this vintage and is not silently accepted.

For OBR table regeneration, independently retrieve the March 2026 Economic and fiscal outlook, detailed forecast tables: debt interest ready reckoner, from https://obr.uk/efo/economic-and-fiscal-outlook-march-2026/ and save it as `data/raw/manual/obr_efo_march2026_detailed_forecast_tables_debt_interest.xlsx`. Its required SHA-256 is `4686d4f77ccba84fa895858e45756bb0d8ed647d9f230a7fa4890c51ef9ee27f`. This comparison is explicitly not validation of the paper's differently defined estimand.

The other BoE files listed in INPUTS.sha256 document provenance and source inspection; they are not required by the numerical regeneration. Links are recorded in PROVENANCE.md. Read original source terms before use. Availability of a historical source vintage is not guaranteed.

Offline checking does not need any omitted resource: `python scripts/verify_certificates.py --frozen` checks all 4,576 endpoint certificates against the shipped exact model snapshots. The producer separately compared those snapshots with the source-based builder. This separates exact encoded-model replay from source acquisition, accounting validity and unaffiliated reproduction.
