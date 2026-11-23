//! The 2.0.0 service crate's account rules and reads, for `backend/app.py`'s routes while they still
//! run in Python: each route decodes its request, calls one of these, and turns a `ServiceRefusal`
//! (kind, words) into its answer. Store errors keep the exceptions the routes already answer.

use std::path::Path;

use flexweek_service::accounts::{self, Account, Asker, Entropy, SignedIn};
use flexweek_service::{
    Refusal, ServiceError, ServiceResult, changes, comfort, desk_requests, homework_saves, plans,
    preferences, records, transfer, views, week_saves, weeks,
};
use pyo3::create_exception;
use pyo3::exceptions::{PyException, PyRuntimeError};
use pyo3::prelude::*;
use pyo3::types::{PyInt, PyModule};
use serde_json::Value;

use crate::guard;

create_exception!(flexweek_engine, ServiceRefusal, PyException);

fn service_py(py: Python<'_>, error: ServiceError) -> PyErr {
    match error {
        ServiceError::Refused(refusal) => {
            let kind = match &refusal {
                Refusal::Invalid(_) => "invalid",
                Refusal::Unauthorized(_) => "unauthorized",
                Refusal::NotFound(_) => "not_found",
                Refusal::Conflict(_) => "conflict",
                Refusal::TooMany(_) => "too_many",
                Refusal::TooLarge(_) => "too_large",
            };
            ServiceRefusal::new_err((kind, refusal.words().to_string()))
        }
        ServiceError::Store(error) => crate::rest::store_py(py, error),
        ServiceError::Broken(why) => PyRuntimeError::new_err(why),
    }
}

