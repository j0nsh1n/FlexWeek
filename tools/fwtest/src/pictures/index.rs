//! What `scripts/pictures/render.py` writes: `index.json` beside the pictures, and the registry
//! `--list` prints. Parsed at the file boundary; a field the renderer leaves out takes its default.

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

/// One declared screen, as `render.py --list` prints it.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Listed {
    pub id: String,
    #[serde(default)]
    pub area: String,
    #[serde(default)]
    pub sources: Vec<String>,
    /// The screens file that declares it, relative to the checkout.
    #[serde(default)]
    pub module: String,
    #[serde(default)]
    pub main: bool,
    #[serde(default)]
    pub styles: Vec<String>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Listing {
    #[serde(default)]
    pub screens: Vec<Listed>,
    #[serde(default)]
    pub problems: Vec<Problem>,
}

/// A screens file that could not be read, or a screen that could not be drawn at all.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Problem {
    #[serde(default)]
    pub module: String,
    #[serde(default)]
    pub screen: String,
    #[serde(default)]
    pub error: String,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Label {
    #[serde(default)]
    pub name: String,
    #[serde(default)]
    pub kind: String,
    #[serde(default)]
    pub text: String,
    #[serde(default)]
    pub rect: Vec<i64>,
    /// None when it cannot be told (rich text).
    #[serde(default)]
    pub too_wide: Option<bool>,
    #[serde(default)]
    pub ink: Option<String>,
    #[serde(default)]
    pub behind: Option<String>,
    #[serde(default)]
    pub contrast: Option<f64>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Focus {
    #[serde(default)]
    pub focused: Option<String>,
    #[serde(default)]
    pub ring: Option<bool>,
    #[serde(default)]
    pub changed_pixels: Option<i64>,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Measurements {
    #[serde(default)]
    pub labels: Vec<Label>,
    #[serde(default)]
    pub focus: Option<Focus>,
}

/// One picture of one screen in one variant.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Picture {
    pub screen: String,
    #[serde(default)]
    pub area: String,
    #[serde(default)]
    pub variant: String,
    #[serde(default)]
    pub checks: String,
    #[serde(default)]
    pub sources: Vec<String>,
    /// The PNG, relative to the folder holding index.json; None when drawing failed.
    #[serde(default)]
    pub picture: Option<String>,
    #[serde(default)]
    pub measurements: Option<Measurements>,
    #[serde(default)]
    pub error: Option<String>,
}

impl Picture {
    /// `<screen>/<variant>`: the same picture on both sides of a comparison.
    pub fn key(&self) -> String {
        format!("{}/{}", self.screen, self.variant)
    }
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Index {
    #[serde(default)]
    pub version: u32,
    #[serde(default)]
    pub set: String,
    #[serde(default)]
    pub commit: String,
    #[serde(default)]
    pub problems: Vec<Problem>,
    #[serde(default)]
    pub pictures: Vec<Picture>,
}

pub fn load_index(folder: &Path) -> Result<Index, String> {
    let path = folder.join("index.json");
    let text = fs::read_to_string(&path)
        .map_err(|error| format!("cannot read {}: {error}", path.display()))?;
    serde_json::from_str(&text)
        .map_err(|error| format!("{} is not an index: {error}", path.display()))
}

pub fn parse_listing(text: &str) -> Result<Listing, String> {
    serde_json::from_str(text)
        .map_err(|error| format!("render.py --list printed no registry: {error}"))
}

/// A screen id or variant as one path segment: anything but letters, digits, `.`, `_` and `-`
/// becomes `-`, and a segment of only dots is refused, so a key never leaves its folder.
pub fn safe_segment(raw: &str) -> String {
    let cleaned: String = raw
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '.' | '_' | '-') {
                c
            } else {
                '-'
            }
        })
        .collect();
    if cleaned.is_empty() || cleaned.chars().all(|c| c == '.') {
        "-".to_string()
    } else {
        cleaned
    }
}

/// `<screen>/<variant>` as a relative path of two safe segments.
pub fn key_path(screen: &str, variant: &str) -> String {
    format!("{}/{}", safe_segment(screen), safe_segment(variant))
}
