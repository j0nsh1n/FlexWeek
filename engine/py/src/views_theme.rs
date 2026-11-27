//! Material theme schemes, category paint, motion levels and look motion (`flexweek_app::views::theme`)
//! for the Python desktop layer. Every exported function is wrapped in `guard(`.

use ::flexweek_engine::EngineError;
use ::flexweek_engine::desk::custom_look;
use flexweek_app::views::theme;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyModule};
use serde_json::{Value, json};

use crate::{guard, raise};

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

#[pyfunction]
fn views_theme_scheme_key(preset: &str, mode: &str, contrast_name: &str) -> PyResult<String> {
    guard(|| Ok(theme::scheme_key(preset, mode, contrast_name)))
}

/// `loaded` is the scheme map the desktop read from its own `tokens.json`. A scheme that file does not
/// hold is a KeyError, as when the desktop looked it up there, so a missing or broken file never opens
/// Material; the colours come from the copy compiled in.
#[pyfunction]
fn views_theme_scheme(
    preset: &str,
    mode: &str,
    contrast_name: &str,
    loaded: &Bound<'_, PyDict>,
) -> PyResult<String> {
    guard(|| {
        let key = theme::scheme_source_key(preset, mode, contrast_name).map_err(raise)?;
        let held = loaded.get_item(&key)?;
        if !held.is_some_and(|value| value.is_instance_of::<PyDict>()) {
            return Err(raise(EngineError::key(key)));
        }
        let found = theme::scheme(preset, mode, contrast_name).map_err(raise)?;
        Ok(Value::Object(found).to_string())
    })
}

#[pyfunction]
fn views_theme_stroke_for(contrast_name: &str) -> PyResult<f64> {
    guard(|| theme::stroke_for(contrast_name).map_err(raise))
}

#[pyfunction]
fn views_theme_bar_for_category(category: &str) -> PyResult<String> {
    guard(|| Ok(theme::bar_for_category(category).to_string()))
}

#[pyfunction]
fn views_theme_paint_for_category(category: &str, mode: &str) -> PyResult<(String, String)> {
    guard(|| {
        let (fill, ink) = theme::paint_for_category(category, mode).map_err(raise)?;
        Ok((fill, ink.to_string()))
    })
}

#[pyfunction]
fn views_theme_category_paint(role: &str, mode: &str) -> PyResult<(String, String)> {
    guard(|| {
        let (fill, ink) = theme::category_paint(role, mode).map_err(raise)?;
        Ok((fill, ink.to_string()))
    })
}

#[pyfunction]
fn views_theme_event_category(category: &str) -> PyResult<String> {
    guard(|| Ok(theme::event_category(category).to_string()))
}

#[pyfunction]
fn views_theme_resolved_mode(mode: &str, worn_dark: bool) -> PyResult<String> {
    guard(|| Ok(theme::resolved_mode(mode, worn_dark).to_string()))
}

#[pyfunction]
fn views_theme_mode_of(choice: &str, worn_dark: bool) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(choice, "choice")?;
        let mode = theme::mode_of(&parsed, worn_dark).map_err(raise)?;
        Ok(mode.to_string())
    })
}

#[pyfunction]
fn views_theme_shown_font(preset: &str, font: &str) -> PyResult<String> {
    guard(|| Ok(theme::shown_font(preset, font)))
}

#[pyfunction]
fn views_theme_read_accent(preferences: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let value = match preferences.cast::<PyDict>() {
            Ok(dict) => match dict.get_item("accent")? {
                Some(item) => match item.extract::<String>() {
                    Ok(accent) => json!({ "accent": accent }),
                    Err(_) => Value::Null,
                },
                None => Value::Null,
            },
            Err(_) => Value::Null,
        };
        Ok(theme::read_accent(&value).to_string())
    })
}

#[pyfunction]
fn views_theme_accented(
    colours: &str,
    accent: &str,
    preset: &str,
    mode: &str,
    contrast_name: &str,
) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(colours, "colours")?;
        let found = theme::accented(&parsed, accent, preset, mode, contrast_name).map_err(raise)?;
        Ok(Value::Object(found).to_string())
    })
}

