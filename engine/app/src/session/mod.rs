//! The session the window holds (`desktop/native/controller.py`'s `NativeSession` today), moving into Rust
//! group by group (2.0.0 plan, P4). The window talks to it in three calls with JSON text across, so a
//! Python window and a Rust one use it the same way:
//!
//! - `send(command)`: `{"cmd": ...}`; answers `{"ok": true, ...}` or `{"ok": false, "error": ...}`;
//! - `view(name)`: what one part of the session holds now;
//! - `take_events()`: what happened since the last call, in order.
//!
//! So far: the frame (group 1), which sends requests and takes their answers back.

pub mod frame;
pub mod words;

use std::path::PathBuf;
use std::sync::Arc;

use serde_json::{Value, json};

pub use frame::{Event, Frame, Host, Identity, Outcome};

pub struct Session {
    frame: Frame,
}

impl Session {
    pub fn new(database: PathBuf, host: Arc<dyn Host>, wake: Arc<dyn Fn() + Send + Sync>) -> Self {
        Self {
            frame: Frame::new(database, host, wake),
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
            other => Err(format!("no command called {other:?}")),
        }
    }

    /// One view as JSON text. `frame`: the account, the epoch, whether a session is held, and how many
    /// requests wait.
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
                })
                .to_string()
            }
            other => json!({ "error": format!("no view called {other:?}") }).to_string(),
        }
    }

    /// The events since the last call, as a JSON array.
    pub fn take_events(&mut self) -> String {
        Value::Array(
            self.frame
                .take_events()
                .iter()
                .map(Event::to_json)
                .collect(),
        )
        .to_string()
    }
}
