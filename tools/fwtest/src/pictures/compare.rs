//! `fwtest pictures compare <before> <after> --out <dir>`: every picture on both sides, matched by
//! screen and variant, with a difference image for each that changed.
//!
//! Two pixels are the same when no channel differs by more than `tolerance`, which absorbs the
//! anti-aliasing noise of text drawn twice. A picture has changed when more than `min_pixels` of its
//! pixels are not the same. Only the pictures that changed, appeared or went are copied into the
//! output folder, so the review page carries what it shows and nothing else.

use std::collections::BTreeMap;
use std::fs::{self, File};
use std::io::{BufReader, BufWriter};
use std::path::{Path, PathBuf};

use serde::{Deserialize, Serialize};

use super::index::{self, Index, Measurements, Picture, Problem};

pub const DEFAULT_TOLERANCE: u8 = 24;
pub const DEFAULT_MIN_PIXELS: u64 = 8;
pub const REPORT: &str = "compare.json";

#[derive(Clone, Copy, Debug)]
pub struct Options {
    pub tolerance: u8,
    pub min_pixels: u64,
}

impl Default for Options {
    fn default() -> Self {
        Self {
            tolerance: DEFAULT_TOLERANCE,
            min_pixels: DEFAULT_MIN_PIXELS,
        }
    }
}

/// An RGBA picture, eight bits a channel.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Image {
    pub width: u32,
    pub height: u32,
    pub rgba: Vec<u8>,
}

#[derive(Clone, Debug, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Status {
    /// Either side could not draw it.
    Failed,
    Changed,
    Added,
    Removed,
    Unchanged,
}

impl Status {
    /// The order the page shows them in: what needs a look first.
    pub fn rank(&self) -> u8 {
        match self {
            Status::Failed => 0,
            Status::Changed => 1,
            Status::Added => 2,
            Status::Removed => 3,
            Status::Unchanged => 4,
        }
    }

    pub fn word(&self) -> &'static str {
        match self {
            Status::Failed => "failed",
            Status::Changed => "changed",
            Status::Added => "added",
            Status::Removed => "removed",
            Status::Unchanged => "unchanged",
        }
    }
}

#[derive(Clone, Debug, PartialEq, Serialize, Deserialize)]
pub struct Entry {
    pub screen: String,
    pub variant: String,
    pub status: Status,
    /// Pixels that are not the same; the whole picture when the sizes differ.
    #[serde(default)]
    pub differing: u64,
    #[serde(default)]
    pub total: u64,
    #[serde(default)]
    pub before_size: Option<(u32, u32)>,
    #[serde(default)]
    pub after_size: Option<(u32, u32)>,
    /// Copies in the output folder, relative to it.
    #[serde(default)]
    pub before: Option<String>,
    #[serde(default)]
    pub after: Option<String>,
    #[serde(default)]
    pub diff: Option<String>,
    #[serde(default)]
    pub checks: String,
    #[serde(default)]
    pub sources: Vec<String>,
    /// The after side's, or the before side's for a removed picture.
    #[serde(default)]
    pub measurements: Option<Measurements>,
    #[serde(default)]
    pub before_error: Option<String>,
    #[serde(default)]
    pub after_error: Option<String>,
}

impl Entry {
    pub fn key(&self) -> String {
        format!("{}/{}", self.screen, self.variant)
    }
}

#[derive(Clone, Debug, Default, PartialEq, Serialize, Deserialize)]
pub struct Report {
    #[serde(default)]
    pub before_commit: String,
    #[serde(default)]
    pub after_commit: String,
    #[serde(default)]
    pub tolerance: u8,
    #[serde(default)]
    pub min_pixels: u64,
    #[serde(default)]
    pub entries: Vec<Entry>,
    #[serde(default)]
    pub before_problems: Vec<Problem>,
    #[serde(default)]
    pub after_problems: Vec<Problem>,
}

impl Report {
    pub fn count(&self, status: &Status) -> usize {
        self.entries.iter().filter(|e| &e.status == status).count()
    }
}

pub fn load_report(folder: &Path) -> Result<Report, String> {
    let path = folder.join(REPORT);
    let text = fs::read_to_string(&path)
        .map_err(|error| format!("cannot read {}: {error}", path.display()))?;
    serde_json::from_str(&text)
        .map_err(|error| format!("{} is not a comparison: {error}", path.display()))
}

pub fn save_report(folder: &Path, report: &Report) -> Result<(), String> {
    let path = folder.join(REPORT);
    let text = serde_json::to_string_pretty(report).map_err(|error| error.to_string())?;
    fs::write(&path, text + "\n")
        .map_err(|error| format!("cannot write {}: {error}", path.display()))
}

