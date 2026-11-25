//! The desktop window's requests, answered by the 2.0.0 service crate in this process
//! (`service_answer`), and the preference fields the window may save.

use std::path::Path;

use flexweek_service::accounts::Entropy;
use flexweek_service::{
    ServiceError, ServiceResult, blocks, desk_requests, homework_saves, plans, preferences,
};
use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyModule;

use crate::guard;

/// Python's `secrets` (or an object with its `token_urlsafe`, `token_hex` and `token_bytes`), so tokens,
/// salts and codes are made as the server made them. The service runs without the GIL; each draw takes it
/// back only while it asks Python.
pub(crate) struct Secrets {
    pub(crate) module: Py<PyAny>,
    pub(crate) failed: Option<PyErr>,
}

impl Secrets {
    /// Keeps Python's own error for the caller and stops the account change, which then saves nothing.
    fn fail(&mut self, error: PyErr) -> ServiceError {
        self.failed.get_or_insert(error);
        ServiceError::Broken("Python's secrets module failed".into())
    }

    fn text(&mut self, name: &str, size: usize) -> ServiceResult<String> {
        let made = Python::attach(|py| {
            self.module
                .bind(py)
                .call_method1(name, (size,))
                .and_then(|value| value.extract::<String>())
        });
        made.map_err(|error| self.fail(error))
    }
}

impl Entropy for Secrets {
    fn session_token(&mut self) -> ServiceResult<String> {
        self.text("token_urlsafe", 32)
    }
    fn salt(&mut self) -> ServiceResult<String> {
        self.text("token_hex", 16)
    }
    fn code_bytes(&mut self) -> ServiceResult<[u8; 8]> {
        let made = Python::attach(|py| {
            self.module
                .bind(py)
                .call_method1("token_bytes", (8,))
                .and_then(|value| value.extract::<Vec<u8>>())
        });
        match made {
            Ok(bytes) => bytes.try_into().map_err(|bytes: Vec<u8>| {
                let wrong = PyRuntimeError::new_err(format!(
                    "secrets.token_bytes(8) gave {} bytes",
                    bytes.len()
                ));
                self.fail(wrong)
            }),
            Err(error) => Err(self.fail(error)),
        }
    }
}

/// One request from the desktop window, answered in this process with no server (P2): the status, the
/// body as JSON text (None for none), whether the session was "kept", "started" or "ended", and the new
/// session token ("" unless started). Refusals are answers here, not exceptions.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (path, method, api_path, body, token, account, seconds, now, restore_token))]
fn service_answer(
    py: Python<'_>,
    path: &str,
    method: &str,
    api_path: &str,
    body: &str,
    token: &str,
    account: Option<&str>,
    seconds: i64,
    now: &str,
    restore_token: &str,
) -> PyResult<(u16, Option<String>, &'static str, String)> {
    guard(|| {
        let mut secrets = Secrets {
            module: py.import("secrets")?.into_any().unbind(),
            failed: None,
        };
        let request = desk_requests::Request {
            method,
            path: api_path,
            body,
            token,
            account,
        };
        let start_clock = || -> plans::Stopwatch {
            let started = std::time::Instant::now();
            Box::new(move || started.elapsed().as_secs_f64() * 1000.0)
        };
        let clock = desk_requests::Clock {
            seconds,
            now,
            restore_token,
            stopwatch: &start_clock,
        };
        let answer =
            py.detach(|| desk_requests::answer(Path::new(path), &request, &clock, &mut secrets));
        if let Some(error) = secrets.failed {
            return Err(error);
        }
        let (session, new_token) = match answer.session {
            desk_requests::Session::Kept => ("kept", String::new()),
            desk_requests::Session::Started(token) => ("started", token),
            desk_requests::Session::Ended => ("ended", String::new()),
        };
        Ok((
            answer.status,
            answer.body.map(|body| body.to_string()),
            session,
            new_token,
        ))
    })
}

/// A block as pydantic's `TimeBlock.model_validate(value).model_dump()` writes it, from JSON text to JSON text;
/// a block it would refuse raises ValueError with why (service/blocks.rs, matched to pydantic on 2,500 blocks).
#[pyfunction]
fn checked_block(text: &str) -> PyResult<String> {
    guard(|| {
        let value: serde_json::Value =
            serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))?;
        blocks::check_block(&value)
            .map(|block| block.to_string())
            .map_err(|refused| PyValueError::new_err(refused.0))
    })
}

/// A homework as pydantic's `Assignment.model_validate(value).model_dump()` writes it, revision included, from
/// JSON text to JSON text; one it would refuse raises ValueError with why (service/homework_saves.rs, matched to
/// pydantic on 2,000 saves).
#[pyfunction]
fn checked_homework(text: &str) -> PyResult<String> {
    guard(|| {
        let value: serde_json::Value =
            serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))?;
        let (mut content, revision) = homework_saves::check_homework(&value)
            .map_err(|refused| PyValueError::new_err(refused.0))?;
        if let Some(fields) = content.as_object_mut() {
            fields.insert("revision".into(), serde_json::Value::from(revision));
        }
        Ok(content.to_string())
    })
}

/// A homework's content as a week or day file holds it (no revision), checked and written as the engine's
/// `assignment_content` does (pydantic's `AssignmentContent`); one it refuses raises ValueError with why.
#[pyfunction]
fn checked_homework_content(text: &str) -> PyResult<String> {
    guard(|| {
        let value: serde_json::Value =
            serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))?;
        flexweek_engine::validate::assignment_content(&value)
            .map(|content| content.to_value().to_string())
            .map_err(PyValueError::new_err)
    })
}

/// The fields a homework save may have (`Assignment.model_fields`): its content's, then the revision.
#[pyfunction]
fn homework_fields() -> PyResult<Vec<&'static str>> {
    guard(|| {
        let mut fields = flexweek_engine::validate::ASSIGNMENT_FIELDS.to_vec();
        fields.push("revision");
        Ok(fields)
    })
}

/// Refuses, with ValueError and why, the first protected time or Study hours window (JSON lists) that a
/// preferences save would refuse (service/preferences.rs); `work` is None when Study hours are not sent.
#[pyfunction]
#[pyo3(signature = (protected, work=None))]
fn check_hours_windows(protected: &str, work: Option<&str>) -> PyResult<()> {
    guard(|| {
        let list = |text: &str| -> PyResult<Vec<serde_json::Value>> {
            serde_json::from_str(text).map_err(|error| PyValueError::new_err(error.to_string()))
        };
        let refused = |refused: blocks::BlockRefused| PyValueError::new_err(refused.0);
        for window in list(protected)? {
            preferences::protected_window(&window).map_err(refused)?;
        }
        if let Some(work) = work {
            for window in list(work)? {
                preferences::work_window(&window).map_err(refused)?;
            }
        }
        Ok(())
    })
}

/// The preference fields an account may save, in their order.
#[pyfunction]
fn preference_fields() -> PyResult<Vec<&'static str>> {
    guard(|| Ok(preferences::FIELDS.to_vec()))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(
        module,
        service_answer,
        preference_fields,
        checked_block,
        checked_homework,
        checked_homework_content,
        homework_fields,
        check_hours_windows
    );
    Ok(())
}
