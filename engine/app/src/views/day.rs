//! View-model for the Material Day and My day screens (`day_board.py` and `bridge_day.py`, P5-D1).
//!
//! Pure over values passed in by the caller: nothing here reads a clock, draws an id, or touches
//! the operating system. Python passes today's date, the clock minute and the session's facts in,
//! and keeps only the Qt models, signals and the calls on the session.

use std::collections::HashSet;

use flexweek_engine::desk::datetext::day_of;
use flexweek_engine::desk::focus::remaining_ms;
use flexweek_engine::desk::weekmodel::{
    clock_label, due_label_text, length_label, live_slack_words, range_label,
};
use flexweek_engine::desk::weekview::date_of;
use flexweek_engine::stored::add_days;
use flexweek_engine::{EngineError, EngineResult};
use serde_json::{Map, Value, json};

use crate::views::hours::{OPENS, opening_minute};
use crate::views::theme::{bar_for_category, event_category, paint_for_category};
use crate::views::week::{OccurrenceInput, occurrence_row, overlapped};

/// The names the settings screen's nudge switch can arrive under.
pub const NUDGE_KEYS: [&str; 2] = ["free_time_nudges", "nudges"];
/// The names the settings screen's dim-finished switch can arrive under.
pub const DIM_KEYS: [&str; 2] = ["dim_completed", "dim"];
pub const LOAD_FAILED: &str = "Couldn't load today.";
pub const LOADING: &str = "Loading…";
pub const SAVING_FIRST: &str = "Saving your last change… That check will work in a moment.";
const QUICK_FOCUS: &str = "Quick focus";

/// A bool preference. A missing key, or a value that is not a bool, keeps `default`.
pub fn read_flag(prefs: &Value, keys: &[&str], default: bool) -> bool {
    let Some(map) = prefs.as_object() else {
        return default;
    };
    keys.iter()
        .find_map(|key| map.get(*key).and_then(Value::as_bool))
        .unwrap_or(default)
}

/// One occurrence on the day, as the week model resolved it.
#[derive(Clone, Debug)]
pub struct DayItem {
    pub base: OccurrenceInput,
    pub missed: bool,
    pub pinned: bool,
    pub due: Option<String>,
    pub slack: Option<String>,
}

impl DayItem {
    fn settled(&self) -> bool {
        self.base.done || self.missed
    }

    // Fixed blocks always count; homework counts until it is done or missed.
    fn live(&self) -> bool {
        !(self.base.work && self.settled())
    }

