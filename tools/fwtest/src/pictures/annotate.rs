//! `fwtest pictures annotate <compare dir> --reviewer <command>`: ask a reviewer about every picture
//! that changed or appeared, and keep its answer beside the picture for the page.
//!
//! The reviewer is any shell command; fwtest ships none and calls no model. For each picture it is
//! run once with `sh -c`, with the request as JSON on its standard input and in the file named by
//! `FWTEST_REVIEW_REQUEST`, and the paths and checks in environment variables too (see
//! docs/tooling/fwtest.md, "Pictures"). What it prints is the answer. A reviewer that exits non-zero
//! or runs past the timeout leaves a note saying so, and the command exits 1 after the rest.

use std::fs;
use std::io::{Read, Write};
use std::os::unix::process::CommandExt;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

use serde::Serialize;

use super::compare::{self, Entry, Status};
use super::page::review_path;

pub const DEFAULT_TIMEOUT_SECS: u64 = 300;

#[derive(Serialize)]
pub struct Request {
    pub screen: String,
    pub variant: String,
    pub status: String,
    pub checks: String,
    pub before: Option<PathBuf>,
    pub after: Option<PathBuf>,
    pub diff: Option<PathBuf>,
    pub measurements: Option<crate::pictures::index::Measurements>,
}

/// What the reviewer is asked about: the pictures that changed or appeared.
pub fn wanted(entry: &Entry) -> bool {
    matches!(entry.status, Status::Changed | Status::Added)
}

pub fn request_for(compare_dir: &Path, entry: &Entry) -> Request {
    let absolute = |relative: &Option<String>| relative.as_ref().map(|r| compare_dir.join(r));
    Request {
        screen: entry.screen.clone(),
        variant: entry.variant.clone(),
        status: entry.status.word().to_string(),
        checks: entry.checks.clone(),
        before: absolute(&entry.before),
        after: absolute(&entry.after),
        diff: absolute(&entry.diff),
        measurements: entry.measurements.clone(),
    }
}

/// How one reviewer run ended.
#[derive(Debug, PartialEq, Eq)]
pub enum Answer {
    Said(String),
    Failed(String),
}

/// Run `reviewer` for one request and wait at most `timeout`.
pub fn ask(reviewer: &str, request: &Request, request_file: &Path, timeout: Duration) -> Answer {
    let body = match serde_json::to_string_pretty(request) {
        Ok(body) => body,
        Err(error) => return Answer::Failed(format!("could not write the request: {error}")),
    };
    if let Err(error) = fs::write(request_file, &body) {
        return Answer::Failed(format!(
            "could not write {}: {error}",
            request_file.display()
        ));
    }
    let path_or_empty = |p: &Option<PathBuf>| {
        p.as_ref()
            .map(|p| p.as_os_str().to_owned())
            .unwrap_or_default()
    };
    let mut child = match Command::new("sh")
        .arg("-c")
        .arg(reviewer)
        .env("FWTEST_REVIEW_REQUEST", request_file)
        .env("FWTEST_SCREEN", &request.screen)
        .env("FWTEST_VARIANT", &request.variant)
        .env("FWTEST_STATUS", &request.status)
        .env("FWTEST_CHECKS", &request.checks)
        .env("FWTEST_BEFORE", path_or_empty(&request.before))
        .env("FWTEST_AFTER", path_or_empty(&request.after))
        .env("FWTEST_DIFF", path_or_empty(&request.diff))
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        // Its own process group, so a timeout stops what the reviewer started too.
        .process_group(0)
        .spawn()
    {
        Ok(child) => child,
        Err(error) => return Answer::Failed(format!("could not start the reviewer: {error}")),
    };
    // A reviewer that never reads its input must not hold this up: the write happens on its own
    // thread, and so do the reads, so a full pipe cannot stall the wait below.
    let mut stdin = child.stdin.take();
    let writer = std::thread::spawn(move || {
        if let Some(stdin) = stdin.as_mut() {
            let _ = stdin.write_all(body.as_bytes());
        }
    });
    let mut stdout = child.stdout.take();
    let mut stderr = child.stderr.take();
    let out_reader = std::thread::spawn(move || {
        let mut text = String::new();
        if let Some(out) = stdout.as_mut() {
            let _ = out.read_to_string(&mut text);
        }
        text
    });
    let err_reader = std::thread::spawn(move || {
        let mut text = String::new();
        if let Some(err) = stderr.as_mut() {
            let _ = err.read_to_string(&mut text);
        }
        text
    });
    let started = Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(status)) => break Some(status),
            Ok(None) if started.elapsed() >= timeout => {
                if let Ok(pid) = i32::try_from(child.id()) {
                    let _ = nix::sys::signal::killpg(
                        nix::unistd::Pid::from_raw(pid),
                        nix::sys::signal::Signal::SIGKILL,
                    );
                }
                let _ = child.kill();
                let _ = child.wait();
                break None;
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(100)),
            Err(error) => return Answer::Failed(format!("lost the reviewer: {error}")),
        }
    };
    let _ = writer.join();
    let said = out_reader.join().unwrap_or_default();
    let complained = err_reader.join().unwrap_or_default();
    match status {
        None => Answer::Failed(format!("the reviewer ran past {} s", timeout.as_secs())),
        Some(status) if !status.success() => Answer::Failed(format!(
            "the reviewer exited with {status}: {}",
            tail(&complained)
        )),
        Some(_) if said.trim().is_empty() => {
            Answer::Failed("the reviewer said nothing".to_string())
        }
        Some(_) => Answer::Said(said),
    }
}

fn tail(text: &str) -> String {
    let lines: Vec<&str> = text.trim().lines().collect();
    lines[lines.len().saturating_sub(20)..].join("\n")
}

pub fn run(compare_dir: &Path, reviewer: &str, timeout_secs: u64) -> u8 {
    let report = match compare::load_report(compare_dir) {
        Ok(report) => report,
        Err(message) => {
            eprintln!("{message}");
            return 1;
        }
    };
    let timeout = Duration::from_secs(timeout_secs.max(1));
    let (mut asked, mut failed) = (0, 0);
    for entry in report.entries.iter().filter(|e| wanted(e)) {
        let answer_file = compare_dir.join(review_path(entry));
        let request_file = answer_file.with_extension("request.json");
        if let Some(parent) = answer_file.parent()
            && let Err(error) = fs::create_dir_all(parent)
        {
            eprintln!("cannot make {}: {error}", parent.display());
            return 1;
        }
        let request = request_for(compare_dir, entry);
        let text = match ask(reviewer, &request, &request_file, timeout) {
            Answer::Said(text) => text,
            Answer::Failed(why) => {
                failed += 1;
                eprintln!("{}: {why}", entry.key());
                format!("Reviewer failed: {why}")
            }
        };
        if let Err(error) = fs::write(&answer_file, text) {
            eprintln!("cannot write {}: {error}", answer_file.display());
            return 1;
        }
        asked += 1;
    }
    println!(
        "Asked about {asked} pictures; {failed} without an answer. Rebuild the page with fwtest pictures page {}",
        compare_dir.display()
    );
    u8::from(failed > 0)
}
