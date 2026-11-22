//! `check_plan_request` against pydantic's `SolveRequest`, the Plan button's request as the app's server
//! reads it: 1,500 generated requests (fixtures/solve_parity.json, made by fixtures/make_solve_corpus.py
//! with the real model) are refused where pydantic refuses them and read exactly as pydantic reads them.

use flexweek_service::plans::check_plan_request;
use serde_json::Value;

#[test]
fn every_generated_plan_request_is_read_as_the_app_reads_it() {
    let text = include_str!("fixtures/solve_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 1000, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["written"].is_null())
        .count();
    assert!(accepted >= 300, "only {accepted} requests are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_plan_request(input).map(|request| request.to_value());
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(read), expected) if !expected.is_null() => {
                serde_json::to_string(read).unwrap() == serde_json::to_string(expected).unwrap()
            }
            _ => false,
        };
        if !same {
            wrong.push(format!(
                "{input}\n  pydantic: {expected}\n  rust:     {got:?}"
            ));
        }
    }
    assert!(
        wrong.is_empty(),
        "{} of {} requests differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong.iter().take(8).cloned().collect::<Vec<_>>().join("\n")
    );
}
