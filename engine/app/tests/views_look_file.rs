//! Tests for `flexweek_app::views::look_file` (P5-T2).
//! Expected values come from the pre-port Python rules and pinning desktop tests,
//! never read back from the code under test.

use flexweek_app::views::look_file::{
    CLASSIC_DESIGN_LOOKS, CORNER_RANGE, DAY_DEFAULT, DAY_SIDE_DEFAULT, DAY_SIDE_RANGE,
    DEFAULT_CONTRAST, DEFAULT_MODE, DEFAULT_PRESET, HOUR_RANGE, INVALID_LOOK_DOCUMENT, LOOK_KIND,
    LOOK_VERSION, MAIN_DEFAULT, PAD_RANGE, SCALE_RANGE, SETTINGS_NAV_DEFAULT, SETTINGS_NAV_RANGE,
    SHADOW_RANGE, SURFACE_DEFAULT, SURFACES, advanced_default, advanced_overrides,
    design_looks_json, export_document, extract_kept_material, float_in, hex_color,
    import_document, int_in, layouts, layouts_json, merge_material_into_look_file, option_default,
    pack_material, read_advanced, read_day_side_width, read_font, read_letter_keys, read_look_tier,
    read_material_choice, read_saved_material, read_settings_nav_width, read_shortcuts,
    sanitize_layout, sanitize_surface,
};
use flexweek_engine::ErrorKind;
use serde_json::{Value, json};

#[test]
fn missing_or_unknown_material_choice_falls_back_to_slate_system_std_comfortable() {
    let blank = json!({
        "preset": "Slate",
        "mode": "system",
        "contrast": "std",
        "density": "comfortable",
    });
    assert_eq!(DEFAULT_PRESET, "Slate");
    assert_eq!(DEFAULT_MODE, "system");
    assert_eq!(DEFAULT_CONTRAST, "std");

    for raw in [
        Value::Null,
        json!({}),
        json!({"material": "nope"}),
        json!({"preset": "Sea"}),
        json!({"material": {"preset": "Mauve", "mode": "dim", "contrast": "max", "density": "roomy"}}),
        json!({"material": {"preset": 7, "mode": true, "contrast": "standard", "density": []}}),
    ] {
        assert_eq!(Value::Object(read_material_choice(&raw)), blank, "{raw}");
    }

    let chosen = read_material_choice(&json!({
        "material": {
            "preset": "Sea",
            "mode": "dark",
            "contrast": "high",
            "density": "compact",
        }
    }));
    assert_eq!(
        Value::Object(chosen),
        json!({
            "preset": "Sea",
            "mode": "dark",
            "contrast": "high",
            "density": "compact",
        })
    );

    // Valid and invalid fields are resolved independently.
    let mixed = read_material_choice(&json!({
        "material": {
            "preset": "Blue",
            "mode": "bogus",
            "contrast": "high",
            "density": 99,
        }
    }));
    assert_eq!(
        Value::Object(mixed),
        json!({
            "preset": "Blue",
            "mode": "system",
            "contrast": "high",
            "density": "comfortable",
        })
    );
}

#[test]
fn read_font_accepts_known_fonts_and_returns_empty_otherwise() {
    assert_eq!(read_font(&json!({"material": {"font": "sans"}})), "sans");
    assert_eq!(read_font(&json!({"material": {"font": "serif"}})), "serif");
    assert_eq!(read_font(&json!({"material": {"font": "mono"}})), "mono");
    for raw in [
        Value::Null,
        json!({}),
        json!({"material": {}}),
        json!({"material": {"font": ""}}),
        json!({"material": {"font": "comic"}}),
        json!({"material": {"font": 1}}),
        json!({"material": {"font": true}}),
    ] {
        assert_eq!(read_font(&raw), "", "{raw}");
    }
}

#[test]
fn advanced_default_has_the_exact_initial_dials() {
    assert_eq!(
        Value::Object(advanced_default()),
        json!({
            "corner": null,
            "hour": null,
            "padding": null,
            "rail": true,
            "scale": 1.0,
            "motion": "Normal",
            "shadow": null,
            "block": "Edge",
            "lines": "Faint",
            "today": true,
            "times": true,
            "lengths": false,
            "now": null,
            "cat": {
                "school": null,
                "sports": null,
                "study": null,
                "homework": null,
            }
        })
    );
}

