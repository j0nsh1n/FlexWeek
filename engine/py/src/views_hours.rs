//! Python bindings for the shared hour decisions. Each function checks the shape of what
//! crossed the boundary and calls the view; the view decides.

// The Python signatures pass each number and each block flag on its own, so a track adapter does no packing.
#![allow(clippy::too_many_arguments, clippy::fn_params_excessive_bools)]

use flexweek_app::views::hours::{self, BlockWords, Frame, Lane, Moment, Pixel, Ring};
use pyo3::exceptions::{PyTypeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyDict, PyInt, PyString};

fn frame(x: f64, y: f64, width: f64, height: f64) -> Frame {
    Frame {
        x,
        y,
        width,
        height,
    }
}

fn pixel_of(value: &Bound<'_, PyAny>) -> PyResult<Pixel> {
    if value.is_instance_of::<PyBool>() || !value.is_instance_of::<PyInt>() {
        return Ok(Pixel::Absent);
    }
    if let Ok(number) = value.extract::<i128>() {
        return Ok(Pixel::Number(number));
    }
    let text: String = value.str()?.extract()?;
    if text.starts_with('-') {
        Ok(Pixel::Low)
    } else {
        Ok(Pixel::High)
    }
}

fn chosen_step(value: &Bound<'_, PyAny>) -> Option<i64> {
    if value.is_instance_of::<PyBool>() || !value.is_instance_of::<PyInt>() {
        return None;
    }
    value.extract::<i64>().ok()
}

#[pyfunction]
fn hours_snap(minute: f64, step: i64) -> PyResult<i64> {
    crate::guard(|| hours::snap(minute, step).map_err(crate::raise))
}

#[pyfunction]
fn hours_next_slot(minute: i64, first: i64, last: i64, step: i64) -> PyResult<(i64, i64)> {
    crate::guard(|| hours::next_slot(minute, first, last, step).map_err(crate::raise))
}

#[pyfunction]
fn hours_drag_step(chosen: &Bound<'_, PyAny>) -> PyResult<i64> {
    crate::guard(|| Ok(hours::drag_step(chosen_step(chosen))))
}

#[pyfunction]
fn hours_overlap_columns(spans: Vec<(i64, i64)>) -> PyResult<Vec<(i64, i64)>> {
    crate::guard(|| hours::overlap_columns(&spans).map_err(crate::raise))
}

#[pyfunction]
fn hours_span_minutes(start: i64, end: i64) -> PyResult<i64> {
    crate::guard(|| Ok(hours::span_minutes(start, end)))
}

#[pyfunction]
fn hours_track_length(width: f64, height: f64, axis: &str) -> PyResult<f64> {
    crate::guard(|| hours::track_length(width, height, axis).map_err(crate::raise))
}

#[pyfunction]
fn hours_per_minute(width: f64, height: f64, axis: &str, first: i64, last: i64) -> PyResult<f64> {
    crate::guard(|| hours::track_per_minute(width, height, axis, first, last).map_err(crate::raise))
}

#[pyfunction]
fn hours_linear_offset(
    width: f64,
    height: f64,
    axis: &str,
    first: i64,
    last: i64,
    minute: f64,
) -> PyResult<f64> {
    crate::guard(|| {
        hours::linear_offset(width, height, axis, first, last, minute).map_err(crate::raise)
    })
}

#[pyfunction]
fn hours_linear_minute_at(
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    axis: &str,
    first: i64,
    last: i64,
    turn: f64,
    px: f64,
    py: f64,
) -> PyResult<f64> {
    crate::guard(|| {
        hours::linear_minute_at(frame(x, y, width, height), axis, first, last, turn, px, py)
            .map_err(crate::raise)
    })
}

#[pyfunction]
fn hours_linear_contains(
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    turn: f64,
    px: f64,
    py: f64,
) -> PyResult<bool> {
    crate::guard(|| {
        Ok(hours::linear_contains(
            frame(x, y, width, height),
            turn,
            px,
            py,
        ))
    })
}

#[pyfunction]
fn hours_linear_rect(
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    axis: &str,
    first: i64,
    last: i64,
    start: i64,
    end: i64,
    column: i64,
    columns: i64,
) -> PyResult<(f64, f64, f64, f64)> {
    crate::guard(|| {
        let drawn = hours::linear_rect(
            frame(x, y, width, height),
            axis,
            first,
            last,
            start,
            end,
            Lane { column, columns },
        )
        .map_err(crate::raise)?;
        Ok((drawn.x, drawn.y, drawn.width, drawn.height))
    })
}

