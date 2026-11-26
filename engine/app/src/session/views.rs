//! Day, week and month navigation for the desktop session (P4 slice 10A): which view is open, the
//! picked day, the month on screen and the month cache. The window still sends the requests and
//! emits its signals. It passes the clock, the open week and whether a save is held, and applies
//! the effect returned here.

use std::collections::{BTreeMap, BTreeSet};

use flexweek_engine::desk::grid::{
    date_for_day, due_day_of, month_anchor_date, month_for_view, shifted_month,
};
use flexweek_engine::time::week_start_on;
use serde_json::{Value, json};

use super::preferences;

/// What the window knows and the view does not: the open week, the clock and whether a save is in the way.
#[derive(Debug, Clone, Copy)]
pub struct ViewWorld<'a> {
    pub signed_in: bool,
    pub account_id: Option<&'a str>,
    pub week_start: &'a str,
    pub today: &'a str,
    pub busy: bool,
    pub held: bool,
    /// A parked unsaved week is in the way, so a kept month must not be shown as if it were current.
    pub parked: bool,
}

/// One GET the window should send. `token` and `generation` are what the reply must still match.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ViewRequest {
    pub kind: &'static str,
    pub method: &'static str,
    pub path: String,
    pub token: i64,
    pub asked: String,
    pub generation: i64,
    pub owner: String,
}

impl ViewRequest {
    fn to_json(&self) -> Value {
        json!({
            "kind": self.kind,
            "method": self.method,
            "path": self.path,
            "token": self.token,
            "asked": self.asked,
            "gen": self.generation,
            "owner": self.owner,
        })
    }
}

/// What the window does with a navigation decision, in this order.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ViewEffect {
    pub set_week_start: Option<String>,
    pub rebase_focus: bool,
    pub load_week: Option<String>,
    pub emit_before_request: bool,
    pub request: Option<ViewRequest>,
    pub emit: bool,
}

impl ViewEffect {
    pub fn none() -> Self {
        Self {
            set_week_start: None,
            rebase_focus: false,
            load_week: None,
            emit_before_request: false,
            request: None,
            emit: false,
        }
    }

    pub fn to_json(&self) -> Value {
        json!({
            "set_week_start": self.set_week_start,
            "rebase_focus": self.rebase_focus,
            "load_week": self.load_week,
            "emit_before_request": self.emit_before_request,
            "request": self.request.as_ref().map(ViewRequest::to_json),
            "emit": self.emit,
        })
    }
}

/// A fetch's answer. `say` is a status line; `emit` asks the window to redraw.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ViewAnswer {
    pub say: Option<String>,
    pub emit: bool,
}

impl ViewAnswer {
    pub fn quiet() -> Self {
        Self {
            say: None,
            emit: false,
        }
    }

    pub fn to_json(&self) -> Value {
        json!({ "say": self.say, "emit": self.emit })
    }
}

/// The reply the window hands back. `owner` is the account the request was started for.
pub struct ViewReply<'a> {
    pub kind: &'a str,
    pub token: i64,
    pub asked: &'a str,
    pub generation: i64,
    pub owner: &'a str,
    pub account_id: Option<&'a str>,
    pub data: Option<&'a Value>,
    pub error: Option<&'a str>,
}

/// The view the session is showing, and the month answers it has kept.
#[derive(Debug, Clone, PartialEq)]
pub struct ViewState {
    pub planner_view: String,
    pub selected_day: String,
    pub day_data: Option<Value>,
    pub selected_month: Option<String>,
    pub month_data: Option<Value>,
    /// 0 Monday through 6 Sunday. Kept on this computer; stored weeks stay keyed by their Monday.
    pub first_weekday: i64,
    /// The first day changed while a save was in flight: open its week once that save lands.
    pub refollow_week: bool,
    /// The type a drag on the hours makes, once one is picked under Add. Until then a block made by
    /// dragging has none: it used to be School, and an hour of Club counted as school.
    pub armed_category: Option<String>,
    pub selected_block_id: Option<String>,
    pub selected_occurrence_day: Option<i64>,
    pub day_ticket: i64,
    pub month_ticket: i64,
    month_cache: BTreeMap<(String, String), Value>,
    pub month_gen: i64,
    pub month_data_gen: i64,
    month_prefetching: BTreeSet<(String, String)>,
}

