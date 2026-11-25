//! Homework saved from the window, finished or reopened, and unpinned (P4 slice 4A): the rules of
//! controller.py's `add_homework`, `_fix_session`, `unpin_assignment` and `complete_homework`. Expected values
//! follow the desktop tests that pin them (`test_homework_edits_keep_sessions.py`,
//! `test_day_finish_homework.py`, `test_homework_pinned_off_quarter_time.py`), not the code's own output.

use flexweek_app::session::homework_edits::{
    HomeworkEdit, HomeworkEditInput, completed_homework, edit_homework, unpin_homework,
};
use serde_json::{Map, Value, json};

const WEEK: &str = "2026-09-21";
const SUNDAY: &str = "2026-09-27";

fn homework(estimate: i64) -> Value {
    json!({"id": "essay", "title": "Essay", "due": SUNDAY, "estimate_min": estimate, "revision": 0})
}

fn session(id: &str, days: Value, start: Option<&str>, minutes: i64) -> Value {
    let mut block = json!({
        "id": id, "title": "Essay", "kind": "flexible", "duration_min": minutes, "days": days,
        "priority": 3, "energy": "medium", "assignment_id": "essay", "category": null,
    });
    if let Some(start) = start {
        block["start"] = json!(start);
    }
    block
}

fn school() -> Value {
    json!({"id": "school", "title": "School", "kind": "locked", "duration_min": 360, "days": [0, 1, 2, 3, 4],
           "start": "08:00"})
}

fn known(items: Value) -> Map<String, Value> {
    let Value::Object(map) = items else {
        panic!("known homework is an object")
    };
    map
}

struct Request {
    blocks: Vec<Value>,
    known: Map<String, Value>,
    basis: Option<Vec<Value>>,
    days: Option<Vec<i64>>,
    spread: bool,
}

impl Request {
    fn new(blocks: Vec<Value>, known: Value) -> Request {
        Request {
            blocks,
            known: known_map(known),
            basis: None,
            days: None,
            spread: false,
        }
    }

    fn run(&self, assignment: &Value) -> Result<HomeworkEdit, String> {
        edit_homework(&HomeworkEditInput {
            blocks: &self.blocks,
            assignments: &self.known,
            basis: self.basis.as_deref(),
            assignment,
            week_start: WEEK,
            days: self.days.as_deref(),
            spread: self.spread,
            new_session_id: "new-session",
        })
    }
}

fn known_map(value: Value) -> Map<String, Value> {
    match value {
        Value::Null => Map::new(),
        other => known(other),
    }
}

fn saved_essay(estimate: i64) -> Value {
    json!({"essay": {"id": "essay", "title": "Essay", "due": SUNDAY, "estimate_min": estimate, "revision": 3,
                     "focus_minutes": 0, "focus_sessions": 0}})
}

fn ids(blocks: &[Value]) -> Vec<&str> {
    blocks
        .iter()
        .map(|block| block["id"].as_str().unwrap())
        .collect()
}

fn block<'a>(edit: &'a HomeworkEdit, id: &str) -> &'a Value {
    edit.blocks.iter().find(|block| block["id"] == id).unwrap()
}

fn three_sessions() -> Vec<Value> {
    vec![
        session("essay-part-0", json!([0]), Some("16:00"), 30),
        session("essay-part-1", json!([2]), Some("16:00"), 30),
        session("essay-part-2", json!([4]), Some("16:00"), 30),
    ]
}

#[test]
fn an_edit_from_an_older_copy_keeps_the_focus_credit_and_the_revision() {
    let mut saved = saved_essay(60);
    saved["essay"]["focus_minutes"] = json!(30);
    saved["essay"]["focus_sessions"] = json!(1);
    let request = Request::new(vec![session("one", json!([0]), Some("16:00"), 60)], saved);
    let mut opened = homework(60);
    opened["checklist"] = json!([{"id": "step-1", "text": "Outline", "done": true}]);
    let edit = request.run(&opened).unwrap();
    assert_eq!(edit.assignment["focus_minutes"], 30);
    assert_eq!(edit.assignment["focus_sessions"], 1);
    assert_eq!(edit.assignment["revision"], 3);
    assert_eq!(
        edit.assignment["checklist"],
        json!([{"id": "step-1", "text": "Outline", "done": true}])
    );
}