    fn homework(&self) -> bool {
        self.base.work && !self.base.assignment_id.is_empty()
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct DayRow {
    pub title: String,
    pub subtitle: String,
    pub icon: String,
    pub bar: String,
    pub fill: String,
    pub ink: String,
    pub tag: String,
    pub tag_kind: String,
    pub can_finish: bool,
    pub assignment_id: String,
    pub dim: bool,
}

impl DayRow {
    pub fn to_json(&self) -> Value {
        json!({
            "title": self.title,
            "subtitle": self.subtitle,
            "icon": self.icon,
            "bar": self.bar,
            "fill": self.fill,
            "ink": self.ink,
            "tag": self.tag,
            "tag_kind": self.tag_kind,
            "can_finish": self.can_finish,
            "assignment_id": self.assignment_id,
            "dim": self.dim,
        })
    }
}

#[derive(Clone, Debug, PartialEq)]
pub struct DayBoard {
    pub left_line: String,
    pub left_count: i64,
    pub show_now: bool,
    pub now_title: String,
    pub now_minutes: i64,
    pub now_line: String,
    // A fixed block such as Soccer is on: the card names it and what is next, and starts nothing.
    pub now_busy: bool,
    pub ring_count: i64,
    pub ring_caption: String,
    pub ring_share: f64,
    pub up_next: Vec<DayRow>,
    pub done: Vec<DayRow>,
    pub focus_block_id: String,
    pub focus_day: i64,
    // The homework Start focus opens, which the card names on its button.
    pub focus_title: String,
}

impl DayBoard {
    pub fn to_json(&self) -> Value {
        json!({
            "left_line": self.left_line,
            "left_count": self.left_count,
            "show_now": self.show_now,
            "now_title": self.now_title,
            "now_minutes": self.now_minutes,
            "now_line": self.now_line,
            "now_busy": self.now_busy,
            "ring_count": self.ring_count,
            "ring_caption": self.ring_caption,
            "ring_share": self.ring_share,
            "up_next": self.up_next.iter().map(DayRow::to_json).collect::<Vec<_>>(),
            "done": self.done.iter().map(DayRow::to_json).collect::<Vec<_>>(),
            "focus_block_id": self.focus_block_id,
            "focus_day": self.focus_day,
            "focus_title": self.focus_title,
        })
    }
}

/// What `board_for` reads. `when` is `today`, `past` or `future`.
pub struct BoardInput<'a> {
    pub items: &'a [DayItem],
    pub minute: i64,
    pub when: &'a str,
    pub nudges: bool,
    pub dim: bool,
    pub mode: &'a str,
    pub on: &'a str,
    /// The real clock as `YYYY-MM-DDTHH:MM`; without it the viewed day's `minute` stands in.
    pub now: Option<&'a str>,
    /// The ids the planner calls missed: those sessions stay under Up next.
    pub missed: &'a HashSet<String>,
    /// Homework due today that still has no time. The ring and the left line count it.
    pub unplaced: i64,
    /// The week model's (title, line) for that homework.
    pub unplaced_words: Option<(&'a str, &'a str)>,
}

fn clock_past(item: &DayItem, minute: i64, when: &str) -> bool {
    match when {
        "past" => true,
        "future" => false,
        _ => item.base.end <= minute,
    }
}

fn gap<'a>(items: &[&'a DayItem], minute: i64, when: &str, nudges: bool) -> Option<&'a DayItem> {
    if !nudges || when != "today" {
        return None;
    }
    if items
        .iter()
        .any(|item| item.live() && item.base.start <= minute && minute < item.base.end)
    {
        return None;
    }
    next_after(items, minute)
}

fn doing<'a>(up: &[&'a DayItem], minute: i64, when: &str, nudges: bool) -> Option<&'a DayItem> {
    if !nudges || when != "today" {
        return None;
    }
    up.iter()
        .copied()
        .filter(|item| item.homework())
        .find(|item| item.base.start <= minute && minute < item.base.end)
}

/// The fixed block on at `minute`. Where several are, the one that ends last (and the first of equals),
/// so the card says when the student is actually free (Jonathan, 2026-11-09).
fn busy<'a>(items: &[&'a DayItem], minute: i64, when: &str, nudges: bool) -> Option<&'a DayItem> {
    if !nudges || when != "today" {
        return None;
    }
    let mut found: Option<&DayItem> = None;
    for item in items.iter().copied() {
        let on = !item.base.work && item.base.start <= minute && minute < item.base.end;
        if on && found.is_none_or(|best| item.base.end > best.base.end) {
            found = Some(item);
        }
    }
    found
}

fn next_after<'a>(items: &[&'a DayItem], minute: i64) -> Option<&'a DayItem> {
    items
        .iter()
        .copied()
        .find(|item| item.live() && item.base.start > minute)
}

fn card_title(
    busy: Option<&DayItem>,
    doing: Option<&DayItem>,
    gap: Option<&DayItem>,
    minute: i64,
    waiting: Option<(&str, &str)>,
) -> String {
    if let Some((title, _)) = waiting {
        return title.to_string();
    }
    if let Some(item) = busy {
        return format!("{} until {}", item.base.title, clock_label(item.base.end));
    }
    if let Some(item) = doing {
        return item.base.title.clone();
    }
    match gap {
        Some(item) => format!("Free for {}", length_label(item.base.start - minute)),
        None => String::new(),
    }
}

fn next_line(item: Option<&DayItem>) -> String {
    match item {
        Some(next) => format!(
            "Next: {} at {}",
            next.base.title,
            clock_label(next.base.start)
        ),
        None => String::new(),
    }
}

