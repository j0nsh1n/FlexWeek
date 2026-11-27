//! View-models for Material screens, theme, and shared helpers (2.0.0 plan, phase P5). Python keeps
//! the Qt types and forwards the decisions here. Plain functions: the caller passes today's date, a
//! fresh id and the local weekday. Nothing here reads a clock, draws a random id, or asks the
//! operating system.

pub mod copy;
pub mod focus;
pub mod hours;
pub mod look_file;
pub mod month;
pub mod sheet_block;
pub mod sheet_homework;
pub mod sheet_preview;
pub mod sheet_rules;
pub mod theme;
pub mod week;
