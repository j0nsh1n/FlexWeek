//! Day, week and month navigation (P4 slice 10A). Expected values come from controller.py's rules
//! and the desktop tests that pin them: a picked day stays when its month closes, a week without
//! today opens on Thursday, and a new view arms no category.

use flexweek_app::session::views::{
    ViewAnswer, ViewEffect, ViewReply, ViewState, ViewWorld, today_column,
};
use flexweek_engine::desk::grid::shifted_month;
use serde_json::{Value, json};

const TODAY: &str = "2026-09-29";
const ACCOUNT: &str = "A";

fn world<'a>(
    signed_in: bool,
    account: Option<&'a str>,
    week_start: &'a str,
    today: &'a str,
) -> ViewWorld<'a> {
    ViewWorld {
        signed_in,
        account_id: account,
        week_start,
        today,
        busy: false,
        held: false,
        parked: false,
    }
}

fn signed<'a>(week_start: &'a str, today: &'a str) -> ViewWorld<'a> {
    world(true, Some(ACCOUNT), week_start, today)
}

fn fresh(today: &str) -> ViewState {
    ViewState::new(today.to_string())
}

fn month_body(month: &str) -> Value {
    json!({"month": month, "days": []})
}

fn ok_reply<'a>(
    kind: &'a str,
    token: i64,
    asked: &'a str,
    generation: i64,
    owner: &'a str,
    account_id: Option<&'a str>,
    data: Option<&'a Value>,
) -> ViewReply<'a> {
    ViewReply {
        kind,
        token,
        asked,
        generation,
        owner,
        account_id,
        data,
        error: None,
    }
}

fn err_reply<'a>(
    kind: &'a str,
    token: i64,
    asked: &'a str,
    generation: i64,
    owner: &'a str,
    account_id: Option<&'a str>,
    error: &'a str,
) -> ViewReply<'a> {
    ViewReply {
        kind,
        token,
        asked,
        generation,
        owner,
        account_id,
        data: None,
        error: Some(error),
    }
}

#[test]
fn a_new_view_arms_no_category() {
    let view = fresh("2026-11-05");
    assert_eq!(view.armed_category, None);
    assert_eq!(view.planner_view, "week");
    assert_eq!(view.selected_day, "2026-11-05");
    assert_eq!(view.selected_month, None);
    assert_eq!(view.first_weekday, 0);
    assert!(!view.refollow_week);
    assert_eq!(view.day_ticket, 0);
    assert_eq!(view.month_ticket, 0);
    assert_eq!(view.month_gen, 0);
}

#[test]
fn today_column_counts_from_the_open_weeks_first_day() {
    // Wednesday 4 November 2026: Thursday is the second day, the next Wednesday is not in it.
    assert_eq!(today_column("2026-11-05", "2026-11-04"), Some(1));
    assert_eq!(today_column("2026-11-10", "2026-11-04"), Some(6));
    assert_eq!(today_column("2026-11-11", "2026-11-04"), None);
    // Sunday 1 November: Thursday 5 November is the fifth day.
    assert_eq!(today_column("2026-11-05", "2026-11-01"), Some(4));
    assert_eq!(today_column("not-a-date", "2026-11-04"), None);
}

#[test]
fn month_keeps_a_picked_day_when_leaving_the_month() {
    // Clock Tuesday 29 September 2026. Wednesday 30 September is picked, the month opens on that
    // day, and closing the month back to Day keeps Wednesday rather than snapping to today.
    let mut view = fresh(TODAY);
    let here = signed("2026-09-28", TODAY);
    let opened = view.open_day("2026-09-30", &here).unwrap();
    assert_eq!(opened.load_week, None);
    assert!(opened.emit);
    assert_eq!(opened.request.unwrap().path, "/api/day?date=2026-09-30");
    view.open_month(None, &here).unwrap();
    assert_eq!(view.selected_day, "2026-09-30");
    assert_eq!(view.selected_month.as_deref(), Some("2026-09"));
    let back = view.set_view("day", &here).unwrap();
    assert_eq!(view.selected_day, "2026-09-30");
    assert_eq!(view.planner_view, "day");
    assert_eq!(back.load_week, None);
    assert!(back.emit);
}