#[test]
fn hex_color_accepts_six_hex_digits_lowercased_and_refuses_bad_strings() {
    assert_eq!(hex_color(&json!("#AA22bb")), Some("#aa22bb".to_string()));
    assert_eq!(hex_color(&json!("#000000")), Some("#000000".to_string()));
    assert_eq!(hex_color(&json!("#FfFfFf")), Some("#ffffff".to_string()));
    for bad in [
        Value::Null,
        json!(123456),
        json!(true),
        json!("#12"),
        json!("#12345"),
        json!("#1234567"),
        json!("123456"),
        json!("#gggggg"),
        json!("# 12345"),
        json!("#+12345"),
        json!("#0x1234"),
    ] {
        assert_eq!(hex_color(&bad), None, "{bad}");
    }
}

#[test]
fn int_in_enforces_inclusive_bounds_and_rejects_bools_and_floats() {
    assert_eq!(int_in(&json!(0), 0, 28), Some(0));
    assert_eq!(int_in(&json!(28), 0, 28), Some(28));
    assert_eq!(int_in(&json!(14), 0, 28), Some(14));
    assert_eq!(int_in(&json!(-1), 0, 28), None);
    assert_eq!(int_in(&json!(29), 0, 28), None);
    assert_eq!(int_in(&json!(true), 0, 28), None);
    assert_eq!(int_in(&json!(false), 0, 28), None);
    assert_eq!(int_in(&json!(14.0), 0, 28), None);
    assert_eq!(int_in(&json!(14.5), 0, 28), None);
    assert_eq!(int_in(&json!("14"), 0, 28), None);
    assert_eq!(int_in(&Value::Null, 0, 28), None);
}

#[test]
fn float_in_matches_python_rounding_inclusive_bounds_and_bool_rejection() {
    assert_eq!(float_in(&json!(0.85), 0.85, 1.8), Some(0.85));
    assert_eq!(float_in(&json!(1.8), 0.85, 1.8), Some(1.8));
    assert_eq!(float_in(&json!(1), 0.85, 1.8), Some(1.0));
    assert_eq!(float_in(&json!(1.2), 0.85, 1.8), Some(1.2));
    assert_eq!(float_in(&json!(0.849), 0.85, 1.8), Some(0.85));
    assert_eq!(float_in(&json!(1.804), 0.85, 1.8), Some(1.8));
    assert_eq!(float_in(&json!(0.84), 0.85, 1.8), None);
    assert_eq!(float_in(&json!(1.806), 0.85, 1.8), None);

    // Exact binary64 half-to-even ties (9/8 = 1.125 -> 1.12, 11/8 = 1.375 -> 1.38)
    // and exact decimal rounding matching Python round(x, 2):
    // 0.855 -> 0.85, 1.055 -> 1.05 (where naive (x * 100).round_ties_even() / 100 wrongly gives 0.86/1.06),
    // 1.005 -> 1.0, 1.255 -> 1.25, 1.155 -> 1.16.
    assert_eq!(float_in(&json!(1.125), 0.85, 1.8), Some(1.12));
    assert_eq!(float_in(&json!(1.375), 0.85, 1.8), Some(1.38));
    assert_eq!(float_in(&json!(1.625), 0.85, 1.8), Some(1.62));
    assert_eq!(float_in(&json!(0.855), 0.85, 1.8), Some(0.85));
    assert_eq!(float_in(&json!(1.055), 0.85, 1.8), Some(1.05));
    assert_eq!(float_in(&json!(1.005), 0.85, 1.8), Some(1.0));
    assert_eq!(float_in(&json!(1.255), 0.85, 1.8), Some(1.25));
    assert_eq!(float_in(&json!(1.155), 0.85, 1.8), Some(1.16));

    assert_eq!(float_in(&json!(true), 0.85, 1.8), None);
    assert_eq!(float_in(&json!(false), 0.0, 2.0), None);
    assert_eq!(float_in(&json!("1.2"), 0.85, 1.8), None);
    assert_eq!(float_in(&Value::Null, 0.85, 1.8), None);
}

