//! Material look-file serialization, readers, and legacy layout/surface sanitizers
//! (`flexweek_app::views::look_file`) for the Python desktop layer. Every exported function
//! is wrapped in `guard(`.

use flexweek_app::views::look_file;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyFloat, PyInt, PyList, PyModule, PyString};
use serde_json::{Map, Value};

use crate::{guard, raise};

const MAX_PY_DEPTH: usize = 32;

fn parse_json(text: &str, what: &str) -> PyResult<Value> {
    serde_json::from_str(text).map_err(|error| PyValueError::new_err(format!("{what}: {error}")))
}

fn py_to_value(obj: &Bound<'_, PyAny>, depth: usize) -> PyResult<Value> {
    if depth >= MAX_PY_DEPTH || obj.is_none() {
        return Ok(Value::Null);
    }
    // Check PyBool before PyInt because Python's `bool` subclasses `int`.
    if obj.is_instance_of::<PyBool>() {
        return Ok(Value::Bool(obj.extract::<bool>()?));
    }
    if obj.is_instance_of::<PyInt>() {
        if let Ok(value) = obj.extract::<i64>() {
            return Ok(Value::Number(value.into()));
        }
        if let Ok(value) = obj.extract::<u64>() {
            return Ok(Value::Number(value.into()));
        }
        if let Ok(value) = obj.extract::<f64>() {
            return Ok(serde_json::Number::from_f64(value).map_or(Value::Null, Value::Number));
        }
        return Ok(Value::Null);
    }
    if obj.is_instance_of::<PyFloat>() {
        let value = obj.extract::<f64>()?;
        return Ok(serde_json::Number::from_f64(value).map_or(Value::Null, Value::Number));
    }
    if obj.is_instance_of::<PyString>() {
        return Ok(Value::String(obj.extract::<String>()?));
    }
    if let Ok(list) = obj.cast::<PyList>() {
        let mut items = Vec::with_capacity(list.len());
        for item in list.iter() {
            items.push(py_to_value(&item, depth + 1)?);
        }
        return Ok(Value::Array(items));
    }
    if let Ok(dict) = obj.cast::<PyDict>() {
        let mut map = Map::new();
        for (key, value) in dict.iter() {
            if key.is_instance_of::<PyString>() {
                let name = key.extract::<String>()?;
                map.insert(name, py_to_value(&value, depth + 1)?);
            }
        }
        return Ok(Value::Object(map));
    }
    Ok(Value::Null)
}

#[pyfunction]
fn views_look_read_material_choice(stored: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(Value::Object(look_file::read_material_choice(&parsed)).to_string())
    })
}

#[pyfunction]
fn views_look_read_font(stored: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(look_file::read_font(&parsed).to_string())
    })
}

#[pyfunction]
fn views_look_advanced_default() -> PyResult<String> {
    guard(|| Ok(Value::Object(look_file::advanced_default()).to_string()))
}

#[pyfunction]
fn views_look_hex_color(value: &Bound<'_, PyAny>) -> PyResult<Option<String>> {
    guard(|| {
        let parsed = py_to_value(value, 0)?;
        Ok(look_file::hex_color(&parsed))
    })
}

#[pyfunction]
fn views_look_int_in(value: &Bound<'_, PyAny>, bounds: (i64, i64)) -> PyResult<Option<i64>> {
    guard(|| {
        let parsed = py_to_value(value, 0)?;
        Ok(look_file::int_in(&parsed, bounds.0, bounds.1))
    })
}

#[pyfunction]
fn views_look_float_in(value: &Bound<'_, PyAny>, bounds: (f64, f64)) -> PyResult<Option<f64>> {
    guard(|| {
        let parsed = py_to_value(value, 0)?;
        Ok(look_file::float_in(&parsed, bounds.0, bounds.1))
    })
}

#[pyfunction]
fn views_look_read_advanced(stored: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(Value::Object(look_file::read_advanced(&parsed)).to_string())
    })
}

#[pyfunction]
fn views_look_read_shortcuts(stored: &Bound<'_, PyAny>) -> PyResult<bool> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(look_file::read_shortcuts(&parsed))
    })
}

#[pyfunction]
fn views_look_read_letter_keys(stored: &Bound<'_, PyAny>) -> PyResult<bool> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(look_file::read_letter_keys(&parsed))
    })
}

#[pyfunction]
fn views_look_read_saved_material(stored: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(Value::Array(look_file::read_saved_material(&parsed)).to_string())
    })
}

#[pyfunction]
fn views_look_advanced_overrides(advanced: &str) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(advanced, "advanced")?;
        let overrides = look_file::advanced_overrides(&parsed).map_err(raise)?;
        Ok(Value::Object(overrides).to_string())
    })
}

#[pyfunction]
fn views_look_read_look_tier(stored: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(look_file::read_look_tier(&parsed).to_string())
    })
}

#[pyfunction]
fn views_look_read_day_side_width(stored: &Bound<'_, PyAny>) -> PyResult<i64> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(look_file::read_day_side_width(&parsed))
    })
}

