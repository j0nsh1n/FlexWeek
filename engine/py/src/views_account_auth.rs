//! Python bindings for the Material account auth and recovery view-model
//! (`flexweek_app::views::account_auth`).
//!
//! Every exported function and method body runs inside `guard(` and refuses wrong-shaped inputs
//! with `ValueError` or `TypeError`.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::account_auth::{
    self, AuthPhase, AuthState, ProblemField, PromptAction, SubmitAction,
};
use pyo3::exceptions::{PyRuntimeError, PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyModule, PyString};
use serde_json::{Map, Value};

use crate::{guard, raise};

fn parse_object(text: &str, what: &str) -> PyResult<Map<String, Value>> {
    let parsed: Value = serde_json::from_str(text)
        .map_err(|error| PyValueError::new_err(format!("{what}: {error}")))?;
    match parsed {
        Value::Object(map) => Ok(map),
        _ => Err(PyTypeError::new_err(format!(
            "{what} must be a JSON object"
        ))),
    }
}

fn read_codes(codes: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    if codes.is_instance_of::<PyString>() || codes.is_instance_of::<PyBytes>() {
        return Err(PyTypeError::new_err(
            "codes must be a sequence of strings, not a single string",
        ));
    }
    let mut out = Vec::new();
    for item in codes.try_iter()? {
        out.push(item?.str()?.extract::<String>()?);
    }
    Ok(out)
}

fn read_optional_path(path: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    if path.is_none() {
        return Ok(None);
    }
    if path.is_instance_of::<PyString>() {
        return Ok(Some(path.extract::<String>()?));
    }
    Err(PyTypeError::new_err("path must be a string or None"))
}

fn prompt_tuple(action: PromptAction) -> (String, Option<String>) {
    match action {
        PromptAction::None => ("none".to_string(), None),
        PromptAction::Question { choice } => ("question".to_string(), Some(choice)),
        PromptAction::QuestionClosed => ("question_closed".to_string(), None),
        PromptAction::Edited { choice } => ("edited".to_string(), choice),
    }
}

#[pyfunction]
fn views_account_auth_words() -> PyResult<String> {
    guard(|| Ok(account_auth::words_json().to_string()))
}

#[pyfunction]
fn views_account_auth_initial_phase(has_account: bool, has_kept_token: bool) -> PyResult<String> {
    guard(|| {
        Ok(account_auth::initial_phase(has_account, has_kept_token)
            .as_str()
            .to_string())
    })
}

#[pyfunction]
fn views_account_auth_field_for(phase: &str, message: &str) -> PyResult<String> {
    guard(|| {
        let phase = AuthPhase::parse(phase).map_err(raise)?;
        Ok(account_auth::field_for(phase, message)
            .map(ProblemField::as_str)
            .unwrap_or("")
            .to_string())
    })
}

#[pyfunction]
fn views_account_auth_recovery_problem(
    username: &str,
    code: &str,
    new_password: &str,
) -> PyResult<String> {
    guard(|| Ok(account_auth::recovery_problem(username, code, new_password)))
}

#[pyfunction]
fn views_account_auth_prompt_choice(choice: &str) -> PyResult<Option<String>> {
    guard(|| Ok(account_auth::edited_prompt_choice(choice).map(str::to_string)))
}

/// Stateful view-model backing `desktop/native/material/bridge_account.py::AccountBridge` auth and
/// recovery flows.
#[pyclass(name = "AccountAuthView", module = "flexweek_engine")]
pub struct AccountAuthViewHandle {
    state: Mutex<AuthState>,
}

impl AccountAuthViewHandle {
    fn locked(&self) -> PyResult<MutexGuard<'_, AuthState>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("the account auth view failed earlier"))
    }
}

#[pymethods]
impl AccountAuthViewHandle {
    #[new]
    fn new(has_account: bool, has_kept_token: bool, keep_signed_in: bool) -> PyResult<Self> {
        guard(|| {
            Ok(Self {
                state: Mutex::new(AuthState::new(has_account, has_kept_token, keep_signed_in)),
            })
        })
    }

