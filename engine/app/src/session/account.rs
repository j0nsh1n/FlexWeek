//! Signing in, up and out (P4 group 1; `NativeSession.register`, `login`, `recover`, `resume` and `logout` in
//! desktop/native/controller.py). The session sends each flow's request itself and reads its answer: who is
//! signed in, whether the session is busy, and what the status line says. The window is told the outcome as
//! one event and does what is still its own (setup answers, the kept session's file, loading the week).
//!
//! As before, an answer for a request the window has moved on from changes nothing; a failed sign-in or sign-up
//! is worded for the sign-in card ([`auth_words`]); a kept session that no longer works is signed out of and,
//! when the service ended it, forgotten.

use serde_json::{Value, json};

use super::Session;
use super::frame::{Event, Identity, Outcome};

/// Said when a sign-in's answer cannot be read as an account.
const UNDISPLAYABLE: &str = "FlexWeek could not display this response.";

/// A flow waiting for its request's answer, with the ticket it began with.
#[derive(Clone, Copy, Debug)]
pub(super) enum Flow {
    Register { ticket: u64 },
    Login { ticket: u64 },
    Recover { ticket: u64 },
    Resume { ticket: u64 },
    Logout { ticket: u64, account: Option<i64> },
}

/// The words for a sign-in (`creating` false) or sign-up that failed on the way: the general ones speak of
/// changes that may not have been saved, which a sign-in never has (client.py `auth_error`).
pub fn auth_words(status: u16, message: &str, creating: bool) -> String {
    let then = if creating {
        "create your account"
    } else {
        "sign in"
    };
    match status {
        0 => format!("FlexWeek stopped responding. Close FlexWeek, open it again, then {then}."),
        503 => format!("FlexWeek can't open its saved data right now. Wait a minute, then {then}."),
        _ => message.to_string(),
    }
}

fn identity(body: &Value) -> Option<Identity> {
    let id = body.get("id")?.as_i64()?;
    let username = body.get("username")?.as_str()?.to_string();
    (id > 0 && !username.is_empty()).then_some(Identity { id, username })
}

fn account_json(identity: &Identity) -> Value {
    json!({ "id": identity.id, "username": identity.username })
}

impl Session {
    /// Starts a flow: a new ticket, busy, its words, and its request sent by the session.
    fn begin_flow(
        &mut self,
        words: &str,
        method: &str,
        path: &str,
        body: Option<&Value>,
        flow: impl FnOnce(u64) -> Flow,
    ) -> Result<Value, String> {
        let ticket = self.status.begin(false);
        self.status.say(words);
        let number = self.frame.request(method, path, body)?;
        self.flows.insert(number, flow(ticket));
        Ok(json!({ "ticket": ticket }))
    }

    pub(super) fn register(
        &mut self,
        username: &str,
        password: &str,
        keep: bool,
    ) -> Result<Value, String> {
        let body = json!({ "username": username, "password": password, "keep": keep });
        self.begin_flow(
            "Creating account…",
            "POST",
            "/api/auth/register",
            Some(&body),
            |ticket| Flow::Register { ticket },
        )
    }

    pub(super) fn login(
        &mut self,
        username: &str,
        password: &str,
        keep: bool,
    ) -> Result<Value, String> {
        let body = json!({ "username": username, "password": password, "keep": keep });
        self.begin_flow(
            "Signing in…",
            "POST",
            "/api/auth/login",
            Some(&body),
            |ticket| Flow::Login { ticket },
        )
    }

    pub(super) fn recover(
        &mut self,
        username: &str,
        code: &str,
        password: &str,
        keep: bool,
    ) -> Result<Value, String> {
        let body =
            json!({ "username": username, "code": code, "password": password, "keep": keep });
        self.begin_flow(
            "Recovering account…",
            "POST",
            "/api/auth/recover",
            Some(&body),
            |ticket| Flow::Recover { ticket },
        )
    }

    /// Takes up a session kept from an earlier launch; asking who it belongs to says whether it still works.
    pub(super) fn resume(&mut self, token: &str) -> Result<Value, String> {
        if token.is_empty() {
            return Err("a kept session has a token".into());
        }
        let ticket = self.status.begin(false);
        self.status.say("Signing in…");
        self.frame.adopt_session(token);
        let number = self.frame.request("GET", "/api/auth/me", None)?;
        self.flows.insert(number, Flow::Resume { ticket });
        Ok(json!({ "ticket": ticket }))
    }

