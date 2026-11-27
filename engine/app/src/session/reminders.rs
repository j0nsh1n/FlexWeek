//! The reminders the window keeps on screen (P4 group 7): the cards a student can Snooze or Close
//! (`desktop/native/kept_alerts.py`'s `KeptReminders`), the queue of alarms ringing one at a time
//! (`desktop/native/controller.py`'s `_enqueue_alarm` and `finish_alarm`), and the block alerts,
//! today's reminder source, the kept-alert strip and the Spotify link check. The window holds the Qt
//! objects and signals; it reads the clock, the parked week and the sets, passes them in, and says
//! what the answers tell it to.

use flexweek_engine::desk::grid::monday_of;
use flexweek_engine::desk::remind::{
    REMINDER_LEAD_DEFAULT_MIN, due_alarms, due_reminders, due_songs, reminder_lead_min,
    reminder_snooze_until, reminder_start_min, reminder_stays, snooze_until, todays_starts,
};
use flexweek_engine::model::valid_spotify_url;
use flexweek_engine::stored::{self, attribute_error, type_name};
use flexweek_engine::{EngineError, EngineResult, ErrorKind};
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

fn type_error(message: impl Into<String>) -> EngineError {
    EngineError {
        kind: ErrorKind::Type,
        message: message.into(),
    }
}

fn json_null() -> &'static Value {
    static NULL: Value = Value::Null;
    &NULL
}

/// `for item in value`, or `*value`: a list's items, a string's characters, a dict's keys.
fn python_list(value: &Value, starred: bool) -> EngineResult<Vec<Value>> {
    match value {
        Value::Array(items) => Ok(items.clone()),
        Value::String(text) => Ok(text.chars().map(|ch| Value::from(ch.to_string())).collect()),
        Value::Object(map) if stored::nonfinite(value).is_none() => {
            Ok(map.keys().cloned().map(Value::from).collect())
        }
        other if starred => Err(type_error(format!(
            "Value after * must be an iterable, not {}",
            type_name(other)
        ))),
        other => Err(type_error(format!(
            "'{}' object is not iterable",
            type_name(other)
        ))),
    }
}

/// What the strip says after a change. `handled` is set only when a drop leaves it empty.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct StripView {
    pub text: String,
    pub handled: bool,
}

/// Notices kept in the window until the student deals with them, oldest first.
#[derive(Debug, Default, Clone, PartialEq, Eq)]
pub struct AlertStrip {
    notices: Vec<Value>,
    text: String,
}

impl AlertStrip {
    pub fn pending(&self) -> usize {
        self.notices.len()
    }

    pub fn text(&self) -> &str {
        &self.text
    }

    pub fn add(&mut self, notices: &[Value]) -> EngineResult<StripView> {
        self.notices.extend(notices.iter().cloned());
        self.render(false)
    }

    pub fn clear(&mut self) -> StripView {
        self.notices.clear();
        self.text.clear();
        StripView {
            text: String::new(),
            handled: false,
        }
    }

    /// Drop the oldest notice. An empty strip is already dealt with.
    pub fn drop(&mut self) -> EngineResult<StripView> {
        if !self.notices.is_empty() {
            self.notices.remove(0);
        }
        self.render(self.notices.is_empty())
    }

    fn render(&mut self, handled: bool) -> EngineResult<StripView> {
        let text = self.line()?;
        self.text.clone_from(&text);
        Ok(StripView { text, handled })
    }

    fn line(&self) -> EngineResult<String> {
        let Some(notice) = self.notices.first() else {
            return Ok(String::new());
        };
        let fields = notice
            .as_object()
            .ok_or_else(|| attribute_error(notice, "get"))?;
        let mut title = words(fields.get("title"));
        if title.is_empty() {
            title = FALLBACK_TITLE.to_string();
        }
        let body = words(fields.get("body"));
        let more = if self.notices.len() > 1 {
            format!("  (+{} more)", self.notices.len() - 1)
        } else {
            String::new()
        };
        if body.is_empty() {
            Ok(format!("{title}{more}"))
        } else {
            Ok(format!("{title} \u{2014} {body}{more}"))
        }
    }
}