#[test]
fn a_week_without_today_opens_its_thursday() {
    let mut view = fresh(TODAY);
    view.selected_day = "2026-09-30".to_string();
    view.planner_view = "week".to_string();
    let later = signed("2026-10-26", TODAY);
    let opened = view.open_month(None, &later).unwrap();
    assert_eq!(view.selected_day, "2026-10-29");
    assert_eq!(view.selected_month.as_deref(), Some("2026-10"));
    assert_eq!(opened.request.unwrap().path, "/api/month?month=2026-10");
}

#[test]
fn open_day_in_another_week_loads_that_week_and_does_not_ask_or_redraw() {
    let mut view = fresh("2026-11-05");
    view.first_weekday = 2;
    let here = signed("2026-11-11", "2026-11-05");
    let stayed = view.open_day("2026-11-17", &here).unwrap();
    assert_eq!(stayed.load_week, None);
    assert!(stayed.request.is_some());
    assert_eq!(view.selected_day, "2026-11-17");
    assert_eq!(view.planner_view, "day");
    let moved = view.open_day("2026-11-30", &here).unwrap();
    assert_eq!(moved.load_week.as_deref(), Some("2026-11-25"));
    assert!(moved.request.is_none());
    assert!(!moved.emit);
    assert_eq!(view.selected_day, "2026-11-30");
    assert_eq!(view.planner_view, "day");
    assert_eq!(view.day_data, None);
}

#[test]
fn open_day_ignores_a_signed_out_session_and_a_date_that_is_not_real() {
    let mut view = fresh("2026-11-05");
    let out = world(false, None, "2026-11-02", "2026-11-05");
    assert_eq!(
        view.open_day("2026-11-05", &out).unwrap(),
        ViewEffect::none()
    );
    assert_eq!(view.planner_view, "week");
    let mut signed_in = fresh("2026-11-05");
    let here = signed("2026-11-02", "2026-11-05");
    assert_eq!(
        signed_in.open_day("2026-02-31", &here).unwrap(),
        ViewEffect::none()
    );
    assert_eq!(signed_in.selected_day, "2026-11-05");
    assert_eq!(signed_in.planner_view, "week");
    let error = signed_in.open_day("20261105", &here).unwrap_err();
    assert_eq!(error, "date must be written YYYY-MM-DD");
    assert_eq!(signed_in.selected_day, "2026-11-05");
}

#[test]
fn set_view_refuses_an_unknown_name_and_a_signed_out_session() {
    let mut view = fresh("2026-11-05");
    let here = signed("2026-11-02", "2026-11-05");
    assert_eq!(view.set_view("year", &here).unwrap(), ViewEffect::none());
    assert_eq!(view.planner_view, "week");
    let out = world(false, None, "2026-11-02", "2026-11-05");
    assert_eq!(view.set_view("day", &out).unwrap(), ViewEffect::none());
    assert_eq!(view.planner_view, "week");
}

#[test]
fn set_view_week_from_day_redraws_without_asking() {
    let mut view = fresh("2026-11-05");
    let here = signed("2026-11-02", "2026-11-05");
    view.set_view("day", &here).unwrap();
    let back = view.set_view("week", &here).unwrap();
    assert_eq!(view.planner_view, "week");
    assert!(back.request.is_none());
    assert!(back.emit);
}

#[test]
fn leaving_a_month_with_no_month_only_switches_the_view() {
    let mut view = fresh(TODAY);
    view.planner_view = "month".to_string();
    view.selected_month = None;
    let effect = view.set_view("week", &signed("2026-09-28", TODAY)).unwrap();
    assert_eq!(view.planner_view, "week");
    assert_eq!(view.selected_day, TODAY);
    assert!(effect.emit);
    assert!(effect.load_week.is_none());
    assert!(effect.request.is_none());
}

