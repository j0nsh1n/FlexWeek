//! Alarms draft/ring view-models, Help/About/Update forms, and Manage account/Restore forms
//! (P5-S3). Expected values come from the product rules and the pinning desktop tests.

use std::sync::{Mutex, MutexGuard};

use flexweek_app::views::copy::{
    ABOUT_HERE, ABOUT_LINE, ACCOUNT_CODES_NOTE, ACCOUNT_DATA_NOTE, ACCOUNT_PASSWORD_NOTE,
    HELP_PLANNING_MATERIAL, HELP_SCREENS, READ_FAILED,
};
use flexweek_app::views::manage_info_alarms::{
    self, AlarmDraft, BAD_LINK, DATA_ACTIONS, DAY_EXPORT_FILENAME, FULL, MAX_ALARMS, NO_DAY,
    NO_LOCATION, NOT_SAVED, RESTORE_FIRST, RingState, SELECT_DAY_FIRST, WeekImportDecision,
};
use flexweek_engine::ErrorKind;
use flexweek_engine::desk::files::EXPORT_FORMAT;
use flexweek_engine::desk::weekmodel::set_clock_24h;
use serde_json::{Value, json};

const SPOTIFY_TRACK: &str = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT";

struct ClockGuard {
    _held: MutexGuard<'static, ()>,
}

fn clock_lock() -> ClockGuard {
    static CLOCK_LOCK: Mutex<()> = Mutex::new(());
    let held = CLOCK_LOCK
        .lock()
        .unwrap_or_else(std::sync::PoisonError::into_inner);
    set_clock_24h(true);
    ClockGuard { _held: held }
}

impl Drop for ClockGuard {
    fn drop(&mut self) {
        set_clock_24h(true);
    }
}

// --- Alarms -------------------------------------------------------------------------------------

#[test]
fn alarm_picker_tables_match_rules() {
    assert_eq!(MAX_ALARMS, 20);
    assert_eq!(NO_DAY, "Pick at least one day.");
    assert_eq!(BAD_LINK, "Use an https://open.spotify.com share link.");
    assert_eq!(FULL, "You can have up to 20 alarms.");
    assert_eq!(NOT_SAVED, "Couldn't save the alarm. Try again.");

    let sounds = manage_info_alarms::alarm_sounds();
    assert_eq!(
        sounds,
        vec![
            json!({"label": "Chime", "value": "chime"}),
            json!({"label": "Soft", "value": "soft"}),
            json!({"label": "Bright", "value": "bright"}),
            json!({"label": "Low", "value": "low"}),
            json!({"label": "Glass", "value": "glass"}),
            json!({"label": "Spotify link", "value": "spotify"}),
        ]
    );

    let hours_24 = manage_info_alarms::hours_24();
    assert_eq!(hours_24.len(), 24);
    assert_eq!(hours_24[0], json!({"label": "00", "value": 0}));
    assert_eq!(hours_24[7], json!({"label": "07", "value": 7}));
    assert_eq!(hours_24[16], json!({"label": "16", "value": 16}));
    assert_eq!(hours_24[23], json!({"label": "23", "value": 23}));

    let hours_12 = manage_info_alarms::hours_12();
    assert_eq!(hours_12.len(), 24);
    assert_eq!(hours_12[0], json!({"label": "12 AM", "value": 0}));
    assert_eq!(hours_12[7], json!({"label": "7 AM", "value": 7}));
    assert_eq!(hours_12[12], json!({"label": "12 PM", "value": 12}));
    assert_eq!(hours_12[16], json!({"label": "4 PM", "value": 16}));
    assert_eq!(hours_12[23], json!({"label": "11 PM", "value": 23}));

    let minutes = manage_info_alarms::minutes_list();
    assert_eq!(minutes.len(), 60);
    assert_eq!(minutes[0], json!({"label": "00", "value": 0}));
    assert_eq!(minutes[5], json!({"label": "05", "value": 5}));
    assert_eq!(minutes[59], json!({"label": "59", "value": 59}));
}