/// The open week the window is showing, when the caller has one.
pub struct OpenWeek<'a> {
    pub week_start: Option<&'a str>,
    pub blocks: &'a Value,
    pub trace: &'a Value,
}

/// Today's open week, or nothing when another week is on screen. The parked week is not read here:
/// looking it up writes drafts, and that only happens once this says the open week is not today.
pub fn open_reminder_source<'a>(
    open: OpenWeek<'a>,
    today_monday: &str,
) -> Option<(&'a Value, &'a Value)> {
    if open.week_start == Some(today_monday) {
        Some((open.blocks, open.trace))
    } else {
        None
    }
}

/// The parked week when there is one, else the cached fetch when it is this week. `parked` is the
/// week object, or null when the draft has none. A parked week with no `blocks` is a `KeyError`.
pub fn parked_or_cached_source<'a>(
    parked: &'a Value,
    cached_week: Option<&str>,
    cached_blocks: &'a Value,
    cached_trace: &'a Value,
    today_monday: &str,
) -> EngineResult<Option<(&'a Value, &'a Value)>> {
    if !parked.is_null() {
        let week = parked_week(parked)?;
        let blocks = week
            .get("blocks")
            .ok_or_else(|| EngineError::key("blocks"))?;
        let trace = week.get("trace").unwrap_or_else(|| json_null());
        return Ok(Some((blocks, trace)));
    }
    if cached_week == Some(today_monday) {
        return Ok(Some((cached_blocks, cached_trace)));
    }
    Ok(None)
}

fn parked_week(parked: &Value) -> EngineResult<&Map<String, Value>> {
    match parked {
        Value::Object(map) if stored::nonfinite(parked).is_none() => Ok(map),
        Value::Array(_) => Err(type_error(
            "list indices must be integers or slices, not str",
        )),
        Value::String(_) => Err(type_error("string indices must be integers, not 'str'")),
        other => Err(type_error(format!(
            "'{}' object is not subscriptable",
            type_name(other)
        ))),
    }
}

/// Today's blocks by reminder key. A later row with the same key replaces the earlier one.
pub fn todays_reminder_blocks(
    blocks: &Value,
    trace: &Value,
    today_iso: &str,
) -> EngineResult<Map<String, Value>> {
    let mut rows = Map::new();
    for (block, _day, _start, key) in todays_starts(blocks, trace, today_iso)? {
        rows.insert(key, block);
    }
    Ok(rows)
}

/// `prefs.get(name)` after `preferences or {}`. A missing preferences value does not ask `.get`.
fn pref_field<'a>(prefs: &'a Value, name: &str) -> EngineResult<Option<&'a Value>> {
    if !stored::truthy(Some(prefs)) {
        return Ok(None);
    }
    match prefs {
        Value::Object(map) if stored::nonfinite(prefs).is_none() => Ok(map.get(name)),
        other => Err(attribute_error(other, "get")),
    }
}

/// Whether block reminders run. Alarms do not ask this.
pub fn block_reminders_on(prefs: &Value) -> EngineResult<bool> {
    Ok(stored::truthy(pref_field(prefs, "reminders_enabled")?))
}

/// The Monday `check_alerts` asks about, or nothing when block reminders are off (no parked lookup,
/// no fetch).
pub fn check_alerts_begin(prefs: &Value, today_iso: &str) -> EngineResult<Option<String>> {
    if !block_reminders_on(prefs)? {
        return Ok(None);
    }
    Ok(Some(monday_of(today_iso)?))
}

/// Whether a cached fetch should still announce today's blocks. The Monday compare is the same one
/// `check_alerts` uses, so a reply that lands after midnight does not announce yesterday.
pub fn cached_reminders_due(
    prefs: &Value,
    today_iso: &str,
    today_monday: &str,
) -> EngineResult<bool> {
    Ok(block_reminders_on(prefs)? && monday_of(today_iso)? == today_monday)
}

/// Copies of the blocks and trace with a stored Spotify link cleared, plus the Settings link the
/// due checks are allowed to play.
pub struct PreparedAlerts {
    blocks: Value,
    trace: Value,
    lead: i64,
    link: Value,
    spotify: bool,
}

