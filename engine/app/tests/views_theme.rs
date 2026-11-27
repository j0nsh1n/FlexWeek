//! Tests for `flexweek_app::views::theme` (P5-T1).
//! Expected hex values come from `desktop/native/material/tokens.json`, the B3A3 spec, and
//! pre-port Python rules, never read back from the code under test.

use flexweek_app::views::theme::{
    CONTRASTS, HIGH_CONTRAST_STROKE, INK_DARK, INK_LIGHT, MOTION_EASE_MS, MOTION_LEVELS, ONE_MODE,
    PRESETS, SIX_CLASSES, THEME_ROLES, accented, bar_for_category, category_paint, dress_theme,
    event_category, hour_row_px, look_motion, mode_of, motion_distance, motion_duration,
    motion_level, motion_moves, pack_axis, paint_for_category, read_accent, reading_problems,
    resolved_mode, scheme, scheme_key, scheme_source_key, shown_font, stroke_for, theme_object,
};
use flexweek_engine::ErrorKind;
use flexweek_engine::desk::tokens::{contrast, luminance};
use serde_json::{Value, json};

fn str_field<'a>(map: &'a serde_json::Map<String, Value>, key: &str) -> &'a str {
    map.get(key)
        .and_then(Value::as_str)
        .unwrap_or_else(|| panic!("missing string field {key:?}"))
}

#[test]
fn scheme_key_joins_preset_mode_and_contrast() {
    assert_eq!(scheme_key("Slate", "light", "std"), "Slate.light.std");
    assert_eq!(
        scheme_key("High contrast", "dark", "high"),
        "High contrast.dark.high"
    );
}

#[test]
fn a_one_mode_preset_reads_its_own_mode_and_an_unknown_name_is_a_key_error() {
    assert_eq!(
        scheme_source_key("Slate", "dark", "high").unwrap(),
        "Slate.dark.high"
    );
    assert_eq!(
        scheme_source_key("Paper", "dark", "std").unwrap(),
        "Paper.light.std"
    );
    for (preset, mode, contrast_name) in [
        ("Nope", "light", "std"),
        ("Slate", "dim", "std"),
        ("Slate", "light", "max"),
    ] {
        let error = scheme_source_key(preset, mode, contrast_name).unwrap_err();
        assert_eq!(error.kind, ErrorKind::Key);
    }
}