#[test]
fn shift_month_walks_inside_the_kept_years_and_stops_at_the_edge() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    view.open_month(Some("2026-10"), &here).unwrap();
    let next = view.shift_month(1, &here).unwrap();
    assert_eq!(view.selected_month.as_deref(), Some("2026-11"));
    assert_eq!(view.month_data, None);
    assert_eq!(next.request.unwrap().asked, "2026-11");
    view.selected_month = Some("2099-12".to_string());
    let stayed = view.shift_month(1, &here).unwrap();
    assert_eq!(stayed, ViewEffect::none());
    assert_eq!(view.selected_month.as_deref(), Some("2099-12"));
    view.selected_month = Some("2000-01".to_string());
    assert_eq!(view.shift_month(-1, &here).unwrap(), ViewEffect::none());
    assert_eq!(view.selected_month.as_deref(), Some("2000-01"));
    view.planner_view = "week".to_string();
    assert_eq!(view.shift_month(1, &here).unwrap(), ViewEffect::none());
}

#[test]
fn shift_month_passes_on_a_month_the_engine_refuses() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    view.planner_view = "month".to_string();
    view.selected_month = Some("nope".to_string());
    let error = view.shift_month(1, &here).unwrap_err();
    assert_eq!(error, shifted_month("nope", 1).unwrap_err().message);
    assert_eq!(view.selected_month.as_deref(), Some("nope"));
}

#[test]
fn an_empty_month_is_not_a_month_and_a_named_one_is_kept() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    view.open_month(Some(""), &here).unwrap();
    assert_eq!(view.selected_month.as_deref(), Some("2026-10"));
    view.planner_view = "week".to_string();
    view.open_month(Some("2026-12"), &here).unwrap();
    assert_eq!(view.selected_month.as_deref(), Some("2026-12"));
    view.selected_month = Some(String::new());
    let fetched = view.fetch_month(&here);
    assert!(fetched.request.is_none());
}

#[test]
fn prefetch_asks_for_the_thursdays_month_once() {
    let mut view = fresh("2026-10-15");
    let monday = signed("2026-10-12", "2026-10-15");
    let first = view.prefetch(&monday).unwrap();
    let request = first.request.unwrap();
    assert_eq!(request.kind, "prefetch");
    assert_eq!(request.method, "GET");
    assert_eq!(request.path, "/api/month?month=2026-10");
    assert_eq!(request.token, 0);
    assert_eq!(request.asked, "2026-10");
    assert_eq!(request.owner, ACCOUNT);
    assert!(view.month_data.is_none());
    assert_eq!(view.prefetch(&monday).unwrap(), ViewEffect::none());
    view.first_weekday = 2;
    view.clear_prefetch();
    let wednesday = signed("2026-10-14", "2026-10-15");
    let again = view.prefetch(&wednesday).unwrap();
    assert_eq!(
        again.request.unwrap().path,
        "/api/month?month=2026-10&first_day=2"
    );
}

#[test]
fn prefetch_skips_a_month_already_kept_and_stores_only_a_matching_answer() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    view.insert_cache(
        ACCOUNT.to_string(),
        "2026-10".to_string(),
        month_body("2026-10"),
    );
    assert_eq!(view.prefetch(&here).unwrap(), ViewEffect::none());
    view.clear_cache();
    let request = view.prefetch(&here).unwrap().request.unwrap();
    let wrong = month_body("2026-11");
    view.view_reply(ok_reply(
        "prefetch",
        0,
        &request.asked,
        request.generation,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&wrong),
    ));
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
    assert!(!view.prefetching(ACCOUNT, "2026-10"));
    view.prefetch(&here).unwrap();
    let other = month_body("2026-10");
    view.view_reply(ok_reply(
        "prefetch",
        0,
        "2026-10",
        0,
        ACCOUNT,
        Some("B"),
        Some(&other),
    ));
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
    view.month_gen = 3;
    view.prefetch(&here).unwrap();
    view.month_gen = 4;
    view.view_reply(ok_reply(
        "prefetch",
        0,
        "2026-10",
        3,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&other),
    ));
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
    view.prefetch(&here).unwrap();
    view.view_reply(ok_reply(
        "prefetch",
        0,
        "2026-10",
        view.month_gen,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&other),
    ));
    assert_eq!(
        view.month_cached(ACCOUNT, "2026-10").unwrap()["month"],
        json!("2026-10")
    );
    view.add_prefetch(ACCOUNT.to_string(), "2026-11".to_string());
    view.view_reply(err_reply(
        "prefetch",
        0,
        "2026-11",
        view.month_gen,
        ACCOUNT,
        Some(ACCOUNT),
        "offline",
    ));
    assert!(!view.prefetching(ACCOUNT, "2026-11"));
    assert!(!view.cache_contains(ACCOUNT, "2026-11"));
}

