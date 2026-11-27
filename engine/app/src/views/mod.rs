//! Screen copy and the sheet rules the bridges share (FlexWeek 2.0.0, P5). Plain functions: the
//! caller passes today's date, a fresh id and the local weekday. Nothing here reads a clock, draws
//! a random id, or asks the operating system.

pub mod copy;
pub mod sheet_rules;
