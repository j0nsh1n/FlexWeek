//! The reminders the window keeps on screen (P4 group 7): the cards a student can Snooze or Close
//! (`desktop/native/kept_alerts.py`'s `KeptReminders`) and the queue of alarms ringing one at a time
//! (`desktop/native/controller.py`'s `_enqueue_alarm` and `finish_alarm`). The window holds the Qt
//! objects and signals; it reads the clock and today's blocks, passes them in, and says what the
//! answers tell it to.

use flexweek_engine::EngineResult;
use flexweek_engine::desk::remind::{
    reminder_snooze_until, reminder_start_min, reminder_stays, snooze_until,
};
use serde_json::{Map, Value, json};

const FALLBACK_TITLE: &str = "FlexWeek";

/// Python's `if value`, which the window's notices and alarms were read with.
fn truthy(value: &Value) -> bool {
    match value {
        Value::Null => false,
        Value::Bool(flag) => *flag,
        Value::Number(number) => number.as_f64().is_some_and(|number| number != 0.0),
        Value::String(text) => !text.is_empty(),
        Value::Array(items) => !items.is_empty(),
        Value::Object(fields) => !fields.is_empty(),
    }
}

/// Python's `str(value or "")`: nothing for a missing or empty field, the text for words, the JSON for
/// anything else.
fn words(value: Option<&Value>) -> String {
    match value {
        Some(Value::String(text)) => text.clone(),
        Some(other) if truthy(other) => other.to_string(),
        _ => String::new(),
    }
}

struct Card {
    key: String,
    title: String,
    body: String,
    /// The block's name when the card was made or last renamed, so a rename can swap just that part
    /// of the title.
    name: String,
    /// The minute a snoozed card comes back; `None` while it shows.
    until: Option<i64>,
}

impl Card {
    /// What a screen reader says when the card appears or comes back.
    fn say(&self) -> String {
        if self.body.is_empty() {
            self.title.clone()
        } else {
            format!("{} \u{2014} {}", self.title, self.body)
        }
    }
}

/// What adding a card did.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Added {
    /// The reminder is on screen now, new or already there.
    pub kept: bool,
    pub changed: bool,
    pub said: Option<String>,
}

/// What following the clock and the week did to the cards.
#[derive(Debug, Default, PartialEq, Eq)]
pub struct Synced {
    pub changed: bool,
    /// Words for each card that came back from Snooze, in order.
    pub said: Vec<String>,
    /// Keys whose card went because its block started, so "starts now" can take over.
    pub released: Vec<String>,
}

#[derive(Default)]
pub struct Cards {
    cards: Vec<Card>,
}

impl Cards {
    pub fn len(&self) -> usize {
        self.cards.len()
    }

    pub fn is_empty(&self) -> bool {
        self.cards.is_empty()
    }

    /// Keep this reminder as a card. `rows` is today's blocks as reminder key to block title, or `None`
    /// when they are not known (another week is open); `now_min` is the minute of the local day.
    pub fn add(
        &mut self,
        notice: &Value,
        rows: Option<&Value>,
        now_min: i64,
    ) -> EngineResult<Added> {
        let Some(key) = notice.get("key").and_then(Value::as_str) else {
            return Ok(Added::default());
        };
        let Some(block_title) = rows.and_then(|rows| rows.get(key)) else {
            return Ok(Added::default());
        };
        if !reminder_stays(reminder_start_min(key)?, now_min) {
            return Ok(Added::default());
        }
        if self.cards.iter().any(|card| card.key == key) {
            return Ok(Added {
                kept: true,
                ..Added::default()
            });
        }
        let mut title = words(notice.get("title"));
        if title.is_empty() {
            title = FALLBACK_TITLE.to_string();
        }
        let card = Card {
            key: key.to_string(),
            title,
            body: words(notice.get("body")),
            name: words(Some(block_title)),
            until: None,
        };
        let said = card.say();
        self.cards.push(card);
        Ok(Added {
            kept: true,
            changed: true,
            said: Some(said),
        })
    }

    /// The cards on screen, newest first; a snoozed one is not among them.
    pub fn visible(&self) -> Vec<Value> {
        self.cards
            .iter()
            .rev()
            .filter(|card| card.until.is_none())
            .map(|card| json!({ "key": card.key, "title": card.title, "body": card.body }))
            .collect()
    }

    /// Hide this key's card until it is due again; whether one was hidden.
    pub fn snooze(&mut self, key: &str, now_min: i64) -> EngineResult<bool> {
        let Some(card) = self
            .cards
            .iter_mut()
            .find(|card| card.key == key && card.until.is_none())
        else {
            return Ok(false);
        };
        card.until = Some(reminder_snooze_until(now_min, reminder_start_min(key)?));
        Ok(true)
    }

