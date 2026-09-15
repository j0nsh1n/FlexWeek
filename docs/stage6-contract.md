# Contract: Stage 6 — make account access and delivery dependable

Status: proposed. Claude owns the browser/desktop frontend. Grok owns
persistence, recovery, deletion, storage status and the authenticated transfer
API. Both clients continue to use the same HTML, CSS and JavaScript frontend.

This contract is based on `feat/stage5-comfort-frontend` at `38817ae`.

GLM is not available in this harness, so this file was written with the
backend slice rather than by a separate contract pass.

## Goal

A student knows which account and which database they are using, can recover
access without email, can change or delete that account, and can move a week
from a local database onto a hosted account after a preview. The same hosted
login works in the browser and the desktop app. Automatic bidirectional or
offline sync is out of scope.

## Owner decisions (proposed defaults)

1. Recovery uses **one-time codes**, not email. Local SQLite has no mailbox, and
   hosted students are the same population. Registering returns eight codes
   once. The server stores hashes only.
2. A code is `xxxx-xxxx-xxxx-xxxx` lowercase hex. Hyphens are optional on
   recover. Using a code sets the new password, drops every session, and signs
   the student in. The same login throttle applies (10 per username / 30 per IP
   each five minutes). Wrong username and wrong code share one 401 sentence so
   the response does not say whether the username exists.
3. Signed-in students can **replace** unused codes by sending the current
   password. That invalidates leftover codes. There is no way to read codes
   again. `GET /api/auth/recovery-status` returns how many unused hashes remain.
4. **Change password** needs the current password. It rotates this session and
   drops every other session. The new password must differ from the current
   one.
5. **Delete account** needs the current password. It removes the user and every
   row keyed by that `user_id`. The username may be registered again. Other
   accounts are untouched.
6. `GET /api/storage-info` keeps the Stage 3 `mode` and `label` values and adds
   `username`, the public `origin`, and `transfer_limit_bytes` (262144). It
   never returns a filesystem path.
7. **Local-to-hosted transfer** is an authenticated export on the source and a
   previewed import on the destination. The snapshot is format 3: weeks,
   assignments, preferences and routines. Restore points, sessions, recovery
   codes and the password stay behind. Import replaces the destination account
   after taking a Stage 3 restore point of its weeks and assignments.
   Preferences and routines are not in that restore point (Stage 3 snapshot
   rule). The snapshot username is a label. It does not have to match the
   hosted username and does not claim another account. Export and import are
   bounded by the same 256 KiB write cap, measured on the import apply
   envelope, not by a separate week-count cap.
8. Export and other password-gated account writes use the current password so a
   stolen session cookie is not enough to dump or destroy the account.
9. Desktop hosted mode already follows `FLEXWEEK_DESKTOP_ORIGIN`. This slice
   does not change packaging. Two sessions of the same hosted user see the same
   weeks and hit the existing revision conflict.

## 1. Recovery codes

`POST /api/auth/register` still returns `id` and `username`, and also:

```json
{
  "id": 1,
  "username": "alice",
  "recovery_codes": [
    "a1b2-c3d4-e5f6-7890",
    "1111-2222-3333-4444",
    "aaaa-bbbb-cccc-dddd",
    "0123-4567-89ab-cdef",
    "fedc-ba98-7654-3210",
    "9999-8888-7777-6666",
    "abcd-ef01-2345-6789",
    "dead-beef-0000-1111"
  ]
}
```

Login is unchanged. Existing accounts that predate this table have zero codes
until they regenerate.

`POST /api/auth/recover` is unauthenticated, CSRF-protected and throttled:

```json
{"username": "alice", "code": "a1b2-c3d4-e5f6-7890", "password": "new-password-12"}
```

Success is 200 with `{id, username}` and a new session cookie. A used code
cannot be reused. 401 detail is `Incorrect username or recovery code`.

`POST /api/auth/recovery-codes` is authenticated and needs `{password}`.
Response is `{recovery_codes, remaining}` with eight new codes. `remaining` is
8.

`GET /api/auth/recovery-status` is authenticated and returns `{remaining}`.

## 2. Password change and deletion

`POST /api/auth/password`:

```json
{"current_password": "a-long-test-password", "new_password": "replacement-pw-1"}
```

401 `Incorrect password` when the current password is wrong. 422 when the two
passwords match. Success returns `{id, username}` and a new cookie.

