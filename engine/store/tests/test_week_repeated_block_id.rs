//! R10: a week that repeats a block id is refused in words, and the week already stored is left alone.

mod common;

use common::scratch;
use flexweek_store::{
    WeekSave, initialize, insert_user, list_account_weeks, open_connection, read_week,
    replace_account, save_week,
};

const WEEK: &str = "2026-10-05";

fn block(id: &str, title: &str) -> String {
    format!(
        r#"{{"days":[0],"duration_min":60,"id":"{id}","kind":"locked","start":"08:00","title":"{title}"}}"#
    )
}

#[test]
fn a_repeated_id_is_named_and_the_stored_week_stays_as_it_was() {
    let path = scratch("week-repeat");
    initialize(&path, WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    let ann = insert_user(&conn, "ann", "scrypt$x").unwrap();
    conn.execute("COMMIT", []).unwrap();
    let kept = format!("[{}]", block("school", "School"));
    assert_eq!(
        save_week(&conn, ann, WEEK, &kept, 0).unwrap(),
        WeekSave::Ready(1)
    );
    conn.execute("COMMIT", []).unwrap();

    let doubled = format!(
        "[{},{},{}]",
        block("school", "School"),
        block("gym", "Gym"),
        block("gym", "Gym again")
    );
    let refused = save_week(&conn, ann, WEEK, &doubled, 1).expect_err("a repeated id is refused");

    assert_eq!(
        refused.to_string(),
        r#"Two blocks in this week share the id "gym". Each block needs its own id."#
    );
    assert_eq!(read_week(&conn, ann, WEEK).unwrap(), Some((kept, 1)));
}

#[test]
fn a_replace_with_a_repeated_id_is_refused_whole_and_the_account_stays_as_it_was() {
    let path = scratch("replace-repeat");
    initialize(&path, WEEK).unwrap();
    let conn = open_connection(&path).unwrap();
    let ann = insert_user(&conn, "ann", "scrypt$x").unwrap();
    conn.execute("COMMIT", []).unwrap();
    let kept = format!("[{}]", block("school", "School"));
    save_week(&conn, ann, WEEK, &kept, 0).unwrap();
    conn.execute("COMMIT", []).unwrap();
    let before = list_account_weeks(&conn, ann).unwrap();

    let fine = format!("[{}]", block("art", "Art"));
    let doubled = format!("[{},{}]", block("gym", "Gym"), block("gym", "Gym again"));
    let refused = replace_account(
        &conn,
        ann,
        &[
            ("2026-10-12".to_string(), fine, 1),
            ("2026-10-19".to_string(), doubled, 1),
        ],
        &[],
    )
    .expect_err("a repeated id refuses the whole replace");

    assert_eq!(
        refused.to_string(),
        r#"Two blocks in this week share the id "gym". Each block needs its own id."#
    );
    assert_eq!(list_account_weeks(&conn, ann).unwrap(), before);
    assert_eq!(read_week(&conn, ann, WEEK).unwrap(), Some((kept, 1)));
}
