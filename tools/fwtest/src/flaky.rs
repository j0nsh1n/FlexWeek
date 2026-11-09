//! The flaky-test log. A test that fails in a pytest run is run again alone, once. A pass alone
//! is logged as flaky and does not fail the run; a second failure does. The log is JSON lines,
//! read back by `fwtest flaky`. Contract: docs/tooling/fwtest.md, "Flaky tests".

use std::collections::BTreeMap;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::{Deserialize, Serialize};

use crate::contain::Session;

/// More failures than this in one run is a real break, not flakiness, so none is rerun.
pub const MAX_RERUNS: usize = 10;

const HOW_LIMIT: usize = 2000;

#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Entry {
    /// pytest node id.
    pub test: String,
    /// UTC, `YYYY-MM-DDTHH:MM:SSZ`.
    pub date: String,
    pub commit: String,
    /// `local`, or `ci <job>` on GitHub Actions.
    pub place: String,
    /// The failure's message and the start of its traceback.
    pub how: String,
    pub beside: Beside,
}

/// What else was going on in the run where the test failed.
#[derive(Clone, Debug, Deserialize, Serialize, PartialEq, Eq)]
pub struct Beside {
    /// The pytest command line, including its worker count and paths.
    pub command: String,
    pub tests_in_run: u64,
    pub other_failures: Vec<String>,
}

/// A failed or errored test case from a JUnit report.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Failed {
    pub id: String,
    pub how: String,
}

/// The log file: `$FWTEST_FLAKY_LOG`, else `~/.flexweek-ui-harness/scratch/fwtest/flaky.jsonl`.
pub fn log_path() -> Result<PathBuf, String> {
    if let Some(path) = std::env::var_os("FWTEST_FLAKY_LOG").filter(|value| !value.is_empty()) {
        return Ok(PathBuf::from(path));
    }
    let root = crate::state::harness_root()?;
    let base = root.parent().unwrap_or(&root);
    Ok(base.join("scratch/fwtest/flaky.jsonl"))
}

/// The arguments to add to a pytest command so its report names each test's file
/// (`xunit1` writes the `file` attribute the node ids are built from).
pub fn report_args(junit: &Path) -> Vec<String> {
    vec![
        format!("--junitxml={}", junit.display()),
        "-o".to_string(),
        "junit_family=xunit1".to_string(),
    ]
}

/// The argv up to and including `pytest`, when the command is a pytest run: `python -m pytest`
/// or a `pytest` program.
pub fn pytest_prefix(argv: &[String]) -> Option<Vec<String>> {
    if let Some(at) = argv
        .windows(2)
        .position(|pair| pair[0] == "-m" && pair[1] == "pytest")
    {
        return Some(argv[..at + 2].to_vec());
    }
    let program = Path::new(argv.first()?).file_name()?.to_string_lossy();
    (program == "pytest" || program == "py.test").then(|| argv[..1].to_vec())
}