`DELETE /api/auth/account` with `{password}` returns 204 and clears the cookie.
Later reads for that user are 401. Assignment and week ids from that account
are 404 for everyone, including a newly registered student who reused the
username.

## 3. Storage status

Authenticated `GET /api/storage-info`:

Loopback (`127.0.0.1`, `localhost`, `testserver`):

```json
{
  "mode": "local",
  "label": "On this device",
  "username": "alice",
  "origin": "http://testserver",
  "transfer_limit_bytes": 262144
}
```

Any other public origin:

```json
{
  "mode": "hosted",
  "label": "On your FlexWeek server",
  "username": "alice",
  "origin": "https://flexweek.example",
  "transfer_limit_bytes": 262144
}
```

`origin` is the process public origin, with no path. It is not a database file.
`transfer_limit_bytes` is the same 256 KiB write cap used by every other POST
(`/api/account-import` included).

## 4. Account transfer

`POST /api/account-export` with `{password}` returns:

```json
{
  "format": 3,
  "exported_at": "2026-09-14T22:00",
  "username": "alice",
  "weeks": [],
  "assignments": [],
  "preferences": {"theme": "system", "reminders_enabled": false},
  "routines": []
}
```

Preferences match GET `/api/preferences` (defaults omitted). Each routine
matches GET `/api/routines` (including `created_at` and `updated_at`). Weeks
and assignments match a Stage 3 restore snapshot.

`POST /api/account-import/preview`:

```json
{"snapshot": { "...format 3..." }}
```

Response:

```json
{
  "state_token": "hex",
  "source_username": "alice",
  "changes": {
    "weeks": {"added": [], "changed": [], "removed": []},
    "assignments": {"added": [], "changed": [], "removed": []},
    "routines": {"added": [], "changed": [], "removed": []},
    "preferences_changed": false
  }
}
```

`POST /api/account-import` with `{snapshot, state_token, operation_id}` applies
in one transaction: Stage 3 restore point of current weeks and assignments,
then replace weeks, assignments, preferences and routines. Stale token is 409
`This preview is out of date. Refresh it before importing.` A retried
`operation_id` returns the first result. Hostile snapshots are 422
(`extra=forbid`, assignment ids must be in the snapshot, week starts unique,
counts capped at the existing assignment and routine limits). Import never
writes recovery codes or sessions for another user.

Export and import share the 256 KiB write cap. Export measures the compact JSON
of `{snapshot, state_token, operation_id}` with a 64-character token and an
80-character operation id, and returns 413
`This account is larger than the 256 KiB transfer limit.` when that envelope
would not fit an import apply. Pretty-printed files may be larger than 256 KiB;
the parsed snapshot still has to fit that envelope. Week count is not a
separate transfer cap. A history with more than 400 small weeks can export
when it still fits.

## Out of scope

- Recovery, transfer, storage-status and delete UI (Claude).
- Email, SMS, magic links, OAuth, or automatic local/hosted sync.
- Changing Stage 3 restore-point contents to include preferences or routines.
- Hosted Render deployment, Windows installers, Linux packaging, Safari and
  iPhone checks, accessibility review, Qt shell changes.
- Spec.md edits until the owner approves this contract.

## Verification (backend)

- Register returns eight hyphenated hex codes; hashes in SQLite are not those
  strings; login JSON still has only `id` and `username`.
- Recover with a code signs in with the new password; the same code then 401s;
  unknown username 401s with the same detail; eleven failures 429.
- Regenerating codes invalidates a leftover code. Recovery-status counts drop
  after one successful recover.
- Change password keeps this client signed in and 401s a copied session cookie.
  Delete removes weeks, assignments, prefs, routines, restore points, sessions
  and codes; a second account's rows remain; the username can register again.
- Storage-info on loopback and on `https://flexweek.example` includes username
  and origin; unauthenticated GET is 401; the JSON never contains a path
  separator from the database file.
- Export without the password is 401. Import preview then apply copies weeks,
  assignments, prefs and routines onto a hosted account. A third account cannot
  GET those assignment ids. A stale token 409s. CSRF without
  `X-FlexWeek-Request` is 403 on the new POSTs and DELETE.
- Export of an account whose import apply envelope exceeds 256 KiB is 413 with
  the transfer-limit sentence. More than 400 small weeks still export when they
  fit.
- Two sessions of one hosted user see the same saved week; a stale revision
  PUT is 409.
- `.venv/bin/python scripts/verify.py --web-only` from this worktree.
