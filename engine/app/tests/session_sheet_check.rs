//! Unit tests for every `block_sheet_problem` and `homework_sheet_problem` message branch, plus
//! accept/refuse parity against the 2,500-block and 2,000-homework corpora.

use flexweek_app::session::sheet_check::{
    BLOCK_DAYS_PROBLEM, BLOCK_REFUSED, BLOCK_SPOTIFY_PROBLEM, BLOCK_TITLE_PROBLEM,
    HOMEWORK_CHECKLIST_LIMIT_PROBLEM, HOMEWORK_CHECKLIST_TEXT_PROBLEM,
    HOMEWORK_COMPLETED_AT_PROBLEM, HOMEWORK_COURSE_PROBLEM, HOMEWORK_DUE_PROBLEM,
    HOMEWORK_ENERGY_PROBLEM, HOMEWORK_ESTIMATE_PROBLEM, HOMEWORK_LINK_LABEL_PROBLEM,
    HOMEWORK_LINK_URL_PROBLEM, HOMEWORK_LINKS_LIMIT_PROBLEM, HOMEWORK_NOTES_PROBLEM,
    HOMEWORK_PRIORITY_PROBLEM, HOMEWORK_REFUSED, HOMEWORK_SPOTIFY_PROBLEM, HOMEWORK_TITLE_EMPTY,
    HOMEWORK_TITLE_LONG, block_sheet_problem, homework_sheet_problem,
};
use flexweek_engine::validate::{ASSIGNMENT_FIELDS, week_request};
use flexweek_service::homework_saves::check_homework;
use serde_json::{Map, Value, json};

fn valid_block() -> Value {
    json!({
        "id": "b1",
        "title": "Math",
        "kind": "locked",
        "duration_min": 60,
        "days": [0, 2],
        "start": "09:00",
    })
}

fn valid_homework() -> Value {
    json!({
        "id": "hw1",
        "title": "History essay",
        "due": "2026-11-28T23:59",
        "estimate_min": 60,
        "revision": 0,
    })
}

#[test]
fn valid_block_returns_none() {
    assert_eq!(block_sheet_problem(&valid_block()), None);
}

#[test]
fn block_title_empty_missing_and_too_long_return_title_problem() {
    let mut empty = valid_block();
    empty["title"] = json!("");
    assert_eq!(
        block_sheet_problem(&empty),
        Some(("title".into(), BLOCK_TITLE_PROBLEM.into()))
    );

    let mut long = valid_block();
    long["title"] = json!("x".repeat(81));
    assert_eq!(
        block_sheet_problem(&long),
        Some(("title".into(), BLOCK_TITLE_PROBLEM.into()))
    );

    let mut missing = valid_block();
    missing.as_object_mut().unwrap().shift_remove("title");
    assert_eq!(
        block_sheet_problem(&missing),
        Some(("title".into(), BLOCK_TITLE_PROBLEM.into()))
    );
}

#[test]
fn block_days_empty_out_of_range_and_non_int_return_days_problem() {
    for bad_days in [
        json!([]),
        json!([7]),
        json!([-1]),
        json!([0, 1, 2, 3, 4, 5, 6, 0]),
        json!(["mon"]),
        json!("not a list"),
    ] {
        let mut block = valid_block();
        block["days"] = bad_days.clone();
        assert_eq!(
            block_sheet_problem(&block),
            Some(("days".into(), BLOCK_DAYS_PROBLEM.into())),
            "days={bad_days}"
        );
    }
}

#[test]
fn block_spotify_url_invalid_returns_spotify_problem_and_empty_is_accepted() {
    let mut empty_spotify = valid_block();
    empty_spotify["spotify_url"] = json!("");
    assert_eq!(block_sheet_problem(&empty_spotify), None);

    let mut valid_spotify = valid_block();
    valid_spotify["spotify_url"] = json!("https://open.spotify.com/track/abc123");
    assert_eq!(block_sheet_problem(&valid_spotify), None);

    for bad in [
        json!("https://example.com/track/1"),
        json!("http://open.spotify.com/track/abc123"),
        json!("https://user:pass@open.spotify.com/track/abc123"),
        json!(123),
    ] {
        let mut block = valid_block();
        block["spotify_url"] = bad.clone();
        assert_eq!(
            block_sheet_problem(&block),
            Some(("spotify_url".into(), BLOCK_SPOTIFY_PROBLEM.into())),
            "spotify={bad}"
        );
    }
}

