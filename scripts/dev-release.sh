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

echo "Started. The build takes about 20 minutes and replaces the dev pre-release."
echo "Follow it at https://github.com/j0nsh1n/FlexWeek/actions/workflows/dev-build.yml"
