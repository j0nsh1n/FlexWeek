//! The canonical text of a restore point: keys sorted, no spaces, the way Python's
//! `json.dumps(value, sort_keys=True, separators=(",", ":"))` writes it.

use flexweek_engine::snapshot::canonical;
use serde_json::json;

#[test]
fn canonical_sorts_keys_and_leaves_out_spaces() {
    let value = json!({"b": 1, "a": {"d": true, "c": null}});
    assert_eq!(canonical(&value), r#"{"a":{"c":null,"d":true},"b":1}"#);
}