pub fn read_png(path: &Path) -> Result<Image, String> {
    let file =
        File::open(path).map_err(|error| format!("cannot open {}: {error}", path.display()))?;
    let mut decoder = png::Decoder::new(BufReader::new(file));
    decoder.set_transformations(png::Transformations::EXPAND | png::Transformations::STRIP_16);
    let mut reader = decoder
        .read_info()
        .map_err(|error| format!("{} is not a PNG: {error}", path.display()))?;
    let size = reader
        .output_buffer_size()
        .ok_or_else(|| format!("{} is too large to read", path.display()))?;
    let mut buffer = vec![0; size];
    let info = reader
        .next_frame(&mut buffer)
        .map_err(|error| format!("cannot read {}: {error}", path.display()))?;
    buffer.truncate(info.buffer_size());
    let rgba = match info.color_type {
        png::ColorType::Rgba => buffer,
        png::ColorType::Rgb => buffer
            .chunks_exact(3)
            .flat_map(|p| [p[0], p[1], p[2], 255])
            .collect(),
        png::ColorType::Grayscale => buffer.iter().flat_map(|&g| [g, g, g, 255]).collect(),
        png::ColorType::GrayscaleAlpha => buffer
            .chunks_exact(2)
            .flat_map(|p| [p[0], p[0], p[0], p[1]])
            .collect(),
        png::ColorType::Indexed => {
            return Err(format!(
                "{} is still indexed after expanding",
                path.display()
            ));
        }
    };
    Ok(Image {
        width: info.width,
        height: info.height,
        rgba,
    })
}

pub fn write_png(path: &Path, image: &Image) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("cannot make {}: {error}", parent.display()))?;
    }
    let file =
        File::create(path).map_err(|error| format!("cannot write {}: {error}", path.display()))?;
    let mut encoder = png::Encoder::new(BufWriter::new(file), image.width, image.height);
    encoder.set_color(png::ColorType::Rgba);
    encoder.set_depth(png::BitDepth::Eight);
    let mut writer = encoder
        .write_header()
        .map_err(|error| format!("cannot write {}: {error}", path.display()))?;
    writer
        .write_image_data(&image.rgba)
        .map_err(|error| format!("cannot write {}: {error}", path.display()))
}

/// How two pictures of one screen differ.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Difference {
    pub differing: u64,
    pub total: u64,
    /// The after picture faded to grey with every differing pixel in magenta. None when the sizes
    /// differ, as there is no pixel to pixel match to show.
    pub image: Option<Image>,
}

const MARK: [u8; 4] = [255, 0, 170, 255];

pub fn difference(before: &Image, after: &Image, tolerance: u8) -> Difference {
    let total = u64::from(after.width) * u64::from(after.height);
    if (before.width, before.height) != (after.width, after.height) {
        let largest = total.max(u64::from(before.width) * u64::from(before.height));
        return Difference {
            differing: largest,
            total: largest,
            image: None,
        };
    }
    let mut rgba = Vec::with_capacity(after.rgba.len());
    let mut differing = 0;
    for (one, two) in before.rgba.chunks_exact(4).zip(after.rgba.chunks_exact(4)) {
        let apart = one.iter().zip(two).any(|(a, b)| a.abs_diff(*b) > tolerance);
        if apart {
            differing += 1;
            rgba.extend_from_slice(&MARK);
        } else {
            let luma = (u32::from(two[0]) * 3 + u32::from(two[1]) * 6 + u32::from(two[2])) / 10;
            let faded = (luma * 35 / 100 + 255 * 65 / 100).min(255) as u8;
            rgba.extend_from_slice(&[faded, faded, faded, 255]);
        }
    }
    Difference {
        differing,
        total,
        image: Some(Image {
            width: after.width,
            height: after.height,
            rgba,
        }),
    }
}

fn by_key(index: &Index) -> BTreeMap<String, &Picture> {
    index.pictures.iter().map(|p| (p.key(), p)).collect()
}

fn copy_into(source: &Path, out: &Path, relative: &str) -> Result<String, String> {
    let target = out.join(relative);
    if let Some(parent) = target.parent() {
        fs::create_dir_all(parent)
            .map_err(|error| format!("cannot make {}: {error}", parent.display()))?;
    }
    fs::copy(source, &target).map_err(|error| {
        format!(
            "cannot copy {} to {}: {error}",
            source.display(),
            target.display()
        )
    })?;
    Ok(relative.to_string())
}

/// The PNG a picture names, or the reason there is none.
fn picture_file(folder: &Path, picture: &Picture) -> Result<PathBuf, String> {
    if let Some(error) = &picture.error {
        return Err(error.clone());
    }
    let Some(relative) = &picture.picture else {
        return Err("the renderer wrote no picture".to_string());
    };
    if relative
        .split('/')
        .any(|part| part == ".." || part.is_empty())
    {
        return Err(format!("{relative} is not a picture inside the folder"));
    }
    Ok(folder.join(relative))
}