#[pyfunction]
#[pyo3(signature = (colours, density, reduce_motion, high_contrast, chips_accent = false))]
fn views_theme_object(
    colours: &str,
    density: &str,
    reduce_motion: bool,
    high_contrast: bool,
    chips_accent: bool,
) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(colours, "colours")?;
        let found =
            theme::theme_object(&parsed, density, reduce_motion, high_contrast, chips_accent)
                .map_err(raise)?;
        Ok(Value::Object(found).to_string())
    })
}

#[pyfunction]
fn views_theme_hour_row_px(density: &str, advanced: &str) -> PyResult<i64> {
    guard(|| {
        let parsed = parse_json(advanced, "advanced")?;
        theme::hour_row_px(density, &parsed).map_err(raise)
    })
}

#[pyfunction]
#[pyo3(signature = (theme_json, advanced, preset = "", font = ""))]
fn views_theme_dress_theme(
    theme_json: &str,
    advanced: &str,
    preset: &str,
    font: &str,
) -> PyResult<String> {
    guard(|| {
        let parsed_theme = parse_json(theme_json, "theme")?;
        let parsed_adv = parse_json(advanced, "advanced")?;
        let dressed =
            theme::dress_theme(&parsed_theme, &parsed_adv, preset, font).map_err(raise)?;
        Ok(Value::Object(dressed).to_string())
    })
}

#[pyfunction]
fn views_theme_reading_problems(mode: &str, advanced: &str) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(advanced, "advanced")?;
        let problems = theme::reading_problems(mode, &parsed).map_err(raise)?;
        Ok(Value::Array(problems).to_string())
    })
}

#[pyfunction]
fn views_theme_motion_levels() -> PyResult<Vec<(String, f64, f64)>> {
    guard(|| {
        Ok(theme::MOTION_LEVELS
            .iter()
            .map(|(name, pace, reach)| ((*name).to_string(), *pace, *reach))
            .collect())
    })
}

#[pyfunction]
fn views_theme_motion_level(
    preference: &Bound<'_, PyAny>,
    look_default: &Bound<'_, PyAny>,
) -> PyResult<String> {
    guard(|| {
        let pref = preference.extract::<String>().ok();
        let look = look_default.extract::<String>().ok();
        Ok(theme::motion_level(pref.as_deref(), look.as_deref()).to_string())
    })
}

#[pyfunction]
#[pyo3(signature = (ms, level = None, fallback = "normal"))]
fn views_theme_motion_duration(ms: i64, level: Option<&str>, fallback: &str) -> PyResult<i64> {
    guard(|| theme::motion_duration(ms, level, fallback).map_err(raise))
}

#[pyfunction]
#[pyo3(signature = (px, level = None, fallback = "normal"))]
fn views_theme_motion_distance(px: i64, level: Option<&str>, fallback: &str) -> PyResult<i64> {
    guard(|| theme::motion_distance(px, level, fallback).map_err(raise))
}

#[pyfunction]
#[pyo3(signature = (level = None, fallback = "normal"))]
fn views_theme_motion_moves(level: Option<&str>, fallback: &str) -> PyResult<bool> {
    guard(|| theme::motion_moves(level, fallback).map_err(raise))
}

#[pyfunction]
fn views_theme_pack_axis(pack: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let value = pack.extract::<String>().map_or(Value::Null, Value::from);
        Ok(theme::pack_axis(&value).to_string())
    })
}

#[pyfunction]
fn views_theme_look_motion(raw: &str) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(raw, "look")?;
        let readable = custom_look::readable(&parsed);
        Ok(theme::look_motion(&readable).to_string())
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("MOTION_EASE_MS", theme::MOTION_EASE_MS)?;
    crate::export!(
        module,
        views_theme_scheme_key,
        views_theme_scheme,
        views_theme_stroke_for,
        views_theme_bar_for_category,
        views_theme_paint_for_category,
        views_theme_category_paint,
        views_theme_event_category,
        views_theme_resolved_mode,
        views_theme_mode_of,
        views_theme_shown_font,
        views_theme_read_accent,
        views_theme_accented,
        views_theme_object,
        views_theme_hour_row_px,
        views_theme_dress_theme,
        views_theme_reading_problems,
        views_theme_motion_levels,
        views_theme_motion_level,
        views_theme_motion_duration,
        views_theme_motion_distance,
        views_theme_motion_moves,
        views_theme_pack_axis,
        views_theme_look_motion,
    );
    Ok(())
}
