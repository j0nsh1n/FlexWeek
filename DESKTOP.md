# FlexWeek desktop packaging recommendation

Date: 2026-09-07. Sources are official docs (links dated below). This is a
packaging choice, not a UI redesign or security audit.

## 1. Recommendation

Use a **minimal PySide6 `QWebEngineView` window** that loads the hosted FlexWeek
origin. Do not embed a second FastAPI process in v1.

**Evidence**

- Qt for Python’s compatibility matrix marks Python **3.14** as supported on
  PySide **6.10.x–6.13.x** (wiki retrieved 2026-08-24):
  https://wiki.qt.io/Qt_for_Python
- Windows and Linux are listed platforms; 32-bit is not.
- `QWebEngineView.load` / `setUrl`, `loadFinished(ok)`, and `createWindow` are
  documented for this wrapper (Qt for Python docs, 2026-08-19):
  https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineWidgets/QWebEngineView.html
- Official deploy path is `pyside6-deploy` (Nuitka) on Windows/Linux/macOS
  (2026-08-19):
  https://doc.qt.io/qtforpython-6/deployment/
- Qt WebEngine **static builds are not supported** (Qt 6.11.2 platform notes):
  https://doc.qt.io/qt-6/qtwebengine-platform-notes.html
  That is a packaging constraint (ship a directory of Qt/Chromium libs), not a
  Python 3.14 blocker.

**pywebview** is the alternative: native WebView2 on Windows, GTK/Qt on Linux,
`pip install pywebview` / `pywebview[gtk|qt|pyside6]`.
https://pywebview.flowrl.com/guide/installation.html

