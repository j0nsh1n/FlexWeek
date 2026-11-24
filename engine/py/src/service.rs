//! The desktop window's requests, answered by the 2.0.0 service crate in this process
//! (`service_answer`), and the preference fields the window may save.

use std::path::Path;

use flexweek_service::accounts::Entropy;
use flexweek_service::{ServiceError, ServiceResult, desk_requests, plans, preferences};
use pyo3::exceptions::PyRuntimeError;
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

/// The preference fields an account may save, in their order.
#[pyfunction]
fn preference_fields() -> PyResult<Vec<&'static str>> {
    guard(|| Ok(preferences::FIELDS.to_vec()))
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(module, service_answer, preference_fields);
    Ok(())
}
