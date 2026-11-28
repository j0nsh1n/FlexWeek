//! Account sign-in, create, reset, recovery-code and prompt-routing view-model (P5-A1), moved
//! from `desktop/native/material/bridge_account.py`. Pure state and decisions: no clock reads,
//! no randomness, no clipboard or file I/O.

use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Map, Value, json};

use crate::session::words::{
    PASSWORD_LENGTH_HINT, SESSION_ENDED, SIGN_IN_AGAIN, TOO_MANY_TRIES, USERNAME_ERROR,
};
use crate::views::copy::{
    CREATE_HEADING, CREATE_NOTE, RECOVERY_COPY, RECOVERY_SAVE, RECOVERY_WAIT, RESET_HEADING,
    RESET_NOTE, SIGN_IN_HEADING, short_password_needed, sign_in_problem, sign_up_problem,
};

pub const RECOVERY_HEADING: &str = "Save these recovery codes";
pub const RECOVERY_NOTE: &str = concat!(
    "They are the only way to reset your password. FlexWeek can't email you. ",
    "Copy them somewhere you will still have if this computer is gone."
);
pub const RECOVERY_ACK: &str = "I have saved these codes";
pub const RECOVERY_CONTINUE: &str = "Continue to my week";
pub const WHY_TITLE: &str = "Why it doesn't say which";
pub const USERNAME_HINT: &str = "3 to 32 letters, numbers or underscores.";
pub const TYPE_RECOVERY_CODE: &str = "Type a recovery code.";
pub const SIGN_IN_WHY_LINK: &str = "Why doesn't it say which?";
pub const SIGN_IN_WHY: &str =
    "FlexWeek doesn't say which one is wrong, so no one can use it to find out who has an account.";
pub const RECOVERY_COPIED: &str = "Copied";
pub const RECOVERY_SAVED: &str = "Saved";
pub const RECOVERY_WRITE_FAILED: &str =
    "FlexWeek couldn't save the codes there. Try another folder.";
pub const WRONG_SIGN_IN_PREFIX: &str = "Wrong username or password";
pub const RESET_NO_USERNAME: &str = "Type your username.";
pub const RESET_NO_PASSWORD: &str = "Choose a password with at least 12 characters.";

pub const AUTH_PHASES: [&str; 3] = ["sign-in", "create", "reset"];
pub const PHASES: [&str; 6] = ["sign-in", "create", "reset", "recovery", "setup", "app"];
pub const EDITED_CHOICES: [&str; 3] = ["keep", "replace", "from_today"];

pub const FINISH_WAIT: &str = "wait";
pub const FINISH_DONE: &str = "finish";

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AuthPhase {
    Opening,
    SignIn,
    Create,
    Reset,
    Recovery,
    Setup,
    App,
}

impl AuthPhase {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Opening => "opening",
            Self::SignIn => "sign-in",
            Self::Create => "create",
            Self::Reset => "reset",
            Self::Recovery => "recovery",
            Self::Setup => "setup",
            Self::App => "app",
        }
    }

    pub fn parse(value: &str) -> EngineResult<Self> {
        match value {
            "opening" => Ok(Self::Opening),
            "sign-in" => Ok(Self::SignIn),
            "create" => Ok(Self::Create),
            "reset" => Ok(Self::Reset),
            "recovery" => Ok(Self::Recovery),
            "setup" => Ok(Self::Setup),
            "app" => Ok(Self::App),
            _ => Err(EngineError::value(format!(
                "unknown account phase: {value}"
            ))),
        }
    }

    pub fn is_auth(self) -> bool {
        matches!(self, Self::SignIn | Self::Create | Self::Reset)
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProblemField {
    Username,
    Password,
    Recovery,
    New,
}

impl ProblemField {
    pub fn as_str(self) -> &'static str {
        match self {
            Self::Username => "username",
            Self::Password => "password",
            Self::Recovery => "recovery",
            Self::New => "new",
        }
    }
}

