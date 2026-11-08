//! Saved looks: a name that is already taken gets a number, and deleting a look removes it.

use flexweek_engine::desk::custom_look::{delete_look, free_name};
use serde_json::json;

#[test]
fn a_name_that_is_taken_gets_the_next_number() {
    let saved = json!([{"name": "My look", "base": "light"}]);
    assert_eq!(free_name(&saved, "My look").expect("a name"), "My look 2");
}

#[test]
fn deleting_the_only_saved_look_leaves_none() {
    let saved = json!([{"name": "My look", "base": "light"}]);
    assert!(delete_look(&saved, "My look").expect("deleted").is_empty());
}
