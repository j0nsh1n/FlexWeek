//! `fwtest pictures render --set full|touched [--base <ref>]`: draw this checkout's pictures and,
//! when a base is given, the base's, with this checkout's renderer, each as one contained job.
//!
//! The base is checked out in a temporary worktree under the scratch folder and removed afterwards.
//! Both sides run on this checkout's Python, so they share one installed engine module: a pull
//! request that changes the engine is drawn with its own engine on both sides.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;

use super::index::{self, Index, Listing};
use super::select;
use crate::contain;

pub const RENDERER: &str = "scripts/pictures/render.py";
pub const DEFAULT_BASE: &str = "origin/main";
pub const DEFAULT_TIMEOUT_SECS: u64 = 3600;

#[derive(Clone, Copy, Debug, PartialEq, Eq, clap::ValueEnum)]
pub enum Set {
    Full,
    Touched,
}

pub struct Args {
    pub set: Set,
    pub base: Option<String>,
    pub out: Option<PathBuf>,
    pub changed: Option<PathBuf>,
    pub python: Option<PathBuf>,
    pub timeout: Option<u64>,
}

pub fn scratch_root() -> Result<PathBuf, String> {
    let home = std::env::var_os("HOME")
        .filter(|value| !value.is_empty())
        .ok_or("HOME is not set, so there is no scratch folder")?;
    Ok(PathBuf::from(home).join(".flexweek-ui-harness/scratch/pictures"))
}