#[test]
fn alarm_rows_format_title_off_flag_spotify_label_and_clock() {
    let _clock = clock_lock();
    let alarms = vec![
        json!({
            "id": "a1",
            "name": "Wake up",
            "time": "06:45",
            "days": [0, 1, 2],
            "enabled": true,
            "sound": "chime",
        }),
        json!({
            "id": "a2",
            "name": "Practice",
            "time": "16:30",
            "days": [0, 1, 2, 3, 4],
            "enabled": false,
            "sound": "glass",
        }),
        json!({
            "id": "a3",
            "name": "Playlist",
            "time": "08:00",
            "days": [5, 6],
            "sound": "spotify",
        }),
        json!({
            "id": "a4",
            "name": "Fallback",
            "time": "07:00",
            "days": [],
        }),
    ];

    set_clock_24h(true);
    let rows_24 = manage_info_alarms::alarm_rows(&alarms).unwrap();
    assert_eq!(
        rows_24,
        vec![
            json!({
                "id": "a1",
                "title": "Wake up · Chime",
                "subtitle": "Rings at 06:45, Mon, Tue and Wed",
            }),
            json!({
                "id": "a2",
                "title": "Practice · Glass · off",
                "subtitle": "Rings at 16:30, Monday to Friday",
            }),
            json!({
                "id": "a3",
                "title": "Playlist · Spotify",
                "subtitle": "Rings at 08:00, Saturday and Sunday",
            }),
            json!({
                "id": "a4",
                "title": "Fallback · Chime",
                "subtitle": "Rings at 07:00, no days",
            }),
        ]
    );

    set_clock_24h(false);
    let rows_12 = manage_info_alarms::alarm_rows(&alarms[..2]).unwrap();
    assert_eq!(rows_12[0]["subtitle"], "Rings at 6:45 AM, Mon, Tue and Wed");
    assert_eq!(rows_12[1]["subtitle"], "Rings at 4:30 PM, Monday to Friday");
}

#[test]
fn alarm_draft_defaults_edit_dirty_bounds_and_candidate() {
    let mut draft = AlarmDraft::new(None, "unknown-sound", "fresh-uuid", false).unwrap();
    assert!(!draft.existing);
    assert_eq!(draft.id, "fresh-uuid");
    assert_eq!(draft.name, "");
    assert_eq!((draft.hour, draft.minute), (7, 0));
    assert_eq!(draft.days, vec![0, 1, 2, 3, 4]);
    assert!(draft.enabled);
    assert_eq!(draft.sound, "chime");
    assert_eq!(draft.link, "");
    assert!(!draft.dirty());

    let form = draft.form();
    assert_eq!(form["kind"], "alarm");
    assert_eq!(form["heading"], "New alarm");
    assert_eq!(form["canRemove"], false);
    assert_eq!(form["hours"][16]["label"], "4 PM");
    assert_eq!(form["days"].as_array().unwrap().len(), 7);
    assert_eq!(
        form["days"][0],
        json!({"label": "Mon", "full": "Monday", "on": true})
    );
    assert_eq!(
        form["days"][5],
        json!({"label": "Sat", "full": "Saturday", "on": false})
    );

    // Out-of-range numbers, unknown sounds, and out-of-range days are ignored.
    draft.error = "old error".to_string();
    draft.set_number("hour", 24);
    draft.set_number("hour", -1);
    draft.set_number("minute", 60);
    draft.set_text("sound", "bogus");
    assert_eq!(
        (draft.hour, draft.minute, draft.sound.as_str()),
        (7, 0, "chime")
    );
    assert_eq!(draft.error, "");
    assert!(!draft.dirty());

    draft.error = "keep on bad day".to_string();
    draft.toggle_day(7);
    draft.toggle_day(-1);
    assert_eq!(draft.error, "keep on bad day");
    assert_eq!(draft.days, vec![0, 1, 2, 3, 4]);

    // Blank name becomes "Alarm" in candidate.
    draft.set_text("name", "   ");
    assert!(draft.dirty());
    let made = draft.candidate().unwrap();
    assert_eq!(
        made,
        json!({
            "id": "fresh-uuid",
            "name": "Alarm",
            "time": "07:00",
            "days": [0, 1, 2, 3, 4],
            "enabled": true,
            "sound": "chime",
            "spotify_url": null,
        })
    );

    // Reverting name clears dirty.
    draft.set_text("name", "");
    assert!(!draft.dirty());
}

