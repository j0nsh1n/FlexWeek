//! The window's session in Rust (`flexweek_app::session`, 2.0.0 plan P4) for the Python window:
//! `desktop/native/client.py`'s `NativeClient` sends its requests through a `NativeCore` and takes their
//! answers back as events.

use std::path::PathBuf;
use std::sync::{Arc, Mutex, OnceLock};
use std::time::{Instant, SystemTime, UNIX_EPOCH};

use flexweek_app::session::{Host, Session, frame};
use flexweek_service::accounts::Entropy;
use flexweek_service::plans::Stopwatch;
use flexweek_service::{ServiceError, ServiceResult};
use pyo3::exceptions::PyRuntimeError;
use pyo3::prelude::*;

use crate::guard;
use crate::service::Secrets;

/// The computer as the Python window sees it: a Python object with `steady_ms()`, `request_clock()` (seconds
/// and `YYYY-MM-DDTHH:MM` on the app's clock, which tests set), `restore_token()` and `entropy()` (an object
/// like `secrets`). Called from the window's thread and from workers, each time taking Python's lock only
/// for the call. A call that fails falls back to Rust's own answer, since the session's calls cannot fail.
struct PyHost {
    host: Py<PyAny>,
}

fn started() -> Instant {
    static STARTED: OnceLock<Instant> = OnceLock::new();
    *STARTED.get_or_init(Instant::now)
}

impl PyHost {
    fn ask<T>(&self, name: &str, read: impl FnOnce(&Bound<'_, PyAny>) -> PyResult<T>) -> Option<T> {
        Python::attach(|py| {
            let made = self
                .host
                .bind(py)
                .call_method0(name)
                .and_then(|value| read(&value));
            made.inspect_err(|error| {
                eprintln!("FlexWeek's session host failed in {name}: {error}");
            })
            .ok()
        })
    }
}

impl Host for PyHost {
    fn steady_ms(&self) -> i64 {
        self.ask("steady_ms", |value| value.extract::<i64>())
            .unwrap_or_else(|| i64::try_from(started().elapsed().as_millis()).unwrap_or(i64::MAX))
    }

    fn request_clock(&self) -> (i64, String) {
        self.ask("request_clock", |value| value.extract::<(i64, String)>())
            .unwrap_or_else(|| {
                let seconds = SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map_or(0, |since| i64::try_from(since.as_secs()).unwrap_or(0));
                (seconds, String::new())
            })
    }

    fn restore_token(&self) -> String {
        self.ask("restore_token", |value| value.extract::<String>())
            .unwrap_or_default()
    }

    fn entropy(&self) -> Box<dyn Entropy + Send> {
        match self.ask("entropy", |value| Ok(value.clone().unbind())) {
            Some(module) => Box::new(Secrets {
                module,
                failed: None,
            }),
            None => Box::new(NoEntropy),
        }
    }

    fn stopwatch(&self) -> Stopwatch {
        let started = Instant::now();
        Box::new(move || started.elapsed().as_secs_f64() * 1000.0)
    }
}

/// When the host could not hand out randomness: whatever needed it fails, and nothing is saved.
struct NoEntropy;

impl Entropy for NoEntropy {
    fn session_token(&mut self) -> ServiceResult<String> {
        Err(ServiceError::Broken("no randomness".into()))
    }
    fn salt(&mut self) -> ServiceResult<String> {
        Err(ServiceError::Broken("no randomness".into()))
    }
    fn code_bytes(&mut self) -> ServiceResult<[u8; 8]> {
        Err(ServiceError::Broken("no randomness".into()))
    }
}

/// One window's session: `send`, `view` and `take_event` with JSON text across (flexweek_app::session).
/// `wake()` is called on a worker's thread when an answer is ready, so it must only post to the window's
/// thread. With `inline`, each request is answered as it is sent, on the caller's thread (the desktop
/// tests' light app).
#[pyclass(name = "NativeCore", module = "flexweek_engine")]
pub struct NativeCore {
    session: Mutex<Session>,
}

#[pymethods]
impl NativeCore {
    #[new]
    #[pyo3(signature = (database, host, wake, inline=false))]
    fn new(database: &str, host: Py<PyAny>, wake: Py<PyAny>, inline: bool) -> PyResult<Self> {
        guard(|| {
            let wake = Arc::new(move || {
                Python::attach(|py| {
                    if let Err(error) = wake.bind(py).call0() {
                        eprintln!("FlexWeek's session wake failed: {error}");
                    }
                });
            });
            let mut session =
                Session::new(PathBuf::from(database), Arc::new(PyHost { host }), wake);
            if inline {
                session.frame().answer_inline();
            }
            Ok(Self {
                session: Mutex::new(session),
            })
        })
    }

    /// One command as JSON text; its answer as JSON text. Python's lock is let go of meanwhile, since an
    /// inline request is answered here.
    fn send(&self, py: Python<'_>, command: &str) -> PyResult<String> {
        guard(|| {
            let answer = py.detach(|| {
                self.session
                    .lock()
                    .map(|mut session| session.send(command))
                    .ok()
            });
            answer.ok_or_else(|| PyRuntimeError::new_err("the session failed earlier"))
        })
    }

    fn view(&self, name: &str) -> PyResult<String> {
        guard(|| {
            let session = self
                .session
                .lock()
                .map_err(|_| PyRuntimeError::new_err("the session failed earlier"))?;
            Ok(session.view(name))
        })
    }

    /// Whether the answer just taken said the session ended; told once, here or as the next event.
    fn take_expiry(&self) -> PyResult<bool> {
        guard(|| {
            let mut session = self
                .session
                .lock()
                .map_err(|_| PyRuntimeError::new_err("the session failed earlier"))?;
            Ok(session.take_expiry())
        })
    }

    /// The next event as JSON text (`null` when nothing more has happened).
    fn take_event(&self, py: Python<'_>) -> PyResult<String> {
        guard(|| {
            let event = py.detach(|| {
                self.session
                    .lock()
                    .map(|mut session| session.take_event())
                    .ok()
            });
            event.ok_or_else(|| PyRuntimeError::new_err("the session failed earlier"))
        })
    }
}

/// At quit: skips work not yet started and waits for the work under way, without holding Python's lock
/// (a worker may need it to finish).
#[pyfunction]
fn stop_session_workers(py: Python<'_>) -> PyResult<()> {
    guard(|| {
        py.detach(frame::stop_workers);
        Ok(())
    })
}

/// The words a student reads for a failed request: `status` (0 when no answer came) and the service's
/// `detail` as JSON text.
#[pyfunction]
fn session_error_words(status: u16, detail: &str) -> PyResult<&'static str> {
    guard(|| {
        let detail = serde_json::from_str::<serde_json::Value>(detail).ok();
        Ok(flexweek_app::session::words::error_words(
            status,
            detail.as_ref(),
        ))
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(module, stop_session_workers, session_error_words);
    module.add_class::<NativeCore>()?;
    Ok(())
}
