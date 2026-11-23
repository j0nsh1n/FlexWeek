//! `check_transfer` against pydantic's `TransferSnapshot`, a backup file as the app's server read it on
//! Import: 1,000 generated files (fixtures/transfer_parity.json, made by fixtures/make_transfer_corpus.py
//! from a real export with the real models) are refused where pydantic refused them and read exactly as
//! `model_dump()` wrote them.

use flexweek_service::transfer::check_transfer;
use serde_json::Value;

#[test]
fn every_generated_backup_file_is_read_as_the_app_read_it() {
    let text = include_str!("fixtures/transfer_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 800, "the corpus shrank to {}", cases.len());
    let accepted = cases
        .iter()
        .filter(|case| !case["written"].is_null())
        .count();
    assert!(accepted >= 300, "only {accepted} files are accepted");
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_transfer(input);
        let same = match (&got, expected) {
            (Err(_), Value::Null) => true,
            (Ok(read), expected) if !expected.is_null() => {
                serde_json::to_string(read).unwrap() == serde_json::to_string(expected).unwrap()
            }
            _ => false,
        };
        if !same {
            let shown: String = input.to_string().chars().take(200).collect();
            let expected: String = expected.to_string().chars().take(600).collect();
            let got: String = format!("{got:?}").chars().take(600).collect();
            wrong.push(format!(
                "{shown}\n  pydantic: {expected}\n  rust:     {got}"
            ));
        }
    }
    assert!(
        wrong.is_empty(),
        "{} of {} files differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong.iter().take(4).cloned().collect::<Vec<_>>().join("\n")
    );
}
