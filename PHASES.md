# FlexWeek phases

Owner: you (code). Partner: calendars, copy, testing, video.
Hard deadline: Monday, October 26, 2026, 9:00 a.m. PDT. **Submit Oct 25 evening.**

Do not start Phase N+1 until the exit test for Phase N is green, except as the kill list says.

---

## Phase 1 — Skeleton (Sep 6–12)

**You**

- [x] `backend/models.py` matches demo JSON
- [x] Slot helpers: 15-min grid, 6:00–23:00, `overlaps`
- [x] `GET /api/demos/alex` and `/jordan`
- [x] Week grid paints locked blocks; flexible list in the sidebar
- [x] `pytest` ≥10 tests on slot math

**Partner**

- [ ] Two anonymized real weeks (replace the seed JSON this week or next)
- [ ] One-sentence pitch in their own words

**Exit:** `uvicorn` shows both demos. `pytest` passes. No solver yet.

Code side of the exit is green (2026-09-06): partner calendars in the demo JSON, grid CSS tightened, logo in the topbar. Partner checkboxes still open.

---

## Phase 2 — Solver v1 (Sep 13–19)

**You**

- [ ] `solve(blocks) -> SolveTrace` in `backend/solver.py`
- [ ] Backtracking + MRV + forward checking
- [ ] 150 ms cap; never hang
- [ ] Fixtures: empty, packed, impossible, paper-due-tomorrow
- [ ] Debug panel: `solve_ms`, placed, unplaced

**Partner**

- [ ] Three break-it cases on paper, then in the app

**Exit:** Packed week solves or returns `NO_SLOT_LEFT`. Property: no overlaps; no flexible start after deadline.

---

## Phase 3 — Usable app (Sep 20–26)

**You**

- [ ] Add locked / add flexible forms
- [ ] `POST /api/solve`
- [ ] `localStorage` for last week; corrupt data resets to a demo
- [ ] Duration must be a multiple of 15 in the form and in Pydantic

**Partner**

- [ ] Build a week without you; 10-row bug list

**Exit:** Create → Solve → refresh → week still there. Skip drag-and-drop if it costs more than a day.

---

## Phase 4 — Must-ship (Sep 27–Oct 3)

**You**

- [ ] Priority (test > quiz > homework > reading)
- [ ] Energy windows (soft)
- [ ] Explain panel using partner sentences
- [ ] Click a move → highlight the block
- [ ] Test: last slot, test vs reading → `PRIORITY_PREEMPT`

**Partner**

- [ ] English for every reason code
- [ ] 5 classmates, 10 minutes, 3 quotes

**Exit:** Load demo → Solve → click unplaced → read the why. **Feature freeze Oct 3** (no new feature types).

---

## Phase 5 — Cascade + slack (Oct 4–10)

**Go / no-go Monday Oct 4.** If Phase 4 is red, polish only.

- [ ] “I missed this block” → re-solve → list diffs
- [ ] Slack hours + ok / tight / danger
- [ ] Sleep never stolen

**Exit:** Video beat works: miss → ripple → reasons.

---

## Phase 6 — Contest surface (Oct 11–17)

**Hard freeze Sunday Oct 11, 6:00 p.m.**

- [ ] Keyboard, contrast, reduced motion
- [ ] Public Render URL in README
- [ ] MIT license, both names
- [ ] AI disclosure if you used a copilot

**Exit:** A judge can clone, run, and understand the algorithm from README.

---

## Phase 7 — Submit (Oct 18–25)

- [ ] Bugs only
- [ ] 90–120s video (names in first 5 seconds, show the trace)
- [ ] CAC written answers
- [ ] Submit **Oct 25 evening**, not Oct 26 morning

---

## Kill list

| Behind after | Cut |
|---|---|
| Phase 2 | Energy (keep priority later) |
| Phase 3 | Drag-and-drop forever |
| Phase 4 | Phase 5 cascade + slack |
| Phase 5 | Grade-impact, TypeScript rewrite, SQL |
| Phase 6 | All code except crash fixes |

## Languages (locked)

Python (solver, tests, FastAPI) · JavaScript · HTML5 · CSS.
Optional later only: TypeScript, SQL. Never: Swift, Kotlin, Java, C++.

## Devices (locked)

Desktop browser first. Phone browser second. No App Store. No `.exe`.