impl ViewState {
    pub fn new(today: String) -> Self {
        Self {
            planner_view: "week".to_string(),
            selected_day: today,
            day_data: None,
            selected_month: None,
            month_data: None,
            first_weekday: 0,
            refollow_week: false,
            armed_category: None,
            selected_block_id: None,
            selected_occurrence_day: None,
            day_ticket: 0,
            month_ticket: 0,
            month_cache: BTreeMap::new(),
            month_gen: 0,
            month_data_gen: 0,
            month_prefetching: BTreeSet::new(),
        }
    }

    pub fn cached_months(&self) -> &BTreeMap<(String, String), Value> {
        &self.month_cache
    }

    pub fn prefetch_keys(&self) -> &BTreeSet<(String, String)> {
        &self.month_prefetching
    }

    pub fn month_cached(&self, owner: &str, month: &str) -> Option<&Value> {
        self.month_cache
            .get(&(owner.to_string(), month.to_string()))
    }

    pub fn cache_contains(&self, owner: &str, month: &str) -> bool {
        self.month_cache
            .contains_key(&(owner.to_string(), month.to_string()))
    }

    pub fn replace_cache(&mut self, entries: BTreeMap<(String, String), Value>) {
        self.month_cache = entries;
    }

    pub fn clear_cache(&mut self) {
        self.month_cache.clear();
    }

    pub fn insert_cache(&mut self, owner: String, month: String, value: Value) {
        self.month_cache.insert((owner, month), value);
    }

    pub fn remove_cache(&mut self, owner: &str, month: &str) {
        self.month_cache
            .remove(&(owner.to_string(), month.to_string()));
    }

    pub fn prefetching(&self, owner: &str, month: &str) -> bool {
        self.month_prefetching
            .contains(&(owner.to_string(), month.to_string()))
    }

    pub fn clear_prefetch(&mut self) {
        self.month_prefetching.clear();
    }

    pub fn add_prefetch(&mut self, owner: String, month: String) {
        self.month_prefetching.insert((owner, month));
    }

    pub fn discard_prefetch(&mut self, owner: &str, month: &str) {
        self.month_prefetching
            .remove(&(owner.to_string(), month.to_string()));
    }

    /// A save landed, or the week's first day changed: a kept month is no longer the one to show.
    pub fn invalidate_months(&mut self) {
        self.month_cache.clear();
        self.month_gen += 1;
    }

    pub fn set_view(&mut self, view: &str, world: &ViewWorld<'_>) -> Result<ViewEffect, String> {
        if !world.signed_in || !matches!(view, "day" | "week" | "month") {
            return Ok(ViewEffect::none());
        }
        if view == "month" {
            return self.open_month(None, world);
        }
        if self.planner_view == "month" {
            return self.leave_month(view, world);
        }
        self.planner_view = view.to_string();
        let mut effect = self.refresh(world)?;
        effect.emit = true;
        Ok(effect)
    }

    pub fn open_day(&mut self, iso_day: &str, world: &ViewWorld<'_>) -> Result<ViewEffect, String> {
        if !world.signed_in || !accepted_day(iso_day)? {
            return Ok(ViewEffect::none());
        }
        let shown = shown_week(iso_day, self.first_weekday)?;
        self.selected_day = iso_day.to_string();
        self.planner_view = "day".to_string();
        self.day_data = None;
        if shown != world.week_start {
            return Ok(ViewEffect {
                load_week: Some(shown),
                ..ViewEffect::none()
            });
        }
        let mut effect = self.fetch_day(world);
        effect.emit = true;
        Ok(effect)
    }

    pub fn open_month(
        &mut self,
        month: Option<&str>,
        world: &ViewWorld<'_>,
    ) -> Result<ViewEffect, String> {
        if !world.signed_in {
            return Ok(ViewEffect::none());
        }
        let anchor = if self.planner_view == "day" {
            self.selected_day.clone()
        } else if today_column(world.today, world.week_start).is_some() {
            world.today.to_string()
        } else {
            // A week that does not hold today opens the month on its Thursday.
            date_on(world.week_start, 3)?
        };
        self.selected_day = anchor.clone();
        self.selected_month = Some(match month {
            Some(text) if !text.is_empty() => text.to_string(),
            _ => month_for_view(&anchor),
        });
        self.planner_view = "month".to_string();
        self.month_data = None;
        let mut effect = self.fetch_month(world);
        effect.emit = true;
        Ok(effect)
    }

