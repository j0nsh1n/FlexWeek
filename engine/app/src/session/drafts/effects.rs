use serde_json::{Value, json};

use super::{Drafts, flag, optional_text, text};

#[derive(Debug)]
enum WaitFor {
    Week {
        previous: String,
        said: Option<String>,
    },
    Assignments {
        previous: String,
        said: Option<String>,
        week: Value,
    },
    Save {
        written: Value,
        destination: Value,
        sent_repeats: bool,
        held: Value,
    },
    Delete,
    DeletedWeek,
    Refresh {
        start: String,
        basis: Value,
    },
}

#[derive(Debug)]
struct PendingEffect {
    id: u64,
    epoch: u64,
    ticket: Option<u64>,
    answer: WaitFor,
}

#[derive(Debug, Default)]
pub(super) struct Effects {
    latest: u64,
    active: Option<PendingEffect>,
    refresh: Option<PendingEffect>,
}

fn week_request(start: &str) -> Value {
    json!({ "method": "GET", "path": format!("/api/week?week_start={start}"), "body": null })
}

fn assignments_request(start: &str) -> Value {
    json!({
        "method": "GET",
        "path": format!("/api/assignments?week_start={start}&include_completed=true"),
        "body": null,
    })
}

impl Effects {
    pub(super) fn clear(&mut self) {
        self.active = None;
        self.refresh = None;
    }

    fn send(
        &mut self,
        mut request: Value,
        answer: WaitFor,
        epoch: u64,
        ticket: Option<u64>,
    ) -> Value {
        self.latest += 1;
        request["id"] = json!(self.latest);
        let effect = PendingEffect {
            id: self.latest,
            epoch,
            ticket,
            answer,
        };
        if ticket.is_some() {
            self.active = Some(effect);
        } else {
            self.refresh = Some(effect);
        }
        request
    }

    fn take(&mut self, id: u64) -> Option<PendingEffect> {
        for slot in [&mut self.active, &mut self.refresh] {
            if slot.as_ref().is_some_and(|effect| effect.id == id) {
                return slot.take();
            }
        }
        None
    }
}

impl Drafts {
    pub(super) fn fetch_effect(
        &mut self,
        command: &Value,
        epoch: u64,
        ticket: u64,
    ) -> Result<Value, String> {
        let start = text(command, "start")?;
        let answer = WaitFor::Week {
            previous: self.week_start(),
            said: optional_text(command, "said")?.map(str::to_owned),
        };
        let effect = self
            .effects
            .send(week_request(start), answer, epoch, Some(ticket));
        Ok(json!({ "effect": effect }))
    }

    pub(super) fn post_effect(
        &mut self,
        command: &Value,
        epoch: u64,
        ticket: u64,
    ) -> Result<Value, String> {
        let prepared = self.prepare_post(command)?;
        if prepared["post"] != true {
            return Err("no week save to post".into());
        }
        let body = &prepared["payload"];
        let answer = WaitFor::Save {
            written: prepared["written"].clone(),
            destination: prepared["destination"].clone(),
            sent_repeats: body.get("repeats").is_some(),
            held: prepared["held_status"].clone(),
        };
        let request =
            json!({ "method": "POST", "path": "/api/changes", "body": body, "clock": true });
        let effect = self.effects.send(request, answer, epoch, Some(ticket));
        Ok(json!({ "effect": effect, "held_status": prepared["held_status"] }))
    }

    pub(super) fn refresh_effect(&mut self, epoch: u64) -> Value {
        let start = self.week_start();
        let request = assignments_request(&start);
        let answer = WaitFor::Refresh {
            start,
            basis: self.field("committed_blocks").clone(),
        };
        json!({ "effect": self.effects.send(request, answer, epoch, None) })
    }

    pub(super) fn delete_effect(
        &mut self,
        command: &Value,
        epoch: u64,
        ticket: u64,
    ) -> Result<Value, String> {
        let begin = self.delete_begin(command)?;
        let mut request = begin["request"].clone();
        request["ids"] = json!(self.parked_count());
        let effect = self
            .effects
            .send(request, WaitFor::Delete, epoch, Some(ticket));
        Ok(json!({ "effect": effect, "title": begin["title"] }))
    }

