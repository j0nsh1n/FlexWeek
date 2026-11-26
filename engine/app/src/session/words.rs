//! What a student reads when a request fails: the words `desktop/native/client.py` (`_error`) gives each
//! answer today, moved here so the window says the same things once the session is in Rust.

use serde_json::Value;

pub const PASSWORD_LENGTH_HINT: &str = "At least 12 characters.";
pub const USERNAME_ERROR: &str = "Use 3 to 32 letters, numbers or underscores, with no spaces.";
pub const WRONG_PASSWORD: &str = "Wrong password. Try again.";
pub const TOO_MANY_TRIES: &str = "Too many tries. Wait 5 minutes, then try again.";
pub const SIGN_IN_WRONG: &str = "Wrong username or password. Try again, or choose Forgot password.";
pub const USERNAME_TAKEN: &str = "That username is taken. Try another.";
pub const WRONG_RECOVERY_CODE: &str =
    "Wrong username or recovery code. Each code works once; try another one.";
/// Said when a session ends, or when sign-in gets a 401 it cannot read.
pub const SIGN_IN_AGAIN: &str =
    "Sign in again. If you were signing in, check your username and password.";
pub const SESSION_ENDED: &str = "Your session ended. Sign in again.";
pub const UNREADABLE: &str =
    "FlexWeek couldn't read its own answer. Close and reopen it, then try again.";

/// The service's details that are a wrong answer at sign-in, not a session that ended.
pub const NOT_AN_EXPIRY: [&str; 3] = [
    "Incorrect password",
    "Incorrect username or password",
    "Incorrect username or recovery code",
];

/// The words for a failed request with `status` (0 when no answer came) and the service's `detail`.
pub fn error_words(status: u16, detail: Option<&Value>) -> &'static str {
    let said = detail.and_then(Value::as_str);
    match (status, said) {
        (401, Some("Incorrect password")) => return WRONG_PASSWORD,
        (401, Some("Incorrect username or password")) => return SIGN_IN_WRONG,
        (409, Some("Username unavailable")) => return USERNAME_TAKEN,
        (401, Some("Incorrect username or recovery code")) => return WRONG_RECOVERY_CODE,
        (401, Some(SESSION_ENDED)) => return SESSION_ENDED,
        _ => {}
    }
    if status == 422 {
        if names_a_field(detail, &["password", "new_password", "current_password"]) {
            return PASSWORD_LENGTH_HINT;
        }
        if names_a_field(detail, &["username"]) {
            return USERNAME_ERROR;
        }
    }
    match status {
        0 => "FlexWeek didn't answer. Your changes may not have been saved. Try again.",
        401 => SIGN_IN_AGAIN,
        403 => "FlexWeek refused that change. Close and reopen FlexWeek, then try again.",
        404 => "This item is no longer available. Reload and try again.",
        409 => "The saved data changed or that name is already in use. Reload and try again.",
        413 => "This request is too large. Reduce its size and try again.",
        422 => "Check the required fields, dates, times and lengths, then try again.",
        429 => TOO_MANY_TRIES,
        503 => {
            "FlexWeek can't open its saved data right now. Keep your changes and try again in a minute."
        }
        _ => "FlexWeek couldn't finish that action. Try again.",
    }
}

/// Whether a list of validation problems names one of `names` in its `loc` (any case).
fn names_a_field(detail: Option<&Value>, names: &[&str]) -> bool {
    let Some(Value::Array(items)) = detail else {
        return false;
    };
    items.iter().any(|item| {
        item.get("loc")
            .and_then(Value::as_array)
            .is_some_and(|loc| {
                loc.iter().any(|part| {
                    let part = match part {
                        Value::String(text) => text.to_lowercase(),
                        other => other.to_string().to_lowercase(),
                    };
                    names.contains(&part.as_str())
                })
            })
    })
}