fn card_line(
    busy: Option<&DayItem>,
    after: Option<&DayItem>,
    doing: Option<&DayItem>,
    gap: Option<&DayItem>,
    minute: i64,
    waiting: Option<(&str, &str)>,
) -> String {
    if let Some((_, line)) = waiting {
        return line.to_string();
    }
    if busy.is_some() {
        return next_line(after);
    }
    if let Some(item) = doing {
        return format!("{} left", length_label(item.base.end - minute));
    }
    next_line(gap)
}

fn now_minutes(
    busy: Option<&DayItem>,
    doing: Option<&DayItem>,
    gap: Option<&DayItem>,
    minute: i64,
) -> i64 {
    if let Some(item) = busy {
        return item.base.end - minute;
    }
    if let Some(item) = doing {
        return item.base.end - minute;
    }
    gap.map_or(0, |item| item.base.start - minute)
}

fn left_line(count: i64, today: bool) -> String {
    if count == 0 {
        return if today {
            "Nothing left today"
        } else {
            "Nothing left"
        }
        .to_string();
    }
    let noun = if count == 1 { "thing" } else { "things" };
    let tail = if today { " today" } else { "" };
    format!("{count} {noun} left{tail}")
}

fn icon_for(category: &str) -> &'static str {
    // Free time has its own sofa, so it does not look like exercise or an activity (Jonathan, 2026-11-19).
    if category == "free" {
        return "weekend";
    }
    match event_category(category) {
        "class" => "school",
        "study" | "assignments" => "edit_note",
        _ => "schedule",
    }
}

fn tag_kind(words: &str) -> &'static str {
    match words {
        "" => "",
        "Tight" => "tight",
        "Plenty of time" => "plenty",
        "Cutting it close" => "cutting",
        _ => "plain",
    }
}

fn row(
    item: &DayItem,
    on: &str,
    stamp: &str,
    mode: &str,
    dim: bool,
    finish: bool,
) -> EngineResult<DayRow> {
    let category = item.base.category.as_str();
    let scheme = if mode == "dark" { "dark" } else { "light" };
    let due = item.due.as_deref().filter(|text| !text.is_empty());
    let words = live_slack_words(item.slack.as_deref(), due, Some(stamp));
    let kind = tag_kind(words);
    let mut parts = vec![range_label(item.base.start, item.base.end)];
    if item.pinned {
        parts.push("Pinned".to_string());
    }
    if let Some(due) = due {
        let label = due_label_text(Some(due), day_of(on)?)?;
        if !label.is_empty() {
            parts.push(format!("Due {label}"));
        }
    }
    let show_tag = finish && !kind.is_empty();
    let (fill, ink) = paint_for_category(category, scheme)?;
    Ok(DayRow {
        title: item.base.title.clone(),
        subtitle: parts.join(" · "),
        icon: icon_for(category).to_string(),
        // ListRow keeps its own fill and paints the class colour on the edge.
        bar: bar_for_category(category).to_string(),
        fill,
        ink: ink.to_string(),
        tag: if show_tag {
            words.to_string()
        } else {
            String::new()
        },
        tag_kind: if show_tag {
            kind.to_string()
        } else {
            String::new()
        },
        can_finish: finish && item.homework(),
        assignment_id: item.base.assignment_id.clone(),
        dim,
    })
}

/// The viewed day at `minute` as `YYYY-MM-DDTHH:MM`, for slack words when the caller has no real clock.
fn stamp_of(on: &str, minute: i64) -> EngineResult<String> {
    let day = add_days(day_of(on)?, minute.div_euclid(24 * 60))?;
    let in_day = minute.rem_euclid(24 * 60);
    Ok(format!("{day}T{:02}:{:02}", in_day / 60, in_day % 60))
}

