//! `check_spread` against pydantic's `SpreadRequest`, the "spread it out" request as the app's server reads
//! it: the generated requests of fixtures/spread_parity.json (made by fixtures/make_spread_corpus.py with the
//! real model) are refused where pydantic refuses them and read as pydantic reads them.

use flexweek_service::homework_saves::check_spread;
use serde_json::{Value, json};

#[test]
fn every_generated_spread_request_is_read_as_the_app_reads_it() {
    let text = include_str!("fixtures/spread_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 500, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["written"].is_null())
        .count();
    assert!(accepted >= 20, "only {accepted} requests are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_spread(input)
            .map(|(minutes, from)| json!({ "session_min": minutes, "from_date": from }));
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(read), expected) if !expected.is_null() => read == expected,
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
        "{} differ:\n{}",
        wrong.len(),
        wrong.join("\n")
    );
}
