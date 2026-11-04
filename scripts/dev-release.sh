#!/usr/bin/env bash
# Trigger the Developer build GitHub workflow from main and print the run URL.
set -euo pipefail

if ! command -v gh >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is not installed." >&2
    exit 1
fi

if ! gh auth status >/dev/null 2>&1; then
    echo "GitHub CLI (gh) is not logged in. Run 'gh auth login' first." >&2
    exit 1
fi

echo "Triggering Developer build workflow from main..."
gh workflow run dev-build.yml --ref main

echo "Waiting for the workflow run to register..."
sleep 3

RUN_URL=$(gh run list --workflow dev-build.yml --limit 1 --json url --jq '.[0].url')
echo "Workflow run started: $RUN_URL"
echo "The build takes about 20 minutes and lands on the dev pre-release."
