//! Test selection by changed paths. The map is `tools/fwtest/areas.toml`; the rules are in
//! docs/tooling/fwtest.md, "Test selection".

use std::collections::{BTreeMap, BTreeSet};
use std::path::{Path, PathBuf};
use std::process::Command;

use serde::Deserialize;

pub const MAP_PATH: &str = "tools/fwtest/areas.toml";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct MapFile {
    #[serde(default)]
    area: Vec<Area>,
    #[serde(default)]
    rule: Vec<Rule>,
    #[serde(default)]
    also: Vec<Also>,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Area {
    pub name: String,
    #[serde(default)]
    pub tests: Vec<String>,
    pub cargo: Option<Cargo>,
    #[serde(default)]
    pub pictures: bool,
}

#[derive(Clone, Debug, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Cargo {
    pub dir: String,
    pub packages: Vec<String>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Rule {
    paths: Vec<String>,
    areas: Option<Vec<String>>,
    #[serde(default)]
    everything: bool,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct Also {
    paths: Vec<String>,
    areas: Vec<String>,
}

#[derive(Debug)]
pub struct Map {
    areas: Vec<Area>,
    rules: Vec<Rule>,
    also: Vec<Also>,
}

/// What a set of changed paths selects.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Selection {
    pub changed: Vec<String>,
    /// True when a path selects every area, either by a rule or because no rule knows it.
    pub everything: bool,
    /// Changed paths no rule matches. Each of them selects every area.
    pub unknown: Vec<String>,
    /// Area names, in the map's order.
    pub areas: Vec<String>,
    /// pytest paths and patterns of the selected areas, in the map's order, before they are
    /// checked against the checkout.
    pub tests: Vec<String>,
    /// Cargo packages to test, by workspace folder.
    pub cargo: BTreeMap<String, BTreeSet<String>>,
    /// Areas whose picture screens may need drawing again.
    pub pictures: Vec<String>,
}

/// What pytest gets for a selection.
#[derive(Debug, PartialEq, Eq)]
pub enum Pytest {
    /// No selected area has pytest tests.
    Nothing,
    /// The whole suite (pytest.ini's testpaths), with the reason.
    Everything(String),
    /// These paths, each present in the checkout.
    Paths(Vec<String>),
}

impl Map {
    pub fn parse(text: &str) -> Result<Self, String> {
        let file: MapFile = toml::from_str(text).map_err(|error| format!("{MAP_PATH}: {error}"))?;
        let mut names = BTreeSet::new();
        for area in &file.area {
            if !names.insert(area.name.as_str()) {
                return Err(format!("{MAP_PATH}: area {} is defined twice", area.name));
            }
            if area.tests.is_empty() && area.cargo.is_none() {
                return Err(format!("{MAP_PATH}: area {} has no tests", area.name));
            }
            for pattern in &area.tests {
                check_pattern(pattern)?;
                if pattern.contains('*') && pattern.ends_with('/') {
                    return Err(format!(
                        "{MAP_PATH}: test pattern {pattern}: \"*\" is only allowed in a file name"
                    ));
                }
                let parts: Vec<&str> = pattern.trim_end_matches('/').split('/').collect();
                if parts[..parts.len() - 1]
                    .iter()
                    .any(|part| part.contains('*'))
                {
                    return Err(format!(
                        "{MAP_PATH}: test pattern {pattern}: \"*\" is only allowed in the last part"
                    ));
                }
            }
            if let Some(cargo) = &area.cargo
                && cargo.packages.is_empty()
            {
                return Err(format!(
                    "{MAP_PATH}: area {} names no cargo packages",
                    area.name
                ));
            }
        }
        for (index, rule) in file.rule.iter().enumerate() {
            let label = format!("rule {} ({})", index + 1, rule.paths.join(", "));
            if rule.paths.is_empty() {
                return Err(format!("{MAP_PATH}: rule {} has no paths", index + 1));
            }
            match (&rule.areas, rule.everything) {
                (Some(_), true) => {
                    return Err(format!(
                        "{MAP_PATH}: {label} sets both areas and everything"
                    ));
                }
                (None, false) => {
                    return Err(format!(
                        "{MAP_PATH}: {label} needs areas (may be []) or everything = true"
                    ));
                }
                _ => {}
            }
            for pattern in &rule.paths {
                check_pattern(pattern)?;
            }
            for name in rule.areas.iter().flatten() {
                if !names.contains(name.as_str()) {
                    return Err(format!("{MAP_PATH}: {label} names unknown area {name}"));
                }
            }
        }
        for (index, also) in file.also.iter().enumerate() {
            if also.paths.is_empty() || also.areas.is_empty() {
                return Err(format!(
                    "{MAP_PATH}: also rule {} needs paths and areas",
                    index + 1
                ));
            }
            for pattern in &also.paths {
                check_pattern(pattern)?;
            }
            for name in &also.areas {
                if !names.contains(name.as_str()) {
                    return Err(format!(
                        "{MAP_PATH}: also rule {} names unknown area {name}",
                        index + 1
                    ));
                }
            }
        }
        Ok(Self {
            areas: file.area,
            rules: file.rule,
            also: file.also,
        })
    }

    pub fn load(checkout: &Path) -> Result<Self, String> {
        let path = checkout.join(MAP_PATH);
        let text = std::fs::read_to_string(&path)
            .map_err(|error| format!("could not read {}: {error}", path.display()))?;
        Self::parse(&text)
    }

    pub fn areas(&self) -> &[Area] {
        &self.areas
    }

    pub fn select(&self, changed: &[String]) -> Selection {
        let mut chosen: BTreeSet<&str> = BTreeSet::new();
        let mut everything = false;
        let mut unknown = Vec::new();
        for path in changed {
            match self.rules.iter().find(|rule| rule.matches(path)) {
                Some(rule) if rule.everything => everything = true,
                Some(rule) => chosen.extend(rule.areas.iter().flatten().map(String::as_str)),
                None => {
                    everything = true;
                    unknown.push(path.clone());
                }
            }
            for also in self.also.iter().filter(|also| also.matches(path)) {
                chosen.extend(also.areas.iter().map(String::as_str));
            }
        }
        let areas: Vec<&Area> = self
            .areas
            .iter()
            .filter(|area| everything || chosen.contains(area.name.as_str()))
            .collect();
        let mut selection = Selection {
            changed: changed.to_vec(),
            everything,
            unknown,
            ..Selection::default()
        };
        for area in areas {
            selection.areas.push(area.name.clone());
            for pattern in &area.tests {
                if !selection.tests.contains(pattern) {
                    selection.tests.push(pattern.clone());
                }
            }
            if let Some(cargo) = &area.cargo {
                selection
                    .cargo
                    .entry(cargo.dir.clone())
                    .or_default()
                    .extend(cargo.packages.iter().cloned());
            }
            if area.pictures {
                selection.pictures.push(area.name.clone());
            }
        }
        selection
    }
}

impl Rule {
    fn matches(&self, path: &str) -> bool {
        self.paths.iter().any(|pattern| matches(pattern, path))
    }
}

impl Also {
    fn matches(&self, path: &str) -> bool {
        self.paths.iter().any(|pattern| matches(pattern, path))
    }
}

fn check_pattern(pattern: &str) -> Result<(), String> {
    let bad = pattern.is_empty()
        || pattern.starts_with('/')
        || pattern.contains("**")
        || pattern.contains('\\')
        || pattern
            .trim_end_matches('/')
            .split('/')
            .any(|part| part.is_empty() || part == "." || part == "..");
    if bad {
        return Err(format!(
            "{MAP_PATH}: bad path pattern {pattern:?} (relative, \"/\" between parts, \"*\" within one part)"
        ));
    }
    Ok(())
}

/// A pattern ending in `/` matches every path under that folder. Otherwise it matches one path.
/// `*` matches any run of characters within one path part.
pub fn matches(pattern: &str, path: &str) -> bool {
    let (folder, pattern) = match pattern.strip_suffix('/') {
        Some(rest) => (true, rest),
        None => (false, pattern),
    };
    let wanted: Vec<&str> = pattern.split('/').collect();
    let parts: Vec<&str> = path.split('/').collect();
    if folder {
        if parts.len() <= wanted.len() {
            return false;
        }
    } else if parts.len() != wanted.len() {
        return false;
    }
    wanted
        .iter()
        .zip(&parts)
        .all(|(pattern, part)| glob(pattern, part))
}

fn glob(pattern: &str, text: &str) -> bool {
    let mut pieces = pattern.split('*');
    let first = pieces.next().unwrap_or("");
    let Some(mut rest) = text.strip_prefix(first) else {
        return false;
    };
    let pieces: Vec<&str> = pieces.collect();
    let Some((last, middle)) = pieces.split_last() else {
        return rest.is_empty();
    };
    for piece in middle {
        match rest.find(piece) {
            Some(at) => rest = &rest[at + piece.len()..],
            None => return false,
        }
    }
    rest.len() >= last.len() && rest.ends_with(last)
}

/// The pytest paths of a selection that exist in the checkout. A selection whose areas have
/// pytest tests but none of them exist yet runs the whole suite: selecting nothing would pass
/// a change no test looked at.
pub fn pytest(checkout: &Path, selection: &Selection) -> Pytest {
    if selection.everything {
        return Pytest::Everything("the changed paths select every area".to_string());
    }
    if selection.tests.is_empty() {
        return Pytest::Nothing;
    }
    let paths = existing_tests(checkout, &selection.tests);
    if paths.is_empty() {
        return Pytest::Everything(
            "none of the selected areas' test folders exist yet".to_string(),
        );
    }
    Pytest::Paths(paths)
}

fn existing_tests(checkout: &Path, patterns: &[String]) -> Vec<String> {
    let mut found = Vec::new();
    for pattern in patterns {
        if pattern.contains('*') {
            let (folder, name) = pattern.rsplit_once('/').unwrap_or(("", pattern));
            let Ok(entries) = std::fs::read_dir(checkout.join(folder)) else {
                continue;
            };
            let mut files: Vec<String> = entries
                .filter_map(Result::ok)
                .filter(|entry| entry.file_type().is_ok_and(|kind| kind.is_file()))
                .filter_map(|entry| entry.file_name().into_string().ok())
                .filter(|file| glob(name, file))
                .map(|file| {
                    if folder.is_empty() {
                        file
                    } else {
                        format!("{folder}/{file}")
                    }
                })
                .collect();
            files.sort();
            found.extend(files);
        } else if let Some(folder) = pattern.strip_suffix('/') {
            if checkout.join(folder).is_dir() {
                found.push(folder.to_string());
            }
        } else if checkout.join(pattern).is_file() {
            found.push(pattern.clone());
        }
    }
    let mut seen = BTreeSet::new();
    found.retain(|path| seen.insert(path.clone()));
    found
}

/// One mutation case a selection asks to run.
#[derive(Debug, PartialEq, Eq)]
pub struct MutationCase {
    pub spec: String,
    pub name: String,
}

#[derive(Deserialize)]
struct SpecCase {
    name: String,
    file: String,
    test: String,
}

/// The mutation cases the changed paths touch: every case when the selection is everything,
/// otherwise each case whose spec, source file or Python test file changed.
pub fn mutation_cases(checkout: &Path, selection: &Selection) -> Result<Vec<MutationCase>, String> {
    let folder = checkout.join("scripts/mutations");
    let Ok(entries) = std::fs::read_dir(&folder) else {
        return Ok(Vec::new());
    };
    let mut specs: Vec<PathBuf> = entries
        .filter_map(Result::ok)
        .map(|entry| entry.path())
        .filter(|path| path.extension().is_some_and(|ext| ext == "json"))
        .collect();
    specs.sort();
    let changed: BTreeSet<&str> = selection.changed.iter().map(String::as_str).collect();
    let mut cases = Vec::new();
    for spec in specs {
        let file_name = spec
            .file_name()
            .map(|name| name.to_string_lossy().into_owned())
            .unwrap_or_default();
        let text = std::fs::read_to_string(&spec)
            .map_err(|error| format!("{}: {error}", spec.display()))?;
        let parsed: Vec<SpecCase> =
            serde_json::from_str(&text).map_err(|error| format!("{}: {error}", spec.display()))?;
        let spec_changed = changed.contains(format!("scripts/mutations/{file_name}").as_str());
        for case in parsed {
            let test_file = case.test.split("::").next().unwrap_or("");
            let touched = selection.everything
                || spec_changed
                || changed.contains(case.file.as_str())
                || (!case.test.starts_with("cargo:") && changed.contains(test_file));
            if touched {
                cases.push(MutationCase {
                    spec: file_name.clone(),
                    name: case.name,
                });
            }
        }
    }
    Ok(cases)
}

/// Where the changed paths come from: a ref to compare with, or a file listing them.
#[derive(Clone, Debug, Default)]
pub struct Change {
    pub base: Option<String>,
    pub paths_from: Option<PathBuf>,
}

/// The changed paths and a line saying where they came from.
pub fn changed_paths(checkout: &Path, change: &Change) -> Result<(String, Vec<String>), String> {
    if let Some(file) = &change.paths_from {
        let text = std::fs::read_to_string(file)
            .map_err(|error| format!("could not read {}: {error}", file.display()))?;
        let paths = tidy(text.lines().map(str::to_string));
        return Ok((format!("paths listed in {}", file.display()), paths));
    }
    let (label, base) = match &change.base {
        Some(base) => (base.clone(), merge_base(checkout, base)?),
        None => default_base(checkout)?,
    };
    let diff = git_lines(
        checkout,
        &["diff", "--name-only", "--no-renames", "-z", &base],
    )?;
    let untracked = git_lines(
        checkout,
        &["ls-files", "--others", "--exclude-standard", "-z"],
    )?;
    let paths = tidy(diff.into_iter().chain(untracked));
    let short: String = base.chars().take(12).collect();
    Ok((
        format!("changes since {label} (merge base {short}), with uncommitted and untracked files"),
        paths,
    ))
}

fn tidy(paths: impl Iterator<Item = String>) -> Vec<String> {
    let set: BTreeSet<String> = paths
        .map(|path| path.trim().trim_start_matches("./").to_string())
        .filter(|path| !path.is_empty())
        .collect();
    set.into_iter().collect()
}

fn default_base(checkout: &Path) -> Result<(String, String), String> {
    for candidate in ["origin/main", "main"] {
        if let Ok(base) = merge_base(checkout, candidate) {
            return Ok((candidate.to_string(), base));
        }
    }
    Err("no origin/main or main to compare with; pass --base REF or --paths-from FILE".to_string())
}

fn merge_base(checkout: &Path, base: &str) -> Result<String, String> {
    let output = Command::new("git")
        .args(["merge-base", base, "HEAD"])
        .current_dir(checkout)
        .output()
        .map_err(|error| format!("git merge-base failed: {error}"))?;
    let sha = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if !output.status.success() || sha.is_empty() {
        return Err(format!("{base} has no merge base with HEAD here"));
    }
    Ok(sha)
}

fn git_lines(checkout: &Path, args: &[&str]) -> Result<Vec<String>, String> {
    let output = Command::new("git")
        .args(args)
        .current_dir(checkout)
        .output()
        .map_err(|error| format!("git {} failed: {error}", args[0]))?;
    if !output.status.success() {
        return Err(format!(
            "git {} failed: {}",
            args.join(" "),
            String::from_utf8_lossy(&output.stderr).trim()
        ));
    }
    Ok(output
        .stdout
        .split(|byte| *byte == 0)
        .filter(|item| !item.is_empty())
        .map(|item| String::from_utf8_lossy(item).into_owned())
        .collect())
}

/// Everything `fwtest select`, `gate --touched` and `run --touched` need: the checkout's map
/// applied to its changed paths.
pub struct Plan {
    pub source: String,
    pub selection: Selection,
    pub pytest: Pytest,
}

pub fn plan(checkout: &Path, change: &Change) -> Result<Plan, String> {
    let map = Map::load(checkout)?;
    let (source, changed) = changed_paths(checkout, change)?;
    let selection = map.select(&changed);
    let pytest = pytest(checkout, &selection);
    Ok(Plan {
        source,
        selection,
        pytest,
    })
}

/// `fwtest select`.
pub fn run(change: &Change) -> u8 {
    let checkout = match crate::state::git_toplevel() {
        Ok(path) => path,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    let plan = match plan(&checkout, change) {
        Ok(plan) => plan,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    let mutations = match mutation_cases(&checkout, &plan.selection) {
        Ok(cases) => cases,
        Err(message) => {
            eprintln!("{message}");
            return 2;
        }
    };
    print!("{}", describe(&plan, &mutations));
    0
}

pub fn describe(plan: &Plan, mutations: &[MutationCase]) -> String {
    let selection = &plan.selection;
    let mut out = String::new();
    out.push_str(&format!("from: {}\n", plan.source));
    out.push_str(&format!("changed: {} path(s)\n", selection.changed.len()));
    for path in &selection.unknown {
        out.push_str(&format!(
            "unknown: {path} (not in {MAP_PATH}, so every area)\n"
        ));
    }
    if selection.changed.is_empty() {
        out.push_str("nothing changed, so nothing is selected\n");
        return out;
    }
    let areas = if selection.everything {
        "every area".to_string()
    } else if selection.areas.is_empty() {
        "none".to_string()
    } else {
        selection.areas.join(", ")
    };
    out.push_str(&format!("areas: {areas}\n"));
    match &plan.pytest {
        Pytest::Nothing => out.push_str("pytest: none\n"),
        Pytest::Everything(reason) => {
            out.push_str(&format!("pytest: the whole suite ({reason})\n"));
        }
        Pytest::Paths(paths) => {
            out.push_str(&format!("pytest: {} path(s)\n", paths.len()));
            for path in paths {
                out.push_str(&format!("  {path}\n"));
            }
        }
    }
    if selection.cargo.is_empty() {
        out.push_str("cargo: none\n");
    }
    for (dir, packages) in &selection.cargo {
        let packages: Vec<&str> = packages.iter().map(String::as_str).collect();
        out.push_str(&format!("cargo {dir}: {}\n", packages.join(" ")));
    }
    if mutations.is_empty() {
        out.push_str("mutations: none\n");
    } else {
        out.push_str(&format!("mutations: {} case(s)\n", mutations.len()));
        for case in mutations {
            out.push_str(&format!("  {} {}\n", case.spec, case.name));
        }
    }
    if selection.pictures.is_empty() {
        out.push_str("pictures: none\n");
    } else {
        out.push_str(&format!(
            "pictures: {} (each screen whose sources changed is drawn again)\n",
            selection.pictures.join(", ")
        ));
    }
    out
}
