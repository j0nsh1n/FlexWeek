//! The standing week: the School and activities Setup made, which every week from Setup's week on
//! has without the student copying them. Each standing block keeps the id Setup gave it (`school`,
//! `sport`, `activity-N`), the same in every week and on every device, so a week that holds a block
//! with that id holds its own version of it for that week.

use std::collections::HashSet;

use serde_json::Value;

use crate::EngineResult;
use crate::desk::grid::is_setup_block;
use crate::repeats::days_of;
use crate::shown::family_id;

fn id_of(block: &Value) -> Option<&str> {
    block.get("id").and_then(Value::as_str)
}

/// The block as it stands in every week: missed days belong to one week, never to the standing one.
pub fn standing_body(block: &Value) -> Value {
    let mut body = block.clone();
    if let Some(fields) = body.as_object_mut() {
        fields.shift_remove("missed_days");
    }
    body
}

/// A week as the student sees it: its own blocks, then each standing block it has no version of. A
/// piece of School split off at a week's seam is that week's version of School.
pub fn with_standing(stored: &[Value], standing: &[Value]) -> Vec<Value> {
    let held: HashSet<&str> = stored.iter().filter_map(id_of).map(family_id).collect();
    let mut week = stored.to_vec();
    week.extend(
        standing
            .iter()
            .filter(|block| id_of(block).is_some_and(|id| !held.contains(id)))
            .cloned(),
    );
    week
}

/// An account from before the standing week: its Setup blocks are those of the newest saved week that
/// has any, standing from that week. None when no week has a Setup block.
pub fn derive_standing(
    weeks: &[(String, Vec<Value>)],
) -> EngineResult<Option<(String, Vec<Value>)>> {
    let mut newest: Option<(String, Vec<Value>)> = None;
    for (week_start, blocks) in weeks {
        if newest
            .as_ref()
            .is_some_and(|(start, _)| start >= week_start)
        {
            continue;
        }
        let mut setup: Vec<Value> = Vec::new();
        // How many days the piece each standing block took its fields from held.
        let mut taken_from: Vec<usize> = Vec::new();
        for block in blocks {
            let Some(id) = id_of(block) else {
                continue;
            };
            if !is_setup_block(block)? {
                continue;
            }
            // School stands once, by its own id, however many pieces the week holds: on all their
            // days, as the piece holding the most of them has it (School's own id on a tie).
            let family = family_id(id);
            let days = days_of(block);
            let mut body = standing_body(block);
            body["id"] = Value::from(family);
            match setup.iter().position(|held| id_of(held) == Some(family)) {
                None => {
                    taken_from.push(days.len());
                    setup.push(body);
                }
                Some(at) => {
                    let mut all = days_of(&setup[at]);
                    for day in &days {
                        if !all.contains(day) {
                            all.push(*day);
                        }
                    }
                    all.sort_unstable();
                    if days.len() > taken_from[at] || (days.len() == taken_from[at] && id == family)
                    {
                        taken_from[at] = days.len();
                        setup[at] = body;
                    }
                    setup[at]["days"] = Value::from(all);
                }
            }
        }
        if !setup.is_empty() {
            newest = Some((week_start.clone(), setup));
        }
    }
    Ok(newest)
}
