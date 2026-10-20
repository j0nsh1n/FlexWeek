# flexweek-mcp

`flexweek-mcp` is a stdio MCP server for the FlexWeek account that is kept
signed in on this computer. It reads that account's schedule. It does not
open a port.

## Build

From the repository root:

```
cargo build -p flexweek-mcp --manifest-path engine/Cargo.toml
```

The binary is `engine/target/debug/flexweek-mcp`.

## Run

With no arguments the server uses the desktop's data folder:

- Linux: `~/.local/share/FlexWeek`
- macOS: `~/Library/Application Support/FlexWeek`

The database is `<data folder>/flexweek.db`. The session file is
`<data folder>/signed-in/flexweek-<16 hex chars>.json`, the same name the
desktop writes for that database. The file has to be readable by its owner
only (mode `0600`). On Windows the program prints a refusal and exits.

```
flexweek-mcp --data-dir DIR [--database FILE] [--session-file FILE]
```

`--database` selects a database file. The session file name is then the hash
of that path, unless `--session-file` names the file directly.

`--now YYYY-MM-DDTHH:MM:SSZ` holds the clock at that UTC instant. It is for
tests. Without it, today's date is the local date.

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