#[test]
fn read_advanced_sanitizes_every_dial_and_ignores_out_of_range_or_bad_types() {
    assert_eq!(read_advanced(&Value::Null), advanced_default());
    assert_eq!(
        read_advanced(&json!({"material": {"advanced": "nope"}})),
        advanced_default()
    );

    let full = read_advanced(&json!({
        "material": {
            "advanced": {
                "corner": CORNER_RANGE.1,
                "hour": HOUR_RANGE.0,
                "padding": PAD_RANGE.1,
                "rail": false,
                "scale": SCALE_RANGE.1,
                "motion": "Faster",
                "shadow": SHADOW_RANGE.1,
                "block": "Outline",
                "lines": "Clear",
                "today": false,
                "times": false,
                "lengths": true,
                "now": "#AA2211",
                "cat": {
                    "school": "#112233",
                    "sports": "#445566",
                    "study": "#778899",
                    "homework": "#AABBCC",
                    "unknown": "#ffffff",
                }
            }
        }
    }));
    assert_eq!(
        Value::Object(full),
        json!({
            "corner": 28,
            "hour": 36,
            "padding": 24,
            "rail": false,
            "scale": 1.8,
            "motion": "Faster",
            "shadow": 3,
            "block": "Outline",
            "lines": "Clear",
            "today": false,
            "times": false,
            "lengths": true,
            "now": "#aa2211",
            "cat": {
                "school": "#112233",
                "sports": "#445566",
                "study": "#778899",
                "homework": "#aabbcc",
            }
        })
    );

    // Every invalid/out-of-range/wrong-typed value stays at its default.
    let bad = read_advanced(&json!({
        "material": {
            "advanced": {
                "corner": true,
                "hour": 91,
                "padding": 3,
                "rail": 0,
                "scale": true,
                "motion": "Warp",
                "shadow": 4,
                "block": "Solid",
                "lines": "Heavy",
                "today": "no",
                "times": 0,
                "lengths": 1,
                "now": "#123",
                "cat": {
                    "school": "red",
                    "sports": 123,
                }
            }
        }
    }));
    assert_eq!(bad, advanced_default());
}

#[test]
fn shortcuts_default_on_and_letter_keys_default_off() {
    assert!(read_shortcuts(&Value::Null));
    assert!(read_shortcuts(&json!({})));
    assert!(read_shortcuts(&json!({"material": {}})));
    assert!(read_shortcuts(&json!({"material": {"shortcuts": "false"}})));
    assert!(read_shortcuts(&json!({"material": {"shortcuts": 0}})));
    assert!(read_shortcuts(&json!({"material": {"shortcuts": true}})));
    assert!(!read_shortcuts(&json!({"material": {"shortcuts": false}})));

    assert!(!read_letter_keys(&Value::Null));
    assert!(!read_letter_keys(&json!({})));
    assert!(!read_letter_keys(&json!({"material": {}})));
    assert!(!read_letter_keys(&json!({"material": {"shortcuts": true}})));
    assert!(!read_letter_keys(&json!({"material": {"letters": "yes"}})));
    assert!(!read_letter_keys(&json!({"material": {"letters": 1}})));
    assert!(!read_letter_keys(
        &json!({"material": {"letters": false, "shortcuts": true}})
    ));
    assert!(read_letter_keys(&json!({"material": {"letters": true}})));
}

#[test]
fn read_saved_material_skips_broken_entries_and_sanitizes_valid_ones() {
    assert_eq!(read_saved_material(&Value::Null), Vec::<Value>::new());
    assert_eq!(
        read_saved_material(&json!({"material": {"saved": "nope"}})),
        Vec::<Value>::new()
    );

    let saved = read_saved_material(&json!({
        "material": {
            "saved": [
                "not a dict",
                {},
                {"name": "   "},
                {"name": 42},
                {
                    "name": "  Study look  ",
                    "preset": "Forest",
                    "mode": "dark",
                    "contrast": "high",
                    "density": "compact",
                    "advanced": {"block": "Outline", "hour": 70, "corner": 999},
                },
                {
                    "name": "Fallback look",
                    "preset": "Unknown",
                }
            ]
        }
    }));
    assert_eq!(saved.len(), 2);
    assert_eq!(saved[0]["name"], "Study look");
    assert_eq!(saved[0]["preset"], "Forest");
    assert_eq!(saved[0]["mode"], "dark");
    assert_eq!(saved[0]["contrast"], "high");
    assert_eq!(saved[0]["density"], "compact");
    assert_eq!(saved[0]["advanced"]["block"], "Outline");
    assert_eq!(saved[0]["advanced"]["hour"], 70);
    assert_eq!(saved[0]["advanced"]["corner"], Value::Null);

    assert_eq!(saved[1]["name"], "Fallback look");
    assert_eq!(saved[1]["preset"], "Slate");
    assert_eq!(saved[1]["mode"], "system");
    assert_eq!(saved[1]["contrast"], "std");
    assert_eq!(saved[1]["density"], "comfortable");
    assert_eq!(saved[1]["advanced"], Value::Object(advanced_default()));
}