/// Up next, Done, the Now card and the ring for one day.
///
/// The Now card shows only on today while nudges are on. It names homework that is happening at
/// `minute`, with its time left; while a fixed block is on, that block, when it ends and what is
/// next; otherwise it gives the free time from `minute` to the next block that still occupies time,
/// and that block. A finished homework block does not occupy that gap.
pub fn board_for(input: &BoardInput<'_>) -> EngineResult<DayBoard> {
    let minute = input.minute;
    let when = input.when;
    let mut ordered: Vec<&DayItem> = input.items.iter().collect();
    ordered.sort_by(|a, b| (a.base.start, &a.base.title).cmp(&(b.base.start, &b.base.title)));
    // A session the planner calls missed is still to do, so it stays under Up next though its time went by.
    let is_up: Vec<bool> = ordered
        .iter()
        .map(|item| {
            !item.settled()
                && (input.missed.contains(&item.base.block_id) || !clock_past(item, minute, when))
        })
        .collect();
    let up: Vec<&DayItem> = ordered
        .iter()
        .zip(&is_up)
        .filter_map(|(item, up)| up.then_some(*item))
        .collect();
    let finished: Vec<&DayItem> = ordered
        .iter()
        .zip(&is_up)
        .filter_map(|(item, up)| (!up).then_some(*item))
        .collect();
    let ahead: Vec<&DayItem> = up
        .iter()
        .copied()
        .filter(|item| !clock_past(item, minute, when))
        .collect();
    let free = gap(&ordered, minute, when, input.nudges);
    let focus = ahead.iter().copied().find(|item| item.homework());
    let working = doing(&ahead, minute, when, input.nudges);
    let fixed = if working.is_some() {
        None
    } else {
        busy(&ordered, minute, when, input.nudges)
    };
    let after = fixed.and_then(|_| next_after(&ordered, minute));
    let unplaced = if when == "today" { input.unplaced } else { 0 };
    let total = ordered.len() as i64 + unplaced;
    let count = up.len() as i64 + unplaced;
    let nothing_ahead = working.is_none() && fixed.is_none() && free.is_none();
    let waiting = input
        .unplaced_words
        .filter(|_| unplaced > 0 && nothing_ahead);
    let stamp = match input.now {
        Some(stamp) => stamp.to_string(),
        None => stamp_of(input.on, minute)?,
    };
    let rows = |items: &[&DayItem], dim: bool, finish: bool| -> EngineResult<Vec<DayRow>> {
        items
            .iter()
            .map(|item| row(item, input.on, &stamp, input.mode, dim, finish))
            .collect()
    };
    Ok(DayBoard {
        left_line: left_line(count, when == "today"),
        left_count: count,
        show_now: working.is_some() || fixed.is_some() || free.is_some() || waiting.is_some(),
        now_title: card_title(fixed, working, free, minute, waiting),
        now_minutes: now_minutes(fixed, working, free, minute),
        now_line: card_line(fixed, after, working, free, minute, waiting),
        now_busy: fixed.is_some(),
        ring_count: count,
        ring_caption: if count == 1 {
            "thing left"
        } else {
            "things left"
        }
        .to_string(),
        ring_share: if total == 0 {
            0.0
        } else {
            (total - count) as f64 / total as f64
        },
        up_next: rows(&up, false, true)?,
        done: rows(&finished, input.dim, false)?,
        focus_block_id: focus.map_or_else(String::new, |item| item.base.block_id.clone()),
        focus_day: focus.map_or(-1, |item| item.base.day),
        focus_title: focus.map_or_else(String::new, |item| item.base.title.clone()),
    })
}

/// What the week model answers about homework due today that has no time yet.
pub trait WeekLookups {
    fn has_unplaced_api(&self) -> bool;
    fn unplaced_count(&self, day: i64) -> EngineResult<usize>;
    fn leftover_kind(&self, day: i64) -> EngineResult<String>;
    fn leftover_title_line(&self, day: i64) -> EngineResult<(String, String)>;
}

/// How many homework items due today have no time yet, and the week model's words for them (its name,
/// then what to do). The words are None while something placed is still ahead.
pub fn waiting_for_a_time(
    week: Option<&dyn WeekLookups>,
    day_index: i64,
    today: bool,
) -> EngineResult<(i64, Option<(String, String)>)> {
    let Some(week) = week else {
        return Ok((0, None));
    };
    if !today || day_index < 0 || !week.has_unplaced_api() {
        return Ok((0, None));
    }
    let count = week.unplaced_count(day_index)?;
    if count == 0 {
        return Ok((0, None));
    }
    let count = count as i64;
    if week.leftover_kind(day_index)? != "needs_time" {
        return Ok((count, None));
    }
    Ok((count, Some(week.leftover_title_line(day_index)?)))
}

