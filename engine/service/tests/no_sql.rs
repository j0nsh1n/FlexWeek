//! The store owns every SQL statement; the service only calls it. (A Python test once spied on the
//! routes' connection to check they read routines and preferences through the store, not raw SQL; the
//! routes are the service now.)

#[test]
fn the_service_holds_no_sql() {
    let src = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("src");
    let mut found = Vec::new();
    for entry in std::fs::read_dir(&src).unwrap() {
        let path = entry.unwrap().path();
        let text = std::fs::read_to_string(&path).unwrap();
        // Unit tests may set up a database by hand; the code above them may not.
        let code = text.split("#[cfg(test)]").next().unwrap_or("");
        for statement in [
            "SELECT ",
            "INSERT INTO",
            "UPDATE ",
            "DELETE FROM",
            "CREATE TABLE",
        ] {
            if code.contains(statement) {
                found.push(format!("{}: {statement}", path.display()));
            }
        }
    }
    assert!(
        found.is_empty(),
        "SQL outside the store:\n{}",
        found.join("\n")
    );
}
