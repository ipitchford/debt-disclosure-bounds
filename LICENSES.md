# Component licence map
- Original manuscript, explanatory documentation, structured claims, original figures and project-created results: CC0-1.0; see LICENSE.
- Original Python/shell/checker code: MIT; see LICENSE-CODE.
- UK DMO official export and Crown source data: Crown copyright, reused under Open Government Licence v3.0 where applicable: https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/ . Source: UK Debt Management Office; no endorsement implied.
- Bank of England general website files, APF workbooks and annual accounts PDF: upstream rights retained; no blanket OGL assumption. These raw resources are excluded from the public package and retrieved separately for replay.
- OBR workbook: excluded from the public archive because redistribution permission was not established in this intake. Retrieve the hash-matched file separately as described in data/EXTERNAL_INPUTS.md.
- US Treasury Fiscal Data JSON: US federal government source data; retained with source attribution and original metadata. No endorsement implied.
- Other externally sourced datasets/material: upstream terms apply; see data/PROVENANCE.md. The house CC0 licence does not override them.
- Private supplied review/audit payloads and local machine paths are not public assets. Public response documentation is original explanatory material; it does not relicense a reviewer report.
- Python dependencies and tools are external software under their own licences; uv.lock is an environment record, not redistribution of those libraries.
Public-package preparation must enforce this boundary before freezing. Keeping a third-party file in a private working tree does not authorize its inclusion in the archive.
