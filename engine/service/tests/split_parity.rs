//! `split_preview` against `POST /api/timer-split-preview`, the route it replaces: 1,200 generated requests
//! (fixtures/split_parity.json, made by fixtures/make_split_corpus.py with the real `TimerSplitRequest`)
//! must be refused where pydantic refuses them and answered exactly as the route answers them. This test
//! and its generator go when the Python model does.

use flexweek_service::comfort::split_preview;
use serde_json::Value;

#[test]
fn every_generated_split_request_is_answered_as_the_route_answers_it() {
    let text = include_str!("fixtures/split_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 1000, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["answer"].is_null())
        .count();
    assert!(accepted >= 300, "only {accepted} requests are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["answer"];
        let got = split_preview(input);
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(answer), expected) if !expected.is_null() => answer == expected,
            _ => false,
        };
        if !same {
            wrong.push(format!("{input}\n  python: {expected}\n  rust:   {got:?}"));
        }
    }
    assert!(
        wrong.is_empty(),
        "{} of {} requests differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong
            .iter()
            .take(12)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}
