//! `fwtest pictures clips [--flow NAME] [--out DIR]`: record the flows that must behave the same in
//! Widgets and Material 3, each with animations on and off, on the rig's hidden desktop.
//!
//! A flow is a play file `scripts/rig/flows/<flow>.<surface>.json` (the format is the rig's, see
//! docs/tooling/fwtest.md, "Playing the app"). Each run is one `fwtest rig --play`, with the play's
//! setup given `motion` and `record`; the rig writes the frames, and the video when it can encode
//! one on the GPU. The runs are listed in `<out>/clips.json`, which `fwtest pictures page --clips`
//! shows as strips of frames.

use std::fs;
use std::path::{Path, PathBuf};

use serde::Deserialize;
use serde_json::Value;

use super::page::{Clip, Clips};

pub const FLOWS: &str = "scripts/rig/flows";
pub const MOTIONS: [&str; 2] = ["on", "off"];

/// What the rig's recorder writes beside a play's output: `clip.json`.
#[derive(Debug, Default, Deserialize)]
struct Recorded {
    #[serde(default)]
    frames: Vec<String>,
    #[serde(default)]
    video: Option<String>,
    #[serde(default)]
    note: String,
}

/// (flow, surface) from `<flow>.<surface>.json`.
pub fn flow_name(file: &Path) -> Option<(String, String)> {
    let stem = file.file_stem()?.to_str()?;
    let (flow, surface) = stem.rsplit_once('.')?;
    matches!(surface, "widgets" | "material").then(|| (flow.to_string(), surface.to_string()))
}

/// The play with the run's motion and recording set, whatever the file's setup says about them.
pub fn play_for(play: &Value, motion: &str) -> Result<Value, String> {
    let mut play = play.clone();
    let object = play.as_object_mut().ok_or("a play file is a JSON object")?;
    let setup = object
        .entry("setup")
        .or_insert_with(|| Value::Object(Default::default()));
    let setup = setup.as_object_mut().ok_or("a play's setup is an object")?;
    setup.insert("motion".to_string(), Value::String(motion.to_string()));
    setup.insert("record".to_string(), Value::Bool(true));
    Ok(play)
}

pub fn flow_files(
    folder: &Path,
    only: Option<&str>,
) -> Result<Vec<(PathBuf, String, String)>, String> {
    let entries = fs::read_dir(folder)
        .map_err(|error| format!("cannot read {}: {error}", folder.display()))?;
    let mut found: Vec<(PathBuf, String, String)> = entries
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|e| e == "json"))
        .filter_map(|path| flow_name(&path).map(|(flow, surface)| (path, flow, surface)))
        .filter(|(_, flow, _)| only.is_none_or(|wanted| wanted == flow))
        .collect();
    found.sort();
    Ok(found)
}

fn record_one(
    file: &Path,
    flow: &str,
    surface: &str,
    motion: &str,
    out: &Path,
    python: Option<&Path>,
) -> Result<Clip, String> {
    let id = format!("{flow}.{surface}.motion-{motion}");
    let text = fs::read_to_string(file)
        .map_err(|error| format!("cannot read {}: {error}", file.display()))?;
    let play: Value = serde_json::from_str(&text)
        .map_err(|error| format!("{} is not JSON: {error}", file.display()))?;
    let play = play_for(&play, motion)?;
    let folder = out.join(&id);
    let play_file = out.join(format!("{id}.play.json"));
    fs::write(
        &play_file,
        serde_json::to_string_pretty(&play).unwrap_or_default(),
    )
    .map_err(|error| format!("cannot write {}: {error}", play_file.display()))?;
    let args = vec![
        "--play".to_string(),
        play_file.to_string_lossy().into_owned(),
        "--out".to_string(),
        folder.to_string_lossy().into_owned(),
    ];
    let result = crate::rig::run(&args, python);
    let recorded: Recorded = fs::read_to_string(folder.join("clip.json"))
        .ok()
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default();
    let inside = |relative: &String| format!("{id}/{relative}");
    Ok(Clip {
        id: id.clone(),
        flow: flow.to_string(),
        surface: surface.to_string(),
        motion: motion.to_string(),
        frames: recorded.frames.iter().map(inside).collect(),
        video: recorded.video.as_ref().map(inside),
        result: i32::from(result),
        note: recorded.note,
    })
}

pub fn run(only: Option<&str>, out: Option<PathBuf>, python: Option<&Path>) -> u8 {
    let checkout = match crate::state::git_toplevel() {
        Ok(path) => path,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    let files = match flow_files(&checkout.join(FLOWS), only) {
        Ok(files) if files.is_empty() => {
            eprintln!("No flow matches in {FLOWS}.");
            return 2;
        }
        Ok(files) => files,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    let out = match out.map(Ok).unwrap_or_else(|| {
        super::render::scratch_root().map(|root| root.join("clips").join(super::stamp()))
    }) {
        Ok(out) => out,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    if let Err(error) = fs::create_dir_all(&out) {
        eprintln!("cannot make {}: {error}", out.display());
        return 2;
    }
    let mut clips = Clips::default();
    let mut worst = 0;
    for (file, flow, surface) in files {
        for motion in MOTIONS {
            match record_one(&file, &flow, &surface, motion, &out, python) {
                Ok(clip) => {
                    worst = worst.max(u8::try_from(clip.result).unwrap_or(1));
                    println!(
                        "{}: exit {}, {} frames",
                        clip.id,
                        clip.result,
                        clip.frames.len()
                    );
                    clips.clips.push(clip);
                }
                Err(message) => {
                    eprintln!("{message}");
                    worst = worst.max(1);
                }
            }
        }
    }
    let listed = out.join("clips.json");
    let text = serde_json::to_string_pretty(&clips).unwrap_or_default();
    if let Err(error) = fs::write(&listed, text + "\n") {
        eprintln!("cannot write {}: {error}", listed.display());
        return 1;
    }
    println!(
        "Clips in {}; show them with fwtest pictures page <compare dir> --clips {}",
        out.display(),
        out.display()
    );
    worst
}
