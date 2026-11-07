//! fwtest pictures: comparing two drawings, choosing the touched screens, the review page, the
//! reviewer step and the clip plays. Expected values come from docs/tooling/fwtest.md, "Pictures",
//! and spec.md's Testing structure rule 6.

use std::fs;
use std::path::{Path, PathBuf};

use fwtest::pictures::compare::{self, Image, Options, Status};
use fwtest::pictures::index::{Label, Listed, Listing, Measurements};
use fwtest::pictures::{annotate, clips, page, select};
use serde_json::json;

fn scratch(name: &str) -> PathBuf {
    // Under target/, on disk: never /tmp, which is memory on the developer's machine.
    let path = Path::new(env!("CARGO_TARGET_TMPDIR"))
        .join(format!("pictures-{name}-{}", std::process::id()));
    let _ = fs::remove_dir_all(&path);
    fs::create_dir_all(&path).unwrap();
    path
}

fn plain(width: u32, height: u32, colour: [u8; 4]) -> Image {
    Image {
        width,
        height,
        rgba: colour.repeat((width * height) as usize),
    }
}

fn paint(image: &mut Image, x: u32, y: u32, w: u32, h: u32, colour: [u8; 4]) {
    for row in y..y + h {
        for col in x..x + w {
            let at = ((row * image.width + col) * 4) as usize;
            image.rgba[at..at + 4].copy_from_slice(&colour);
        }
    }
}

const WHITE: [u8; 4] = [255, 255, 255, 255];
const INK: [u8; 4] = [20, 30, 40, 255];

/// A folder as render.py writes it: index.json and the named PNGs.
fn drawing(folder: &Path, pictures: &[(&str, &str, Option<&Image>, Option<&str>)]) {
    fs::create_dir_all(folder).unwrap();
    let mut listed = Vec::new();
    for (screen, variant, image, error) in pictures {
        let relative = format!("{screen}/{variant}.png");
        if let Some(image) = image {
            compare::write_png(&folder.join(&relative), image).unwrap();
        }
        listed.push(json!({
            "screen": screen,
            "area": screen.split('.').next().unwrap(),
            "variant": variant,
            "checks": format!("check {screen}"),
            "sources": ["desktop/native/window.py"],
            "picture": image.map(|_| relative.clone()),
            "measurements": {"labels": [], "focus": {"focused": null, "ring": null}},
            "error": error,
        }));
    }
    let index = json!({"version": 1, "set": "touched", "commit": "abc", "problems": [], "pictures": listed});
    fs::write(folder.join("index.json"), index.to_string()).unwrap();
}

#[test]
fn the_same_picture_twice_is_unchanged_and_not_copied() {
    let root = scratch("same");
    let image = plain(20, 10, WHITE);
    drawing(
        &root.join("a"),
        &[("week.grid", "classic.light", Some(&image), None)],
    );
    drawing(
        &root.join("b"),
        &[("week.grid", "classic.light", Some(&image), None)],
    );
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    assert_eq!(report.entries.len(), 1);
    assert_eq!(report.entries[0].status, Status::Unchanged);
    assert_eq!(report.entries[0].differing, 0);
    assert!(report.entries[0].after.is_none());
    assert!(!root.join("out/after").exists());
    assert!(root.join("out/compare.json").is_file());
}

#[test]
fn a_moved_block_is_changed_and_its_difference_marks_exactly_those_pixels() {
    let root = scratch("changed");
    let before = plain(30, 20, WHITE);
    let mut after = before.clone();
    paint(&mut after, 5, 5, 4, 3, INK);
    drawing(
        &root.join("a"),
        &[("week.grid", "classic.light", Some(&before), None)],
    );
    drawing(
        &root.join("b"),
        &[("week.grid", "classic.light", Some(&after), None)],
    );
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    let entry = &report.entries[0];
    assert_eq!(entry.status, Status::Changed);
    assert_eq!((entry.differing, entry.total), (12, 600));
    let diff = compare::read_png(&root.join("out").join(entry.diff.as_ref().unwrap())).unwrap();
    let marked = diff
        .rgba
        .chunks_exact(4)
        .filter(|p| *p == [255, 0, 170, 255])
        .count();
    assert_eq!(marked, 12);
    assert_eq!(
        compare::read_png(&root.join("out").join(entry.after.as_ref().unwrap())).unwrap(),
        after
    );
    assert_eq!(
        compare::read_png(&root.join("out").join(entry.before.as_ref().unwrap())).unwrap(),
        before
    );
}