#[test]
fn alarm_draft_rejects_no_days_and_bad_spotify_link() {
    let mut draft = AlarmDraft::new(None, "glass", "u1", true).unwrap();
    assert_eq!(draft.sound, "glass");
    assert_eq!(draft.form()["hours"][16]["label"], "16");

    for day in 0..5 {
        draft.toggle_day(day);
    }
    assert!(draft.days.is_empty());
    assert!(draft.candidate().is_none());
    assert_eq!(draft.days_problem, NO_DAY);
    assert_eq!(draft.form()["daysProblem"], NO_DAY);

    draft.toggle_day(0);
    assert_eq!(draft.days, vec![0]);
    assert_eq!(draft.days_problem, "");

    draft.set_text("link", "https://example.org/song");
    assert!(draft.candidate().is_none());
    assert_eq!(draft.link_problem, BAD_LINK);

    draft.set_text("link", &format!("  {SPOTIFY_TRACK}  "));
    assert_eq!(draft.link_problem, "");
    draft.set_text("sound", "spotify");
    draft.set_text("name", "Wake up");
    draft.set_number("hour", 6);
    draft.set_number("minute", 45);
    draft.set_enabled(false);

    let made = draft.candidate().unwrap();
    assert_eq!(
        made,
        json!({
            "id": "u1",
            "name": "Wake up",
            "time": "06:45",
            "days": [0],
            "enabled": false,
            "sound": "spotify",
            "spotify_url": SPOTIFY_TRACK,
        })
    );
}

#[test]
fn alarm_draft_editing_existing_alarm_preserves_fields() {
    let existing = json!({
        "id": "a9",
        "name": "Wake up",
        "time": "06:45",
        "days": [2, 0, 1],
        "enabled": false,
        "sound": "low",
        "spotify_url": SPOTIFY_TRACK,
    });
    let draft = AlarmDraft::new(Some(&existing), "chime", "unused-id", false).unwrap();
    assert!(draft.existing);
    assert_eq!(draft.id, "a9");
    assert_eq!(draft.name, "Wake up");
    assert_eq!((draft.hour, draft.minute), (6, 45));
    assert_eq!(draft.days, vec![0, 1, 2]);
    assert!(!draft.enabled);
    assert_eq!(draft.sound, "low");
    assert_eq!(draft.link, SPOTIFY_TRACK);
    assert!(!draft.dirty());
    assert_eq!(draft.form()["heading"], "Edit alarm");
    assert_eq!(draft.form()["canRemove"], true);
}

#[test]
fn ring_form_and_ring_state_handle_alarm_block_and_spotify() {
    let _clock = clock_lock();
    set_clock_24h(false);

    let alarm = json!({"id": "a1", "name": "Practice", "time": "07:00", "sound": "glass"});
    let form = manage_info_alarms::ring_form(&alarm, "").unwrap();
    assert_eq!(
        form,
        json!({
            "title": "Practice",
            "detail": "7:00 AM · Alarm is ringing",
            "spotify": false,
            "playing": "",
            "snoozeLabel": "Snooze 5 minutes",
        })
    );

    let block_alarm = json!({"block": true, "time": "16:30"});
    let block_form = manage_info_alarms::ring_form(&block_alarm, SPOTIFY_TRACK).unwrap();
    assert_eq!(
        block_form,
        json!({
            "title": "Alarm",
            "detail": "4:30 PM · Starting now",
            "spotify": true,
            "playing": "",
            "snoozeLabel": "Snooze 5 minutes",
        })
    );

    let no_time = manage_info_alarms::ring_form(&json!({"name": "Now"}), "").unwrap();
    assert_eq!(no_time["detail"], " · Alarm is ringing");

    let mut ring = RingState::new();
    assert!(!ring.open);
    assert!(ring.show_playing("Song").is_none());
    assert!(!ring.finish());
    assert!(ring.spotify_url().is_none());

    ring.show_alarm(&alarm, SPOTIFY_TRACK).unwrap();
    assert!(ring.open);
    assert_eq!(ring.spotify_url(), Some(SPOTIFY_TRACK));
    let updated = ring.show_playing("Playing Song").unwrap();
    assert_eq!(updated["playing"], "Playing Song");
    assert!(ring.finish());
    assert!(!ring.open);
    assert_eq!(ring.form, json!({}));
    assert!(!ring.finish());
}