It is not the first choice here: current `pyproject.toml` has
`requires-python >= 3.8` but classifiers only through **3.13**. That is not a
stated “3.14 fails” blocker, but it is not an official 3.14 claim either.
Default `private_mode=True` also discards cookies unless the wrapper opts out
(https://pywebview.flowrl.com/api/). Linux still needs GTK+WebKit or a Qt
WebEngine stack. No third option is required; PySide6 has no 3.14 hard blocker.

PySide6 is LGPLv3/GPLv2/commercial (same wiki). A GPL-3.0 app may link LGPLv3
Qt. WebEngine onedir builds are large because they include Chromium.

## 2. Smallest useful first release

- **Entrypoint:** `desktop/main.py` — `QApplication`, persistent
  `QWebEngineProfile`, one `QWebEngineView`, load `FLEXWEEK_DESKTOP_ORIGIN`
  (fallback `FLEXWEEK_ORIGIN`, then `http://127.0.0.1:8000`).
- **URL/env:** exact origin including port, matching the web app’s origin check.
- **Login persistence:** profile `setPersistentCookiesPolicy(AllowPersistentCookies)`
  and a writable `setPersistentStoragePath` under the user config dir. SameSite
  Strict cookies stay first-party if the view’s URL is that origin.
- **Connection errors:** `loadFinished(False)` shows a native Retry page (Reload
  the origin). Do not invent offline editing.
- **External links:** reimplement `createWindow` so `target=_blank` / popups
  open with `QDesktopServices.openUrl` instead of a second web view.
- **Artifacts:** `pyside6-deploy desktop/main.py` → Windows `.exe` + Qt/WebEngine
  libs; Linux `.bin` + the same libs. Prefer onedir, not `--onefile`. Qt’s
  PyInstaller page still warns Qt 6 plugin copy is partial and `--onefile` is
  not viable without extra steps
  (https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html).

## 3. One UI / session model, no extra bridge

The desktop window is a browser tab pointed at the hosted app. Leave
`HttpOnly` / `SameSite=Strict` cookies and CSRF origin/header checks unchanged.
Do not enable Qt WebChannel, do not inject Python `js_api`, and do not read
cookies from native code. The page already owns login, save, and solve.

## 4. Checklist and acceptance tests

1. Window opens the configured origin at 1280×800.
2. Register/login, refresh, still signed in (persistent profile).
3. Unplug / bad origin → Retry UI; after recovery, draft still in the page.
4. Link with `target=_blank` opens the OS browser, not a second Qt window.
5. Sign-out in the page clears the session; a new login is another account.
6. Windows onedir and Linux onedir both start without a local Python install.

Observable: cookie file appears under the profile path after login; killing and
reopening the app restores the session until the seven-day cookie expiry.

## 5. Unresolved product decisions

- Production origin URL (local vs hosted) and whether the desktop build may
  ever target localhost.
- Windows WebEngine onedir size vs asking users to install WebView2 (that would
  be a pywebview revisit, not this slice).
- Code signing / SmartScreen and Linux package format (AppImage vs .deb).
- Whether a future slice bundles a local server; v1 should not.

---

## 6. Linux build — implemented 2026-09-07

The recommendation above is now built. Verified on this machine: PySide6 6.11.2
(`cp310-abi3` wheels, so the stable ABI covers Python 3.14.7), Nuitka 4.2.1,
patchelf 0.19.1, GCC 16.2.1.

```bash
pip install -r requirements-desktop.txt
./desktop/build_linux.sh          # -> dist/FlexWeek/FlexWeek
```

Point it at a server with `FLEXWEEK_DESKTOP_ORIGIN`, falling back to
`FLEXWEEK_ORIGIN`, then `http://127.0.0.1:8000`.

**Layout**

- `desktop/origin.py` — origin resolution and the same-origin test. No Qt
  imports, so it is unit-tested without the 1 GB dependency.
- `desktop/main.py` — `QApplication`, one persistent `QWebEngineProfile`, one
  `QWebEngineView`, the native retry panel, and the external-link handling.
- `desktop/build_linux.sh` — the build.

**Deviation from section 1:** Nuitka is invoked directly rather than through
`pyside6-deploy`. The wrapper rewrites its own `pysidedeploy.spec` with absolute
machine paths on every run, so a committed spec does not survive. `pyside6-deploy`
only shells out to `python -m nuitka` anyway; the script keeps the plugin list the
wrapper computed. `pysidedeploy.spec` is gitignored so running the wrapper by hand
does not dirty the tree.

**Artifact:** onedir, ~390 MB (Chromium), with a ~33 MB launcher binary. Not
`--onefile`, per section 2.

### Checklist status (section 4)

| # | Test | Status |
|---|---|---|
| 1 | Window opens the configured origin | Verified — page title `FlexWeek` |
| 2 | Login survives a restart | Verified — register in-window, kill, reopen: `/api/auth/me` returns the account; an empty profile returns 401 |
| 3 | Bad origin shows Retry | Verified — dead port switches to the native panel |
| 4 | `target=_blank` opens the OS browser | Real Qt link test emits one OS handoff and retains no hidden page; OS browser availability remains a manual check |
| 5 | Sign-out clears the session | Verified in real WebEngine: sign-out clears the grid, a second account starts empty, original account restores its week |
| 6 | Onedir starts with no Python installed | Verified on Linux — runs under `env -i` |
| 7 | Runs with no separate server (added 2026-09-07) | Verified — the binary itself holds the listening socket on 127.0.0.1, serves `/api/health` 200 and `<title>FlexWeek</title>`, and releases the port on exit |
| 8 | Writes nothing into its own bundle | Verified — database and cookies land in the user data dir; no file under `dist/FlexWeek/` changed during a run |

Windows is untouched. Only `build_linux.sh` and the Linux checks exist.

---

## 7. Bundled server — scope change 2026-09-07

**This supersedes section 1's "Do not embed a second FastAPI process in v1" and
settles the last open question in section 5.** The owner asked for an executable
that does not depend on a server being up. Section 1's reasoning still holds for
a *second* process; what ships instead is the same FastAPI app running in a
background thread of the one desktop process.

How it works:

- `desktop/server.py` binds a loopback socket on an ephemeral port **before**
  the app is built, because the backend pins its CSRF origin check and
  `TrustedHostMiddleware` to one exact origin — the port has to be known first.
  uvicorn is then handed the already-bound socket, so there is no
  pick-a-port-and-hope race.
- uvicorn runs with `loop="asyncio"` and `http="h11"`: uvloop and httptools are
  optional native extras and there is no reason to depend on them surviving
  being frozen.
- The SQLite database lives next to the browser profile under the user data
  directory, never inside the read-only application bundle.
- `frontend/` ships as bundle data, because `backend/app.py` serves it from
  `<bundle>/frontend`.
- The window closing stops the server via `aboutToQuit`.

Setting `FLEXWEEK_DESKTOP_ORIGIN` (or `FLEXWEEK_ORIGIN`) still points the window
at a hosted deployment and skips the bundled server entirely. An invalid value
is an error rather than a silent fall back to local, so a typo in a hosted
deployment cannot quietly start serving a different, empty database.

Security posture is unchanged: same origin checks, same CSRF header, same
cookies. The listener is bound to `127.0.0.1`, so it is not reachable from the
network.

## 8. Desktop completion checks — 2026-09-07

The account flow is now exercised automatically by `desktop/tests/test_webengine.py`
in real Qt WebEngine processes, using temporary profiles and databases. It covers
registration, editor save, Solve, reload, theme persistence, sign-out, second-account
isolation, phone/desktop widths, external links and offline draft downloads.
PySide6 is optional for the backend test environment; these tests skip explicitly
when desktop dependencies are absent. The test processes keep the Chromium sandbox
enabled and use offscreen rendering with GPU acceleration disabled.

Two wrapper defects were reproduced and fixed: new-window links retained hidden
pages after handoff, and requested downloads had no native handler. New windows
now use Qt's `newWindowRequested` signal without creating another page; only
HTTP(S) destinations are handed to the system browser. Draft downloads use a
native Save dialog and cancel when no destination is selected.

Qt API references:
- https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEnginePage.html#PySide6.QtWebEngineCore.QWebEnginePage.newWindowRequested
- https://doc.qt.io/qtforpython-6/PySide6/QtWebEngineCore/QWebEngineDownloadRequest.html

The Linux build now compiles in a unique staging directory, excludes application
test packages, and preserves the previous successful artifact under a dated
`.previous.*` path before publishing a new one. `FLEXWEEK_BUILD_OUTPUT` can select
a different destination and `FLEXWEEK_BUILD_JOBS` defaults to four compiler jobs.
Build intermediates remain available for diagnosis; existing build folders are
not deleted.

## 9. Windows build preparation — 2026-09-07

GLM-5.3 Flash drafted `desktop/build_windows.ps1` and made `patchelf` a Linux-only
requirement. The main agent reviewed the draft and tightened staging, compiler
selection, environment restoration and publication checks. The script uses Python 3.14, Nuitka and PySide6 to create a standalone
Windows directory with the backend and frontend included. It stages builds and
refuses to overwrite `dist/FlexWeek-Windows`.

From a Windows PowerShell prompt in the repository:

```powershell
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt -r requirements-desktop.txt
.\desktop\build_windows.ps1
.\dist\FlexWeek-Windows\FlexWeek.exe
```

A compatible Visual Studio C++ build toolchain is required. No Windows host or
PowerShell interpreter was available in this session, so neither a Windows
executable nor PowerShell execution has been verified. The remaining Windows
check is build → open → register → save → restart → sign out, plus external-link
and draft-download checks on a machine without the development virtualenv.

The default self-contained desktop mode stores accounts locally. Hosted mode
(`FLEXWEEK_DESKTOP_ORIGIN`) uses that deployment's accounts and weeks in both the
desktop app and browser. There is no automatic local-to-hosted synchronization.

### Windows release build — CI, same method as Daily Scheduler (2026-09-09)

Nuitka cannot cross-compile: the Windows package is built on a GitHub Actions
`windows-latest` runner, mirroring Local-Schedule-Assistant's
`release-windows.yml`. `.github/workflows/release-windows.yml` fires when a
release is published (or by hand against an existing tag), installs both
requirements files into a fresh Python 3.14, runs `desktop/build_windows.ps1`
(MSVC is preinstalled on the runner), smoke-checks the freeze layout
(`FlexWeek.exe`, `frontend/index.html`, `QtWebEngineCore.dll`), zips
`dist\FlexWeek-Windows` to `FlexWeek-win64.zip` with a `.sha256`, and uploads
both to the release. The first CI run is also the first real execution of
`build_windows.ps1`; if it fails, the workflow log is the diagnosis.

---

## 8. Releasing the Linux build

The built app is **not** committed. `dist/` is gitignored, and it has to stay
that way: `libQt6WebEngineCore.so.6` alone is 194 MB against GitHub's hard
100 MB per-file limit, so a plain `git add dist/` produces a repository that
cannot be pushed. It would also take `.git` from under a megabyte to over half
a gigabyte, permanently, and every judge cloning the repo would pay for it.

Distribute it as a release asset instead. GitHub Releases allow 2 GB per file.

```bash
./desktop/build_linux.sh                       # -> dist/FlexWeek/
cd dist && tar -czf FlexWeek-linux-x86_64-$(date +%Y%m%d).tar.gz FlexWeek
sha256sum FlexWeek-linux-x86_64-*.tar.gz | tee FlexWeek-linux-x86_64-*.tar.gz.sha256
```

528 MB on disk compresses to about 205 MB. Attach the tarball and its `.sha256`
to a GitHub Release; users extract it and run `FlexWeek/FlexWeek`, with no
Python and no separate server.

Verify a release candidate by extracting it somewhere clean and starting it with
an empty profile, rather than trusting the tree it was built from:

```bash
tar -xzf FlexWeek-linux-x86_64-*.tar.gz -C /tmp/check
XDG_DATA_HOME=/tmp/check-profile /tmp/check/FlexWeek/FlexWeek
```

**Housekeeping.** `build_linux.sh` preserves each previous build as
`dist/FlexWeek.previous.<timestamp>` and never prunes them, so `dist/` grows by
about 528 MB per rebuild. Delete the ones you do not need.

## Reminders (Phase 5)

Start reminders ship in the shared web UI (preferences, in-app toast, Notification
API while the window is open). Phase 7 added the tray presenter described below.

## Window, tray and quitting (2026-09-10)

- Launching FlexWeek shows its window. If it is already running, the existing
  window comes forward instead (see the last point).
- When the desktop has a system tray, FlexWeek puts its logo there. Closing the
  window hides it to the tray, so reminders and alarms keep firing. The first
  close shows a tray message that says so.
- Click the tray icon, or choose **Open FlexWeek** from its menu, to bring the
  window back. Choose **Quit** from the tray menu to stop FlexWeek.
- Without a tray, or when the tray icon cannot load, closing the window quits.
  FlexWeek never keeps running with no window and no tray icon.
- Launching FlexWeek again while it runs brings the existing window forward
  instead of starting a second copy on the same database. One copy runs per
  user data directory.

The tray icon is loaded from `frontend/logo.png` next to the bundled backend.
Before this fix the path was taken from `desktop/main.py`. Nuitka places that file
at the bundle root, so the path pointed one directory above the bundle. Qt logged
`QSystemTrayIcon::setVisible: No Icon set`, the tray entry was invisible, and a
closed window left the process running with no visible way back.
