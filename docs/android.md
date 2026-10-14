# Building the Android app

The phone app lives in `android/`. It is a Kotlin and Jetpack Compose app, package `com.flexweek.app`. It needs Android 8.0 (API 26) or newer and targets API 36. It builds for `arm64-v8a` and `x86_64`. Facts come from `android/` and `scripts/android/build-rust.sh` on `release/1.0.0`.

## What you need

- **JDK 25.** On Fedora: `sudo dnf install java-25-openjdk-devel`. Set `JAVA_HOME` to it, for example `export JAVA_HOME=/usr/lib/jvm/java-25-openjdk`. The Java code is compiled to Java 17 bytecode (`compileOptions` in `android/app/build.gradle.kts`). The Fedora package name has not been checked on a clean machine.
- **Android SDK** with platform 36, build-tools and platform-tools. Put it in `~/Android/Sdk`, or set `ANDROID_HOME` to where it is.
- **An Android NDK**, for the Rust core that Gradle builds (below). The machine that built 1.0.0 used NDK 30.0.16248370; Gradle does not pin a version.
- **Gradle does not need installing.** The project includes the wrapper (`./gradlew`, Gradle 9.8.1). Android Gradle Plugin 9.4.1 and Kotlin 2.4.21 are pinned in `android/gradle/libs.versions.toml`.
- **An emulator or a phone** only for the screenshot scripts and for real-device checks. Unit tests need neither.

```bash
export JAVA_HOME=/usr/lib/jvm/java-25-openjdk
export ANDROID_HOME="$HOME/Android/Sdk"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$PATH"
```

## Build and test

Run these from `android/`:

```bash
./gradlew testDebugUnitTest      # JVM unit tests, no device needed
./gradlew assembleDebug          # writes app/build/outputs/apk/debug/app-debug.apk
```

The unit tests cover the Pair screen's code, Today, reminders, the reminder scheduler, the v2 screens (Add homework, Plan, Running late), the foreground sync, the phone's JSON over the Rust core, and core startup.

Build variants:

| Variant | `BuildConfig.V2_ENABLED` | Notes |
|---|---|---|
| debug | true | The v2 screens (Add homework, Plan, Running late, Week) are on. |
| release | false | The v2 screens are hidden. Minification is off. 1.0.0 ships this variant. |

Release APKs are signed with `scripts/android/sign-release.sh`, which needs `FLEXWEEK_ANDROID_KEYSTORE`, `FLEXWEEK_ANDROID_KEYSTORE_PASSWORD_FILE` and `ANDROID_HOME` in the environment, and signs with the `flexweek-release` key alias unless another is set.

## The Rust core

The app calls the Rust core through UniFFI. Gradle builds it: every build task (including `assembleDebug`) runs `scripts/android/build-rust.sh` first, wired through `preBuild` in `android/app/build.gradle.kts`. The script needs `cargo-ndk` and the Rust targets `aarch64-linux-android` and `x86_64-linux-android`, plus the NDK above. `cargo install cargo-ndk` and `rustup target add aarch64-linux-android x86_64-linux-android` are the usual install commands; they have not been run on the machine that wrote this page. The script puts `libflexweek_ffi.so` into `android/app/src/main/jniLibs/`, and the app loads that file when it starts. Without it the app does not start.

## Screenshots

`android/capture-shots.sh` and `android/capture-v2-shots.sh` take screenshots from a running emulator with `adb`. Each script writes its PNG files to a folder set by `OUT` near the top of the script. Both scripts default `OUT` to a lane folder outside this repository, so set `OUT` to a folder of your own before you run either script.

## Permissions

The app asks for these in `AndroidManifest.xml`:

- `INTERNET`: needed for sync.
- `POST_NOTIFICATIONS`: for reminders (asked for in Settings).
- `SCHEDULE_EXACT_ALARM`: for exact reminder times. Without it, reminders fire within about 5 minutes.
- `RECEIVE_BOOT_COMPLETED`: to set reminders again after a restart.

Backups are off (`allowBackup="false"`).

## Known gaps

- The phone cannot scan the pairing QR code yet; pairing is by typing the 8-digit code.
- Reminder timing has been checked on an emulator only. Pairing and two-way sync have been checked on a real phone (2026-10-13, over mobile data through the n0 relay).
