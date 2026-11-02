//! Material colour schemes. A port of Google's material-color-utilities 0.3.0
//! (Apache-2.0). The notice is in `NOTICE`.

mod color;
mod hct;
mod planes;
mod scheme;
mod temperature;

pub use scheme::{ROLES, material_scheme};