#[test]
fn slate_and_b3a3_presets_match_exact_hex_strings_across_modes_and_contrasts() {
    let slate_light_std = scheme("Slate", "light", "std").unwrap();
    assert_eq!(str_field(&slate_light_std, "primary"), "#3d6fc4");
    assert_eq!(str_field(&slate_light_std, "onPrimary"), "#ffffff");
    assert_eq!(str_field(&slate_light_std, "secondaryContainer"), "#e6edf8");
    assert_eq!(
        str_field(&slate_light_std, "onSecondaryContainer"),
        "#0f172a"
    );
    assert_eq!(str_field(&slate_light_std, "surface"), "#eef1f5");
    assert_eq!(
        str_field(&slate_light_std, "surfaceContainerLowest"),
        "#ffffff"
    );
    assert_eq!(
        str_field(&slate_light_std, "surfaceContainerLow"),
        "#f6f8fc"
    );
    assert_eq!(str_field(&slate_light_std, "surfaceContainer"), "#edf0f7");
    assert_eq!(
        str_field(&slate_light_std, "surfaceContainerHigh"),
        "#e3e8f2"
    );
    assert_eq!(
        str_field(&slate_light_std, "surfaceContainerHighest"),
        "#d8dfec"
    );
    assert_eq!(str_field(&slate_light_std, "surfaceVariant"), "#e3e8f2");
    assert_eq!(str_field(&slate_light_std, "outlineVariant"), "#d4dce8");
    assert_eq!(str_field(&slate_light_std, "outline"), "#64748b");
    assert_eq!(str_field(&slate_light_std, "onSurface"), "#0f172a");
    assert_eq!(str_field(&slate_light_std, "onSurfaceVariant"), "#475569");
    assert_eq!(str_field(&slate_light_std, "inverseOnSurface"), "#f0f0f7");

    let slate_light_high = scheme("Slate", "light", "high").unwrap();
    assert_eq!(str_field(&slate_light_high, "onSurfaceVariant"), "#334155");
    assert_eq!(str_field(&slate_light_high, "primary"), "#3d6fc4");
    assert_eq!(str_field(&slate_light_high, "surface"), "#eef1f5");

    let slate_dark_std = scheme("Slate", "dark", "std").unwrap();
    assert_eq!(str_field(&slate_dark_std, "primary"), "#7fa8ff");
    assert_eq!(str_field(&slate_dark_std, "onPrimary"), "#0b1220");
    assert_eq!(str_field(&slate_dark_std, "secondaryContainer"), "#1c2433");
    assert_eq!(
        str_field(&slate_dark_std, "onSecondaryContainer"),
        "#ececec"
    );
    assert_eq!(str_field(&slate_dark_std, "surface"), "#0b0d10");
    assert_eq!(
        str_field(&slate_dark_std, "surfaceContainerLowest"),
        "#0e1116"
    );
    assert_eq!(str_field(&slate_dark_std, "surfaceContainerLow"), "#14171c");
    assert_eq!(str_field(&slate_dark_std, "surfaceContainer"), "#1b202a");
    assert_eq!(
        str_field(&slate_dark_std, "surfaceContainerHigh"),
        "#232936"
    );
    assert_eq!(
        str_field(&slate_dark_std, "surfaceContainerHighest"),
        "#2c3444"
    );
    assert_eq!(str_field(&slate_dark_std, "outlineVariant"), "#252a33");
    assert_eq!(str_field(&slate_dark_std, "outline"), "#6b7280");
    assert_eq!(str_field(&slate_dark_std, "onSurface"), "#ececec");
    assert_eq!(str_field(&slate_dark_std, "onSurfaceVariant"), "#9a9fa8");

    let slate_dark_high = scheme("Slate", "dark", "high").unwrap();
    assert_eq!(str_field(&slate_dark_high, "onSurfaceVariant"), "#c4c8d0");
    assert_eq!(str_field(&slate_dark_high, "primary"), "#7fa8ff");

    // Non-Slate presets keep their tokens.json primaries and use B3A3 neutrals.
    let blue_light_std = scheme("Blue", "light", "std").unwrap();
    assert_eq!(str_field(&blue_light_std, "primary"), "#425e91");
    assert_eq!(str_field(&blue_light_std, "surface"), "#eef1f5");
    assert_eq!(str_field(&blue_light_std, "onSurface"), "#0f172a");

    let blue_light_high = scheme("Blue", "light", "high").unwrap();
    assert_eq!(str_field(&blue_light_high, "primary"), "#052b5b");
    assert_eq!(str_field(&blue_light_high, "onSurfaceVariant"), "#334155");

    let blue_dark_std = scheme("Blue", "dark", "std").unwrap();
    assert_eq!(str_field(&blue_dark_std, "primary"), "#abc7ff");
    assert_eq!(str_field(&blue_dark_std, "surface"), "#0b0d10");

    let sea_light_std = scheme("Sea", "light", "std").unwrap();
    assert_eq!(str_field(&sea_light_std, "primary"), "#00696e");
    let sea_light_high = scheme("Sea", "light", "high").unwrap();
    assert_eq!(str_field(&sea_light_high, "primary"), "#003235");
}