#[test]
fn block_precedence_prefers_title_over_days_and_spotify_even_when_id_also_fails() {
    let mut both = valid_block();
    both["id"] = json!("");
    both["title"] = json!("");
    both["days"] = json!([]);
    both["spotify_url"] = json!("bad");
    assert_eq!(
        block_sheet_problem(&both),
        Some(("title".into(), BLOCK_TITLE_PROBLEM.into()))
    );

    let mut days_and_spotify = valid_block();
    days_and_spotify["days"] = json!([]);
    days_and_spotify["spotify_url"] = json!("bad");
    assert_eq!(
        block_sheet_problem(&days_and_spotify),
        Some(("days".into(), BLOCK_DAYS_PROBLEM.into()))
    );
}

#[test]
fn block_week_request_and_other_field_failures_return_block_refused() {
    let mut past_midnight = valid_block();
    past_midnight["start"] = json!("23:30");
    past_midnight["duration_min"] = json!(60);
    assert_eq!(
        block_sheet_problem(&past_midnight),
        Some((String::new(), BLOCK_REFUSED.into()))
    );

    let mut dup_days = valid_block();
    dup_days["days"] = json!([1, 1]);
    assert_eq!(
        block_sheet_problem(&dup_days),
        Some((String::new(), BLOCK_REFUSED.into()))
    );

    let mut missing_start = valid_block();
    missing_start["start"] = Value::Null;
    assert_eq!(
        block_sheet_problem(&missing_start),
        Some((String::new(), BLOCK_REFUSED.into()))
    );

    let mut zero_duration = valid_block();
    zero_duration["duration_min"] = json!(0);
    assert_eq!(
        block_sheet_problem(&zero_duration),
        Some((String::new(), BLOCK_REFUSED.into()))
    );

    assert_eq!(
        block_sheet_problem(&json!("not an object")),
        Some((String::new(), BLOCK_REFUSED.into()))
    );
}

#[test]
fn valid_homework_and_extra_sheet_fields_return_none() {
    assert_eq!(homework_sheet_problem(&valid_homework()), None);

    let mut with_extras = valid_homework();
    with_extras["fixed_at"] = json!({"day": 2, "start": "16:00"});
    with_extras["planned_minutes"] = json!(30);
    assert_eq!(homework_sheet_problem(&with_extras), None);
}

#[test]
fn homework_title_distinguishes_empty_blank_and_too_long() {
    let mut empty = valid_homework();
    empty["title"] = json!("");
    assert_eq!(
        homework_sheet_problem(&empty),
        Some(("title".into(), HOMEWORK_TITLE_EMPTY.into()))
    );

    let mut blank = valid_homework();
    blank["title"] = json!("   \t\n");
    assert_eq!(
        homework_sheet_problem(&blank),
        Some(("title".into(), HOMEWORK_TITLE_EMPTY.into()))
    );

    let mut long = valid_homework();
    long["title"] = json!("a".repeat(81));
    assert_eq!(
        homework_sheet_problem(&long),
        Some(("title".into(), HOMEWORK_TITLE_LONG.into()))
    );

    let mut long_spaces = valid_homework();
    long_spaces["title"] = json!(" ".repeat(81));
    assert_eq!(
        homework_sheet_problem(&long_spaces),
        Some(("title".into(), HOMEWORK_TITLE_LONG.into()))
    );
}

#[test]
fn homework_every_named_field_returns_its_exact_message() {
    let cases: [(&str, Value, &str); 8] = [
        ("course", json!("c".repeat(41)), HOMEWORK_COURSE_PROBLEM),
        ("priority", json!(5), HOMEWORK_PRIORITY_PROBLEM),
        ("energy", json!("midnight"), HOMEWORK_ENERGY_PROBLEM),
        (
            "spotify_url",
            json!("https://example.com/song"),
            HOMEWORK_SPOTIFY_PROBLEM,
        ),
        ("due", json!("not-a-date"), HOMEWORK_DUE_PROBLEM),
        ("estimate_min", json!(20), HOMEWORK_ESTIMATE_PROBLEM),
        (
            "completed_at",
            json!("2026-11-26"),
            HOMEWORK_COMPLETED_AT_PROBLEM,
        ),
        ("notes", json!("n".repeat(4001)), HOMEWORK_NOTES_PROBLEM),
    ];
    for (field, bad_value, expected) in cases {
        let mut hw = valid_homework();
        hw[field] = bad_value;
        assert_eq!(
            homework_sheet_problem(&hw),
            Some((field.into(), expected.into())),
            "field={field}"
        );
    }

    let mut estimate_zero = valid_homework();
    estimate_zero["estimate_min"] = json!(0);
    assert_eq!(
        homework_sheet_problem(&estimate_zero),
        Some(("estimate_min".into(), HOMEWORK_ESTIMATE_PROBLEM.into()))
    );

    let mut estimate_over = valid_homework();
    estimate_over["estimate_min"] = json!(1455);
    assert_eq!(
        homework_sheet_problem(&estimate_over),
        Some(("estimate_min".into(), HOMEWORK_ESTIMATE_PROBLEM.into()))
    );
}