/// A link stored on a block stays in the week. The copies handed to the due checks have that field
/// cleared, so a block start uses the Settings link, and only when the alarm sound is Spotify.
pub fn prepare_block_alerts(
    blocks: &Value,
    trace: &Value,
    prefs: &Value,
) -> EngineResult<PreparedAlerts> {
    let lead = lead_minutes(prefs)?;
    let blocks = quiet_blocks(blocks)?;
    let trace = quiet_trace(trace)?;
    let link = settings_link(prefs)?;
    let spotify = matches!(
        pref_field(prefs, "alarm_tone")?,
        Some(Value::String(tone)) if tone == "spotify"
    );
    Ok(PreparedAlerts {
        blocks,
        trace,
        lead,
        link,
        spotify,
    })
}

fn lead_minutes(prefs: &Value) -> EngineResult<i64> {
    let lead = reminder_lead_min(prefs, REMINDER_LEAD_DEFAULT_MIN)?;
    i64::try_from(lead)
        .map_err(|_| EngineError::overflow("Python int too large to convert to C long"))
}

/// `item.get("spotify_url")` keeps a falsy link as it was. Only a link that would play is cleared,
/// and only on the copy.
fn quiet_copy(item: &Value) -> EngineResult<Value> {
    let map = item
        .as_object()
        .ok_or_else(|| attribute_error(item, "get"))?;
    if !stored::truthy(map.get("spotify_url")) {
        return Ok(item.clone());
    }
    let mut copy = map.clone();
    copy.insert("spotify_url".to_string(), Value::Null);
    Ok(Value::Object(copy))
}

fn quiet_blocks(blocks: &Value) -> EngineResult<Value> {
    let mut copies = Vec::new();
    for block in python_list(blocks, false)? {
        copies.push(quiet_copy(&block)?);
    }
    Ok(Value::Array(copies))
}

fn quiet_trace(trace: &Value) -> EngineResult<Value> {
    let Value::Object(map) = trace else {
        return Ok(trace.clone());
    };
    if stored::nonfinite(trace).is_some() {
        return Ok(trace.clone());
    }
    let Some(Value::Array(placed)) = map.get("placed") else {
        return Ok(trace.clone());
    };
    let mut copies = Vec::with_capacity(placed.len());
    for item in placed {
        if item.is_object() {
            copies.push(quiet_copy(item)?);
        } else {
            copies.push(item.clone());
        }
    }
    let mut copy = map.clone();
    copy.insert("placed".to_string(), Value::Array(copies));
    Ok(Value::Object(copy))
}

fn settings_link(prefs: &Value) -> EngineResult<Value> {
    let Some(raw) = pref_field(prefs, "default_spotify_url")? else {
        return Ok(Value::Null);
    };
    if !stored::truthy(Some(raw)) {
        return Ok(Value::Null);
    }
    let Value::String(text) = raw else {
        return Err(spotify_type(raw));
    };
    match valid_spotify_url(Some(text)) {
        Ok(Some(url)) => Ok(Value::from(url)),
        Ok(None) => Ok(Value::Null),
        Err(error) if error.kind == ErrorKind::Value => Ok(Value::Null),
        Err(error) => Err(error),
    }
}

fn spotify_type(value: &Value) -> EngineError {
    type_error(format!(
        "expected string or bytes-like object, got '{}'",
        type_name(value)
    ))
}

/// A set the caller holds, written as the list of its members, and whether `.add` is allowed.
pub struct Membership<'a> {
    pub values: &'a Value,
    pub is_set: bool,
}

/// Notices and songs for blocks that are due. The fired and played keys are the ones the caller
/// adds to its sets; notices are added before songs are read, so a failure in the songs keeps the
/// notices' keys.
#[derive(Debug, Clone, PartialEq)]
pub struct BlockAlerts {
    pub notices: Vec<Value>,
    pub songs: Vec<Value>,
    pub fired: Vec<String>,
    pub played: Vec<String>,
}

