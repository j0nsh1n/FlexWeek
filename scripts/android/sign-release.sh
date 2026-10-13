#!/usr/bin/env bash
set -euo pipefail

unsigned_apk="${1:?Pass the unsigned APK path}"
signed_apk="${2:?Pass the signed APK destination}"
keystore="${FLEXWEEK_ANDROID_KEYSTORE:?Set the keystore path}"
password_file="${FLEXWEEK_ANDROID_KEYSTORE_PASSWORD_FILE:?Set the private password file path}"
alias="${FLEXWEEK_ANDROID_KEY_ALIAS:-flexweek-release}"
signer="${ANDROID_HOME:?Source the Android environment first}/build-tools/36.0.0/apksigner"

"$signer" sign --ks "$keystore" --ks-key-alias "$alias" \
    --ks-pass "file:$password_file" \
    --out "$signed_apk" "$unsigned_apk"
"$signer" verify --print-certs "$signed_apk"
wc -c < "$signed_apk"