/// After a pytest run exited 1: rerun each failed test alone, log the ones that pass, and say
/// whether the run still fails. Any other exit code is returned unchanged by the caller; it is
/// not a test failure (collection error, interrupt, timeout).
pub fn settle(
    session: &Session,
    checkout: &Path,
    argv: &[String],
    junit: &Path,
    timeout: Option<u64>,
) -> u8 {
    let Some(prefix) = pytest_prefix(argv) else {
        return 1;
    };
    let text = match std::fs::read_to_string(junit) {
        Ok(text) => text,
        Err(error) => {
            eprintln!("pytest failed and its report could not be read ({error}); nothing rerun");
            return 1;
        }
    };
    let failed = failed_tests(&text, checkout);
    if failed.is_empty() {
        eprintln!("pytest failed but its report names no failed test; nothing rerun");
        return 1;
    }
    if failed.len() > MAX_RERUNS {
        eprintln!(
            "{} tests failed, more than {MAX_RERUNS}, so none is rerun alone",
            failed.len()
        );
        return 1;
    }
    let tests_in_run = report_totals(&text).0;
    let mut still_failing = 0;
    for test in &failed {
        println!("\nRerunning alone: {}", test.id);
        let _ = std::io::stdout().flush();
        let mut rerun = prefix.clone();
        rerun.extend(["-q", "-p", "no:cacheprovider"].map(String::from));
        rerun.push(test.id.clone());
        let code = match session.run_in(&rerun, timeout, checkout) {
            Ok(code) => code,
            Err(error) => {
                eprintln!("could not rerun {}: {error}", test.id);
                still_failing += 1;
                continue;
            }
        };
        if code != 0 {
            eprintln!("FAILED again alone: {}", test.id);
            still_failing += 1;
            continue;
        }
        let entry = Entry {
            test: test.id.clone(),
            date: crate::contain::utc_now(),
            commit: head_commit(checkout),
            place: place(),
            how: test.how.clone(),
            beside: Beside {
                command: argv.join(" "),
                tests_in_run,
                other_failures: failed
                    .iter()
                    .filter(|other| other.id != test.id)
                    .map(|other| other.id.clone())
                    .collect(),
            },
        };
        let logged = match log_path().and_then(|path| append(&path, &entry).map(|()| path)) {
            Ok(path) => format!("logged in {}", path.display()),
            Err(message) => format!("NOT logged: {message}"),
        };
        println!(
            "FLAKY: {} failed in the run and passed alone; {logged}",
            test.id
        );
        step_summary(&entry);
    }
    if still_failing > 0 {
        return 1;
    }
    println!("Every failed test passed alone. Flaky tests do not fail the run; they are logged.");
    0
}

pub fn append(path: &Path, entry: &Entry) -> Result<(), String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|error| format!("could not create {}: {error}", parent.display()))?;
    }
    let mut line = serde_json::to_string(entry).map_err(|error| error.to_string())?;
    line.push('\n');
    let mut file = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| format!("could not open {}: {error}", path.display()))?;
    file.write_all(line.as_bytes())
        .map_err(|error| format!("could not write {}: {error}", path.display()))
}

fn step_summary(entry: &Entry) {
    let Some(path) = std::env::var_os("GITHUB_STEP_SUMMARY").filter(|value| !value.is_empty())
    else {
        return;
    };
    let first = entry.how.lines().next().unwrap_or("");
    let line = format!(
        "- FLAKY `{}`: failed in the run, passed alone. {}\n",
        entry.test, first
    );
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    {
        let _ = file.write_all(line.as_bytes());
    }
}

fn place() -> String {
    if std::env::var("GITHUB_ACTIONS").as_deref() == Ok("true") {
        let job = std::env::var("GITHUB_JOB").unwrap_or_default();
        return format!("ci {job}").trim_end().to_string();
    }
    "local".to_string()
}

fn head_commit(checkout: &Path) -> String {
    Command::new("git")
        .args(["rev-parse", "HEAD"])
        .current_dir(checkout)
        .output()
        .ok()
        .filter(|output| output.status.success())
        .map(|output| String::from_utf8_lossy(&output.stdout).trim().to_string())
        .filter(|sha| !sha.is_empty())
        .unwrap_or_else(|| "unknown".to_string())
}

/// Tests and skips summed over every `<testsuite>` in a JUnit report.
pub fn report_totals(text: &str) -> (u64, u64) {
    let mut tests = 0;
    let mut skipped = 0;
    for tag in tags(text, "testsuite") {
        tests += attr(tag.attrs, "tests")
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(0);
        skipped += attr(tag.attrs, "skipped")
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(0);
    }
    (tests, skipped)
}

