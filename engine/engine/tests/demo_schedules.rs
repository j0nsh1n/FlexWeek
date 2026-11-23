//! The two demo schedules (Alex and Jordan, in backend/data) load as valid blocks that sit on the 15-minute
//! grid. The Rust twins of backend/tests/test_demo_schedules.py.

use flexweek_engine::time::hhmm_to_slot;
use flexweek_engine::validate::time_block;
use serde_json::Value;

const DEMOS: [&str; 2] = ["demo_alex.json", "demo_jordan.json"];

/// A demo's blocks, each read through the same check a saved block goes through.
fn blocks(name: &str) -> Vec<flexweek_engine::validate::TimeBlock> {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../backend/data")
        .join(name);
    let text = std::fs::read_to_string(&path).unwrap_or_else(|err| panic!("{name}: {err}"));
    let raw: Value = serde_json::from_str(&text).unwrap();
    raw.as_array()
        .unwrap()
        .iter()
        .map(|item| time_block(item).unwrap_or_else(|err| panic!("{name}: {err}")))
        .collect()
}

#[test]
fn each_demo_validates_with_locked_and_flexible_blocks() {
    for name in DEMOS {
        let blocks = blocks(name);
        assert!(blocks.iter().any(|b| b.kind == "locked"), "{name}");
        assert!(blocks.iter().any(|b| b.kind == "flexible"), "{name}");
        for block in blocks.iter().filter(|b| b.kind == "locked") {
            assert!(block.start.is_some(), "{name}: {}", block.id);
        }
    }
}

#[test]
fn each_demo_has_eight_flexible_blocks() {
    for name in DEMOS {
        let flexible = blocks(name).iter().filter(|b| b.kind == "flexible").count();
        assert_eq!(flexible, 8, "{name}");
    }
}

#[test]
fn locked_starts_are_on_the_grid() {
    for name in DEMOS {
        for block in blocks(name).iter().filter(|b| b.kind == "locked") {
            let start = block.start.as_deref().unwrap();
            assert_ne!(start, "23:00", "{name}: {}", block.id);
            assert!(hhmm_to_slot(start).unwrap() >= 0, "{name}: {}", block.id);
        }
    }
}

#[test]
fn durations_are_positive_multiples_of_15() {
    for name in DEMOS {
        for block in blocks(name) {
            assert!(block.duration_min > 0, "{name}: {}", block.id);
            assert_eq!(block.duration_min % 15, 0, "{name}: {}", block.id);
        }
    }
}
