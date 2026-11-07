//! `fwtest pictures page <compare dir> [--clips <dir>]`: one static HTML page for the reviewer.
//!
//! Failed and changed pictures come first, then added and removed, each with before, after and the
//! difference, the screen's checks, the reviewer's notes when `annotate` ran, and the measurements.
//! Unchanged pictures are listed by name only. Video clips are shown as strips of frames with the
//! video linked, since the person reviewing may not be able to play video. Everything the page
//! shows is inside the compare folder, so the folder can be uploaded as it is.

use std::fs;
use std::path::Path;

use serde::{Deserialize, Serialize};

use super::compare::{self, Entry, Report, Status};
use super::index::{Label, Measurements, key_path};

pub const PAGE: &str = "index.html";
/// Below this the page flags a label's contrast. WCAG's AA line for body text; large text needs
/// 3:1, which the reviewer judges from the picture.
pub const LOW_CONTRAST: f64 = 4.5;
/// Frames a clip's strip shows, picked evenly from the first to the last.
pub const STRIP_FRAMES: usize = 8;

/// One recorded flow, as `fwtest pictures clips` lists it in `clips.json`.
#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Clip {
    pub id: String,
    #[serde(default)]
    pub flow: String,
    #[serde(default)]
    pub surface: String,
    #[serde(default)]
    pub motion: String,
    /// Frames relative to the clips folder, in order.
    #[serde(default)]
    pub frames: Vec<String>,
    #[serde(default)]
    pub video: Option<String>,
    /// The rig's exit code for the run: 0 when every step was done.
    #[serde(default)]
    pub result: i32,
    #[serde(default)]
    pub note: String,
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Clips {
    #[serde(default)]
    pub clips: Vec<Clip>,
}

pub fn escape(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match c {
            '&' => out.push_str("&amp;"),
            '<' => out.push_str("&lt;"),
            '>' => out.push_str("&gt;"),
            '"' => out.push_str("&quot;"),
            '\'' => out.push_str("&#39;"),
            _ => out.push(c),
        }
    }
    out
}

/// Up to `count` items picked evenly, always the first and the last.
pub fn evenly<T: Clone>(items: &[T], count: usize) -> Vec<T> {
    if items.len() <= count || count < 2 {
        return items.iter().take(count.max(1)).cloned().collect::<Vec<_>>();
    }
    (0..count)
        .map(|step| items[step * (items.len() - 1) / (count - 1)].clone())
        .collect()
}

/// The labels worth a look: low contrast or words wider than their label.
pub fn flagged(measurements: &Measurements) -> Vec<&Label> {
    measurements
        .labels
        .iter()
        .filter(|label| {
            label.too_wide == Some(true) || label.contrast.is_some_and(|c| c < LOW_CONTRAST)
        })
        .collect()
}