/// Python's `secrets`, so tokens, salts and codes are made exactly as the routes made them. The service
/// runs without the GIL; each draw takes it back only while it asks Python.
struct Secrets {
    module: Py<PyModule>,
    failed: Option<PyErr>,
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

/// Runs one service call without the GIL, as the routes' own store calls wait on the database and hash
/// passwords without it: holding it there would stop every other Python thread, including one that holds
/// the write lock this call waits for.
fn served<T: Send>(py: Python<'_>, work: impl FnOnce() -> ServiceResult<T> + Send) -> PyResult<T> {
    py.detach(work).map_err(|error| service_py(py, error))
}

fn served_json(
    py: Python<'_>,
    work: impl FnOnce() -> ServiceResult<Value> + Send,
) -> PyResult<String> {
    served(py, work).map(|value| value.to_string())
}

fn with_secrets<T: Send>(
    py: Python<'_>,
    work: impl FnOnce(&mut Secrets) -> Result<T, ServiceError> + Send,
) -> PyResult<T> {
    let mut secrets = Secrets {
        module: py.import("secrets")?.unbind(),
        failed: None,
    };
    let outcome = py.detach(|| work(&mut secrets));
    if let Some(error) = secrets.failed {
        return Err(error);
    }
    outcome.map_err(|error| service_py(py, error))
}

/// The request body as the client sent it. Text that is not JSON is the one refusal every bad request
/// gets, as FastAPI's own check answered it.
fn sent_body(given: &str) -> PyResult<Value> {
    serde_json::from_str(given)
        .map_err(|_| ServiceRefusal::new_err(("invalid", accounts::INVALID_INPUT.to_string())))
}

fn signed_in_tuple(signed: SignedIn) -> (i64, String, String, Option<Vec<String>>) {
    (
        signed.account.id,
        signed.account.username,
        signed.token,
        signed.recovery_codes,
    )
}

fn account(user_id: i64, username: &str) -> Account {
    Account {
        id: user_id,
        username: username.to_string(),
    }
}

/// (id, username, token, recovery codes or None).
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn service_register(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    username: &str,
    password: &str,
    keep: bool,
    previous_token: &str,
) -> PyResult<(i64, String, String, Option<Vec<String>>)> {
    guard(|| {
        with_secrets(py, |secrets| {
            accounts::register(
                Path::new(path),
                Asker { address, now },
                secrets,
                username,
                password,
                keep,
                previous_token,
            )
        })
        .map(signed_in_tuple)
    })
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn service_login(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    username: &str,
    password: &str,
    keep: bool,
    previous_token: &str,
) -> PyResult<(i64, String, String, Option<Vec<String>>)> {
    guard(|| {
        with_secrets(py, |secrets| {
            accounts::login(
                Path::new(path),
                Asker { address, now },
                secrets,
                username,
                password,
                keep,
                previous_token,
            )
        })
        .map(signed_in_tuple)
    })
}

/// (id, username) of the session, refused when it ended or belongs to another account than `expected_id`.
#[pyfunction]
#[pyo3(signature = (path, token, now, expected_id=None))]
fn service_signed_in(
    py: Python<'_>,
    path: &str,
    token: &str,
    now: i64,
    expected_id: Option<&str>,
) -> PyResult<(i64, String)> {
    guard(|| {
        served(py, || {
            accounts::signed_in(Path::new(path), token, now, expected_id)
        })
        .map(|found| (found.id, found.username))
    })
}

#[pyfunction]
#[pyo3(signature = (path, token, now, expected_id=None))]
fn service_logout(
    py: Python<'_>,
    path: &str,
    token: &str,
    now: i64,
    expected_id: Option<&str>,
) -> PyResult<()> {
    guard(|| {
        served(py, || {
            accounts::logout(Path::new(path), token, now, expected_id)
        })
    })
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn service_recover(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    username: &str,
    code: &str,
    new_password: &str,
    keep: bool,
) -> PyResult<(i64, String, String, Option<Vec<String>>)> {
    guard(|| {
        with_secrets(py, |secrets| {
            accounts::recover(
                Path::new(path),
                Asker { address, now },
                secrets,
                username,
                code,
                new_password,
                keep,
            )
        })
        .map(signed_in_tuple)
    })
}

#[pyfunction]
fn service_recovery_codes_left(py: Python<'_>, path: &str, user_id: i64) -> PyResult<i64> {
    guard(|| {
        served(py, || {
            accounts::recovery_codes_left(Path::new(path), user_id)
        })
    })
}

#[pyfunction]
fn service_renew_recovery_codes(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    user_id: i64,
    username: &str,
    password: &str,
) -> PyResult<Vec<String>> {
    guard(|| {
        with_secrets(py, |secrets| {
            accounts::renew_recovery_codes(
                Path::new(path),
                Asker { address, now },
                secrets,
                &account(user_id, username),
                password,
            )
        })
    })
}

/// The new session token.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn service_change_password(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    user_id: i64,
    username: &str,
    current: &str,
    new: &str,
) -> PyResult<String> {
    guard(|| {
        with_secrets(py, |secrets| {
            accounts::change_password(
                Path::new(path),
                Asker { address, now },
                secrets,
                &account(user_id, username),
                current,
                new,
            )
        })
    })
}

#[pyfunction]
fn service_delete_account(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    user_id: i64,
    username: &str,
    password: &str,
) -> PyResult<()> {
    guard(|| {
        served(py, || {
            accounts::delete_account(
                Path::new(path),
                Asker { address, now },
                &account(user_id, username),
                password,
            )
        })
    })
}

#[pyfunction]
fn service_read_week(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    week_start: &str,
) -> PyResult<String> {
    guard(|| {
        served_json(py, || {
            weeks::read_week(Path::new(path), user_id, week_start)
        })
    })
}

#[pyfunction]
fn service_list_weeks(py: Python<'_>, path: &str, user_id: i64) -> PyResult<String> {
    guard(|| served_json(py, || weeks::list_weeks(Path::new(path), user_id)))
}

fn moment(now: &str) -> PyResult<::flexweek_engine::plan::Moment> {
    ::flexweek_engine::plan::parse_moment(now).map_err(crate::raise)
}

#[pyfunction]
fn service_day(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    date: &str,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let now = moment(now)?;
        served_json(py, || views::day(Path::new(path), user_id, date, now))
    })
}

#[pyfunction]
fn service_month(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    month: &str,
    first_day: u32,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let now = moment(now)?;
        served_json(py, || {
            views::month(Path::new(path), user_id, month, first_day, now)
        })
    })
}

#[pyfunction]
fn service_homework(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    week_start: &str,
    include_completed: bool,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let now = moment(now)?;
        served_json(py, || {
            views::homework(Path::new(path), user_id, week_start, include_completed, now)
        })
    })
}

#[pyfunction]
fn service_routines(py: Python<'_>, path: &str, user_id: i64) -> PyResult<String> {
    guard(|| served_json(py, || views::routines(Path::new(path), user_id)))
}

#[pyfunction]
fn service_restore_points(py: Python<'_>, path: &str, user_id: i64) -> PyResult<String> {
    guard(|| served_json(py, || views::restore_points(Path::new(path), user_id)))
}