#[test]
fn homework_links_report_url_label_and_limit_separately() {
    let mut bad_url = valid_homework();
    bad_url["links"] = json!([{"label": "Rubric", "url": "ftp://example.com/r"}]);
    assert_eq!(
        homework_sheet_problem(&bad_url),
        Some(("links".into(), HOMEWORK_LINK_URL_PROBLEM.into()))
    );

    let mut blank_label = valid_homework();
    blank_label["links"] = json!([{"label": "   ", "url": "https://example.com"}]);
    assert_eq!(
        homework_sheet_problem(&blank_label),
        Some(("links".into(), HOMEWORK_LINK_LABEL_PROBLEM.into()))
    );

    let mut long_label = valid_homework();
    long_label["links"] = json!([{"label": "L".repeat(81), "url": "https://example.com"}]);
    assert_eq!(
        homework_sheet_problem(&long_label),
        Some(("links".into(), HOMEWORK_LINK_LABEL_PROBLEM.into()))
    );

    let mut too_many = valid_homework();
    let many_links: Vec<Value> = (0..21)
        .map(|i| json!({"label": format!("Link {i}"), "url": "https://example.com"}))
        .collect();
    too_many["links"] = Value::Array(many_links);
    assert_eq!(
        homework_sheet_problem(&too_many),
        Some(("links".into(), HOMEWORK_LINKS_LIMIT_PROBLEM.into()))
    );
}

#[test]
fn homework_checklist_reports_text_and_limit_separately() {
    let mut blank_text = valid_homework();
    blank_text["checklist"] = json!([{"id": "c1", "text": "  ", "done": false}]);
    assert_eq!(
        homework_sheet_problem(&blank_text),
        Some(("checklist".into(), HOMEWORK_CHECKLIST_TEXT_PROBLEM.into()))
    );

    let mut long_text = valid_homework();
    long_text["checklist"] = json!([{"id": "c1", "text": "t".repeat(81), "done": false}]);
    assert_eq!(
        homework_sheet_problem(&long_text),
        Some(("checklist".into(), HOMEWORK_CHECKLIST_TEXT_PROBLEM.into()))
    );

    let mut too_many = valid_homework();
    let many_steps: Vec<Value> = (0..41)
        .map(|i| json!({"id": format!("c{i}"), "text": format!("Step {i}"), "done": false}))
        .collect();
    too_many["checklist"] = Value::Array(many_steps);
    assert_eq!(
        homework_sheet_problem(&too_many),
        Some(("checklist".into(), HOMEWORK_CHECKLIST_LIMIT_PROBLEM.into()))
    );
}

#[test]
fn a_list_over_its_cap_says_the_cap_even_when_its_first_item_is_bad() {
    // pydantic 2.13.5 reports the list's too_long and never reaches the items.
    let mut links = valid_homework();
    let mut items: Vec<Value> = vec![json!({"label": "", "url": "https://example.com"})];
    items.extend(
        (0..20).map(|i| json!({"label": format!("Link {i}"), "url": "https://example.com"})),
    );
    links["links"] = Value::Array(items);
    assert_eq!(
        homework_sheet_problem(&links),
        Some(("links".into(), HOMEWORK_LINKS_LIMIT_PROBLEM.into()))
    );

    let mut steps = valid_homework();
    let mut items: Vec<Value> = vec![json!({"id": "c0", "text": "", "done": false})];
    items.extend(
        (1..41).map(|i| json!({"id": format!("c{i}"), "text": format!("Step {i}"), "done": false})),
    );
    steps["checklist"] = Value::Array(items);
    assert_eq!(
        homework_sheet_problem(&steps),
        Some(("checklist".into(), HOMEWORK_CHECKLIST_LIMIT_PROBLEM.into()))
    );
}

