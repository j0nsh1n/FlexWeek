# Handoff: refine the 0.15 plan (ChatGPT)

You have this repository. Read, in this order:

1. `docs/0.15/plan-report.md`, the plan to refine.
2. `docs/0.15/architecture.md`, the shape of the shared drag engine, with its alternatives and the
   findings a review already raised.
3. `desktop/native/hours/`, the engine as built so far: `geometry.py`, `hand.py`, `canvas.py`,
   `chips.py`, `classic.py`.
4. `scripts/rig/drive.py` and `scripts/rig/hidden_session.py`, the real-pointer test rig, and its
   scenario list near the bottom of `drive.py`.
5. `docs/0.15/mockup/index.html`, the clickable mock-up of every concept. Open it in a browser
   (`python -m http.server` in that folder) or read its `CONCEPTS` and `SURFACES` tables.

Branch `feat/0.15-tabs`, on top of `main` at the 0.14.3 release. The last commit is a checkpoint:
Today's app runs on the new engine and passes the rig, and 15 older tests still read the retired
week canvas and Day list.

Refine the plan. Specifically:

1. Sequencing. Is the unit order right? What moves earlier because other work depends on it, or
   because it carries the most risk?
2. Scope. What would you cut from 0.15 or push to 0.15.1 to ship sooner, without losing what the
   owner asked for, which is dragging that works like Daily Scheduler in every design?
3. Acceptance. For each unit, is "done" defined tightly enough? Give concrete acceptance criteria
   where it is vague, in the shape the rig can check.
4. Testing. Which scenarios is the rig missing? Name cases where every scenario could pass while a
   student still has a bad time.
5. Risks. Which risk is under-rated, and what would you do about it?
6. Answer each open question at the end of the report with a recommendation.

Treat "What the owner decided" as fixed. Do not change code in this pass.

Write your revised plan to `docs/0.15/plan-refined.md`, keeping the same section order, and end it
with "Changes from the first plan", a short list of what you changed and why. Commit it on a branch
of your own (`chatgpt/0-15-plan`); do not push, do not open a pull request.