#[test]
fn advanced_overrides_returns_only_dials_that_differ_from_defaults() {
    let default = Value::Object(advanced_default());
    assert!(advanced_overrides(&default).unwrap().is_empty());

    // Integer 1 matches Python's `1 == 1.0`, so it is not an override.
    assert!(
        advanced_overrides(&json!({"scale": 1, "cat": null}))
            .unwrap()
            .is_empty()
    );

    let changed = advanced_overrides(&json!({
        "corner": 0,
        "hour": null,
        "scale": 1.3,
        "block": "Filled",
        "rail": true,
        "cat": {
            "school": "#336699",
            "sports": null,
            "study": "",
            "ignored": "#ffffff",
        }
    }))
    .unwrap();
    assert_eq!(
        Value::Object(changed),
        json!({
            "corner": 0,
            "scale": 1.3,
            "block": "Filled",
            "cat": {"school": "#336699"},
        })
    );

    assert_eq!(
        advanced_overrides(&json!("not an object"))
            .unwrap_err()
            .kind,
        ErrorKind::Value
    );
}

#[test]
fn look_tier_and_panel_widths_match_bounds_and_defaults() {
    for tier in ["simple", "more", "all"] {
        assert_eq!(
            read_look_tier(&json!({"material": {"lookTier": tier}})),
            tier
        );
    }
    for raw in [
        Value::Null,
        json!({}),
        json!({"material": {"lookTier": "sideways"}}),
        json!({"material": {"lookTier": 1}}),
    ] {
        assert_eq!(read_look_tier(&raw), "", "{raw}");
    }

    assert_eq!(DAY_SIDE_DEFAULT, 312);
    assert_eq!(SETTINGS_NAV_DEFAULT, 220);

    let cases = [
        (Value::Null, DAY_SIDE_DEFAULT, SETTINGS_NAV_DEFAULT),
        (json!({}), DAY_SIDE_DEFAULT, SETTINGS_NAV_DEFAULT),
        (
            json!({"surface": "material", "material": {"preset": "Slate"}}),
            DAY_SIDE_DEFAULT,
            SETTINGS_NAV_DEFAULT,
        ),
        (
            json!({"material": {"daySideWidth": DAY_SIDE_RANGE.0, "settingsNavWidth": SETTINGS_NAV_RANGE.0}}),
            DAY_SIDE_RANGE.0,
            SETTINGS_NAV_RANGE.0,
        ),
        (
            json!({"material": {"daySideWidth": DAY_SIDE_RANGE.1, "settingsNavWidth": SETTINGS_NAV_RANGE.1}}),
            DAY_SIDE_RANGE.1,
            SETTINGS_NAV_RANGE.1,
        ),
        (
            json!({"material": {"daySideWidth": DAY_SIDE_RANGE.0 - 1, "settingsNavWidth": SETTINGS_NAV_RANGE.1 + 1}}),
            DAY_SIDE_DEFAULT,
            SETTINGS_NAV_DEFAULT,
        ),
        (
            json!({"material": {"daySideWidth": true, "settingsNavWidth": false}}),
            DAY_SIDE_DEFAULT,
            SETTINGS_NAV_DEFAULT,
        ),
        (
            json!({"material": {"daySideWidth": "340", "settingsNavWidth": 210.5}}),
            DAY_SIDE_DEFAULT,
            SETTINGS_NAV_DEFAULT,
        ),
        (
            json!({"material": {"daySideWidth": 300.0, "settingsNavWidth": 200.0}}),
            DAY_SIDE_DEFAULT,
            SETTINGS_NAV_DEFAULT,
        ),
    ];
    for (stored, expected_day, expected_nav) in cases {
        assert_eq!(read_day_side_width(&stored), expected_day, "{stored}");
        assert_eq!(read_settings_nav_width(&stored), expected_nav, "{stored}");
    }
}

