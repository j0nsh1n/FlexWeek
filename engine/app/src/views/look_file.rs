//! Material look-file readers, writers, export/import documents, and legacy layout/surface
//! sanitizers (P5-T2). Pure over JSON values; disk I/O stays in Python until P6.

use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Map, Value, json};

use crate::views::theme::{CATEGORY_KEYS, CONTRASTS, DEFAULT_DENSITY, FONTS, PRESETS};

pub const SAVED_MODES: [&str; 3] = ["system", "light", "dark"];
pub const DENSITIES: [&str; 2] = ["comfortable", "compact"];
pub const DEFAULT_PRESET: &str = "Slate";
pub const DEFAULT_MODE: &str = "system";
pub const DEFAULT_CONTRAST: &str = "std";

pub const CORNER_RANGE: (i64, i64) = (0, 28);
pub const SCALE_RANGE: (f64, f64) = (0.85, 1.8);
pub const HOUR_RANGE: (i64, i64) = (36, 90);
pub const PAD_RANGE: (i64, i64) = (4, 24);
pub const SHADOW_RANGE: (i64, i64) = (0, 3);
pub const MOTION_SPEEDS: [&str; 4] = ["Slower", "Normal", "Faster", "Off"];
pub const BLOCK_STYLES: [&str; 3] = ["Edge", "Filled", "Outline"];
pub const HOUR_LINES: [&str; 3] = ["None", "Faint", "Clear"];

pub const LOOK_KIND: &str = "FlexWeek material look";
pub const LOOK_VERSION: i64 = 1;
pub const INVALID_LOOK_DOCUMENT: &str = "That file isn't a FlexWeek material look.";

pub const LOOK_TIERS: [&str; 3] = ["simple", "more", "all"];
pub const DAY_SIDE_RANGE: (i64, i64) = (240, 480);
pub const DAY_SIDE_DEFAULT: i64 = 312;
pub const SETTINGS_NAV_RANGE: (i64, i64) = (72, 340);
pub const SETTINGS_NAV_DEFAULT: i64 = 220;

pub const MAIN_DEFAULT: &str = "classic";
pub const DAY_DEFAULT: &str = "dial";
pub const SURFACES: [&str; 1] = ["material"];
pub const SURFACE_DEFAULT: &str = "material";

pub const CLASSIC_DESIGN_LOOKS: [(&str, &str); 5] = [
    ("pack:light-frost", "Light"),
    ("preset:high-contrast", "High contrast"),
    ("pack:dark-frost", "Dark"),
    ("preset:paper", "Paper"),
    ("preset:poster", "Poster"),
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayoutChoiceItem {
    pub value: &'static str,
    pub label: &'static str,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayoutOption {
    pub key: &'static str,
    pub label: &'static str,
    pub level: &'static str,
    pub choices: Vec<LayoutChoiceItem>,
    /// The value as the design ships, when that is not the first choice.
    pub shipped: &'static str,
}

impl LayoutOption {
    pub fn default_value(&self) -> &'static str {
        option_default(self.shipped, self.choices.first().map_or("", |c| c.value))
    }

    pub fn values(&self) -> Vec<&'static str> {
        self.choices.iter().map(|c| c.value).collect()
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LayoutSpec {
    pub id: &'static str,
    pub role: &'static str,
    pub label: &'static str,
    pub summary: &'static str,
    pub options: Vec<LayoutOption>,
    pub purpose: &'static str,
}

fn material_map(stored: &Value) -> Option<&Map<String, Value>> {
    stored.as_object()?.get("material")?.as_object()
}

fn read_material_choice_from_map(raw: Option<&Map<String, Value>>) -> Map<String, Value> {
    let pick = |key: &str, allowed: &[&str], fallback: &str| -> String {
        raw.and_then(|map| map.get(key))
            .and_then(Value::as_str)
            .filter(|value| allowed.contains(value))
            .unwrap_or(fallback)
            .to_string()
    };
    let mut out = Map::new();
    out.insert(
        "preset".to_string(),
        Value::String(pick("preset", &PRESETS, DEFAULT_PRESET)),
    );
    out.insert(
        "mode".to_string(),
        Value::String(pick("mode", &SAVED_MODES, DEFAULT_MODE)),
    );
    out.insert(
        "contrast".to_string(),
        Value::String(pick("contrast", &CONTRASTS, DEFAULT_CONTRAST)),
    );
    out.insert(
        "density".to_string(),
        Value::String(pick("density", &DENSITIES, DEFAULT_DENSITY)),
    );
    out
}

/// Preset, mode, contrast, and density from a look file's top-level `material` object.
/// Missing or unknown values fall back to Slate, follow system, standard contrast, comfortable.
pub fn read_material_choice(stored: &Value) -> Map<String, Value> {
    read_material_choice_from_map(material_map(stored))
}

/// The student's own font from the look file's `material` object; `""` means the preset's own.
pub fn read_font(stored: &Value) -> &'static str {
    let Some(font) = material_map(stored)
        .and_then(|map| map.get("font"))
        .and_then(Value::as_str)
    else {
        return "";
    };
    FONTS
        .iter()
        .copied()
        .find(|known| *known == font)
        .unwrap_or("")
}

