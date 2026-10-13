#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
engine_dir="$repo_root/engine"
jni_libs="$repo_root/android/app/src/main/jniLibs"

export CARGO_NET_OFFLINE=true
cd "$engine_dir"
cargo ndk -t arm64-v8a -t x86_64 -o "$jni_libs" build --release -p flexweek-ffi

for abi in arm64-v8a x86_64; do
    abi_dir="$jni_libs/$abi"
    find "$abi_dir" -maxdepth 1 -type f ! -name libflexweek_ffi.so -delete
    count="$(find "$abi_dir" -maxdepth 1 -type f -name '*.so' | wc -l)"
    if [[ "$count" != 1 || ! -f "$abi_dir/libflexweek_ffi.so" ]]; then
        printf 'expected only libflexweek_ffi.so under %s\n' "$abi_dir" >&2
        exit 1
    fi
done
