# roadmap.md — FlexWeek

Phases, their complete-when conditions and status. Finished phases are removed; their history is in this file's git
history and in `CHANGELOG.md` (pruned 2026-11-06: Phase 8, 1.1.1, the 0.18.x series, 0.18.5 and the 1.0.0 running
list, all shipped).

## Where things stand (2026-11-06)
- v1.2.0 is the latest release. Developer build 1.2.0.202611061702 (from main 33fe5eef) carries FIX-SPEC 1.3 and the
  J lanes (J21 Material Week zoom, J22 Material Day hours, J23 Month study fill, J25 Look preview side by side).
- Next: R1 (unblock releases); R3 (the testing rebuild) starts on Jonathan's go.

## After FIX-SPEC 1.3 (planned 2026-11-06)
FIX-SPEC 1.3 and the J lanes (J21 Week zoom, J22 Day hours, J23 Month study fill, J25 Look preview side by side)
are on main (PRs #67-#83). In order:

### R1 — Unblock releases
- Windows packaging: `opengl32sw.dll imports imagehlp.dll` fails the Windows release job (since Nov 4). Fixed on
  `fix/r1-release-unblock`: `imagehlp.dll` joins the system DLL list, and the Windows bundle now drops Qt's web modules
  the way Linux does (the next step failed on them). A by-hand run of the release workflow on that branch built,
  smoke-tested and made the installers on both Windows and Linux (run 42344994884, 2026-11-07). Open until it is
  merged and a tagged release builds.
- The local Nuitka build on Fedora drops the PySide6 libraries. Not reproduced (2026-11-07): a fresh venv from the
  requirements files builds a bundle with 0 check problems; the old failure most likely came from a symlinked `.venv`
  in a detached worktree (unproven). The working steps are in the R1 PR description.
- spec.md catch-up (Jonathan approves): CI jobs (engine wheel once, sharded mutations, rig matrix, no ffmpeg in
  rigs), the developer channel keeping the previous build, the "Material 3" switch label (FIX-SPEC said "Back to
  Material"), reason and notice wording. Proposal with exact text written 2026-11-07; waiting on Jonathan's approval.
- Developer builds: the commit in the release title and the kept copy's tag (the number stays for ordering). Done
  (PRs #84, #86).
- Complete when: a stable release builds on every platform and spec.md matches CI.
- Status: [ ] open.

### R2 — Correctness
- Two quick settings saves can overwrite each other (save_preferences).
- The phone does not receive same-day `notices`.
- Material memory growth (1.9 GB after 49 min on the tarball): measure, then fix or close.
- The autostart entry is only rewritten when the switch changes; no check at startup.
- Check and close or fix: the Undo notice 6 s against the spec's 10 s; planner spread around held pieces and
  grouping that ignores "one piece".
- Complete when: each has a test that failed first, or is closed with a reason.
- Status: [ ] open.

### R3 — Testing structure (rebuild; rules in spec.md, Validation & Tooling, "Testing structure", approved 2026-11-06)
Jonathan's decisions 2026-11-06: behaviour in code, looks by pictures and video, a light app plus a small end-to-end
set, CI as the gate, Rust tools in fwtest. Draft: `~/.flexweek-ui-harness/scratch/testing-revision/`.
- R3.1 Foundations: the shared fake clock (a test reading the real clock fails), clean look file and settings per
  test, one wait helper, the light app with seeded data. Complete when: Week's existing tests pass on them unchanged
  in behaviour, at the same or lower run time.
- R3.2 Week first: Week's behaviour tests regrouped and rewritten on the light app, its visual checks removed from
  code, its logic tests moved to engine tests, its mutation specs pointed at the new tests. Complete when: the old
  Week files are deleted and every Week mutation is still caught.
- R3.3 Pictures and video: fwtest's picture renderer, comparer and review page (main vs pull request, touched screens
  only), the rig's Widgets-and-Material flows with frame strips, CI keeping them until merge. Complete when: a pull
  request touching Week shows its changed pictures and clips on the review page and Kimi's annotations.
- R3.4 The other areas, one pull request each (Day, Month, My day, Focus, Settings, sheets, setup, account, sync,
  updater, planner). Complete when: no test file is named after a PR or audit and none reads the real clock.
- R3.5 Test selection and the flaky log in fwtest; CI as the gate; spec.md and fwtest's contract updated. Complete
  when: a local run picks only the touched area and CI runs everything.
- Status: [ ] approved 2026-11-06. R3.1 built 2026-11-07 on `test/r3-1-foundations`: the 65 Week files pass on the
  one clock, a clean computer per test, the shared wait helper and the light app, in 898 s of test time against
  main's 1,193 s; done when its pull request merges. Left for R3.2: Week's fixed waits for animations (drag results,
  hours zoom, hours hand, Material week, bare end times), its focus tests' own session clock (`logic_support`), and
  the module-wide Material windows. Left for R3.4: `test_layouts_window`'s overdue month card holds Saturday on the
  session only (one shared clock keeps the Unfinished card shut there; not yet understood).

### R4 — Look and feel (Jonathan's calls)
- Material Week: move an existing block by dragging (decide).
- Retro ignores Surface fine-tuning.
- Look preview at 1280 px gets about 52% (two Look tiles come first): keep or change.
- A real-screen check of J21, J22, J23 and J25.
- Complete when: each is built, closed or decided.
- Status: [ ] open.

### R5 — Bigger work (needs scope from Jonathan)
- The setup rebuild and day-to-day changes (Nov 3), the power-user vs everyday settings split, the Material 3
  style option.
- Status: [ ] waiting on scope.

## Carried over (open items from older lists; triage with Jonathan)
Full wording is in this file's git history (before 2026-11-06).

### From earlier plans
- Student trials (first use, several assignments, an impossible workload, a
  missed session, next-week reuse, recovery from an edit) and the task-time
  comparison against the first UI. Year view stays optional.
- Looks live on this computer, not on the account. The account fields for
  them (Amendment A of `docs/stage8-appearance-contract.md`) were never
  approved; whether looks should follow the account is an open decision.
- A Test or Preview of a reminder from the desktop tray was planned in the
  comfort stage; it is not in the native Settings. Confirm it was dropped on
  purpose, or add it.

### Decisions left from 0.18.1
- Typed dates: a date typed without a year means its next occurrence; confirm.
- Edit homework has two placement buttons ("Choose a time…" and "Let FlexWeek place it"); keep both or merge.
- The Delete key deletes the focused block at once (with Undo); keep or ask first.
- Drag step: clicks, the free-time menu and new blocks snap to 15 minutes while drags follow the 5/15 setting.
- Blocks that share a time: the arrow keys reach only the first; add a way to the others.
- The amber conflict row keeps its light fill in dark looks.
- The Running late notice keeps its 420 px maximum width.
- Setup's First homework page has no Save on the date.
- `hypothesis` is used by no test since the differential tests went; remove the dependency or use it.
- About 100 cases the deleted differential tests pinned have no test now (part of R3).
- Wording proposed for spec.md: reminders and Spotify links, the 5-minute reminder lead, "No homework after" choices.

### From the 1.0.0 list
- R11: Day / Week / Month / My day as one keyboard radio group (patch `R11-for-1.0.0.patch`; Month stopped fitting
  1024x640 after two tries).
- 1b-R: overdue and carried-over homework (patches in `1bR-for-1.0.0/`; its gate hung four times).
- The 0.19.1 handoff's Next patch N1-N14 and its wording items from T-W3 on.
- QA leftovers: Running late also places homework that had no time (product call); stale outlines after Undo of
  Running late and after Plan; Month opening scrolled past its first row.
- Standing design decisions: J8 Timeline's draggable fold, J10 Clay's shared scroll.
- Tooling: fwtest's hidden session inherits the caller's environment, so a rig started from a Codex agent dies for want
  of XDG_RUNTIME_DIR; the rig can inherit another run's look; a play's `text: large` is ignored with the empty seed.

### From the 1.1 and 1.2 work
- Static audit (2026-11-03): F1, the cold Advanced Month preview has no data; W3, Bento's headers drift up to 49 px
  at 1024 px, Large text, Saturday as today. Both paused at the debugging limits, waiting on Jonathan.
- MCP track C: Plan, Running late and explain tools, routines and restore; then the app moves to the Rust views and
  write door so nothing is written twice. Duplicates until then: Python validators and homework-edit rules in
  `backend/` and `desktop/`, and the focus phase advance in `controller.py` beside the phone's.
- Phone screens not built: full-screen focus with breaks (8 A), Month (6 B), Day (7 A), Week C with drag (plans in
  `~/.flexweek-ui-harness/scratch/android-1.1/`).
- Waiting on Jonathan: what shrinks on My day and One thing at 1024x640 Large; a device check of the phone updater.

## Later
- Left for after 1.0.0: a camera scan of the pairing code, a restore copy of
  the phone-link key, the v2 phone screens (Add homework, Plan, Running late,
  Week) in release builds, a same-Wi-Fi sync check on a real phone, and a
  CI-built APK.
- Simple assignment list or ICS file import. Not live Canvas, Blackboard or
  Google Classroom OAuth, and not syllabus-photo ML.
- Stronger deadline-cluster insight on top of the slack badges, without
  mental-health or IEP product claims.
- Rejected: syllabus OCR, LLM auto-reschedule chat, LMS API bridges,
  offline-first AI mobile shell.