#[test]
fn a_kept_month_is_shown_at_once_and_the_fresh_answer_replaces_it() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    let kept = json!({"month": "2026-10", "days": [], "fresh": false});
    view.insert_cache(ACCOUNT.to_string(), "2026-10".to_string(), kept.clone());
    view.open_month(Some("2026-10"), &here).unwrap();
    let fetched = view.fetch_month(&here);
    assert!(fetched.emit_before_request);
    assert_eq!(view.month_data, Some(kept));
    assert_eq!(view.month_data_gen, 0);
    let request = fetched.request.unwrap();
    assert_eq!(request.token, view.month_ticket);
    assert_eq!(request.generation, 0);
    let fresh_body = json!({"month": "2026-10", "days": [], "fresh": true});
    let answer = view.view_reply(ok_reply(
        "month",
        request.token,
        "2026-10",
        0,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&fresh_body),
    ));
    assert!(answer.emit);
    assert_eq!(answer.say, None);
    assert_eq!(view.month_data, Some(fresh_body.clone()));
    assert_eq!(view.month_cached(ACCOUNT, "2026-10"), Some(&fresh_body));
}

#[test]
fn a_held_or_parked_week_does_not_show_the_kept_month_but_still_asks() {
    let mut view = fresh("2026-10-15");
    view.insert_cache(
        ACCOUNT.to_string(),
        "2026-10".to_string(),
        month_body("2026-10"),
    );
    view.planner_view = "month".to_string();
    view.selected_month = Some("2026-10".to_string());
    let mut held = signed("2026-10-12", "2026-10-15");
    held.held = true;
    let fetched = view.fetch_month(&held);
    assert!(!fetched.emit_before_request);
    assert!(view.month_data.is_none());
    assert!(fetched.request.is_some());
    let mut parked = signed("2026-10-12", "2026-10-15");
    parked.parked = true;
    let again = view.fetch_month(&parked);
    assert!(!again.emit_before_request);
    assert!(again.request.is_some());
}

#[test]
fn a_month_answer_from_an_older_generation_or_another_month_is_dropped() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    view.open_month(Some("2026-10"), &here).unwrap();
    let first = view.month_ticket;
    view.invalidate_months();
    let body = month_body("2026-10");
    let stale = view.view_reply(ok_reply(
        "month",
        first,
        "2026-10",
        0,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&body),
    ));
    assert_eq!(stale, ViewAnswer::quiet());
    assert!(view.month_data.is_none());
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
    let request = view.fetch_month(&here).request.unwrap();
    view.selected_month = Some("2026-11".to_string());
    view.view_reply(ok_reply(
        "month",
        request.token,
        "2026-10",
        request.generation,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&body),
    ));
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
    view.selected_month = Some("2026-10".to_string());
    view.planner_view = "week".to_string();
    view.view_reply(ok_reply(
        "month",
        request.token,
        "2026-10",
        request.generation,
        ACCOUNT,
        Some(ACCOUNT),
        Some(&body),
    ));
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
}

