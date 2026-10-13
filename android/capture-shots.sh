#!/usr/bin/env bash
# Emulator screenshots for lane android-s45. Source android-env.sh first.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
OUT="${HOME}/.flexweek-ui-harness/scratch/1.0.0/android-shots"
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
      extra=(--ez darkTheme "$dark" --ez largeText "$large")
      base="android-${width}-${text}-${theme}"
      capture "${base}-pair" --es screen pair "${extra[@]}"
      capture "${base}-today" --es screen today --ez prePaired true --es sync ok "${extra[@]}"
      capture "${base}-today-sync-off" --es screen today --ez prePaired true --es sync off "${extra[@]}"
      capture "${base}-reminders" --es screen reminders --ez prePaired true "${extra[@]}"
    done
  done
done
adb shell wm size reset
