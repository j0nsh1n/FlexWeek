//! sRGB, XYZ and L* conversions from material-color-utilities `utils/color_utils.js`.
//! Copyright 2021 Google LLC. Apache-2.0. See `NOTICE`.

const SRGB_TO_XYZ: [[f64; 3]; 3] = [
    [0.412_338_95, 0.357_620_64, 0.180_510_42],
    [0.2126, 0.7152, 0.0722],
    [0.019_321_41, 0.119_163_82, 0.950_344_78],
];

const WHITE_POINT_D65: [f64; 3] = [95.047, 100.0, 108.883];

pub(crate) fn argb_from_rgb(red: i32, green: i32, blue: i32) -> u32 {
    0xff00_0000 | ((red as u32 & 255) << 16) | ((green as u32 & 255) << 8) | (blue as u32 & 255)
}

pub(crate) fn argb_from_linrgb(linrgb: [f64; 3]) -> u32 {
    argb_from_rgb(
        delinearized(linrgb[0]),
        delinearized(linrgb[1]),
        delinearized(linrgb[2]),
    )
}

pub(crate) fn red(argb: u32) -> u8 {
    ((argb >> 16) & 255) as u8
}

pub(crate) fn green(argb: u32) -> u8 {
    ((argb >> 8) & 255) as u8
}

pub(crate) fn blue(argb: u32) -> u8 {
    (argb & 255) as u8
}

pub(crate) fn hex_from_argb(argb: u32) -> String {
    format!("#{:02x}{:02x}{:02x}", red(argb), green(argb), blue(argb))
}

pub(crate) fn xyz_from_argb(argb: u32) -> [f64; 3] {
    let row = [
        linearized(red(argb) as f64),
        linearized(green(argb) as f64),
        linearized(blue(argb) as f64),
    ];
    matrix_multiply(row, SRGB_TO_XYZ)
}

pub(crate) fn lab_from_argb(argb: u32) -> [f64; 3] {
    let linear_r = linearized(red(argb) as f64);
    let linear_g = linearized(green(argb) as f64);
    let linear_b = linearized(blue(argb) as f64);
    let x =
        SRGB_TO_XYZ[0][0] * linear_r + SRGB_TO_XYZ[0][1] * linear_g + SRGB_TO_XYZ[0][2] * linear_b;
    let y =
        SRGB_TO_XYZ[1][0] * linear_r + SRGB_TO_XYZ[1][1] * linear_g + SRGB_TO_XYZ[1][2] * linear_b;
    let z =
        SRGB_TO_XYZ[2][0] * linear_r + SRGB_TO_XYZ[2][1] * linear_g + SRGB_TO_XYZ[2][2] * linear_b;
    let fx = lab_f(x / WHITE_POINT_D65[0]);
    let fy = lab_f(y / WHITE_POINT_D65[1]);
    let fz = lab_f(z / WHITE_POINT_D65[2]);
    [116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz)]
}

pub(crate) fn argb_from_lstar(lstar: f64) -> u32 {
    let component = delinearized(y_from_lstar(lstar));
    argb_from_rgb(component, component, component)
}

pub(crate) fn lstar_from_argb(argb: u32) -> f64 {
    let y = xyz_from_argb(argb)[1];
    116.0 * lab_f(y / 100.0) - 16.0
}

pub(crate) fn y_from_lstar(lstar: f64) -> f64 {
    100.0 * lab_invf((lstar + 16.0) / 116.0)
}

pub(crate) fn lstar_from_y(y: f64) -> f64 {
    lab_f(y / 100.0) * 116.0 - 16.0
}

pub(crate) fn linearized(rgb_component: f64) -> f64 {
    let normalized = rgb_component / 255.0;
    if normalized <= 0.040_449_936 {
        normalized / 12.92 * 100.0
    } else {
        ((normalized + 0.055) / 1.055).powf(2.4) * 100.0
    }
}

pub(crate) fn delinearized(rgb_component: f64) -> i32 {
    let normalized = rgb_component / 100.0;
    let delinearized = if normalized <= 0.003_130_8 {
        normalized * 12.92
    } else {
        1.055 * normalized.powf(1.0 / 2.4) - 0.055
    };
    clamp_int(0, 255, (delinearized * 255.0).round() as i32)
}

pub(crate) fn white_point_d65() -> [f64; 3] {
    WHITE_POINT_D65
}

fn lab_f(t: f64) -> f64 {
    let e = 216.0 / 24389.0;
    let kappa = 24389.0 / 27.0;
    if t > e {
        t.powf(1.0 / 3.0)
    } else {
        (kappa * t + 16.0) / 116.0
    }
}

fn lab_invf(ft: f64) -> f64 {
    let e = 216.0 / 24389.0;
    let kappa = 24389.0 / 27.0;
    let ft3 = ft * ft * ft;
    if ft3 > e {
        ft3
    } else {
        (116.0 * ft - 16.0) / kappa
    }
}

pub(crate) fn clamp_int(min: i32, max: i32, input: i32) -> i32 {
    input.clamp(min, max)
}

pub(crate) fn clamp_double(min: f64, max: f64, input: f64) -> f64 {
    input.clamp(min, max)
}

pub(crate) fn lerp(start: f64, stop: f64, amount: f64) -> f64 {
    (1.0 - amount) * start + amount * stop
}

/// JavaScript `Math.sign` is not this. The library returns 0 for both zeros.
pub(crate) fn signum(num: f64) -> f64 {
    if num < 0.0 {
        -1.0
    } else if num == 0.0 {
        0.0
    } else {
        1.0
    }
}

pub(crate) fn sanitize_degrees(degrees: f64) -> f64 {
    let mut degrees = degrees % 360.0;
    if degrees < 0.0 {
        degrees += 360.0;
    }
    degrees
}

pub(crate) fn matrix_multiply(row: [f64; 3], matrix: [[f64; 3]; 3]) -> [f64; 3] {
    [
        row[0] * matrix[0][0] + row[1] * matrix[0][1] + row[2] * matrix[0][2],
        row[0] * matrix[1][0] + row[1] * matrix[1][1] + row[2] * matrix[1][2],
        row[0] * matrix[2][0] + row[1] * matrix[2][1] + row[2] * matrix[2][2],
    ]
}
