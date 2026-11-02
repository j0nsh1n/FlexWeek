//! The six preset seeds must match every role in `tokens.json`. Those schemes
//! were written by @material/material-color-utilities, not by this port.

use std::collections::BTreeMap;
use std::path::PathBuf;

use flexweek_engine::material::{ROLES, material_scheme};

const PRESETS: &[(&str, &str, &str)] = &[
    ("Blue", "#0B62C4", "Tonal Spot"),
    ("Sea", "#00797F", "Tonal Spot"),
    ("Forest", "#3B7A4B", "Fidelity"),
    ("Gold", "#8A6A00", "Tonal Spot"),
    ("Rose", "#B4235A", "Vibrant"),
    ("Plum", "#6D4BC3", "Expressive"),
];

fn tokens() -> BTreeMap<String, BTreeMap<String, String>> {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../desktop/native/material/tokens.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|err| panic!("{path:?}: {err}"));
    serde_json::from_str(&text).expect("tokens.json")
}

#[test]
fn material_presets_match_the_reference_schemes() {
    let tokens = tokens();
    let mut mismatches = Vec::new();
    for (name, seed, style) in PRESETS {
        for (dark, mode) in [(false, "light"), (true, "dark")] {
            for (contrast, level) in [(0.0, "std"), (1.0, "high")] {
                let key = format!("{name}.{mode}.{level}");
                let expected = tokens.get(&key).unwrap_or_else(|| panic!("missing {key}"));
                let got = material_scheme(seed, style, dark, contrast).expect(&key);
                assert_eq!(got.len(), ROLES.len());
                for (role, colour) in got {
                    let want = expected.get(role).unwrap_or_else(|| panic!("{key} {role}"));
                    if colour != *want {
                        mismatches.push(format!("{key} {role}: got {colour}, want {want}"));
                    }
                }
            }
        }
    }
    assert!(
        mismatches.is_empty(),
        "{} mismatches\n{}",
        mismatches.len(),
        mismatches.join("\n")
    );
}

#[test]
fn a_bad_seed_is_refused() {
    let err = material_scheme("not-a-colour", "Tonal Spot", false, 0.0).unwrap_err();
    assert_eq!(err.message, "seed colour must be a hex colour");
}

#[test]
fn contrast_outside_the_scale_is_refused() {
    let err = material_scheme("#0B62C4", "Tonal Spot", false, 1.5).unwrap_err();
    assert_eq!(err.message, "contrast must be from -1 to 1");
    let err = material_scheme("#0B62C4", "Tonal Spot", false, f64::NAN).unwrap_err();
    assert_eq!(err.message, "contrast must be from -1 to 1");
}

#[test]
fn material_more_seeds_match_the_reference() {
    let path =
        PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/material-schemes.json");
    let text = std::fs::read_to_string(&path).unwrap_or_else(|err| panic!("{path:?}: {err}"));
    let tokens: BTreeMap<String, BTreeMap<String, String>> =
        serde_json::from_str(&text).expect("material-schemes.json");
    let seeds = [
        "#0B62C4", "#00797F", "#3B7A4B", "#8A6A00", "#B4235A", "#6D4BC3", "#E91E63", "#2E7D32",
        "#000000", "#FFFFFF",
    ];
    let styles = [
        "Tonal Spot",
        "Vibrant",
        "Expressive",
        "Fidelity",
        "Neutral",
        "Monochrome",
    ];
    let contrasts = [
        ("-1", -1.0),
        ("-0.5", -0.5),
        ("0", 0.0),
        ("0.75", 0.75),
        ("1", 1.0),
    ];
    let mut mismatches = Vec::new();
    for seed in seeds {
        for style in styles {
            for (dark, mode) in [(false, "light"), (true, "dark")] {
                for (label, contrast) in contrasts {
                    let key = format!("{seed}|{style}|{mode}|{label}");
                    let expected = tokens.get(&key).unwrap_or_else(|| panic!("missing {key}"));
                    let got = material_scheme(seed, style, dark, contrast).expect(&key);
                    for (role, colour) in got {
                        let want = expected.get(role).unwrap_or_else(|| panic!("{key} {role}"));
                        if colour != *want {
                            mismatches.push(format!("{key} {role}: got {colour}, want {want}"));
                        }
                    }
                }
            }
        }
    }
    assert!(
        mismatches.is_empty(),
        "{} mismatches\n{}",
        mismatches.len(),
        mismatches
            .iter()
            .take(40)
            .cloned()
            .collect::<Vec<_>>()
            .join("\n")
    );
}

#[test]
fn an_unknown_style_is_refused() {
    let err = material_scheme("#0B62C4", "Content", false, 0.0).unwrap_err();
    assert_eq!(err.message, "unknown palette style");
}
