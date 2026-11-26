use std::sync::Arc;
use std::sync::atomic::{AtomicU64, Ordering};

use flexweek_app::session::{Host, Session};
use flexweek_service::{accounts::Entropy, plans::Stopwatch};
use flexweek_testkit::{Counting, TestDb};
use serde_json::{Value, json};

const FIRST: &str = "2026-11-02";
const NEXT: &str = "2026-11-09";
const NOW: &str = "2026-11-05T19:00";

#[derive(Default)]
struct Clock(AtomicU64);

impl Host for Clock {
    fn steady_ms(&self) -> i64 {
        1000
    }

    fn request_clock(&self) -> (i64, String) {
        (1_793_905_200, NOW.into())
    }

    fn restore_token(&self) -> String {
        format!("{:016x}", self.0.fetch_add(1, Ordering::Relaxed))
    }

    fn entropy(&self) -> Box<dyn Entropy + Send> {
        Box::new(Counting(self.0.fetch_add(1000, Ordering::Relaxed)))
    }

    fn stopwatch(&self) -> Stopwatch {
        Box::new(|| 0.0)
    }
}

struct Desk {
    session: Session,
    _db: TestDb,
    first_weekday: u32,
}

impl Desk {
    fn signed_in(name: &str) -> Self {
        let db = TestDb::new(name);
        let mut session =
            Session::new(db.path.clone(), Arc::new(Clock::default()), Arc::new(|| {}));
        session.frame().answer_inline();
        let mut desk = Self {
            session,
            _db: db,
            first_weekday: 0,
        };
        desk.send(json!({
            "cmd": "register", "username": "ana", "password": "a-long-test-password", "keep": true
        }));
        assert_eq!(desk.event()["kind"], "registered");
        desk
    }

    fn send(&mut self, command: Value) -> Value {
        let answer: Value = serde_json::from_str(&self.session.send(&command.to_string())).unwrap();
        assert_eq!(answer["ok"], true, "{command}: {answer}");
        answer
    }

    fn event(&mut self) -> Value {
        serde_json::from_str(&self.session.take_event()).unwrap()
    }

    fn view(&self, name: &str) -> Value {
        serde_json::from_str(&self.session.view(&format!("drafts.{name}"))).unwrap()
    }

    fn ticket(&mut self) -> Value {
        self.send(json!({ "cmd": "begin" }))["ticket"].clone()
    }

    fn idle(&mut self, ticket: Value) {
        assert_eq!(
            self.send(json!({ "cmd": "idle", "ticket": ticket }))["idle"],
            true
        );
    }

    fn request(&mut self, effect: &Value) -> Value {
        let sent = self.send(json!({
            "cmd": "request", "method": effect["method"], "path": effect["path"], "body": effect["body"],
        }));
        let event = self.event();
        assert_eq!(event["number"], sent["number"], "{event}");
        event
    }

    fn reply(&mut self, effect: &Value, event: &Value, selection: &Value) -> Value {
        let error = if event["ok"] == true {
            Value::Null
        } else {
            json!({ "status": event["status"], "message": event["message"] })
        };
        self.send(json!({
            "cmd": "drafts_reply", "effect_id": effect["id"], "data": event["body"], "error": error,
            "now": NOW, "shifted_week": self.first_weekday != 0, "selection": selection, "ids": ["renewed-parked-save"],
        }))
    }

    fn carry(&mut self, effect: &Value, selection: &Value) -> Value {
        let event = self.request(effect);
        self.reply(effect, &event, selection)
    }

    fn choose(&mut self, start: &str) -> Value {
        self.send(json!({
            "cmd": "drafts_load", "requested": start, "first_weekday": self.first_weekday, "discard": false,
            "selection": { "selected_day": self.view("week_start"), "selected_block_id": "band" },
        }))
    }

    fn fetch(&mut self, start: &str) -> (Value, Value) {
        let ticket = self.ticket();
        let first = self.send(json!({ "cmd": "drafts_fetch", "start": start, "ticket": ticket }));
        let next = self.carry(&first["effect"], &Value::Null);
        assert_eq!(next["action"], "request");
        assert_eq!(
            next["effect"]["path"],
            format!("/api/assignments?week_start={start}&include_completed=true")
        );
        (ticket, next["effect"].clone())
    }

    fn load(&mut self, start: &str) {
        let route = self.choose(start);
        if route["action"] == "restore" {
            return;
        }
        assert_eq!(route["action"], "fetch");
        let selection =
            json!({ "selected_day": self.view("week_start"), "selected_block_id": "band" });
        let (ticket, effect) = self.fetch(start);
        assert_eq!(self.carry(&effect, &selection)["action"], "loaded");
        self.idle(ticket);
    }