#[test]
fn one_mode_presets_keep_their_own_surfaces_and_ignore_the_other_mode() {
    let hc = scheme("High contrast", "dark", "std").unwrap();
    assert_eq!(str_field(&hc, "primary"), "#ffd400");
    assert_eq!(str_field(&hc, "surface"), "#000000");
    assert_eq!(scheme("High contrast", "light", "std").unwrap(), hc);

    let hc_high = scheme("High contrast", "dark", "high").unwrap();
    assert_eq!(str_field(&hc_high, "onSurfaceVariant"), "#ffffff");

    let paper = scheme("Paper", "light", "std").unwrap();
    assert_eq!(str_field(&paper, "surface"), "#f7f0e1");
    assert_eq!(str_field(&paper, "primary"), "#1f3a68");
    assert_eq!(scheme("Paper", "dark", "std").unwrap(), paper);

    let ink = scheme("Ink", "dark", "std").unwrap();
    assert_eq!(str_field(&ink, "surface"), "#1c1b19");
    assert_eq!(scheme("Ink", "light", "std").unwrap(), ink);

    let terminal = scheme("Terminal", "dark", "std").unwrap();
    assert_eq!(str_field(&terminal, "surface"), "#0d1117");
    assert_eq!(scheme("Terminal", "light", "std").unwrap(), terminal);

    for (preset, mode) in ONE_MODE {
        let s = scheme(preset, mode, "std").unwrap();
        let dark = luminance(str_field(&s, "surface")).unwrap() < 0.18;
        assert_eq!(dark, mode == "dark", "{preset}");
    }
}

#[test]
fn unknown_preset_mode_or_contrast_returns_key_error() {
    let err = scheme("Mauve", "light", "std").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
    assert_eq!(err.message, "Mauve.light.std");

    let err = scheme("Blue", "dim", "std").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
    assert_eq!(err.message, "Blue.dim.std");

    let err = scheme("Blue", "light", "max").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
    assert_eq!(err.message, "Blue.light.max");
}

#[test]
fn stroke_for_and_category_paints_match_spec_hex_values() {
    assert_eq!(stroke_for("high").unwrap(), HIGH_CONTRAST_STROKE);
    assert_eq!(stroke_for("high").unwrap(), 1.5);
    assert_eq!(stroke_for("std").unwrap(), 0.0);
    assert_eq!(stroke_for("max").unwrap_err().kind, ErrorKind::Key);

    assert_eq!(bar_for_category("class"), "#3d6fc4");
    assert_eq!(bar_for_category("exercise"), "#2b9665");
    assert_eq!(bar_for_category("extra"), "#0f8a8a");
    assert_eq!(bar_for_category("assignments"), "#a87512");
    assert_eq!(bar_for_category("study"), "#c2557a");
    assert_eq!(bar_for_category("meals"), "#64748b");
    assert_eq!(bar_for_category("sleep"), "#64748b");
    assert_eq!(bar_for_category("free"), "#64748b");
    assert_eq!(bar_for_category("unknown"), "#64748b");

    assert_eq!(
        paint_for_category("class", "light").unwrap(),
        ("#e4ebf7".to_string(), INK_DARK)
    );
    assert_eq!(
        paint_for_category("class", "dark").unwrap(),
        ("#1e2c44".to_string(), INK_LIGHT)
    );
    assert_eq!(
        paint_for_category("exercise", "light").unwrap(),
        ("#e1f0e9".to_string(), INK_DARK)
    );
    assert_eq!(
        paint_for_category("exercise", "dark").unwrap(),
        ("#1a352e".to_string(), INK_LIGHT)
    );
    assert_eq!(
        paint_for_category("extra", "light").unwrap(),
        ("#ddefef".to_string(), INK_DARK)
    );
    assert_eq!(
        paint_for_category("extra", "dark").unwrap(),
        ("#133336".to_string(), INK_LIGHT)
    );
    assert_eq!(
        paint_for_category("assignments", "light").unwrap(),
        ("#f3ecde".to_string(), INK_DARK)
    );
    assert_eq!(
        paint_for_category("assignments", "dark").unwrap(),
        ("#382e1a".to_string(), INK_LIGHT)
    );
    assert_eq!(
        paint_for_category("study", "light").unwrap(),
        ("#f6e7ec".to_string(), INK_DARK)
    );
    assert_eq!(
        paint_for_category("study", "dark").unwrap(),
        ("#3e2633".to_string(), INK_LIGHT)
    );
    assert_eq!(
        paint_for_category("other", "light").unwrap(),
        ("#e9ecef".to_string(), INK_DARK)
    );
    assert_eq!(
        paint_for_category("other", "dark").unwrap(),
        ("#272d37".to_string(), INK_LIGHT)
    );
    assert_eq!(
        paint_for_category("class", "dim").unwrap_err().kind,
        ErrorKind::Key
    );

    assert_eq!(
        category_paint("school", "light").unwrap(),
        ("#e4ebf7".to_string(), INK_DARK)
    );
    assert_eq!(
        category_paint("soccer", "dark").unwrap(),
        ("#1a352e".to_string(), INK_LIGHT)
    );
    assert_eq!(
        category_paint("clubs", "light").unwrap(),
        ("#ddefef".to_string(), INK_DARK)
    );
    assert_eq!(
        category_paint("reading", "dark").unwrap(),
        ("#3e2633".to_string(), INK_LIGHT)
    );
    assert_eq!(
        category_paint("homework", "light").unwrap(),
        ("#f3ecde".to_string(), INK_DARK)
    );
    assert_eq!(
        category_paint("anything_else", "light").unwrap(),
        ("#e9ecef".to_string(), INK_DARK)
    );

    for cat in SIX_CLASSES {
        assert_eq!(event_category(cat), cat);
    }
    assert_eq!(event_category("meals"), "other");
    assert_eq!(event_category("meal"), "other");
    assert_eq!(event_category("sleep"), "other");
}