#[test]
fn an_edit_keeps_the_session_weeks_and_the_three_server_counts() {
    let mut saved = saved_essay(60);
    saved["essay"]["session_weeks"] = json!(["2026-09-14"]);
    saved["essay"]["planned_min"] = json!(60);
    saved["essay"]["unplanned_min"] = json!(15);
    saved["essay"]["done_min"] = json!(30);
    let request = Request::new(vec![session("one", json!([0]), Some("16:00"), 60)], saved);
    let edit = request.run(&homework(60)).unwrap();
    assert_eq!(edit.assignment["session_weeks"], json!(["2026-09-14"]));
    assert_eq!(edit.assignment["planned_min"], 60);
    assert_eq!(edit.assignment["unplanned_min"], 15);
    assert_eq!(edit.assignment["done_min"], 30);
}

#[test]
fn a_count_the_server_never_sent_is_not_made_up() {
    let request = Request::new(vec![session("one", json!([0]), None, 60)], saved_essay(60));
    let edit = request.run(&homework(60)).unwrap();
    for key in ["planned_min", "unplanned_min", "done_min"] {
        assert!(
            edit.assignment.get(key).is_none(),
            "{key} appeared from nowhere"
        );
    }
    assert_eq!(edit.assignment["session_weeks"], json!([]));
}

#[test]
fn a_partial_session_is_not_stretched_to_the_estimate() {
    let request = Request::new(vec![session("one", json!([0]), None, 60)], saved_essay(120));
    let mut notes = homework(120);
    notes["notes"] = json!("Half was done last week");
    let edit = request.run(&notes).unwrap();
    assert_eq!(edit.blocks[0]["duration_min"], 60);
}

#[test]
fn a_single_whole_session_follows_a_new_estimate() {
    let request = Request::new(vec![session("one", json!([0]), None, 60)], saved_essay(60));
    let edit = request.run(&homework(90)).unwrap();
    assert_eq!(edit.blocks[0]["duration_min"], 90);
}

#[test]
fn a_whole_session_ticked_done_keeps_its_length() {
    let mut done = session("one", json!([0]), Some("16:00"), 60);
    done["completed"] = json!(true);
    let request = Request::new(vec![done], saved_essay(60));
    let edit = request.run(&homework(90)).unwrap();
    assert_eq!(edit.blocks[0]["duration_min"], 60);
}

#[test]
fn two_sessions_keep_their_lengths_when_the_estimate_changes() {
    let request = Request::new(
        vec![
            session("a", json!([0]), None, 60),
            session("b", json!([1]), None, 60),
        ],
        saved_essay(60),
    );
    let edit = request.run(&homework(90)).unwrap();
    assert_eq!(edit.blocks[0]["duration_min"], 60);
    assert_eq!(edit.blocks[1]["duration_min"], 60);
}

#[test]
fn a_notes_edit_keeps_every_session_of_a_spread_homework() {
    let request = Request::new(three_sessions(), saved_essay(90));
    let mut notes = homework(90);
    notes["notes"] = json!("Cite two sources");
    let edit = request.run(&notes).unwrap();
    assert_eq!(
        ids(&edit.blocks),
        ["essay-part-0", "essay-part-1", "essay-part-2"]
    );
    assert_eq!(edit.assignment["notes"], "Cite two sources");
    assert_eq!(
        edit.changed_ids,
        ["essay-part-0", "essay-part-1", "essay-part-2"]
    );
    assert_eq!(edit.label, "editing Essay");
}

#[test]
fn a_new_title_priority_energy_and_category_reach_every_session() {
    let request = Request::new(three_sessions(), saved_essay(90));
    let mut changed = homework(90);
    changed["title"] = json!("History essay");
    changed["priority"] = json!(1);
    changed["energy"] = json!("high");
    changed["category"] = json!("study");
    let edit = request.run(&changed).unwrap();
    for session in &edit.blocks {
        assert_eq!(session["title"], "History essay");
        assert_eq!(session["priority"], 1);
        assert_eq!(session["energy"], "high");
        assert_eq!(session["category"], "study");
    }
}

#[test]
fn a_homework_without_a_category_leaves_the_sessions_category_alone() {
    let mut tagged = session("one", json!([0]), None, 60);
    tagged["category"] = json!("reading");
    let request = Request::new(vec![tagged], saved_essay(60));
    let edit = request.run(&homework(60)).unwrap();
    assert_eq!(edit.blocks[0]["category"], "reading");
}

