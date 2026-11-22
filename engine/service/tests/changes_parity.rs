//! `check_changes` against pydantic's `ChangesRequest`, the multi-week save as the app's server read it:
//! 2,500 generated saves (fixtures/changes_parity.json, made by fixtures/make_changes_corpus.py with the
//! real models) are refused where pydantic refused them, read exactly as `model_dump()` wrote them, and keyed
//! by the same digest, so a save sent again across the update still finds its first answer.

use flexweek_service::changes::check_changes;
use flexweek_store::payload_digest;
use serde_json::Value;

#[test]
fn every_generated_save_is_read_and_keyed_as_the_app_read_it() {
    let text = include_str!("fixtures/changes_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 2000, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["written"].is_null())
        .count();
    assert!(accepted >= 500, "only {accepted} saves are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_changes(input).map(|request| request.to_value());
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(read), expected) if !expected.is_null() => {
                serde_json::to_string(read).unwrap() == serde_json::to_string(expected).unwrap()
                    && case["digest"] == payload_digest(read).as_str()
            }
            _ => false,
        };
        if !same {
            let shown = input.to_string();
            let shown: String = shown.chars().take(300).collect();
            wrong.push(format!(
                "{shown}\n  pydantic: {expected}\n  rust:     {got:?}"
            ));
        }
    }
    assert!(
        wrong.is_empty(),
        "{} of {} saves differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong.iter().take(6).cloned().collect::<Vec<_>>().join("\n")
    );
}