#[test]
fn pack_material_preserves_valid_optional_fields_and_drops_invalid_ones() {
    let choice = Value::Object(read_material_choice(&Value::Null));
    let adv = Value::Object(advanced_default());

    let packed = pack_material(
        &choice,
        &adv,
        true,
        false,
        &json!([]),
        "serif",
        "more",
        &json!(360),
        &json!(260),
    )
    .unwrap();
    assert_eq!(packed["preset"], "Slate");
    assert_eq!(packed["mode"], "system");
    assert_eq!(packed["contrast"], "std");
    assert_eq!(packed["density"], "comfortable");
    assert_eq!(packed["shortcuts"], true);
    assert_eq!(packed["letters"], false);
    assert!(!packed.contains_key("saved"));
    assert_eq!(packed["font"], "serif");
    assert_eq!(packed["lookTier"], "more");
    assert_eq!(packed["daySideWidth"], 360);
    assert_eq!(packed["settingsNavWidth"], 260);

    let bad = pack_material(
        &choice,
        &adv,
        true,
        true,
        &json!([{"name": "Saved"}]),
        "comic",
        "sideways",
        &json!(10),
        &json!(9999),
    )
    .unwrap();
    assert_eq!(bad["saved"], json!([{"name": "Saved"}]));
    assert!(!bad.contains_key("font"));
    assert!(!bad.contains_key("lookTier"));
    assert!(!bad.contains_key("daySideWidth"));
    assert!(!bad.contains_key("settingsNavWidth"));

    // Bool widths are rejected just like _int_in.
    let bool_widths = pack_material(
        &choice,
        &adv,
        true,
        false,
        &json!([]),
        "",
        "",
        &json!(true),
        &json!(false),
    )
    .unwrap();
    assert!(!bool_widths.contains_key("daySideWidth"));
    assert!(!bool_widths.contains_key("settingsNavWidth"));

    let missing_key = pack_material(
        &json!({"preset": "Slate"}),
        &adv,
        true,
        false,
        &json!([]),
        "",
        "",
        &Value::Null,
        &Value::Null,
    )
    .unwrap_err();
    assert_eq!(missing_key.kind, ErrorKind::Key);
}