#[test]
fn with_alarm_replaces_in_place_or_appends() {
    let alarms = vec![
        json!({"id": "a1", "name": "First"}),
        json!({"id": "a2", "name": "Second"}),
    ];
    let replaced =
        manage_info_alarms::with_alarm(&alarms, &json!({"id": "a1", "name": "Edited"})).unwrap();
    assert_eq!(
        replaced,
        vec![
            json!({"id": "a1", "name": "Edited"}),
            json!({"id": "a2", "name": "Second"}),
        ]
    );
    let added =
        manage_info_alarms::with_alarm(&alarms, &json!({"id": "a3", "name": "Third"})).unwrap();
    assert_eq!(
        added,
        vec![
            json!({"id": "a1", "name": "First"}),
            json!({"id": "a2", "name": "Second"}),
            json!({"id": "a3", "name": "Third"}),
        ]
    );
    let err = manage_info_alarms::with_alarm(&alarms, &json!({"name": "NoId"})).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
}

// --- Info ---------------------------------------------------------------------------------------

#[test]
fn sign_out_help_about_and_update_forms_match_wording() {
    assert_eq!(
        manage_info_alarms::sign_out_question(),
        json!({
            "id": "sign-out",
            "title": "Sign out",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text", "default": true},
                {"id": "yes", "label": "Sign out", "kind": "danger"},
            ],
        })
    );

    let help = manage_info_alarms::help_form(true, false);
    assert_eq!(help["heading"], "Help");
    assert_eq!(help["planning"], HELP_PLANNING_MATERIAL);
    assert_eq!(
        help["screens"].as_array().unwrap().len(),
        HELP_SCREENS.len()
    );
    assert_eq!(
        help["screens"][0],
        json!({"name": HELP_SCREENS[0].0, "words": HELP_SCREENS[0].1})
    );
    let keys = help["keys"].as_array().unwrap();
    assert_eq!(keys[0]["spoken"], "1 to 5");
    assert_eq!(
        keys[0]["parts"],
        json!([
            {"text": "1", "cap": true},
            {"text": "to", "cap": false},
            {"text": "5", "cap": true},
        ])
    );
    assert!(!keys.iter().any(|row| row["spoken"] == "Ctrl+K"));
    assert!(!keys.iter().any(|row| row["spoken"] == "D W M"));

    let help_letters = manage_info_alarms::help_form(false, true);
    let letter_spoken: Vec<&str> = help_letters["keys"]
        .as_array()
        .unwrap()
        .iter()
        .map(|row| row["spoken"].as_str().unwrap())
        .collect();
    assert!(!letter_spoken.contains(&"1 to 5"));
    assert!(letter_spoken.contains(&"D W M"));
    assert!(letter_spoken.contains(&"Ctrl+Shift+F"));

    let about = manage_info_alarms::about_form(
        &json!({"mode": "local"}),
        "file:///app/assets/logo.png",
        "2.0.0",
    )
    .unwrap();
    assert_eq!(
        about,
        json!({
            "heading": "About FlexWeek",
            "logo": "file:///app/assets/logo.png",
            "version": "FlexWeek 2.0.0",
            "what": ABOUT_LINE,
            "where": ABOUT_HERE,
            "folder": true,
        })
    );

    let update = json!({
        "version": "1.5.0",
        "notes": "## What changed\n- Material 3 is the one look.\n- Fewer pop-ups.\n\nMore detail below.",
    });
    let state = json!({
        "status": "Downloading…",
        "problem": false,
        "busy": true,
        "progress": 0.25,
    });
    let form = manage_info_alarms::update_form(&update, "1.4.0", &state).unwrap();
    assert_eq!(
        form,
        json!({
            "heading": "FlexWeek 1.5.0 is ready",
            "version": "1.5.0",
            "current": "1.4.0",
            "detail": "You have 1.4.0. Updating keeps your account and your weeks.",
            "notes": "What changed\n•  Material 3 is the one look.\n•  Fewer pop-ups.\nMore detail below.",
            "status": "Downloading…",
            "problem": false,
            "busy": true,
            "progress": 0.25,
        })
    );
}

