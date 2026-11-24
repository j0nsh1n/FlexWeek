//! The session the window holds (`desktop/native/controller.py`'s `NativeSession` today), moving into Rust
//! group by group (2.0.0 plan, P4). The window talks to it in three calls with JSON text across, so a
//! Python window and a Rust one use it the same way:
//!
//! - `send(command)`: `{"cmd": ...}`; answers `{"ok": true, ...}` or `{"ok": false, "error": ...}`;
//! - `view(name)`: what one part of the session holds now;
//! - `take_event()`: the next thing that happened, or `null`; one at a time, so what the window does with
//!   one (signing out, say) counts before the next is read.
//!
//! So far: the frame (group 1), which sends requests and takes their answers back, and the status (which
//! request is the latest, whether the session is busy, the status line).

pub mod autosave;
pub mod frame;
pub mod status;
pub mod words;

use std::path::PathBuf;
use std::sync::Arc;

use serde_json::{Value, json};

pub use frame::{Event, Frame, Host, Identity, Outcome};
pub use status::Status;

pub struct Session {
    frame: Frame,
    status: Status,
    autosave: autosave::Autosave,
}

impl Session {
    pub fn new(database: PathBuf, host: Arc<dyn Host>, wake: Arc<dyn Fn() + Send + Sync>) -> Self {
        Self {
            frame: Frame::new(database, host, wake),
            status: Status::default(),
            autosave: autosave::Autosave::default(),
        }
    }

    pub fn frame(&mut self) -> &mut Frame {
        &mut self.frame
    }

    /// One command as JSON text; its answer as JSON text.
    pub fn send(&mut self, command: &str) -> String {
        let answer = match serde_json::from_str::<Value>(command) {
            Ok(command) => self.command(&command),
            Err(error) => Err(format!("a command is JSON: {error}")),
        };
        match answer {
            Ok(Value::Object(mut fields)) => {
                fields.insert("ok".into(), Value::Bool(true));
                Value::Object(fields).to_string()
            }
            Ok(_) => json!({ "ok": true }).to_string(),
            Err(error) => json!({ "ok": false, "error": error }).to_string(),
        }
    }

    fn command(&mut self, command: &Value) -> Result<Value, String> {
        let text = |name: &str| -> Result<&str, String> {
            command[name]
                .as_str()
                .ok_or_else(|| format!("{name} is text"))
        };
        match command["cmd"].as_str() {
            Some("request") => {
                let body = match &command["body"] {
                    Value::Null => None,
                    body => Some(body),
                };
                let number = self.frame.request(text("method")?, text("path")?, body)?;
                Ok(json!({ "number": number }))
            }
            Some("set_account") => {
                let id = command["id"].as_i64().ok_or("id is a whole number")?;
                let username = text("username")?.to_string();
                self.frame.set_account(Identity { id, username })?;
                Ok(json!({}))
            }
            Some("reset") => {
                self.frame.reset();
                Ok(json!({}))
            }
            Some("adopt_session") => {
                self.frame.adopt_session(text("token")?);
                Ok(json!({}))
            }
            Some("begin") => {
                let planning = match &command["planning"] {
                    Value::Null => false,
                    planning => planning.as_bool().ok_or("planning is true or false")?,
                };
                Ok(json!({ "ticket": self.status.begin(planning) }))
            }
            Some("idle") => {
                let ticket = command["ticket"]
                    .as_u64()
                    .ok_or("ticket is a whole number")?;
                Ok(json!({ "idle": self.status.idle(ticket) }))
            }
            Some("cancel") => {
                self.status.cancel();
                Ok(json!({}))
            }
            Some("set_busy") => {
                let busy = command["busy"].as_bool().ok_or("busy is true or false")?;
                self.status.set_busy(busy);
                Ok(json!({}))
            }
            Some("autosave") => {
                let flag = |name: &str| -> Result<bool, String> {
                    command[name]
                        .as_bool()
                        .ok_or_else(|| format!("{name} is true or false"))
                };
                let week = autosave::Week {
                    signed_in: flag("signed_in")?,
                    conflict: flag("conflict")?,
                    dirty: flag("dirty")?,
                    pending: flag("pending")?,
                };
                let now = self.frame.steady_ms();
                Ok(json!({ "save": self.autosave.due(week, self.status.busy(), now) }))
            }
            Some("autosave_times") => {
                let time = |name: &str| -> Result<Option<i64>, String> {
                    match &command[name] {
                        Value::Null => Ok(None),
                        value => value
                            .as_i64()
                            .map(Some)
                            .ok_or_else(|| format!("{name} is a whole number")),
                    }
                };
                if let Some(changed) = time("changed_ms")? {
                    self.autosave.changed_ms = changed;
                }
                if let Some(tried) = time("last_try_ms")? {
                    self.autosave.last_try_ms = tried;
                }
                Ok(json!({}))
            }
            Some("autosave_changed") => {
                self.autosave.changed_ms = self.frame.steady_ms();
                Ok(json!({}))
            }
            Some("autosave_failed") => {
                self.autosave.last_try_ms = self.frame.steady_ms();
                Ok(json!({}))
            }
            Some("say") => {
                self.status.say(text("text")?);
                Ok(json!({}))
            }
            other => Err(format!("no command called {other:?}")),
        }
    }

    /// One view as JSON text. `frame`: the account, the epoch, the session token held (or null), how many
    /// requests wait, and when on the steady clock the next one reaches its limit (or null). `status`: the
    /// latest ticket, whether the session is busy or planning, and the status line.
    pub fn view(&self, name: &str) -> String {
        match name {
            "frame" => {
                let account = self
                    .frame
                    .account()
                    .map(|identity| json!({ "id": identity.id, "username": identity.username }));
                json!({
                    "account": account,
                    "epoch": self.frame.epoch(),
                    "token": self.frame.token(),
                    "waiting": self.frame.waiting(),
                    "next_deadline": self.frame.next_deadline(),
                })
                .to_string()
            }
            "status" => json!({
                "ticket": self.status.ticket(),
                "busy": self.status.busy(),
                "planning": self.status.planning(),
                "message": self.status.message(),
            })
            .to_string(),
            "autosave" => json!({
                "changed_ms": self.autosave.changed_ms,
                "last_try_ms": self.autosave.last_try_ms,
                "after_ms": autosave::AFTER_MS,
                "retry_ms": autosave::RETRY_MS,
            })
            .to_string(),
            other => json!({ "error": format!("no view called {other:?}") }).to_string(),
        }
    }

    /// Whether the answer just taken said the session ended (see [`Frame::take_expiry`]).
    pub fn take_expiry(&mut self) -> bool {
        self.frame.take_expiry()
    }

    /// The next event as JSON text, or `null` when nothing more has happened.
    pub fn take_event(&mut self) -> String {
        self.frame
            .take_event()
            .map_or(Value::Null, |event| event.to_json())
            .to_string()
    }
}
