#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
cd "$repo_root/engine"
export CARGO_NET_OFFLINE=true
cargo build --release -p flexweek-ffi -p uniffi-bindgen
target_dir="$(cargo metadata --offline --format-version 1 --no-deps | python3 -c 'import json,sys; print(json.load(sys.stdin)["target_directory"])')"
"$target_dir/release/uniffi-bindgen" generate \
    --library "$target_dir/release/libflexweek_ffi.so" --language kotlin \
    --no-format --out-dir "$repo_root/android/app/build/generated/uniffi"
