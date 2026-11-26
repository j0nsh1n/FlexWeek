//! When the week saves itself (P4 group 2; `NativeWindow._autosave_tick` in desktop/native/window.py). Save
//! stopped being a button, so this has to be dependable rather than clever: it waits for the student to stop
//! changing things, never saves while a request is in flight, and never touches a week whose save came back
//! 409 (another window wrote it; answering that is the student's decision, not a timer's). A save that failed
//! keeps its payload and operation id, so trying it again every [`RETRY_MS`] writes the same thing once.
//!
//! Times are on the host's steady clock, as durations: a clock set back must not hold a save.

/// How long after the last change the week saves itself. Long enough that dragging a block does not save on
/// every pixel, short enough that closing the laptop straight after a change keeps it.
pub const AFTER_MS: i64 = 1_500;
/// How long a failed save waits before it is tried again.
pub const RETRY_MS: i64 = 6_000;

/// The open draft and whether the window is signed in.
#[derive(Clone, Copy, Debug, Default)]
pub struct Week {
    pub signed_in: bool,
    pub conflict: bool,
    pub dirty: bool,
    /// A save that failed is waiting to be tried again.
    pub pending: bool,
}

impl Week {
    pub(super) fn can_save(self, busy: bool) -> bool {
        self.signed_in && !busy && !self.conflict
    }
}

#[derive(Debug, Default)]
pub struct Autosave {
    /// When the last change was made.
    pub changed_ms: i64,
    /// When a save was last started by the timer, or last failed.
    pub last_try_ms: i64,
}

impl Autosave {
    /// Whether to save now, at `now` on the steady clock; a save counts as tried from now. `busy`: a request
    /// is in flight.
    pub fn due(&mut self, week: Week, busy: bool, now: i64) -> bool {
        if !week.can_save(busy) {
            return false;
        }
        let due = if week.pending {
            now - self.last_try_ms >= RETRY_MS
        } else {
            week.dirty && now - self.changed_ms >= AFTER_MS
        };
        if due {
            self.last_try_ms = now;
        }
        due
    }
}