/// The focus timer as the Now card names it.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct TimerWords {
    pub title: String,
    /// Time left, or "Session finished" once it has run out and has not been cleared ("Finished" when
    /// its homework was already done).
    pub line: String,
    pub ended: bool,
    /// Its homework is still open.
    pub open: bool,
    /// Its homework is already done.
    pub done: bool,
}

/// The timer's homework and its time left; blank when there is none. `homework_done` is None when the
/// timer's homework is not among the session's assignments.
pub fn timer_words(
    state: &Value,
    now_ms: i64,
    homework_done: Option<bool>,
) -> EngineResult<TimerWords> {
    let Some(map) = state.as_object() else {
        return Ok(TimerWords::default());
    };
    let title = match map.get("title") {
        Some(Value::String(text)) if !text.is_empty() => text.clone(),
        _ => QUICK_FOCUS.to_string(),
    };
    let phase = map.get("phase").and_then(Value::as_str).unwrap_or("");
    if phase == "ended" {
        let done = homework_done == Some(true);
        return Ok(TimerWords {
            title,
            line: if done { "Finished" } else { "Session finished" }.to_string(),
            ended: true,
            open: !done && homework_done.is_some(),
            done,
        });
    }
    let remaining = remaining_ms(state, now_ms)?;
    let left = (-(-remaining).div_euclid(60_000)).max(1);
    let left = i64::try_from(left).unwrap_or(i64::MAX);
    let mut line = format!("{} left", length_label(left));
    if phase == "break" || phase == "long_break" {
        line = format!("Break, {line}");
    }
    Ok(TimerWords {
        title,
        line,
        ended: false,
        open: false,
        done: false,
    })
}

/// Whether the timer's session has run out and has not been cleared.
pub fn focus_ended(state: &Value) -> bool {
    state
        .as_object()
        .and_then(|map| map.get("phase"))
        .and_then(Value::as_str)
        == Some("ended")
}

/// Whether the session's answer to Mark finished means the timer card may have changed.
pub fn finish_refreshes(outcome: Option<&str>) -> bool {
    matches!(outcome, Some("finished" | "queued"))
}

/// What the Finish button on a Day row does.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FinishPlan {
    /// Words for the snackbar before anything is done (the session is still saving).
    pub say_now: Option<String>,
    /// Words for the snackbar once the homework is marked finished and saved; None when nothing is done.
    pub finished: Option<String>,
}

pub fn finish_plan(
    assignment_id: &str,
    busy: bool,
    saving: bool,
    title: Option<&str>,
) -> FinishPlan {
    if assignment_id.is_empty() {
        return FinishPlan {
            say_now: None,
            finished: None,
        };
    }
    if busy || saving {
        return FinishPlan {
            say_now: Some(SAVING_FIRST.to_string()),
            finished: None,
        };
    }
    let title = title.filter(|text| !text.is_empty()).unwrap_or("Homework");
    FinishPlan {
        say_now: None,
        finished: Some(format!("Finished {title}")),
    }
}

/// Which call the Now card's Start focus makes.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct FocusPlan {
    /// `open_focus` (back to the running timer), `hook`, `widgets` or `session`.
    pub action: &'static str,
    pub block_id: Option<String>,
    pub day: Option<i64>,
}

/// What the window offers for Start focus, in the order it is tried.
pub struct FocusHooks {
    pub opener: bool,
    pub hook: bool,
    pub starter: bool,
}

/// The state the Day screen keeps between reloads. `today_only` is My day: today, and the week that
/// holds it, loaded on its own.
#[derive(Clone, Debug)]
pub struct DayView {
    pub today_only: bool,
    mode: String,
    iso: String,
    year: i64,
    month: i64,
    mini_day: i64,
    day_index: i64,
    opening_minute: i64,
    waiting: bool,
    load_error: String,
    asked_week: String,
    load_started: bool,
    // Day asked for today while another week was loading; that load lands later and moves the day.
    want_today: bool,
    timer: TimerWords,
    today: bool,
    pending: Option<Pending>,
}