#[test]
fn other_homeworks_and_blocks_are_not_touched() {
    let mut other = session("other", json!([3]), Some("10:00"), 45);
    other["assignment_id"] = json!("reading");
    other["title"] = json!("Reading");
    let request = Request::new(
        vec![
            school(),
            other.clone(),
            session("one", json!([0]), None, 60),
        ],
        saved_essay(60),
    );
    let mut renamed = homework(60);
    renamed["title"] = json!("New name");
    let edit = request.run(&renamed).unwrap();
    assert_eq!(edit.blocks[0], school());
    assert_eq!(edit.blocks[1], other);
    assert_eq!(edit.changed_ids, ["one"]);
}

#[test]
fn finishing_a_homework_keeps_its_sessions_and_ticks_each() {
    let request = Request::new(three_sessions(), saved_essay(90));
    let finished = completed_homework(&saved_essay(90)["essay"], true, "2026-09-23T10:00").unwrap();
    let edit = request.run(&finished).unwrap();
    assert_eq!(
        ids(&edit.blocks),
        ["essay-part-0", "essay-part-1", "essay-part-2"]
    );
    assert!(
        edit.blocks
            .iter()
            .all(|session| session["completed"] == true)
    );
    assert_eq!(edit.label, "finishing Essay");
    assert_eq!(edit.assignment["completed"], true);
}

#[test]
fn finishing_stamps_the_day_a_placed_one_day_session_was_done() {
    let request = Request::new(
        vec![
            session("placed", json!([2]), Some("16:00"), 30),
            session("waiting", json!([1]), None, 30),
            session("many-days", json!([0, 1]), Some("17:00"), 30),
        ],
        saved_essay(90),
    );
    let finished = completed_homework(&saved_essay(90)["essay"], true, "2026-09-23T10:00").unwrap();
    let edit = request.run(&finished).unwrap();
    assert_eq!(block(&edit, "placed")["completed_day"], 2);
    assert!(
        block(&edit, "waiting").get("completed_day").is_none(),
        "a waiting session was not done on a day"
    );
    assert!(
        block(&edit, "many-days").get("completed_day").is_none(),
        "two days name no one day"
    );
}

#[test]
fn reopening_unticks_every_session_and_drops_the_day_done() {
    let mut done_session = session("placed", json!([2]), Some("16:00"), 30);
    done_session["completed"] = json!(true);
    done_session["completed_day"] = json!(2);
    let mut saved = saved_essay(30);
    saved["essay"]["completed"] = json!(true);
    saved["essay"]["completed_at"] = json!("2026-09-23T10:00");
    let request = Request::new(vec![done_session], saved.clone());
    let reopened = completed_homework(&saved["essay"], false, "2026-09-24T09:00").unwrap();
    let edit = request.run(&reopened).unwrap();
    assert_eq!(edit.blocks[0]["completed"], false);
    assert!(edit.blocks[0].get("completed_day").is_none());
    assert_eq!(edit.label, "reopening Essay");
    assert_eq!(edit.assignment["completed"], false);
    assert_eq!(edit.assignment["completed_at"], Value::Null);
}

#[test]
fn an_edit_that_does_not_change_done_leaves_the_sessions_ticks_alone() {
    let mut done_session = session("placed", json!([2]), Some("16:00"), 30);
    done_session["completed"] = json!(true);
    done_session["completed_day"] = json!(2);
    let request = Request::new(vec![done_session.clone()], saved_essay(30));
    let edit = request.run(&homework(30)).unwrap();
    assert_eq!(edit.blocks[0]["completed"], true);
    assert_eq!(edit.blocks[0]["completed_day"], 2);
    assert_eq!(edit.label, "editing Essay");
}

