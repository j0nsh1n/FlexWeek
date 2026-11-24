//! What the session is doing (P4 group 1, `NativeSession`'s `_begin`, `_idle`, `_say` and `planning` in
//! desktop/native/controller.py): each request the window starts takes a new ticket and makes the session busy;
//! only the latest ticket's answer may make it idle again, so an answer to a request the window has moved on
//! from changes nothing. The status line's words are kept here too.

/// The window's current request and status line.
#[derive(Debug, Default)]
pub struct Status {
    ticket: u64,
    /// The ticket of a Plan asked for, while it is the latest one.
    plan_ticket: Option<u64>,
    busy: bool,
    message: String,
}

impl Status {
    /// A new request: it gets the next ticket, and the session is busy until that ticket's answer is in.
    /// `planning` marks it as a Plan, which the window shows differently.
    pub fn begin(&mut self, planning: bool) -> u64 {
        self.ticket += 1;
        self.plan_ticket = planning.then_some(self.ticket);
        self.busy = true;
        self.ticket
    }

    /// Whether `ticket` is still the latest request.
    pub fn alive(&self, ticket: u64) -> bool {
        ticket == self.ticket
    }

    /// The answer to `ticket` is in: the session is no longer busy, if it is still the latest request. Says
    /// whether it was.
    pub fn idle(&mut self, ticket: u64) -> bool {
        if !self.alive(ticket) {
            return false;
        }
        self.busy = false;
        true
    }

    /// Every request under way stops counting (the session ended): none of their answers can make the
    /// session idle, and it is not busy.
    pub fn cancel(&mut self) {
        self.ticket += 1;
        self.busy = false;
    }

    pub fn set_busy(&mut self, busy: bool) {
        self.busy = busy;
    }

    pub fn say(&mut self, text: &str) {
        self.message = text.to_string();
    }

    pub fn ticket(&self) -> u64 {
        self.ticket
    }

    pub fn busy(&self) -> bool {
        self.busy
    }

    /// A Plan was asked for and its answer is not in yet.
    pub fn planning(&self) -> bool {
        self.busy && self.plan_ticket == Some(self.ticket)
    }

    pub fn message(&self) -> &str {
        &self.message
    }
}
