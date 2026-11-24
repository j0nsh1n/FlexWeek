//! The desktop app's core with no window toolkit: the session that `NativeSession` holds today
//! (`desktop/native/controller.py`: loading and saving, undo, homework and blocks, planning, focus,
//! reminders, preferences), each screen's state as plain view-models, and the shell's decisions. Screens read
//! its views and send it commands; slow work goes to worker threads (2.0.0 plan, phases P4 and P5).

pub mod session;
pub mod upgrade;