/// The advanced draft before anyone moves a dial.
pub fn advanced_default() -> Map<String, Value> {
    let mut cat = Map::new();
    for key in CATEGORY_KEYS {
        cat.insert(key.to_string(), Value::Null);
    }
    let mut out = Map::new();
    out.insert("corner".to_string(), Value::Null);
    out.insert("hour".to_string(), Value::Null);
    out.insert("padding".to_string(), Value::Null);
    out.insert("rail".to_string(), Value::Bool(true));
    out.insert("scale".to_string(), json!(1.0));
    out.insert("motion".to_string(), Value::String("Normal".to_string()));
    out.insert("shadow".to_string(), Value::Null);
    out.insert("block".to_string(), Value::String("Edge".to_string()));
    out.insert("lines".to_string(), Value::String("Faint".to_string()));
    out.insert("today".to_string(), Value::Bool(true));
    out.insert("times".to_string(), Value::Bool(true));
    out.insert("lengths".to_string(), Value::Bool(false));
    out.insert("now".to_string(), Value::Null);
    out.insert("cat".to_string(), Value::Object(cat));
    out
}

/// A `#rrggbb` colour string, lowercased, or `None` when not a 6-digit hex colour.
pub fn hex_color(value: &Value) -> Option<String> {
    let text = value.as_str()?;
    let bytes = text.as_bytes();
    if bytes.len() != 7 || bytes[0] != b'#' || !bytes[1..].iter().all(u8::is_ascii_hexdigit) {
        return None;
    }
    Some(text.to_ascii_lowercase())
}

/// An integer (never a bool or float) within `[low, high]` inclusive.
pub fn int_in(value: &Value, low: i64, high: i64) -> Option<i64> {
    let number = value.as_i64()?;
    (low <= number && number <= high).then_some(number)
}

fn round_two_decimals(value: f64) -> f64 {
    if value.abs() >= 1e15 {
        return value;
    }
    format!("{value:.2}").parse::<f64>().unwrap_or(value)
}

/// An int or float (never a bool), rounded to two decimals, within `[low, high]` inclusive.
pub fn float_in(value: &Value, low: f64, high: f64) -> Option<f64> {
    let raw = value.as_f64()?;
    if !raw.is_finite() {
        return None;
    }
    let number = round_two_decimals(raw);
    (low - 1e-9 <= number && number <= high + 1e-9).then_some(number)
}