#[test]
fn anti_aliasing_noise_within_the_tolerance_is_not_a_change() {
    let root = scratch("noise");
    let before = plain(16, 16, [100, 100, 100, 255]);
    let mut after = before.clone();
    for value in after.rgba.chunks_exact_mut(4) {
        value[0] = 100 + compare::DEFAULT_TOLERANCE;
    }
    drawing(
        &root.join("a"),
        &[("day.hours", "dial.dark", Some(&before), None)],
    );
    drawing(
        &root.join("b"),
        &[("day.hours", "dial.dark", Some(&after), None)],
    );
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    assert_eq!(report.entries[0].status, Status::Unchanged);
}

#[test]
fn a_change_of_no_more_than_min_pixels_is_not_a_change_and_one_more_is() {
    let root = scratch("few");
    let before = plain(40, 40, WHITE);
    let mut few = before.clone();
    paint(&mut few, 0, 0, compare::DEFAULT_MIN_PIXELS as u32, 1, INK);
    let mut more = before.clone();
    paint(
        &mut more,
        0,
        0,
        compare::DEFAULT_MIN_PIXELS as u32 + 1,
        1,
        INK,
    );
    drawing(
        &root.join("a"),
        &[
            ("week.a", "v", Some(&before), None),
            ("week.b", "v", Some(&before), None),
        ],
    );
    drawing(
        &root.join("b"),
        &[
            ("week.a", "v", Some(&few), None),
            ("week.b", "v", Some(&more), None),
        ],
    );
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    let status = |screen: &str| {
        report
            .entries
            .iter()
            .find(|e| e.screen == screen)
            .unwrap()
            .status
            .clone()
    };
    assert_eq!(status("week.a"), Status::Unchanged);
    assert_eq!(status("week.b"), Status::Changed);
}

#[test]
fn a_picture_that_changed_size_is_changed_with_no_difference_image() {
    let root = scratch("size");
    drawing(
        &root.join("a"),
        &[("week.grid", "v", Some(&plain(10, 10, WHITE)), None)],
    );
    drawing(
        &root.join("b"),
        &[("week.grid", "v", Some(&plain(12, 10, WHITE)), None)],
    );
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    let entry = &report.entries[0];
    assert_eq!(entry.status, Status::Changed);
    assert_eq!(entry.differing, 120);
    assert!(entry.diff.is_none());
    assert_eq!(
        (entry.before_size, entry.after_size),
        (Some((10, 10)), Some((12, 10)))
    );
}

#[test]
fn new_and_gone_pictures_are_added_and_removed() {
    let root = scratch("added");
    let image = plain(4, 4, WHITE);
    drawing(&root.join("a"), &[("week.old", "v", Some(&image), None)]);
    drawing(&root.join("b"), &[("week.new", "v", Some(&image), None)]);
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    let find = |screen: &str| report.entries.iter().find(|e| e.screen == screen).unwrap();
    assert_eq!(find("week.new").status, Status::Added);
    assert!(
        root.join("out")
            .join(find("week.new").after.as_ref().unwrap())
            .is_file()
    );
    assert_eq!(find("week.old").status, Status::Removed);
    assert!(
        root.join("out")
            .join(find("week.old").before.as_ref().unwrap())
            .is_file()
    );
}

#[test]
fn a_screen_that_could_not_be_drawn_is_failed_first_and_fails_the_command() {
    let root = scratch("failed");
    let image = plain(8, 8, WHITE);
    let mut moved = image.clone();
    paint(&mut moved, 0, 0, 8, 8, INK);
    drawing(
        &root.join("a"),
        &[
            ("week.broken", "v", Some(&image), None),
            ("week.moved", "v", Some(&image), None),
        ],
    );
    drawing(
        &root.join("b"),
        &[
            ("week.broken", "v", None, Some("Traceback: prepare raised")),
            ("week.moved", "v", Some(&moved), None),
        ],
    );
    let out = root.join("out");
    let report =
        compare::compare(&root.join("a"), &root.join("b"), &out, Options::default()).unwrap();
    assert_eq!(report.entries[0].screen, "week.broken");
    assert_eq!(report.entries[0].status, Status::Failed);
    assert_eq!(
        report.entries[0].after_error.as_deref(),
        Some("Traceback: prepare raised")
    );
    assert!(
        report.entries[0].before.is_some(),
        "the side that drew is still shown"
    );
    assert_eq!(report.entries[1].status, Status::Changed);
    assert_eq!(
        compare::run(&root.join("a"), &root.join("b"), &out, Options::default()),
        1
    );
}