#[pyfunction]
fn hours_linear_point(
    x: f64,
    y: f64,
    width: f64,
    height: f64,
    axis: &str,
    first: i64,
    last: i64,
    turn: f64,
    minute: i64,
) -> PyResult<(f64, f64)> {
    crate::guard(|| {
        hours::linear_point(frame(x, y, width, height), axis, first, last, turn, minute)
            .map_err(crate::raise)
    })
}

fn ring(x: f64, y: f64, inner: f64, outer: f64, first: i64, last: i64, sweep: f64) -> Ring {
    Ring {
        x,
        y,
        inner,
        outer,
        first,
        last,
        sweep,
    }
}

#[pyfunction]
fn hours_dial_turn(x: f64, y: f64, px: f64, py: f64) -> PyResult<f64> {
    crate::guard(|| {
        let face = ring(x, y, 0.0, 0.0, 0, 0, 0.0);
        Ok(hours::dial_turn(&face, px, py))
    })
}

#[pyfunction]
fn hours_dial_minute(
    x: f64,
    y: f64,
    inner: f64,
    outer: f64,
    first: i64,
    last: i64,
    sweep: f64,
    px: f64,
    py: f64,
) -> PyResult<f64> {
    crate::guard(|| {
        hours::dial_minute(&ring(x, y, inner, outer, first, last, sweep), px, py)
            .map_err(crate::raise)
    })
}

#[pyfunction]
fn hours_dial_contains(
    x: f64,
    y: f64,
    inner: f64,
    outer: f64,
    first: i64,
    last: i64,
    sweep: f64,
    px: f64,
    py: f64,
) -> PyResult<bool> {
    crate::guard(|| {
        Ok(hours::dial_contains(
            &ring(x, y, inner, outer, first, last, sweep),
            px,
            py,
        ))
    })
}

#[pyfunction]
fn hours_dial_point(
    x: f64,
    y: f64,
    inner: f64,
    outer: f64,
    first: i64,
    last: i64,
    sweep: f64,
    minute: i64,
) -> PyResult<(f64, f64)> {
    crate::guard(|| {
        hours::dial_point(&ring(x, y, inner, outer, first, last, sweep), minute)
            .map_err(crate::raise)
    })
}

#[pyfunction]
fn hours_scale_check(key: &str) -> PyResult<()> {
    crate::guard(|| hours::scale_check(key).map_err(PyValueError::new_err))
}

#[pyfunction]
fn hours_scale_nearest(levels: Vec<i64>, default: i64, px: &Bound<'_, PyAny>) -> PyResult<i64> {
    crate::guard(|| {
        let px = pixel_of(px)?;
        hours::nearest(&levels, default, px).map_err(PyValueError::new_err)
    })
}

#[pyfunction]
fn hours_scale_step(
    levels: Vec<i64>,
    default: i64,
    px: &Bound<'_, PyAny>,
    by: i64,
) -> PyResult<i64> {
    crate::guard(|| {
        let px = pixel_of(px)?;
        hours::step(&levels, default, px, by).map_err(PyValueError::new_err)
    })
}

#[pyfunction]
fn hours_opening_minute(
    today: Option<i64>,
    now: Option<i64>,
    day: Option<i64>,
    starts: Vec<i64>,
    day_starts: Option<Vec<i64>>,
) -> PyResult<i64> {
    crate::guard(|| {
        Ok(hours::opening_minute(
            today,
            now,
            day,
            &starts,
            day_starts.as_deref(),
        ))
    })
}

#[pyfunction]
fn hours_short_length(minutes: i64) -> PyResult<String> {
    crate::guard(|| Ok(hours::short_length(minutes)))
}

#[pyfunction]
fn hours_sanitize_zoom(raw: &Bound<'_, PyAny>) -> PyResult<Vec<(String, i64)>> {
    crate::guard(|| {
        if !raw.is_instance_of::<PyDict>() {
            return Ok(Vec::new());
        }
        let dict = raw.cast::<PyDict>()?;
        let mut pairs = Vec::new();
        for (key, value) in dict {
            let key = if key.is_instance_of::<PyString>() {
                Some(key.extract::<String>()?)
            } else {
                None
            };
            let px = if value.is_instance_of::<PyBool>() || !value.is_instance_of::<PyInt>() {
                None
            } else {
                value.extract::<i64>().ok()
            };
            pairs.push((key, px));
        }
        Ok(hours::sanitize_zoom(&pairs))
    })
}

#[pyfunction]
fn hours_read_clock(text: &str, end: bool, whole: bool) -> PyResult<Option<i64>> {
    crate::guard(|| Ok(hours::read_clock(text, end, whole)))
}

#[pyfunction]
fn hours_accepted_week_start(value: &Bound<'_, PyAny>) -> PyResult<String> {
    crate::guard(|| {
        let name = if value.is_instance_of::<PyString>() {
            Some(value.extract::<String>()?)
        } else {
            None
        };
        Ok(hours::accepted_week_start(name.as_deref()).to_string())
    })
}

