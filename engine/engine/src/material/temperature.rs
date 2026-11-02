//! Complementary hue for the Fidelity scheme, from `temperature/temperature_cache.js`.
//! Copyright 2023 Google LLC. Apache-2.0. See `NOTICE`.

#![allow(clippy::float_cmp)]

use std::f64::consts::PI;

use super::color::{lab_from_argb, sanitize_degrees};
use super::hct::Hct;

/// The colour as cool-warm as `input` is warm-cool, at the same chroma and tone.
pub(crate) fn complement(input: Hct) -> Hct {
    let by_hue: Vec<Hct> = (0..=360)
        .map(|hue| Hct::from(f64::from(hue), input.chroma, input.tone))
        .collect();
    let temps: Vec<f64> = by_hue.iter().copied().map(raw_temperature).collect();
    let input_temp = raw_temperature(input);
    let (cold_t, cold_hue, warm_t, warm_hue) = extremes(&temps, &by_hue, input, input_temp);
    let range = warm_t - cold_t;
    let input_rel = relative(input_temp, cold_t, range);
    let cold_to_warm = is_between(input.hue, cold_hue, warm_hue);
    let start_hue = if cold_to_warm { warm_hue } else { cold_hue };
    let end_hue = if cold_to_warm { cold_hue } else { warm_hue };
    let mut smallest = 1000.0;
    let mut answer = by_hue[hue_index(input.hue)];
    let target = 1.0 - input_rel;
    for addend in 0..=360 {
        let hue = sanitize_degrees(start_hue + f64::from(addend));
        if !is_between(hue, start_hue, end_hue) {
            continue;
        }
        let index = hue_index(hue);
        let rel = (temps[index] - cold_t) / range;
        let error = (target - rel).abs();
        if error < smallest {
            smallest = error;
            answer = by_hue[index];
        }
    }
    answer
}

fn extremes(temps: &[f64], by_hue: &[Hct], input: Hct, input_temp: f64) -> (f64, f64, f64, f64) {
    // Hue samples come first, then the input, and a stable sort keeps that order on a tie.
    let mut cold_t = f64::INFINITY;
    let mut warm_t = f64::NEG_INFINITY;
    let mut cold_hue = input.hue;
    let mut warm_hue = input.hue;
    for (temp, sample) in temps.iter().zip(by_hue) {
        if *temp < cold_t {
            cold_t = *temp;
            cold_hue = sample.hue;
        }
        if *temp >= warm_t {
            warm_t = *temp;
            warm_hue = sample.hue;
        }
    }
    if input_temp < cold_t {
        cold_t = input_temp;
        cold_hue = input.hue;
    }
    if input_temp >= warm_t {
        warm_t = input_temp;
        warm_hue = input.hue;
    }
    (cold_t, cold_hue, warm_t, warm_hue)
}

fn relative(temp: f64, cold: f64, range: f64) -> f64 {
    if range == 0.0 {
        0.5
    } else {
        (temp - cold) / range
    }
}

fn is_between(angle: f64, a: f64, b: f64) -> bool {
    if a < b {
        a <= angle && angle <= b
    } else {
        a <= angle || angle <= b
    }
}

fn hue_index(hue: f64) -> usize {
    hue.round() as usize
}

fn raw_temperature(color: Hct) -> f64 {
    let lab = lab_from_argb(color.argb);
    let hue = sanitize_degrees(lab[2].atan2(lab[1]) * 180.0 / PI);
    let chroma = (lab[1] * lab[1] + lab[2] * lab[2]).sqrt();
    -0.5 + 0.02 * chroma.powf(1.07) * sanitize_degrees(hue - 50.0).to_radians().cos()
}