/// Every `<testcase>` with a `<failure>` or `<error>` inside, as a pytest node id and how it
/// failed. The id comes from the `file` attribute when the report has one (`xunit1`), else from
/// the dotted `classname`, matched against the files in the checkout.
pub fn failed_tests(text: &str, checkout: &Path) -> Vec<Failed> {
    let mut failed = Vec::new();
    for case in tags(text, "testcase") {
        let Some(body) = case.body else {
            continue;
        };
        let Some(problem) = tags(body, "failure")
            .into_iter()
            .chain(tags(body, "error"))
            .next()
        else {
            continue;
        };
        let Some(name) = attr(case.attrs, "name") else {
            continue;
        };
        let classname = attr(case.attrs, "classname").unwrap_or_default();
        let file = attr(case.attrs, "file");
        let id = node_id(file.as_deref(), &classname, &name, checkout);
        let mut how = attr(problem.attrs, "message").unwrap_or_default();
        let detail = unescape(problem.body.unwrap_or("").trim());
        if !detail.is_empty() {
            if !how.is_empty() {
                how.push('\n');
            }
            how.push_str(&detail);
        }
        failed.push(Failed {
            id,
            how: clip(&how, HOW_LIMIT),
        });
    }
    failed
}

fn node_id(file: Option<&str>, classname: &str, name: &str, checkout: &Path) -> String {
    let parts: Vec<&str> = classname
        .split('.')
        .filter(|part| !part.is_empty())
        .collect();
    let (path, classes) = match file {
        Some(file) => {
            let module = file.trim_end_matches(".py").replace('/', ".");
            let classes = classname
                .strip_prefix(module.as_str())
                .map(|rest| rest.trim_start_matches('.'))
                .unwrap_or("");
            (file.to_string(), classes.to_string())
        }
        None => {
            let split = (1..=parts.len())
                .rev()
                .find(|count| {
                    let candidate = format!("{}.py", parts[..*count].join("/"));
                    checkout.join(candidate).is_file()
                })
                .unwrap_or(parts.len());
            (
                format!("{}.py", parts[..split].join("/")),
                parts[split..].join("."),
            )
        }
    };
    let mut id = path;
    for class in classes.split('.').filter(|class| !class.is_empty()) {
        id.push_str("::");
        id.push_str(class);
    }
    id.push_str("::");
    id.push_str(name);
    id
}

fn clip(text: &str, limit: usize) -> String {
    if text.len() <= limit {
        return text.to_string();
    }
    let mut end = limit;
    while !text.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}...", &text[..end])
}

struct Tag<'a> {
    attrs: &'a str,
    body: Option<&'a str>,
}

/// Elements named `name`, outermost first, with their attribute text and inner text. Enough for
/// pytest's JUnit reports, which do not nest an element inside one of the same name.
fn tags<'a>(text: &'a str, name: &str) -> Vec<Tag<'a>> {
    let open = format!("<{name}");
    let close = format!("</{name}>");
    let mut found = Vec::new();
    let mut rest = text;
    while let Some(start) = rest.find(&open) {
        let after = &rest[start + open.len()..];
        let boundary = after.chars().next();
        if !matches!(boundary, Some(' ' | '\t' | '\n' | '\r' | '>' | '/')) {
            rest = after;
            continue;
        }
        let Some(end) = tag_end(after) else {
            break;
        };
        let head = &after[..end];
        if let Some(attrs) = head.strip_suffix('/') {
            found.push(Tag { attrs, body: None });
            rest = &after[end + 1..];
            continue;
        }
        let inner = &after[end + 1..];
        match inner.find(&close) {
            Some(stop) => {
                found.push(Tag {
                    attrs: head,
                    body: Some(&inner[..stop]),
                });
                rest = &inner[stop + close.len()..];
            }
            None => {
                found.push(Tag {
                    attrs: head,
                    body: Some(inner),
                });
                break;
            }
        }
    }
    found
}

/// The `>` that ends a start tag, skipping any inside quoted attribute values.
fn tag_end(text: &str) -> Option<usize> {
    let mut quote = None;
    for (at, ch) in text.char_indices() {
        match (quote, ch) {
            (None, '"' | '\'') => quote = Some(ch),
            (Some(open), _) if ch == open => quote = None,
            (None, '>') => return Some(at),
            _ => {}
        }
    }
    None
}

