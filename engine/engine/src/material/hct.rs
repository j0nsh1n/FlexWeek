//! HCT and the CAM16 pieces a scheme needs, from material-color-utilities.
//! Copyright 2021 Google LLC. Apache-2.0. See `NOTICE`.
//!
//! The solver follows `hct/hct_solver.js`. Comparisons that look exact are the
//! library's own: a plane index, a zero chroma, and the sign of a zero.

#![allow(clippy::float_cmp, clippy::many_single_char_names)]

use std::f64::consts::PI;
use std::sync::OnceLock;

use super::color::{
    argb_from_linrgb, argb_from_lstar, lerp, linearized, lstar_from_argb, matrix_multiply,
    sanitize_degrees, signum, white_point_d65, y_from_lstar,
};
use super::planes::CRITICAL_PLANES;

#[derive(Clone, Copy, Debug)]
pub(crate) struct Hct {
    pub argb: u32,
    pub hue: f64,
    pub chroma: f64,
    pub tone: f64,
}

impl Hct {
    pub(crate) fn from_argb(argb: u32) -> Self {
        let cam = cam16_from_argb(argb);
        Self {
            argb,
            hue: cam.0,
            chroma: cam.1,
            tone: lstar_from_argb(argb),
        }
    }

    pub(crate) fn from(hue: f64, chroma: f64, tone: f64) -> Self {
        Self::from_argb(solve_to_int(hue, chroma, tone))
    }
}

/// Dark yellow-greens are lifted to tone 70. Anything else is returned as it is.
pub(crate) fn fix_if_disliked(hct: Hct) -> Hct {
    let hue_passes = hct.hue.round() >= 90.0 && hct.hue.round() <= 111.0;
    let chroma_passes = hct.chroma.round() > 16.0;
    let tone_passes = hct.tone.round() < 65.0;
    if hue_passes && chroma_passes && tone_passes {
        Hct::from(hct.hue, hct.chroma, 70.0)
    } else {
        hct
    }
}

struct Viewing {
    n: f64,
    aw: f64,
    nbb: f64,
    ncb: f64,
    c: f64,
    nc: f64,
    rgb_d: [f64; 3],
    fl: f64,
}

fn standard_viewing() -> &'static Viewing {
    static VIEW: OnceLock<Viewing> = OnceLock::new();
    VIEW.get_or_init(|| {
        let xyz = white_point_d65();
        let adapting = (200.0 / PI) * y_from_lstar(50.0) / 100.0;
        let surround = 2.0;
        let r_w = xyz[0] * 0.401_288 + xyz[1] * 0.650_173 + xyz[2] * -0.051_461;
        let g_w = xyz[0] * -0.250_268 + xyz[1] * 1.204_414 + xyz[2] * 0.045_854;
        let b_w = xyz[0] * -0.002_079 + xyz[1] * 0.048_952 + xyz[2] * 0.953_127;
        let f = 0.8 + surround / 10.0;
        let c = if f >= 0.9 {
            lerp(0.59, 0.69, (f - 0.9) * 10.0)
        } else {
            lerp(0.525, 0.59, (f - 0.8) * 10.0)
        };
        let mut d = f * (1.0 - (1.0 / 3.6) * ((-adapting - 42.0) / 92.0).exp());
        d = d.clamp(0.0, 1.0);
        let rgb_d = [
            d * (100.0 / r_w) + 1.0 - d,
            d * (100.0 / g_w) + 1.0 - d,
            d * (100.0 / b_w) + 1.0 - d,
        ];
        let k = 1.0 / (5.0 * adapting + 1.0);
        let k4 = k * k * k * k;
        let k4_f = 1.0 - k4;
        let fl = k4 * adapting + 0.1 * k4_f * k4_f * (5.0 * adapting).cbrt();
        let n = y_from_lstar(50.0) / xyz[1];
        let nbb = 0.725 / n.powf(0.2);
        let factors = [
            ((fl * rgb_d[0] * r_w) / 100.0).powf(0.42),
            ((fl * rgb_d[1] * g_w) / 100.0).powf(0.42),
            ((fl * rgb_d[2] * b_w) / 100.0).powf(0.42),
        ];
        let rgb_a = [
            (400.0 * factors[0]) / (factors[0] + 27.13),
            (400.0 * factors[1]) / (factors[1] + 27.13),
            (400.0 * factors[2]) / (factors[2] + 27.13),
        ];
        let aw = (2.0 * rgb_a[0] + rgb_a[1] + 0.05 * rgb_a[2]) * nbb;
        Viewing {
            n,
            aw,
            nbb,
            ncb: nbb,
            c,
            nc: f,
            rgb_d,
            fl,
        }
    })
}

