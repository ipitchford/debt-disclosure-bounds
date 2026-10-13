#!/bin/sh
# Replays every result in the paper from the source files in data/raw.
# Requires uv (https://docs.astral.sh/uv/) and, for the PDF, tectonic.
set -eu
cd "$(dirname "$0")"
uv sync --frozen
PY=.venv/bin/python
$PY scripts/check_inputs.py
$PY -m pytest -q tests/
$PY scripts/verify_official_gilts.py
$PY scripts/verify_accounting.py
$PY scripts/run_experiments.py
$PY scripts/run_perimeter.py
$PY scripts/run_inflation_terms.py
$PY scripts/run_revision_extensions.py
$PY scripts/freeze_models.py --check
$PY scripts/verify_certificates.py
PYTHONOPTIMIZE=1 $PY scripts/verify_certificates.py
$PY scripts/negative_controls.py
PYTHONOPTIMIZE=1 $PY scripts/negative_controls.py
$PY scripts/make_figures.py
$PY scripts/make_tables.py
if command -v tectonic >/dev/null 2>&1; then
  (cd paper && printf '\\newcommand{\\buildinfo}{git %s}\n' "$(git rev-parse --short HEAD 2>/dev/null || echo unversioned)" > build_info.tex \
     && tectonic -X compile main.tex)
fi
echo "replay complete"
