//! Material 3 colour schemes, category paints, theme dressing, readability checks, motion levels,
//! and look-motion rules (P5-T1). Pure over JSON values; `tokens.json` is embedded once at build
//! time and parsed on first use.

use std::sync::OnceLock;

use flexweek_engine::desk::{custom_look, tokens};
use flexweek_engine::material::material_scheme;
use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Map, Value, json};

const TOKENS_JSON: &str = include_str!("../../../../desktop/native/material/tokens.json");

pub const PRESETS: [&str; 11] = [
    "Slate",
    "Blue",
    "Sea",
    "Forest",
    "Gold",
    "Rose",
    "Plum",
    "High contrast",
    "Paper",
    "Ink",
    "Terminal",
];

pub const ONE_MODE: [(&str, &str); 4] = [
    ("High contrast", "dark"),
    ("Paper", "light"),
    ("Ink", "dark"),
    ("Terminal", "dark"),
];

pub const FONTS: [&str; 3] = ["sans", "serif", "mono"];

pub const ACCENTS: [&str; 5] = ["default", "sky", "gold", "sea", "sand"];

pub const ACCENT_SEEDS: [(&str, &str); 4] = [
    ("sky", "#0369a1"),
    ("gold", "#a16207"),
    ("sea", "#0f766e"),
    ("sand", "#805441"),
];

pub const ACCENT_LOCKED: [&str; 1] = ["High contrast"];
pub const MODES: [&str; 2] = ["light", "dark"];
pub const CONTRASTS: [&str; 2] = ["std", "high"];
pub const HIGH_CONTRAST_STROKE: f64 = 1.5;

pub const DEFAULT_DENSITY: &str = "comfortable";

pub const CLASS_COLORS: [(&str, &str); 8] = [
    ("class", "#3d6fc4"),
    ("exercise", "#2b9665"),
    ("extra", "#0f8a8a"),
    ("assignments", "#a87512"),
    ("study", "#c2557a"),
    ("meals", "#64748b"),
    ("sleep", "#64748b"),
    ("free", "#64748b"),
];
pub const OTHER_CLASS_COLOR: &str = "#64748b";
pub const SIX_CLASSES: [&str; 6] = [
    "class",
    "exercise",
    "extra",
    "assignments",
    "study",
    "other",
];
pub const INK_DARK: &str = "#0f172a";
pub const INK_LIGHT: &str = "#ececec";

pub const THEME_ROLES: [&str; 30] = [
    "primary",
    "onPrimary",
    "primaryContainer",
    "onPrimaryContainer",
    "secondary",
    "onSecondary",
    "secondaryContainer",
    "onSecondaryContainer",
    "tertiary",
    "onTertiary",
    "tertiaryContainer",
    "onTertiaryContainer",
    "error",
    "onError",
    "errorContainer",
    "onErrorContainer",
    "surface",
    "onSurface",
    "onSurfaceVariant",
    "surfaceContainerLowest",
    "surfaceContainerLow",
    "surfaceContainer",
    "surfaceContainerHigh",
    "surfaceContainerHighest",
    "surfaceVariant",
    "outline",
    "outlineVariant",
    "inverseSurface",
    "inverseOnSurface",
    "inversePrimary",
];

// QML treats a name starting with "on" as a signal handler. The same object carries both.
pub const INK_ALIASES: [(&str, &str); 10] = [
    ("onPrimary", "inkPrimary"),
    ("onPrimaryContainer", "inkPrimaryContainer"),
    ("onSecondary", "inkSecondary"),
    ("onSecondaryContainer", "inkSecondaryContainer"),
    ("onTertiary", "inkTertiary"),
    ("onTertiaryContainer", "inkTertiaryContainer"),
    ("onError", "inkError"),
    ("onErrorContainer", "inkErrorContainer"),
    ("onSurface", "inkSurface"),
    ("onSurfaceVariant", "inkMuted"),
];

pub const CATEGORY_KEYS: [&str; 4] = ["school", "sports", "study", "homework"];