#[test]
fn changed_pictures_are_ordered_by_how_much_changed() {
    let root = scratch("order");
    let image = plain(10, 10, WHITE);
    let mut little = image.clone();
    paint(&mut little, 0, 0, 3, 3, INK);
    let mut lot = image.clone();
    paint(&mut lot, 0, 0, 9, 9, INK);
    drawing(
        &root.join("a"),
        &[
            ("week.a", "v", Some(&image), None),
            ("week.b", "v", Some(&image), None),
        ],
    );
    drawing(
        &root.join("b"),
        &[
            ("week.a", "v", Some(&little), None),
            ("week.b", "v", Some(&lot), None),
            ("week.c", "v", Some(&image), None),
        ],
    );
    let report = compare::compare(
        &root.join("a"),
        &root.join("b"),
        &root.join("out"),
        Options::default(),
    )
    .unwrap();
    let order: Vec<&str> = report.entries.iter().map(|e| e.screen.as_str()).collect();
    assert_eq!(order, ["week.b", "week.a", "week.c"]);
}

#[test]
fn a_changed_path_touches_its_file_and_the_folders_holding_it_only() {
    assert!(select::touches(
        "desktop/native/window.py",
        "desktop/native/window.py"
    ));
    assert!(select::touches(
        "desktop/native/hours/zoom.py",
        "desktop/native/hours"
    ));
    assert!(select::touches(
        "desktop/native/hours/zoom.py",
        "desktop/native/hours/"
    ));
    assert!(select::touches(
        "./desktop/native/hours/zoom.py",
        "desktop/native"
    ));
    assert!(!select::touches(
        "desktop/native/weekmodel.py",
        "desktop/native/week"
    ));
    assert!(!select::touches("desktop/native", "desktop/native/hours"));
    assert!(!select::touches("", "desktop"));
}

fn listing() -> Listing {
    let screen = |id: &str, module: &str, sources: &[&str]| Listed {
        id: id.to_string(),
        area: id.split('.').next().unwrap().to_string(),
        sources: sources.iter().map(|s| s.to_string()).collect(),
        module: module.to_string(),
        main: false,
        styles: Vec::new(),
    };
    Listing {
        screens: vec![
            screen(
                "week.grid",
                "desktop/tests/pictures/screens_week.py",
                &["desktop/native/hours", "desktop/native/window.py"],
            ),
            screen(
                "day.hours",
                "desktop/tests/pictures/screens_day.py",
                &["desktop/native/hours"],
            ),
            screen(
                "settings.look",
                "desktop/tests/pictures/screens_settings.py",
                &["desktop/native/settings.py"],
            ),
        ],
        problems: Vec::new(),
    }
}

fn changed(paths: &[&str]) -> Vec<String> {
    paths.iter().map(|p| p.to_string()).collect()
}

#[test]
fn the_touched_screens_are_those_whose_sources_a_change_touches_in_registry_order() {
    let chosen = select::select(&listing(), &changed(&["desktop/native/hours/geometry.py"]));
    assert_eq!(chosen, ["week.grid", "day.hours"]);
    let chosen = select::select(
        &listing(),
        &changed(&["desktop/native/settings.py", "README.md"]),
    );
    assert_eq!(chosen, ["settings.look"]);
}

#[test]
fn a_change_to_a_screens_file_draws_its_screens() {
    let chosen = select::select(
        &listing(),
        &changed(&["desktop/tests/pictures/screens_day.py"]),
    );
    assert_eq!(chosen, ["day.hours"]);
}

#[test]
fn a_change_to_what_every_picture_uses_draws_every_screen() {
    for shared in [
        "scripts/pictures/render.py",
        "desktop/tests/light_app.py",
        "desktop/assets/fonts/Inter-Regular.ttf",
    ] {
        assert_eq!(
            select::select(&listing(), &changed(&[shared])).len(),
            3,
            "{shared}"
        );
    }
}