    pub fn shift_month(
        &mut self,
        amount: i64,
        world: &ViewWorld<'_>,
    ) -> Result<ViewEffect, String> {
        if self.planner_view != "month" {
            return Ok(ViewEffect::none());
        }
        let Some(current) = self
            .selected_month
            .clone()
            .filter(|month| !month.is_empty())
        else {
            return Ok(ViewEffect::none());
        };
        let Some(next) = shifted_month(&current, amount).map_err(|error| error.message)? else {
            return Ok(ViewEffect::none());
        };
        self.selected_month = Some(next);
        self.month_data = None;
        let mut effect = self.fetch_month(world);
        effect.emit = true;
        Ok(effect)
    }

    pub fn follow_first_weekday(
        &mut self,
        new_weekday: i64,
        world: &ViewWorld<'_>,
    ) -> Result<ViewEffect, String> {
        let decision =
            preferences::follow_first_weekday(self.first_weekday, new_weekday, world.signed_in);
        self.first_weekday = new_weekday;
        // The month's rows changed, so what was kept is asked for again.
        self.invalidate_months();
        let mut effect = ViewEffect::none();
        if !world.signed_in {
            effect.set_week_start = Some(shown_week(&self.selected_day, self.first_weekday)?);
        } else if decision.refollow {
            effect.rebase_focus = decision.rebase_focus;
            self.refollow_week = true;
            effect.load_week = self.follow_week(world)?.load_week;
        }
        if self.planner_view == "month" {
            let fetch = self.fetch_month(world);
            effect.emit_before_request = fetch.emit_before_request;
            effect.request = fetch.request;
        }
        effect.emit = true;
        Ok(effect)
    }

    pub fn follow_week(&mut self, world: &ViewWorld<'_>) -> Result<ViewEffect, String> {
        if !self.refollow_week || !world.signed_in || world.busy || world.held {
            return Ok(ViewEffect::none());
        }
        self.refollow_week = false;
        let anchor = if today_column(&self.selected_day, world.week_start).is_some() {
            self.selected_day.clone()
        } else {
            world.week_start.to_string()
        };
        let target = shown_week(&anchor, self.first_weekday)?;
        if target != world.week_start {
            self.selected_day = anchor;
            return Ok(ViewEffect {
                load_week: Some(target),
                ..ViewEffect::none()
            });
        }
        Ok(ViewEffect::none())
    }

    pub fn refresh(&mut self, world: &ViewWorld<'_>) -> Result<ViewEffect, String> {
        if self.planner_view == "day" {
            self.ensure_selected_day(world.week_start)?;
            return Ok(self.fetch_day(world));
        }
        if self.planner_view == "month" && chosen(&self.selected_month) {
            return Ok(self.fetch_month(world));
        }
        Ok(ViewEffect::none())
    }

    pub fn fetch_day(&mut self, world: &ViewWorld<'_>) -> ViewEffect {
        ViewEffect {
            request: self.begin_day(world),
            ..ViewEffect::none()
        }
    }

    pub fn fetch_month(&mut self, world: &ViewWorld<'_>) -> ViewEffect {
        let (showed, request) = self.begin_month(world);
        ViewEffect {
            emit_before_request: showed,
            request,
            ..ViewEffect::none()
        }
    }

    pub fn prefetch(&mut self, world: &ViewWorld<'_>) -> Result<ViewEffect, String> {
        let Some(owner) = world.account_id else {
            return Ok(ViewEffect::none());
        };
        if !world.signed_in {
            return Ok(ViewEffect::none());
        }
        let asked = month_for_view(&date_on(world.week_start, 3)?);
        let key = (owner.to_string(), asked.clone());
        if self.month_cache.contains_key(&key) || self.month_prefetching.contains(&key) {
            return Ok(ViewEffect::none());
        }
        self.month_prefetching.insert(key);
        Ok(ViewEffect {
            request: Some(ViewRequest {
                kind: "prefetch",
                method: "GET",
                path: self.month_path(&asked),
                token: 0,
                asked,
                generation: self.month_gen,
                owner: owner.to_string(),
            }),
            ..ViewEffect::none()
        })
    }