#[derive(Clone, Debug)]
struct Pending {
    viewed: String,
    when: &'static str,
    // How many days the week on screen started before today; negative when it starts after.
    offset: i64,
    clock_minute: i64,
}

/// What `DayView::begin_reload` reads from the session.
pub struct BeginInput<'a> {
    pub mode: &'a str,
    pub prefs: &'a Value,
    pub today_iso: &'a str,
    pub clock_minute: i64,
    pub selected_day: Option<&'a str>,
    pub signed_in: bool,
    pub week_start: Option<&'a str>,
    /// The week that holds today, as the shown week starts.
    pub needed_week: &'a str,
    pub busy: bool,
    pub message: Option<&'a str>,
    pub fetch: bool,
    pub screen: &'a str,
    pub can_load: bool,
}

/// What the caller does next after `begin_reload`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct BeginOutcome {
    pub clock_24h: bool,
    /// False when the reload ends here (a week is loading, or its load failed).
    pub proceed: bool,
    /// The week the session should load now.
    pub load: Option<String>,
    /// Which day of the shown week is viewed; None when it is not in that week.
    pub day: Option<i64>,
    /// Whether to read the built week and the missed ids from the session.
    pub read_week: bool,
}

/// What `DayView::finish_reload` reads once the session's week is read.
pub struct FinishInput<'a> {
    pub items: &'a [DayItem],
    pub missed: &'a HashSet<String>,
    pub prefs: &'a Value,
    pub timer: TimerWords,
    pub week: Option<&'a dyn WeekLookups>,
    /// The real clock as `YYYY-MM-DDTHH:MM`.
    pub now: &'a str,
}

pub struct Published {
    pub board: DayBoard,
    pub block_rows: Vec<Value>,
}

impl DayView {
    pub fn new(today_only: bool) -> Self {
        Self {
            today_only,
            mode: "light".to_string(),
            iso: String::new(),
            year: 2026,
            month: 1,
            mini_day: 0,
            day_index: -1,
            opening_minute: OPENS,
            waiting: false,
            load_error: String::new(),
            asked_week: String::new(),
            load_started: false,
            want_today: false,
            timer: TimerWords::default(),
            today: false,
            pending: None,
        }
    }

    pub fn mode(&self) -> &str {
        &self.mode
    }

    /// Reads the session once: which day is viewed, and whether My day must first load its week.
    pub fn begin_reload(&mut self, input: &BeginInput<'_>) -> EngineResult<BeginOutcome> {
        self.mode = if input.mode == "dark" {
            "dark"
        } else {
            "light"
        }
        .to_string();
        let clock_24h = input
            .prefs
            .get("clock_24h")
            .and_then(Value::as_bool)
            .unwrap_or(false);
        let today = day_of(input.today_iso)?;
        let viewed = if self.today_only {
            today
        } else {
            match input
                .selected_day
                .filter(|text| !text.is_empty())
                .map(day_of)
            {
                Some(Ok(chosen)) => chosen,
                _ => today,
            }
        };
        self.iso = viewed.to_string();
        let (year, month, day) = date_of(&self.iso, 0)?;
        self.year = i64::from(year);
        self.month = i64::from(month);
        self.mini_day = i64::from(day);
        self.day_index = -1;
        let week_start = input.week_start.unwrap_or("");
        let quit = |load: Option<String>| BeginOutcome {
            clock_24h,
            proceed: false,
            load,
            day: None,
            read_week: false,
        };
        if self.today_only && input.signed_in {
            let needed = input.needed_week;
            if week_start != needed {
                let idle = !input.busy;
                if self.load_started && self.asked_week == needed && idle {
                    self.waiting = false;
                    self.load_error = input
                        .message
                        .filter(|text| !text.is_empty())
                        .unwrap_or(LOAD_FAILED)
                        .to_string();
                    return Ok(quit(None));
                }
                self.waiting = true;
                self.load_error.clear();
                self.asked_week = needed.to_string();
                let want = input.fetch || input.screen == "myday" || self.load_started;
                self.load_started = false;
                let load = (want && input.can_load && idle).then(|| needed.to_string());
                return Ok(quit(load));
            }
            self.waiting = false;
            self.load_error.clear();
            self.asked_week.clear();
            self.load_started = false;
        }
        let in_week_data = input.signed_in && !week_start.is_empty();
        let mut offset = -1;
        let mut day = None;
        if in_week_data {
            let start = day_of(week_start)?;
            offset = (today - start).num_days();
            if start <= viewed && viewed <= add_days(start, 6)? {
                let index = (viewed - start).num_days();
                self.day_index = index;
                day = Some(index);
            }
        }
        let when = if viewed == today {
            "today"
        } else if viewed < today {
            "past"
        } else {
            "future"
        };
        self.pending = Some(Pending {
            viewed: self.iso.clone(),
            when,
            offset,
            clock_minute: input.clock_minute,
        });
        Ok(BeginOutcome {
            clock_24h,
            proceed: true,
            load: None,
            day,
            read_week: in_week_data,
        })
    }

