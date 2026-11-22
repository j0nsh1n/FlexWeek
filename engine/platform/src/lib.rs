//! The operating-system pieces, behind traits the app core calls: the data folder, the kept sign-in and
//! single instance, the updater's download and swap, the login entry, sounds, notifications, Spotify, opening
//! links, and the clock. This is the only desktop crate that may read the real time (2.0.0 plan, phase P6).

pub mod clock;
pub mod folders;