    pub(super) fn answer_effect(
        &mut self,
        command: &Value,
        epoch: u64,
        ticket: u64,
    ) -> Result<Value, String> {
        let id = command["effect_id"]
            .as_u64()
            .ok_or("effect_id is a whole number")?;
        let Some(pending) = self.effects.take(id) else {
            return Ok(json!({ "action": "ignore" }));
        };
        if pending.epoch != epoch || pending.ticket.is_some_and(|expected| expected != ticket) {
            return Ok(json!({ "action": "ignore" }));
        }
        let data = &command["data"];
        let error = &command["error"];
        let failed = !error.is_null();
        let message = if failed { text(error, "message")? } else { "" };
        match pending.answer {
            WaitFor::Week { previous, said } => {
                if failed {
                    return Ok(
                        json!({ "action": "load_failed", "message": message, "assignments": false }),
                    );
                }
                let start = text(data, "week_start")?;
                let request = assignments_request(start);
                let answer = WaitFor::Assignments {
                    previous,
                    said,
                    week: data.clone(),
                };
                let effect = self.effects.send(request, answer, epoch, Some(ticket));
                Ok(json!({ "action": "request", "effect": effect }))
            }
            WaitFor::Assignments {
                previous,
                said,
                week,
            } => {
                if failed {
                    return Ok(
                        json!({ "action": "load_failed", "message": message, "assignments": true }),
                    );
                }
                let mut answer = self.install(&json!({
                    "previous": previous, "said": said, "week": week,
                    "assignments": data["assignments"], "selection": command["selection"],
                }))?;
                answer["action"] = json!("loaded");
                Ok(answer)
            }
            WaitFor::Save {
                written,
                destination,
                sent_repeats,
                held,
            } => {
                if failed {
                    let mut answer = self.save_failed(error)?;
                    answer["action"] = json!("save_failed");
                    return Ok(answer);
                }
                let mut answer = self.saved(&json!({
                    "data": data, "written": written, "held": held,
                    "sent_repeats": sent_repeats, "now": command["now"],
                    "shifted_week": flag(command, "shifted_week")?,
                }))?;
                answer["action"] = json!("saved");
                answer["destination"] = destination;
                answer["written"] = written;
                answer["repeat_notice"] = data["repeats"]["notice"].clone();
                answer["point_id"] =
                    json!(data["restore_point"]["id"].as_str().unwrap_or_default());
                answer["doubled"] = data["repeats"]["doubled_weeks"]
                    .as_array()
                    .map_or_else(|| json!([]), |weeks| json!(weeks));
                Ok(answer)
            }
            WaitFor::Delete if failed => {
                self.deleting = None;
                Ok(json!({ "action": "delete_failed", "words": format!("Not deleted. {message}") }))
            }
            WaitFor::Delete => {
                let answer = self.delete_ok(&json!({ "data": data, "ids": command["ids"] }))?;
                self.continue_delete(answer["request"].clone(), epoch, ticket, true)
            }
            WaitFor::DeletedWeek => {
                let week = if failed { &Value::Null } else { data };
                let answer = self.delete_read(&json!({ "week": week }))?;
                self.continue_delete(answer["request"].clone(), epoch, ticket, false)
            }
            WaitFor::Refresh { start, basis } => {
                if failed || self.week_start() != start {
                    return Ok(json!({ "action": "ignore" }));
                }
                self.refresh_assignments(
                    &json!({ "incoming": data["assignments"], "basis": basis }),
                )?;
                Ok(json!({ "action": "refreshed" }))
            }
        }
    }

    fn continue_delete(
        &mut self,
        request: Value,
        epoch: u64,
        ticket: u64,
        deleted: bool,
    ) -> Result<Value, String> {
        if request.is_null() {
            let answer = self.delete_finish()?;
            Ok(json!({ "action": "deleted", "words": answer["words"], "deleted": deleted }))
        } else {
            let effect = self
                .effects
                .send(request, WaitFor::DeletedWeek, epoch, Some(ticket));
            Ok(json!({ "action": "request", "effect": effect, "deleted": deleted }))
        }
    }
}