#[test]
fn mode_font_and_accent_resolution_follow_preset_and_student_precedence() {
    assert_eq!(resolved_mode("light", true), "light");
    assert_eq!(resolved_mode("dark", false), "dark");
    assert_eq!(resolved_mode("system", true), "dark");
    assert_eq!(resolved_mode("system", false), "light");

    assert_eq!(
        mode_of(&json!({"preset": "Slate", "mode": "system"}), true).unwrap(),
        "dark"
    );
    assert_eq!(
        mode_of(&json!({"preset": "Paper", "mode": "dark"}), true).unwrap(),
        "light"
    );
    assert_eq!(
        mode_of(&json!({"preset": "Terminal", "mode": "light"}), false).unwrap(),
        "dark"
    );
    assert_eq!(mode_of(&json!({}), false).unwrap_err().kind, ErrorKind::Key);
    assert_eq!(
        mode_of(&json!("bad"), false).unwrap_err().kind,
        ErrorKind::Value
    );

    assert_eq!(shown_font("Terminal", ""), "mono");
    assert_eq!(shown_font("Terminal", "sans"), "sans");
    assert_eq!(shown_font("Paper", ""), "serif");
    assert_eq!(shown_font("Ink", ""), "serif");
    assert_eq!(shown_font("High contrast", ""), "sans");
    assert_eq!(shown_font("Slate", ""), "sans");

    assert_eq!(read_accent(&json!({"accent": "sea"})), "sea");
    assert_eq!(read_accent(&json!({"accent": "neon"})), "default");
    assert_eq!(read_accent(&json!({"accent": 12})), "default");
    assert_eq!(read_accent(&Value::Null), "default");
}

