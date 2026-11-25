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

pub mod account;
pub mod autosave;
pub mod copies;
pub mod focus;
pub mod frame;
pub mod homework_edits;
pub mod leaving;
pub mod preferences;
pub mod reminders;
pub mod spotify;
pub mod status;
pub mod transfer;
pub mod words;

use std::collections::BTreeMap;
use std::path::PathBuf;
use std::sync::Arc;

use serde_json::{Value, json};

pub use frame::{Event, Frame, Host, Identity, Outcome};
pub use status::Status;

pub struct Session {
    frame: Frame,
    status: Status,
    /// Flows (signing in, up or out) waiting for their request's answer, by request number.
    flows: BTreeMap<u64, account::Flow>,
    autosave: autosave::Autosave,
    leaving: leaving::Leaving,
}

impl Session {
    pub fn new(database: PathBuf, host: Arc<dyn Host>, wake: Arc<dyn Fn() + Send + Sync>) -> Self {
        Self {
            frame: Frame::new(database, host, wake),
            status: Status::default(),
            flows: BTreeMap::new(),
            autosave: autosave::Autosave::default(),
            leaving: leaving::Leaving::default(),
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
            Some("register") => {
                let keep = command["keep"].as_bool().ok_or("keep is true or false")?;
                self.register(text("username")?, text("password")?, keep)
            }
            Some("login") => {
                let keep = command["keep"].as_bool().ok_or("keep is true or false")?;
                self.login(text("username")?, text("password")?, keep)
            }
            Some("recover") => {
                let keep = command["keep"].as_bool().ok_or("keep is true or false")?;
                self.recover(text("username")?, text("code")?, text("password")?, keep)
            }
            Some("resume") => self.resume(text("token")?),
            Some("logout") => self.logout(command["account_id"].as_i64()),
            Some("change_password") => {
                self.change_password(text("current_password")?, text("new_password")?)
            }
            Some("replace_recovery_codes") => self.replace_recovery_codes(text("password")?),
            Some("delete_account") => {
                let owner = command["owner"].as_str().map(str::to_string);
                self.delete_account(text("password")?, owner)
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
                let busy = self.status.busy();
                // The clock is read only when a save could be due, as the window did.
                let save = !(!week.signed_in || busy || week.conflict)
                    && self.autosave.due(week, busy, self.frame.steady_ms());
                Ok(json!({ "save": save }))
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
                let (changed, tried) = (time("changed_ms")?, time("last_try_ms")?);
                if let Some(changed) = changed {
                    self.autosave.changed_ms = changed;
                }
                if let Some(tried) = tried {
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
            Some("leaving_start") => {
                let limit = command["limit_ms"]
                    .as_i64()
                    .ok_or("limit_ms is a whole number")?;
                self.leaving.start(limit, text("again")?);
                Ok(json!({}))
            }
            Some("leaving_poll") => {
                let poll = command["poll_ms"]
                    .as_i64()
                    .ok_or("poll_ms is a whole number")?;
                let flag = |name: &str| -> Result<bool, String> {
                    command[name]
                        .as_bool()
                        .ok_or_else(|| format!("{name} is true or false"))
                };
                let (held, parked) = (flag("held")?, flag("parked")?);
                let step = self.leaving.poll(poll, self.status.busy(), held, parked);
                let mut answer = json!({ "step": step.name() });
                if step == leaving::Step::GiveUp {
                    answer["words"] = json!(self.leaving.gave_up_words());
                }
                Ok(answer)
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

    /// The next event as JSON text, or `null` when nothing more has happened. A flow's answer is read here
    /// and told as the flow's own event (account.rs); one the window has moved on from is passed over.
    pub fn take_event(&mut self) -> String {
        while let Some(event) = self.frame.take_event() {
            let flow = match &event {
                Event::Answered { number, .. } | Event::Dropped { number } => {
                    self.flows.remove(number)
                }
                Event::Expired => None,
            };
            match flow {
                Some(flow) => {
                    if let Some(told) = self.finish_flow(flow, event) {
                        return told.to_string();
                    }
                }
                None => return event.to_json().to_string(),
            }
        }
        Value::Null.to_string()
    }
}
