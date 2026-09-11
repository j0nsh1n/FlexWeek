# FlexWeek

Places homework around school and sports, then explains why something moved.

Congressional App Challenge 2026. No chatbot. No product demo mode.

## Download

From the [latest GitHub Release](https://github.com/j0nsh1n/FlexWeek/releases/latest):

- **Download for Windows.** `FlexWeek-Windows-x64.zip`
- **Download for Linux.** `FlexWeek-Linux-x86_64.tar.gz`

Checksum files (`.sha256`) sit next to those downloads if you want to confirm the file is complete. You can ignore them and still open FlexWeek.

**Windows.** Extract the zip first. Running FlexWeek.exe from inside the zip does not work. Open FlexWeek.exe. If Windows shows "Windows protected your PC", choose More info, then Run anyway. FlexWeek is not code-signed yet; the warning is SmartScreen not recognizing a new publisher, not a virus finding.

**Linux.** Extract the archive and open the file named FlexWeek. You need a 64-bit Linux desktop (GNOME, KDE Plasma, Cinnamon, Xfce), glibc 2.38 or newer (Ubuntu 24.04, Linux Mint 22, Debian 13, Fedora 39 or newer), and working graphics (OpenGL or EGL). A remote or headless session without a display will not work. The X11 cursor helper (libxcb-cursor) is inside the download.

**Chromebooks.** Use the web version when it is online. It is not online yet. From this source tree you can run the web app locally (see below).

Open FlexWeek, choose Create account, and follow the short first-week setup (school hours, a sport, then homework). You can skip any step.

## Run from source

Requires Python 3.14.

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.app:app --reload
```

Open **http://127.0.0.1:8000**. The first screen is Create account; returning
users choose Log in. Usernames use 3–32 letters, numbers or underscores;
passwords use 12–128 characters. A new account opens a short setup for school
hours, one sport and the first homework, then runs Solve. You can skip it.

To add more, pick a type in the sidebar and drag on the calendar, or click for a
1-hour block. The dialog asks whether the item is a **Fixed time** (school,
practice: Solve never moves it) or **Flexible** (homework: Solve picks a free
time before it is due). Every save goes to your account; Solve previews placement
without replacing your entered blocks.

Theme starts on System, which follows your device's light or dark setting.
Choose Light or Dark from Theme to keep one. The choice is saved to your
account. If a save fails, keep the page open and use Retry save. A conflicting
save from another window offers a draft download and reload of the saved week.
Password recovery is planned for the later hardening phase.

Existing browser-only weeks can be explicitly imported after logging in. Import
replaces the account's current week after confirmation; invalid legacy data is
left untouched. Private account weeks are not stored in localStorage.

## Storage and hosting configuration

| Variable | Default | Purpose |
|---|---|---|
| `FLEXWEEK_DATABASE` | `var/flexweek.db` | SQLite account, session, week and theme storage |
| `FLEXWEEK_ORIGIN` | `http://127.0.0.1:8000` | Exact browser origin, including port |

For a different local port, set `FLEXWEEK_ORIGIN` to match. Non-local origins
require HTTPS. HTTPS deployments use Secure session cookies. A hosted release
needs a persistent database directory and backups; an ephemeral filesystem
loses accounts and schedules. Configure trusted reverse proxies explicitly so
client-address throttling sees the intended source. Full deployment, account
recovery, deletion/retention policy and security audits remain later work.

The database and its journals are gitignored. Back up the database with SQLite's
backup API or with the app stopped; protect backups as private account data.

## Checks

```bash
.venv/bin/python scripts/verify.py
```

This runs all frontend, backend and desktop source checks. For a web-only
environment, use `--web-only`; desktop is then explicitly unverified. See the
[coverage map and feature verification guide](docs/verification.md) for focused
checks and release limitations. Node is development-only, with no npm packages
or frontend build step.

## Progress

Phases 3 and 4 are complete: accounts, saved weeks and Daily Scheduler themes
are verified in the real desktop web engine. See the [roadmap](roadmap.md) for
the separate desktop app, calendar interaction port, later design work and
contest delivery. Windows/Linux are desktop targets. Windows packages are
built on GitHub Actions when a release is published; a Windows machine still
needs a person to extract the zip and click through SmartScreen.

A Linux desktop build exists: a PySide6 `QWebEngineView` window with the FastAPI
backend bundled inside it. It needs no separate server and no Python install.
Build it with `pip install -r requirements-desktop.txt` then
`./desktop/build_linux.sh`. Package the download with
`./desktop/package_linux.sh` to get `FlexWeek-Linux-x86_64.tar.gz` (and a
`.sha256`) containing README, icon, `.desktop` file and the app. Releases
attach that archive rather than committing `dist/`, because the bundled Qt
WebEngine library exceeds GitHub's per-file limit; see [DESKTOP.md](DESKTOP.md).
The paste-ready GitHub release text is in [docs/github-release.md](docs/github-release.md).
Set `FLEXWEEK_DESKTOP_ORIGIN` to point the window at a hosted deployment instead;
local and hosted accounts are separate, without automatic synchronization.

Windows packages are built on GitHub Actions when a release is published
(`desktop/build_windows.ps1`) and attached as `FlexWeek-Windows-x64.zip`.
ICU (`icuuc`/`icuin`) is part of Windows 10 1809+; the bundle check requires
those imports to be satisfied without copying Microsoft's DLLs. The saved
theme names `nocturne` and `slate` come from Daily Scheduler (the GPL-3.0
`Local-Schedule-Assistant` project); the hybrid frost colors replaced its
palette in September 2026. The Figtree typeface in `frontend/fonts/` is under
the SIL Open Font License (`Figtree-OFL.txt`). AI assistance was used in development,
including Codex and GLM-5.3 Flash test contribution; the runtime uses no AI
service.

The original Sep 6 contest brief (working title Reslot) is in
[docs/cac-build-plan.md](docs/cac-build-plan.md). The living schedule is the
[roadmap](roadmap.md).

Submit by Sunday, October 25, 2026, 8:00 p.m. PDT.

License: GPL-3.0. Contributor listing is pending completion before submission.