    /// Signs out of `account` (the window's; None when no one is). With no session to end it finishes at once,
    /// and the answer carries the `signed_out` event.
    pub(super) fn logout(&mut self, account: Option<i64>) -> Result<Value, String> {
        let ticket = self.status.begin(false);
        self.status.say("Signing out…");
        if self.frame.account().is_none() {
            let finished = self.signed_out(ticket, account);
            return Ok(json!({ "ticket": ticket, "finished": finished }));
        }
        let number = self.frame.request("POST", "/api/auth/logout", None)?;
        self.flows.insert(number, Flow::Logout { ticket, account });
        Ok(json!({ "ticket": ticket, "finished": null }))
    }

    /// What a flow makes of its request's answer, as the event the window is told; None when the window has
    /// moved on from it.
    pub(super) fn finish_flow(&mut self, flow: Flow, event: Event) -> Option<Value> {
        let outcome = match event {
            Event::Answered { outcome, .. } => outcome,
            // Sent before a sign-in or sign-out: it changes nothing, as its callbacks were never called.
            Event::Dropped { .. } | Event::Expired => return None,
        };
        match flow {
            Flow::Register { ticket } => self.registered(ticket, outcome),
            Flow::Login { ticket } => self.signed_in(ticket, outcome, "login", Some(false)),
            Flow::Recover { ticket } => self.signed_in(ticket, outcome, "recover", None),
            Flow::Resume { ticket } => self.resumed(ticket, outcome),
            Flow::Logout { ticket, account } => self.signed_out(ticket, account),
        }
    }

    /// A sign-in that worked: idle, and signed in as the answer's account. `auth` words a failure for the
    /// sign-in card (Some(creating)), or leaves the service's words (None).
    fn signed_in(
        &mut self,
        ticket: u64,
        outcome: Outcome,
        how: &str,
        auth: Option<bool>,
    ) -> Option<Value> {
        if !self.status.alive(ticket) {
            return None;
        }
        let (status, body) = match outcome {
            Outcome::Ok { status, body } => (status, body),
            Outcome::Failed { status, message } => {
                return self.failed(ticket, status, &message, auth);
            }
        };
        let Some(made) = identity(&body) else {
            return self.failed(ticket, status, UNDISPLAYABLE, auth);
        };
        self.status.idle(ticket);
        self.frame.set_account(made.clone()).ok()?;
        Some(json!({ "kind": "signed_in", "how": how, "account": account_json(&made) }))
    }

    fn registered(&mut self, ticket: u64, outcome: Outcome) -> Option<Value> {
        if !self.status.alive(ticket) {
            return None;
        }
        let (status, body) = match outcome {
            Outcome::Ok { status, body } => (status, body),
            Outcome::Failed { status, message } => {
                return self.failed(ticket, status, &message, Some(true));
            }
        };
        let Some(made) = identity(&body) else {
            return self.failed(ticket, status, UNDISPLAYABLE, Some(true));
        };
        self.frame.set_account(made.clone()).ok()?;
        self.status.set_busy(false);
        self.status
            .say("Save these recovery codes before continuing.");
        let codes = body
            .get("recovery_codes")
            .cloned()
            .unwrap_or_else(|| json!([]));
        Some(json!({ "kind": "registered", "account": account_json(&made), "codes": codes }))
    }

    /// A kept session that failed is signed out of whatever the window did meanwhile, and forgotten when the
    /// service said it no longer works (401); the words follow only if the window is still waiting on it.
    fn resumed(&mut self, ticket: u64, outcome: Outcome) -> Option<Value> {
        let (status, message) = match outcome {
            Outcome::Ok { status, body } => match identity(&body) {
                Some(_) => {
                    return self.signed_in(ticket, Outcome::Ok { status, body }, "resume", None);
                }
                None => (status, UNDISPLAYABLE.to_string()),
            },
            Outcome::Failed { status, message } => (status, message),
        };
        self.frame.reset();
        let idle = self.status.idle(ticket);
        if idle {
            self.status.say(&message);
        }
        Some(
            json!({ "kind": "auth_failed", "idle": idle, "forget": status == 401, "message": message }),
        )
    }

    fn failed(
        &mut self,
        ticket: u64,
        status: u16,
        message: &str,
        auth: Option<bool>,
    ) -> Option<Value> {
        if !self.status.idle(ticket) {
            return None;
        }
        let message = match auth {
            Some(creating) => auth_words(status, message, creating),
            None => message.to_string(),
        };
        self.status.say(&message);
        Some(json!({ "kind": "auth_failed", "idle": true, "forget": false, "message": message }))
    }

    /// Signed out, whatever the service answered: no account, no session, not busy.
    fn signed_out(&mut self, ticket: u64, account: Option<i64>) -> Option<Value> {
        if !self.status.alive(ticket) {
            return None;
        }
        self.frame.reset();
        self.status.set_busy(false);
        self.status.say("Signed out.");
        Some(json!({ "kind": "signed_out", "account_id": account }))
    }
}