    fn phase(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.phase().to_string()))
    }

    fn set_phase(&self, value: &str) -> PyResult<()> {
        guard(|| self.locked()?.set_phase(value).map_err(raise))
    }

    fn codes(&self) -> PyResult<Vec<String>> {
        guard(|| Ok(self.locked()?.codes()))
    }

    fn show_sign_in(&self, clear: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.show_sign_in(clear);
            Ok(())
        })
    }

    fn show_create(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.show_create();
            Ok(())
        })
    }

    fn show_reset(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.show_reset();
            Ok(())
        })
    }

    fn set_username(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_username(value);
            Ok(())
        })
    }

    fn set_password(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_password(value);
            Ok(())
        })
    }

    fn set_recovery_code(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_recovery_code(value);
            Ok(())
        })
    }

    fn set_new_password(&self, value: String) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_new_password(value);
            Ok(())
        })
    }

    fn set_keep_signed_in(&self, on: bool) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.set_keep_signed_in(on)))
    }

    fn submit(&self) -> PyResult<Option<(String, Vec<String>)>> {
        guard(|| {
            let outcome = self.locked()?.submit().map_err(raise)?;
            Ok(match outcome {
                SubmitAction::None => None,
                SubmitAction::Problem => Some(("problem".to_string(), Vec::new())),
                SubmitAction::Login { username, password } => {
                    Some(("login".to_string(), vec![username, password]))
                }
                SubmitAction::Register { username, password } => {
                    Some(("register".to_string(), vec![username, password]))
                }
                SubmitAction::Recover {
                    username,
                    code,
                    new_password,
                } => Some(("recover".to_string(), vec![username, code, new_password])),
            })
        })
    }

    fn explain_why(&self) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.explain_why().then_some(true)))
    }

    fn dismiss_why(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.dismiss_why();
            Ok(())
        })
    }

    fn show_recovery(&self, codes: &Bound<'_, PyAny>) -> PyResult<()> {
        guard(|| {
            let items = read_codes(codes)?;
            self.locked()?.show_recovery(items);
            Ok(())
        })
    }

    fn set_recovery_ack(&self, on: bool) -> PyResult<()> {
        guard(|| {
            self.locked()?.set_recovery_ack(on);
            Ok(())
        })
    }

    fn copy_codes(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.copy_codes()))
    }

    fn recovery_file_payload(&self, path: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
        guard(|| {
            let chosen = read_optional_path(path)?;
            Ok(self.locked()?.recovery_file_payload(chosen.as_deref()))
        })
    }

    fn mark_save_failed(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.mark_save_failed();
            Ok(())
        })
    }

    fn mark_save_succeeded(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.mark_save_succeeded();
            Ok(())
        })
    }

    fn finish_recovery(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.finish_recovery().to_string()))
    }

    fn show_app(&self) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.show_app().then_some(true)))
    }

    fn pose_edited(&self, ask_json: &str, has_done: bool) -> PyResult<()> {
        guard(|| {
            let ask = parse_object(ask_json, "ask")?;
            self.locked()?.pose_edited(ask, has_done);
            Ok(())
        })
    }

    fn ask_json(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.ask_value().to_string()))
    }

    fn pose_question(&self, question_json: &str, has_handlers: bool) -> PyResult<()> {
        guard(|| {
            let question = parse_object(question_json, "question")?;
            self.locked()?.pose_question(question, has_handlers);
            Ok(())
        })
    }

    fn answer(&self, choice: &str) -> PyResult<(String, Option<String>)> {
        guard(|| Ok(prompt_tuple(self.locked()?.answer(choice))))
    }

    fn close_sheet(&self) -> PyResult<(String, Option<String>)> {
        guard(|| Ok(prompt_tuple(self.locked()?.close_sheet())))
    }

    #[pyo3(signature = (choice = None))]
    fn finish_edited(&self, choice: Option<String>) -> PyResult<(String, Option<String>)> {
        guard(|| Ok(prompt_tuple(self.locked()?.finish_edited(choice))))
    }

    #[pyo3(signature = (setup_heading = None))]
    fn heading(&self, setup_heading: Option<&str>) -> PyResult<String> {
        guard(|| self.locked()?.heading(setup_heading).map_err(raise))
    }

    #[pyo3(signature = (setup_note = None))]
    fn note(&self, setup_note: Option<&str>) -> PyResult<String> {
        guard(|| self.locked()?.note(setup_note).map_err(raise))
    }

    fn username(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.username().to_string()))
    }

    fn password(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.password().to_string()))
    }

    fn keep_signed_in(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.keep_signed_in()))
    }

    fn username_hint(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.username_hint().to_string()))
    }

    fn password_hint(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.password_hint().to_string()))
    }

    fn username_problem(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.username_problem().to_string()))
    }

    fn password_problem(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.password_problem().to_string()))
    }

    fn recovery_problem_text(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.recovery_problem_text().to_string()))
    }

    fn new_password_problem(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.new_password_problem().to_string()))
    }

    fn status_line(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.status_line().to_string()))
    }

    fn why_visible(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.why_visible()))
    }

    fn why_open(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.why_open()))
    }

    fn recovery_code(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.recovery_code().to_string()))
    }

    fn new_password(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.new_password().to_string()))
    }

    fn recovery_codes_text(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.recovery_codes_text()))
    }

    fn recovery_ack(&self) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.recovery_ack()))
    }

    fn recovery_ready(&self, busy: bool) -> PyResult<bool> {
        guard(|| Ok(self.locked()?.recovery_ready(busy)))
    }

    fn copy_label(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.copy_label().to_string()))
    }

    fn save_label(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.save_label().to_string()))
    }

    fn recovery_status(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.recovery_status().to_string()))
    }

    fn on_resume_failed(&self) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.on_resume_failed().then_some(true)))
    }

    fn on_status(&self, message: &str) -> PyResult<Option<bool>> {
        guard(|| Ok(self.locked()?.on_status(message).then_some(true)))
    }

    fn field_for(&self, message: &str) -> PyResult<String> {
        guard(|| Ok(self.locked()?.field_for(message).to_string()))
    }

    fn show_problem(&self, message: &str) -> PyResult<()> {
        guard(|| {
            self.locked()?.show_problem(message);
            Ok(())
        })
    }

    fn clear_problems(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.clear_problems();
            Ok(())
        })
    }

    fn recovery_problem(&self) -> PyResult<String> {
        guard(|| Ok(self.locked()?.recovery_problem()))
    }

    fn reset_recovery_labels(&self) -> PyResult<()> {
        guard(|| {
            self.locked()?.reset_recovery_labels();
            Ok(())
        })
    }
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<AccountAuthViewHandle>()?;
    crate::export!(
        module,
        views_account_auth_words,
        views_account_auth_initial_phase,
        views_account_auth_field_for,
        views_account_auth_recovery_problem,
        views_account_auth_prompt_choice,
    );
    Ok(())
}