/// Notices, dialogs, blocks settling after a plan: long enough to see where things went, short
/// enough never to feel like waiting.
pub const MOTION_EASE_MS: i64 = 220;

/// Stored Animations levels as `(id, pace, reach)`. Reduce keeps fades and nothing travels.
pub const MOTION_LEVELS: [(&str, f64, f64); 4] = [
    ("normal", 1.0, 1.0),
    ("extra", 2.5, 4.0 / 3.0),
    ("reduce", 1.0, 0.0),
    ("off", 0.0, 0.0),
];

const B3A3_NEUTRALS: [(&str, &str, &str); 10] = [
    ("surface", "#eef1f5", "#0b0d10"),
    ("surfaceContainerLowest", "#ffffff", "#0e1116"),
    ("surfaceContainerLow", "#f6f8fc", "#14171c"),
    ("surfaceContainer", "#edf0f7", "#1b202a"),
    ("surfaceContainerHigh", "#e3e8f2", "#232936"),
    ("surfaceContainerHighest", "#d8dfec", "#2c3444"),
    ("surfaceVariant", "#e3e8f2", "#232936"),
    ("outlineVariant", "#d4dce8", "#252a33"),
    ("outline", "#64748b", "#6b7280"),
    ("onSurface", "#0f172a", "#ececec"),
];

const B3A3_ON_SURFACE_VARIANT: (&str, &str) = ("#475569", "#9a9fa8");
const B3A3_ON_SURFACE_VARIANT_HIGH: (&str, &str) = ("#334155", "#c4c8d0");

const B3A3_SLATE: [(&str, &str, &str); 4] = [
    ("primary", "#3d6fc4", "#7fa8ff"),
    ("onPrimary", "#ffffff", "#0b1220"),
    ("secondaryContainer", "#e6edf8", "#1c2433"),
    ("onSecondaryContainer", "#0f172a", "#ececec"),
];

const STATUS_LIGHT: [(&str, &str); 3] = [
    ("statusDone", "#276b3f"),
    ("statusDueSoon", "#8a5a00"),
    ("statusOverdue", "#b42318"),
];

const STATUS_DARK: [(&str, &str); 3] = [
    ("statusDone", "#8fd19e"),
    ("statusDueSoon", "#f0c674"),
    ("statusOverdue", "#ff9b8f"),
];

fn parsed_tokens() -> &'static Map<String, Value> {
    static TOKENS: OnceLock<Map<String, Value>> = OnceLock::new();
    TOKENS.get_or_init(|| {
        let parsed: Value =
            serde_json::from_str(TOKENS_JSON).expect("embedded tokens.json must be valid JSON");
        match parsed {
            Value::Object(map) => map,
            _ => panic!("embedded tokens.json must be a JSON object of schemes"),
        }
    })
}

fn one_mode_for(preset: &str) -> Option<&'static str> {
    ONE_MODE
        .iter()
        .find(|(name, _)| *name == preset)
        .map(|(_, mode)| *mode)
}

fn preset_font(preset: &str) -> Option<&'static str> {
    match preset {
        "High contrast" => Some("sans"),
        "Paper" | "Ink" => Some("serif"),
        "Terminal" => Some("mono"),
        _ => None,
    }
}

fn preset_corner(preset: &str) -> Option<i64> {
    match preset {
        "High contrast" | "Terminal" => Some(0),
        _ => None,
    }
}

fn font_families(font: &str) -> EngineResult<(&'static str, &'static str)> {
    match font {
        "sans" => Ok(("Inter", "Inter")),
        "serif" => Ok(("Inter", "Newsreader")),
        "mono" => Ok(("JetBrains Mono", "JetBrains Mono")),
        _ => Err(EngineError::key(font)),
    }
}

fn pick_mode<'a>(mode: &str, light: &'a str, dark: &'a str) -> &'a str {
    if mode == "dark" { dark } else { light }
}

pub fn scheme_key(preset: &str, mode: &str, contrast_name: &str) -> String {
    format!("{preset}.{mode}.{contrast_name}")
}

