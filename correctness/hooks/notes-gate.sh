#!/usr/bin/env bash
# The notes gate: structure and coverage on every commit. Findings re-run their
# evidence in the second hook, which is slower and so runs on push and in CI.
set -euo pipefail
python correctness/checks/check_notes.py "$@"