#[derive(Debug, Clone, Default, PartialEq, Eq)]
struct FieldProblems {
    username: String,
    password: String,
    recovery: String,
    new_password: String,
}

impl FieldProblems {
    fn clear(&mut self) {
        self.username.clear();
        self.password.clear();
        self.recovery.clear();
        self.new_password.clear();
    }

    fn set(&mut self, field: ProblemField, message: String) {
        match field {
            ProblemField::Username => self.username = message,
            ProblemField::Password => self.password = message,
            ProblemField::Recovery => self.recovery = message,
            ProblemField::New => self.new_password = message,
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum SubmitAction {
    None,
    Problem,
    Login {
        username: String,
        password: String,
    },
    Register {
        username: String,
        password: String,
    },
    Recover {
        username: String,
        code: String,
        new_password: String,
    },
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum PromptAction {
    None,
    Question { choice: String },
    QuestionClosed,
    Edited { choice: Option<String> },
}

/// Phase chosen when the window opens: signed-in goes straight to the week; a kept session hides
/// the sign-in card behind `opening` until it answers; otherwise sign-in shows.
pub fn initial_phase(has_account: bool, has_kept_token: bool) -> AuthPhase {
    if has_account {
        AuthPhase::App
    } else if has_kept_token {
        AuthPhase::Opening
    } else {
        AuthPhase::SignIn
    }
}

/// Which field a client or server error message belongs under, or `None` for the general status line.
pub fn field_for(phase: AuthPhase, message: &str) -> Option<ProblemField> {
    if message == SIGN_IN_AGAIN || message == SESSION_ENDED {
        return None;
    }
    if message == TOO_MANY_TRIES {
        return Some(if phase == AuthPhase::Reset {
            ProblemField::Recovery
        } else {
            ProblemField::Password
        });
    }
    if message == USERNAME_ERROR {
        return Some(ProblemField::Username);
    }
    if message.starts_with(WRONG_SIGN_IN_PREFIX) {
        return Some(ProblemField::Password);
    }
    let words = message.to_lowercase();
    if words.contains("recovery code") || words.contains("each code") {
        return Some(ProblemField::Recovery);
    }
    if words.contains("username") {
        return Some(ProblemField::Username);
    }
    if words.contains("password") {
        return Some(if phase == AuthPhase::Reset {
            ProblemField::New
        } else {
            ProblemField::Password
        });
    }
    None
}

/// Client-side validation for resetting a password with a recovery code.
pub fn recovery_problem(username: &str, code: &str, new_password: &str) -> String {
    if username.trim().is_empty() {
        return RESET_NO_USERNAME.to_string();
    }
    if code.trim().is_empty() {
        return TYPE_RECOVERY_CODE.to_string();
    }
    if new_password.is_empty() {
        return RESET_NO_PASSWORD.to_string();
    }
    let len = new_password.chars().count();
    if len < 12 {
        return short_password_needed(12 - i64::try_from(len).unwrap_or(0));
    }
    String::new()
}

/// Only the three edited-weeks choices count as answers; anything else cancels.
pub fn edited_prompt_choice(choice: &str) -> Option<&'static str> {
    EDITED_CHOICES.iter().copied().find(|item| *item == choice)
}

/// Constant wording and phase tuples exported to Python so callers keep their names.
pub fn words_json() -> Value {
    json!({
        "recovery_heading": RECOVERY_HEADING,
        "recovery_note": RECOVERY_NOTE,
        "recovery_ack": RECOVERY_ACK,
        "recovery_continue": RECOVERY_CONTINUE,
        "why_title": WHY_TITLE,
        "why_link": SIGN_IN_WHY_LINK,
        "why_body": SIGN_IN_WHY,
        "auth_phases": AUTH_PHASES,
        "phases": PHASES,
    })
}

#[derive(Debug, Clone)]
pub struct AuthState {
    phase: AuthPhase,
    username: String,
    password: String,
    keep_signed_in: bool,
    code: String,
    new_password: String,
    problems: FieldProblems,
    status: String,
    why_open: bool,
    codes: Vec<String>,
    ack: bool,
    copy_label: String,
    save_label: String,
    recovery_status: String,
    ask: Map<String, Value>,
    has_handlers: bool,
    has_edited_done: bool,
}

impl AuthState {
    pub fn new(has_account: bool, has_kept_token: bool, keep_signed_in: bool) -> Self {
        Self {
            phase: initial_phase(has_account, has_kept_token),
            username: String::new(),
            password: String::new(),
            keep_signed_in,
            code: String::new(),
            new_password: String::new(),
            problems: FieldProblems::default(),
            status: String::new(),
            why_open: false,
            codes: Vec::new(),
            ack: false,
            copy_label: RECOVERY_COPY.to_string(),
            save_label: RECOVERY_SAVE.to_string(),
            recovery_status: String::new(),
            ask: Map::new(),
            has_handlers: false,
            has_edited_done: false,
        }
    }

    pub fn phase(&self) -> &'static str {
        self.phase.as_str()
    }

    pub fn set_phase(&mut self, value: &str) -> EngineResult<()> {
        self.phase = AuthPhase::parse(value)?;
        Ok(())
    }

    pub fn codes(&self) -> Vec<String> {
        self.codes.clone()
    }

    pub fn show_sign_in(&mut self, clear: bool) {
        if clear {
            self.username.clear();
            self.password.clear();
            self.code.clear();
            self.new_password.clear();
        }
        self.phase = AuthPhase::SignIn;
        self.clear_problems();
        self.status.clear();
        self.why_open = false;
    }

    pub fn show_create(&mut self) {
        self.phase = AuthPhase::Create;
        self.clear_problems();
        self.status.clear();
        self.why_open = false;
    }

    pub fn show_reset(&mut self) {
        self.phase = AuthPhase::Reset;
        self.clear_problems();
        self.status.clear();
        self.why_open = false;
    }

    pub fn set_username(&mut self, value: String) {
        self.username = value;
        self.problems.username.clear();
    }

    pub fn set_password(&mut self, value: String) {
        self.password = value;
        self.problems.password.clear();
        self.why_open = false;
    }

    pub fn set_recovery_code(&mut self, value: String) {
        self.code = value;
        self.problems.recovery.clear();
    }

    pub fn set_new_password(&mut self, value: String) {
        self.new_password = value;
        self.problems.new_password.clear();
    }

    pub fn set_keep_signed_in(&mut self, on: bool) -> bool {
        self.keep_signed_in = on;
        self.keep_signed_in
    }

    pub fn submit(&mut self) -> EngineResult<SubmitAction> {
        let name = self.username.trim().to_string();
        let (problem, action) = match self.phase {
            AuthPhase::SignIn => (
                sign_in_problem(&name, &self.password)?,
                SubmitAction::Login {
                    username: name,
                    password: self.password.clone(),
                },
            ),
            AuthPhase::Create => (
                sign_up_problem(&name, &self.password)?,
                SubmitAction::Register {
                    username: name,
                    password: self.password.clone(),
                },
            ),
            AuthPhase::Reset => (
                self.recovery_problem(),
                SubmitAction::Recover {
                    username: name,
                    code: self.code.trim().to_string(),
                    new_password: self.new_password.clone(),
                },
            ),
            AuthPhase::Opening | AuthPhase::Recovery | AuthPhase::Setup | AuthPhase::App => {
                return Ok(SubmitAction::None);
            }
        };
        if !problem.is_empty() {
            self.show_problem(&problem);
            return Ok(SubmitAction::Problem);
        }
        Ok(action)
    }

    pub fn explain_why(&mut self) -> bool {
        if self.why_visible() {
            self.why_open = true;
            return true;
        }
        false
    }

    pub fn dismiss_why(&mut self) {
        self.why_open = false;
    }

    pub fn show_recovery(&mut self, codes: Vec<String>) {
        self.codes = codes;
        self.ack = false;
        self.copy_label = RECOVERY_COPY.to_string();
        self.save_label = RECOVERY_SAVE.to_string();
        self.recovery_status.clear();
        self.phase = AuthPhase::Recovery;
    }

    pub fn set_recovery_ack(&mut self, on: bool) {
        self.ack = on;
    }

    /// Marks the copy button label as "Copied" and returns the newline-terminated text to copy.
    pub fn copy_codes(&mut self) -> String {
        self.copy_label = RECOVERY_COPIED.to_string();
        self.recovery_file_text()
    }

    /// Returns the newline-terminated text to write when a non-empty path was picked.
    pub fn recovery_file_payload(&self, path: Option<&str>) -> Option<String> {
        match path {
            Some(chosen) if !chosen.is_empty() => Some(self.recovery_file_text()),
            _ => None,
        }
    }

    pub fn mark_save_failed(&mut self) {
        self.recovery_status = RECOVERY_WRITE_FAILED.to_string();
    }

    pub fn mark_save_succeeded(&mut self) {
        self.recovery_status.clear();
        self.save_label = RECOVERY_SAVED.to_string();
    }

    pub fn finish_recovery(&mut self) -> &'static str {
        if !self.ack {
            self.recovery_status = RECOVERY_WAIT.to_string();
            return FINISH_WAIT;
        }
        FINISH_DONE
    }

    pub fn show_app(&mut self) -> bool {
        if self.phase == AuthPhase::App {
            return false;
        }
        self.phase = AuthPhase::App;
        self.why_open = false;
        true
    }

    pub fn pose_edited(&mut self, ask: Map<String, Value>, has_done: bool) {
        self.ask = ask;
        self.has_edited_done = has_done;
    }

    pub fn ask_value(&self) -> Value {
        Value::Object(self.ask.clone())
    }

    pub fn pose_question(&mut self, question: Map<String, Value>, has_handlers: bool) {
        self.ask = question;
        self.has_handlers = has_handlers;
    }

    pub fn answer(&mut self, choice: &str) -> PromptAction {
        if self.has_handlers {
            self.has_handlers = false;
            self.ask.clear();
            return PromptAction::Question {
                choice: choice.to_string(),
            };
        }
        let picked = edited_prompt_choice(choice).map(str::to_string);
        self.finish_edited(picked)
    }

    pub fn close_sheet(&mut self) -> PromptAction {
        if self.has_handlers {
            self.has_handlers = false;
            self.ask.clear();
            return PromptAction::QuestionClosed;
        }
        self.finish_edited(None)
    }

    pub fn finish_edited(&mut self, choice: Option<String>) -> PromptAction {
        let had_done = self.has_edited_done;
        self.has_edited_done = false;
        if self.ask.is_empty() && !had_done {
            return PromptAction::None;
        }
        self.ask.clear();
        PromptAction::Edited { choice }
    }

    pub fn heading(&self, setup_heading: Option<&str>) -> EngineResult<String> {
        match self.phase {
            AuthPhase::Recovery => Ok(RECOVERY_HEADING.to_string()),
            AuthPhase::Setup => setup_heading
                .map(str::to_string)
                .ok_or_else(|| EngineError::key("setup_step")),
            AuthPhase::SignIn => Ok(SIGN_IN_HEADING.to_string()),
            AuthPhase::Create => Ok(CREATE_HEADING.to_string()),
            AuthPhase::Reset => Ok(RESET_HEADING.to_string()),
            AuthPhase::Opening | AuthPhase::App => Ok(String::new()),
        }
    }

    pub fn note(&self, setup_note: Option<&str>) -> EngineResult<String> {
        match self.phase {
            AuthPhase::Recovery => Ok(RECOVERY_NOTE.to_string()),
            AuthPhase::Create => Ok(CREATE_NOTE.to_string()),
            AuthPhase::Reset => Ok(RESET_NOTE.to_string()),
            AuthPhase::Setup => setup_note
                .map(str::to_string)
                .ok_or_else(|| EngineError::key("setup_step")),
            AuthPhase::SignIn | AuthPhase::Opening | AuthPhase::App => Ok(String::new()),
        }
    }

    pub fn username(&self) -> &str {
        &self.username
    }

    pub fn password(&self) -> &str {
        &self.password
    }

    pub fn keep_signed_in(&self) -> bool {
        self.keep_signed_in
    }

    pub fn username_hint(&self) -> &'static str {
        if self.phase == AuthPhase::Create {
            USERNAME_HINT
        } else {
            ""
        }
    }