#[test]
fn merge_material_round_trip_preserves_unknown_and_legacy_keys_untouched_and_in_place() {
    let existing = r#"{
  "preset": "high-contrast",
  "saved_looks": [{"name": "Night study", "base": "paper", "extra_nested": {"flag": true}}],
  "layout": {"main": "classic", "day": "dial", "options": {"classic": {"look": "preset:paper"}}},
  "surface": "material",
  "material": {"preset": "Slate", "mode": "light"},
  "zoom": {"classic.week": 64},
  "updates": {"check": true, "last_ms": 1700000000000, "skip": "", "developer_builds": false},
  "rail": {"open": true},
  "cpu_drawing_version": "1.6.0",
  "unknown_future_top": {"nested_unknown": [1, "two", {"deep": 3}]}
}
"#;
    let new_material = json!({
        "preset": "Forest",
        "mode": "dark",
        "contrast": "high",
        "density": "compact",
        "shortcuts": true,
        "letters": false,
        "advanced": advanced_default(),
    });

    let written = merge_material_into_look_file(Some(existing), &new_material).unwrap();
    assert!(written.ends_with('\n'));

    let parsed: Value = serde_json::from_str(&written).unwrap();
    let map = parsed.as_object().unwrap();

    // Key order is preserved with "material" updated in place.
    let keys: Vec<&str> = map.keys().map(String::as_str).collect();
    assert_eq!(
        keys,
        vec![
            "preset",
            "saved_looks",
            "layout",
            "surface",
            "material",
            "zoom",
            "updates",
            "rail",
            "cpu_drawing_version",
            "unknown_future_top",
        ]
    );

    // Every legacy and unknown key (including nested objects) is untouched.
    assert_eq!(map["preset"], "high-contrast");
    assert_eq!(
        map["saved_looks"],
        json!([{"name": "Night study", "base": "paper", "extra_nested": {"flag": true}}])
    );
    assert_eq!(
        map["layout"],
        json!({"main": "classic", "day": "dial", "options": {"classic": {"look": "preset:paper"}}})
    );
    assert_eq!(map["surface"], "material");
    assert_eq!(map["zoom"], json!({"classic.week": 64}));
    assert_eq!(
        map["updates"],
        json!({"check": true, "last_ms": 1700000000000i64, "skip": "", "developer_builds": false})
    );
    assert_eq!(map["rail"], json!({"open": true}));
    assert_eq!(map["cpu_drawing_version"], "1.6.0");
    assert_eq!(
        map["unknown_future_top"],
        json!({"nested_unknown": [1, "two", {"deep": 3}]})
    );
    assert_eq!(map["material"], new_material);

    // extract_kept_material reads back the exact material object.
    assert_eq!(
        extract_kept_material(&written).map(Value::Object),
        Some(new_material.clone())
    );

    // Missing, corrupt, or non-object existing files still write cleanly.
    for bad in [None, Some("{not json"), Some("[1, 2]"), Some("null")] {
        let out = merge_material_into_look_file(bad, &new_material).unwrap();
        let obj: Value = serde_json::from_str(&out).unwrap();
        assert_eq!(obj, json!({"material": new_material}));
    }
    assert_eq!(extract_kept_material("{not json"), None);
    assert_eq!(extract_kept_material("[]"), None);
    assert_eq!(extract_kept_material(r#"{"material": "nope"}"#), None);
    assert_eq!(
        merge_material_into_look_file(None, &json!("nope"))
            .unwrap_err()
            .kind,
        ErrorKind::Value
    );
}

#[test]
fn export_and_import_document_round_trip_and_refuse_invalid_files() {
    let choice = json!({
        "preset": "Forest",
        "mode": "dark",
        "contrast": "std",
        "density": "compact",
    });
    let mut adv = advanced_default();
    adv.insert("corner".to_string(), json!(4));
    adv.insert("scale".to_string(), json!(1.2));
    adv.insert("block".to_string(), json!("Outline"));
    adv.insert("lines".to_string(), json!("Clear"));
    adv.insert("now".to_string(), json!("#aa2211"));

    let exported = export_document(&choice, &Value::Object(adv.clone())).unwrap();
    let parsed: Value = serde_json::from_str(&exported).unwrap();
    assert_eq!(parsed["kind"], LOOK_KIND);
    assert_eq!(parsed["version"], LOOK_VERSION);

    let (found, error) = import_document(&exported);
    assert_eq!(error, "");
    let found = found.unwrap();
    assert_eq!(found["choice"], choice);
    assert_eq!(found["advanced"], Value::Object(adv));

    for bad in [
        "{not json",
        "[]",
        r#"{"kind": "something else", "version": 1}"#,
        r#"{"kind": "FlexWeek material look", "version": 2}"#,
        r#"{"kind": "FlexWeek material look", "version": true}"#,
        r#"{"kind": "FlexWeek material look", "version": "1"}"#,
        r#"{"kind": "FlexWeek material look"}"#,
    ] {
        let (res, msg) = import_document(bad);
        assert!(res.is_none(), "{bad}");
        assert_eq!(msg, INVALID_LOOK_DOCUMENT, "{bad}");
    }

    // Valid header with unknown values sanitizes back to defaults.
    let (sanitized, err) = import_document(
        r#"{"kind": "FlexWeek material look", "version": 1, "preset": "Mauve", "advanced": {"corner": 999, "block": "Outline"}}"#,
    );
    assert_eq!(err, "");
    let sanitized = sanitized.unwrap();
    assert_eq!(sanitized["choice"]["preset"], "Slate");
    assert_eq!(sanitized["advanced"]["corner"], Value::Null);
    assert_eq!(sanitized["advanced"]["block"], "Outline");
}

#[test]
fn layout_registry_holds_todays_app_with_curated_looks_and_your_look_default() {
    assert_eq!(MAIN_DEFAULT, "classic");
    assert_eq!(DAY_DEFAULT, "dial");
    assert_eq!(SURFACES, ["material"]);
    assert_eq!(SURFACE_DEFAULT, "material");

    let specs = layouts();
    let plan_ids: Vec<&str> = specs
        .iter()
        .filter(|s| s.role == "plan")
        .map(|s| s.id)
        .collect();
    let day_ids: Vec<&str> = specs
        .iter()
        .filter(|s| s.role == "day")
        .map(|s| s.id)
        .collect();
    assert_eq!(plan_ids, vec!["classic"]);
    assert!(day_ids.is_empty());

    let classic = &specs[0];
    let look_opt = classic.options.iter().find(|o| o.key == "look").unwrap();
    let mut expected_values: Vec<&str> = CLASSIC_DESIGN_LOOKS.iter().map(|(v, _)| *v).collect();
    expected_values.push("your");
    assert_eq!(look_opt.values(), expected_values);
    assert_eq!(look_opt.default_value(), "your");
    assert_eq!(option_default("your", "pack:light-frost"), "your");
    assert_eq!(option_default("", "pack:light-frost"), "pack:light-frost");

    let looks_json = design_looks_json();
    assert_eq!(looks_json["classic"].as_array().unwrap().len(), 5);
    assert_eq!(layouts_json().len(), 1);
}

#[test]
fn missing_design_looks_keep_the_account_look() {
    let choice = sanitize_layout(&json!({"main": "classic", "options": {}}));
    assert_eq!(choice["options"], json!({}));
    for spec in layouts() {
        let look_opt = spec.options.iter().find(|o| o.key == "look").unwrap();
        assert_eq!(look_opt.default_value(), "your");
    }
}

#[test]
fn sanitize_layout_cleans_options_migrates_colour_and_drops_removed_designs() {
    let shipped = json!({"main": "classic", "day": "dial", "options": {}});

    // Valid choice kept; extra keys like surface stripped.
    let kept = sanitize_layout(&json!({
        "main": "classic",
        "day": "dial",
        "options": {"classic": {"look": "preset:paper"}},
        "surface": "material",
    }));
    assert_eq!(
        Value::Object(kept),
        json!({
            "main": "classic",
            "day": "dial",
            "options": {"classic": {"look": "preset:paper"}},
        })
    );

    // Unknown values, keys, and non-dict options dropped.
    let cleaned = sanitize_layout(&json!({
        "main": "classic",
        "day": "dial",
        "options": {
            "classic": {"look": "preset:nope", "strange": "value"},
            "timeline": "not a dict",
            "ghost": {"look": "your"},
        },
    }));
    assert_eq!(Value::Object(cleaned), shipped);

    // Removed designs fall back to classic.
    for design in ["timeline", "bento", "retro"] {
        let loaded = sanitize_layout(&json!({
            "main": design,
            "day": "dial",
            "options": {design: {"look": "your", "density": "compact"}},
        }));
        assert_eq!(Value::Object(loaded), shipped, "{design}");
    }

    // Bad roots and wrong roles fall back to shipped.
    for raw in [
        Value::Null,
        json!("bento"),
        json!([]),
        json!({"main": 7, "day": null, "options": "x"}),
        json!({"main": "one", "day": "bento"}),
    ] {
        assert_eq!(Value::Object(sanitize_layout(&raw)), shipped, "{raw}");
    }

    // Legacy colour migrates to "your" when look is absent, but does not override look.
    let migrated = sanitize_layout(&json!({
        "main": "classic",
        "options": {"classic": {"colour": "unknown"}},
    }));
    assert_eq!(migrated["options"]["classic"]["look"], "your");

    let explicit = sanitize_layout(&json!({
        "main": "classic",
        "options": {"classic": {"colour": "unknown", "look": "preset:paper"}},
    }));
    assert_eq!(explicit["options"]["classic"]["look"], "preset:paper");
}

#[test]
fn sanitize_surface_always_opens_material() {
    for raw in [
        json!({"surface": "widgets"}),
        json!({"preset": "paper", "layout": {"main": "timeline"}}),
        json!({}),
        Value::Null,
        json!({"surface": "nope"}),
        json!({"surface": 7}),
        json!({"surface": null}),
        json!({"surface": "material"}),
        json!("widgets"),
        json!({"layout": {"main": "classic", "surface": "widgets"}}),
    ] {
        assert_eq!(sanitize_surface(&raw), "material", "{raw}");
    }
}
