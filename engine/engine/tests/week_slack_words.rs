//! The slack chip's words: homework due within 24 hours is never "Plenty of time", and an all-day
//! due counts as the end of that day. Rust twin of the slack tests of the Python week model.

use flexweek_engine::desk::weekmodel::live_slack_words;

#[test]
fn test_plenty_of_time_is_never_due_within_24_hours() {
    let now = Some("2026-11-05T19:00");
    assert_eq!(
        live_slack_words(Some("ok"), Some("2026-11-06T18:00"), now),
        "Tight"
    );
    assert_eq!(
        live_slack_words(Some("ok"), Some("2026-11-06T20:00"), now),
        "Plenty of time"
    );
    assert_eq!(
        live_slack_words(Some("ok"), Some("2026-11-06T19:00"), now),
        "Plenty of time"
    );
    assert_eq!(
        live_slack_words(Some("danger"), Some("2026-11-06T18:00"), now),
        "Cutting it close"
    );
    assert_eq!(
        live_slack_words(Some("ok"), Some("2026-11-06T18:00"), None),
        "Plenty of time"
    );
}

#[test]
fn test_an_all_day_due_is_tight_five_hours_before_the_end_of_that_day() {
    assert_eq!(
        live_slack_words(Some("ok"), Some("2026-11-06"), Some("2026-11-06T19:00")),
        "Tight"
    );
    assert_eq!(
        live_slack_words(
            Some("ok"),
            Some("2026-11-06T23:59"),
            Some("2026-11-06T00:00")
        ),
        "Plenty of time"
    );
}