    fn edit(&mut self, blocks: Value, homework: Value, trace: Value) {
        self.send(json!({
            "cmd": "drafts_touch", "label": "editing the week", "blocks": blocks,
            "put_homework": homework, "trace": trace,
        }));
    }

    fn save(&mut self, operation: &str, plan: bool) {
        self.send(json!({
            "cmd": "drafts_save", "ids": [operation, format!("{operation}-step")],
            "join": false, "record_history": true, "plan": plan,
        }));
    }

    fn post(&mut self) -> (Value, Value) {
        let ticket = self.ticket();
        let post = self.send(json!({
            "cmd": "drafts_post", "ticket": ticket, "shifted_week": self.first_weekday != 0,
        }));
        (ticket, post["effect"].clone())
    }

    fn save_to_store(&mut self, operation: &str) {
        self.save(operation, false);
        let (ticket, effect) = self.post();
        assert_eq!(self.carry(&effect, &Value::Null)["action"], "saved");
        self.idle(ticket);
    }

    fn start_delete(&mut self) -> (Value, Value) {
        let ticket = self.ticket();
        let delete = self.send(json!({
            "cmd": "drafts_delete_start", "ticket": ticket, "assignment_id": "essay",
            "operation_id": "delete-essay", "key": "delete-essay",
        }));
        (ticket, delete["effect"].clone())
    }

    fn end_delete(&mut self, ticket: Value, mut answer: Value) {
        while answer["action"] == "request" {
            answer = self.carry(&answer["effect"], &Value::Null);
        }
        assert_eq!(answer["action"], "deleted");
        assert_eq!(answer["words"], "Deleted Essay.");
        self.idle(ticket);
    }

    fn stored(&mut self, start: &str) -> Value {
        let event = self
            .request(&json!({ "method": "GET", "path": format!("/api/week?week_start={start}") }));
        assert_eq!(event["ok"], true, "{event}");
        event["body"].clone()
    }

    fn undo(&mut self) {
        let answer = self.send(json!({ "cmd": "drafts_travel", "redo": false }));
        assert_eq!(answer["go"], true, "{answer}");
        self.edit(self.view("blocks"), json!([]), Value::Null);
    }
}

fn band() -> Value {
    json!({ "id": "band", "title": "Band", "kind": "locked", "days": [1], "start": "18:00", "duration_min": 60 })
}

fn essay(id: &str) -> Value {
    json!({
        "id": id, "title": "Essay", "assignment_id": "essay", "kind": "flexible",
        "days": [0], "start": "16:00", "duration_min": 30,
    })
}

fn homework() -> Value {
    json!({
        "id": "essay", "title": "Essay", "due": "2026-11-20", "estimate_min": 60, "revision": 0,
    })
}

fn offline() -> Value {
    json!({ "ok": false, "status": 0, "message": "No connection" })
}

#[test]
fn both_reads_must_land_before_a_dirty_week_is_parked() {
    let mut desk = Desk::signed_in("draft-both-reads");
    desk.load(FIRST);
    desk.edit(json!([band()]), json!([]), Value::Null);
    assert_eq!(desk.choose(NEXT)["action"], "fetch");
    let (ticket, effect) = desk.fetch(NEXT);
    assert_eq!(
        desk.reply(&effect, &offline(), &Value::Null)["action"],
        "load_failed"
    );
    assert_eq!(desk.view("week_start"), FIRST);
    assert_eq!(desk.view("blocks"), json!([band()]));
    assert_eq!(desk.view("meta")["parked_count"], 0);
    desk.idle(ticket);

    desk.load(NEXT);
    assert_eq!(desk.view("meta")["parked_held"], FIRST);
    let restored = desk.choose(FIRST);
    assert_eq!(restored["action"], "restore");
    assert_eq!(restored["selection"]["selected_block_id"], "band");
    assert_eq!(desk.view("blocks"), json!([band()]));
    assert_eq!(desk.view("meta")["parked_count"], 0);
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
}

