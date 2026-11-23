//! What a failed write leaves behind (nothing), and that a write begun with BEGIN IMMEDIATE commits or rolls
//! back as a whole, through the service's one way into the database (`with_db`). The Rust twins of the first
//! two tests in backend/tests/test_database_transactions.py (its third, that waiting on a lock lets other
//! Python threads run, goes with the Python layer in P2).

use flexweek_service::{ServiceError, with_db};
use flexweek_testkit::TestDb;

fn count(db: &TestDb, sql: &str) -> Vec<String> {
    let conn = rusqlite::Connection::open(&db.path).unwrap();
    let mut stmt = conn.prepare(sql).unwrap();
    stmt.query_map([], |row| row.get::<_, String>(0))
        .unwrap()
        .collect::<Result<_, _>>()
        .unwrap()
}

#[test]
fn a_failed_later_write_rolls_the_earlier_ones_back() {
    let db = TestDb::new("tx-later");
    with_db(&db.path, |conn| {
        conn.execute_batch("CREATE TABLE names(id INTEGER PRIMARY KEY, name TEXT UNIQUE)")
            .unwrap();
        Ok(())
    })
    .unwrap();
    let failed: Result<(), ServiceError> = with_db(&db.path, |conn| {
        flexweek_store::begin_immediate(conn)?;
        for name in ["a", "b", "a"] {
            conn.execute("INSERT INTO names(name) VALUES (?1)", [name])
                .map_err(flexweek_store::StoreError::Sqlite)?;
        }
        Ok(())
    });
    assert!(failed.is_err());
    assert!(
        count(&db, "SELECT name FROM names").is_empty(),
        "the first two names stayed"
    );
}

#[test]
fn a_write_begun_immediately_commits_or_rolls_back_as_a_whole() {
    let db = TestDb::new("tx-immediate");
    with_db(&db.path, |conn| {
        conn.execute_batch("CREATE TABLE t(id INTEGER PRIMARY KEY, name TEXT)")
            .unwrap();
        Ok(())
    })
    .unwrap();
    with_db(&db.path, |conn| {
        flexweek_store::begin_immediate(conn)?;
        conn.execute("INSERT INTO t(name) VALUES ('kept')", [])
            .unwrap();
        Ok(())
    })
    .unwrap();
    assert_eq!(count(&db, "SELECT name FROM t"), ["kept"]);
    let failed: Result<(), ServiceError> = with_db(&db.path, |conn| {
        flexweek_store::begin_immediate(conn)?;
        // The first insert lands and the second clashes with it, so only a rollback can take 'x' away. (The
        // Python original reused id 1, which 'kept' holds, so its first insert already failed.)
        conn.execute("INSERT INTO t(id, name) VALUES (2, 'x')", [])
            .map_err(flexweek_store::StoreError::Sqlite)?;
        conn.execute("INSERT INTO t(id, name) VALUES (2, 'y')", [])
            .map_err(flexweek_store::StoreError::Sqlite)?;
        Ok(())
    });
    assert!(failed.is_err());
    assert_eq!(count(&db, "SELECT name FROM t"), ["kept"]);
}