#[test]
fn completed_homework_keeps_a_stamp_it_has_and_gets_one_when_it_has_none() {
    let mut stamped = saved_essay(60)["essay"].clone();
    stamped["completed_at"] = json!("2026-09-01T08:00");
    let kept = completed_homework(&stamped, true, "2026-09-23T10:00").unwrap();
    assert_eq!(kept["completed"], true);
    assert_eq!(kept["completed_at"], "2026-09-01T08:00");
    let fresh = completed_homework(&saved_essay(60)["essay"], true, "2026-09-23T10:00").unwrap();
    assert_eq!(fresh["completed_at"], "2026-09-23T10:00");
    let reopened = completed_homework(&stamped, false, "2026-09-23T10:00").unwrap();
    assert_eq!(reopened["completed"], false);
    assert_eq!(reopened["completed_at"], Value::Null);
    assert_eq!(reopened["title"], "Essay");
}

#[test]
fn spread_drops_every_open_session_makes_none_and_keeps_the_done_ones() {
    let mut done_session = session("done", json!([0]), Some("16:00"), 30);
    done_session["completed"] = json!(true);
    let mut request = Request::new(
        vec![
            done_session,
            session("open-a", json!([1]), Some("16:00"), 30),
            session("open-b", json!([2]), None, 30),
        ],
        saved_essay(90),
    );
    request.spread = true;
    let edit = request.run(&homework(90)).unwrap();
    assert_eq!(ids(&edit.blocks), ["done"]);
    assert_eq!(edit.changed_ids, ["done"]);
}

#[test]
fn spread_of_a_homework_with_nothing_placed_makes_no_session() {
    let mut request = Request::new(vec![school()], saved_essay(90));
    request.spread = true;
    let edit = request.run(&homework(90)).unwrap();
    assert_eq!(ids(&edit.blocks), ["school"]);
    assert!(edit.changed_ids.is_empty());
}

#[test]
fn a_new_homework_gets_one_session_as_long_as_its_estimate_by_its_due_day() {
    let request = Request::new(vec![school()], Value::Null);
    let mut wednesday = homework(75);
    wednesday["due"] = json!("2026-09-23");
    let edit = request.run(&wednesday).unwrap();
    assert_eq!(edit.label, "adding Essay");
    assert_eq!(ids(&edit.blocks), ["school", "new-session"]);
    let made = block(&edit, "new-session");
    assert_eq!(made["duration_min"], 75);
    assert_eq!(made["days"], json!([0, 1, 2]));
    assert_eq!(made["kind"], "flexible");
    assert_eq!(made["assignment_id"], "essay");
    assert_eq!(made["title"], "Essay");
    assert_eq!(edit.changed_ids, ["new-session"]);
    assert_eq!(edit.assignment["revision"], 0);
}

#[test]
fn a_new_homework_due_before_the_week_goes_on_the_first_day_and_after_it_on_every_day() {
    let request = Request::new(vec![], Value::Null);
    let mut early = homework(30);
    early["due"] = json!("2026-09-01");
    assert_eq!(
        block(&request.run(&early).unwrap(), "new-session")["days"],
        json!([0])
    );
    let mut late = homework(30);
    late["due"] = json!("2026-12-01");
    assert_eq!(
        block(&request.run(&late).unwrap(), "new-session")["days"],
        json!([0, 1, 2, 3, 4, 5, 6])
    );
}

#[test]
fn the_days_a_caller_names_go_on_a_new_session_and_on_a_lone_waiting_one() {
    let mut request = Request::new(vec![], Value::Null);
    request.days = Some(vec![3, 4]);
    assert_eq!(
        block(&request.run(&homework(30)).unwrap(), "new-session")["days"],
        json!([3, 4])
    );

    let mut lone = Request::new(vec![session("one", json!([0]), None, 30)], saved_essay(30));
    lone.days = Some(vec![5]);
    assert_eq!(
        lone.run(&homework(30)).unwrap().blocks[0]["days"],
        json!([5])
    );
}

#[test]
fn the_days_a_caller_names_leave_a_placed_session_and_a_pair_of_sessions_alone() {
    let mut placed = Request::new(
        vec![session("one", json!([0]), Some("16:00"), 30)],
        saved_essay(30),
    );
    placed.days = Some(vec![5]);
    assert_eq!(
        placed.run(&homework(30)).unwrap().blocks[0]["days"],
        json!([0])
    );

    let mut pair = Request::new(
        vec![
            session("a", json!([0]), None, 15),
            session("b", json!([1]), None, 15),
        ],
        saved_essay(30),
    );
    pair.days = Some(vec![5]);
    let edit = pair.run(&homework(30)).unwrap();
    assert_eq!(edit.blocks[0]["days"], json!([0]));
    assert_eq!(edit.blocks[1]["days"], json!([1]));
}