#[test]
fn leaving_reopens_and_saves_each_parked_draft_in_order() {
    let mut desk = Desk::signed_in("leaving-parked-drafts");
    desk.load(NEXT);
    desk.edit(json!([band()]), json!([]), Value::Null);
    desk.load(FIRST);
    desk.edit(json!([band()]), json!([]), Value::Null);
    desk.load("2026-11-16");

    let start =
        json!({ "cmd": "drafts_leaving_start", "limit_ms": 5000, "again": "close FlexWeek again" });
    assert_eq!(desk.send(start.clone())["waiting"], true);

    let poll = json!({ "cmd": "drafts_leaving_poll", "poll_ms": 100 });
    for (expected, operation) in [(NEXT, "save-next"), (FIRST, "save-first")] {
        let action = desk.send(poll.clone());
        assert_eq!(action["step"], "load");
        assert_eq!(action["week"], expected);
        assert_eq!(
            desk.choose(action["week"].as_str().unwrap())["action"],
            "restore"
        );
        assert_eq!(desk.send(poll.clone())["step"], "save");
        desk.save_to_store(operation);
        assert_eq!(desk.stored(expected)["blocks"][0]["id"], "band");
    }
    assert_eq!(desk.send(poll)["step"], "leave");
    assert_eq!(desk.send(start)["waiting"], false);
}

#[test]
fn giving_up_after_a_failed_save_keeps_the_retry_and_the_parked_draft() {
    let mut desk = Desk::signed_in("leaving-keeps-drafts");
    desk.load(FIRST);
    desk.edit(json!([band()]), json!([]), Value::Null);
    desk.load(NEXT);
    let open_block = json!({
        "id": "club", "title": "Club", "kind": "locked", "days": [0], "start": "15:00", "duration_min": 45,
    });
    desk.edit(json!([open_block]), json!([]), Value::Null);

    let start =
        json!({ "cmd": "drafts_leaving_start", "limit_ms": 5000, "again": "sign out again" });
    assert_eq!(desk.send(start)["waiting"], true);
    let poll = json!({ "cmd": "drafts_leaving_poll", "poll_ms": 100 });
    assert_eq!(desk.send(poll.clone())["step"], "save");
    desk.save("unsaved-club", false);
    let (ticket, effect) = desk.post();
    assert_eq!(desk.send(poll.clone())["step"], "wait");
    assert_eq!(
        desk.reply(&effect, &offline(), &Value::Null)["action"],
        "save_failed"
    );
    desk.idle(ticket);

    let pending = desk.view("pending_save");
    assert_eq!(pending["operation_id"], "unsaved-club");
    let action = desk.send(poll);
    assert_eq!(action["step"], "give_up");
    assert_eq!(
        action["words"],
        "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then sign out again."
    );
    assert_eq!(desk.view("week_start"), NEXT);
    assert_eq!(desk.view("blocks"), json!([open_block]));
    assert_eq!(desk.view("pending_save"), pending);
    assert_eq!(desk.view("meta")["parked_held"], FIRST);
    assert_eq!(desk.choose(FIRST)["action"], "restore");
    assert_eq!(desk.view("blocks"), json!([band()]));
    assert_eq!(desk.stored(NEXT)["blocks"], json!([]));
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
}

#[test]
fn a_lost_answer_retries_one_frozen_body_and_a_failed_undo_keeps_its_step() {
    let mut desk = Desk::signed_in("draft-retry-and-undo");
    desk.load(FIRST);
    desk.edit(json!([band()]), json!([]), Value::Null);
    desk.save("first-save", true);
    let (ticket, first) = desk.post();
    assert_eq!(desk.request(&first)["ok"], true);
    let failure = desk.reply(&first, &offline(), &Value::Null);
    assert_eq!(failure["action"], "save_failed");
    assert!(
        failure["words"]
            .as_str()
            .unwrap()
            .contains("Choose Retry save.")
    );
    desk.idle(ticket);

    desk.save("ignored-next-id", false);
    let (ticket, retry) = desk.post();
    assert_eq!(retry["body"], first["body"]);
    assert_ne!(retry["id"], first["id"]);
    let answer = desk.carry(&retry, &Value::Null);
    assert_eq!(answer["action"], "saved");
    assert_eq!(answer["planned"], true);
    desk.idle(ticket);
    assert_eq!(desk.stored(FIRST)["revision"], 1);
    let head = desk.view("last_step");
    assert!(head["token"].is_number());

    desk.undo();
    desk.save("unsent-undo", false);
    let (ticket, undo) = desk.post();
    desk.reply(&undo, &offline(), &Value::Null);
    desk.idle(ticket);
    assert_eq!(desk.view("last_step"), head);
    assert_eq!(desk.view("blocks")[0]["id"], "band");
    assert_eq!(desk.view("pending_save"), Value::Null);

    desk.undo();
    desk.save_to_store("undo-again");
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
    assert_eq!(desk.view("redo").as_array().unwrap().len(), 1);
}