fn read_advanced_from_map(raw: Option<&Map<String, Value>>) -> Map<String, Value> {
    let mut found = advanced_default();
    let Some(raw) = raw else {
        return found;
    };
    if let Some(corner) = raw
        .get("corner")
        .and_then(|v| int_in(v, CORNER_RANGE.0, CORNER_RANGE.1))
    {
        found.insert("corner".to_string(), json!(corner));
    }
    if let Some(hour) = raw
        .get("hour")
        .and_then(|v| int_in(v, HOUR_RANGE.0, HOUR_RANGE.1))
    {
        found.insert("hour".to_string(), json!(hour));
    }
    if let Some(padding) = raw
        .get("padding")
        .and_then(|v| int_in(v, PAD_RANGE.0, PAD_RANGE.1))
    {
        found.insert("padding".to_string(), json!(padding));
    }
    if let Some(rail) = raw.get("rail").and_then(Value::as_bool) {
        found.insert("rail".to_string(), Value::Bool(rail));
    }
    if let Some(scale) = raw
        .get("scale")
        .and_then(|v| float_in(v, SCALE_RANGE.0, SCALE_RANGE.1))
    {
        found.insert("scale".to_string(), json!(scale));
    }
    if let Some(motion) = raw
        .get("motion")
        .and_then(Value::as_str)
        .filter(|value| MOTION_SPEEDS.contains(value))
    {
        found.insert("motion".to_string(), Value::String(motion.to_string()));
    }
    if let Some(shadow) = raw
        .get("shadow")
        .and_then(|v| int_in(v, SHADOW_RANGE.0, SHADOW_RANGE.1))
    {
        found.insert("shadow".to_string(), json!(shadow));
    }
    if let Some(block) = raw
        .get("block")
        .and_then(Value::as_str)
        .filter(|value| BLOCK_STYLES.contains(value))
    {
        found.insert("block".to_string(), Value::String(block.to_string()));
    }
    if let Some(lines) = raw
        .get("lines")
        .and_then(Value::as_str)
        .filter(|value| HOUR_LINES.contains(value))
    {
        found.insert("lines".to_string(), Value::String(lines.to_string()));
    }
    if let Some(today) = raw.get("today").and_then(Value::as_bool) {
        found.insert("today".to_string(), Value::Bool(today));
    }
    if let Some(times) = raw.get("times").and_then(Value::as_bool) {
        found.insert("times".to_string(), Value::Bool(times));
    }
    if let Some(lengths) = raw.get("lengths").and_then(Value::as_bool) {
        found.insert("lengths".to_string(), Value::Bool(lengths));
    }
    if let Some(now) = raw.get("now").and_then(hex_color) {
        found.insert("now".to_string(), Value::String(now));
    }
    if let Some(cats) = raw.get("cat").and_then(Value::as_object)
        && let Some(Value::Object(found_cat)) = found.get_mut("cat")
    {
        for key in CATEGORY_KEYS {
            if let Some(colour) = cats.get(key).and_then(hex_color) {
                found_cat.insert(key.to_string(), Value::String(colour));
            }
        }
    }
    found
}

/// Advanced dials from the look file. A missing or unknown value stays at the default.
pub fn read_advanced(stored: &Value) -> Map<String, Value> {
    let raw = material_map(stored)
        .and_then(|map| map.get("advanced"))
        .and_then(Value::as_object);
    read_advanced_from_map(raw)
}

/// The number keys (1 to 5) stay on unless the look file turns them off.
pub fn read_shortcuts(stored: &Value) -> bool {
    material_map(stored)
        .and_then(|map| map.get("shortcuts"))
        .and_then(Value::as_bool)
        .unwrap_or(true)
}

/// The P, Z and F keys are off unless the look file explicitly sets `letters` to `true`.
pub fn read_letter_keys(stored: &Value) -> bool {
    material_map(stored)
        .and_then(|map| map.get("letters"))
        .and_then(Value::as_bool)
        .unwrap_or(false)
}

/// Named material looks kept beside the preset. A broken entry is left out.
pub fn read_saved_material(stored: &Value) -> Vec<Value> {
    let Some(raw) = material_map(stored)
        .and_then(|map| map.get("saved"))
        .and_then(Value::as_array)
    else {
        return Vec::new();
    };
    let mut kept = Vec::new();
    for item in raw {
        let Some(map) = item.as_object() else {
            continue;
        };
        let Some(name) = map
            .get("name")
            .and_then(Value::as_str)
            .map(str::trim)
            .filter(|text| !text.is_empty())
        else {
            continue;
        };
        let choice = read_material_choice_from_map(Some(map));
        let advanced = read_advanced_from_map(map.get("advanced").and_then(Value::as_object));
        let mut entry = Map::new();
        entry.insert("name".to_string(), Value::String(name.to_string()));
        for key in ["preset", "mode", "contrast", "density"] {
            if let Some(value) = choice.get(key) {
                entry.insert(key.to_string(), value.clone());
            }
        }
        entry.insert("advanced".to_string(), Value::Object(advanced));
        kept.push(Value::Object(entry));
    }
    kept
}