#[pyfunction]
fn views_look_read_settings_nav_width(stored: &Bound<'_, PyAny>) -> PyResult<i64> {
    guard(|| {
        let parsed = py_to_value(stored, 0)?;
        Ok(look_file::read_settings_nav_width(&parsed))
    })
}

#[pyfunction]
#[allow(clippy::too_many_arguments)]
#[pyo3(signature = (choice, advanced, shortcuts, letters, saved, font = "", tier = "", day_side_width = None, settings_nav_width = None))]
fn views_look_pack_material(
    choice: &str,
    advanced: &str,
    shortcuts: bool,
    letters: bool,
    saved: &str,
    font: &str,
    tier: &str,
    day_side_width: Option<&Bound<'_, PyAny>>,
    settings_nav_width: Option<&Bound<'_, PyAny>>,
) -> PyResult<String> {
    guard(|| {
        let parsed_choice = parse_json(choice, "choice")?;
        let parsed_adv = parse_json(advanced, "advanced")?;
        let parsed_saved = parse_json(saved, "saved")?;
        let day_val = match day_side_width {
            Some(obj) => py_to_value(obj, 0)?,
            None => Value::Null,
        };
        let nav_val = match settings_nav_width {
            Some(obj) => py_to_value(obj, 0)?,
            None => Value::Null,
        };
        let packed = look_file::pack_material(
            &parsed_choice,
            &parsed_adv,
            shortcuts,
            letters,
            &parsed_saved,
            font,
            tier,
            &day_val,
            &nav_val,
        )
        .map_err(raise)?;
        Ok(Value::Object(packed).to_string())
    })
}

#[pyfunction]
fn views_look_merge_material(existing_text: Option<&str>, material: &str) -> PyResult<String> {
    guard(|| {
        let parsed = parse_json(material, "material")?;
        look_file::merge_material_into_look_file(existing_text, &parsed).map_err(raise)
    })
}

#[pyfunction]
fn views_look_extract_kept_material(existing_text: &str) -> PyResult<Option<String>> {
    guard(|| {
        Ok(look_file::extract_kept_material(existing_text)
            .map(|map| Value::Object(map).to_string()))
    })
}

#[pyfunction]
fn views_look_export_document(choice: &str, advanced: &str) -> PyResult<String> {
    guard(|| {
        let parsed_choice = parse_json(choice, "choice")?;
        let parsed_adv = parse_json(advanced, "advanced")?;
        look_file::export_document(&parsed_choice, &parsed_adv).map_err(raise)
    })
}

#[pyfunction]
fn views_look_import_document(text: &str) -> PyResult<(Option<String>, String)> {
    guard(|| {
        let (found, error) = look_file::import_document(text);
        Ok((
            found.map(|map| Value::Object(map).to_string()),
            error.to_string(),
        ))
    })
}

#[pyfunction]
fn views_look_design_looks() -> PyResult<String> {
    guard(|| Ok(Value::Object(look_file::design_looks_json()).to_string()))
}

#[pyfunction]
fn views_look_layouts() -> PyResult<String> {
    guard(|| Ok(Value::Array(look_file::layouts_json()).to_string()))
}

#[pyfunction]
fn views_look_option_default(shipped: &str, first_choice: &str) -> PyResult<String> {
    guard(|| Ok(look_file::option_default(shipped, first_choice).to_string()))
}

#[pyfunction]
fn views_look_sanitize_layout(raw: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(raw, 0)?;
        Ok(Value::Object(look_file::sanitize_layout(&parsed)).to_string())
    })
}

#[pyfunction]
fn views_look_sanitize_surface(raw: &Bound<'_, PyAny>) -> PyResult<String> {
    guard(|| {
        let parsed = py_to_value(raw, 0)?;
        Ok(look_file::sanitize_surface(&parsed).to_string())
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("LOOK_MAIN_DEFAULT", look_file::MAIN_DEFAULT)?;
    module.add("LOOK_DAY_DEFAULT", look_file::DAY_DEFAULT)?;
    module.add("LOOK_SURFACES", look_file::SURFACES.to_vec())?;
    module.add("LOOK_SURFACE_DEFAULT", look_file::SURFACE_DEFAULT)?;
    crate::export!(
        module,
        views_look_read_material_choice,
        views_look_read_font,
        views_look_advanced_default,
        views_look_hex_color,
        views_look_int_in,
        views_look_float_in,
        views_look_read_advanced,
        views_look_read_shortcuts,
        views_look_read_letter_keys,
        views_look_read_saved_material,
        views_look_advanced_overrides,
        views_look_read_look_tier,
        views_look_read_day_side_width,
        views_look_read_settings_nav_width,
        views_look_pack_material,
        views_look_merge_material,
        views_look_extract_kept_material,
        views_look_export_document,
        views_look_import_document,
        views_look_design_looks,
        views_look_layouts,
        views_look_option_default,
        views_look_sanitize_layout,
        views_look_sanitize_surface,
    );
    Ok(())
}