fn attr(attrs: &str, name: &str) -> Option<String> {
    let mut rest = attrs;
    loop {
        let at = rest.find(name)?;
        let before = rest[..at].chars().last();
        let after = &rest[at + name.len()..];
        let after_trim = after.trim_start();
        let is_name = before.is_none_or(char::is_whitespace) && after_trim.starts_with('=');
        if !is_name {
            rest = after;
            continue;
        }
        let value = after_trim[1..].trim_start();
        let quote = value.chars().next()?;
        if quote != '"' && quote != '\'' {
            return None;
        }
        let value = &value[1..];
        let end = value.find(quote)?;
        return Some(unescape(&value[..end]));
    }
}

fn unescape(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    let mut rest = text;
    while let Some(at) = rest.find('&') {
        out.push_str(&rest[..at]);
        let tail = &rest[at..];
        let Some(semi) = tail.find(';').filter(|semi| *semi <= 10) else {
            out.push('&');
            rest = &tail[1..];
            continue;
        };
        let entity = &tail[1..semi];
        let decoded = match entity {
            "amp" => Some('&'),
            "lt" => Some('<'),
            "gt" => Some('>'),
            "quot" => Some('"'),
            "apos" => Some('\''),
            _ => entity
                .strip_prefix("#x")
                .and_then(|hex| u32::from_str_radix(hex, 16).ok())
                .or_else(|| entity.strip_prefix('#').and_then(|dec| dec.parse().ok()))
                .and_then(char::from_u32),
        };
        match decoded {
            Some(ch) => {
                out.push(ch);
                rest = &tail[semi + 1..];
            }
            None => {
                out.push('&');
                rest = &tail[1..];
            }
        }
    }
    out.push_str(rest);
    out
}

/// One line of `fwtest flaky`: a test and how often it was logged.
#[derive(Debug, PartialEq, Eq)]
pub struct Summary {
    pub test: String,
    pub count: usize,
    pub last: Entry,
}

/// Group the log by test, most frequent first, then most recent, then by id.
pub fn summarise(text: &str) -> (Vec<Summary>, usize) {
    let mut bad = 0;
    let mut by_test: BTreeMap<String, (usize, Entry)> = BTreeMap::new();
    for line in text.lines().filter(|line| !line.trim().is_empty()) {
        let Ok(entry) = serde_json::from_str::<Entry>(line) else {
            bad += 1;
            continue;
        };
        match by_test.get_mut(&entry.test) {
            Some((count, last)) => {
                *count += 1;
                if entry.date >= last.date {
                    *last = entry;
                }
            }
            None => {
                by_test.insert(entry.test.clone(), (1, entry));
            }
        }
    }
    let mut summaries: Vec<Summary> = by_test
        .into_iter()
        .map(|(test, (count, last))| Summary { test, count, last })
        .collect();
    summaries.sort_by(|a, b| {
        b.count
            .cmp(&a.count)
            .then_with(|| b.last.date.cmp(&a.last.date))
            .then_with(|| a.test.cmp(&b.test))
    });
    (summaries, bad)
}

/// `fwtest flaky`.
pub fn run(log: Option<&Path>) -> u8 {
    let path = match log {
        Some(path) => path.to_path_buf(),
        None => match log_path() {
            Ok(path) => path,
            Err(message) => {
                eprintln!("{message}");
                return 2;
            }
        },
    };
    let text = match std::fs::read_to_string(&path) {
        Ok(text) => text,
        Err(error) if error.kind() == std::io::ErrorKind::NotFound => {
            println!("no flaky tests logged ({} does not exist)", path.display());
            return 0;
        }
        Err(error) => {
            eprintln!("could not read {}: {error}", path.display());
            return 2;
        }
    };
    let (summaries, bad) = summarise(&text);
    if summaries.is_empty() {
        println!("no flaky tests logged in {}", path.display());
    }
    for summary in &summaries {
        let short: String = summary.last.commit.chars().take(10).collect();
        let first = summary.last.how.lines().next().unwrap_or("");
        println!(
            "{:>4}  {}\n      last {} at {} ({}): {}",
            summary.count, summary.test, summary.last.date, short, summary.last.place, first
        );
    }
    if bad > 0 {
        eprintln!("{bad} line(s) in {} could not be read", path.display());
    }
    0
}