#[test]
fn accented_replaces_primary_roles_and_respects_high_contrast_lock() {
    let slate_light = Value::Object(scheme("Slate", "light", "std").unwrap());
    let sky = accented(&slate_light, "sky", "Slate", "light", "std").unwrap();
    assert_eq!(str_field(&sky, "primary"), "#2d628b");
    assert_eq!(str_field(&sky, "onPrimary"), "#ffffff");
    assert_eq!(str_field(&sky, "primaryContainer"), "#cde5ff");
    assert_eq!(str_field(&sky, "onPrimaryContainer"), "#0a4a72");
    assert_eq!(str_field(&sky, "inversePrimary"), "#9acbfa");
    assert_eq!(str_field(&sky, "secondaryContainer"), "#ced9e6");
    assert_eq!(str_field(&sky, "onSecondaryContainer"), "#0f172a");

    let slate_dark = Value::Object(scheme("Slate", "dark", "std").unwrap());
    let gold = accented(&slate_dark, "gold", "Slate", "dark", "std").unwrap();
    assert_eq!(str_field(&gold, "primary"), "#fbba73");
    assert_eq!(str_field(&gold, "onPrimary"), "#492900");
    assert_eq!(str_field(&gold, "primaryContainer"), "#683d00");
    assert_eq!(str_field(&gold, "onPrimaryContainer"), "#ffdcbc");
    assert_eq!(str_field(&gold, "inversePrimary"), "#845416");
    assert_eq!(str_field(&gold, "secondaryContainer"), "#3f3936");
    assert_eq!(str_field(&gold, "onSecondaryContainer"), "#ececec");

    let blue_high = Value::Object(scheme("Blue", "light", "high").unwrap());
    let sea = accented(&blue_high, "sea", "Blue", "light", "high").unwrap();
    assert_eq!(str_field(&sea, "primary"), "#00322e");
    assert_eq!(str_field(&sea, "primaryContainer"), "#00534d");
    assert_eq!(str_field(&sea, "secondaryContainer"), "#c7d2d7");

    let paper = Value::Object(scheme("Paper", "light", "std").unwrap());
    let sand = accented(&paper, "sand", "Paper", "light", "std").unwrap();
    assert_eq!(str_field(&sand, "primary"), "#8e4d2f");
    assert_eq!(str_field(&sand, "secondaryContainer"), "#eadbcc");
    assert_eq!(str_field(&sand, "onSecondaryContainer"), "#1a1a1a");

    // Default or unknown accent leaves colours untouched.
    assert_eq!(
        Value::Object(accented(&slate_light, "default", "Slate", "light", "std").unwrap()),
        slate_light
    );
    assert_eq!(
        Value::Object(accented(&slate_light, "unknown", "Slate", "light", "std").unwrap()),
        slate_light
    );

    // High contrast keeps its yellow under every accent.
    let hc = Value::Object(scheme("High contrast", "dark", "std").unwrap());
    assert_eq!(
        Value::Object(accented(&hc, "sky", "High contrast", "dark", "std").unwrap()),
        hc
    );
}

#[test]
fn theme_object_builds_roles_ink_aliases_status_tints_and_classes() {
    let slate_light = scheme("Slate", "light", "std").unwrap();
    let theme = theme_object(
        &Value::Object(slate_light.clone()),
        "comfortable",
        false,
        false,
        false,
    )
    .unwrap();
    for role in THEME_ROLES {
        assert_eq!(theme.get(role), slate_light.get(role), "role {role}");
    }
    assert_eq!(str_field(&theme, "inkSurface"), "#0f172a");
    assert_eq!(str_field(&theme, "inkPrimary"), "#ffffff");
    assert_eq!(str_field(&theme, "inkMuted"), "#475569");
    assert!(!theme.contains_key("inkInverseSurface"));
    assert_eq!(str_field(&theme, "density"), "comfortable");
    assert_eq!(theme.get("reduceMotion"), Some(&Value::Bool(false)));
    assert_eq!(theme.get("highContrast"), Some(&Value::Bool(false)));
    assert_eq!(str_field(&theme, "page"), "#eef1f5");
    assert_eq!(str_field(&theme, "card"), "#ffffff");
    assert_eq!(str_field(&theme, "edge"), "#d4dce8");
    assert_eq!(str_field(&theme, "focusRing"), "#3d6fc4");
    assert_eq!(str_field(&theme, "statusDone"), "#276b3f");
    assert_eq!(str_field(&theme, "statusDoneTint"), "#dce7e0");
    assert_eq!(str_field(&theme, "statusDueSoon"), "#8a5a00");
    assert_eq!(str_field(&theme, "statusDueSoonTint"), "#ece5d6");
    assert_eq!(str_field(&theme, "statusOverdue"), "#b42318");
    assert_eq!(str_field(&theme, "statusOverdueTint"), "#f3dcda");
    assert_eq!(
        theme["classes"]["class"],
        json!({"bar": "#3d6fc4", "fill": "#e4ebf7", "ink": "#0f172a"})
    );

    let slate_dark = Value::Object(scheme("Slate", "dark", "std").unwrap());
    let dark = theme_object(&slate_dark, "compact", true, true, true).unwrap();
    assert_eq!(str_field(&dark, "page"), "#0b0d10");
    assert_eq!(str_field(&dark, "card"), "#14171c");
    assert_eq!(str_field(&dark, "edge"), "#252a33");
    assert_eq!(str_field(&dark, "focusRing"), "#7fa8ff");
    assert_eq!(str_field(&dark, "statusDoneTint"), "#283531");
    assert_eq!(str_field(&dark, "statusDueSoonTint"), "#37332a");
    assert_eq!(str_field(&dark, "statusOverdueTint"), "#3a2c2e");
    // chips_accent colours every category with the primary accent.
    for cat in SIX_CLASSES {
        assert_eq!(
            dark["classes"][cat],
            json!({"bar": "#7fa8ff", "fill": "#2e3a52", "ink": "#ececec"})
        );
    }
}

