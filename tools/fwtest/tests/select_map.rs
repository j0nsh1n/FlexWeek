//! The areas map and what changed paths select. Expected values come from the rules in
//! docs/tooling/fwtest.md ("Test selection") and spec.md's Testing structure rule 7.

use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

use fwtest::select::{Map, MutationCase, Pytest, matches, mutation_cases, pytest};

fn scratch(name: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!(
        "fwtest-select-{name}-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    fs::create_dir_all(&path).unwrap();
    path
}

fn write(path: &Path, text: &str) {
    fs::create_dir_all(path.parent().unwrap()).unwrap();
    fs::write(path, text).unwrap();
}

fn paths(list: &[&str]) -> Vec<String> {
    list.iter().map(|path| path.to_string()).collect()
}

const SMALL: &str = r#"
[[area]]
name = "week"
tests = ["desktop/tests/week/"]
pictures = true

[[area]]
name = "day"
tests = ["desktop/tests/day/"]
pictures = true

[[area]]
name = "unmoved"
tests = ["desktop/tests/test_*.py"]

[[area]]
name = "engine-sync"
cargo = { dir = "engine", packages = ["flexweek-sync", "flexweek-py"] }

[[area]]
name = "engine-mcp"
cargo = { dir = "engine", packages = ["flexweek-mcp", "flexweek-py"] }

[[rule]]
paths = ["desktop/native/window.py"]
everything = true

[[rule]]
paths = ["desktop/native/hours/classic.py"]
areas = ["week", "day"]

[[rule]]
paths = ["desktop/native/hours/", "desktop/tests/week/"]
areas = ["week"]

[[rule]]
paths = ["engine/sync/"]
areas = ["engine-sync"]

[[rule]]
paths = ["engine/mcp/"]
areas = ["engine-mcp"]

[[rule]]
paths = ["docs/", "scripts/mutations/"]
areas = []

[[also]]
paths = ["desktop/"]
areas = ["unmoved"]
"#;

#[test]
fn a_folder_pattern_matches_everything_under_it_and_not_the_folder_name_itself() {
    assert!(matches("desktop/native/", "desktop/native/window.py"));
    assert!(matches("desktop/native/", "desktop/native/hours/zoom.py"));
    assert!(!matches("desktop/native/", "desktop/native"));
    assert!(!matches("desktop/native/", "desktop/nativeish/window.py"));
}

#[test]
fn a_file_pattern_matches_one_path_and_star_stays_within_one_part() {
    assert!(matches("README.md", "README.md"));
    assert!(!matches("README.md", "docs/README.md"));
    assert!(matches(
        "desktop/tests/test_*.py",
        "desktop/tests/test_week.py"
    ));
    assert!(!matches(
        "desktop/tests/test_*.py",
        "desktop/tests/week/test_drag.py"
    ));
    assert!(!matches(
        "desktop/tests/test_*.py",
        "desktop/tests/conftest.py"
    ));
    assert!(matches("backend/*.py", "backend/app.py"));
    assert!(!matches("backend/*.py", "backend/tests/test_api.py"));
}

#[test]
fn the_first_matching_rule_decides_so_a_specific_rule_beats_a_general_one() {
    let map = Map::parse(SMALL).unwrap();
    let classic = map.select(&paths(&["desktop/native/hours/classic.py"]));
    assert_eq!(classic.areas, ["week", "day", "unmoved"]);
    let zoom = map.select(&paths(&["desktop/native/hours/zoom.py"]));
    assert_eq!(zoom.areas, ["week", "unmoved"]);
    assert!(!zoom.everything);
}

#[test]
fn a_path_no_rule_knows_selects_every_area_never_nothing() {
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&["somewhere/new.py"]));
    assert!(selection.everything);
    assert_eq!(selection.unknown, ["somewhere/new.py"]);
    assert_eq!(
        selection.areas,
        ["week", "day", "unmoved", "engine-sync", "engine-mcp"]
    );
}

#[test]
fn an_also_rule_adds_areas_but_does_not_make_a_path_known() {
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&["desktop/native/brand_new.py"]));
    assert!(selection.everything, "desktop/ is only an also rule");
    assert_eq!(selection.unknown, ["desktop/native/brand_new.py"]);
}