/// One scheme from embedded `tokens.json` with B3A3 neutral and Slate overrides applied.
/// An unknown preset, mode or contrast returns `ErrorKind::Key`, not a quiet fallback.
pub fn scheme(preset: &str, mode: &str, contrast_name: &str) -> EngineResult<Map<String, Value>> {
    if !PRESETS.contains(&preset) || !MODES.contains(&mode) || !CONTRASTS.contains(&contrast_name) {
        return Err(EngineError::key(scheme_key(preset, mode, contrast_name)));
    }
    let effective_mode = one_mode_for(preset).unwrap_or(mode);
    let key = scheme_key(preset, effective_mode, contrast_name);
    let raw = parsed_tokens()
        .get(&key)
        .and_then(Value::as_object)
        .ok_or_else(|| EngineError::key(&key))?;
    let mut found = raw.clone();
    if one_mode_for(preset).is_some() {
        return Ok(found);
    }
    for (role, light, dark) in B3A3_NEUTRALS {
        found.insert(
            role.to_string(),
            Value::String(pick_mode(effective_mode, light, dark).to_string()),
        );
    }
    let (muted_light, muted_dark) = if contrast_name == "high" {
        B3A3_ON_SURFACE_VARIANT_HIGH
    } else {
        B3A3_ON_SURFACE_VARIANT
    };
    found.insert(
        "onSurfaceVariant".to_string(),
        Value::String(pick_mode(effective_mode, muted_light, muted_dark).to_string()),
    );
    if preset == "Slate" {
        for (role, light, dark) in B3A3_SLATE {
            found.insert(
                role.to_string(),
                Value::String(pick_mode(effective_mode, light, dark).to_string()),
            );
        }
    }
    Ok(found)
}

/// High contrast draws a solid 1.5px outline. Standard contrast does not add one.
pub fn stroke_for(contrast_name: &str) -> EngineResult<f64> {
    match contrast_name {
        "high" => Ok(HIGH_CONTRAST_STROKE),
        "std" => Ok(0.0),
        _ => Err(EngineError::key(contrast_name)),
    }
}

/// The solid accent bar colour for an event category.
pub fn bar_for_category(category: &str) -> &'static str {
    CLASS_COLORS
        .iter()
        .find(|(name, _)| *name == category)
        .map_or(OTHER_CLASS_COLOR, |(_, colour)| *colour)
}

/// A week block's category key (`class`, `assignments`, ...) as a Material `(fill, ink)` pair.
pub fn paint_for_category(category: &str, mode: &str) -> EngineResult<(String, &'static str)> {
    if !MODES.contains(&mode) {
        return Err(EngineError::key(mode));
    }
    let bar = bar_for_category(category);
    let (card, alpha, ink) = if mode == "light" {
        ("#ffffff", 0.14, INK_DARK)
    } else {
        ("#14171c", 0.24, INK_LIGHT)
    };
    let fill = tokens::mix(bar, card, alpha)?;
    Ok((fill, ink))
}

/// Fill and ink for a role or category name.
pub fn category_paint(role: &str, mode: &str) -> EngineResult<(String, &'static str)> {
    let category = match role {
        "school" | "class" => "class",
        "soccer" | "sports" | "exercise" => "exercise",
        "clubs" | "extra" => "extra",
        "homework" | "assignments" => "assignments",
        "reading" | "study" => "study",
        _ => "other",
    };
    paint_for_category(category, mode)
}

/// The EventBlock category for a week block: the category itself when in `SIX_CLASSES`, else `"other"`.
pub fn event_category(category: &str) -> &'static str {
    SIX_CLASSES
        .iter()
        .copied()
        .find(|known| *known == category)
        .unwrap_or("other")
}

/// `system` follows the worn look's light or dark axis. An explicit `light` or `dark` wins.
pub fn resolved_mode(mode: &str, worn_dark: bool) -> &'static str {
    match mode {
        "light" => "light",
        "dark" => "dark",
        _ if worn_dark => "dark",
        _ => "light",
    }
}