/// Compare the pictures in `before` and `after` (each a folder render.py wrote), copy what changed
/// into `out` and write `out/compare.json`.
pub fn compare(
    before: &Path,
    after: &Path,
    out: &Path,
    options: Options,
) -> Result<Report, String> {
    let old = index::load_index(before)?;
    let new = index::load_index(after)?;
    fs::create_dir_all(out).map_err(|error| format!("cannot make {}: {error}", out.display()))?;
    let (old_keys, new_keys) = (by_key(&old), by_key(&new));
    let mut keys: Vec<&String> = old_keys.keys().chain(new_keys.keys()).collect();
    keys.sort();
    keys.dedup();
    let mut entries = Vec::new();
    for key in keys {
        let (was, now) = (old_keys.get(key).copied(), new_keys.get(key).copied());
        let shown = now.or(was).expect("a key comes from one side");
        let path = index::key_path(&shown.screen, &shown.variant);
        let mut entry = Entry {
            screen: shown.screen.clone(),
            variant: shown.variant.clone(),
            status: Status::Unchanged,
            differing: 0,
            total: 0,
            before_size: None,
            after_size: None,
            before: None,
            after: None,
            diff: None,
            checks: shown.checks.clone(),
            sources: shown.sources.clone(),
            measurements: shown.measurements.clone(),
            before_error: None,
            after_error: None,
        };
        let old_file = was.map(|p| picture_file(before, p));
        let new_file = now.map(|p| picture_file(after, p));
        let old_image = match &old_file {
            Some(Ok(file)) => {
                Some(read_png(file).inspect_err(|e| entry.before_error = Some(e.clone())))
            }
            Some(Err(error)) => {
                entry.before_error = Some(error.clone());
                None
            }
            None => None,
        };
        let new_image = match &new_file {
            Some(Ok(file)) => {
                Some(read_png(file).inspect_err(|e| entry.after_error = Some(e.clone())))
            }
            Some(Err(error)) => {
                entry.after_error = Some(error.clone());
                None
            }
            None => None,
        };
        if entry.before_error.is_some() || entry.after_error.is_some() {
            entry.status = Status::Failed;
        }
        let before_png = format!("before/{path}.png");
        let after_png = format!("after/{path}.png");
        match (old_image, new_image) {
            (Some(Ok(one)), Some(Ok(two))) => {
                let found = difference(&one, &two, options.tolerance);
                entry.differing = found.differing;
                entry.total = found.total;
                entry.before_size = Some((one.width, one.height));
                entry.after_size = Some((two.width, two.height));
                if found.differing > options.min_pixels || found.image.is_none() {
                    entry.status = Status::Changed;
                    if let (Some(Ok(a)), Some(Ok(b))) = (&old_file, &new_file) {
                        entry.before = Some(copy_into(a, out, &before_png)?);
                        entry.after = Some(copy_into(b, out, &after_png)?);
                    }
                    if let Some(image) = found.image {
                        let diff_png = format!("diff/{path}.png");
                        write_png(&out.join(&diff_png), &image)?;
                        entry.diff = Some(diff_png);
                    }
                }
            }
            (None, Some(Ok(two))) if entry.status != Status::Failed => {
                entry.status = Status::Added;
                entry.after_size = Some((two.width, two.height));
                if let Some(Ok(b)) = &new_file {
                    entry.after = Some(copy_into(b, out, &after_png)?);
                }
            }
            (Some(Ok(one)), None) if entry.status != Status::Failed => {
                entry.status = Status::Removed;
                entry.before_size = Some((one.width, one.height));
                if let Some(Ok(a)) = &old_file {
                    entry.before = Some(copy_into(a, out, &before_png)?);
                }
            }
            (one, two) => {
                // A failed side: show whichever picture there is.
                if let (Some(Ok(_)), Some(Ok(a))) = (&one, &old_file) {
                    entry.before = Some(copy_into(a, out, &before_png)?);
                }
                if let (Some(Ok(_)), Some(Ok(b))) = (&two, &new_file) {
                    entry.after = Some(copy_into(b, out, &after_png)?);
                }
            }
        }
        entries.push(entry);
    }
    entries.sort_by(|a, b| {
        a.status
            .rank()
            .cmp(&b.status.rank())
            .then(b.differing.cmp(&a.differing))
            .then(a.key().cmp(&b.key()))
    });
    let report = Report {
        before_commit: old.commit,
        after_commit: new.commit,
        tolerance: options.tolerance,
        min_pixels: options.min_pixels,
        entries,
        before_problems: old.problems,
        after_problems: new.problems,
    };
    save_report(out, &report)?;
    Ok(report)
}

/// The command: prints the counts. Exit 1 when the after side failed to draw anything it declared.
pub fn run(before: &Path, after: &Path, out: &Path, options: Options) -> u8 {
    match compare(before, after, out, options) {
        Ok(report) => {
            println!(
                "{} changed, {} added, {} removed, {} unchanged, {} failed. Comparison in {}",
                report.count(&Status::Changed),
                report.count(&Status::Added),
                report.count(&Status::Removed),
                report.count(&Status::Unchanged),
                report.count(&Status::Failed),
                out.display()
            );
            let broken = report.entries.iter().any(|e| e.after_error.is_some())
                || !report.after_problems.is_empty();
            u8::from(broken)
        }
        Err(message) => {
            eprintln!("{message}");
            1
        }
    }
}
