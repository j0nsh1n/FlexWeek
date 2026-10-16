mod account;
mod agenda;
mod core;
mod homework;
mod plan_week;
mod reminders;
mod running_late;
mod sync_api;
mod update;
mod week_shape;

pub use core::{FfiError, FlexWeek, Host, Reminder};

uniffi::setup_scaffolding!();
