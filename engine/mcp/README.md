# flexweek-mcp

`flexweek-mcp` is a stdio MCP server for the FlexWeek account that is kept
signed in on this computer. It reads that account's schedule. It does not
open a port.

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

Point the client's MCP config at the built binary. No arguments are required
when FlexWeek's data folder is the default above.

```json
{
  "mcpServers": {
    "flexweek": {
      "command": "/absolute/path/to/flexweek-mcp"
    }
  }
}
```

The read tools are `whoami`, `get_today`, `get_week`, `get_month`,
`list_homework`, `list_routines`, and `list_restore_points`.

The write tools are `add_homework`, `edit_homework`, `delete_homework`,
`set_homework_done`, `set_block_done`, `move_block` and `delete_block`. Each takes an
`operation_id` (8 to 80 characters): the same id with the same arguments returns the
first answer and changes nothing, and the same id with other arguments is refused.
Edits carry the revision they were read at; a stale one returns
`{"error": "conflict", "current_revision": N}` and changes nothing. School and
activities are changed in the app, not here.