const STYLE: &str = r#"
:root { --ink:#1b1f24; --muted:#5b6470; --page:#f6f7f9; --card:#fff; --line:#d9dde3;
  --bad:#b42318; --warn:#9a6700; --good:#1a7f37; --mark:#ff00aa; }
@media (prefers-color-scheme: dark) { :root { --ink:#e8eaed; --muted:#a1a8b3; --page:#111418;
  --card:#1a1e24; --line:#2c323b; --bad:#ff8a80; --warn:#f2cc60; --good:#7ee2a8; } }
* { box-sizing: border-box; }
body { margin:0; padding:24px 16px 64px; font:15px/1.45 system-ui,sans-serif; color:var(--ink);
  background:var(--page); }
main { max-width: 1500px; margin: 0 auto; }
h1 { font-size: 22px; margin: 0 0 4px; } h2 { font-size: 18px; margin: 32px 0 8px; }
h3 { font-size: 15px; margin: 0; font-family: ui-monospace,monospace; overflow-wrap:anywhere; }
.meta { color: var(--muted); margin: 0 0 16px; }
.counts { display:flex; flex-wrap:wrap; gap:8px; margin:8px 0 0; padding:0; list-style:none; }
.counts li { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:4px 10px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:14px;
  margin:12px 0; }
.status { font-weight:600; text-transform:uppercase; font-size:12px; letter-spacing:.04em; }
.failed .status, .bad { color: var(--bad); } .changed .status, .warn { color: var(--warn); }
.added .status, .removed .status { color: var(--muted); }
.trio { display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:10px; margin-top:10px; }
figure { margin:0; } figcaption { color:var(--muted); font-size:13px; margin-bottom:4px; }
figure img { width:100%; height:auto; border:1px solid var(--line); border-radius:4px; display:block; }
.checks { margin:8px 0 0; white-space:pre-wrap; }
.review { margin:10px 0 0; padding:8px 10px; border-left:3px solid var(--warn); white-space:pre-wrap; }
details { margin-top:8px; } summary { cursor:pointer; color:var(--muted); }
table { border-collapse:collapse; width:100%; font-size:13px; margin-top:6px; }
th, td { text-align:left; padding:3px 6px; border-bottom:1px solid var(--line); vertical-align:top; }
pre { white-space:pre-wrap; overflow-wrap:anywhere; font-size:12px; margin:6px 0 0; }
.strip { display:flex; gap:6px; overflow-x:auto; padding-bottom:6px; margin-top:8px; }
.strip img { height:150px; width:auto; border:1px solid var(--line); border-radius:3px; }
.swatch { display:inline-block; width:12px; height:12px; border:1px solid var(--line);
  vertical-align:-2px; margin-right:3px; }
ul.plain { margin:6px 0 0; padding-left:18px; font-family:ui-monospace,monospace; font-size:13px; }
"#;

fn figure(caption: &str, path: &Option<String>) -> String {
    match path {
        Some(path) => format!(
            "<figure><figcaption>{}</figcaption><a href=\"{p}\"><img src=\"{p}\" alt=\"{} picture\" loading=\"lazy\"></a></figure>",
            escape(caption),
            escape(caption),
            p = escape(path)
        ),
        None => String::new(),
    }
}

fn swatch(colour: &Option<String>) -> String {
    match colour {
        Some(colour) => format!(
            "<span class=\"swatch\" style=\"background:{c}\"></span>{c}",
            c = escape(colour)
        ),
        None => String::new(),
    }
}

fn measurements_html(measurements: &Option<Measurements>) -> String {
    let Some(measurements) = measurements else {
        return String::new();
    };
    let mut html = String::new();
    let shown = flagged(measurements);
    let focus = match &measurements.focus {
        Some(focus) => match (&focus.focused, focus.ring) {
            (None, _) => "Nothing has the keyboard focus.".to_string(),
            (Some(name), Some(true)) => {
                format!("{} has focus and draws a focus ring.", escape(name))
            }
            (Some(name), Some(false)) => format!(
                "<span class=\"bad\">{} has focus but draws nothing different for it.</span>",
                escape(name)
            ),
            (Some(name), None) => format!(
                "{} has focus; its ring could not be measured.",
                escape(name)
            ),
        },
        None => "Focus was not measured.".to_string(),
    };
    html.push_str(&format!(
        "<p class=\"meta\">{} labels measured; {} to look at. {}</p>",
        measurements.labels.len(),
        shown.len(),
        focus
    ));
    if !shown.is_empty() {
        html.push_str("<table><tr><th>Words</th><th>Widget</th><th>Contrast</th><th>Ink</th><th>Behind</th><th>Wider than its label</th></tr>");
        for label in shown {
            let contrast = match label.contrast {
                Some(c) if c < LOW_CONTRAST => format!("<span class=\"bad\">{c:.2}:1</span>"),
                Some(c) => format!("{c:.2}:1"),
                None => "-".to_string(),
            };
            let wide = match label.too_wide {
                Some(true) => "<span class=\"bad\">yes</span>",
                Some(false) => "no",
                None => "-",
            };
            html.push_str(&format!(
                "<tr><td>{}</td><td>{} {}</td><td>{contrast}</td><td>{}</td><td>{}</td><td>{wide}</td></tr>",
                escape(&label.text),
                escape(&label.kind),
                escape(&label.name),
                swatch(&label.ink),
                swatch(&label.behind)
            ));
        }
        html.push_str("</table>");
    }
    html
}

fn sizes(entry: &Entry) -> String {
    match (entry.before_size, entry.after_size) {
        (Some(a), Some(b)) if a != b => {
            format!(" The size changed from {}x{} to {}x{}.", a.0, a.1, b.0, b.1)
        }
        _ => String::new(),
    }
}

fn entry_html(entry: &Entry, review: Option<&str>) -> String {
    let mut html = format!(
        "<section class=\"card {s}\" id=\"{id}\"><span class=\"status\">{s}</span><h3>{key}</h3>",
        s = entry.status.word(),
        id = escape(&key_path(&entry.screen, &entry.variant)),
        key = escape(&entry.key())
    );
    if entry.status == Status::Changed && entry.total > 0 {
        let share = entry.differing as f64 * 100.0 / entry.total as f64;
        html.push_str(&format!(
            "<p class=\"meta\">{} of {} pixels differ ({share:.2}%).{}</p>",
            entry.differing,
            entry.total,
            sizes(entry)
        ));
    }
    html.push_str(&format!(
        "<p class=\"checks\"><strong>Check:</strong> {}</p>",
        escape(&entry.checks)
    ));
    if let Some(review) = review {
        html.push_str(&format!(
            "<div class=\"review\"><strong>Reviewer:</strong> {}</div>",
            escape(review.trim())
        ));
    }
    for (side, error) in [
        ("Before", &entry.before_error),
        ("After", &entry.after_error),
    ] {
        if let Some(error) = error {
            html.push_str(&format!(
                "<details open><summary class=\"bad\">{side} could not be drawn</summary><pre>{}</pre></details>",
                escape(error)
            ));
        }
    }
    html.push_str("<div class=\"trio\">");
    html.push_str(&figure("Before", &entry.before));
    html.push_str(&figure("After", &entry.after));
    html.push_str(&figure("Difference", &entry.diff));
    html.push_str("</div>");
    html.push_str(&measurements_html(&entry.measurements));
    if !entry.sources.is_empty() {
        html.push_str(&format!(
            "<details><summary>Drawn from</summary><ul class=\"plain\">{}</ul></details>",
            entry
                .sources
                .iter()
                .map(|s| format!("<li>{}</li>", escape(s)))
                .collect::<String>()
        ));
    }
    html.push_str("</section>");
    html
}

fn clip_html(clip: &Clip) -> String {
    let mut html = format!(
        "<section class=\"card\"><h3>{}</h3><p class=\"meta\">{} on {}, animations {}.{}</p>",
        escape(&clip.id),
        escape(&clip.flow),
        escape(&clip.surface),
        escape(&clip.motion),
        if clip.result == 0 {
            String::new()
        } else {
            format!(
                " <span class=\"bad\">The rig could not do every step (exit {}).</span>",
                clip.result
            )
        }
    );
    if !clip.note.is_empty() {
        html.push_str(&format!("<p class=\"meta\">{}</p>", escape(&clip.note)));
    }
    if clip.frames.is_empty() {
        html.push_str("<p class=\"meta\">No frames were recorded.</p>");
    } else {
        html.push_str("<div class=\"strip\">");
        for (number, frame) in clip.frames.iter().enumerate() {
            html.push_str(&format!(
                "<a href=\"{f}\"><img src=\"{f}\" alt=\"frame {} of {}\" loading=\"lazy\"></a>",
                number + 1,
                escape(&clip.id),
                f = escape(frame)
            ));
        }
        html.push_str("</div>");
    }
    match &clip.video {
        Some(video) => html.push_str(&format!(
            "<p><a href=\"{}\">The video</a></p>",
            escape(video)
        )),
        None => html.push_str("<p class=\"meta\">No video: frames only.</p>"),
    }
    html.push_str("</section>");
    html
}

/// The page for `report`. `review` gives the reviewer's notes for a key; `clips` are already
/// copied into the compare folder, their frames relative to it.
pub fn render(
    report: &Report,
    review: &dyn Fn(&Entry) -> Option<String>,
    clips: &[Clip],
) -> String {
    let mut html = String::from(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>FlexWeek pictures</title><style>",
    );
    html.push_str(STYLE);
    html.push_str("</style></head><body><main><h1>FlexWeek pictures</h1>");
    let commits = match (report.before_commit.as_str(), report.after_commit.as_str()) {
        ("", "") => String::new(),
        (before, after) => format!(
            "Before {} and after {}. ",
            escape(short(before)),
            escape(short(after))
        ),
    };
    html.push_str(&format!(
        "<p class=\"meta\">{commits}A pixel counts as different when a channel moves by more than {}; a picture has changed when more than {} pixels do.</p>",
        report.tolerance, report.min_pixels
    ));
    html.push_str("<ul class=\"counts\">");
    for status in [
        Status::Failed,
        Status::Changed,
        Status::Added,
        Status::Removed,
        Status::Unchanged,
    ] {
        html.push_str(&format!(
            "<li>{} {}</li>",
            report.count(&status),
            status.word()
        ));
    }
    html.push_str(&format!("<li>{} clips</li></ul>", clips.len()));
    let problems: Vec<(&str, &super::index::Problem)> = report
        .before_problems
        .iter()
        .map(|p| ("before", p))
        .chain(report.after_problems.iter().map(|p| ("after", p)))
        .collect();
    if !problems.is_empty() {
        html.push_str("<h2>Screens that could not be read</h2>");
        for (side, problem) in problems {
            let what = [problem.module.as_str(), problem.screen.as_str()]
                .into_iter()
                .filter(|s| !s.is_empty())
                .collect::<Vec<_>>()
                .join(" ");
            html.push_str(&format!(
                "<section class=\"card failed\"><span class=\"status\">{side}</span><h3>{}</h3><pre>{}</pre></section>",
                escape(&what),
                escape(&problem.error)
            ));
        }
    }
    let shown: Vec<&Entry> = report
        .entries
        .iter()
        .filter(|e| e.status != Status::Unchanged)
        .collect();
    if shown.is_empty() {
        html.push_str("<h2>No picture changed</h2>");
    } else {
        html.push_str("<h2>Pictures to look at</h2>");
        for entry in shown {
            html.push_str(&entry_html(entry, review(entry).as_deref()));
        }
    }
    if !clips.is_empty() {
        html.push_str("<h2>Clips</h2>");
        for clip in clips {
            html.push_str(&clip_html(clip));
        }
    }
    let same: Vec<&Entry> = report
        .entries
        .iter()
        .filter(|e| e.status == Status::Unchanged)
        .collect();
    if !same.is_empty() {
        html.push_str(&format!(
            "<h2>Unchanged</h2><details><summary>{} pictures</summary><ul class=\"plain\">{}</ul></details>",
            same.len(),
            same.iter()
                .map(|e| format!("<li>{}</li>", escape(&e.key())))
                .collect::<String>()
        ));
    }
    html.push_str("</main></body></html>\n");
    html
}

fn short(commit: &str) -> &str {
    commit.get(..10).unwrap_or(commit)
}

/// Where `annotate` keeps a reviewer's answer for a picture, relative to the compare folder.
pub fn review_path(entry: &Entry) -> String {
    format!("review/{}.txt", key_path(&entry.screen, &entry.variant))
}

/// Copy each clip's strip (and video) into `<compare>/clips/<id>/`, so the page carries it.
fn bring_clips(compare_dir: &Path, clips_dir: &Path) -> Result<Vec<Clip>, String> {
    let listed = clips_dir.join("clips.json");
    let text = fs::read_to_string(&listed)
        .map_err(|error| format!("cannot read {}: {error}", listed.display()))?;
    let all: Clips = serde_json::from_str(&text)
        .map_err(|error| format!("{} is not a clip list: {error}", listed.display()))?;
    let mut brought = Vec::new();
    for clip in all.clips {
        let folder = format!("clips/{}", super::index::safe_segment(&clip.id));
        let target = compare_dir.join(&folder);
        fs::create_dir_all(&target)
            .map_err(|error| format!("cannot make {}: {error}", target.display()))?;
        let mut frames = Vec::new();
        for (number, frame) in evenly(&clip.frames, STRIP_FRAMES).iter().enumerate() {
            let source = clips_dir.join(frame);
            let extension = Path::new(frame)
                .extension()
                .and_then(|e| e.to_str())
                .unwrap_or("jpg");
            let name = format!(
                "{folder}/{:02}.{}",
                number + 1,
                super::index::safe_segment(extension)
            );
            fs::copy(&source, compare_dir.join(&name))
                .map_err(|error| format!("cannot copy {}: {error}", source.display()))?;
            frames.push(name);
        }
        let video = match &clip.video {
            Some(video) => {
                let source = clips_dir.join(video);
                let name = format!("{folder}/clip.mp4");
                fs::copy(&source, compare_dir.join(&name))
                    .map_err(|error| format!("cannot copy {}: {error}", source.display()))?;
                Some(name)
            }
            None => None,
        };
        brought.push(Clip {
            frames,
            video,
            ..clip
        });
    }
    Ok(brought)
}

pub fn build(compare_dir: &Path, clips_dir: Option<&Path>) -> Result<std::path::PathBuf, String> {
    // Clips alone need no comparison: a page of strips is made in an empty folder.
    let report = if clips_dir.is_some() && !compare_dir.join(compare::REPORT).exists() {
        fs::create_dir_all(compare_dir)
            .map_err(|error| format!("cannot make {}: {error}", compare_dir.display()))?;
        Report::default()
    } else {
        compare::load_report(compare_dir)?
    };
    let clips = match clips_dir {
        Some(dir) => bring_clips(compare_dir, dir)?,
        None => Vec::new(),
    };
    let review = |entry: &Entry| fs::read_to_string(compare_dir.join(review_path(entry))).ok();
    let html = render(&report, &review, &clips);
    let path = compare_dir.join(PAGE);
    fs::write(&path, html).map_err(|error| format!("cannot write {}: {error}", path.display()))?;
    Ok(path)
}

pub fn run(compare_dir: &Path, clips_dir: Option<&Path>) -> u8 {
    match build(compare_dir, clips_dir) {
        Ok(path) => {
            println!("Review page: {}", path.display());
            0
        }
        Err(message) => {
            eprintln!("{message}");
            1
        }
    }
}