    /// A Monday start asks as it always did; the server's first day is Monday when none is named.
    pub fn month_path(&self, month: &str) -> String {
        if self.first_weekday == 0 {
            format!("/api/month?month={month}")
        } else {
            format!("/api/month?month={month}&first_day={}", self.first_weekday)
        }
    }

    pub fn view_reply(&mut self, reply: ViewReply<'_>) -> ViewAnswer {
        match reply.kind {
            "day" => self.day_reply(reply),
            "month" => self.month_reply(reply),
            "prefetch" => self.prefetch_reply(reply),
            _ => ViewAnswer::quiet(),
        }
    }

    /// Which day of the open week `iso_day` is (0 its first day), or None when it is not in it.
    pub fn ensure_selected_day(&mut self, week_start: &str) -> Result<(), String> {
        if today_column(&self.selected_day, week_start).is_some() {
            return Ok(());
        }
        let weekday = match weekday_in_its_week(&self.selected_day, self.first_weekday) {
            Ok(day) => day,
            Err(_) => {
                self.selected_day = week_start.to_string();
                return Ok(());
            }
        };
        self.selected_day = date_on(week_start, weekday)?;
        Ok(())
    }

    fn leave_month(&mut self, view: &str, world: &ViewWorld<'_>) -> Result<ViewEffect, String> {
        let Some(month) = self.selected_month.clone().filter(|text| !text.is_empty()) else {
            self.planner_view = view.to_string();
            return Ok(ViewEffect {
                emit: true,
                ..ViewEffect::none()
            });
        };
        let anchor = self.picked_day_or_anchor(&month, world.today);
        let shown = shown_week(&anchor, self.first_weekday)?;
        self.selected_day = anchor;
        self.planner_view = view.to_string();
        if shown != world.week_start {
            return Ok(ViewEffect {
                load_week: Some(shown),
                ..ViewEffect::none()
            });
        }
        let mut effect = self.refresh(world)?;
        effect.emit = true;
        Ok(effect)
    }

    /// A day picked inside the month on screen stays. Any other month opens on today, or the 1st.
    fn picked_day_or_anchor(&self, month: &str, today: &str) -> String {
        if prefix7(&self.selected_day) == month {
            self.selected_day.clone()
        } else {
            month_anchor_date(month, today)
        }
    }

    fn begin_day(&mut self, world: &ViewWorld<'_>) -> Option<ViewRequest> {
        if !world.signed_in || self.planner_view != "day" {
            return None;
        }
        self.day_ticket += 1;
        let asked = self.selected_day.clone();
        Some(ViewRequest {
            kind: "day",
            method: "GET",
            path: format!("/api/day?date={asked}"),
            token: self.day_ticket,
            asked,
            generation: self.month_gen,
            owner: String::new(),
        })
    }

    fn begin_month(&mut self, world: &ViewWorld<'_>) -> (bool, Option<ViewRequest>) {
        let Some(owner) = world.account_id else {
            return (false, None);
        };
        if !world.signed_in || self.planner_view != "month" || !chosen(&self.selected_month) {
            return (false, None);
        }
        let asked = self.selected_month.clone().unwrap_or_default();
        self.month_ticket += 1;
        let generation = self.month_gen;
        let key = (owner.to_string(), asked.clone());
        let mut showed = false;
        if !world.held
            && !world.parked
            && let Some(cached) = self.month_cache.get(&key).cloned()
        {
            // Shown at once, then asked for again: another week may have changed since it was kept.
            self.month_data = Some(cached);
            self.month_data_gen = generation;
            showed = true;
        }
        let request = ViewRequest {
            kind: "month",
            method: "GET",
            path: self.month_path(&asked),
            token: self.month_ticket,
            asked,
            generation,
            owner: owner.to_string(),
        };
        (showed, Some(request))
    }