#[test]
fn deleting_homework_keeps_other_weeks_for_undo() {
    let mut desk = Desk::signed_in("draft-delete-read-back");
    desk.load(FIRST);
    desk.edit(
        json!([essay("first-session")]),
        json!([homework()]),
        Value::Null,
    );
    desk.save_to_store("save-first-session");
    desk.load(NEXT);
    desk.edit(json!([essay("second-session")]), json!([]), Value::Null);
    desk.save_to_store("save-second-session");

    let (ticket, delete) = desk.start_delete();
    let answer = desk.carry(&delete, &Value::Null);
    desk.end_delete(ticket, answer);
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
    assert_eq!(desk.stored(NEXT)["blocks"], json!([]));
    desk.undo();
    desk.save_to_store("undo-delete");
    assert_eq!(desk.stored(FIRST)["blocks"][0]["id"], "first-session");
    assert_eq!(desk.stored(NEXT)["blocks"][0]["id"], "second-session");
    assert_eq!(desk.view("assignments")["essay"]["title"], "Essay");
}

#[test]
fn deleting_elsewhere_renews_a_parked_retry_and_prunes_its_trace_and_history() {
    let mut desk = Desk::signed_in("draft-delete-parked");
    desk.load(FIRST);
    desk.edit(
        json!([essay("first-session")]),
        json!([homework()]),
        Value::Null,
    );
    desk.save_to_store("save-essay");
    desk.edit(
        json!([essay("first-session"), band()]),
        json!([]),
        json!({ "placed": [essay("first-session"), band()] }),
    );
    desk.save("parked-original", false);
    let (ticket, parked) = desk.post();
    desk.reply(&parked, &offline(), &Value::Null);
    desk.idle(ticket);
    desk.load(NEXT);

    let (ticket, delete) = desk.start_delete();
    let answer = desk.carry(&delete, &Value::Null);
    desk.end_delete(ticket, answer);
    desk.load(FIRST);
    assert_eq!(desk.view("assignments"), json!({}));
    assert_eq!(desk.view("trace")["placed"], json!([band()]));
    assert_eq!(desk.view("undo"), json!([]));
    desk.save("unused-retry-id", false);
    let (ticket, retry) = desk.post();
    assert_eq!(retry["body"]["operation_id"], "renewed-parked-save");
    assert_eq!(retry["body"]["weeks"][0]["revision"], 2);
    assert_eq!(desk.carry(&retry, &Value::Null)["action"], "saved");
    desk.idle(ticket);
    assert_eq!(desk.stored(FIRST)["blocks"][0]["id"], "band");

    desk.undo();
    desk.save_to_store("undo-band");
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
    assert_eq!(desk.view("assignments"), json!({}));
}

#[test]
fn an_answer_from_an_old_ticket_or_account_does_not_change_the_week() {
    let mut desk = Desk::signed_in("draft-late-reply");
    desk.load(FIRST);
    let (_, read) = desk.fetch(NEXT);
    let landed = desk.request(&read);
    let newer = desk.ticket();
    assert_eq!(desk.reply(&read, &landed, &Value::Null)["action"], "ignore");
    assert_eq!(desk.view("week_start"), FIRST);
    desk.idle(newer);

    let (_, read) = desk.fetch(NEXT);
    let landed = desk.request(&read);
    let frame: Value = serde_json::from_str(&desk.session.view("frame")).unwrap();
    desk.send(json!({ "cmd": "set_account", "id": frame["account"]["id"], "username": "ana" }));
    assert_eq!(desk.reply(&read, &landed, &Value::Null)["action"], "ignore");
    assert_eq!(desk.view("week_start"), FIRST);

    let (_, read) = desk.fetch(NEXT);
    let landed = desk.request(&read);
    desk.send(json!({ "cmd": "set_account", "id": 2, "username": "bo" }));
    assert_eq!(desk.reply(&read, &landed, &Value::Null)["action"], "ignore");
    assert_eq!(desk.view("week_start"), "");
}