#[test]
fn a_change_no_screen_is_drawn_from_draws_nothing() {
    assert!(
        select::select(
            &listing(),
            &changed(&["backend/app.py", "docs/tooling/fwtest.md"])
        )
        .is_empty()
    );
}

#[test]
fn changed_paths_are_read_one_per_line() {
    assert_eq!(
        select::read_changed("a.py\n\n  b/c.py \n"),
        ["a.py", "b/c.py"]
    );
}

fn compared(root: &Path) -> PathBuf {
    let image = plain(10, 10, WHITE);
    let mut moved = image.clone();
    paint(&mut moved, 0, 0, 5, 5, INK);
    drawing(
        &root.join("a"),
        &[
            ("week.same", "v", Some(&image), None),
            ("week.moved", "v", Some(&image), None),
        ],
    );
    drawing(
        &root.join("b"),
        &[
            ("week.same", "v", Some(&image), None),
            ("week.moved", "v", Some(&moved), None),
            ("week.new", "v", Some(&image), None),
        ],
    );
    let out = root.join("out");
    compare::compare(&root.join("a"), &root.join("b"), &out, Options::default()).unwrap();
    out
}

#[test]
fn the_page_shows_changed_then_added_pictures_and_lists_unchanged_ones_by_name() {
    let root = scratch("page");
    let out = compared(&root);
    let path = page::build(&out, None).unwrap();
    let html = fs::read_to_string(path).unwrap();
    let changed = html.find("week.moved/v").unwrap();
    let added = html.find("week.new/v").unwrap();
    let unchanged = html.find("Unchanged").unwrap();
    assert!(changed < added && added < unchanged);
    assert!(html.contains("<li>week.same/v</li>"));
    assert!(html.contains("src=\"before/week.moved/v.png\""));
    assert!(html.contains("src=\"after/week.moved/v.png\""));
    assert!(html.contains("src=\"diff/week.moved/v.png\""));
    assert!(html.contains("25 of 100 pixels differ"));
    assert!(html.contains("check week.moved"));
    assert!(
        !html.contains("src=\"after/week.same"),
        "an unchanged picture is not shown"
    );
}

#[test]
fn the_page_shows_the_reviewers_notes_and_escapes_what_it_shows() {
    let root = scratch("page-review");
    let out = compared(&root);
    let mut report = compare::load_report(&out).unwrap();
    report.entries[0].checks = "<script>alert(1)</script> fits".to_string();
    compare::save_report(&out, &report).unwrap();
    let note = out.join(page::review_path(&report.entries[0]));
    fs::create_dir_all(note.parent().unwrap()).unwrap();
    fs::write(&note, "The title <b>clips</b> at Large").unwrap();
    let html = fs::read_to_string(page::build(&out, None).unwrap()).unwrap();
    assert!(html.contains("&lt;script&gt;alert(1)&lt;/script&gt; fits"));
    assert!(!html.contains("<script>alert"));
    assert!(html.contains("The title &lt;b&gt;clips&lt;/b&gt; at Large"));
}

#[test]
fn low_contrast_and_words_too_wide_are_flagged_for_the_reviewer() {
    let label = |text: &str, contrast: f64, too_wide: Option<bool>| Label {
        text: text.to_string(),
        contrast: Some(contrast),
        too_wide,
        ..Label::default()
    };
    let measured = Measurements {
        labels: vec![
            label("fine", 7.0, Some(false)),
            label("faint", 3.2, Some(false)),
            label("long", 9.0, Some(true)),
            label("edge", page::LOW_CONTRAST, None),
        ],
        focus: None,
    };
    let shown: Vec<&str> = page::flagged(&measured)
        .iter()
        .map(|l| l.text.as_str())
        .collect();
    assert_eq!(shown, ["faint", "long"]);
}

#[test]
fn a_clip_strip_takes_frames_evenly_from_first_to_last() {
    let frames: Vec<u32> = (0..100).collect();
    assert_eq!(page::evenly(&frames, 5), [0, 24, 49, 74, 99]);
    assert_eq!(page::evenly(&frames[..3], 8), [0, 1, 2]);
}