pub fn block_notices(
    prepared: &PreparedAlerts,
    today_iso: &str,
    now_min: i64,
    fired: Membership<'_>,
) -> EngineResult<(Vec<Value>, Vec<String>)> {
    let due = due_reminders(
        &prepared.blocks,
        &prepared.trace,
        today_iso,
        now_min,
        prepared.lead,
        fired.values,
        fired.is_set,
        &prepared.link,
        prepared.spotify,
    )?;
    let mut notices = Vec::with_capacity(due.len());
    let mut keys = Vec::with_capacity(due.len());
    for item in due {
        let key = item
            .get("key")
            .and_then(Value::as_str)
            .ok_or_else(|| EngineError::key("key"))?
            .to_string();
        notices.push(json!({
            "title": item.get("title").cloned().unwrap_or(Value::Null),
            "body": item.get("body").cloned().unwrap_or(Value::Null),
            "kind": "reminder",
            "key": key,
        }));
        keys.push(key);
    }
    Ok((notices, keys))
}

pub fn block_songs(
    prepared: &PreparedAlerts,
    today_iso: &str,
    now_min: i64,
    played: Membership<'_>,
) -> EngineResult<(Vec<Value>, Vec<String>)> {
    let due = due_songs(
        &prepared.blocks,
        &prepared.trace,
        today_iso,
        now_min,
        prepared.lead,
        played.values,
        played.is_set,
        &prepared.link,
        prepared.spotify,
    )?;
    let mut ids = Vec::with_capacity(due.len());
    for song in &due {
        ids.push(
            song.get("id")
                .and_then(Value::as_str)
                .ok_or_else(|| EngineError::key("id"))?
                .to_string(),
        );
    }
    Ok((due, ids))
}

pub fn due_block_alerts(
    blocks: &Value,
    trace: &Value,
    today_iso: &str,
    now_min: i64,
    prefs: &Value,
    fired: Membership<'_>,
    played: Membership<'_>,
) -> EngineResult<BlockAlerts> {
    let prepared = prepare_block_alerts(blocks, trace, prefs)?;
    let (notices, fired_keys) = block_notices(&prepared, today_iso, now_min, fired)?;
    let (songs, played_ids) = block_songs(&prepared, today_iso, now_min, played)?;
    Ok(BlockAlerts {
        notices,
        songs,
        fired: fired_keys,
        played: played_ids,
    })
}

/// Whether to ask the server for today's week. The same Monday already in flight is not asked again.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FetchBegin {
    pub send: bool,
    pub fetching: String,
    pub ticket: i64,
}

pub fn reminder_fetch_begin(
    fetching: Option<&str>,
    ticket: i64,
    today_monday: &str,
) -> EngineResult<FetchBegin> {
    if fetching == Some(today_monday) {
        return Ok(FetchBegin {
            send: false,
            fetching: today_monday.to_string(),
            ticket,
        });
    }
    let ticket = ticket
        .checked_add(1)
        .ok_or_else(|| EngineError::overflow("Python int too large to convert to C long"))?;
    Ok(FetchBegin {
        send: true,
        fetching: today_monday.to_string(),
        ticket,
    })
}

/// What a fetch reply is allowed to do. `need_parked` is false when the open week is already today,
/// so the reply does not look the parked week up.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct FetchGate {
    pub ignore: bool,
    pub need_parked: bool,
}

pub fn reminder_fetch_gate(
    token: i64,
    ticket: i64,
    account: &Value,
    week_start: &Value,
    today_monday: &str,
) -> FetchGate {
    if token != ticket || account.is_null() {
        return FetchGate {
            ignore: true,
            need_parked: false,
        };
    }
    FetchGate {
        ignore: false,
        need_parked: week_start.as_str() != Some(today_monday),
    }
}

/// A reply that is still the one in flight: reuse a week already here, or keep what the server sent.
#[derive(Debug, Clone, PartialEq)]
pub enum FetchApply {
    Reuse,
    Cache { week: Value, blocks: Vec<Value> },
}