#[test]
fn a_known_homework_with_nothing_placed_gets_a_session_for_what_is_left_down_to_a_quarter_hour() {
    let mut saved = saved_essay(60);
    saved["essay"]["focus_minutes"] = json!(10);
    let request = Request::new(vec![], saved);
    let edit = request.run(&homework(60)).unwrap();
    assert_eq!(block(&edit, "new-session")["duration_min"], 45);
}

#[test]
fn a_known_homework_that_is_finished_gets_no_new_session() {
    let request = Request::new(vec![], saved_essay(60));
    let finished = completed_homework(&saved_essay(60)["essay"], true, "2026-09-23T10:00").unwrap();
    let edit = request.run(&finished).unwrap();
    assert!(edit.blocks.is_empty());
}

#[test]
fn the_remaining_count_reads_the_server_counts_against_the_basis_week() {
    let mut saved = saved_essay(120);
    saved["essay"]["planned_min"] = json!(75);
    saved["essay"]["unplanned_min"] = json!(45);
    saved["essay"]["done_min"] = json!(0);

    // The basis week held 75 minutes of it, all of "planned": nothing sits in later weeks.
    let mut with_basis = Request::new(vec![], saved.clone());
    with_basis.basis = Some(vec![session("old", json!([0]), Some("16:00"), 75)]);
    assert_eq!(
        block(&with_basis.run(&homework(120)).unwrap(), "new-session")["duration_min"],
        120
    );

    // No basis yet: the 75 planned minutes are all in other weeks, so 45 are left for this one.
    let without = Request::new(vec![], saved);
    assert_eq!(
        block(&without.run(&homework(120)).unwrap(), "new-session")["duration_min"],
        45
    );
}

#[test]
fn a_pin_the_dialog_chose_moves_every_open_session_to_that_day_and_start() {
    let mut done_session = session("done", json!([0]), Some("16:00"), 30);
    done_session["completed"] = json!(true);
    let request = Request::new(
        vec![done_session, session("open", json!([1]), Some("16:00"), 30)],
        saved_essay(60),
    );
    let mut pinned = homework(60);
    pinned["fixed_at"] = json!({"day": 4, "start": "18:55"});
    let edit = request.run(&pinned).unwrap();
    let open = block(&edit, "open");
    assert_eq!(open["start"], "18:55");
    assert_eq!(open["days"], json!([4]));
    assert_eq!(open["pinned"], true);
    assert_eq!(edit.pinned_ids, ["open"]);
    let done = block(&edit, "done");
    assert_eq!(
        done["days"],
        json!([0]),
        "a session already done is not moved"
    );
    assert_eq!(done["start"], "16:00");
    assert!(
        done.get("pinned").is_none() || done["pinned"] == false,
        "a session already done is not pinned"
    );
}

#[test]
fn a_save_without_touching_the_pin_keeps_it_exactly() {
    let mut pinned = session("pinned", json!([4]), Some("18:55"), 60);
    pinned["pinned"] = json!(true);
    let request = Request::new(vec![pinned.clone()], saved_essay(60));
    let mut renamed = homework(60);
    renamed["title"] = json!("History essay, final");
    let edit = request.run(&renamed).unwrap();
    let kept = &edit.blocks[0];
    assert_eq!(kept["start"], "18:55");
    assert_eq!(kept["days"], json!([4]));
    assert_eq!(kept["pinned"], true);
    assert_eq!(kept["title"], "History essay, final");
    assert!(edit.pinned_ids.is_empty());
}

#[test]
fn letting_flexweek_pick_a_time_takes_the_pin_off_and_keeps_the_time_until_it_moves() {
    let mut pinned = session("pinned", json!([4]), Some("18:55"), 60);
    pinned["pinned"] = json!(true);
    let request = Request::new(vec![pinned], saved_essay(60));
    let mut clear = homework(60);
    clear["fixed_at"] = Value::Null;
    let edit = request.run(&clear).unwrap();
    assert!(edit.blocks[0].get("pinned").is_none());
    assert_eq!(edit.blocks[0]["start"], "18:55");
    assert!(edit.pinned_ids.is_empty());
}