/// The light or dark a choice shows: its preset's own when it has only one, else Mode's.
pub fn mode_of(choice: &Value, worn_dark: bool) -> EngineResult<&'static str> {
    let map = choice
        .as_object()
        .ok_or_else(|| EngineError::value("choice must be an object"))?;
    let preset = map
        .get("preset")
        .ok_or_else(|| EngineError::key("preset"))?
        .as_str()
        .ok_or_else(|| EngineError::value("choice.preset must be a string"))?;
    if let Some(fixed) = one_mode_for(preset) {
        return Ok(fixed);
    }
    let mode = map
        .get("mode")
        .ok_or_else(|| EngineError::key("mode"))?
        .as_str()
        .ok_or_else(|| EngineError::value("choice.mode must be a string"))?;
    Ok(resolved_mode(mode, worn_dark))
}

/// The font worn: the student's choice, else the preset's own, else `"sans"`.
pub fn shown_font(preset: &str, font: &str) -> String {
    if !font.is_empty() {
        return font.to_string();
    }
    preset_font(preset).unwrap_or("sans").to_string()
}

/// The saved accent name; anything this build does not know is `"default"` (Same as preset).
pub fn read_accent(preferences: &Value) -> &'static str {
    let Some(map) = preferences.as_object() else {
        return "default";
    };
    let Some(value) = map.get("accent").and_then(Value::as_str) else {
        return "default";
    };
    ACCENTS
        .iter()
        .copied()
        .find(|known| *known == value)
        .unwrap_or("default")
}

fn role_str<'a>(map: &'a Map<String, Value>, role: &str) -> EngineResult<&'a str> {
    map.get(role)
        .ok_or_else(|| EngineError::key(role))?
        .as_str()
        .ok_or_else(|| EngineError::value(format!("colours.{role} must be a string")))
}

/// `colours` with the accent's primary roles over the preset's. Same as preset, High contrast, and
/// any unknown accent leave them unchanged.
pub fn accented(
    colours: &Value,
    accent: &str,
    preset: &str,
    mode: &str,
    contrast_name: &str,
) -> EngineResult<Map<String, Value>> {
    let map = colours
        .as_object()
        .ok_or_else(|| EngineError::value("colours must be an object"))?;
    let seed = ACCENT_SEEDS
        .iter()
        .find(|(name, _)| *name == accent)
        .map(|(_, hex)| *hex);
    let Some(seed) = seed else {
        return Ok(map.clone());
    };
    if ACCENT_LOCKED.contains(&preset) {
        return Ok(map.clone());
    }
    let level = if contrast_name == "high" { 1.0 } else { 0.0 };
    let tone = material_scheme(seed, "Tonal Spot", mode == "dark", level)?;
    let mut found = map.clone();
    let mut tone_primary = None;
    for (role, hex) in tone {
        if role == "primary" {
            tone_primary = Some(hex.clone());
        }
        if matches!(
            role,
            "primary" | "onPrimary" | "primaryContainer" | "onPrimaryContainer" | "inversePrimary"
        ) {
            found.insert(role.to_string(), Value::String(hex));
        }
    }
    let primary_hex = tone_primary.ok_or_else(|| EngineError::key("primary"))?;
    let surface_container = role_str(&found, "surfaceContainer")?.to_string();
    let on_surface = role_str(&found, "onSurface")?.to_string();
    let secondary_container = tokens::mix(&primary_hex, &surface_container, 0.16)?;
    found.insert(
        "secondaryContainer".to_string(),
        Value::String(secondary_container),
    );
    found.insert(
        "onSecondaryContainer".to_string(),
        Value::String(on_surface),
    );
    Ok(found)
}