    pub fn password_hint(&self) -> &'static str {
        if self.phase == AuthPhase::Create {
            PASSWORD_LENGTH_HINT
        } else {
            ""
        }
    }

    pub fn username_problem(&self) -> &str {
        &self.problems.username
    }

    pub fn password_problem(&self) -> &str {
        &self.problems.password
    }

    pub fn recovery_problem_text(&self) -> &str {
        &self.problems.recovery
    }

    pub fn new_password_problem(&self) -> &str {
        &self.problems.new_password
    }

    pub fn status_line(&self) -> &str {
        &self.status
    }

    pub fn why_visible(&self) -> bool {
        self.problems.password.starts_with(WRONG_SIGN_IN_PREFIX)
    }

    pub fn why_open(&self) -> bool {
        self.why_open
    }

    pub fn recovery_code(&self) -> &str {
        &self.code
    }

    pub fn new_password(&self) -> &str {
        &self.new_password
    }

    pub fn recovery_codes_text(&self) -> String {
        self.codes.join("\n")
    }

    pub fn recovery_ack(&self) -> bool {
        self.ack
    }

    pub fn recovery_ready(&self, busy: bool) -> bool {
        self.ack && !busy
    }

    pub fn copy_label(&self) -> &str {
        &self.copy_label
    }

    pub fn save_label(&self) -> &str {
        &self.save_label
    }

    pub fn recovery_status(&self) -> &str {
        &self.recovery_status
    }

    pub fn on_resume_failed(&mut self) -> bool {
        if self.phase == AuthPhase::Opening {
            self.phase = AuthPhase::SignIn;
            return true;
        }
        false
    }

    pub fn on_status(&mut self, message: &str) -> bool {
        if !self.phase.is_auth() {
            return false;
        }
        if message.is_empty() {
            self.clear_problems();
            self.status.clear();
            return true;
        }
        if message.ends_with('\u{2026}') {
            self.status = message.to_string();
            return true;
        }
        if let Some(field) = field_for(self.phase, message) {
            self.clear_problems();
            self.problems.set(field, message.to_string());
            self.status.clear();
        } else {
            // Unclassified status lines keep any existing field problem intact, matching Python.
            self.status = message.to_string();
        }
        true
    }

    pub fn field_for(&self, message: &str) -> &'static str {
        field_for(self.phase, message)
            .map(ProblemField::as_str)
            .unwrap_or("")
    }

    pub fn show_problem(&mut self, message: &str) {
        self.clear_problems();
        if let Some(field) = field_for(self.phase, message) {
            self.problems.set(field, message.to_string());
            self.status.clear();
        } else {
            self.status = message.to_string();
        }
    }

    pub fn clear_problems(&mut self) {
        self.problems.clear();
        self.why_open = false;
    }

    pub fn recovery_problem(&self) -> String {
        recovery_problem(&self.username, &self.code, &self.new_password)
    }

    pub fn reset_recovery_labels(&mut self) {
        self.copy_label = RECOVERY_COPY.to_string();
        self.save_label = RECOVERY_SAVE.to_string();
    }

    fn recovery_file_text(&self) -> String {
        let mut text = self.codes.join("\n");
        text.push('\n');
        text
    }
}