#[test]
fn a_month_failure_is_said_when_the_ticket_and_generation_still_match() {
    let mut view = fresh("2026-10-15");
    let here = signed("2026-10-12", "2026-10-15");
    let request = view
        .open_month(Some("2026-10"), &here)
        .unwrap()
        .request
        .unwrap();
    view.planner_view = "week".to_string();
    let said = view.view_reply(err_reply(
        "month",
        request.token,
        "2026-10",
        request.generation,
        ACCOUNT,
        Some(ACCOUNT),
        "The planner is unavailable.",
    ));
    assert_eq!(said.say.as_deref(), Some("The planner is unavailable."));
    assert!(said.emit);
    view.invalidate_months();
    let quiet = view.view_reply(err_reply(
        "month",
        request.token,
        "2026-10",
        request.generation,
        ACCOUNT,
        Some(ACCOUNT),
        "The planner is unavailable.",
    ));
    assert_eq!(quiet.say, None);
    assert!(!quiet.emit);
}

#[test]
fn a_day_answer_lands_only_for_the_day_still_open() {
    let mut view = fresh("2026-11-05");
    let here = signed("2026-11-02", "2026-11-05");
    let request = view.open_day("2026-11-05", &here).unwrap().request.unwrap();
    assert_eq!(request.kind, "day");
    assert_eq!(request.token, 1);
    let body = json!({"date": "2026-11-05"});
    view.selected_day = "2026-11-06".to_string();
    let ignored = view.view_reply(ok_reply(
        "day",
        request.token,
        "2026-11-05",
        0,
        "",
        Some(ACCOUNT),
        Some(&body),
    ));
    assert!(!ignored.emit);
    assert!(view.day_data.is_none());
    view.selected_day = "2026-11-05".to_string();
    view.planner_view = "week".to_string();
    assert!(
        !view
            .view_reply(ok_reply(
                "day",
                request.token,
                "2026-11-05",
                0,
                "",
                Some(ACCOUNT),
                Some(&body)
            ))
            .emit
    );
    view.planner_view = "day".to_string();
    let landed = view.view_reply(ok_reply(
        "day",
        request.token,
        "2026-11-05",
        0,
        "",
        Some(ACCOUNT),
        Some(&body),
    ));
    assert!(landed.emit);
    assert_eq!(view.day_data, Some(body));
}

#[test]
fn a_day_failure_redraws_when_its_ticket_matches_even_if_the_view_changed() {
    let mut view = fresh("2026-11-05");
    let here = signed("2026-11-02", "2026-11-05");
    let request = view.open_day("2026-11-05", &here).unwrap().request.unwrap();
    view.planner_view = "week".to_string();
    let failed = view.view_reply(err_reply(
        "day",
        request.token,
        "2026-11-05",
        0,
        "",
        Some(ACCOUNT),
        "offline",
    ));
    assert!(failed.emit);
    assert_eq!(failed.say, None);
    let stale = view.view_reply(err_reply(
        "day",
        request.token - 1,
        "2026-11-05",
        0,
        "",
        Some(ACCOUNT),
        "offline",
    ));
    assert!(!stale.emit);
}

#[test]
fn follow_first_weekday_reopens_the_week_that_holds_the_selected_day() {
    let mut view = fresh("2026-11-05");
    view.selected_day = "2026-11-05".to_string();
    let here = signed("2026-11-02", "2026-11-05");
    view.insert_cache(
        ACCOUNT.to_string(),
        "2026-11".to_string(),
        month_body("2026-11"),
    );
    let followed = view.follow_first_weekday(2, &here).unwrap();
    assert_eq!(view.first_weekday, 2);
    assert!(!view.cache_contains(ACCOUNT, "2026-11"));
    assert_eq!(view.month_gen, 1);
    assert!(followed.rebase_focus);
    assert_eq!(followed.load_week.as_deref(), Some("2026-11-04"));
    assert!(followed.emit);
    assert!(!view.refollow_week);
    assert_eq!(view.selected_day, "2026-11-05");
    let sunday_week = signed("2026-11-04", "2026-11-05");
    let sunday = view.follow_first_weekday(6, &sunday_week).unwrap();
    assert_eq!(sunday.load_week.as_deref(), Some("2026-11-01"));
}