    pub fn close(&mut self, key: &str) -> bool {
        let before = self.cards.len();
        self.cards.retain(|card| card.key != key);
        self.cards.len() != before
    }

    pub fn clear(&mut self) -> bool {
        let had = !self.cards.is_empty();
        self.cards.clear();
        had
    }

    /// Follow the clock and the week: a card whose block started, moved or went is dropped, a snoozed
    /// one that is due comes back, and a renamed block's card shows the new name. `rows` as in `add`;
    /// with `None` nothing changes.
    pub fn sync(&mut self, rows: Option<&Value>, now_min: i64) -> EngineResult<Synced> {
        let Some(rows) = rows else {
            return Ok(Synced::default());
        };
        let mut told = Synced::default();
        let mut keep = Vec::with_capacity(self.cards.len());
        for card in &mut self.cards {
            let Some(block_title) = rows.get(card.key.as_str()) else {
                told.changed = true;
                keep.push(false);
                continue;
            };
            if !reminder_stays(reminder_start_min(&card.key)?, now_min) {
                told.released.push(card.key.clone());
                told.changed = true;
                keep.push(false);
                continue;
            }
            let name = words(Some(block_title));
            if name != card.name {
                let tail: String = card.title.chars().skip(card.name.chars().count()).collect();
                card.title = format!("{name}{tail}");
                card.name = name;
                told.changed = told.changed || card.until.is_none();
            }
            if let Some(until) = card.until
                && now_min >= until
            {
                card.until = None;
                told.changed = true;
                told.said.push(card.say());
            }
            keep.push(true);
        }
        let mut keep = keep.into_iter();
        self.cards.retain(|_| keep.next().unwrap_or(true));
        Ok(told)
    }
}

/// What finishing the ringing alarm did.
#[derive(Debug, Default, PartialEq)]
pub struct Finished {
    /// The alarm's id and the time it comes back, when it was snoozed.
    pub snoozed: Option<(String, i64)>,
    /// The alarm that rings next, if one was waiting.
    pub next: Option<Value>,
}

/// Alarms ring one at a time; the rest wait their turn.
#[derive(Default)]
pub struct AlarmQueue {
    active: Option<Value>,
    waiting: Vec<Value>,
    /// A block's song is in no list of alarms, so a snooze keeps it here to ring again.
    songs: Vec<(String, Value)>,
}

fn id_of(alarm: &Value) -> &Value {
    alarm.get("id").unwrap_or(&Value::Null)
}

impl AlarmQueue {
    /// Whether this alarm rings now. One already ringing or waiting, by id, changes nothing.
    pub fn enqueue(&mut self, alarm: Value) -> bool {
        let id = id_of(&alarm);
        if self
            .active
            .as_ref()
            .is_some_and(|active| id_of(active) == id)
        {
            return false;
        }
        if self.waiting.iter().any(|item| id_of(item) == id) {
            return false;
        }
        if self.active.is_none() {
            self.active = Some(alarm);
            return true;
        }
        self.waiting.push(alarm);
        false
    }

    /// The student dealt with the ringing alarm; the next one starts. A snooze is told as the alarm's id
    /// and when it comes back, from `now_ms`, and a block's song is kept to ring again or forgotten.
    pub fn finish(&mut self, snooze: bool, now_ms: i64) -> Finished {
        let alarm = self.active.take();
        let mut snoozed = None;
        if let Some(alarm) = &alarm
            && let Some(id) = alarm.get("id").and_then(Value::as_str)
        {
            if snooze {
                snoozed = Some((id.to_string(), snooze_until(now_ms)));
            }
            if alarm.get("block").is_some_and(truthy) {
                if snooze {
                    self.keep_song(id, alarm.clone());
                } else {
                    self.songs.retain(|(kept, _)| kept != id);
                }
            }
        }
        let next = if self.waiting.is_empty() {
            None
        } else {
            Some(self.waiting.remove(0))
        };
        self.active = next.clone();
        Finished { snoozed, next }
    }

    fn keep_song(&mut self, id: &str, alarm: Value) {
        match self.songs.iter_mut().find(|(kept, _)| kept == id) {
            Some((_, held)) => *held = alarm,
            None => self.songs.push((id.to_string(), alarm)),
        }
    }

    pub fn active(&self) -> Option<&Value> {
        self.active.as_ref()
    }

    pub fn waiting(&self) -> &[Value] {
        &self.waiting
    }

    /// The kept songs by alarm id, oldest first.
    pub fn songs(&self) -> Map<String, Value> {
        self.songs
            .iter()
            .map(|(id, alarm)| (id.clone(), alarm.clone()))
            .collect()
    }

    pub fn clear(&mut self) {
        self.active = None;
        self.waiting.clear();
        self.songs.clear();
    }
}