// --- Manage & Restore ---------------------------------------------------------------------------

#[test]
fn account_form_and_restore_form_match_wording() {
    assert_eq!(
        NO_LOCATION,
        "FlexWeek can't find where saved copies are stored."
    );
    assert_eq!(RESTORE_FIRST, "Choose a copy.");
    assert_eq!(DAY_EXPORT_FILENAME, "flexweek-day.json");
    assert_eq!(SELECT_DAY_FIRST, "Select a day first.");
    assert_eq!(DATA_ACTIONS.len(), 5);

    let form = manage_info_alarms::account_form(&json!({"username": "sam"}), &json!(8)).unwrap();
    assert_eq!(form["heading"], "Manage account");
    assert_eq!(
        form["info"],
        "Signed in as sam. Your week is saved on this computer, under this account."
    );
    assert_eq!(form["passwordNote"], ACCOUNT_PASSWORD_NOTE);
    assert_eq!(form["codesNote"], ACCOUNT_CODES_NOTE);
    assert_eq!(form["codesStatus"], "8 unused recovery codes remain.");
    assert_eq!(form["codesProblem"], false);
    assert_eq!(form["dataNote"], ACCOUNT_DATA_NOTE);
    assert_eq!(
        form["files"],
        json!([
            {"name": "exportAccount", "id": "export", "label": "Export backup file"},
            {"name": "importAccount", "id": "import", "label": "Import backup file"},
            {"name": "exportWeek", "id": "week", "label": "Export week"},
            {"name": "exportDay", "id": "day", "label": "Export day"},
            {"name": "importFile", "id": "import-week", "label": "Import week or day file"},
        ])
    );

    let zero = manage_info_alarms::account_form(&Value::Null, &json!(0)).unwrap();
    assert_eq!(zero["codesProblem"], true);
    assert_eq!(
        zero["codesStatus"],
        "No unused recovery codes remain. Replace them before signing out."
    );
    assert_eq!(
        zero["info"],
        "Signed in as . Your week is saved on this computer, under this account."
    );

    let points = vec![json!({
        "id": "p1",
        "label": "Before term 2",
        "created_at": "2026-11-01 09:00",
        "weeks_count": 1,
    })];
    let preview = json!({
        "id": "p1",
        "changes": {
            "weeks": {"added": [], "changed": ["2026-11-02"], "removed": []},
            "assignments": {"added": [], "changed": [], "removed": []},
        },
    });
    let restore = manage_info_alarms::restore_form(
        &points,
        &preview,
        &json!({"label": "Data on this computer"}),
        "p1",
        "Draft label",
        "Choose a copy.",
    )
    .unwrap();
    assert_eq!(
        restore,
        json!({
            "heading": "Saved copies",
            "where": "Data on this computer",
            "label": "Draft label",
            "points": [{
                "id": "p1",
                "title": "Before term 2",
                "detail": "2026-11-01 09:00 · 1 week",
                "text": "Before term 2 · 2026-11-01 09:00 · 1 week",
            }],
            "selected": "p1",
            "summary": "0 added, 1 changed, 0 removed.",
            "note": "Choose a copy.",
        })
    );

    // Mismatched preview id yields empty summary; missing storage yields NO_LOCATION.
    let unselected =
        manage_info_alarms::restore_form(&points, &preview, &Value::Null, "other", "", "").unwrap();
    assert_eq!(unselected["where"], NO_LOCATION);
    assert_eq!(unselected["summary"], "");
}

