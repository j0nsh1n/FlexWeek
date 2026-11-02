//! Dynamic schemes for the six Material palette styles.
//! Copyright 2022 Google LLC. Apache-2.0. See `NOTICE`.
//!
//! Tones follow `dynamiccolor/material_dynamic_colors.js` and `dynamic_color.js`
//! for the 30 roles the theme reads. Fixed roles are not among those 30.

#![allow(clippy::float_cmp)]

use super::color::{clamp_double, hex_from_argb, lerp, lstar_from_y, y_from_lstar};
use super::hct::{Hct, fix_if_disliked};
use super::temperature::complement;
use crate::{EngineError, EngineResult};

pub const ROLES: [&str; 30] = [
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

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Style {
    TonalSpot,
    Vibrant,
    Expressive,
    Fidelity,
    Neutral,
    Monochrome,
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum Role {
    Primary,
    OnPrimary,
    PrimaryContainer,
    OnPrimaryContainer,
    Secondary,
    OnSecondary,
    SecondaryContainer,
    OnSecondaryContainer,
    Tertiary,
    OnTertiary,
    TertiaryContainer,
    OnTertiaryContainer,
    Error,
    OnError,
    ErrorContainer,
    OnErrorContainer,
    Surface,
    OnSurface,
    OnSurfaceVariant,
    SurfaceContainerLowest,
    SurfaceContainerLow,
    SurfaceContainer,
    SurfaceContainerHigh,
    SurfaceContainerHighest,
    SurfaceVariant,
    Outline,
    OutlineVariant,
    InverseSurface,
    InverseOnSurface,
    InversePrimary,
    SurfaceDim,
    SurfaceBright,
}

const ORDER: [Role; 30] = [
    Role::Primary,
    Role::OnPrimary,
    Role::PrimaryContainer,
    Role::OnPrimaryContainer,
    Role::Secondary,
    Role::OnSecondary,
    Role::SecondaryContainer,
    Role::OnSecondaryContainer,
    Role::Tertiary,
    Role::OnTertiary,
    Role::TertiaryContainer,
    Role::OnTertiaryContainer,
    Role::Error,
    Role::OnError,
    Role::ErrorContainer,
    Role::OnErrorContainer,
    Role::Surface,
    Role::OnSurface,
    Role::OnSurfaceVariant,
    Role::SurfaceContainerLowest,
    Role::SurfaceContainerLow,
    Role::SurfaceContainer,
    Role::SurfaceContainerHigh,
    Role::SurfaceContainerHighest,
    Role::SurfaceVariant,
    Role::Outline,
    Role::OutlineVariant,
    Role::InverseSurface,
    Role::InverseOnSurface,
    Role::InversePrimary,
];

#[derive(Clone, Copy)]
struct Curve {
    low: f64,
    normal: f64,
    medium: f64,
    high: f64,
}

impl Curve {
    fn get(self, level: f64) -> f64 {
        if level <= -1.0 {
            self.low
        } else if level < 0.0 {
            lerp(self.low, self.normal, level + 1.0)
        } else if level < 0.5 {
            lerp(self.normal, self.medium, level / 0.5)
        } else if level < 1.0 {
            lerp(self.medium, self.high, (level - 0.5) / 0.5)
        } else {
            self.high
        }
    }
}

#[derive(Clone, Copy)]
struct Palette {
    hue: f64,
    chroma: f64,
}

impl Palette {
    fn at(self, tone: f64) -> Hct {
        Hct::from(self.hue, self.chroma, tone)
    }
}

struct Built {
    style: Style,
    dark: bool,
    contrast: f64,
    source: Hct,
    primary: Palette,
    secondary: Palette,
    tertiary: Palette,
    neutral: Palette,
    neutral_variant: Palette,
    error: Palette,
}

/// The 30 theme roles for one seed, style, mode and contrast, in `ROLES` order.
pub fn material_scheme(
    seed: &str,
    style: &str,
    dark: bool,
    contrast: f64,
) -> EngineResult<Vec<(&'static str, String)>> {
    let style = parse_style(style)?;
    if !contrast.is_finite() || !(-1.0..=1.0).contains(&contrast) {
        return Err(EngineError::value("contrast must be from -1 to 1"));
    }
    let source = Hct::from_argb(parse_seed(seed)?);
    let built = build(style, dark, contrast, source);
    Ok(ROLES
        .iter()
        .zip(ORDER)
        .map(|(name, role)| {
            let tone = get_tone(role, &built);
            let argb = palette_for(role, &built).at(tone).argb;
            (*name, hex_from_argb(argb))
        })
        .collect())
}

fn parse_style(style: &str) -> EngineResult<Style> {
    match style {
        "Tonal Spot" => Ok(Style::TonalSpot),
        "Vibrant" => Ok(Style::Vibrant),
        "Expressive" => Ok(Style::Expressive),
        "Fidelity" => Ok(Style::Fidelity),
        "Neutral" => Ok(Style::Neutral),
        "Monochrome" => Ok(Style::Monochrome),
        _ => Err(EngineError::value("unknown palette style")),
    }
}

fn parse_seed(seed: &str) -> EngineResult<u32> {
    let hex = seed.strip_prefix('#').unwrap_or(seed);
    let expanded;
    let digits: &str = if hex.len() == 3 {
        expanded = format!("{0}{0}{1}{1}{2}{2}", &hex[0..1], &hex[1..2], &hex[2..3]);
        &expanded
    } else {
        hex
    };
    let (red, green, blue) = match digits.len() {
        6 => (&digits[0..2], &digits[2..4], &digits[4..6]),
        8 => (&digits[2..4], &digits[4..6], &digits[6..8]),
        _ => return Err(EngineError::value("seed colour must be a hex colour")),
    };
    let channel = |text: &str| {
        u8::from_str_radix(text, 16)
            .map_err(|_| EngineError::value("seed colour must be a hex colour"))
    };
    Ok(0xff00_0000
        | (u32::from(channel(red)?) << 16)
        | (u32::from(channel(green)?) << 8)
        | u32::from(channel(blue)?))
}

fn build(style: Style, dark: bool, contrast: f64, source: Hct) -> Built {
    let hue = source.hue;
    let chroma = source.chroma;
    let (primary, secondary, tertiary, neutral, neutral_variant) = match style {
        Style::TonalSpot => (
            Palette { hue, chroma: 36.0 },
            Palette { hue, chroma: 16.0 },
            Palette {
                hue: super::color::sanitize_degrees(hue + 60.0),
                chroma: 24.0,
            },
            Palette { hue, chroma: 6.0 },
            Palette { hue, chroma: 8.0 },
        ),
        Style::Vibrant => (
            Palette { hue, chroma: 200.0 },
            Palette {
                hue: rotated(hue, VIBRANT_HUES, VIBRANT_SECONDARY),
                chroma: 24.0,
            },
            Palette {
                hue: rotated(hue, VIBRANT_HUES, VIBRANT_TERTIARY),
                chroma: 32.0,
            },
            Palette { hue, chroma: 10.0 },
            Palette { hue, chroma: 12.0 },
        ),
        Style::Expressive => (
            Palette {
                hue: super::color::sanitize_degrees(hue + 240.0),
                chroma: 40.0,
            },
            Palette {
                hue: rotated(hue, EXPRESSIVE_HUES, EXPRESSIVE_SECONDARY),
                chroma: 24.0,
            },
            Palette {
                hue: rotated(hue, EXPRESSIVE_HUES, EXPRESSIVE_TERTIARY),
                chroma: 32.0,
            },
            Palette {
                hue: hue + 15.0,
                chroma: 8.0,
            },
            Palette {
                hue: hue + 15.0,
                chroma: 12.0,
            },
        ),
        Style::Fidelity => {
            let fixed = fix_if_disliked(complement(source));
            let read = Hct::from_argb(fixed.argb);
            (
                Palette { hue, chroma },
                Palette {
                    hue,
                    chroma: (chroma - 32.0).max(chroma * 0.5),
                },
                Palette {
                    hue: read.hue,
                    chroma: read.chroma,
                },
                Palette {
                    hue,
                    chroma: chroma / 8.0,
                },
                Palette {
                    hue,
                    chroma: chroma / 8.0 + 4.0,
                },
            )
        }
        Style::Neutral => (
            Palette { hue, chroma: 12.0 },
            Palette { hue, chroma: 8.0 },
            Palette { hue, chroma: 16.0 },
            Palette { hue, chroma: 2.0 },
            Palette { hue, chroma: 2.0 },
        ),
        Style::Monochrome => (
            Palette { hue, chroma: 0.0 },
            Palette { hue, chroma: 0.0 },
            Palette { hue, chroma: 0.0 },
            Palette { hue, chroma: 0.0 },
            Palette { hue, chroma: 0.0 },
        ),
    };
    Built {
        style,
        dark,
        contrast,
        source,
        primary,
        secondary,
        tertiary,
        neutral,
        neutral_variant,
        error: Palette {
            hue: 25.0,
            chroma: 84.0,
        },
    }
}

const VIBRANT_HUES: [f64; 9] = [0.0, 41.0, 61.0, 101.0, 131.0, 181.0, 251.0, 301.0, 360.0];
const VIBRANT_SECONDARY: [f64; 9] = [18.0, 15.0, 10.0, 12.0, 15.0, 18.0, 15.0, 12.0, 12.0];
const VIBRANT_TERTIARY: [f64; 9] = [35.0, 30.0, 20.0, 25.0, 30.0, 35.0, 30.0, 25.0, 25.0];
const EXPRESSIVE_HUES: [f64; 9] = [0.0, 21.0, 51.0, 121.0, 151.0, 191.0, 271.0, 321.0, 360.0];
const EXPRESSIVE_SECONDARY: [f64; 9] = [45.0, 95.0, 45.0, 20.0, 45.0, 90.0, 45.0, 45.0, 45.0];
const EXPRESSIVE_TERTIARY: [f64; 9] = [120.0, 120.0, 20.0, 45.0, 20.0, 15.0, 20.0, 120.0, 120.0];

fn rotated(hue: f64, hues: [f64; 9], rotations: [f64; 9]) -> f64 {
    for index in 0..hues.len() - 1 {
        if hues[index] < hue && hue < hues[index + 1] {
            return super::color::sanitize_degrees(hue + rotations[index]);
        }
    }
    hue
}

fn palette_for(role: Role, scheme: &Built) -> Palette {
    match role {
        Role::Primary
        | Role::OnPrimary
        | Role::PrimaryContainer
        | Role::OnPrimaryContainer
        | Role::InversePrimary => scheme.primary,
        Role::Secondary
        | Role::OnSecondary
        | Role::SecondaryContainer
        | Role::OnSecondaryContainer => scheme.secondary,
        Role::Tertiary | Role::OnTertiary | Role::TertiaryContainer | Role::OnTertiaryContainer => {
            scheme.tertiary
        }
        Role::Error | Role::OnError | Role::ErrorContainer | Role::OnErrorContainer => scheme.error,
        Role::SurfaceVariant | Role::OnSurfaceVariant | Role::Outline | Role::OutlineVariant => {
            scheme.neutral_variant
        }
        _ => scheme.neutral,
    }
}

fn fidelity(scheme: &Built) -> bool {
    scheme.style == Style::Fidelity
}

fn monochrome(scheme: &Built) -> bool {
    scheme.style == Style::Monochrome
}

fn get_tone(role: Role, scheme: &Built) -> f64 {
    if let Some((nearer, farther)) = tone_pair(role) {
        return pair_tone(role, nearer, farther, scheme);
    }
    let mut answer = base_tone(role, scheme);
    let Some(background) = background(role, scheme) else {
        return answer;
    };
    let background_tone = get_tone(background, scheme);
    let desired = curve(role).get(scheme.contrast);
    if ratio_of_tones(background_tone, answer) < desired || scheme.contrast < 0.0 {
        answer = foreground_tone(background_tone, desired);
    }
    if is_background(role) && (50.0..60.0).contains(&answer) {
        answer = if ratio_of_tones(49.0, background_tone) >= desired {
            49.0
        } else {
            60.0
        };
    }
    answer
}

fn tone_pair(role: Role) -> Option<(Role, Role)> {
    match role {
        Role::Primary | Role::PrimaryContainer => Some((Role::PrimaryContainer, Role::Primary)),
        Role::Secondary | Role::SecondaryContainer => {
            Some((Role::SecondaryContainer, Role::Secondary))
        }
        Role::Tertiary | Role::TertiaryContainer => Some((Role::TertiaryContainer, Role::Tertiary)),
        Role::Error | Role::ErrorContainer => Some((Role::ErrorContainer, Role::Error)),
        _ => None,
    }
}

fn pair_tone(role: Role, nearer: Role, farther: Role, scheme: &Built) -> f64 {
    let delta = 10.0;
    let background_tone = get_tone(highest(scheme), scheme);
    let expansion = if scheme.dark { 1.0 } else { -1.0 };
    let nearer_ratio = curve(nearer).get(scheme.contrast);
    let farther_ratio = curve(farther).get(scheme.contrast);
    let nearer_initial = base_tone(nearer, scheme);
    let farther_initial = base_tone(farther, scheme);
    let mut nearer_tone = if ratio_of_tones(background_tone, nearer_initial) >= nearer_ratio {
        nearer_initial
    } else {
        foreground_tone(background_tone, nearer_ratio)
    };
    let mut farther_tone = if ratio_of_tones(background_tone, farther_initial) >= farther_ratio {
        farther_initial
    } else {
        foreground_tone(background_tone, farther_ratio)
    };
    if scheme.contrast < 0.0 {
        nearer_tone = foreground_tone(background_tone, nearer_ratio);
        farther_tone = foreground_tone(background_tone, farther_ratio);
    }
    if (farther_tone - nearer_tone) * expansion < delta {
        farther_tone = clamp_double(0.0, 100.0, nearer_tone + delta * expansion);
        if (farther_tone - nearer_tone) * expansion < delta {
            nearer_tone = clamp_double(0.0, 100.0, farther_tone - delta * expansion);
        }
    }
    if (50.0..60.0).contains(&nearer_tone) {
        if expansion > 0.0 {
            nearer_tone = 60.0;
            farther_tone = farther_tone.max(nearer_tone + delta * expansion);
        } else {
            nearer_tone = 49.0;
            farther_tone = farther_tone.min(nearer_tone + delta * expansion);
        }
    } else if (50.0..60.0).contains(&farther_tone) {
        farther_tone = if expansion > 0.0 { 60.0 } else { 49.0 };
    }
    if role == nearer {
        nearer_tone
    } else {
        farther_tone
    }
}

fn highest(scheme: &Built) -> Role {
    if scheme.dark {
        Role::SurfaceBright
    } else {
        Role::SurfaceDim
    }
}

fn background(role: Role, scheme: &Built) -> Option<Role> {
    match role {
        Role::OnPrimary => Some(Role::Primary),
        Role::OnPrimaryContainer => Some(Role::PrimaryContainer),
        Role::OnSecondary => Some(Role::Secondary),
        Role::OnSecondaryContainer => Some(Role::SecondaryContainer),
        Role::OnTertiary => Some(Role::Tertiary),
        Role::OnTertiaryContainer => Some(Role::TertiaryContainer),
        Role::OnError => Some(Role::Error),
        Role::OnErrorContainer => Some(Role::ErrorContainer),
        Role::OnSurface | Role::OnSurfaceVariant | Role::Outline | Role::OutlineVariant => {
            Some(highest(scheme))
        }
        Role::InverseOnSurface | Role::InversePrimary => Some(Role::InverseSurface),
        _ => None,
    }
}

fn is_background(role: Role) -> bool {
    matches!(
        role,
        Role::Primary
            | Role::PrimaryContainer
            | Role::Secondary
            | Role::SecondaryContainer
            | Role::Tertiary
            | Role::TertiaryContainer
            | Role::Error
            | Role::ErrorContainer
            | Role::Surface
            | Role::SurfaceDim
            | Role::SurfaceBright
            | Role::SurfaceContainerLowest
            | Role::SurfaceContainerLow
            | Role::SurfaceContainer
            | Role::SurfaceContainerHigh
            | Role::SurfaceContainerHighest
            | Role::SurfaceVariant
            | Role::InverseSurface
    )
}

fn curve(role: Role) -> Curve {
    let (low, normal, medium, high) = match role {
        Role::OnPrimary
        | Role::OnSecondary
        | Role::OnTertiary
        | Role::OnError
        | Role::OnSurface
        | Role::InverseOnSurface => (4.5, 7.0, 11.0, 21.0),
        Role::Primary | Role::Secondary | Role::Tertiary | Role::Error | Role::InversePrimary => {
            (3.0, 4.5, 7.0, 7.0)
        }
        Role::OnPrimaryContainer
        | Role::OnSecondaryContainer
        | Role::OnTertiaryContainer
        | Role::OnErrorContainer
        | Role::OnSurfaceVariant => (3.0, 4.5, 7.0, 11.0),
        Role::PrimaryContainer
        | Role::SecondaryContainer
        | Role::TertiaryContainer
        | Role::ErrorContainer
        | Role::OutlineVariant => (1.0, 1.0, 3.0, 4.5),
        Role::Outline => (1.5, 3.0, 4.5, 7.0),
        _ => (1.0, 1.0, 1.0, 1.0),
    };
    Curve {
        low,
        normal,
        medium,
        high,
    }
}

fn base_tone(role: Role, scheme: &Built) -> f64 {
    let dark = scheme.dark;
    match role {
        Role::Primary => {
            if monochrome(scheme) {
                if dark { 100.0 } else { 0.0 }
            } else if dark {
                80.0
            } else {
                40.0
            }
        }
        Role::OnPrimary => {
            if monochrome(scheme) {
                if dark { 10.0 } else { 90.0 }
            } else if dark {
                20.0
            } else {
                100.0
            }
        }
        Role::PrimaryContainer => {
            if fidelity(scheme) {
                scheme.source.tone
            } else if monochrome(scheme) {
                if dark { 85.0 } else { 25.0 }
            } else if dark {
                30.0
            } else {
                90.0
            }
        }
        Role::OnPrimaryContainer => {
            if fidelity(scheme) {
                foreground_tone(base_tone(Role::PrimaryContainer, scheme), 4.5)
            } else if monochrome(scheme) {
                if dark { 0.0 } else { 100.0 }
            } else if dark {
                90.0
            } else {
                30.0
            }
        }
        Role::Secondary => {
            if dark {
                80.0
            } else {
                40.0
            }
        }
        Role::OnSecondary => {
            if monochrome(scheme) {
                if dark { 10.0 } else { 100.0 }
            } else if dark {
                20.0
            } else {
                100.0
            }
        }
        Role::SecondaryContainer => secondary_container_tone(scheme),
        Role::OnSecondaryContainer => {
            if monochrome(scheme) {
                if dark { 90.0 } else { 10.0 }
            } else if !fidelity(scheme) {
                if dark { 90.0 } else { 30.0 }
            } else {
                foreground_tone(base_tone(Role::SecondaryContainer, scheme), 4.5)
            }
        }
        Role::Tertiary => {
            if monochrome(scheme) {
                if dark { 90.0 } else { 25.0 }
            } else if dark {
                80.0
            } else {
                40.0
            }
        }
        Role::OnTertiary => {
            if monochrome(scheme) {
                if dark { 10.0 } else { 90.0 }
            } else if dark {
                20.0
            } else {
                100.0
            }
        }
        Role::TertiaryContainer => tertiary_container_tone(scheme),
        Role::OnTertiaryContainer => {
            if monochrome(scheme) {
                if dark { 0.0 } else { 100.0 }
            } else if !fidelity(scheme) {
                if dark { 90.0 } else { 30.0 }
            } else {
                foreground_tone(base_tone(Role::TertiaryContainer, scheme), 4.5)
            }
        }
        Role::Error => {
            if dark {
                80.0
            } else {
                40.0
            }
        }
        Role::OnError => {
            if dark {
                20.0
            } else {
                100.0
            }
        }
        Role::ErrorContainer => {
            if dark {
                30.0
            } else {
                90.0
            }
        }
        Role::OnErrorContainer => {
            if monochrome(scheme) {
                if dark { 90.0 } else { 10.0 }
            } else if dark {
                90.0
            } else {
                30.0
            }
        }
        Role::Surface | Role::SurfaceDim if dark => 6.0,
        Role::Surface => 98.0,
        Role::SurfaceDim => Curve {
            low: 87.0,
            normal: 87.0,
            medium: 80.0,
            high: 75.0,
        }
        .get(scheme.contrast),
        Role::SurfaceBright if dark => Curve {
            low: 24.0,
            normal: 24.0,
            medium: 29.0,
            high: 34.0,
        }
        .get(scheme.contrast),
        Role::SurfaceBright => 98.0,
        Role::SurfaceContainerLowest if dark => Curve {
            low: 4.0,
            normal: 4.0,
            medium: 2.0,
            high: 0.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainerLowest => 100.0,
        Role::SurfaceContainerLow if dark => Curve {
            low: 10.0,
            normal: 10.0,
            medium: 11.0,
            high: 12.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainerLow => Curve {
            low: 96.0,
            normal: 96.0,
            medium: 96.0,
            high: 95.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainer if dark => Curve {
            low: 12.0,
            normal: 12.0,
            medium: 16.0,
            high: 20.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainer => Curve {
            low: 94.0,
            normal: 94.0,
            medium: 92.0,
            high: 90.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainerHigh if dark => Curve {
            low: 17.0,
            normal: 17.0,
            medium: 21.0,
            high: 25.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainerHigh => Curve {
            low: 92.0,
            normal: 92.0,
            medium: 88.0,
            high: 85.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainerHighest if dark => Curve {
            low: 22.0,
            normal: 22.0,
            medium: 26.0,
            high: 30.0,
        }
        .get(scheme.contrast),
        Role::SurfaceContainerHighest => Curve {
            low: 90.0,
            normal: 90.0,
            medium: 84.0,
            high: 80.0,
        }
        .get(scheme.contrast),
        Role::OnSurface => {
            if dark {
                90.0
            } else {
                10.0
            }
        }
        Role::SurfaceVariant => {
            if dark {
                30.0
            } else {
                90.0
            }
        }
        Role::OnSurfaceVariant => {
            if dark {
                80.0
            } else {
                30.0
            }
        }
        Role::InverseSurface => {
            if dark {
                90.0
            } else {
                20.0
            }
        }
        Role::InverseOnSurface => {
            if dark {
                20.0
            } else {
                95.0
            }
        }
        Role::Outline => {
            if dark {
                60.0
            } else {
                50.0
            }
        }
        Role::OutlineVariant => {
            if dark {
                30.0
            } else {
                80.0
            }
        }
        Role::InversePrimary => {
            if dark {
                40.0
            } else {
                80.0
            }
        }
    }
}

fn secondary_container_tone(scheme: &Built) -> f64 {
    let initial = if scheme.dark { 30.0 } else { 90.0 };
    if monochrome(scheme) {
        if scheme.dark { 30.0 } else { 85.0 }
    } else if !fidelity(scheme) {
        initial
    } else {
        find_desired_chroma(
            scheme.secondary.hue,
            scheme.secondary.chroma,
            initial,
            !scheme.dark,
        )
    }
}

fn tertiary_container_tone(scheme: &Built) -> f64 {
    if monochrome(scheme) {
        return if scheme.dark { 60.0 } else { 49.0 };
    }
    if !fidelity(scheme) {
        return if scheme.dark { 30.0 } else { 90.0 };
    }
    let proposed = scheme.tertiary.at(scheme.source.tone);
    fix_if_disliked(proposed).tone
}

fn find_desired_chroma(hue: f64, chroma: f64, tone: f64, by_decreasing: bool) -> f64 {
    let mut answer = tone;
    let mut closest = Hct::from(hue, chroma, tone);
    if closest.chroma >= chroma {
        return answer;
    }
    let mut peak = closest.chroma;
    while closest.chroma < chroma {
        answer += if by_decreasing { -1.0 } else { 1.0 };
        let potential = Hct::from(hue, chroma, answer);
        if peak > potential.chroma || (potential.chroma - chroma).abs() < 0.4 {
            break;
        }
        if (potential.chroma - chroma).abs() < (closest.chroma - chroma).abs() {
            closest = potential;
        }
        peak = peak.max(potential.chroma);
    }
    answer
}

fn ratio_of_ys(y1: f64, y2: f64) -> f64 {
    let lighter = if y1 > y2 { y1 } else { y2 };
    let darker = if lighter == y2 { y1 } else { y2 };
    (lighter + 5.0) / (darker + 5.0)
}

fn ratio_of_tones(tone_a: f64, tone_b: f64) -> f64 {
    ratio_of_ys(
        y_from_lstar(tone_a.clamp(0.0, 100.0)),
        y_from_lstar(tone_b.clamp(0.0, 100.0)),
    )
}

fn lighter(tone: f64, ratio: f64) -> f64 {
    if !(0.0..=100.0).contains(&tone) {
        return -1.0;
    }
    let dark_y = y_from_lstar(tone);
    let light_y = ratio * (dark_y + 5.0) - 5.0;
    let real = ratio_of_ys(light_y, dark_y);
    if real < ratio && (real - ratio).abs() > 0.04 {
        return -1.0;
    }
    let value = lstar_from_y(light_y) + 0.4;
    if !(0.0..=100.0).contains(&value) {
        -1.0
    } else {
        value
    }
}

fn darker(tone: f64, ratio: f64) -> f64 {
    if !(0.0..=100.0).contains(&tone) {
        return -1.0;
    }
    let light_y = y_from_lstar(tone);
    let dark_y = ((light_y + 5.0) / ratio) - 5.0;
    let real = ratio_of_ys(light_y, dark_y);
    if real < ratio && (real - ratio).abs() > 0.04 {
        return -1.0;
    }
    let value = lstar_from_y(dark_y) - 0.4;
    if !(0.0..=100.0).contains(&value) {
        -1.0
    } else {
        value
    }
}

fn lighter_unsafe(tone: f64, ratio: f64) -> f64 {
    let safe = lighter(tone, ratio);
    if safe < 0.0 { 100.0 } else { safe }
}

fn darker_unsafe(tone: f64, ratio: f64) -> f64 {
    let safe = darker(tone, ratio);
    if safe < 0.0 { 0.0 } else { safe }
}

fn prefers_light_foreground(tone: f64) -> bool {
    tone.round() < 60.0
}

fn foreground_tone(background: f64, ratio: f64) -> f64 {
    let lighter_tone = lighter_unsafe(background, ratio);
    let darker_tone = darker_unsafe(background, ratio);
    let lighter_ratio = ratio_of_tones(lighter_tone, background);
    let darker_ratio = ratio_of_tones(darker_tone, background);
    if prefers_light_foreground(background) {
        let negligible = (lighter_ratio - darker_ratio).abs() < 0.1
            && lighter_ratio < ratio
            && darker_ratio < ratio;
        if lighter_ratio >= ratio || lighter_ratio >= darker_ratio || negligible {
            lighter_tone
        } else {
            darker_tone
        }
    } else if darker_ratio >= ratio || darker_ratio >= lighter_ratio {
        darker_tone
    } else {
        lighter_tone
    }
}
