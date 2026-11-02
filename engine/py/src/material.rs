//! The Material scheme. The core stays free of Qt; the platform accent is read in Python.

use ::flexweek_engine::material;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyModule};

use crate::guard;

#[pyfunction]
fn material_scheme<'py>(
    py: Python<'py>,
    seed: &str,
    style: &str,
    dark: bool,
    contrast: f64,
) -> PyResult<Bound<'py, PyDict>> {
    guard(|| {
        let pairs = material::material_scheme(seed, style, dark, contrast).map_err(crate::raise)?;
        let dict = PyDict::new(py);
        for (name, colour) in pairs {
            dict.set_item(name, colour)?;
        }
        Ok(dict)
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    crate::export!(module, material_scheme);
    Ok(())
}