#[test]
fn manage_questions_and_account_action_helpers() {
    assert_eq!(
        manage_info_alarms::restore_question(),
        json!({
            "id": "restore-copy",
            "title": "Restore",
            "body": "Restore this copy? FlexWeek saves a copy of your current weeks and homework first.",
            "answers": [
                {"id": "not", "label": "Not now", "kind": "text", "default": true},
                {"id": "restore", "label": "Restore", "kind": "danger"},
            ],
        })
    );

    let delete = manage_info_alarms::delete_question("sam", &Value::Null).unwrap();
    assert_eq!(
        delete,
        json!({
            "id": "delete-account",
            "title": "Delete account",
            "body": "Delete the account sam? Every week, all your homework and your settings are removed from this computer. This can't be undone.",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text", "default": true},
                {"id": "delete", "label": "Delete sam", "kind": "danger"},
            ],
        })
    );

    let fallback_delete =
        manage_info_alarms::account_delete_question(&Value::Null, &Value::Null).unwrap();
    assert_eq!(
        fallback_delete["answers"][1]["label"],
        "Delete this account"
    );

    let empty_import = manage_info_alarms::import_question(&json!({})).unwrap();
    assert_eq!(empty_import["id"], "import-account");
    assert_eq!(empty_import["title"], "Import backup file?");
    assert_eq!(
        empty_import["body"],
        "From another account's backup: Nothing in it is different from your account.\nFlexWeek saves a copy of your current weeks and homework first, so you can go back."
    );
    assert_eq!(
        empty_import["answers"],
        json!([
            {"id": "stay", "label": "Cancel", "kind": "text", "default": true},
            {"id": "import", "label": "Import", "kind": "filled"},
        ])
    );

    let replace = manage_info_alarms::replace_week_question("Week of 2 – 8 Nov");
    assert_eq!(
        replace,
        json!({
            "id": "replace-week",
            "title": "Replace week",
            "body": "Replace everything in Week of 2 – 8 Nov with this file? Other weeks aren't changed. You can undo this.",
            "answers": [
                {"id": "stay", "label": "Cancel", "kind": "text", "default": true},
                {"id": "replace", "label": "Replace week", "kind": "danger"},
            ],
        })
    );

    assert_eq!(
        manage_info_alarms::week_export_filename("2026-11-02"),
        "flexweek-2026-11-02.json"
    );

    assert_eq!(
        manage_info_alarms::parse_backup_json(r#"{"username":"sam"}"#),
        Ok(json!({"username": "sam"}))
    );
    assert_eq!(
        manage_info_alarms::parse_backup_json("[1, 2]"),
        Err(READ_FAILED)
    );
    assert_eq!(
        manage_info_alarms::parse_backup_json("{bad"),
        Err(READ_FAILED)
    );

    // Week import decisions: error -> Error, week format with existing blocks -> AskReplace,
    // week format on empty week or day format -> Import.
    assert_eq!(
        manage_info_alarms::decide_week_import(
            &json!({"error": "bad file"}),
            true,
            "2026-11-02",
            "2026-11-03",
        )
        .unwrap(),
        WeekImportDecision::Error("bad file".to_string())
    );
    assert_eq!(
        manage_info_alarms::decide_week_import(
            &json!({"format": EXPORT_FORMAT}),
            false,
            "2026-11-02",
            "2026-11-03",
        )
        .unwrap(),
        WeekImportDecision::Import
    );
    assert_eq!(
        manage_info_alarms::decide_week_import(
            &json!({"format": "flexweek-day"}),
            true,
            "2026-11-02",
            "2026-11-03",
        )
        .unwrap(),
        WeekImportDecision::Import
    );
    let ask = manage_info_alarms::decide_week_import(
        &json!({"format": EXPORT_FORMAT}),
        true,
        "2026-11-02",
        "2026-11-03",
    )
    .unwrap();
    assert_eq!(
        ask,
        WeekImportDecision::AskReplace(manage_info_alarms::replace_week_question(
            "Week of 2 – 8 Nov"
        ))
    );
}

#[test]
fn wrong_shaped_inputs_return_errors() {
    let err = manage_info_alarms::about_form(&json!([]), "file:///x", "2.0.0").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Type);

    let err = manage_info_alarms::account_form(&json!("bad"), &json!(1)).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Type);

    let err = manage_info_alarms::ring_form(&json!(42), "").unwrap_err();
    assert_eq!(err.kind, ErrorKind::Attribute);

    let err = manage_info_alarms::update_form(&json!({}), "1.0.0", &json!({})).unwrap_err();
    assert_eq!(err.kind, ErrorKind::Key);
}