fn cam16_from_argb(argb: u32) -> (f64, f64) {
    let view = standard_viewing();
    let red_l = linearized(f64::from((argb >> 16) & 255));
    let green_l = linearized(f64::from((argb >> 8) & 255));
    let blue_l = linearized(f64::from(argb & 255));
    let x = 0.412_338_95 * red_l + 0.357_620_64 * green_l + 0.180_510_42 * blue_l;
    let y = 0.2126 * red_l + 0.7152 * green_l + 0.0722 * blue_l;
    let z = 0.019_321_41 * red_l + 0.119_163_82 * green_l + 0.950_344_78 * blue_l;
    let r_c = 0.401_288 * x + 0.650_173 * y - 0.051_461 * z;
    let g_c = -0.250_268 * x + 1.204_414 * y + 0.045_854 * z;
    let b_c = -0.002_079 * x + 0.048_952 * y + 0.953_127 * z;
    let r_d = view.rgb_d[0] * r_c;
    let g_d = view.rgb_d[1] * g_c;
    let b_d = view.rgb_d[2] * b_c;
    let r_af = ((view.fl * r_d.abs()) / 100.0).powf(0.42);
    let g_af = ((view.fl * g_d.abs()) / 100.0).powf(0.42);
    let b_af = ((view.fl * b_d.abs()) / 100.0).powf(0.42);
    let r_a = (signum(r_d) * 400.0 * r_af) / (r_af + 27.13);
    let g_a = (signum(g_d) * 400.0 * g_af) / (g_af + 27.13);
    let b_a = (signum(b_d) * 400.0 * b_af) / (b_af + 27.13);
    let a = (11.0 * r_a + -12.0 * g_a + b_a) / 11.0;
    let b = (r_a + g_a - 2.0 * b_a) / 9.0;
    let u = (20.0 * r_a + 20.0 * g_a + 21.0 * b_a) / 20.0;
    let p2 = (40.0 * r_a + 20.0 * g_a + b_a) / 20.0;
    let atan_degrees = b.atan2(a) * 180.0 / PI;
    let hue = if atan_degrees < 0.0 {
        atan_degrees + 360.0
    } else if atan_degrees >= 360.0 {
        atan_degrees - 360.0
    } else {
        atan_degrees
    };
    let ac = p2 * view.nbb;
    let j = 100.0 * (ac / view.aw).powf(view.c * view.z());
    let hue_prime = if hue < 20.14 { hue + 360.0 } else { hue };
    let e_hue = 0.25 * ((hue_prime * PI / 180.0 + 2.0).cos() + 3.8);
    let p1 = (50000.0 / 13.0) * e_hue * view.nc * view.ncb;
    let t = (p1 * (a * a + b * b).sqrt()) / (u + 0.305);
    let alpha = t.powf(0.9) * (1.64 - 0.29_f64.powf(view.n)).powf(0.73);
    let chroma = alpha * (j / 100.0).sqrt();
    (hue, chroma)
}

impl Viewing {
    fn z(&self) -> f64 {
        1.48 + self.n.sqrt()
    }
}

const SCALED_DISCOUNT_FROM_LINRGB: [[f64; 3]; 3] = [
    [
        0.001_200_833_568_784_504,
        0.002_389_694_492_170_889,
        0.000_279_574_288_586_112_4,
    ],
    [
        0.000_589_108_665_137_599_9,
        0.002_978_550_257_343_875_8,
        0.000_327_066_610_400_839_8,
    ],
    [
        0.000_101_466_924_916_405_72,
        0.000_536_421_435_918_669_4,
        0.003_297_940_177_071_207_6,
    ],
];

const LINRGB_FROM_SCALED_DISCOUNT: [[f64; 3]; 3] = [
    [
        1_373.219_870_959_423_1,
        -1_100.425_119_075_482_1,
        -7.278_681_089_101_213,
    ],
    [
        -271.815_969_077_903,
        559.658_046_594_073_3,
        -32.460_474_827_911_94,
    ],
    [
        1.962_289_959_966_566_6,
        -57.173_814_538_844_006,
        308.723_319_781_238_5,
    ],
];

const Y_FROM_LINRGB: [f64; 3] = [0.2126, 0.7152, 0.0722];

fn sanitize_radians(angle: f64) -> f64 {
    (angle + PI * 8.0) % (PI * 2.0)
}