#[test]
fn a_rule_that_marks_everything_selects_every_area_without_calling_the_path_unknown() {
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&["desktop/native/window.py"]));
    assert!(selection.everything);
    assert!(selection.unknown.is_empty());
    assert_eq!(selection.pictures, ["week", "day"]);
}

#[test]
fn a_known_path_with_no_tests_selects_nothing() {
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&["docs/testing/structure.md"]));
    assert!(!selection.everything);
    assert!(selection.areas.is_empty());
    assert!(selection.tests.is_empty());
    assert!(selection.cargo.is_empty());
}

#[test]
fn cargo_packages_of_several_areas_merge_by_workspace() {
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&[
        "engine/sync/src/lib.rs",
        "engine/mcp/src/main.rs",
    ]));
    assert_eq!(selection.cargo.len(), 1);
    let engine: Vec<&str> = selection.cargo["engine"]
        .iter()
        .map(String::as_str)
        .collect();
    assert_eq!(engine, ["flexweek-mcp", "flexweek-py", "flexweek-sync"]);
    assert!(selection.tests.is_empty());
    assert!(selection.pictures.is_empty());
}

#[test]
fn no_changed_paths_select_nothing() {
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&[]);
    assert!(!selection.everything);
    assert!(selection.areas.is_empty());
}

#[test]
fn a_map_with_mistakes_is_refused_with_the_mistake_named() {
    let unknown = "[[area]]\nname = \"week\"\ntests = [\"a/\"]\n[[rule]]\npaths = [\"x/\"]\nareas = [\"nope\"]\n";
    assert!(
        Map::parse(unknown)
            .unwrap_err()
            .contains("unknown area nope")
    );
    let both = "[[area]]\nname = \"week\"\ntests = [\"a/\"]\n[[rule]]\npaths = [\"x/\"]\nareas = [\"week\"]\neverything = true\n";
    assert!(
        Map::parse(both)
            .unwrap_err()
            .contains("both areas and everything")
    );
    let neither = "[[area]]\nname = \"week\"\ntests = [\"a/\"]\n[[rule]]\npaths = [\"x/\"]\n";
    assert!(Map::parse(neither).unwrap_err().contains("needs areas"));
    let twice = "[[area]]\nname = \"week\"\ntests = [\"a/\"]\n[[area]]\nname = \"week\"\ntests = [\"b/\"]\n";
    assert!(Map::parse(twice).unwrap_err().contains("defined twice"));
    let absolute =
        "[[area]]\nname = \"week\"\ntests = [\"a/\"]\n[[rule]]\npaths = [\"/etc/\"]\nareas = []\n";
    assert!(
        Map::parse(absolute)
            .unwrap_err()
            .contains("bad path pattern")
    );
    let typo = "[[area]]\nname = \"week\"\ntest = [\"a/\"]\n";
    assert!(Map::parse(typo).is_err());
}

#[test]
fn pytest_gets_only_the_selected_paths_that_exist_with_globs_expanded_in_order() {
    let repo = scratch("pytest-paths");
    write(&repo.join("desktop/tests/week/test_drag.py"), "");
    write(&repo.join("desktop/tests/test_b.py"), "");
    write(&repo.join("desktop/tests/test_a.py"), "");
    write(&repo.join("desktop/tests/conftest.py"), "");
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&["desktop/native/hours/classic.py"]));
    let wanted = paths(&[
        "desktop/tests/week",
        "desktop/tests/test_a.py",
        "desktop/tests/test_b.py",
    ]);
    assert_eq!(pytest(&repo, &selection), Pytest::Paths(wanted));
    let _ = fs::remove_dir_all(repo);
}

#[test]
fn selected_areas_whose_tests_do_not_exist_yet_run_the_whole_suite() {
    let repo = scratch("pytest-missing");
    let map = Map::parse(SMALL).unwrap();
    let selection = map.select(&paths(&["desktop/native/hours/classic.py"]));
    assert!(matches!(pytest(&repo, &selection), Pytest::Everything(_)));
    let _ = fs::remove_dir_all(repo);
}

