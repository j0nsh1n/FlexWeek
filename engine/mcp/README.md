# flexweek-mcp

`flexweek-mcp` is a stdio MCP server for the FlexWeek account that is kept
signed in on this computer. An assistant can read that account's schedule and,
unless the server runs with `--read-only`, change it: add and plan homework, add
fixed time, change school and activity times. Every change saves a restore point
first, so it can be undone in one step. It does not open a port.

## Build

From the repository root:

```
cargo build --release --locked -p flexweek-mcp --manifest-path engine/Cargo.toml
```

The binary is `engine/target/release/flexweek-mcp` (without `--release`,
`engine/target/debug/flexweek-mcp`).

## Run

With no arguments the server uses the desktop's data folder:

- Linux: `$XDG_DATA_HOME/FlexWeek` when `XDG_DATA_HOME` is an absolute path,
  otherwise `~/.local/share/FlexWeek` (the folder the desktop's Qt picks)
- macOS: `~/Library/Application Support/FlexWeek`

The database is `<data folder>/flexweek.db`. The session file is
`<data folder>/signed-in/flexweek-<16 hex chars>.json`, the same name the
desktop writes for that database. The file has to be readable by its owner
only (mode `0600`). On Windows the program prints a refusal and exits.
A session file without its database is treated as signed out; the server
never creates a database.

The session is checked on every call. Starting the server and the read tools
only look at it; a write tool renews it, as the desktop does on each request,
so an assistant that only reads does not keep the student signed in.

```
flexweek-mcp --data-dir DIR [--database FILE] [--session-file FILE]
```

`--database` selects a database file. The session file name is then the hash
of that path, unless `--session-file` names the file directly.

`--read-only` lists and serves only the read tools. A call to a write tool is
answered with a JSON-RPC error and changes nothing. Use it for an assistant
that should see the schedule but never change it.

`--now` holds the clock at a UTC (`...Z`) or RFC 3339 offset timestamp, for
tests. An offset timestamp uses its own date and minute (for example,
`--now 2026-10-21T08:00:00+09:00`). Without it, the date and minute use the
computer's local clock.

stdout is newline-delimited JSON-RPC. The start line and one line per call
go to stderr. Those lines do not include the token, the username, a title,
or a path.

## Client

A student uses the helper packaged with FlexWeek, not a build from this folder.
In the Linux download it is started through the launcher with `--mcp`; every
argument after `--mcp` goes to the helper. For example, in a client's MCP config:

```json
{
  "mcpServers": {
    "flexweek": {
      "command": "/home/you/FlexWeek/FlexWeek",
      "args": ["--mcp"]
    }
  }
}
```

With the AppImage the command is the AppImage itself, with the same `--mcp`
argument. Add `"--read-only"` after `"--mcp"` for an assistant that may look but
never change anything. No other argument is needed when FlexWeek's data folder is
the default above. A developer may point `command` at a binary built here instead.

## Tools

Read tools (always served):

| Tool | What it returns |
|---|---|
| `whoami` | Who is signed in, when the session ends |
| `get_today` | One day (optional `date`): due soon, sessions, fixed blocks, next action, workload |
| `get_week` | One week (`week_start`, a Monday) with School and activities merged in, and its revision |
| `get_month` | One month (`month`, `YYYY-MM`): the grid, deadlines, overdue work |
| `list_homework` | Homework with planned and unplanned minutes (`week_start`, `include_completed`) |
| `list_routines` | Saved routines |
| `list_restore_points` | Restore points, newest first |

Write tools (not served with `--read-only`):

| Tool | What it changes |
|---|---|
| `add_homework` | New homework and one open session this week |
| `edit_homework` | Homework, with its sessions kept in step |
| `delete_homework` | Homework and its sessions (destructive) |
| `set_homework_done` | Homework done or not, and its sessions |
| `set_block_done` | One block on one day done or not |
| `plan_homework` | Runs FlexWeek's own planner, as Plan my homework does, for a week or one `day`; returns `placed` and `not_placed` (with the planner's reason) |
| `add_block` | Fixed time that is not homework on one or more `days`: `category` is `free` (a break or rest), `meals`, `extra` (an event or activity, the default), `exercise`, `sleep` or `class` |
| `edit_block` | Fixed time's title, start, end, days or category, for the series or one day (`scope: "occurrence"`, `day`) |
| `move_block` | A block to a day and time, as dragging it does |
| `skip_block_day` | Fixed time skipped on one day (a day off): it stays shown as missed and its time is free to plan |
| `delete_block` | A block, or one day of it (destructive) |
| `restore_point` | The whole schedule back to a restore point (destructive; it saves one of its own first) |

The rules are the app's: an end after its start, no new or moved start in the
past, fixed time may sit beside other blocks (the reply names one in `beside`),
and Plan never places homework before now or after it is due. School and Setup's
activities change in this week only, as in the app's block editor; `every_week`
on `edit_block` or `delete_block` changes them from this week on, as the app's
School hours and "This week and later" do. Taken out of this week alone, School
stays in it missed on its days, as in the app.

Each write takes an `operation_id` (8 to 80 characters): the same id with the
same arguments returns the first answer and changes nothing, and the same id with
other arguments is refused. Edits carry the revision they were read at; a stale
one returns `{"error": "conflict", "current_revision": N}` and changes nothing.

`set_homework_done` and `set_block_done` take an optional `expected_revision`
(the homework's revision, or the week's from `get_week`), checked the same way
when it is given.

Several writes can be sent at once without waiting for each answer. Each one
reads what it changes and saves it under one database lock, so changes to
different things all apply; only a change made against a revision that has
moved is refused.

While FlexWeek is open on this computer it shows a write within a few seconds,
without a restart. If the student has edits there that are not saved yet, they
are kept, and the week is marked as changed elsewhere until the student chooses
More > Reload this week.

### Undo

Before each change the helper saves the whole schedule as a restore point named
"Before assistant <tool> — <time>". `list_restore_points` shows them, and
`restore_point` with one's `id` brings the schedule back to how it was before
that change, in one step, the same way Restore in the app does. Restoring the
point made before an assistant's first change undoes everything it did after.
The restore saves a "Before restore" point first, so it can be undone too.
FlexWeek keeps 20 restore points; the assistant keeps at most 10 of its own, so
it never pushes out the ones the student made.