fn true_delinearized(rgb_component: f64) -> f64 {
    let normalized = rgb_component / 100.0;
    let delinearized = if normalized <= 0.003_130_8 {
        normalized * 12.92
    } else {
        1.055 * normalized.powf(1.0 / 2.4) - 0.055
    };
    delinearized * 255.0
}

fn chromatic_adaptation(component: f64) -> f64 {
    let af = component.abs().powf(0.42);
    signum(component) * 400.0 * af / (af + 27.13)
}

fn hue_of(linrgb: [f64; 3]) -> f64 {
    let scaled = matrix_multiply(linrgb, SCALED_DISCOUNT_FROM_LINRGB);
    let r_a = chromatic_adaptation(scaled[0]);
    let g_a = chromatic_adaptation(scaled[1]);
    let b_a = chromatic_adaptation(scaled[2]);
    let a = (11.0 * r_a + -12.0 * g_a + b_a) / 11.0;
    let b = (r_a + g_a - 2.0 * b_a) / 9.0;
    b.atan2(a)
}

fn are_in_cyclic_order(a: f64, b: f64, c: f64) -> bool {
    sanitize_radians(b - a) < sanitize_radians(c - a)
}

fn lerp_point(source: [f64; 3], t: f64, target: [f64; 3]) -> [f64; 3] {
    [
        source[0] + (target[0] - source[0]) * t,
        source[1] + (target[1] - source[1]) * t,
        source[2] + (target[2] - source[2]) * t,
    ]
}

fn set_coordinate(source: [f64; 3], coordinate: f64, target: [f64; 3], axis: usize) -> [f64; 3] {
    let t = (coordinate - source[axis]) / (target[axis] - source[axis]);
    lerp_point(source, t, target)
}

fn is_bounded(x: f64) -> bool {
    (0.0..=100.0).contains(&x)
}

fn nth_vertex(y: f64, n: i32) -> [f64; 3] {
    let (k_r, k_g, k_b) = (Y_FROM_LINRGB[0], Y_FROM_LINRGB[1], Y_FROM_LINRGB[2]);
    let coord_a = if n % 4 <= 1 { 0.0 } else { 100.0 };
    let coord_b = if n % 2 == 0 { 0.0 } else { 100.0 };
    if n < 4 {
        let g = coord_a;
        let b = coord_b;
        let r = (y - g * k_g - b * k_b) / k_r;
        if is_bounded(r) {
            [r, g, b]
        } else {
            [-1.0, -1.0, -1.0]
        }
    } else if n < 8 {
        let b = coord_a;
        let r = coord_b;
        let g = (y - r * k_r - b * k_b) / k_g;
        if is_bounded(g) {
            [r, g, b]
        } else {
            [-1.0, -1.0, -1.0]
        }
    } else {
        let r = coord_a;
        let g = coord_b;
        let b = (y - r * k_r - g * k_g) / k_b;
        if is_bounded(b) {
            [r, g, b]
        } else {
            [-1.0, -1.0, -1.0]
        }
    }
}

fn bisect_to_segment(y: f64, target_hue: f64) -> ([f64; 3], [f64; 3]) {
    let mut left = [-1.0, -1.0, -1.0];
    let mut right = left;
    let mut left_hue = 0.0;
    let mut right_hue = 0.0;
    let mut initialized = false;
    let mut uncut = true;
    for n in 0..12 {
        let mid = nth_vertex(y, n);
        if mid[0] < 0.0 {
            continue;
        }
        let mid_hue = hue_of(mid);
        if !initialized {
            left = mid;
            right = mid;
            left_hue = mid_hue;
            right_hue = mid_hue;
            initialized = true;
            continue;
        }
        if uncut || are_in_cyclic_order(left_hue, mid_hue, right_hue) {
            uncut = false;
            if are_in_cyclic_order(left_hue, target_hue, mid_hue) {
                right = mid;
                right_hue = mid_hue;
            } else {
                left = mid;
                left_hue = mid_hue;
            }
        }
    }
    (left, right)
}

fn critical_plane_below(x: f64) -> i32 {
    (x - 0.5).floor() as i32
}

fn critical_plane_above(x: f64) -> i32 {
    (x - 0.5).ceil() as i32
}