    fn day_reply(&mut self, reply: ViewReply<'_>) -> ViewAnswer {
        if reply.error.is_some() {
            return ViewAnswer {
                say: None,
                emit: reply.token == self.day_ticket,
            };
        }
        if reply.token != self.day_ticket
            || self.planner_view != "day"
            || self.selected_day != reply.asked
        {
            return ViewAnswer::quiet();
        }
        self.day_data = reply.data.cloned();
        ViewAnswer {
            say: None,
            emit: true,
        }
    }

    fn month_reply(&mut self, reply: ViewReply<'_>) -> ViewAnswer {
        if reply.token != self.month_ticket || reply.generation != self.month_gen {
            return ViewAnswer::quiet();
        }
        if let Some(message) = reply.error {
            return ViewAnswer {
                say: Some(message.to_string()),
                emit: true,
            };
        }
        if self.planner_view != "month" || self.selected_month.as_deref() != Some(reply.asked) {
            return ViewAnswer::quiet();
        }
        if let Some(data) = reply.data {
            self.month_data = Some(data.clone());
            self.month_data_gen = reply.generation;
            self.month_cache.insert(
                (reply.owner.to_string(), reply.asked.to_string()),
                data.clone(),
            );
        }
        ViewAnswer {
            say: None,
            emit: true,
        }
    }

    fn prefetch_reply(&mut self, reply: ViewReply<'_>) -> ViewAnswer {
        self.month_prefetching
            .remove(&(reply.owner.to_string(), reply.asked.to_string()));
        if let Some(data) = reply.data
            && reply.error.is_none()
            && reply.account_id == Some(reply.owner)
            && reply.generation == self.month_gen
            && data.get("month").and_then(Value::as_str) == Some(reply.asked)
        {
            self.month_cache.insert(
                (reply.owner.to_string(), reply.asked.to_string()),
                data.clone(),
            );
        }
        ViewAnswer::quiet()
    }
}

/// Which day of the open week `iso_day` is (0 on `week_start`), or None when it is not in those seven
/// days or it is not a date.
pub fn today_column(iso_day: &str, week_start: &str) -> Option<i64> {
    match due_day_of(&Value::String(iso_day.to_string()), week_start) {
        Ok(Some(day)) if (0..=6).contains(&day) => Some(day),
        _ => None,
    }
}

fn chosen(month: &Option<String>) -> bool {
    month.as_ref().is_some_and(|text| !text.is_empty())
}

fn prefix7(text: &str) -> String {
    text.chars().take(7).collect()
}

fn date_on(week_start: &str, day: i64) -> Result<String, String> {
    date_for_day(week_start, &json!(day)).map_err(|error| error.message)
}

fn shown_week(iso_day: &str, first_weekday: i64) -> Result<String, String> {
    let day = u32::try_from(first_weekday).unwrap_or(7);
    week_start_on(iso_day, day).map_err(|error| error.message)
}

fn weekday_in_its_week(iso_day: &str, first_weekday: i64) -> Result<i64, String> {
    let shown = shown_week(iso_day, first_weekday)?;
    match due_day_of(&Value::String(iso_day.to_string()), &shown) {
        Ok(Some(day)) => Ok(day),
        Ok(None) => Err("no day".to_string()),
        Err(error) => Err(error.message),
    }
}

/// `date.fromisoformat` accepted this day. A dashed date the engine can read is accepted here. A
/// compact `YYYYMMDD` that Python accepts is refused, because the week that holds it is asked with
/// the dashed form and that call raises.
fn accepted_day(iso_day: &str) -> Result<bool, String> {
    match week_start_on(iso_day, 0) {
        Ok(_) => Ok(true),
        Err(error)
            if error.message == "date must be written YYYY-MM-DD" && compact_iso(iso_day) =>
        {
            Err(error.message)
        }
        Err(_) => Ok(false),
    }
}

fn compact_iso(text: &str) -> bool {
    if text.len() != 8 || !text.bytes().all(|byte| byte.is_ascii_digit()) {
        return false;
    }
    let dashed = format!("{}-{}-{}", &text[..4], &text[4..6], &text[6..8]);
    week_start_on(&dashed, 0).is_ok()
}