fn is_truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

fn equals_default(key: &str, value: &Value, default_value: &Value) -> bool {
    // Python treats `1 == 1.0`, so an integer `1` matches the default float scale `1.0`.
    if key == "scale" && value.as_f64() == Some(1.0) {
        return true;
    }
    value == default_value
}

/// Only the dials that differ from the default, so a preset can stay in charge of the rest.
pub fn advanced_overrides(advanced: &Value) -> EngineResult<Map<String, Value>> {
    let adv_map = advanced
        .as_object()
        .ok_or_else(|| EngineError::value("advanced must be an object"))?;
    let default = advanced_default();
    let mut changed = Map::new();
    for (key, value) in adv_map {
        if key == "cat" {
            let cats = match value {
                Value::Null => continue,
                Value::Object(map) => map,
                _ => return Err(EngineError::value("advanced.cat must be an object or null")),
            };
            let mut colours = Map::new();
            for (name, colour) in cats {
                if CATEGORY_KEYS.contains(&name.as_str()) && is_truthy(colour) {
                    colours.insert(name.clone(), colour.clone());
                }
            }
            if !colours.is_empty() {
                changed.insert("cat".to_string(), Value::Object(colours));
            }
        } else {
            let default_value = default.get(key).unwrap_or(&Value::Null);
            if !equals_default(key, value, default_value) {
                changed.insert(key.clone(), value.clone());
            }
        }
    }
    Ok(changed)
}

/// How many Look controls the Advanced page shows on this computer: `simple`, `more`, `all`, or `""`.
pub fn read_look_tier(stored: &Value) -> &'static str {
    let Some(tier) = material_map(stored)
        .and_then(|map| map.get("lookTier"))
        .and_then(Value::as_str)
    else {
        return "";
    };
    LOOK_TIERS
        .iter()
        .copied()
        .find(|known| *known == tier)
        .unwrap_or("")
}

/// Remembered width of the Day right sidebar on this computer.
pub fn read_day_side_width(stored: &Value) -> i64 {
    material_map(stored)
        .and_then(|map| map.get("daySideWidth"))
        .and_then(|v| int_in(v, DAY_SIDE_RANGE.0, DAY_SIDE_RANGE.1))
        .unwrap_or(DAY_SIDE_DEFAULT)
}

/// Remembered width of the Settings section list on this computer.
pub fn read_settings_nav_width(stored: &Value) -> i64 {
    material_map(stored)
        .and_then(|map| map.get("settingsNavWidth"))
        .and_then(|v| int_in(v, SETTINGS_NAV_RANGE.0, SETTINGS_NAV_RANGE.1))
        .unwrap_or(SETTINGS_NAV_DEFAULT)
}

fn require_choice_field<'a>(map: &'a Map<String, Value>, key: &str) -> EngineResult<&'a Value> {
    map.get(key).ok_or_else(|| EngineError::key(key))
}

/// The `material` object written into the look file.
#[allow(clippy::too_many_arguments)]
pub fn pack_material(
    choice: &Value,
    advanced: &Value,
    shortcuts: bool,
    letters: bool,
    saved: &Value,
    font: &str,
    tier: &str,
    day_side_width: &Value,
    settings_nav_width: &Value,
) -> EngineResult<Map<String, Value>> {
    let choice_map = choice
        .as_object()
        .ok_or_else(|| EngineError::value("choice must be an object"))?;
    let saved_list = saved
        .as_array()
        .ok_or_else(|| EngineError::value("saved must be a list"))?;
    let mut body = Map::new();
    for key in ["preset", "mode", "contrast", "density"] {
        let value = require_choice_field(choice_map, key)?;
        body.insert(key.to_string(), value.clone());
    }
    body.insert("shortcuts".to_string(), Value::Bool(shortcuts));
    body.insert("letters".to_string(), Value::Bool(letters));
    body.insert("advanced".to_string(), advanced.clone());
    if !saved_list.is_empty() {
        body.insert("saved".to_string(), Value::Array(saved_list.clone()));
    }
    if FONTS.contains(&font) {
        body.insert("font".to_string(), Value::String(font.to_string()));
    }
    if LOOK_TIERS.contains(&tier) {
        body.insert("lookTier".to_string(), Value::String(tier.to_string()));
    }
    if let Some(width) = int_in(day_side_width, DAY_SIDE_RANGE.0, DAY_SIDE_RANGE.1) {
        body.insert("daySideWidth".to_string(), json!(width));
    }
    if let Some(width) = int_in(
        settings_nav_width,
        SETTINGS_NAV_RANGE.0,
        SETTINGS_NAV_RANGE.1,
    ) {
        body.insert("settingsNavWidth".to_string(), json!(width));
    }
    Ok(body)
}