#[test]
fn a_wednesday_week_can_save_three_edits_and_undo_each_without_a_conflict() {
    let mut desk = Desk::signed_in("draft-shifted-undo");
    desk.first_weekday = 2;
    desk.load("2026-11-04");
    assert_eq!(desk.view("revision"), json!([0, 0]));
    let mut first = band();
    first["days"] = json!([0]);
    let mut second = band();
    second["id"] = json!("later");
    second["days"] = json!([5]);
    let mut third = first.clone();
    third["title"] = json!("Band rehearsal");
    for (blocks, id) in [
        (json!([first]), "add-first"),
        (json!([first, second]), "add-second"),
        (json!([third, second]), "rename-first"),
    ] {
        desk.edit(blocks, json!([]), Value::Null);
        desk.save_to_store(id);
        assert_eq!(desk.view("revision").as_array().unwrap().len(), 2);
        assert_eq!(desk.view("conflict"), false);
    }
    assert_eq!(desk.stored(FIRST)["blocks"][0]["title"], "Band rehearsal");
    assert_eq!(desk.stored(NEXT)["blocks"][0]["id"], "later");

    desk.undo();
    desk.save_to_store("undo-rename");
    assert_eq!(desk.stored(FIRST)["blocks"][0]["title"], "Band");
    assert_eq!(desk.stored(NEXT)["blocks"][0]["id"], "later");
    desk.undo();
    desk.save_to_store("undo-later");
    assert_eq!(desk.stored(FIRST)["blocks"][0]["id"], "band");
    assert_eq!(desk.stored(NEXT)["blocks"], json!([]));
    desk.undo();
    desk.save_to_store("undo-first");
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
    assert_eq!(desk.view("redo").as_array().unwrap().len(), 3);
}

#[test]
fn a_malformed_week_reply_can_still_finish_as_a_read_failure() {
    let mut desk = Desk::signed_in("draft-unreadable-answer");
    desk.load(FIRST);
    let (ticket, effect) = desk.fetch(NEXT);
    let malformed = json!({
        "cmd": "drafts_reply", "effect_id": effect["id"], "data": { "assignments": "not rows" },
    });
    let rejected: Value = serde_json::from_str(&desk.session.send(&malformed.to_string())).unwrap();
    assert_eq!(rejected["ok"], false);
    assert_eq!(
        desk.reply(&effect, &offline(), &Value::Null)["action"],
        "load_failed"
    );
    desk.idle(ticket);
    assert_eq!(desk.view("week_start"), FIRST);
    assert_eq!(desk.view("meta")["parked_count"], 0);
}

#[test]
fn a_failed_delete_read_back_still_leaves_an_undo_for_the_homework() {
    let mut desk = Desk::signed_in("draft-delete-read-refused");
    desk.load(FIRST);
    desk.edit(
        json!([essay("first-session")]),
        json!([homework()]),
        Value::Null,
    );
    desk.save_to_store("first-session");
    desk.load(NEXT);
    desk.edit(json!([essay("second-session")]), json!([]), Value::Null);
    desk.save_to_store("second-session");

    let (ticket, delete) = desk.start_delete();
    let answer = desk.carry(&delete, &Value::Null);
    assert_eq!(
        answer["effect"]["path"],
        format!("/api/week?week_start={FIRST}")
    );
    let failed_read = desk.reply(&answer["effect"], &offline(), &Value::Null);
    desk.end_delete(ticket, failed_read);
    desk.undo();
    desk.save_to_store("undo-delete");
    assert_eq!(desk.view("assignments")["essay"]["title"], "Essay");
    assert_eq!(desk.stored(NEXT)["blocks"][0]["id"], "second-session");
    assert_eq!(desk.stored(FIRST)["blocks"], json!([]));
}

#[test]
fn fixture_fields_are_saved_through_the_same_draft_and_retry_path() {
    let mut desk = Desk::signed_in("draft-fixture-fields");
    desk.load(FIRST);
    desk.send(json!({
        "cmd": "drafts_set", "fields": {
            "blocks": [essay("first-session")], "assignments": { "essay": homework() },
            "dirty_assignments": ["essay", "essay"], "dirty": true,
        },
    }));
    assert_eq!(desk.view("dirty_assignments"), json!(["essay"]));
    desk.save_to_store("fixture-save");
    assert_eq!(desk.stored(FIRST)["blocks"][0]["assignment_id"], "essay");
    assert_eq!(desk.view("assignments")["essay"]["revision"], 1);
    assert_eq!(desk.view("dirty_assignments"), json!([]));
}

#[test]
fn a_phone_change_cannot_replace_even_an_empty_held_batch() {
    let mut desk = Desk::signed_in("draft-empty-pending");
    desk.load(FIRST);
    desk.send(json!({ "cmd": "drafts_set", "fields": { "pending_save": {} } }));
    let decision = desk.send(json!({
        "cmd": "drafts_remote_change", "signed_in": true, "who": "your phone",
    }));
    assert_eq!(decision["accepted"], true);
    assert_eq!(decision["conflict"], true);
    assert_eq!(decision["words"], Value::Null);
    assert_eq!(desk.view("pending_save"), json!({}));
}