/// One map for every control: the 30 Material roles, the 10 ink aliases, the three shell flags,
/// semantic surface/status tokens, and the six category paints.
pub fn theme_object(
    colours: &Value,
    density: &str,
    reduce_motion: bool,
    high_contrast: bool,
    chips_accent: bool,
) -> EngineResult<Map<String, Value>> {
    let map = colours
        .as_object()
        .ok_or_else(|| EngineError::value("colours must be an object"))?;
    let mut theme = Map::new();
    for role in THEME_ROLES {
        let value = map.get(role).ok_or_else(|| EngineError::key(role))?;
        theme.insert(role.to_string(), value.clone());
    }
    for (source, alias) in INK_ALIASES {
        let value = map.get(source).ok_or_else(|| EngineError::key(source))?;
        theme.insert(alias.to_string(), value.clone());
    }
    theme.insert("density".to_string(), Value::String(density.to_string()));
    theme.insert("reduceMotion".to_string(), Value::Bool(reduce_motion));
    theme.insert("highContrast".to_string(), Value::Bool(high_contrast));

    let surface = role_str(map, "surface")?;
    let mode = if tokens::luminance(surface)? < 0.18 {
        "dark"
    } else {
        "light"
    };
    let card = if mode == "light" {
        role_str(map, "surfaceContainerLowest")?
    } else {
        role_str(map, "surfaceContainerLow")?
    };
    let page = surface;
    let edge = role_str(map, "outlineVariant")?;
    let primary = role_str(map, "primary")?;

    theme.insert("page".to_string(), Value::String(page.to_string()));
    theme.insert("card".to_string(), Value::String(card.to_string()));
    theme.insert("edge".to_string(), Value::String(edge.to_string()));
    theme.insert("focusRing".to_string(), Value::String(primary.to_string()));

    let statuses = if mode == "dark" {
        STATUS_DARK
    } else {
        STATUS_LIGHT
    };
    for (key, val) in statuses {
        theme.insert(key.to_string(), Value::String(val.to_string()));
        let tint = tokens::mix(val, card, 0.16)?;
        theme.insert(format!("{key}Tint"), Value::String(tint));
    }

    let mut classes = Map::new();
    if chips_accent {
        let alpha = if mode == "light" { 0.14 } else { 0.24 };
        let accent_fill = tokens::mix(primary, card, alpha)?;
        for cat in SIX_CLASSES {
            let (_, ink) = paint_for_category(cat, mode)?;
            classes.insert(
                cat.to_string(),
                json!({
                    "bar": primary,
                    "fill": accent_fill,
                    "ink": ink,
                }),
            );
        }
    } else {
        for cat in SIX_CLASSES {
            let bar = bar_for_category(cat);
            let (fill, ink) = paint_for_category(cat, mode)?;
            classes.insert(
                cat.to_string(),
                json!({
                    "bar": bar,
                    "fill": fill,
                    "ink": ink,
                }),
            );
        }
    }
    theme.insert("classes".to_string(), Value::Object(classes));
    Ok(theme)
}