#[pyfunction]
fn service_read_preferences(py: Python<'_>, path: &str, user_id: i64) -> PyResult<String> {
    guard(|| {
        served_json(py, || {
            preferences::read_preferences(Path::new(path), user_id)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_write_preferences(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    given: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            preferences::write_preferences(Path::new(path), user_id, &given)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_spread_preview(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    id: &str,
    given: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            homework_saves::spread_preview(Path::new(path), user_id, id, &given)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_save_routine(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    id: &str,
    given: &str,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            records::save_routine(Path::new(path), user_id, id, &given, now)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_save_homework(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    id: &str,
    given: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            homework_saves::save_homework(Path::new(path), user_id, id, &given)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_plan(py: Python<'_>, path: &str, user_id: i64, given: &str) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        let start_clock = || -> plans::Stopwatch {
            let started = std::time::Instant::now();
            Box::new(move || started.elapsed().as_secs_f64() * 1000.0)
        };
        served_json(py, || {
            plans::plan(Path::new(path), user_id, &given, &start_clock)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_repeat_edits(py: Python<'_>, path: &str, user_id: i64, given: &str) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            week_saves::preview_repeat_edits(Path::new(path), user_id, &given)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_save_week(py: Python<'_>, path: &str, user_id: i64, given: &str) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            week_saves::save_week(Path::new(path), user_id, &given)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_split_preview(py: Python<'_>, given: &str) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || comfort::split_preview(&given))
    })
}

#[pyfunction]
fn service_create_restore_point(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    given: &str,
    token: &str,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            records::create_restore_point(Path::new(path), user_id, &given, token, now)
        })
    })
}

#[pyfunction]
fn service_restore_preview(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    point_id: &str,
) -> PyResult<String> {
    guard(|| {
        served_json(py, || {
            records::restore_preview(Path::new(path), user_id, point_id)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it.
#[pyfunction]
fn service_restore(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    point_id: &str,
    given: &str,
    token: &str,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            records::restore(Path::new(path), user_id, point_id, &given, token, now)
        })
    })
}

/// `given` is the request body as JSON text; the service checks it. `token` names the restore point a save
/// may ask for, made at `now`.
#[pyfunction]
fn service_changes(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    given: &str,
    token: &str,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            changes::apply_changes(Path::new(path), user_id, &given, token, now)
        })
    })
}

/// `given` is the request body as JSON text (`{"password"}`); `stamp` is when the file is written.
#[pyfunction]
#[allow(clippy::too_many_arguments)]
fn service_export_account(
    py: Python<'_>,
    path: &str,
    address: &str,
    now: i64,
    user_id: i64,
    username: &str,
    given: &str,
    stamp: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            transfer::export_account(
                Path::new(path),
                Asker { address, now },
                &account(user_id, username),
                &given,
                stamp,
            )
        })
    })
}

/// `given` is the request body as JSON text (`{"snapshot"}`).
#[pyfunction]
fn service_import_preview(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    given: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            transfer::import_preview(Path::new(path), user_id, &given)
        })
    })
}

/// `given` is the request body as JSON text; `token` names the restore point made first, at `now`.
#[pyfunction]
fn service_import_account(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    given: &str,
    token: &str,
    now: &str,
) -> PyResult<String> {
    guard(|| {
        let given = sent_body(given)?;
        served_json(py, || {
            transfer::import_account(Path::new(path), user_id, &given, token, now)
        })
    })
}

/// A revision as the store reads it: one past 64 bits can match no stored revision.
fn in_range(revision: &Bound<'_, PyInt>) -> Option<i64> {
    revision.extract::<i64>().ok()
}

#[pyfunction]
#[pyo3(signature = (path, user_id, routine_id, revision, operation_id=None))]
fn service_delete_routine(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    routine_id: &str,
    revision: &Bound<'_, PyInt>,
    operation_id: Option<&str>,
) -> PyResult<String> {
    let revision = in_range(revision);
    guard(|| {
        served_json(py, || {
            records::delete_routine(Path::new(path), user_id, routine_id, revision, operation_id)
        })
    })
}

#[pyfunction]
fn service_delete_homework(
    py: Python<'_>,
    path: &str,
    user_id: i64,
    id: &str,
    revision: &Bound<'_, PyInt>,
) -> PyResult<String> {
    let revision = in_range(revision);
    guard(|| {
        served_json(py, || {
            records::delete_homework(Path::new(path), user_id, id, revision)
        })
    })
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
            module: py.import("secrets")?.unbind(),
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

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("ServiceRefusal", module.py().get_type::<ServiceRefusal>())?;
    crate::export!(
        module,
        service_register,
        service_login,
        service_signed_in,
        service_logout,
        service_recover,
        service_recovery_codes_left,
        service_renew_recovery_codes,
        service_change_password,
        service_delete_account,
        service_read_week,
        service_list_weeks,
        service_day,
        service_month,
        service_homework,
        service_routines,
        service_restore_points,
        service_read_preferences,
        service_write_preferences,
        service_split_preview,
        service_save_week,
        service_save_homework,
        service_save_routine,
        service_spread_preview,
        service_repeat_edits,
        service_plan,
        service_restore_preview,
        service_restore,
        service_changes,
        service_export_account,
        service_import_preview,
        service_import_account,
        service_create_restore_point,
        service_delete_routine,
        service_delete_homework,
        service_answer,
    );
    Ok(())
}