/// Put `material` on the look file JSON and leave every other key untouched and in place.
/// Returns the serialized JSON with a trailing newline.
pub fn merge_material_into_look_file(
    existing_text: Option<&str>,
    material: &Value,
) -> EngineResult<String> {
    if !material.is_object() {
        return Err(EngineError::value("material must be an object"));
    }
    let mut stored = existing_text
        .and_then(|text| serde_json::from_str::<Value>(text).ok())
        .and_then(|value| match value {
            Value::Object(map) => Some(map),
            _ => None,
        })
        .unwrap_or_default();
    stored.insert("material".to_string(), material.clone());
    let mut text = serde_json::to_string(&Value::Object(stored))
        .map_err(|err| EngineError::value(err.to_string()))?;
    text.push('\n');
    Ok(text)
}

/// The `material` object already in the look file text, or `None` when absent or invalid.
pub fn extract_kept_material(existing_text: &str) -> Option<Map<String, Value>> {
    let parsed: Value = serde_json::from_str(existing_text).ok()?;
    parsed.as_object()?.get("material")?.as_object().cloned()
}

/// The advanced page's export: the basic look and the draft, formatted for a later import.
pub fn export_document(choice: &Value, advanced: &Value) -> EngineResult<String> {
    let choice_map = choice
        .as_object()
        .ok_or_else(|| EngineError::value("choice must be an object"))?;
    let mut doc = Map::new();
    doc.insert("kind".to_string(), Value::String(LOOK_KIND.to_string()));
    doc.insert("version".to_string(), json!(LOOK_VERSION));
    for key in ["preset", "mode", "contrast", "density"] {
        let value = require_choice_field(choice_map, key)?;
        doc.insert(key.to_string(), value.clone());
    }
    doc.insert("advanced".to_string(), advanced.clone());
    serde_json::to_string_pretty(&Value::Object(doc))
        .map_err(|err| EngineError::value(err.to_string()))
}

/// A document from `export_document`, or a sentence saying why it was refused.
pub fn import_document(text: &str) -> (Option<Map<String, Value>>, &'static str) {
    let Ok(Value::Object(raw)) = serde_json::from_str::<Value>(text) else {
        return (None, INVALID_LOOK_DOCUMENT);
    };
    let kind_ok = raw.get("kind").and_then(Value::as_str) == Some(LOOK_KIND);
    let version_ok = raw.get("version").and_then(Value::as_i64) == Some(LOOK_VERSION);
    if !kind_ok || !version_ok {
        return (None, INVALID_LOOK_DOCUMENT);
    }
    let choice = read_material_choice_from_map(Some(&raw));
    let advanced = read_advanced_from_map(raw.get("advanced").and_then(Value::as_object));
    let mut out = Map::new();
    out.insert("choice".to_string(), Value::Object(choice));
    out.insert("advanced".to_string(), Value::Object(advanced));
    (Some(out), "")
}

/// The default value of a layout option: its shipped value when set, else its first choice.
pub fn option_default<'a>(shipped: &'a str, first_choice: &'a str) -> &'a str {
    if shipped.is_empty() {
        first_choice
    } else {
        shipped
    }
}

fn design_looks_for(layout_id: &str) -> &'static [(&'static str, &'static str)] {
    match layout_id {
        "classic" => &CLASSIC_DESIGN_LOOKS,
        _ => &[],
    }
}