    /// Builds the board and the hour blocks for the day `begin_reload` chose.
    pub fn finish_reload(&mut self, input: &FinishInput<'_>) -> EngineResult<Published> {
        let pending = self
            .pending
            .take()
            .ok_or_else(|| EngineError::value("finish_reload needs begin_reload first"))?;
        let today = pending.when == "today";
        self.today = today;
        self.timer = input.timer.clone();
        let minute = if today { pending.clock_minute } else { 0 };
        self.opening_minute = self.opening_for(input, today.then_some(minute));
        self.waiting = false;
        self.load_error.clear();
        let dim = read_flag(input.prefs, &DIM_KEYS, true);
        let mut block_rows = Vec::with_capacity(input.items.len());
        for item in input.items {
            let (day, end) = (item.base.day, item.base.end);
            let gone = if pending.offset > 6 {
                true
            } else if pending.offset < 0 {
                false
            } else {
                day < pending.offset || (day == pending.offset && end <= pending.clock_minute)
            };
            let missed = input.missed.contains(&item.base.block_id);
            block_rows.push(Value::Object(occurrence_row(
                &item.base, &self.mode, dim, gone, false, missed,
            )?));
        }
        let (unplaced, words) = waiting_for_a_time(input.week, self.day_index, today)?;
        let board = board_for(&BoardInput {
            items: input.items,
            minute,
            when: pending.when,
            nudges: read_flag(input.prefs, &NUDGE_KEYS, true),
            dim,
            mode: &self.mode,
            on: &pending.viewed,
            now: Some(input.now),
            missed: input.missed,
            unplaced,
            unplaced_words: words
                .as_ref()
                .map(|(title, line)| (title.as_str(), line.as_str())),
        })?;
        Ok(Published {
            board,
            block_rows: overlapped(block_rows)?,
        })
    }

    // Now on today, else the day's first block, else 08:00. QML only scrolls.
    fn opening_for(&self, input: &FinishInput<'_>, now: Option<i64>) -> i64 {
        if self.day_index < 0 || input.week.is_none() {
            return now.unwrap_or(OPENS);
        }
        let starts: Vec<i64> = input.items.iter().map(|item| item.base.start).collect();
        let today_index = now.map(|_| self.day_index);
        opening_minute(today_index, now, Some(self.day_index), &[], Some(&starts))
    }

    pub fn mark_load_started(&mut self) {
        self.load_started = true;
    }

    /// Forget a week load Day or My day asked for, so the next reload asks again.
    pub fn reset_load(&mut self) {
        self.asked_week.clear();
        self.load_started = false;
        self.load_error.clear();
    }

    /// Whether Today means opening today on this screen: Day does; My day is always today.
    pub fn today_requested(&self, has_session: bool) -> bool {
        has_session && !self.today_only
    }

    pub fn set_want_today(&mut self, wanted: bool) {
        self.want_today = wanted;
    }

    /// Takes the wish to reopen today once a week load that was already running when Day asked has
    /// landed: only when the session is idle again.
    pub fn after_week(&mut self, has_session: bool, busy: bool) -> bool {
        if !self.want_today || !has_session || busy {
            return false;
        }
        self.want_today = false;
        true
    }