#[test]
fn the_page_carries_each_clips_strip_and_video_and_needs_no_comparison() {
    let root = scratch("page-clips");
    let clips_dir = root.join("clips");
    let frames: Vec<String> = (0..20)
        .map(|n| format!("add.widgets.motion-on/frames/{n:05}.jpg"))
        .collect();
    for frame in &frames {
        let path = clips_dir.join(frame);
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, b"jpg").unwrap();
    }
    fs::write(clips_dir.join("add.widgets.motion-on/clip.mp4"), b"mp4").unwrap();
    let listed = page::Clips {
        clips: vec![page::Clip {
            id: "add.widgets.motion-on".to_string(),
            flow: "add".to_string(),
            surface: "widgets".to_string(),
            motion: "on".to_string(),
            frames,
            video: Some("add.widgets.motion-on/clip.mp4".to_string()),
            result: 0,
            note: String::new(),
        }],
    };
    fs::write(
        clips_dir.join("clips.json"),
        serde_json::to_string(&listed).unwrap(),
    )
    .unwrap();
    let out = root.join("page");
    let html = fs::read_to_string(page::build(&out, Some(&clips_dir)).unwrap()).unwrap();
    assert_eq!(
        html.matches("<img src=\"clips/add.widgets.motion-on/")
            .count(),
        page::STRIP_FRAMES
    );
    assert!(out.join("clips/add.widgets.motion-on/01.jpg").is_file());
    assert!(out.join("clips/add.widgets.motion-on/clip.mp4").is_file());
    assert!(html.contains("href=\"clips/add.widgets.motion-on/clip.mp4\""));
}

#[test]
fn the_reviewer_is_asked_about_changed_and_added_pictures_and_its_answer_is_kept() {
    let root = scratch("annotate");
    let out = compared(&root);
    let reviewer =
        r#"read -r first; test -f "$FWTEST_AFTER" && echo "seen $FWTEST_SCREEN $FWTEST_STATUS""#;
    assert_eq!(annotate::run(&out, reviewer, 30), 0);
    let report = compare::load_report(&out).unwrap();
    for entry in &report.entries {
        let answer = fs::read_to_string(out.join(page::review_path(entry)));
        match entry.status {
            Status::Changed | Status::Added => assert_eq!(
                answer.unwrap().trim(),
                format!("seen {} {}", entry.screen, entry.status.word())
            ),
            _ => assert!(answer.is_err(), "{} was not asked about", entry.screen),
        }
    }
    let html = fs::read_to_string(page::build(&out, None).unwrap()).unwrap();
    assert!(html.contains("seen week.moved changed"));
}

#[test]
fn a_reviewer_that_fails_or_runs_too_long_leaves_a_note_and_fails_the_command() {
    let root = scratch("annotate-fail");
    let out = compared(&root);
    assert_eq!(annotate::run(&out, "echo nope >&2; exit 3", 30), 1);
    let report = compare::load_report(&out).unwrap();
    let changed = report
        .entries
        .iter()
        .find(|e| e.status == Status::Changed)
        .unwrap();
    let note = fs::read_to_string(out.join(page::review_path(changed))).unwrap();
    assert!(
        note.starts_with("Reviewer failed: the reviewer exited with"),
        "{note}"
    );
    assert!(note.contains("nope"));
    assert_eq!(annotate::run(&out, "sleep 5; echo late", 1), 1);
    let note = fs::read_to_string(out.join(page::review_path(changed))).unwrap();
    assert_eq!(note, "Reviewer failed: the reviewer ran past 1 s");
}

#[test]
fn a_flow_file_names_its_flow_and_surface() {
    assert_eq!(
        clips::flow_name(Path::new("scripts/rig/flows/add-homework.material.json")),
        Some(("add-homework".to_string(), "material".to_string()))
    );
    assert_eq!(clips::flow_name(Path::new("flows/add-homework.json")), None);
    assert_eq!(clips::flow_name(Path::new("flows/add.phone.json")), None);
}

#[test]
fn each_clip_runs_the_flow_with_its_motion_and_recording_on() {
    let play =
        json!({"setup": {"design": "classic", "motion": "on"}, "steps": [{"see": "School"}]});
    let off = clips::play_for(&play, "off").unwrap();
    assert_eq!(
        off["setup"],
        json!({"design": "classic", "motion": "off", "record": true})
    );
    assert_eq!(off["steps"], play["steps"]);
    let bare = clips::play_for(&json!({"steps": []}), "on").unwrap();
    assert_eq!(bare["setup"], json!({"motion": "on", "record": true}));
}
