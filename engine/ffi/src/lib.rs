mod agenda;
mod core;
mod reminders;
mod sync_api;

pub use core::{FfiError, FlexWeek, Host, Reminder};

uniffi::setup_scaffolding!();
