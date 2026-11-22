//! `check_homework` against pydantic's `Assignment`, a homework save as the app's server checks it: 2,000
//! generated saves (fixtures/homework_parity.json, made by fixtures/make_homework_corpus.py with the real
//! model) are refused where pydantic refuses them and written exactly as pydantic writes them.

use flexweek_service::homework_saves::check_homework;
use serde_json::Value;

#[test]
fn every_generated_homework_save_is_read_as_the_app_reads_it() {
    let text = include_str!("fixtures/homework_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 1500, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["written"].is_null())
        .count();
    assert!(accepted >= 400, "only {accepted} saves are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_homework(input).map(|(mut content, revision)| {
            content
                .as_object_mut()
                .unwrap()
                .insert("revision".into(), Value::from(revision));
            content
        });
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
        "{} of {} saves differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong.iter().take(8).cloned().collect::<Vec<_>>().join("\n")
    );
}
