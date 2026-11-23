//! The account checks against the server's pydantic models (`Credentials` for sign-up and sign-in,
//! `RecoverRequest`, `PasswordChange` in backend/app.py), which go with the server in P2: the generated names,
//! passwords and codes of fixtures/account_parity.json (made by fixtures/make_account_corpus.py with the real
//! models) are refused where pydantic refused them and kept as pydantic kept them.

use flexweek_service::accounts::{checked_code, checked_password, checked_username};
use serde_json::{Value, json};

fn text<'a>(case: &'a Value, field: &str) -> &'a str {
    case["input"][field].as_str().unwrap()
}

#[test]
fn every_generated_account_request_is_read_as_the_server_read_it() {
    let cases: Vec<Value> =
        serde_json::from_str(include_str!("fixtures/account_parity.json")).unwrap();
    assert!(cases.len() >= 1000, "the corpus shrank to {}", cases.len());
    for part in ["credentials", "recover", "change"] {
        let accepted = cases.iter().filter(|case| !case[part].is_null()).count();
        assert!(
            accepted >= 100,
            "only {accepted} {part} requests are accepted"
        );
    }
    let mut wrong = Vec::new();
    for case in &cases {
        let (name, password, code, new) = (
            text(case, "username"),
            text(case, "password"),
            text(case, "code"),
            text(case, "new_password"),
        );
        let credentials = match (checked_username(name), checked_password(password)) {
            (Ok(name), Ok(password)) => {
                json!({ "username": name, "password": password, "keep": false })
            }
            _ => Value::Null,
        };
        let recover = match (
            checked_username(name),
            checked_code(code),
            checked_password(password),
        ) {
            (Ok(name), Ok(code), Ok(password)) => {
                json!({ "username": name, "code": code, "password": password, "keep": false })
            }
            _ => Value::Null,
        };
        let change = match (checked_password(password), checked_password(new)) {
            (Ok(current), Ok(new)) => json!({ "current_password": current, "new_password": new }),
            _ => Value::Null,
        };
        for (part, got) in [
            ("credentials", credentials),
            ("recover", recover),
            ("change", change),
        ] {
            if got != case[part] {
                let shown: String = case["input"].to_string().chars().take(200).collect();
                wrong.push(format!(
                    "{part} {shown}\n  pydantic: {}\n  rust:     {got}",
                    case[part]
                ));
            }
        }
    }
    assert!(
        wrong.is_empty(),
        "{} differ; first ones:\n{}",
        wrong.len(),
        wrong.iter().take(6).cloned().collect::<Vec<_>>().join("\n")
    );
}
