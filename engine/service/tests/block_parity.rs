//! `check_block` against pydantic's `TimeBlock`, the rule it replaces: 2,500 generated blocks
//! (fixtures/block_parity.json, made by running each through `TimeBlock.model_validate(...).model_dump()`)
//! must be refused where pydantic refuses them and written out exactly as pydantic writes them, field
//! order included. Rebuild the corpus from the repository root with
//! `PYTHONPATH=. .venv/bin/python engine/service/tests/fixtures/make_block_corpus.py
//! engine/service/tests/fixtures/block_parity.json 2500`; this test and its generator go when the Python model
//! does.

use flexweek_service::blocks::check_block;
use serde_json::Value;

#[test]
fn every_generated_block_is_read_as_pydantic_reads_it() {
    let text = include_str!("fixtures/block_parity.json");
    let cases: Vec<Value> = serde_json::from_str(text).unwrap();
    assert!(cases.len() >= 2000, "the corpus shrank to {}", cases.len());
    let mut wrong = Vec::new();
    for case in &cases {
        let input = &case["input"];
        let expected = &case["written"];
        let got = check_block(input);
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
        "{} of {} blocks differ; first ones:\n{}",
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
