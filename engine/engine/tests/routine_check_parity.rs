//! The engine's routine check against pydantic's `Routine`, the Routines screen's save as the app's server
//! checks it: 1,500 generated saves (service/tests/fixtures/routine_parity.json, made by
//! make_routine_corpus.py with the real model) are refused where pydantic refuses them and written exactly as
//! pydantic writes them.

use flexweek_engine::validate::routine;
use serde_json::Value;

#[test]
fn every_generated_routine_save_is_read_as_the_app_reads_it() {
    let text = include_str!("../../service/tests/fixtures/routine_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 1000, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["written"].is_null())
        .count();
    assert!(accepted >= 300, "only {accepted} saves are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = routine(input).map(|checked| checked.to_value());
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(written), expected) if !expected.is_null() => {
                serde_json::to_string(written).unwrap() == serde_json::to_string(expected).unwrap()
            }
            _ => false,
        };
        if !same {
            wrong.push(format!(
                "{input}\n  pydantic: {expected}\n  engine:   {got:?}"
            ));
        }
    }
    assert!(
        wrong.is_empty(),
        "{} of {} saves differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong.iter().take(8).cloned().collect::<Vec<_>>().join("\n")
    );
}