#[test]
fn follow_while_busy_or_held_waits_and_the_same_weekday_does_not_move() {
    let mut view = fresh("2026-11-05");
    let mut busy = signed("2026-11-02", "2026-11-05");
    busy.busy = true;
    let waited = view.follow_first_weekday(2, &busy).unwrap();
    assert!(waited.load_week.is_none());
    assert!(view.refollow_week);
    assert!(waited.rebase_focus);
    let mut held = signed("2026-11-02", "2026-11-05");
    held.held = true;
    assert_eq!(view.follow_week(&held).unwrap(), ViewEffect::none());
    assert!(view.refollow_week);
    let free = view
        .follow_week(&signed("2026-11-02", "2026-11-05"))
        .unwrap();
    assert_eq!(free.load_week.as_deref(), Some("2026-11-04"));
    assert!(!view.refollow_week);
    let again = view
        .follow_first_weekday(2, &signed("2026-11-04", "2026-11-05"))
        .unwrap();
    assert!(again.load_week.is_none());
    assert!(!again.rebase_focus);
    assert!(!view.refollow_week);
    assert!(again.emit);
    assert_eq!(view.month_gen, 2);
}

#[test]
fn signed_out_follow_moves_the_draft_week_and_does_not_refollow() {
    let mut view = fresh("2026-11-05");
    let out = world(false, None, "2026-11-02", "2026-11-05");
    let effect = view.follow_first_weekday(2, &out).unwrap();
    assert_eq!(effect.set_week_start.as_deref(), Some("2026-11-04"));
    assert!(!effect.rebase_focus);
    assert!(effect.load_week.is_none());
    assert!(effect.emit);
    assert!(!view.refollow_week);
    assert_eq!(view.first_weekday, 2);
    assert_eq!(view.month_gen, 1);
}

#[test]
fn ensure_selected_day_maps_the_weekday_onto_the_open_week() {
    let mut view = fresh(TODAY);
    view.selected_day = "2026-09-30".to_string();
    view.ensure_selected_day("2026-10-26").unwrap();
    assert_eq!(view.selected_day, "2026-10-28");
    view.ensure_selected_day("2026-10-26").unwrap();
    assert_eq!(view.selected_day, "2026-10-28");
    view.selected_day = "nope".to_string();
    view.ensure_selected_day("2026-10-26").unwrap();
    assert_eq!(view.selected_day, "2026-10-26");
}

#[test]
fn invalidate_months_drops_what_was_kept_and_not_what_is_being_asked_ahead() {
    let mut view = fresh("2026-10-15");
    view.insert_cache(
        ACCOUNT.to_string(),
        "2026-10".to_string(),
        month_body("2026-10"),
    );
    view.add_prefetch(ACCOUNT.to_string(), "2026-10".to_string());
    view.invalidate_months();
    assert!(!view.cache_contains(ACCOUNT, "2026-10"));
    assert!(view.prefetching(ACCOUNT, "2026-10"));
    assert_eq!(view.month_gen, 1);
}

#[test]
fn an_effect_names_every_step_the_window_applies() {
    let effect = ViewEffect::none().to_json();
    for key in [
        "set_week_start",
        "rebase_focus",
        "load_week",
        "emit_before_request",
        "request",
        "emit",
    ] {
        assert!(effect.get(key).is_some(), "{key}");
    }
    assert!(effect["set_week_start"].is_null());
    assert!(effect["request"].is_null());
    assert_eq!(effect["emit"], json!(false));
}

#[test]
fn monday_start_omits_the_first_day_the_server_already_uses() {
    let view = fresh("2026-10-15");
    assert_eq!(view.month_path("2026-10"), "/api/month?month=2026-10");
    let mut wednesday = view;
    wednesday.first_weekday = 2;
    assert_eq!(
        wednesday.month_path("2026-10"),
        "/api/month?month=2026-10&first_day=2"
    );
}
