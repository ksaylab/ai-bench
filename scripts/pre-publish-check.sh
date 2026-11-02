#!/bin/sh
# Required check before any push (METHODOLOGY.md, "Before publishing").
# Needs PRIVATE_TERMS_FILE pointing to the private list of terms, outside this repository.
set -eu
cd "$(dirname "$0")/.."
echo "== tests (no network) =="
python3 -m unittest discover -s tests -t . -q
echo "== secrets and private terms =="
python3 -m aibench.check "$@"
