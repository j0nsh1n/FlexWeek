mod common;

use serde_json::{Value, json};

#[test]
fn a_numeric_jsonrpc_id_round_trips() {
    let dir = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../target/mcp-tests")
        .join(format!("spike-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("scratch dir");
    let dir = dir.to_string_lossy().into_owned();
    let mut server = common::Server::spawn(&["--data-dir", &dir, "--now", "2026-10-21T12:00:00Z"]);
    let response = server.request(
        "initialize",
        json!({
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "flexweek-test", "version": "0"}
        }),
        7,
    );
    assert_eq!(
        response.get("id").and_then(Value::as_i64),
        Some(7),
        "numeric JSON-RPC id must round-trip"
    );
    assert!(
        response.get("error").is_none(),
        "numeric JSON-RPC id must round-trip, got an error: {response}"
    );
}