fn git(checkout: &Path, args: &[&str]) -> Result<String, String> {
    let output = Command::new("git")
        .arg("-C")
        .arg(checkout)
        .args(args)
        .output()
        .map_err(|error| format!("git {} failed: {error}", args.join(" ")))?;
    if !output.status.success() {
        return Err(format!(
            "git {} failed: {}",
            args.join(" "),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(String::from_utf8_lossy(&output.stdout).into_owned())
}

/// The paths this checkout changes against `base`: committed since the two parted, and anything
/// changed in the working tree or not yet tracked.
pub fn changed_since(checkout: &Path, base: &str) -> Result<Vec<String>, String> {
    let parted = git(checkout, &["merge-base", base, "HEAD"])?;
    let mut paths = select::read_changed(&git(checkout, &["diff", "--name-only", parted.trim()])?);
    paths.extend(select::read_changed(&git(
        checkout,
        &["ls-files", "--others", "--exclude-standard"],
    )?));
    paths.sort();
    paths.dedup();
    Ok(paths)
}

/// The screens `root` declares, as this renderer lists them. Run directly: it imports the screens
/// files and draws nothing.
fn list_screens(python: &Path, renderer: &Path, root: &Path) -> Result<Listing, String> {
    let output = Command::new(python)
        .arg(renderer)
        .arg("--list")
        .arg("--root")
        .arg(root)
        .current_dir(root)
        .output()
        .map_err(|error| format!("could not run {}: {error}", renderer.display()))?;
    if !output.status.success() {
        return Err(format!(
            "{} --list failed: {}",
            renderer.display(),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    index::parse_listing(&String::from_utf8_lossy(&output.stdout))
}

/// An index with no pictures, for a side where nothing was chosen; drawing nothing still costs a
/// sign-up, so the renderer is not started.
fn write_empty(out: &Path, listing: &Listing, root: &Path) -> Result<(), String> {
    fs::create_dir_all(out).map_err(|error| format!("cannot make {}: {error}", out.display()))?;
    let empty = Index {
        version: 1,
        set: "touched".to_string(),
        commit: git(root, &["rev-parse", "HEAD"])
            .unwrap_or_default()
            .trim()
            .to_string(),
        problems: listing.problems.clone(),
        pictures: Vec::new(),
    };
    let text = serde_json::to_string_pretty(&empty).map_err(|error| error.to_string())?;
    fs::write(out.join("index.json"), text + "\n").map_err(|error| error.to_string())
}

struct Side<'a> {
    session: &'a contain::Session,
    python: &'a Path,
    renderer: &'a Path,
    timeout: u64,
}

impl Side<'_> {
    /// Draw `root` into `out`: everything, or the screens `changed` touches. Returns the exit code.
    fn draw(&self, root: &Path, out: &Path, changed: Option<&[String]>) -> Result<u8, String> {
        let mut argv = vec![
            self.python.to_string_lossy().into_owned(),
            self.renderer.to_string_lossy().into_owned(),
            "--root".to_string(),
            root.to_string_lossy().into_owned(),
            "--out".to_string(),
            out.to_string_lossy().into_owned(),
        ];
        match changed {
            None => argv.extend(["--set".to_string(), "full".to_string()]),
            Some(changed) => {
                let listing = list_screens(self.python, self.renderer, root)?;
                let chosen = select::select(&listing, changed);
                println!("{}: {} screens touched", root.display(), chosen.len());
                if chosen.is_empty() {
                    write_empty(out, &listing, root)?;
                    return Ok(u8::from(!listing.problems.is_empty()));
                }
                fs::create_dir_all(out)
                    .map_err(|error| format!("cannot make {}: {error}", out.display()))?;
                let ids = out.with_extension("screens.txt");
                fs::write(&ids, chosen.join("\n") + "\n")
                    .map_err(|error| format!("cannot write {}: {error}", ids.display()))?;
                argv.extend([
                    "--set".to_string(),
                    "touched".to_string(),
                    "--screens".to_string(),
                    ids.to_string_lossy().into_owned(),
                ]);
            }
        }
        self.session
            .run_in(&argv, Some(self.timeout), root)
            .map_err(|error| format!("the renderer could not run: {error}"))
    }
}

/// A detached worktree of `base` that is removed when dropped.
struct BaseTree {
    checkout: PathBuf,
    path: PathBuf,
}

impl BaseTree {
    fn add(checkout: &Path, base: &str) -> Result<Self, String> {
        let folder = scratch_root()?.join("worktrees");
        fs::create_dir_all(&folder)
            .map_err(|error| format!("cannot make {}: {error}", folder.display()))?;
        let path = folder.join(format!("base-{}", super::stamp()));
        let target = path.to_string_lossy().into_owned();
        git(checkout, &["worktree", "add", "--detach", &target, base])?;
        Ok(Self {
            checkout: checkout.to_path_buf(),
            path,
        })
    }
}

impl Drop for BaseTree {
    fn drop(&mut self) {
        let target = self.path.to_string_lossy().into_owned();
        if let Err(message) = git(&self.checkout, &["worktree", "remove", "--force", &target]) {
            eprintln!("could not remove the base worktree {target}: {message}");
        }
    }
}

pub fn run(args: Args) -> u8 {
    match render(args) {
        Ok(code) => code,
        Err(message) => {
            eprintln!("{message}");
            2
        }
    }
}

fn render(args: Args) -> Result<u8, String> {
    let checkout = crate::state::git_toplevel()?;
    let python = crate::state::resolve_python(args.python.as_deref(), &checkout)?;
    let renderer = checkout.join(RENDERER);
    if !renderer.is_file() {
        return Err(format!("Missing {}.", renderer.display()));
    }
    let base = match (args.set, args.base) {
        (Set::Touched, None) => Some(DEFAULT_BASE.to_string()),
        (_, base) => base,
    };
    let changed = match (args.set, &args.changed, &base) {
        (Set::Full, _, _) => None,
        (Set::Touched, Some(file), _) => Some(select::read_changed(
            &fs::read_to_string(file)
                .map_err(|error| format!("cannot read {}: {error}", file.display()))?,
        )),
        (Set::Touched, None, Some(base)) => Some(changed_since(&checkout, base)?),
        (Set::Touched, None, None) => unreachable!("touched always has a base"),
    };
    let out = match args.out {
        Some(out) => out,
        None => scratch_root()?.join(super::stamp()),
    };
    fs::create_dir_all(&out).map_err(|error| format!("cannot make {}: {error}", out.display()))?;
    let out = out
        .canonicalize()
        .map_err(|error| format!("cannot find {}: {error}", out.display()))?;
    if let Some(changed) = &changed {
        fs::write(out.join("changed.txt"), changed.join("\n") + "\n")
            .map_err(|error| format!("cannot write the changed paths: {error}"))?;
    }
    let session = match contain::session() {
        Ok(session) => session,
        Err(code) => return Ok(code),
    };
    let side = Side {
        session: &session,
        python: &python,
        renderer: &renderer,
        timeout: args.timeout.unwrap_or(DEFAULT_TIMEOUT_SECS),
    };
    let head = side.draw(&checkout, &out.join("head"), changed.as_deref())?;
    let mut worst = head;
    if let Some(base) = &base {
        let tree = BaseTree::add(&checkout, base)?;
        let drawn = side.draw(&tree.path, &out.join("base"), changed.as_deref())?;
        worst = worst.max(drawn);
        drop(tree);
        println!(
            "Next: fwtest pictures compare {b} {h} --out {c} && fwtest pictures page {c}",
            b = out.join("base").display(),
            h = out.join("head").display(),
            c = out.join("compare").display()
        );
    }
    println!("Pictures in {}", out.display());
    Ok(worst)
}