#[test]
fn a_selection_without_pytest_areas_runs_no_pytest() {
    let repo = scratch("pytest-none");
    let map = Map::parse(SMALL).unwrap();
    let docs = map.select(&paths(&["docs/x.md"]));
    assert_eq!(pytest(&repo, &docs), Pytest::Nothing);
    let engine = map.select(&paths(&["engine/sync/src/lib.rs"]));
    assert_eq!(pytest(&repo, &engine), Pytest::Nothing);
    let everything = map.select(&paths(&["desktop/native/window.py"]));
    assert!(matches!(pytest(&repo, &everything), Pytest::Everything(_)));
    let _ = fs::remove_dir_all(repo);
}

#[test]
fn mutation_cases_follow_their_spec_their_source_file_and_their_test_file() {
    let repo = scratch("mutations");
    write(
        &repo.join("scripts/mutations/look.json"),
        r#"[
  {"name": "tint", "file": "desktop/native/look.py", "old": "a", "new": "b", "test": "desktop/tests/test_look.py::test_tint"},
  {"name": "zoom", "file": "desktop/native/hours/zoom.py", "old": "a", "new": "b", "test": "desktop/tests/week/test_zoom.py::test_zoom"},
  {"name": "solver", "file": "engine/engine/src/solver.rs", "old": "a", "new": "b", "test": "cargo:flexweek-engine:test_solver:test_x"}
]"#,
    );
    write(
        &repo.join("scripts/mutations/month.json"),
        r#"[{"name": "fill", "file": "desktop/native/hours/month.py", "old": "a", "new": "b", "test": "desktop/tests/month/test_fill.py::test_fill"}]"#,
    );
    let map = Map::parse(SMALL).unwrap();
    let case = |spec: &str, name: &str| MutationCase {
        spec: spec.to_string(),
        name: name.to_string(),
    };

    let by_source = map.select(&paths(&["desktop/native/hours/month.py"]));
    assert!(!by_source.everything);
    assert_eq!(
        mutation_cases(&repo, &by_source).unwrap(),
        [case("month.json", "fill")]
    );

    let by_test = map.select(&paths(&["desktop/tests/week/test_zoom.py"]));
    assert!(!by_test.everything);
    assert_eq!(
        mutation_cases(&repo, &by_test).unwrap(),
        [case("look.json", "zoom")]
    );

    let by_spec = map.select(&paths(&["scripts/mutations/month.json"]));
    assert!(!by_spec.everything);
    assert_eq!(
        mutation_cases(&repo, &by_spec).unwrap(),
        [case("month.json", "fill")]
    );

    let everything = map.select(&paths(&["desktop/native/window.py"]));
    assert_eq!(mutation_cases(&repo, &everything).unwrap().len(), 4);

    let docs = map.select(&paths(&["docs/x.md"]));
    assert!(mutation_cases(&repo, &docs).unwrap().is_empty());
    let _ = fs::remove_dir_all(repo);
}

// --- The committed map.

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR")).join("../..")
}

fn committed() -> Map {
    Map::load(&repo_root()).expect("tools/fwtest/areas.toml parses")
}

fn screen_areas() -> BTreeSet<String> {
    let text = fs::read_to_string(repo_root().join("desktop/tests/pictures/screen.py")).unwrap();
    let start = text.find("AREAS = (").expect("screen.py has AREAS") + "AREAS = (".len();
    let end = start + text[start..].find(')').unwrap();
    text[start..end]
        .split(',')
        .map(|item| item.trim().trim_matches('"').to_string())
        .filter(|item| !item.is_empty())
        .collect()
}

#[test]
fn the_committed_maps_picture_areas_are_the_screen_contracts_areas() {
    let map = committed();
    let pictures: BTreeSet<String> = map
        .areas()
        .iter()
        .filter(|area| area.pictures)
        .map(|area| area.name.clone())
        .collect();
    let wanted = screen_areas();
    assert_eq!(wanted.len(), 12, "{wanted:?}");
    assert_eq!(pictures, wanted);
    for area in map.areas().iter().filter(|area| area.pictures) {
        assert_eq!(area.tests, [format!("desktop/tests/{}/", area.name)]);
    }
}