fn look_option(layout_id: &str) -> LayoutOption {
    let mut choices: Vec<LayoutChoiceItem> = design_looks_for(layout_id)
        .iter()
        .map(|(value, label)| LayoutChoiceItem { value, label })
        .collect();
    choices.push(LayoutChoiceItem {
        value: "your",
        label: "Your look",
    });
    LayoutOption {
        key: "look",
        label: "Look",
        level: "style",
        choices,
        shipped: "your",
    }
}

/// Curated looks per layout id as JSON (`{layout_id: [[value, label], ...]}`).
pub fn design_looks_json() -> Map<String, Value> {
    let pairs: Vec<Value> = CLASSIC_DESIGN_LOOKS
        .iter()
        .map(|(value, label)| json!([value, label]))
        .collect();
    let mut map = Map::new();
    map.insert("classic".to_string(), Value::Array(pairs));
    map
}

/// The legacy layout registry: Today's app is the only design left.
pub fn layouts() -> Vec<LayoutSpec> {
    vec![LayoutSpec {
        id: "classic",
        role: "plan",
        label: "Today's app",
        summary: "The week grid with the sidebar. Its colours come from the look you choose above.",
        options: vec![look_option("classic")],
        purpose: "Calendar",
    }]
}

/// The layout registry serialized for Python's `LAYOUTS` dict.
pub fn layouts_json() -> Vec<Value> {
    layouts()
        .into_iter()
        .map(|spec| {
            let options: Vec<Value> = spec
                .options
                .into_iter()
                .map(|opt| {
                    let choices: Vec<Value> = opt
                        .choices
                        .into_iter()
                        .map(|choice| json!({ "value": choice.value, "label": choice.label }))
                        .collect();
                    json!({
                        "key": opt.key,
                        "label": opt.label,
                        "level": opt.level,
                        "choices": choices,
                        "shipped": opt.shipped,
                    })
                })
                .collect();
            json!({
                "id": spec.id,
                "role": spec.role,
                "label": spec.label,
                "summary": spec.summary,
                "options": options,
                "purpose": spec.purpose,
            })
        })
        .collect()
}

/// Whatever the file on disk says, hand back a layout choice this build can show.
pub fn sanitize_layout(raw: &Value) -> Map<String, Value> {
    let mut clean = Map::new();
    clean.insert("main".to_string(), Value::String(MAIN_DEFAULT.to_string()));
    clean.insert("day".to_string(), Value::String(DAY_DEFAULT.to_string()));
    let mut clean_options = Map::new();

    let Some(raw_map) = raw.as_object() else {
        clean.insert("options".to_string(), Value::Object(clean_options));
        return clean;
    };

    let specs = layouts();
    for (slot, role) in [("main", "plan"), ("day", "day")] {
        if let Some(chosen) = raw_map.get(slot).and_then(Value::as_str)
            && let Some(spec) = specs.iter().find(|s| s.id == chosen && s.role == role)
        {
            clean.insert(slot.to_string(), Value::String(spec.id.to_string()));
        }
    }

    if let Some(stored) = raw_map.get("options").and_then(Value::as_object) {
        for (layout_id, values) in stored {
            let Some(spec) = specs.iter().find(|s| s.id == layout_id) else {
                continue;
            };
            let Some(val_map) = values.as_object() else {
                continue;
            };
            let migrated_look = if !val_map.contains_key("look")
                && val_map.get("colour").is_some_and(Value::is_string)
            {
                Some("your")
            } else {
                None
            };
            let mut kept = Map::new();
            for option in &spec.options {
                let valid = option.values();
                let candidate = if option.key == "look" {
                    val_map
                        .get("look")
                        .and_then(Value::as_str)
                        .or(migrated_look)
                } else {
                    val_map.get(option.key).and_then(Value::as_str)
                };
                if let Some(chosen) = candidate
                    && valid.contains(&chosen)
                {
                    kept.insert(option.key.to_string(), Value::String(chosen.to_string()));
                }
            }
            if !kept.is_empty() {
                clean_options.insert(layout_id.clone(), Value::Object(kept));
            }
        }
    }

    clean.insert("options".to_string(), Value::Object(clean_options));
    clean
}

/// Material 3 is the only style a student can reach, so every look file opens Material.
pub fn sanitize_surface(_raw: &Value) -> &'static str {
    SURFACE_DEFAULT
}