/// The week hour row height in pixels. An advanced integer `hour` replaces the density's row;
/// otherwise the density's base row is scaled by positive `scale` (rounded half-to-even).
pub fn hour_row_px(density: &str, advanced: &Value) -> EngineResult<i64> {
    let map = advanced
        .as_object()
        .ok_or_else(|| EngineError::value("advanced must be an object"))?;
    if let Some(hour) = map.get("hour").and_then(Value::as_i64) {
        return Ok(hour);
    }
    let base: i64 = match density {
        "compact" => 44,
        _ => 56,
    };
    if let Some(scale) = map.get("scale").and_then(Value::as_f64)
        && scale.is_finite()
        && scale > 0.0
    {
        return Ok((base as f64 * scale).round_ties_even() as i64);
    }
    Ok(base)
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

fn is_default_advanced_value(key: &str, value: &Value) -> bool {
    match key {
        "corner" | "hour" | "padding" | "shadow" | "now" => value.is_null(),
        "rail" | "today" | "times" => value == &Value::Bool(true),
        "lengths" => value == &Value::Bool(false),
        // Python treats `1 == 1.0`, so an integer `1` is also the default scale.
        "scale" => value.as_f64() == Some(1.0),
        "motion" => value.as_str() == Some("Normal"),
        "block" => value.as_str() == Some("Edge"),
        "lines" => value.as_str() == Some("Faint"),
        _ => false,
    }
}

/// The theme object plus only the advanced dials that differ from the components' defaults,
/// and the resolved font families. A preset's own font and corner act as defaults until overridden.
pub fn dress_theme(
    theme: &Value,
    advanced: &Value,
    preset: &str,
    font: &str,
) -> EngineResult<Map<String, Value>> {
    let theme_map = theme
        .as_object()
        .ok_or_else(|| EngineError::value("theme must be an object"))?;
    let adv_map = advanced
        .as_object()
        .ok_or_else(|| EngineError::value("advanced must be an object"))?;

    let mut dressed = theme_map.clone();
    let shown = shown_font(preset, font);
    let (body, heading) = font_families(&shown)?;
    dressed.insert("fontFamily".to_string(), Value::String(body.to_string()));
    dressed.insert(
        "headingFamily".to_string(),
        Value::String(heading.to_string()),
    );

    let override_of = |key: &str| -> Option<&Value> {
        let value = adv_map.get(key)?;
        (!is_default_advanced_value(key, value)).then_some(value)
    };

    if let Some(corner) = override_of("corner") {
        dressed.insert("corner".to_string(), corner.clone());
    } else if let Some(default_corner) = preset_corner(preset) {
        dressed.insert("corner".to_string(), json!(default_corner));
    }

    for (adv_key, theme_key) in [
        ("scale", "typeScale"),
        ("shadow", "shadow"),
        ("block", "blockStyle"),
        ("lines", "hourLines"),
        ("today", "todayHighlight"),
        ("times", "showTimes"),
        ("lengths", "showLengths"),
        ("rail", "railLabels"),
        ("padding", "cardPad"),
        ("now", "nowLine"),
    ] {
        if let Some(value) = override_of(adv_key) {
            dressed.insert(theme_key.to_string(), value.clone());
        }
    }

    if let Some(motion) = adv_map.get("motion") {
        if motion.as_str() == Some("Off") {
            dressed.insert("reduceMotion".to_string(), Value::Bool(true));
        }
        // Normal is the components' own speed; naming it would alter an untouched theme object.
        if !motion.is_null() && motion.as_str() != Some("Normal") {
            dressed.insert("motionSpeed".to_string(), motion.clone());
        }
    }

    if let Some(Value::Object(cats)) = adv_map.get("cat") {
        for (name, colour) in cats {
            if CATEGORY_KEYS.contains(&name.as_str()) && is_truthy(colour) {
                let mut chars = name.chars();
                if let Some(first) = chars.next() {
                    let key = format!("cat{}{}", first.to_ascii_uppercase(), chars.as_str());
                    dressed.insert(key, colour.clone());
                }
            }
        }
    }

    Ok(dressed)
}

fn round_two_decimals(value: f64) -> f64 {
    format!("{value:.2}").parse::<f64>().unwrap_or(value)
}

/// Category colours the student set that read under 4.5:1 against that category's ink, plus
/// a `now` line under 3.0:1 against the page surface.
pub fn reading_problems(mode: &str, advanced: &Value) -> EngineResult<Vec<Value>> {
    let adv_map = advanced
        .as_object()
        .ok_or_else(|| EngineError::value("advanced must be an object"))?;
    let mut problems = Vec::new();
    let cats = adv_map.get("cat").and_then(Value::as_object);
    for (key, role) in [
        ("school", "school"),
        ("sports", "soccer"),
        ("study", "reading"),
        ("homework", "homework"),
    ] {
        let Some(fill) = cats.and_then(|map| map.get(key)).and_then(Value::as_str) else {
            continue;
        };
        let (_, ink) = category_paint(role, mode)?;
        let ratio = tokens::contrast(ink, fill)?;
        if ratio >= 4.5 {
            continue;
        }
        let fixed = tokens::fit_lightness(fill, &[Value::String(ink.to_string())], 4.5)?;
        problems.push(json!({
            "words": format!("{key} colour on its ink"),
            "role": key,
            "ink": ink,
            "ground": fill,
            "ratio": round_two_decimals(ratio),
            "fixed": fixed,
        }));
    }
    if let Some(now) = adv_map.get("now").and_then(Value::as_str) {
        let surface = if mode == "dark" { "#1a1c20" } else { "#ffffff" };
        let ratio = tokens::contrast(now, surface)?;
        if ratio < 3.0 {
            let fixed = tokens::fit_lightness(now, &[Value::String(surface.to_string())], 3.0)?;
            problems.push(json!({
                "words": "now line on the page",
                "role": "now",
                "ink": now,
                "ground": surface,
                "ratio": round_two_decimals(ratio),
                "fixed": fixed,
            }));
        }
    }
    Ok(problems)
}

fn find_motion_level(name: &str) -> Option<(f64, f64)> {
    MOTION_LEVELS
        .iter()
        .find(|(id, _, _)| *id == name)
        .map(|(_, pace, reach)| (*pace, *reach))
}

fn resolve_level<'a>(level: Option<&'a str>, fallback: &'a str) -> &'a str {
    match level {
        Some(name) if !name.is_empty() => name,
        _ => fallback,
    }
}

/// The student's Animations setting, or the look's own when they never chose one.
pub fn motion_level(preference: Option<&str>, look_default: Option<&str>) -> &'static str {
    if let Some(pref) = preference
        && let Some((id, _, _)) = MOTION_LEVELS.iter().find(|(id, _, _)| *id == pref)
    {
        return id;
    }
    if let Some(default) = look_default
        && let Some((id, _, _)) = MOTION_LEVELS.iter().find(|(id, _, _)| *id == default)
    {
        return id;
    }
    "normal"
}

