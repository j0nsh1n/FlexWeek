# Grok prompt — FlexWeek desktop delivery

Recommend a concrete desktop packaging approach for the next FlexWeek slice.
Do not redesign the UI or perform a security audit.

Context:
- The owner chose a separate desktop app plus web app, not a PWA.
- Provisional desktop targets: Windows and Linux, matching Daily Scheduler.
- FlexWeek runs Python 3.14, FastAPI, vanilla JavaScript/HTML/CSS, with no frontend
  framework or build step. The solver stays on the backend.
- Individual username/password accounts, SQLite-owned weeks, expiring opaque
  HttpOnly SameSite=Strict cookies, and same-origin write checks are implemented.
- The desktop app should share the hosted account backend and web UI. Full
  offline editing, local AI, Google Calendar OAuth and native mobile stores
  are outside this slice. Offline/connection failure needs a clear recovery UI.
- Daily Scheduler is Python/PySide6 and provides Nocturne/Slate themes, calendar
  navigation, drag create/move/resize, context menus, copy/paste and undo/redo.
  FlexWeek will port these behaviors incrementally; Qt widgets cannot be copied
  directly into browser code. Both projects are GPL-3.0.

Compare a minimal PySide6 QtWebEngine wrapper with pywebview. Verify current
Python 3.14 support and Windows/Linux packaging against official documentation;
include dated source links. Identify any hard blocker instead of assuming
compatibility. Consider a third approach only if both have a concrete blocker.

Return:
1. Recommended approach and the evidence supporting it.
2. Smallest useful first release: entrypoint, URL/environment configuration,
   login persistence, connection-error handling, external-link routing and
   Windows/Linux build artifacts.
3. How to retain one UI/account session model without exposing an unnecessary
   native JavaScript bridge or changing the hosted app's CSRF behavior.
4. A short implementation checklist and observable acceptance tests.
5. Unresolved product decisions, separated from implementation choices.

Keep it under 800 words. Do not claim to have inspected or tested the repository.