#[test]
fn a_new_homework_with_a_pin_gets_a_pinned_session_and_one_without_gets_none() {
    let request = Request::new(vec![], Value::Null);
    let mut pinned = homework(60);
    pinned["fixed_at"] = json!({"day": 2, "start": "17:30"});
    let edit = request.run(&pinned).unwrap();
    let made = block(&edit, "new-session");
    assert_eq!(made["days"], json!([2]));
    assert_eq!(made["start"], "17:30");
    assert_eq!(made["pinned"], true);
    assert_eq!(edit.pinned_ids, ["new-session"]);

    let mut cleared = homework(60);
    cleared["fixed_at"] = Value::Null;
    let edit = request.run(&cleared).unwrap();
    assert!(block(&edit, "new-session").get("pinned").is_none());
    assert!(edit.pinned_ids.is_empty());
}

#[test]
fn unpinning_takes_the_pin_off_this_homeworks_sessions_only() {
    let mut pinned = session("pinned", json!([4]), Some("18:55"), 60);
    pinned["pinned"] = json!(true);
    let mut other = session("other", json!([1]), Some("10:00"), 30);
    other["assignment_id"] = json!("reading");
    other["pinned"] = json!(true);
    let loose = session("loose", json!([2]), None, 30);
    let blocks = vec![school(), pinned, other.clone(), loose.clone()];
    let after = unpin_homework(&blocks, "essay").unwrap();
    assert!(after[1].get("pinned").is_none());
    assert_eq!(after[1]["start"], "18:55");
    assert_eq!(after[0], school());
    assert_eq!(after[2], other, "another homework's pin stays");
    assert_eq!(after[3], loose);
}

#[test]
fn unpinning_a_homework_with_no_pin_changes_nothing() {
    let blocks = vec![school(), session("loose", json!([2]), None, 30)];
    assert_eq!(unpin_homework(&blocks, "essay"), None);
    assert_eq!(unpin_homework(&blocks, "unknown"), None);
}

#[test]
fn a_homework_the_engine_would_refuse_is_refused_with_words() {
    let request = Request::new(vec![], Value::Null);
    let mut nameless = homework(60);
    nameless["title"] = json!("   ");
    assert!(request.run(&nameless).is_err());
    assert!(request.run(&json!("essay")).is_err());
    let mut bad_pin = homework(60);
    bad_pin["fixed_at"] = json!({"day": 2});
    assert!(request.run(&bad_pin).is_err());
}

#[test]
fn a_refused_edit_changes_nothing() {
    let blocks = three_sessions();
    let request = Request::new(blocks.clone(), saved_essay(90));
    let mut nameless = homework(90);
    nameless["title"] = json!("");
    assert!(request.run(&nameless).is_err());
    assert_eq!(request.blocks, blocks);
}

#[test]
fn the_json_answer_names_the_assignment_blocks_changed_pinned_and_label() {
    let request = Request::new(vec![session("one", json!([0]), None, 60)], saved_essay(60));
    let answer = request.run(&homework(60)).unwrap().to_json();
    assert_eq!(answer["assignment"]["id"], "essay");
    assert_eq!(answer["blocks"][0]["id"], "one");
    assert_eq!(answer["changed"], json!(["one"]));
    assert_eq!(answer["pinned"], json!([]));
    assert_eq!(answer["label"], "editing Essay");
}

fn pin_refused(request: &Request, pin: Value) -> String {
    let mut given = homework(60);
    given["fixed_at"] = pin;
    request
        .run(&given)
        .expect_err("a malformed pin must be refused")
}

#[test]
fn a_malformed_pin_is_refused_when_a_session_is_made() {
    let request = Request::new(vec![], Value::Null);
    for pin in [
        json!([]),
        json!({}),
        json!("Friday"),
        json!(4),
        json!(true),
        json!([4, "18:55"]),
    ] {
        pin_refused(&request, pin);
    }
}

#[test]
fn a_malformed_pin_is_refused_when_sessions_exist_and_when_none_is_open() {
    let request = Request::new(vec![session("one", json!([0]), None, 60)], saved_essay(60));
    for pin in [json!([]), json!({}), json!("Friday")] {
        pin_refused(&request, pin);
    }
    let mut done_only = session("done", json!([0]), Some("16:00"), 60);
    done_only["completed"] = json!(true);
    let request = Request::new(vec![done_only], saved_essay(60));
    pin_refused(&request, json!([]));
}

