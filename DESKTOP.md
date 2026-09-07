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