#[test]
fn homework_model_validators_and_unmapped_fields_return_homework_refused() {
    let mut completed_no_stamp = valid_homework();
    completed_no_stamp["completed"] = json!(true);
    assert_eq!(
        homework_sheet_problem(&completed_no_stamp),
        Some((String::new(), HOMEWORK_REFUSED.into()))
    );

    let mut dup_check_ids = valid_homework();
    dup_check_ids["checklist"] = json!([
        {"id": "same", "text": "Step 1", "done": false},
        {"id": "same", "text": "Step 2", "done": false},
    ]);
    assert_eq!(
        homework_sheet_problem(&dup_check_ids),
        Some((String::new(), HOMEWORK_REFUSED.into()))
    );

    let mut bad_id = valid_homework();
    bad_id["id"] = json!("");
    bad_id["title"] = json!("");
    // `id` precedes `title` in Assignment's field order, so `id` wins first error.
    assert_eq!(
        homework_sheet_problem(&bad_id),
        Some(("id".into(), HOMEWORK_REFUSED.into()))
    );

    let mut bad_rev = valid_homework();
    bad_rev["revision"] = json!(-1);
    assert_eq!(
        homework_sheet_problem(&bad_rev),
        Some(("revision".into(), HOMEWORK_REFUSED.into()))
    );

    assert_eq!(
        homework_sheet_problem(&json!(42)),
        Some((String::new(), HOMEWORK_REFUSED.into()))
    );
}

#[test]
fn block_sheet_problem_matches_block_parity_corpus_and_week_request() {
    let text = include_str!("../../service/tests/fixtures/block_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 2000, "corpus shrank to {}", cases.len());
    let mut accepted = 0usize;
    let mut refused = 0usize;
    for case in &cases {
        let input = &case["input"];
        let expected_block_ok = !case["written"].is_null();
        let expected_week_ok = week_request(&json!({ "blocks": [input] })).is_ok();
        let got = block_sheet_problem(input);
        if !expected_block_ok {
            assert!(
                got.is_some(),
                "TimeBlock refused but block_sheet_problem accepted: {input}"
            );
        }
        assert_eq!(
            got.is_none(),
            expected_week_ok,
            "week_request mismatch for {input}: got={got:?}"
        );
        if let Some((field, msg)) = got {
            refused += 1;
            let expected_msg = match field.as_str() {
                "title" => BLOCK_TITLE_PROBLEM,
                "days" => BLOCK_DAYS_PROBLEM,
                "spotify_url" => BLOCK_SPOTIFY_PROBLEM,
                "" => BLOCK_REFUSED,
                other => panic!("unexpected block field {other:?} for {input}"),
            };
            assert_eq!(msg, expected_msg);
        } else {
            accepted += 1;
        }
    }
    assert!(accepted >= 200, "too few accepted blocks: {accepted}");
    assert!(refused >= 1000, "too few refused blocks: {refused}");
}

#[test]
fn homework_sheet_problem_matches_homework_parity_corpus() {
    let text = include_str!("../../service/tests/fixtures/homework_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 1500, "corpus shrank to {}", cases.len());
    let mut accepted = 0usize;
    let mut refused = 0usize;
    for case in &cases {
        let input = &case["input"];
        let got = homework_sheet_problem(input);
        let filtered_ok = input.as_object().is_some_and(|raw| {
            let filtered: Map<String, Value> = raw
                .iter()
                .filter(|(k, _)| {
                    k.as_str() == "revision" || ASSIGNMENT_FIELDS.contains(&k.as_str())
                })
                .map(|(k, v)| (k.clone(), v.clone()))
                .collect();
            check_homework(&Value::Object(filtered)).is_ok()
        });
        assert_eq!(
            got.is_none(),
            filtered_ok,
            "filtered check_homework mismatch for {input}: got={got:?}"
        );
        if !case["written"].is_null() {
            assert_eq!(
                got, None,
                "Assignment accepted but homework_sheet_problem refused: {input}"
            );
            accepted += 1;
        } else if got.is_some() {
            refused += 1;
        }
        // When there are no extra keys, accept/refuse must match Assignment 100%.
        let has_extra = input.as_object().is_some_and(|raw| {
            raw.keys()
                .any(|k| k.as_str() != "revision" && !ASSIGNMENT_FIELDS.contains(&k.as_str()))
        });
        if !has_extra {
            assert_eq!(
                got.is_none(),
                !case["written"].is_null(),
                "exact-key Assignment mismatch for {input}: got={got:?}"
            );
        }
    }
    assert!(
        accepted >= 400,
        "too few accepted homework saves: {accepted}"
    );
    assert!(refused >= 500, "too few refused homework saves: {refused}");
}
