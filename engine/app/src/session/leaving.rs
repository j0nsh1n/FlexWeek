//! Saving before leaving (P4 group 2; `NativeWindow._save_before_leaving` in desktop/native/window.py): closing
//! FlexWeek or signing out with changes not yet saved waits for them, polling, and leaves once they are in; if a
//! save fails, or the wait runs out, it stays open and says so. The window runs the poll's timer and does each
//! step; the session decides the step.

/// What the window does on one poll.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Step {
    /// A request is in flight: poll again.
    Wait,
    /// Save the week on screen (the first time it is found unsaved).
    Save,
    /// Open a week parked with unsaved changes, so it can be saved next.
    Load,
    /// Everything is saved: leave.
    Leave,
    /// The save failed or the wait ran out: stay open and say so.
    GiveUp,
}

impl Step {
    pub fn name(self) -> &'static str {
        match self {
            Step::Wait => "wait",
            Step::Save => "save",
            Step::Load => "load",
            Step::Leave => "leave",
            Step::GiveUp => "give_up",
        }
    }
}

#[derive(Debug, Default)]
pub struct Leaving {
    /// How long has been waited, counted in polls.
    waited_ms: i64,
    /// The longest wait.
    limit_ms: i64,
    /// The week on screen was saved once already while leaving: still unsaved after that, the save failed.
    tried_week: bool,
    /// What the student was doing, for the words if it gives up ("close FlexWeek again", "sign out again").
    again: String,
}

impl Leaving {
    /// Starts leaving, waiting at most `limit_ms`; `again` names what to do once the save is retried.
    pub fn start(&mut self, limit_ms: i64, again: &str) {
        *self = Leaving {
            waited_ms: 0,
            limit_ms,
            tried_week: false,
            again: again.to_string(),
        };
    }

    /// One poll, `poll_ms` after the last: `busy` (a request in flight), `held` (the week on screen has unsaved
    /// changes), `parked` (another week does).
    pub fn poll(&mut self, poll_ms: i64, busy: bool, held: bool, parked: bool) -> Step {
        self.waited_ms += poll_ms;
        if self.waited_ms > self.limit_ms {
            return Step::GiveUp;
        }
        if busy {
            return Step::Wait;
        }
        if held {
            if self.tried_week {
                return Step::GiveUp;
            }
            self.tried_week = true;
            return Step::Save;
        }
        if parked {
            self.tried_week = false;
            return Step::Load;
        }
        Step::Leave
    }

    /// What the window says when it gives up.
    pub fn gave_up_words(&self) -> String {
        format!(
            "Couldn't save, so FlexWeek stayed open. Your changes are still on screen. Choose Retry save, then {}.",
            self.again
        )
    }
}
