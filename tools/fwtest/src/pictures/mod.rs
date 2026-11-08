//! `fwtest pictures`: draw the app's screens, compare two drawings, record the flows as clips, ask a
//! reviewer, and build the review page. The contract is docs/tooling/fwtest.md, "Pictures"; the
//! rules are spec.md's Testing structure, rule 6.

pub mod annotate;
pub mod clips;
pub mod compare;
pub mod index;
pub mod page;
pub mod render;
pub mod select;

use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};

use clap::Subcommand;

#[derive(Subcommand)]
pub enum Command {
    /// Draw this checkout's screens and, with --base, the base's, each as one contained job.
    Render {
        /// full: every screen. touched: the screens the changed paths touch, here and on the base.
        #[arg(long, value_enum)]
        set: render::Set,
        /// The base to compare with. Default for touched: origin/main.
        #[arg(long)]
        base: Option<String>,
        /// Where the pictures go (head/, base/). Default: a new folder under the scratch folder.
        #[arg(long)]
        out: Option<PathBuf>,
        /// A file of changed paths, one per line, instead of git's changes since the base.
        #[arg(long)]
        changed: Option<PathBuf>,
        /// Stop a side's drawing after this many seconds (exit 124). Default 3600.
        #[arg(long)]
        timeout: Option<u64>,
        /// Python interpreter. Overrides FWTEST_PYTHON and .venv/bin/python.
        #[arg(long)]
        python: Option<PathBuf>,
    },
    /// Compare two folders of pictures and write the differences and compare.json.
    Compare {
        before: PathBuf,
        after: PathBuf,
        #[arg(long)]
        out: PathBuf,
        /// Largest change of one channel (0-255) that still counts as the same pixel.
        #[arg(long, default_value_t = compare::DEFAULT_TOLERANCE)]
        tolerance: u8,
        /// A picture has changed when more pixels than this differ.
        #[arg(long, default_value_t = compare::DEFAULT_MIN_PIXELS)]
        min_pixels: u64,
    },
    /// Build the review page (index.html) in a compare folder.
    Page {
        compare: PathBuf,
        /// A folder `fwtest pictures clips` wrote; its clips are shown as strips of frames.
        #[arg(long)]
        clips: Option<PathBuf>,
    },
    /// Run a reviewer command for every changed or added picture and keep its answers.
    Annotate {
        compare: PathBuf,
        /// A shell command; see docs/tooling/fwtest.md, "annotate and writing a reviewer".
        #[arg(long)]
        reviewer: String,
        /// Seconds one picture's review may take.
        #[arg(long, default_value_t = annotate::DEFAULT_TIMEOUT_SECS)]
        timeout: u64,
    },
    /// Record the Widgets and Material flows on the rig, animations on and off.
    Clips {
        /// Only this flow (the name before .widgets / .material).
        #[arg(long)]
        flow: Option<String>,
        #[arg(long)]
        out: Option<PathBuf>,
        /// Python interpreter. Overrides FWTEST_PYTHON and .venv/bin/python.
        #[arg(long)]
        python: Option<PathBuf>,
    },
}

pub fn run(command: Command) -> u8 {
    match command {
        Command::Render {
            set,
            base,
            out,
            changed,
            timeout,
            python,
        } => render::run(render::Args {
            set,
            base,
            out,
            changed,
            python,
            timeout,
        }),
        Command::Compare {
            before,
            after,
            out,
            tolerance,
            min_pixels,
        } => compare::run(
            &before,
            &after,
            &out,
            compare::Options {
                tolerance,
                min_pixels,
            },
        ),
        Command::Page { compare, clips } => page::run(&compare, clips.as_deref()),
        Command::Annotate {
            compare,
            reviewer,
            timeout,
        } => annotate::run(&compare, &reviewer, timeout),
        Command::Clips { flow, out, python } => clips::run(flow.as_deref(), out, python.as_deref()),
    }
}

/// A folder name no other run shares: the time and this process.
pub fn stamp() -> String {
    let seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{seconds}-{}", std::process::id())
}
