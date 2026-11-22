//! `check_preferences` against pydantic's `Preferences`, the rule it replaces: 1,600 generated preference
//! sets (fixtures/preferences_parity.json, made by fixtures/make_preferences_corpus.py with the real model)
//! must be refused where pydantic refuses them and written out exactly as pydantic writes them, field order
//! included. This test and its generator go when the Python model does.

use flexweek_service::preferences::check_preferences;
use serde_json::Value;

#[test]
fn every_generated_preference_set_is_read_as_pydantic_reads_it() {
    let text = include_str!("fixtures/preferences_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 1500, "the corpus shrank to {}", cases.len());
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_preferences(input);
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(written), expected) if !expected.is_null() => {
                serde_json::to_string(written).unwrap() == serde_json::to_string(expected).unwrap()
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
        "{} of {} preference sets differ; first ones:\n{}",
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