    /// Whether the landed week left Day off today, so it must open today again.
    pub fn reopen_today(
        &self,
        screen: &str,
        selected_day: Option<&str>,
        week_start: Option<&str>,
        holding: &str,
        today_iso: &str,
    ) -> bool {
        screen == "day" && (selected_day != Some(today_iso) || week_start != Some(holding))
    }

    /// Whether a session going idle must reload My day.
    pub fn on_busy(&self, busy: bool, screen: &str) -> bool {
        if busy || !self.today_only {
            return false;
        }
        self.load_started || (self.waiting && screen == "myday")
    }

    /// The date `day` of the month the side panel shows, or None for a day that month does not have.
    pub fn pick_target(&self, day: i64) -> Option<String> {
        if self.today_only || !(1..=31).contains(&day) {
            return None;
        }
        day_of(&format!("{:04}-{:02}-{day:02}", self.year, self.month))
            .ok()
            .map(|date| date.to_string())
    }

    /// The date `days` away from the day shown; None on My day, which never moves.
    pub fn shift_target(&self, days: i64) -> EngineResult<Option<String>> {
        if self.today_only || self.iso.is_empty() {
            return Ok(None);
        }
        Ok(Some(add_days(day_of(&self.iso)?, days)?.to_string()))
    }

    /// Takes a fresh reading of the timer. True when the card's words changed.
    pub fn refresh_timer(&mut self, words: TimerWords) -> bool {
        if words == self.timer {
            return false;
        }
        self.timer = words;
        true
    }

    pub fn left_line(&self, board_line: &str) -> String {
        if self.waiting {
            return LOADING.to_string();
        }
        if !self.load_error.is_empty() {
            return self.load_error.clone();
        }
        board_line.to_string()
    }

    pub fn show_now(&self, board_show_now: bool) -> bool {
        board_show_now || self.timer_running()
    }

    // The timer's card shows on today only.
    fn timer_running(&self) -> bool {
        self.today && !self.timer.title.is_empty()
    }

    pub fn start_focus_plan(&self, hooks: &FocusHooks, block_id: &str, day: i64) -> FocusPlan {
        let day_or_none = (day >= 0).then_some(day);
        if self.timer_running() && hooks.opener {
            return FocusPlan {
                action: "open_focus",
                block_id: None,
                day: None,
            };
        }
        if hooks.hook {
            return FocusPlan {
                action: "hook",
                block_id: Some(block_id.to_string()),
                day: Some(day),
            };
        }
        if hooks.starter {
            return FocusPlan {
                action: "widgets",
                block_id: Some(block_id.to_string()),
                day: day_or_none,
            };
        }
        FocusPlan {
            action: "session",
            block_id: Some(block_id.to_string()).filter(|text| !text.is_empty()),
            day: day_or_none,
        }
    }

    /// Every property the bridge exposes to QML that does not depend on the board.
    pub fn snapshot(&self) -> Value {
        let ended = self.timer_running() && self.timer.ended;
        let mut map = Map::new();
        map.insert("iso".into(), json!(self.iso));
        map.insert("waiting".into(), json!(self.waiting));
        map.insert("loadError".into(), json!(self.load_error));
        map.insert("year".into(), json!(self.year));
        map.insert("month".into(), json!(self.month));
        map.insert("miniDay".into(), json!(self.mini_day));
        map.insert("dayIndex".into(), json!(self.day_index));
        map.insert("openingMinute".into(), json!(self.opening_minute));
        map.insert(
            "timerTitle".into(),
            json!(if self.today {
                self.timer.title.as_str()
            } else {
                ""
            }),
        );
        map.insert(
            "timerLine".into(),
            json!(if self.today {
                self.timer.line.as_str()
            } else {
                ""
            }),
        );
        map.insert("timerEnded".into(), json!(ended));
        map.insert("timerDone".into(), json!(ended && self.timer.done));
        map.insert("timerCanFinish".into(), json!(ended && self.timer.open));
        Value::Object(map)
    }
}