#[test]
fn a_malformed_pin_is_refused_by_spread_too() {
    let mut request = Request::new(vec![session("one", json!([0]), None, 60)], saved_essay(60));
    request.spread = true;
    pin_refused(&request, json!([]));
    pin_refused(&request, json!({"day": 2}));
    pin_refused(&request, json!({"day": 7, "start": "16:00"}));
    pin_refused(&request, json!({"day": 2, "start": "four"}));
}

#[test]
fn a_pin_needs_a_day_from_0_to_6_and_a_start_as_hours_and_minutes() {
    let request = Request::new(vec![], Value::Null);
    pin_refused(&request, json!({"day": 7, "start": "16:00"}));
    pin_refused(&request, json!({"day": -1, "start": "16:00"}));
    pin_refused(&request, json!({"day": "2", "start": "16:00"}));
    pin_refused(&request, json!({"day": 2, "start": 1600}));
    pin_refused(&request, json!({"day": 2, "start": "four"}));
    pin_refused(&request, json!({"start": "16:00"}));
}

#[test]
fn a_cleared_pin_and_an_absent_pin_stay_different_and_both_are_accepted() {
    let mut pinned = session("pinned", json!([4]), Some("18:55"), 60);
    pinned["pinned"] = json!(true);
    let request = Request::new(vec![pinned], saved_essay(60));
    let absent = request.run(&homework(60)).unwrap();
    assert_eq!(absent.blocks[0]["pinned"], true);
    let mut cleared = homework(60);
    cleared["fixed_at"] = Value::Null;
    let cleared = request.run(&cleared).unwrap();
    assert!(cleared.blocks[0].get("pinned").is_none());
}

fn counted(key: &str, count: Value) -> Request {
    let mut saved = saved_essay(60);
    saved["essay"][key] = count;
    Request::new(vec![], saved)
}

#[test]
fn a_server_count_that_is_not_a_whole_number_of_minutes_from_0_is_refused() {
    for key in ["planned_min", "unplanned_min", "done_min"] {
        for bad in [
            json!(-1),
            json!(30.5),
            json!(30.0),
            json!("30"),
            json!(true),
            json!([30]),
            json!(1e30),
        ] {
            let request = counted(key, bad.clone());
            let said = request
                .run(&homework(60))
                .expect_err(&format!("{key} = {bad} must be refused"));
            assert!(said.contains(key), "the words name the count: {said}");
        }
    }
}

#[test]
fn a_server_count_of_0_a_whole_number_or_null_is_accepted() {
    for key in ["planned_min", "unplanned_min", "done_min"] {
        for good in [json!(0), json!(45), Value::Null] {
            assert!(
                counted(key, good).run(&homework(60)).is_ok(),
                "{key} was refused"
            );
        }
    }
}

#[test]
fn a_basis_session_length_that_is_not_minutes_is_refused_for_this_homework_only() {
    let mut other = session("other", json!([0]), Some("16:00"), 30);
    other["assignment_id"] = json!("reading");
    other["duration_min"] = json!("long");
    for bad in [
        json!(-5),
        json!(7141),
        json!(30.5),
        json!("30"),
        Value::Null,
    ] {
        let mut ours = session("old", json!([0]), Some("16:00"), 30);
        ours["duration_min"] = bad.clone();
        let mut request = Request::new(vec![], saved_essay(60));
        request.basis = Some(vec![ours]);
        assert!(request.run(&homework(60)).is_err(), "{bad} was accepted");
    }
    let mut request = Request::new(vec![], saved_essay(60));
    request.basis = Some(vec![other, session("old", json!([0]), Some("16:00"), 7140)]);
    assert!(request.run(&homework(60)).is_ok());
}

#[test]
fn a_done_count_at_the_top_of_what_a_number_holds_is_refused_not_wrapped() {
    let mut saved = saved_essay(60);
    saved["essay"]["done_min"] = json!(i64::MAX);
    let mut ticked = session("one", json!([0]), Some("16:00"), 30);
    ticked["completed"] = json!(true);
    let mut request = Request::new(vec![ticked], saved);
    request.basis = Some(vec![]);
    let said = request
        .run(&homework(60))
        .expect_err("30 more than the largest count cannot be counted");
    assert!(said.contains("too many"), "{said}");
}
