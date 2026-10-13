#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${HOME}/.flexweek-ui-harness/scratch/1.0.0/android-shots/v2"
APK="${ROOT}/app/build/outputs/apk/debug/app-debug.apk"
PKG=com.flexweek.app
ACTIVITY=${PKG}/.MainActivity
mkdir -p "$OUT"

capture() {
  local name=$1
  shift
  adb shell am force-stop "$PKG"
  sleep 1
  adb shell am start -n "$ACTIVITY" "$@" >/dev/null
  sleep 3
  adb exec-out screencap -p > "${OUT}/${name}.png"
  echo "wrote ${OUT}/${name}.png"
}

adb wait-for-device
adb install -r "$APK" | tail -1

for width in 360 412; do
  adb shell wm size "${width}x800"
  for theme in light dark; do
    dark=false
    [[ "$theme" == dark ]] && dark=true
    for text in normal large; do
      large=false
      [[ "$text" == large ]] && large=true
      extra=(--ez darkTheme "$dark" --ez largeText "$large" --ez prePaired true --es sync ok)
      base="v2-${width}-${text}-${theme}"
      capture "${base}-today" --es screen today "${extra[@]}"
      capture "${base}-week" --es screen week "${extra[@]}"
      capture "${base}-add-sheet" --es screen today --es sheet add "${extra[@]}"
      capture "${base}-plan-sheet" --es screen today --es sheet plan "${extra[@]}"
      capture "${base}-late-sheet" --es screen today --es sheet late "${extra[@]}"
    done
  done
done
adb shell wm size reset