/// How long Normal's `ms` takes at `level` (or `fallback` when `level` is absent/empty); 0 is at once.
pub fn motion_duration(ms: i64, level: Option<&str>, fallback: &str) -> EngineResult<i64> {
    let chosen = resolve_level(level, fallback);
    let (pace, _) = find_motion_level(chosen).ok_or_else(|| EngineError::key(chosen))?;
    Ok((ms as f64 * pace).round_ties_even() as i64)
}

/// How far Normal's `px` goes at `level` (or `fallback`); 0 under Reduce and Off.
pub fn motion_distance(px: i64, level: Option<&str>, fallback: &str) -> EngineResult<i64> {
    let chosen = resolve_level(level, fallback);
    let (_, reach) = find_motion_level(chosen).ok_or_else(|| EngineError::key(chosen))?;
    Ok((px as f64 * reach).round_ties_even() as i64)
}

/// Whether things travel at `level` (or `fallback`), rather than only fading or not moving.
pub fn motion_moves(level: Option<&str>, fallback: &str) -> EngineResult<bool> {
    let chosen = resolve_level(level, fallback);
    let (_, reach) = find_motion_level(chosen).ok_or_else(|| EngineError::key(chosen))?;
    Ok(reach > 0.0)
}

/// Maps a known pack name to its light/dark/system axis.
pub fn pack_axis(pack: &Value) -> &'static str {
    match custom_look::known_pack(pack).as_str() {
        Some("light-frost" | "slate") => "slate",
        Some("dark-frost" | "nocturne") => "nocturne",
        _ => "system",
    }
}

/// The motion level a look starts at when the student never chose one: a custom look's own, Reduce
/// for Paper, else Normal.
pub fn look_motion(look: &Value) -> &'static str {
    let selected = custom_look::sanitize_look(look);
    if let Some(Value::Object(custom)) = selected.get("custom") {
        if let Some(motion) = custom
            .get("motion")
            .and_then(Value::as_str)
            .filter(|m| !m.is_empty())
            && let Some((id, _, _)) = MOTION_LEVELS.iter().find(|(id, _, _)| *id == motion)
        {
            return id;
        }
        let base = custom.get("base").and_then(Value::as_str).unwrap_or("");
        let base_preset = custom_look::LOOK_BASES
            .iter()
            .find(|(name, _, _)| *name == base)
            .map_or("", |(_, _, preset)| *preset);
        return if base_preset == "paper" {
            "reduce"
        } else {
            "normal"
        };
    }
    let preset = selected.get("preset").and_then(Value::as_str).unwrap_or("");
    if preset == "paper" {
        "reduce"
    } else {
        "normal"
    }
}
