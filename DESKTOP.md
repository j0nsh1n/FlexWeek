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
| 4 | `target=_blank` opens the OS browser | Code in place; not yet exercised against a real link |
| 5 | Sign-out clears the session | Not yet tested |
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