#[test]
fn hour_row_px_and_dress_theme_apply_overrides_and_preset_defaults() {
    let default_adv = json!({
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
        "cat": {"school": null, "sports": null, "study": null, "homework": null}
    });
    assert_eq!(hour_row_px("comfortable", &default_adv).unwrap(), 56);
    assert_eq!(hour_row_px("compact", &default_adv).unwrap(), 44);
    assert_eq!(hour_row_px("unknown", &default_adv).unwrap(), 56);
    assert_eq!(
        hour_row_px("comfortable", &json!({"hour": 70})).unwrap(),
        70
    );
    assert_eq!(
        hour_row_px("comfortable", &json!({"scale": 1.2})).unwrap(),
        67
    );
    assert_eq!(
        hour_row_px("comfortable", &json!({"scale": 0})).unwrap(),
        56
    );

    let base = Value::Object(
        theme_object(
            &Value::Object(scheme("Slate", "light", "std").unwrap()),
            "comfortable",
            false,
            false,
            false,
        )
        .unwrap(),
    );
    let plain = dress_theme(&base, &default_adv, "Slate", "").unwrap();
    assert_eq!(str_field(&plain, "fontFamily"), "Inter");
    assert_eq!(str_field(&plain, "headingFamily"), "Inter");
    assert!(!plain.contains_key("corner"));
    assert!(!plain.contains_key("typeScale"));
    assert!(!plain.contains_key("motionSpeed"));

    // Integer scale 1 equals default 1.0 in Python, so typeScale is not added.
    let int_scale = dress_theme(&base, &json!({"scale": 1}), "Slate", "").unwrap();
    assert!(!int_scale.contains_key("typeScale"));

    // Terminal defaults to mono font and sharp (0) corners until overridden.
    let terminal_default = dress_theme(&base, &default_adv, "Terminal", "").unwrap();
    assert_eq!(str_field(&terminal_default, "fontFamily"), "JetBrains Mono");
    assert_eq!(
        str_field(&terminal_default, "headingFamily"),
        "JetBrains Mono"
    );
    assert_eq!(terminal_default.get("corner"), Some(&json!(0)));

    let custom_adv = json!({
        "corner": 20,
        "padding": 16,
        "rail": false,
        "scale": 1.2,
        "motion": "Off",
        "shadow": 2,
        "block": "Outline",
        "lines": "Clear",
        "today": false,
        "times": false,
        "lengths": true,
        "now": "#aa2211",
        "cat": {"school": "#112233", "sports": null, "study": "#445566", "homework": null}
    });
    let dressed = dress_theme(&base, &custom_adv, "Terminal", "serif").unwrap();
    assert_eq!(str_field(&dressed, "fontFamily"), "Inter");
    assert_eq!(str_field(&dressed, "headingFamily"), "Newsreader");
    assert_eq!(dressed.get("corner"), Some(&json!(20)));
    assert_eq!(dressed.get("typeScale"), Some(&json!(1.2)));
    assert_eq!(dressed.get("shadow"), Some(&json!(2)));
    assert_eq!(dressed.get("blockStyle"), Some(&json!("Outline")));
    assert_eq!(dressed.get("hourLines"), Some(&json!("Clear")));
    assert_eq!(dressed.get("todayHighlight"), Some(&json!(false)));
    assert_eq!(dressed.get("showTimes"), Some(&json!(false)));
    assert_eq!(dressed.get("showLengths"), Some(&json!(true)));
    assert_eq!(dressed.get("railLabels"), Some(&json!(false)));
    assert_eq!(dressed.get("cardPad"), Some(&json!(16)));
    assert_eq!(dressed.get("nowLine"), Some(&json!("#aa2211")));
    assert_eq!(dressed.get("reduceMotion"), Some(&json!(true)));
    assert_eq!(dressed.get("motionSpeed"), Some(&json!("Off")));
    assert_eq!(dressed.get("catSchool"), Some(&json!("#112233")));
    assert_eq!(dressed.get("catStudy"), Some(&json!("#445566")));
    assert!(!dressed.contains_key("catSports"));
}