#[pyfunction]
fn hours_week_start_day(name: &str) -> PyResult<i64> {
    crate::guard(|| Ok(hours::week_start_day(name)))
}

#[pyfunction]
fn hours_plan_placed(work: bool, pinned: bool, done: bool, missed: bool) -> PyResult<bool> {
    crate::guard(|| Ok(hours::plan_placed(work, pinned, done, missed)))
}

#[pyfunction]
fn hours_tag_words(history: &str, placed_by_plan: bool) -> PyResult<Vec<String>> {
    crate::guard(|| Ok(hours::tag_words(history, placed_by_plan)))
}

#[pyfunction]
fn hours_length_words(minutes: i64, done: bool, missed: bool) -> PyResult<String> {
    crate::guard(|| Ok(hours::length_words(minutes, done, missed)))
}

#[pyfunction]
fn hours_tail_words(
    words: &str,
    done: bool,
    pinned: bool,
    history: &str,
    history_due: Option<&str>,
    placed_by_plan: bool,
) -> PyResult<String> {
    crate::guard(|| {
        Ok(hours::tail_words(
            words,
            BlockWords {
                done,
                missed: false,
                pinned,
                history,
                history_due,
                placed_by_plan,
            },
        ))
    })
}

#[pyfunction]
fn hours_detail_words(
    start: i64,
    end: i64,
    done: bool,
    missed: bool,
    pinned: bool,
    history: &str,
    history_due: Option<&str>,
    placed_by_plan: bool,
) -> PyResult<String> {
    crate::guard(|| {
        Ok(hours::detail_words(
            start,
            end,
            BlockWords {
                done,
                missed,
                pinned,
                history,
                history_due,
                placed_by_plan,
            },
        ))
    })
}

#[pyfunction]
fn hours_end_after_start_words(start: &str) -> PyResult<String> {
    crate::guard(|| Ok(hours::end_after_start_words(start)))
}

#[pyfunction]
fn hours_homework_time_sentence(left_over: &str, needed: &str) -> PyResult<String> {
    crate::guard(|| hours::homework_time_sentence(left_over, needed).map_err(PyValueError::new_err))
}

#[pyfunction]
fn hours_overdue_indexes(
    dues: &Bound<'_, PyAny>,
    year: i32,
    month: i32,
    day: i32,
    hour: i32,
    minute: i32,
    second: i32,
    micro: i32,
) -> PyResult<Vec<usize>> {
    crate::guard(|| {
        if !dues.is_instance_of::<pyo3::types::PyList>() {
            return Err(PyTypeError::new_err("dues must be a list"));
        }
        let mut texts = Vec::new();
        for item in dues.try_iter()? {
            let item = item?;
            if item.is_none() || !item.is_instance_of::<PyString>() {
                texts.push(None);
            } else {
                texts.push(Some(item.extract::<String>()?));
            }
        }
        let borrowed: Vec<Option<&str>> = texts.iter().map(|text| text.as_deref()).collect();
        let now = Moment {
            year,
            month,
            day,
            hour,
            minute,
            second,
            micro,
        };
        Ok(hours::overdue_indexes(&borrowed, &now))
    })
}

pub fn add(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add("HOURS_GAP", hours::GAP)?;
    module.add("HOURS_BETWEEN", hours::BETWEEN)?;
    module.add("HOURS_OPENS", hours::OPENS)?;
    module.add("HOURS_NARROW_WIDTH", hours::NARROW_WIDTH)?;
    module.add("HOURS_DEFAULT_DRAG_STEP", hours::DEFAULT_DRAG_STEP)?;
    module.add("HOURS_DRAG_STEPS", hours::DRAG_STEPS.to_vec())?;
    crate::export!(
        module,
        hours_snap,
        hours_next_slot,
        hours_drag_step,
        hours_overlap_columns,
        hours_span_minutes,
        hours_track_length,
        hours_per_minute,
        hours_linear_offset,
        hours_linear_minute_at,
        hours_linear_contains,
        hours_linear_rect,
        hours_linear_point,
        hours_dial_turn,
        hours_dial_minute,
        hours_dial_contains,
        hours_dial_point,
        hours_scale_check,
        hours_scale_nearest,
        hours_scale_step,
        hours_opening_minute,
        hours_short_length,
        hours_sanitize_zoom,
        hours_read_clock,
        hours_accepted_week_start,
        hours_week_start_day,
        hours_plan_placed,
        hours_tag_words,
        hours_length_words,
        hours_tail_words,
        hours_detail_words,
        hours_end_after_start_words,
        hours_homework_time_sentence,
        hours_overdue_indexes,
    );
    Ok(())
}