fn bisect_to_limit(y: f64, target_hue: f64) -> [f64; 3] {
    let (mut left, mut right) = bisect_to_segment(y, target_hue);
    let mut left_hue = hue_of(left);
    for axis in 0..3 {
        if left[axis] == right[axis] {
            continue;
        }
        let (mut l_plane, mut r_plane) = if left[axis] < right[axis] {
            (
                critical_plane_below(true_delinearized(left[axis])),
                critical_plane_above(true_delinearized(right[axis])),
            )
        } else {
            (
                critical_plane_above(true_delinearized(left[axis])),
                critical_plane_below(true_delinearized(right[axis])),
            )
        };
        for _ in 0..8 {
            if (r_plane - l_plane).abs() <= 1 {
                break;
            }
            let m_plane = (((l_plane + r_plane) as f64) / 2.0).floor() as i32;
            let mid = set_coordinate(left, CRITICAL_PLANES[m_plane as usize], right, axis);
            let mid_hue = hue_of(mid);
            if are_in_cyclic_order(left_hue, target_hue, mid_hue) {
                right = mid;
                r_plane = m_plane;
            } else {
                left = mid;
                left_hue = mid_hue;
                l_plane = m_plane;
            }
        }
    }
    [
        (left[0] + right[0]) / 2.0,
        (left[1] + right[1]) / 2.0,
        (left[2] + right[2]) / 2.0,
    ]
}

fn inverse_chromatic_adaptation(adapted: f64) -> f64 {
    let adapted_abs = adapted.abs();
    let base = (27.13 * adapted_abs / (400.0 - adapted_abs)).max(0.0);
    signum(adapted) * base.powf(1.0 / 0.42)
}

fn find_result_by_j(hue_radians: f64, chroma: f64, y: f64) -> u32 {
    let view = standard_viewing();
    let mut j = y.sqrt() * 11.0;
    let t_inner = 1.0 / (1.64 - 0.29_f64.powf(view.n)).powf(0.73);
    let e_hue = 0.25 * ((hue_radians + 2.0).cos() + 3.8);
    let p1 = e_hue * (50000.0 / 13.0) * view.nc * view.ncb;
    let h_sin = hue_radians.sin();
    let h_cos = hue_radians.cos();
    let z = view.z();
    for iteration in 0..5 {
        let j_normalized = j / 100.0;
        let alpha = if chroma == 0.0 || j == 0.0 {
            0.0
        } else {
            chroma / j_normalized.sqrt()
        };
        let t = (alpha * t_inner).powf(1.0 / 0.9);
        let ac = view.aw * j_normalized.powf(1.0 / view.c / z);
        let p2 = ac / view.nbb;
        let gamma = 23.0 * (p2 + 0.305) * t / (23.0 * p1 + 11.0 * t * h_cos + 108.0 * t * h_sin);
        let a = gamma * h_cos;
        let b = gamma * h_sin;
        let r_a = (460.0 * p2 + 451.0 * a + 288.0 * b) / 1403.0;
        let g_a = (460.0 * p2 - 891.0 * a - 261.0 * b) / 1403.0;
        let b_a = (460.0 * p2 - 220.0 * a - 6300.0 * b) / 1403.0;
        let linrgb = matrix_multiply(
            [
                inverse_chromatic_adaptation(r_a),
                inverse_chromatic_adaptation(g_a),
                inverse_chromatic_adaptation(b_a),
            ],
            LINRGB_FROM_SCALED_DISCOUNT,
        );
        if linrgb[0] < 0.0 || linrgb[1] < 0.0 || linrgb[2] < 0.0 {
            return 0;
        }
        let fnj = Y_FROM_LINRGB[0] * linrgb[0]
            + Y_FROM_LINRGB[1] * linrgb[1]
            + Y_FROM_LINRGB[2] * linrgb[2];
        if fnj <= 0.0 {
            return 0;
        }
        if iteration == 4 || (fnj - y).abs() < 0.002 {
            if linrgb[0] > 100.01 || linrgb[1] > 100.01 || linrgb[2] > 100.01 {
                return 0;
            }
            return argb_from_linrgb(linrgb);
        }
        j -= (fnj - y) * j / (2.0 * fnj);
    }
    0
}

pub(crate) fn solve_to_int(hue_degrees: f64, chroma: f64, lstar: f64) -> u32 {
    if chroma < 0.0001 || lstar < 0.0001 || lstar > 99.9999 {
        return argb_from_lstar(lstar);
    }
    let hue_degrees = sanitize_degrees(hue_degrees);
    let y = y_from_lstar(lstar);
    let exact = find_result_by_j(hue_degrees / 180.0 * PI, chroma, y);
    if exact != 0 {
        return exact;
    }
    argb_from_linrgb(bisect_to_limit(y, hue_degrees / 180.0 * PI))
}