fn product_files(folder: &Path, prefix: &str, found: &mut Vec<String>) {
    for entry in fs::read_dir(folder).unwrap().filter_map(Result::ok) {
        let name = entry.file_name().to_string_lossy().into_owned();
        let path = format!("{prefix}{name}");
        let kind = entry.file_type().unwrap();
        if kind.is_dir() {
            if name != "__pycache__" {
                product_files(&entry.path(), &format!("{path}/"), found);
            }
        } else if !name.ends_with(".pyc") {
            found.push(path);
        }
    }
}

#[test]
fn every_desktop_and_backend_product_file_is_known_to_the_committed_map() {
    let map = committed();
    let root = repo_root();
    let mut files = Vec::new();
    product_files(&root.join("desktop/native"), "desktop/native/", &mut files);
    for entry in fs::read_dir(root.join("backend"))
        .unwrap()
        .filter_map(Result::ok)
    {
        let name = entry.file_name().to_string_lossy().into_owned();
        if name.ends_with(".py") {
            files.push(format!("backend/{name}"));
        }
    }
    assert!(files.len() > 50, "{files:?}");
    let unknown: Vec<&String> = files
        .iter()
        .filter(|file| !map.select(std::slice::from_ref(*file)).unknown.is_empty())
        .collect();
    assert!(
        unknown.is_empty(),
        "add these to tools/fwtest/areas.toml: {unknown:?}"
    );
}

#[test]
fn shared_plumbing_and_test_foundations_select_every_area() {
    let map = committed();
    for path in [
        "desktop/native/window.py",
        "desktop/native/controller.py",
        "desktop/tests/light_app.py",
        "desktop/tests/conftest.py",
        "desktop/tests/waiting.py",
        "backend/tests/fake_clock.py",
        "conftest.py",
        "requirements-desktop.txt",
        "engine/engine/src/solver.rs",
    ] {
        let selection = map.select(&paths(&[path]));
        assert!(selection.everything, "{path}");
        assert!(selection.unknown.is_empty(), "{path} is known");
    }
}

#[test]
fn an_area_file_selects_its_area_and_the_unmoved_desktop_files() {
    let map = committed();
    let focus = map.select(&paths(&["desktop/native/focus_screen.py"]));
    assert!(!focus.everything);
    assert_eq!(focus.areas, ["focus", "unmoved"]);
    assert_eq!(focus.pictures, ["focus"]);
    let week_test = map.select(&paths(&["desktop/tests/week/test_drag_a_block.py"]));
    assert_eq!(week_test.areas, ["week", "unmoved"]);
    let solver = map.select(&paths(&["backend/solver.py"]));
    assert_eq!(solver.areas, ["planner", "backend", "unmoved"]);
    let backend_test = map.select(&paths(&["backend/tests/test_api.py"]));
    assert_eq!(backend_test.areas, ["backend"]);
}

#[test]
fn harness_engine_crates_and_prose_select_what_they_test() {
    let map = committed();
    let harness = map.select(&paths(&["tools/fwtest/src/gate.rs"]));
    assert_eq!(harness.areas, ["fwtest"]);
    assert_eq!(
        harness.cargo["tools/fwtest"].iter().collect::<Vec<_>>(),
        ["fwtest"]
    );
    let sync = map.select(&paths(&["engine/sync/src/merge.rs"]));
    let packages: Vec<&str> = sync.cargo["engine"].iter().map(String::as_str).collect();
    assert_eq!(
        packages,
        [
            "flexweek-ffi",
            "flexweek-mcp",
            "flexweek-py",
            "flexweek-sync"
        ]
    );
    assert!(sync.areas.contains(&"sync".to_string()));
    let prose = map.select(&paths(&["docs/testing/structure.md", "spec.md"]));
    assert!(prose.areas.is_empty() && !prose.everything);
    let unknown = map.select(&paths(&["somewhere/else.txt"]));
    assert!(unknown.everything);
}
