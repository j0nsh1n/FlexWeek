#!/usr/bin/env bash
# Start the Developer build workflow on Depot CI from main and say where to follow it. CI moved from
# GitHub Actions to Depot on 2026-11-24 (.depot/workflows/dev-build.yml).
set -euo pipefail

DEPOT="${DEPOT:-depot}"
if ! command -v "$DEPOT" >/dev/null 2>&1; then
    echo "The Depot CLI (depot) is not installed: https://depot.dev/docs/cli/installation" >&2
    exit 1
fi

echo "Starting the Developer build workflow on Depot from main..."
"$DEPOT" ci dispatch --repo j0nsh1n/FlexWeek --workflow dev-build.yml --ref main

echo "Started. The build takes about 20 minutes and replaces the dev pre-release."
echo "Follow it with: $DEPOT ci workflow list --repo j0nsh1n/FlexWeek --name 'Developer build'"
