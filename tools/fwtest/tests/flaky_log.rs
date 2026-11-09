//! Reading pytest's JUnit report and the flaky-test log. Expected values come from the rules in
//! docs/tooling/fwtest.md ("Flaky tests").

use std::fs;
use std::path::{Path, PathBuf};

use fwtest::flaky::{Beside, Entry, append, failed_tests, pytest_prefix, report_totals, summarise};

fn scratch(name: &str) -> PathBuf {
    let path = std::env::temp_dir().join(format!(
        "fwtest-flaky-{name}-{}-{}",
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

const XUNIT1: &str = r#"<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="1" failures="1" skipped="1" tests="5" time="3.2">
<testcase classname="desktop.tests.week.test_drag.TestDrop" name="test_drop_lands[early-9:00]" file="desktop/tests/week/test_drag.py" line="12" time="0.4"><failure message="assert 3 == 4">def test_drop_lands():
&gt;   assert blocks == 4
E   assert 3 == 4</failure></testcase>
<testcase classname="desktop.tests.week.test_drag" name="test_passes" file="desktop/tests/week/test_drag.py" line="30" time="0.1" />
<testcase classname="backend.tests.test_api" name="test_setup_breaks" file="backend/tests/test_api.py" line="5" time="0.0"><error message="failed on setup with &quot;KeyError: &apos;x&apos;&quot;">fixture went wrong</error></testcase>
<testcase classname="backend.tests.test_api" name="test_skipped" file="backend/tests/test_api.py" line="9" time="0.0"><skipped message="not today" /></testcase>
<testcase classname="backend.tests.test_api" name="test_ok" file="backend/tests/test_api.py" line="11" time="0.0"></testcase>
</testsuite></testsuites>
"#;

#[test]
fn failed_and_errored_tests_become_node_ids_with_how_they_failed() {
    let failed = failed_tests(XUNIT1, Path::new("/nowhere"));
    let ids: Vec<&str> = failed.iter().map(|test| test.id.as_str()).collect();
    assert_eq!(
        ids,
        [
            "desktop/tests/week/test_drag.py::TestDrop::test_drop_lands[early-9:00]",
            "backend/tests/test_api.py::test_setup_breaks",
        ]
    );
    assert!(
        failed[0].how.starts_with("assert 3 == 4\n"),
        "{}",
        failed[0].how
    );
    assert!(
        failed[0].how.contains(">   assert blocks == 4"),
        "{}",
        failed[0].how
    );
    assert!(
        failed[1]
            .how
            .starts_with("failed on setup with \"KeyError: 'x'\""),
        "{}",
        failed[1].how
    );
}

#[test]
fn a_report_without_file_attributes_finds_the_module_in_the_checkout() {
    let repo = scratch("xunit2");
    write(&repo.join("desktop/tests/test_look.py"), "");
    let report = r#"<testsuites><testsuite tests="1">
<testcase classname="desktop.tests.test_look.TestTint" name="test_tint" time="0.1"><failure message="boom">x</failure></testcase>
<testcase classname="desktop.tests.test_look" name="test_plain" time="0.1"><failure message="boom">y</failure></testcase>
</testsuite></testsuites>"#;
    let ids: Vec<String> = failed_tests(report, &repo)
        .into_iter()
        .map(|test| test.id)
        .collect();
    assert_eq!(
        ids,
        [
            "desktop/tests/test_look.py::TestTint::test_tint",
            "desktop/tests/test_look.py::test_plain",
        ]
    );
    let _ = fs::remove_dir_all(repo);
}

#[test]
fn report_totals_add_up_every_suite_and_ignore_the_wrapper() {
    assert_eq!(report_totals(XUNIT1), (5, 1));
    let two = r#"<testsuites tests="99"><testsuite tests="3" skipped="0"></testsuite><testsuite tests="4" skipped="2"></testsuite></testsuites>"#;
    assert_eq!(report_totals(two), (7, 2));
}

#[test]
fn a_pytest_command_is_recognised_and_cut_where_its_arguments_start() {
    let words = |text: &str| -> Vec<String> { text.split(' ').map(String::from).collect() };
    assert_eq!(
        pytest_prefix(&words(".venv/bin/python -m pytest -q -n 4 desktop/tests")),
        Some(words(".venv/bin/python -m pytest"))
    );
    assert_eq!(
        pytest_prefix(&words("/usr/bin/pytest -q")),
        Some(words("/usr/bin/pytest"))
    );
    assert_eq!(pytest_prefix(&words(".venv/bin/python scripts/x.py")), None);
    assert_eq!(pytest_prefix(&words("cargo test")), None);
}

fn entry(test: &str, date: &str, how: &str) -> Entry {
    Entry {
        test: test.to_string(),
        date: date.to_string(),
        commit: "abcdef1234567890".to_string(),
        place: "local".to_string(),
        how: how.to_string(),
        beside: Beside {
            command: "python -m pytest -n 8".to_string(),
            tests_in_run: 100,
            other_failures: Vec::new(),
        },
    }
}

#[test]
fn the_summary_puts_the_most_frequent_first_then_the_most_recent() {
    let path = scratch("summary").join("flaky.jsonl");
    for item in [
        entry("a::once_old", "2026-11-01T10:00:00Z", "old"),
        entry("b::twice", "2026-11-02T10:00:00Z", "first"),
        entry("c::once_new", "2026-11-05T10:00:00Z", "new"),
        entry("b::twice", "2026-11-04T10:00:00Z", "second\nmore"),
    ] {
        append(&path, &item).unwrap();
    }
    let mut text = fs::read_to_string(&path).unwrap();
    text.push_str("not json\n\n");
    let (summaries, bad) = summarise(&text);
    let order: Vec<(&str, usize)> = summaries
        .iter()
        .map(|summary| (summary.test.as_str(), summary.count))
        .collect();
    assert_eq!(
        order,
        [("b::twice", 2), ("c::once_new", 1), ("a::once_old", 1)]
    );
    assert_eq!(summaries[0].last.how, "second\nmore");
    assert_eq!(summaries[0].last.date, "2026-11-04T10:00:00Z");
    assert_eq!(bad, 1);
    let _ = fs::remove_dir_all(path.parent().unwrap());
}

#[test]
fn each_log_line_is_one_json_object_with_the_fields_the_contract_names() {
    let path = scratch("fields").join("deep/flaky.jsonl");
    append(&path, &entry("x::y", "2026-11-07T08:00:00Z", "boom")).unwrap();
    let text = fs::read_to_string(&path).unwrap();
    assert_eq!(text.lines().count(), 1);
    let value: serde_json::Value = serde_json::from_str(text.trim()).unwrap();
    for key in ["test", "date", "commit", "place", "how", "beside"] {
        assert!(value.get(key).is_some(), "{key} missing in {text}");
    }
    for key in ["command", "tests_in_run", "other_failures"] {
        assert!(value["beside"].get(key).is_some(), "beside.{key} missing");
    }
    let _ = fs::remove_dir_all(path.parent().unwrap().parent().unwrap());
}