pub fn reminder_fetch_apply(
    need_parked: bool,
    parked: &Value,
    data: &Value,
    today_monday: &str,
) -> EngineResult<FetchApply> {
    if !need_parked || !parked.is_null() {
        return Ok(FetchApply::Reuse);
    }
    if stored::nonfinite(data).is_some() || !data.is_object() {
        return Err(attribute_error(data, "get"));
    }
    let data = data.as_object().expect("object");
    let week = match data.get("week_start") {
        Some(value) if stored::truthy(Some(value)) => value.clone(),
        _ => Value::from(today_monday),
    };
    let blocks = match data.get("blocks") {
        Some(value) if stored::truthy(Some(value)) => python_list(value, false)?,
        _ => Vec::new(),
    };
    Ok(FetchApply::Cache { week, blocks })
}

/// A failed fetch clears the in-flight flag only when it is still the latest request.
pub fn reminder_fetch_failed(token: i64, ticket: i64) -> bool {
    token == ticket
}

/// The local clock `due_alarms` is asked about. `due_ms_of` is the caller's own conversion of an
/// hour and minute into milliseconds, so no timezone is known here.
pub struct AlarmClock<'a> {
    pub today_iso: &'a str,
    pub weekday: i64,
    pub now_ms: i64,
    pub last_check_ms: Option<i64>,
}

/// Keys `due_alarms` marks, including the ones marked before a later failure.
pub struct AlarmSeen<'a> {
    pub fired: &'a Value,
    pub is_set: bool,
    pub added: &'a mut Vec<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct AlarmPlan {
    pub queued: Vec<Value>,
    pub snoozed: Map<String, Value>,
    pub last_alarm_check: i64,
}

pub fn due_alarm_plan(
    prefs: &Value,
    snoozed_songs: &Value,
    clock: AlarmClock<'_>,
    seen: &mut AlarmSeen<'_>,
    snoozed: &Value,
    due_ms_of: &mut dyn FnMut(i64, i64) -> EngineResult<i64>,
) -> EngineResult<AlarmPlan> {
    let mut alarms = match prefs {
        value if !stored::truthy(Some(value)) => Vec::new(),
        Value::Object(map) if stored::nonfinite(prefs).is_none() => {
            star_or_empty(map.get("alarms"))?
        }
        other => return Err(attribute_error(other, "get")),
    };
    alarms.extend(song_values(snoozed_songs)?);
    let (queued, remaining, last) = due_alarms(
        &Value::Array(alarms),
        clock.today_iso,
        clock.weekday,
        clock.now_ms,
        clock.last_check_ms,
        seen.fired,
        seen.is_set,
        seen.added,
        snoozed,
        due_ms_of,
    )?;
    let snoozed = remaining
        .into_iter()
        .filter_map(|(id, due)| id.as_str().map(|name| (name.to_string(), due)))
        .collect();
    Ok(AlarmPlan {
        queued,
        snoozed,
        last_alarm_check: last,
    })
}

fn star_or_empty(value: Option<&Value>) -> EngineResult<Vec<Value>> {
    match value {
        Some(value) if stored::truthy(Some(value)) => python_list(value, true),
        _ => Ok(Vec::new()),
    }
}

fn song_values(songs: &Value) -> EngineResult<Vec<Value>> {
    match songs {
        Value::Object(map) if stored::nonfinite(songs).is_none() => {
            Ok(map.values().cloned().collect())
        }
        other => Err(attribute_error(other, "values")),
    }
}

/// `spotify_url`: a link handed in, or the Settings link when nothing was handed in (`value` null).
/// An invalid link is an empty string. A non-string is a `TypeError`, as the pattern match raises.
pub fn resolve_spotify_url(prefs: &Value, value: &Value) -> EngineResult<String> {
    let raw = if value.is_null() {
        pref_field(prefs, "default_spotify_url")?
    } else {
        Some(value)
    };
    let Some(raw) = raw else {
        return Ok(String::new());
    };
    if raw.is_null() {
        return Ok(String::new());
    }
    let Value::String(text) = raw else {
        return Err(spotify_type(raw));
    };
    if text.is_empty() {
        return Ok(String::new());
    }
    match valid_spotify_url(Some(text)) {
        Ok(Some(url)) => Ok(url),
        Ok(None) => Ok(String::new()),
        Err(error) if error.kind == ErrorKind::Value => Ok(String::new()),
        Err(error) => Err(error),
    }
}
