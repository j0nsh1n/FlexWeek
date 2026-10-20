mod account;
mod agenda;
mod core;
mod focus;
mod hand_move;
mod homework;
mod plan_week;
mod reminders;
mod running_late;
mod sync_api;
mod update;
mod week_rows;
mod week_shape;

pub use core::{FfiError, FlexWeek, HandLanding, Host, Reminder};

uniffi::setup_scaffolding!();