#[test]
fn reading_problems_reports_failing_categories_and_now_line_with_fixes() {
    let light_adv = json!({
        "cat": {"school": "#0f172a", "sports": "#e1f0e9", "study": null, "homework": null},
        "now": "#fafafa"
    });
    let light_problems = reading_problems("light", &light_adv).unwrap();
    assert_eq!(
        light_problems,
        vec![
            json!({
                "words": "school colour on its ink",
                "role": "school",
                "ink": "#0f172a",
                "ground": "#0f172a",
                "ratio": 1.0,
                "fixed": "#758098",
            }),
            json!({
                "words": "now line on the page",
                "role": "now",
                "ink": "#fafafa",
                "ground": "#ffffff",
                "ratio": 1.04,
                "fixed": "#959494",
            }),
        ]
    );
    assert!(contrast("#0f172a", "#758098").unwrap() >= 4.5);
    assert!(contrast("#959494", "#ffffff").unwrap() >= 3.0);

    let dark_adv = json!({
        "cat": {"school": "#ececec", "sports": null, "study": null, "homework": null},
        "now": "#202226"
    });
    let dark_problems = reading_problems("dark", &dark_adv).unwrap();
    assert_eq!(
        dark_problems,
        vec![
            json!({
                "words": "school colour on its ink",
                "role": "school",
                "ink": "#ececec",
                "ground": "#ececec",
                "ratio": 1.0,
                "fixed": "#6b6b6b",
            }),
            json!({
                "words": "now line on the page",
                "role": "now",
                "ink": "#202226",
                "ground": "#1a1c20",
                "ratio": 1.07,
                "fixed": "#64676b",
            }),
        ]
    );

    let clean = reading_problems(
        "light",
        &json!({"cat": {"school": "#e4ebf7"}, "now": "#111111"}),
    )
    .unwrap();
    assert!(clean.is_empty());
}

#[test]
fn motion_level_precedence_and_scaling() {
    assert_eq!(motion_level(Some("off"), Some("extra")), "off");
    assert_eq!(motion_level(None, Some("extra")), "extra");
    assert_eq!(motion_level(None, None), "normal");
    assert_eq!(motion_level(Some("fast"), Some("normal")), "normal");
    assert_eq!(motion_level(None, Some("reduce")), "reduce");
    assert_eq!(motion_level(Some("reduce"), Some("normal")), "reduce");

    assert_eq!(
        MOTION_LEVELS.map(|(name, _, _)| name),
        ["normal", "extra", "reduce", "off"]
    );
    assert_eq!(
        motion_duration(MOTION_EASE_MS, Some("normal"), "normal").unwrap(),
        220
    );
    assert_eq!(
        motion_duration(MOTION_EASE_MS, Some("extra"), "normal").unwrap(),
        550
    );
    assert_eq!(
        motion_duration(MOTION_EASE_MS, Some("reduce"), "normal").unwrap(),
        220
    );
    assert_eq!(
        motion_duration(MOTION_EASE_MS, Some("off"), "normal").unwrap(),
        0
    );
    assert_eq!(motion_duration(100, None, "extra").unwrap(), 250);
    assert_eq!(motion_duration(100, Some(""), "off").unwrap(), 0);
    assert_eq!(
        motion_duration(100, Some("bogus"), "normal")
            .unwrap_err()
            .kind,
        ErrorKind::Key
    );
}

