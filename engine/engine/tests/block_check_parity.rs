//! The engine's block check against pydantic's `TimeBlock`, the desktop's rule (Jonathan, 2026-11-22: the
//! assistant accepts what the desktop accepts): the 2,500 generated blocks of the service's parity corpus
//! (made by service/tests/fixtures/make_block_corpus.py with the real model) are refused where pydantic
//! refuses them and written exactly as pydantic writes them, field order included.

use flexweek_engine::validate::time_block;
use serde_json::Value;

#[test]
fn every_generated_block_is_read_as_the_desktop_reads_it() {
    let text = include_str!("../../service/tests/fixtures/block_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 2000, "the corpus shrank to {}", cases.len());
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = time_block(input).map(|block| block.to_value());
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
        "{} of {} blocks differ; first ones:\n{}",
        wrong.len(),
        cases.len(),
        wrong
            .iter()
            .take(10)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}