#[test]
fn normal_runs_the_plans_numbers_and_the_other_levels_scale_them() {
    let sample_ms = [120, 160, 30, 200];
    let sample_px = [24, 8];
    for ms in sample_ms {
        assert_eq!(motion_duration(ms, Some("normal"), "normal").unwrap(), ms);
        assert_eq!(motion_duration(ms, Some("reduce"), "normal").unwrap(), ms);
        assert!(motion_duration(ms, Some("extra"), "normal").unwrap() > ms);
        assert_eq!(motion_duration(ms, Some("off"), "normal").unwrap(), 0);
    }
    for px in sample_px {
        assert_eq!(motion_distance(px, Some("normal"), "normal").unwrap(), px);
        assert_eq!(motion_distance(px, Some("reduce"), "normal").unwrap(), 0);
        assert_eq!(motion_distance(px, Some("off"), "normal").unwrap(), 0);
        assert!(motion_distance(px, Some("extra"), "normal").unwrap() > px);
    }
    assert_eq!(
        [
            motion_moves(Some("normal"), "normal").unwrap(),
            motion_moves(Some("extra"), "normal").unwrap(),
            motion_moves(Some("reduce"), "normal").unwrap(),
            motion_moves(Some("off"), "normal").unwrap(),
        ],
        [true, true, false, false]
    );
}

#[test]
fn pack_axis_maps_frost_and_named_packs() {
    assert_eq!(pack_axis(&json!("light-frost")), "slate");
    assert_eq!(pack_axis(&json!("slate")), "slate");
    assert_eq!(pack_axis(&json!("dark-frost")), "nocturne");
    assert_eq!(pack_axis(&json!("nocturne")), "nocturne");
    assert_eq!(pack_axis(&json!("system")), "system");
    assert_eq!(pack_axis(&json!("no-such-pack")), "system");
    assert_eq!(pack_axis(&Value::Null), "system");
}

#[test]
fn paper_starts_at_reduce_motion_and_every_other_look_at_normal() {
    assert_eq!(
        look_motion(&json!({"preset": "paper", "knobs": {}})),
        "reduce"
    );
    for preset in ["default", "ink", "terminal", "high-contrast"] {
        assert_eq!(
            look_motion(&json!({"preset": preset, "knobs": {}})),
            "normal",
            "{preset}"
        );
    }
    // Custom look's own motion wins; custom built on Paper without motion starts at Reduce.
    let custom_extra = json!({
        "preset": "default",
        "knobs": {},
        "custom": {"name": "Night study", "base": "paper", "motion": "extra"}
    });
    assert_eq!(look_motion(&custom_extra), "extra");

    let custom_paper = json!({
        "preset": "default",
        "knobs": {},
        "custom": {"name": "Night study", "base": "paper"}
    });
    assert_eq!(look_motion(&custom_paper), "reduce");

    let custom_ink = json!({
        "preset": "default",
        "knobs": {},
        "custom": {"name": "Night study", "base": "ink"}
    });
    assert_eq!(look_motion(&custom_ink), "normal");

    assert_eq!(look_motion(&Value::Null), "normal");
}

#[test]
fn every_preset_and_contrast_in_tokens_loads_with_all_thirty_roles() {
    for preset in PRESETS {
        for mode in ["light", "dark"] {
            for level in CONTRASTS {
                let found = scheme(preset, mode, level).unwrap();
                for role in THEME_ROLES {
                    assert!(
                        found.get(role).and_then(Value::as_str).is_some(),
                        "{preset}.{mode}.{level} missing {role}"
                    );
                }
            }
        }
    }
}
